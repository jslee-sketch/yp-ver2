"""
CS 분쟁(중재) 강화 라우터 — 3-way choice, 직접합의, 외부기관, 관리자 강제종결

Endpoints:
  POST   /v3/disputes                          — 분쟁 신청
  GET    /v3/disputes/my                       — 내 분쟁 목록
  POST   /v3/disputes/{id}/respond             — 상대방 반론 + 제안 (Phase 2)
  POST   /v3/disputes/{id}/choose              — 3-way 선택 (Phase 4/8)
  POST   /v3/disputes/{id}/round2-initiator    — R2 신청인 재반론
  POST   /v3/disputes/{id}/round2-respond      — R2 상대방 재반론
  POST   /v3/disputes/{id}/direct-agreement    — 직접 합의 등록 (결렬 후)
  POST   /v3/disputes/{id}/direct-agreement/accept — 직접 합의 수락/거절
  POST   /v3/disputes/{id}/external-filing     — 외부기관 접수 등록
  POST   /v3/disputes/admin/{id}/external-result — 외부기관 결과 반영 (관리자)
  POST   /v3/disputes/admin/{id}/force-close   — 관리자 강제 종결
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    CSReturnRequest,
    Dispute,
    RefundRequest,
    Reservation,
    ReservationSettlement,
    User,
)
from app.services.proposal_calculator import calculate_proposal_amount
from app.services.working_days import add_working_days

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v3/disputes", tags=["cs-disputes"])

# ── 기존 disputes 테이블에 새 컬럼 추가 (ALTER TABLE) ──
def _ensure_dispute_columns():
    """기존 SQLite disputes 테이블에 새 컬럼이 없으면 추가"""
    from app.database import engine
    new_cols = [
        ("rejected_request_id", "INTEGER"),
        ("initiator_comp_type", "VARCHAR(20)"),
        ("initiator_comp_amount", "FLOAT"),
        ("respondent_comp_type", "VARCHAR(20)"),
        ("respondent_comp_amount", "FLOAT"),
        ("ai_r1_comp_type", "VARCHAR(20)"),
        ("ai_r1_comp_amount", "FLOAT"),
        ("r2_initiator_comp_type", "VARCHAR(20)"),
        ("r2_initiator_comp_amount", "FLOAT"),
        ("r2_respondent_comp_type", "VARCHAR(20)"),
        ("r2_respondent_comp_amount", "FLOAT"),
        ("ai_r2_comp_type", "VARCHAR(20)"),
        ("ai_r2_comp_amount", "FLOAT"),
        ("r1_initiator_choice", "VARCHAR(20)"),
        ("r1_respondent_choice", "VARCHAR(20)"),
        ("r2_initiator_choice", "VARCHAR(20)"),
        ("r2_respondent_choice", "VARCHAR(20)"),
        ("agreed_comp_type", "VARCHAR(20)"),
        ("agreed_comp_amount", "FLOAT"),
        ("agreed_resolution", "VARCHAR(30)"),
        ("grace_deadline", "TIMESTAMP"),
        ("max_hold_deadline", "TIMESTAMP"),
        ("admin_decided", "BOOLEAN DEFAULT FALSE"),
        ("admin_decided_at", "TIMESTAMP"),
        ("admin_decision_basis", "VARCHAR(30)"),
        ("admin_decision_reason", "TEXT"),
        ("admin_decision_comp_type", "VARCHAR(20)"),
        ("admin_decision_comp_amount", "FLOAT"),
        ("admin_decision_resolution", "VARCHAR(30)"),
        ("post_failure_status", "VARCHAR(40)"),
        ("direct_agreement_requested_by", "INTEGER"),
        ("direct_agreement_comp_type", "VARCHAR(20)"),
        ("direct_agreement_comp_amount", "FLOAT"),
        ("direct_agreement_resolution", "VARCHAR(30)"),
        ("direct_agreement_description", "TEXT"),
        ("direct_agreement_accepted", "BOOLEAN"),
        ("direct_agreement_accepted_at", "TIMESTAMP"),
        ("external_agency_type", "VARCHAR(30)"),
        ("external_agency_case_number", "VARCHAR(100)"),
        ("external_agency_filed_at", "TIMESTAMP"),
        ("external_agency_filed_by", "INTEGER"),
        ("external_agency_evidence_urls", "TEXT DEFAULT '[]'"),
        ("external_agency_hold_extended", "BOOLEAN DEFAULT FALSE"),
        ("external_agency_hold_deadline", "TIMESTAMP"),
        ("external_result_received_at", "TIMESTAMP"),
        ("external_result_description", "TEXT"),
        ("external_result_document_urls", "TEXT DEFAULT '[]'"),
        ("external_result_comp_type", "VARCHAR(20)"),
        ("external_result_comp_amount", "FLOAT"),
        ("external_result_resolution", "VARCHAR(30)"),
        ("external_result_applied_by", "INTEGER"),
        ("external_result_applied_at", "TIMESTAMP"),
    ]
    try:
        with engine.connect() as conn:
            for col_name, col_type in new_cols:
                try:
                    conn.execute(
                        __import__("sqlalchemy").text(
                            f"ALTER TABLE disputes ADD COLUMN {col_name} {col_type}"
                        )
                    )
                    conn.commit()
                except Exception:
                    pass  # 이미 존재하는 컬럼은 무시
        print("[cs_disputes] ALTER TABLE disputes — columns ensured", flush=True)
    except Exception as e:
        print(f"[cs_disputes] ALTER TABLE skip: {e}", flush=True)

try:
    _ensure_dispute_columns()
except Exception:
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Pydantic schemas
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class FileDisputeBody(BaseModel):
    order_number: str
    reservation_id: int
    initiator_id: int
    respondent_id: int
    rejected_request_id: int
    claim: str
    evidence_urls: List[str] = Field(default_factory=list)
    compensation_type: str = "fixed"  # 'fixed' | 'percentage'
    compensation_amount: float = 0
    desired_resolution: str = "partial_refund"


class RespondBody(BaseModel):
    reply: str
    evidence_urls: List[str] = Field(default_factory=list)
    compensation_type: str = "fixed"
    compensation_amount: float = 0
    proposal_resolution: str = "partial_refund"


class ChooseBody(BaseModel):
    user_id: int
    chosen: str  # 'initiator' | 'ai' | 'respondent'


class Round2Body(BaseModel):
    user_id: int
    rebuttal: str
    evidence_urls: List[str] = Field(default_factory=list)
    compensation_type: str = "fixed"
    compensation_amount: float = 0
    proposal_resolution: str = "partial_refund"


class DirectAgreementBody(BaseModel):
    compensation_type: str = "fixed"
    compensation_amount: float = 0
    resolution: str = "partial_refund"
    description: str = ""


class DirectAgreementAcceptBody(BaseModel):
    user_id: int
    accepted: bool


class ExternalFilingBody(BaseModel):
    user_id: int
    agency_type: str  # 'kca' | 'small_claims' | 'other'
    case_number: str
    evidence_urls: List[str] = Field(default_factory=list)


class ExternalResultBody(BaseModel):
    result_description: str
    document_urls: List[str] = Field(default_factory=list)
    compensation_type: str = "fixed"
    compensation_amount: float = 0
    resolution: str = "partial_refund"


class ForceCloseBody(BaseModel):
    basis: str = "manual"  # 'ai_proposal' | 'manual'
    reason: str = ""
    compensation_type: str = "fixed"
    compensation_amount: float = 0
    resolution: str = "partial_refund"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helper: safe notification
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _safe_notify(user_id, event_type, variables, db):
    try:
        if user_id is None:
            return
        from app.services.notification_service import send_notification
        send_notification(db, user_id=user_id, event_type=event_type, variables=variables)
    except Exception:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helper: settle_dispute — 환불/정산 처리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _settle_dispute(dispute: Dispute, comp_type: str, comp_amount: float,
                    resolution: str, db: Session) -> dict:
    """
    분쟁 합의/결정 후 최종 정산 처리:
    1. comp_type(fixed/percentage) 기반 환불 금액 계산
    2. RefundRequest 생성
    3. ReservationSettlement 조정
    4. 정산 보류 해제
    5. Dispute 상태 → RESOLVED
    """
    reservation = db.query(Reservation).filter(
        Reservation.id == dispute.reservation_id
    ).first()
    if not reservation:
        return {"error": "예약을 찾을 수 없습니다"}

    total = reservation.amount_total or 0

    # 1. 환불 금액 계산
    if comp_type == "percentage":
        refund_amount = int(total * (comp_amount / 100.0))
    else:
        refund_amount = int(comp_amount)

    # 결제 금액 초과 방지
    refund_amount = max(0, min(refund_amount, total))

    # 2. RefundRequest 생성
    refund_req = RefundRequest(
        reservation_id=reservation.id,
        buyer_id=reservation.buyer_id,
        reason=f"dispute_{dispute.id}",
        reason_detail=f"분쟁 #{dispute.id} 합의: {resolution}",
        evidence_urls=dispute.evidence_urls or "[]",
        status="AUTO_APPROVED",
        dispute_id=dispute.id,
    )
    db.add(refund_req)

    # 3. ReservationSettlement 조정
    settlement = db.query(ReservationSettlement).filter(
        ReservationSettlement.reservation_id == reservation.id
    ).first()

    if settlement:
        if refund_amount >= total * 0.9:
            # 전액 환불 수준 → 정산 취소
            settlement.status = "CANCELLED"
            settlement.seller_payout_amount = 0
            settlement.platform_commission_amount = 0
        elif refund_amount > 0:
            # 부분 환불 → 정산 감액
            try:
                from app.services.refund_calculator import _load_raw_policy
                raw = _load_raw_policy()
                fee_rate = raw.get("money", {}).get("platform_fee_rate", 0.035)
            except Exception:
                fee_rate = 0.035

            remaining = max(0, total - refund_amount)
            ship_fee = reservation.amount_shipping or 0
            seller_base = max(0, remaining - ship_fee)
            settlement.seller_payout_amount = int(seller_base * (1 - fee_rate))
            settlement.platform_commission_amount = int(seller_base * fee_rate)
            settlement.status = "ADJUSTED"
        else:
            # 환불 금액 0 → 보류 해제만
            if settlement.status == "DISPUTE_HOLD":
                settlement.status = "READY"

        # DISPUTE_HOLD 해제
        if settlement.status == "DISPUTE_HOLD":
            settlement.status = "READY"

        settlement.dispute_closed_at = datetime.utcnow()

    # 4. Reservation 환불 추적 업데이트
    if refund_amount > 0:
        reservation.refunded_qty = (reservation.refunded_qty or 0) + (reservation.qty or 0)
        reservation.refunded_amount_total = (reservation.refunded_amount_total or 0) + refund_amount
        reservation.refund_type = "refund"

    # 5. Dispute 상태 → RESOLVED
    now = datetime.utcnow()
    dispute.status = "RESOLVED"
    dispute.closed_at = now
    dispute.closed_reason = f"settled_{resolution}"
    dispute.resolution_amount = refund_amount
    dispute.agreed_comp_type = comp_type
    dispute.agreed_comp_amount = comp_amount
    dispute.agreed_resolution = resolution

    db.commit()
    db.refresh(refund_req)

    # 알림
    _safe_notify(dispute.initiator_id, "DISPUTE_RESOLVED", {
        "dispute_id": dispute.id,
        "refund_amount": f"{refund_amount:,}",
    }, db)
    _safe_notify(dispute.respondent_id, "S_DISPUTE_RESOLVED", {
        "dispute_id": dispute.id,
        "refund_amount": f"{refund_amount:,}",
    }, db)

    return {
        "dispute_id": dispute.id,
        "status": "RESOLVED",
        "refund_request_id": refund_req.id,
        "refund_amount": refund_amount,
        "resolution": resolution,
        "settlement_status": settlement.status if settlement else None,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helper: _get_choice_proposal — 3-way 선택에서 선택된 제안 내용 반환
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_choice_proposal(dispute: Dispute, chosen: str, round_num: int) -> dict:
    """chosen='initiator'|'ai'|'respondent' → {comp_type, comp_amount, resolution}"""
    prefix = f"r{round_num}_"

    if chosen == "initiator":
        if round_num == 2:
            return {
                "comp_type": dispute.r2_initiator_comp_type or dispute.initiator_comp_type or "fixed",
                "comp_amount": dispute.r2_initiator_comp_amount or dispute.initiator_comp_amount or 0,
                "resolution": (getattr(dispute, "r2_initiator_proposal_type", None)
                               or dispute.requested_resolution or "partial_refund"),
            }
        return {
            "comp_type": dispute.initiator_comp_type or "fixed",
            "comp_amount": dispute.initiator_comp_amount or dispute.requested_amount or 0,
            "resolution": dispute.requested_resolution or "partial_refund",
        }
    elif chosen == "ai":
        return {
            "comp_type": getattr(dispute, f"ai_r{round_num}_comp_type", None) or "fixed",
            "comp_amount": getattr(dispute, f"ai_r{round_num}_comp_amount", None)
                           or getattr(dispute, f"{prefix}ai_recommendation_amount", 0) or 0,
            "resolution": getattr(dispute, f"{prefix}ai_recommendation", "partial_refund") or "partial_refund",
        }
    elif chosen == "respondent":
        if round_num == 2:
            return {
                "comp_type": dispute.r2_respondent_comp_type or dispute.respondent_comp_type or "fixed",
                "comp_amount": dispute.r2_respondent_comp_amount or dispute.respondent_comp_amount or 0,
                "resolution": (getattr(dispute, "r2_respondent_proposal_type", None)
                               or dispute.r1_respondent_proposal_type or "partial_refund"),
            }
        return {
            "comp_type": dispute.respondent_comp_type or "fixed",
            "comp_amount": dispute.respondent_comp_amount or dispute.r1_respondent_proposal_amount or 0,
            "resolution": dispute.r1_respondent_proposal_type or "partial_refund",
        }

    return {"comp_type": "fixed", "comp_amount": 0, "resolution": "no_action"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. POST / — 분쟁 신청
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("")
def file_dispute(body: FileDisputeBody, db: Session = Depends(get_db)):
    # 주문 존재 확인
    reservation = db.query(Reservation).filter(
        Reservation.id == body.reservation_id,
        Reservation.order_number == body.order_number,
    ).first()
    if not reservation:
        raise HTTPException(404, "주문을 찾을 수 없습니다 (order_number/reservation_id 불일치)")

    # 결제 완료 확인
    if reservation.paid_at is None:
        raise HTTPException(400, "결제가 완료되지 않은 주문입니다")

    # 거절된 CS 요청 확인
    rejected_req = db.query(CSReturnRequest).filter(
        CSReturnRequest.id == body.rejected_request_id,
        CSReturnRequest.status == "SELLER_REJECTED",
    ).first()
    if not rejected_req:
        raise HTTPException(400, "거절된 CS 요청을 찾을 수 없습니다 (SELLER_REJECTED 상태만 가능)")

    # 동일 예약에 활성 분쟁 없는지 확인
    active_dispute = db.query(Dispute).filter(
        Dispute.reservation_id == body.reservation_id,
        Dispute.status.notin_(["RESOLVED", "REJECTED", "AUTO_CLOSED", "ACCEPTED"]),
    ).first()
    if active_dispute:
        raise HTTPException(409, f"이미 활성 분쟁이 존재합니다 (dispute #{active_dispute.id})")

    now = datetime.utcnow()
    total = reservation.amount_total or 0

    # 보상 금액 계산
    calculated = calculate_proposal_amount(body.compensation_type, body.compensation_amount, total)

    # initiator/respondent role 결정
    if body.initiator_id == reservation.buyer_id:
        initiator_role = "buyer"
    else:
        initiator_role = "seller"

    dispute = Dispute(
        reservation_id=reservation.id,
        initiator_id=body.initiator_id,
        respondent_id=body.respondent_id,
        initiator_role=initiator_role,
        category=rejected_req.reason_code or "기타",
        title=f"분쟁: {body.order_number}",
        description=body.claim,
        evidence_urls=json.dumps(body.evidence_urls, ensure_ascii=False),
        requested_resolution=body.desired_resolution,
        requested_amount=calculated,
        rejected_request_id=body.rejected_request_id,
        status="ROUND1_RESPONSE",
        current_round=1,
        r1_respondent_deadline=add_working_days(now, 3),
        # 구조화 보상금
        initiator_comp_type=body.compensation_type,
        initiator_comp_amount=body.compensation_amount,
        initiator_amount_type=body.compensation_type,
        initiator_amount_value=body.compensation_amount,
        initiator_amount_calculated=calculated,
    )
    db.add(dispute)

    # 정산 보류
    settlement = db.query(ReservationSettlement).filter(
        ReservationSettlement.reservation_id == reservation.id
    ).first()
    if settlement and settlement.status not in ("CANCELLED", "DISPUTE_HOLD"):
        settlement.status = "DISPUTE_HOLD"
        settlement.dispute_opened_at = now

    # Reservation 분쟁 플래그
    reservation.is_disputed = True
    reservation.dispute_opened_at = now

    db.commit()
    db.refresh(dispute)

    _safe_notify(body.respondent_id, "S_DISPUTE_FILED", {
        "dispute_id": dispute.id,
        "order_number": body.order_number,
        "deadline": str(dispute.r1_respondent_deadline),
    }, db)

    return {
        "dispute_id": dispute.id,
        "status": dispute.status,
        "respondent_deadline": str(dispute.r1_respondent_deadline),
        "calculated_amount": calculated,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. GET /my — 내 분쟁 목록
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/my")
def my_disputes(user_id: int = Query(...), db: Session = Depends(get_db)):
    disputes = (
        db.query(Dispute)
        .filter(
            (Dispute.initiator_id == user_id) | (Dispute.respondent_id == user_id)
        )
        .order_by(Dispute.created_at.desc())
        .all()
    )
    results = []
    for d in disputes:
        reservation = db.query(Reservation).filter(Reservation.id == d.reservation_id).first()
        results.append({
            "id": d.id,
            "reservation_id": d.reservation_id,
            "order_number": getattr(reservation, "order_number", None) if reservation else None,
            "status": d.status,
            "post_failure_status": getattr(d, "post_failure_status", None),
            "category": d.category,
            "title": d.title,
            "current_round": d.current_round,
            "initiator_id": d.initiator_id,
            "respondent_id": d.respondent_id,
            "my_role": "initiator" if d.initiator_id == user_id else "respondent",
            "resolution_amount": d.resolution_amount,
            "created_at": str(d.created_at) if d.created_at else None,
            "closed_at": str(d.closed_at) if d.closed_at else None,
        })
    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. POST /{id}/respond — 상대방 반론 + 제안 (Phase 2)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/{dispute_id}/respond")
def respond_to_dispute(dispute_id: int, body: RespondBody, db: Session = Depends(get_db)):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(404, "분쟁을 찾을 수 없습니다")
    if dispute.status != "ROUND1_RESPONSE":
        raise HTTPException(400, "현재 Round 1 반론 단계가 아닙니다")
    if dispute.r1_respondent_deadline and datetime.utcnow() > dispute.r1_respondent_deadline:
        raise HTTPException(400, "반론 기한이 만료되었습니다")

    reservation = db.query(Reservation).filter(Reservation.id == dispute.reservation_id).first()
    total = (reservation.amount_total if reservation else 0) or 0

    calculated = calculate_proposal_amount(body.compensation_type, body.compensation_amount, total)
    now = datetime.utcnow()

    dispute.r1_respondent_reply = body.reply
    dispute.r1_respondent_evidence_urls = json.dumps(body.evidence_urls, ensure_ascii=False)
    dispute.r1_respondent_proposal_type = body.proposal_resolution
    dispute.r1_respondent_proposal_amount = calculated
    dispute.r1_respondent_at = now

    # 구조화 보상금
    dispute.respondent_comp_type = body.compensation_type
    dispute.respondent_comp_amount = body.compensation_amount
    dispute.r1_respondent_amount_type = body.compensation_type
    dispute.r1_respondent_amount_value = body.compensation_amount
    dispute.r1_respondent_amount_calculated = calculated

    # AI 중재 단계로 전환
    dispute.status = "ROUND1_AI"
    db.commit()

    # AI 중재 실행 (기존 서비스 활용)
    try:
        from app.services.dispute_service import run_ai_mediation
        result = run_ai_mediation(dispute_id, round_num=1, db=db)
        return result
    except Exception as e:
        logger.warning(f"AI 중재 실행 실패: {e}")
        # fallback: ROUND1_REVIEW로 수동 전환
        dispute.status = "ROUND1_REVIEW"
        dispute.r1_initiator_deadline = add_working_days(now, 1)
        db.commit()
        return {
            "status": dispute.status,
            "message": "반론 접수 완료. AI 중재 처리 중 오류 발생, 관리자 검토 대기.",
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. POST /{id}/choose — 3-way 선택 (Phase 4/8)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/{dispute_id}/choose")
def choose_proposal(dispute_id: int, body: ChooseBody, db: Session = Depends(get_db)):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(404, "분쟁을 찾을 수 없습니다")

    if dispute.status not in ("ROUND1_REVIEW", "ROUND2_REVIEW"):
        raise HTTPException(400, f"현재 선택 단계가 아닙니다 (status={dispute.status})")

    if body.chosen not in ("initiator", "ai", "respondent"):
        raise HTTPException(400, "chosen 값은 'initiator', 'ai', 'respondent' 중 하나여야 합니다")

    round_num = dispute.current_round
    prefix = f"r{round_num}_"

    # 역할 확인 + 선택 기록
    if body.user_id == dispute.initiator_id:
        setattr(dispute, f"{prefix}initiator_choice", body.chosen)
        setattr(dispute, f"{prefix}initiator_decision", "choose")
        setattr(dispute, f"{prefix}initiator_decision_at", datetime.utcnow())
    elif body.user_id == dispute.respondent_id:
        setattr(dispute, f"{prefix}respondent_choice", body.chosen)
        setattr(dispute, f"{prefix}respondent_decision", "choose")
        setattr(dispute, f"{prefix}respondent_decision_at", datetime.utcnow())
    else:
        raise HTTPException(403, "분쟁 당사자가 아닙니다")

    db.commit()

    # 양쪽 모두 선택했는지 확인
    init_choice = getattr(dispute, f"{prefix}initiator_choice")
    resp_choice = getattr(dispute, f"{prefix}respondent_choice")

    if not init_choice or not resp_choice:
        who = "신청인" if body.user_id == dispute.initiator_id else "상대방"
        return {"status": dispute.status, "message": f"{who} 선택 완료. 상대방 선택 대기 중."}

    # ── 양쪽 모두 선택 완료: 결과 판정 ──

    # Case 1: 신청인이 상대방 제안을 선택 → 즉시 합의
    if init_choice == "respondent":
        proposal = _get_choice_proposal(dispute, "respondent", round_num)
        return _settle_dispute(dispute, proposal["comp_type"], proposal["comp_amount"],
                               proposal["resolution"], db)

    # Case 2: 양쪽이 같은 것을 선택 → 즉시 합의
    if init_choice == resp_choice:
        proposal = _get_choice_proposal(dispute, init_choice, round_num)
        return _settle_dispute(dispute, proposal["comp_type"], proposal["comp_amount"],
                               proposal["resolution"], db)

    # Case 3: 다른 선택 → Round 2 or 결렬
    if round_num == 1:
        # Round 2로 전환
        now = datetime.utcnow()
        dispute.current_round = 2
        dispute.status = "ROUND2_RESPONSE"
        dispute.r2_rebuttal_by = "initiator,respondent"
        dispute.r2_rebuttal_deadline = add_working_days(now, 2)
        db.commit()

        _safe_notify(dispute.initiator_id, "DISPUTE_ROUND2", {"dispute_id": dispute.id}, db)
        _safe_notify(dispute.respondent_id, "S_DISPUTE_ROUND2", {"dispute_id": dispute.id}, db)

        return {
            "status": "ROUND2_RESPONSE",
            "message": "1차 합의 실패. 2차 라운드가 시작됩니다.",
            "deadline": str(dispute.r2_rebuttal_deadline),
        }

    # Round 2에서도 불일치 → 결렬 (FAILED)
    now = datetime.utcnow()
    dispute.status = "FAILED"
    dispute.closed_at = now
    dispute.closed_reason = "round2_choice_mismatch"
    dispute.post_failure_status = "GRACE_PERIOD"
    dispute.grace_deadline = now + timedelta(days=7)
    dispute.max_hold_deadline = now + timedelta(days=90)
    dispute.legal_guidance_sent = True
    dispute.legal_guidance_sent_at = now
    db.commit()

    # 정산 보류 유지 (LEGAL_HOLD)
    settlement = db.query(ReservationSettlement).filter(
        ReservationSettlement.reservation_id == dispute.reservation_id
    ).first()
    if settlement:
        settlement.status = "LEGAL_HOLD"
        db.commit()

    _safe_notify(dispute.initiator_id, "DISPUTE_FAILED", {
        "dispute_id": dispute.id,
        "grace_deadline": str(dispute.grace_deadline),
    }, db)
    _safe_notify(dispute.respondent_id, "S_DISPUTE_FAILED", {
        "dispute_id": dispute.id,
        "grace_deadline": str(dispute.grace_deadline),
    }, db)

    return {
        "status": "FAILED",
        "post_failure_status": "GRACE_PERIOD",
        "grace_deadline": str(dispute.grace_deadline),
        "message": "2차 중재 결렬. 7일 유예기간 내 직접 합의 또는 외부기관 접수 가능.",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. POST /{id}/round2-initiator — R2 신청인 재반론
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/{dispute_id}/round2-initiator")
def round2_initiator(dispute_id: int, body: Round2Body, db: Session = Depends(get_db)):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(404, "분쟁을 찾을 수 없습니다")
    if dispute.status != "ROUND2_RESPONSE":
        raise HTTPException(400, "현재 Round 2 재반론 단계가 아닙니다")
    if body.user_id != dispute.initiator_id:
        raise HTTPException(403, "신청인만 제출할 수 있습니다")
    if dispute.r2_rebuttal_deadline and datetime.utcnow() > dispute.r2_rebuttal_deadline:
        raise HTTPException(400, "재반론 기한이 만료되었습니다")

    reservation = db.query(Reservation).filter(Reservation.id == dispute.reservation_id).first()
    total = (reservation.amount_total if reservation else 0) or 0
    calculated = calculate_proposal_amount(body.compensation_type, body.compensation_amount, total)

    dispute.r2_initiator_rebuttal = body.rebuttal
    dispute.r2_initiator_evidence_urls = json.dumps(body.evidence_urls, ensure_ascii=False)
    dispute.r2_initiator_proposal_type = body.proposal_resolution
    dispute.r2_initiator_proposal_amount = calculated
    dispute.r2_initiator_comp_type = body.compensation_type
    dispute.r2_initiator_comp_amount = body.compensation_amount
    dispute.r2_initiator_amount_type = body.compensation_type
    dispute.r2_initiator_amount_value = body.compensation_amount
    dispute.r2_initiator_amount_calculated = calculated
    dispute.r2_rebuttal_at = datetime.utcnow()

    db.commit()

    # 상대방도 제출 완료인지 확인
    if dispute.r2_respondent_rebuttal:
        dispute.status = "ROUND2_AI"
        db.commit()
        try:
            from app.services.dispute_service import run_ai_mediation
            return run_ai_mediation(dispute_id, round_num=2, db=db)
        except Exception as e:
            logger.warning(f"R2 AI 중재 실패: {e}")
            dispute.status = "ROUND2_REVIEW"
            dispute.r2_initiator_deadline = add_working_days(datetime.utcnow(), 1)
            db.commit()
            return {"status": dispute.status, "message": "AI 중재 오류, 관리자 검토 대기."}

    return {"status": "ROUND2_RESPONSE", "message": "신청인 재반론 제출 완료. 상대방 제출 대기."}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. POST /{id}/round2-respond — R2 상대방 재반론
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/{dispute_id}/round2-respond")
def round2_respond(dispute_id: int, body: Round2Body, db: Session = Depends(get_db)):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(404, "분쟁을 찾을 수 없습니다")
    if dispute.status != "ROUND2_RESPONSE":
        raise HTTPException(400, "현재 Round 2 재반론 단계가 아닙니다")
    if body.user_id != dispute.respondent_id:
        raise HTTPException(403, "상대방만 제출할 수 있습니다")
    if dispute.r2_rebuttal_deadline and datetime.utcnow() > dispute.r2_rebuttal_deadline:
        raise HTTPException(400, "재반론 기한이 만료되었습니다")

    reservation = db.query(Reservation).filter(Reservation.id == dispute.reservation_id).first()
    total = (reservation.amount_total if reservation else 0) or 0
    calculated = calculate_proposal_amount(body.compensation_type, body.compensation_amount, total)

    dispute.r2_respondent_rebuttal = body.rebuttal
    dispute.r2_respondent_evidence_urls = json.dumps(body.evidence_urls, ensure_ascii=False)
    dispute.r2_respondent_proposal_type = body.proposal_resolution
    dispute.r2_respondent_proposal_amount = calculated
    dispute.r2_respondent_comp_type = body.compensation_type
    dispute.r2_respondent_comp_amount = body.compensation_amount
    dispute.r2_respondent_amount_type = body.compensation_type
    dispute.r2_respondent_amount_value = body.compensation_amount
    dispute.r2_respondent_amount_calculated = calculated
    dispute.r2_rebuttal_at = datetime.utcnow()

    db.commit()

    # 신청인도 제출 완료인지 확인
    if dispute.r2_initiator_rebuttal:
        dispute.status = "ROUND2_AI"
        db.commit()
        try:
            from app.services.dispute_service import run_ai_mediation
            return run_ai_mediation(dispute_id, round_num=2, db=db)
        except Exception as e:
            logger.warning(f"R2 AI 중재 실패: {e}")
            dispute.status = "ROUND2_REVIEW"
            dispute.r2_respondent_deadline = add_working_days(datetime.utcnow(), 1)
            db.commit()
            return {"status": dispute.status, "message": "AI 중재 오류, 관리자 검토 대기."}

    return {"status": "ROUND2_RESPONSE", "message": "상대방 재반론 제출 완료. 신청인 제출 대기."}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. POST /{id}/direct-agreement — 직접 합의 등록 (결렬 후)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/{dispute_id}/direct-agreement")
def register_direct_agreement(
    dispute_id: int, body: DirectAgreementBody, db: Session = Depends(get_db)
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(404, "분쟁을 찾을 수 없습니다")
    if dispute.status != "FAILED":
        raise HTTPException(400, "결렬(FAILED) 상태에서만 직접 합의를 등록할 수 있습니다")
    if dispute.post_failure_status != "GRACE_PERIOD":
        raise HTTPException(400, f"유예 기간(GRACE_PERIOD)이 아닙니다 (현재: {dispute.post_failure_status})")

    # 유예 기한 초과 확인
    if dispute.grace_deadline and datetime.utcnow() > dispute.grace_deadline:
        raise HTTPException(400, "유예 기간이 만료되었습니다")

    now = datetime.utcnow()
    dispute.post_failure_status = "DIRECT_AGREEMENT_PENDING"
    dispute.direct_agreement_requested_by = dispute.initiator_id  # 보통 신청인이 등록
    dispute.direct_agreement_comp_type = body.compensation_type
    dispute.direct_agreement_comp_amount = body.compensation_amount
    dispute.direct_agreement_resolution = body.resolution
    dispute.direct_agreement_description = body.description

    db.commit()

    # 상대방에게 알림
    _safe_notify(dispute.respondent_id, "DISPUTE_DIRECT_AGREEMENT_PROPOSAL", {
        "dispute_id": dispute.id,
        "compensation": f"{body.compensation_amount}",
    }, db)

    return {
        "dispute_id": dispute.id,
        "post_failure_status": "DIRECT_AGREEMENT_PENDING",
        "message": "직접 합의 제안이 등록되었습니다. 상대방 수락 대기 중.",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 8. POST /{id}/direct-agreement/accept — 직접 합의 수락/거절
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/{dispute_id}/direct-agreement/accept")
def accept_direct_agreement(
    dispute_id: int, body: DirectAgreementAcceptBody, db: Session = Depends(get_db)
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(404, "분쟁을 찾을 수 없습니다")
    if dispute.post_failure_status != "DIRECT_AGREEMENT_PENDING":
        raise HTTPException(400, "직접 합의 대기(DIRECT_AGREEMENT_PENDING) 상태가 아닙니다")

    # 제안자가 아닌 상대방만 수락/거절 가능
    if body.user_id == dispute.direct_agreement_requested_by:
        raise HTTPException(400, "제안자는 수락/거절할 수 없습니다 (상대방만 가능)")

    now = datetime.utcnow()
    dispute.direct_agreement_accepted = body.accepted
    dispute.direct_agreement_accepted_at = now

    if body.accepted:
        dispute.post_failure_status = "DIRECT_AGREEMENT_ACCEPTED"
        db.commit()

        # 합의 실행 → settle_dispute
        result = _settle_dispute(
            dispute,
            comp_type=dispute.direct_agreement_comp_type or "fixed",
            comp_amount=dispute.direct_agreement_comp_amount or 0,
            resolution=dispute.direct_agreement_resolution or "partial_refund",
            db=db,
        )
        return {**result, "message": "직접 합의 수락. 환불/정산 처리 완료."}
    else:
        # 거절 → GRACE_PERIOD로 복귀
        dispute.post_failure_status = "GRACE_PERIOD"
        db.commit()

        _safe_notify(dispute.direct_agreement_requested_by, "DISPUTE_DIRECT_AGREEMENT_REJECTED", {
            "dispute_id": dispute.id,
        }, db)

        return {
            "dispute_id": dispute.id,
            "post_failure_status": "GRACE_PERIOD",
            "message": "직접 합의가 거절되었습니다. 유예 기간 내 재제안 또는 외부기관 접수 가능.",
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 9. POST /{id}/external-filing — 외부기관 접수 등록
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/{dispute_id}/external-filing")
def register_external_filing(
    dispute_id: int, body: ExternalFilingBody, db: Session = Depends(get_db)
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(404, "분쟁을 찾을 수 없습니다")
    if dispute.status != "FAILED":
        raise HTTPException(400, "결렬(FAILED) 상태에서만 외부기관 접수를 등록할 수 있습니다")
    if dispute.post_failure_status not in ("GRACE_PERIOD", "DIRECT_AGREEMENT_PENDING", None):
        raise HTTPException(400, f"외부기관 접수 불가 상태입니다 (현재: {dispute.post_failure_status})")

    # 당사자 확인
    if body.user_id not in (dispute.initiator_id, dispute.respondent_id):
        raise HTTPException(403, "분쟁 당사자만 외부기관 접수를 등록할 수 있습니다")

    now = datetime.utcnow()
    dispute.post_failure_status = "EXTERNAL_FILED"
    dispute.external_agency_type = body.agency_type
    dispute.external_agency_case_number = body.case_number
    dispute.external_agency_filed_at = now
    dispute.external_agency_filed_by = body.user_id
    dispute.external_agency_evidence_urls = json.dumps(body.evidence_urls, ensure_ascii=False)

    # 정산 보류 연장 → max_hold_deadline까지
    if dispute.max_hold_deadline:
        dispute.external_agency_hold_extended = True
        dispute.external_agency_hold_deadline = dispute.max_hold_deadline
    else:
        # max_hold_deadline 미설정 시 90일 연장
        dispute.external_agency_hold_extended = True
        max_deadline = now + timedelta(days=90)
        dispute.max_hold_deadline = max_deadline
        dispute.external_agency_hold_deadline = max_deadline

    db.commit()

    # 상대방 알림
    other_id = dispute.respondent_id if body.user_id == dispute.initiator_id else dispute.initiator_id
    _safe_notify(other_id, "DISPUTE_EXTERNAL_FILED", {
        "dispute_id": dispute.id,
        "agency_type": body.agency_type,
        "case_number": body.case_number,
    }, db)

    return {
        "dispute_id": dispute.id,
        "post_failure_status": "EXTERNAL_FILED",
        "agency_type": body.agency_type,
        "case_number": body.case_number,
        "hold_deadline": str(dispute.external_agency_hold_deadline),
        "message": "외부기관 접수 등록 완료. 결과 수신 시 관리자가 반영합니다.",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 10. POST /admin/{id}/external-result — 관리자: 외부기관 결과 반영
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/admin/{dispute_id}/external-result")
def apply_external_result(
    dispute_id: int, body: ExternalResultBody, db: Session = Depends(get_db)
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(404, "분쟁을 찾을 수 없습니다")
    if dispute.post_failure_status != "EXTERNAL_FILED":
        raise HTTPException(400, "외부기관 접수(EXTERNAL_FILED) 상태가 아닙니다")

    now = datetime.utcnow()
    dispute.post_failure_status = "EXTERNAL_RESULT_RECEIVED"
    dispute.external_result_received_at = now
    dispute.external_result_description = body.result_description
    dispute.external_result_document_urls = json.dumps(body.document_urls, ensure_ascii=False)
    dispute.external_result_comp_type = body.compensation_type
    dispute.external_result_comp_amount = body.compensation_amount
    dispute.external_result_resolution = body.resolution
    dispute.external_result_applied_at = now

    db.commit()

    # 외부기관 결과에 따라 정산 처리
    result = _settle_dispute(
        dispute,
        comp_type=body.compensation_type,
        comp_amount=body.compensation_amount,
        resolution=body.resolution,
        db=db,
    )

    return {
        **result,
        "message": "외부기관 결과 반영 + 정산 처리 완료.",
        "external_result": body.result_description,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 11. POST /admin/{id}/force-close — 관리자 강제 종결
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/admin/{dispute_id}/force-close")
def admin_force_close(
    dispute_id: int, body: ForceCloseBody, db: Session = Depends(get_db)
):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(404, "분쟁을 찾을 수 없습니다")

    # 이미 종결된 분쟁은 강제 종결 불가
    if dispute.status == "RESOLVED":
        raise HTTPException(400, "이미 해결된 분쟁입니다")

    now = datetime.utcnow()

    # 관리자 결정 기록
    dispute.admin_decided = True
    dispute.admin_decided_at = now
    dispute.admin_decision_basis = body.basis
    dispute.admin_decision_reason = body.reason
    dispute.admin_decision_comp_type = body.compensation_type
    dispute.admin_decision_comp_amount = body.compensation_amount
    dispute.admin_decision_resolution = body.resolution
    dispute.post_failure_status = "ADMIN_FORCE_CLOSED"

    db.commit()

    # 정산 처리
    result = _settle_dispute(
        dispute,
        comp_type=body.compensation_type,
        comp_amount=body.compensation_amount,
        resolution=body.resolution,
        db=db,
    )

    return {
        **result,
        "message": "관리자 강제 종결 + 정산 처리 완료.",
        "admin_basis": body.basis,
        "admin_reason": body.reason,
    }
