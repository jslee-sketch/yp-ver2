# app/routers/actuators.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app import models, schemas, crud

from datetime import datetime, timezone
from app.routers.notifications import create_notification

import logging


router = APIRouter(
    prefix="/actuators",
    tags=["actuators (NO-AUTH DEV)"],
)


@router.post("/", response_model=schemas.ActuatorOut)
def create_actuator(
    body: schemas.ActuatorCreate,
    db: Session = Depends(get_db),
):
    """
    Actuator 신규 등록 (DEV용: 바로 ACTIVE 상태)
    """
    act = models.Actuator(
        name=body.name,
        email=body.email,
        phone=body.phone,
        settlement_info=body.settlement_info,
        status="ACTIVE",  # 초기엔 바로 ACTIVE, 나중에 심사 플로우 넣을 수 있음
    )
    db.add(act)
    db.commit()
    db.refresh(act)

    # ---------------------------------------------------------
    # ✅ Evidence Pack (actuator_create_v1)
    #    위치: db.commit(); db.refresh(act) 직후, return 직전
    # ---------------------------------------------------------
    try:
        from app.routers.activity_log import log_evidence_pack
        from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

        evidence_pack = build_evidence_pack_v0(
            db,
            kind="actuator_create_v1",
            payload={
                "actuator": act,
                "actor": "admin_create_actuator",   # DEV NO-AUTH라 admin 취급
                "expected_source": "routers.actuators.create_actuator",
                "before": {},
                "run_id": None,
                "request_id": None,
                "notes": [],
            },
        )

        aid = int(getattr(act, "id", 0) or 0)
        log_evidence_pack(
            db,
            evidence_pack_version="actuator_create_v1",
            actor_type="SYSTEM",
            actor_id=None,
            # actuator는 buyer/seller처럼 전용 컬럼이 없으니 meta에 id 포함이 핵심
            idempotency_key=f"evidence:actuator_create_v1:{aid}",
            meta=evidence_pack,
        )
    except Exception:
        pass

    return act


@router.get("/{actuator_id}", response_model=schemas.ActuatorOut)
def get_actuator(
    actuator_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    Actuator 단건 조회
    """
    act = db.query(models.Actuator).get(actuator_id)
    if not act:
        raise HTTPException(status_code=404, detail="Actuator not found")
    return act


@router.get("/", response_model=List[schemas.ActuatorOut])
def list_actuators(db: Session = Depends(get_db)):
    """
    Actuator 전체 조회 (DEV용)
    """
    return db.query(models.Actuator).all()


@router.post("/{actuator_id}/status/{new_status}", response_model=schemas.ActuatorOut)
def update_actuator_status(
    actuator_id: int,
    new_status: str,
    db: Session = Depends(get_db),
):
    """
    Actuator 상태 변경
    - new_status: ACTIVE / SUSPENDED / CLOSED
    """
    if new_status not in {"ACTIVE", "SUSPENDED", "CLOSED"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    act = db.query(models.Actuator).get(actuator_id)
    if not act:
        raise HTTPException(status_code=404, detail="Actuator not found")

    act.status = new_status
    db.commit()
    db.refresh(act)
    return act

# --------------------------------------------
# 💰 [DEV] Actuator 커미션 로그 조회
# --------------------------------------------
@router.get(
    "/{actuator_id}/commissions",
    response_model=List[schemas.ActuatorCommissionOut],
    summary="[DEV] 해당 Actuator의 커미션 로그 목록",
)
def list_actuator_commissions(
    actuator_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    - 결제 성공 시 쌓인 ActuatorCommission 로그를 확인하기 위한 DEV용 API
    - 나중에 운영에서는 기간/페이지네이션 등 추가하면 됨.
    """
    rows = (
        db.query(models.ActuatorCommission)
          .filter(models.ActuatorCommission.actuator_id == actuator_id)
          .order_by(models.ActuatorCommission.id.desc())
          .all()
    )
    return rows


# --------------------------------------------
# 💰 Actuator 커미션 지급 처리 + 알림
# --------------------------------------------
@router.post(
    "/commissions/{commission_id}/mark_paid",
    response_model=schemas.ActuatorCommissionOut,
    summary="Actuator 커미션 지급 처리 (DEV용)",
)
def mark_actuator_commission_paid(
    commission_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    - 특정 ActuatorCommission 을 '지급 완료' 상태로 바꾸고
    - 해당 Actuator 에게 '커미션 지급 완료' 알림을 보낸다.
    - 실제 운용에서는 배치/정산 시스템에서 이 API 를 호출하거나,
      내부 함수로만 써도 된다.
    """
    comm = db.query(models.ActuatorCommission).get(commission_id)
    if not comm:
        raise HTTPException(status_code=404, detail="ActuatorCommission not found")

    now = datetime.now(timezone.utc)

    # 모델에 따라 필드 이름이 다를 수 있으니 getattr/setattr 패턴으로 안전하게 처리
    # 예: status, paid_at, paid_amount 등은 네 모델 정의에 맞게 조정 가능
    if hasattr(comm, "status"):
        comm.status = "PAID"
    if hasattr(comm, "paid_at"):
        comm.paid_at = now

    db.add(comm)
    db.commit()
    db.refresh(comm)

    # 🔔 Actuator 알림: "커미션 지급 완료"
    try:
        actuator_id = int(getattr(comm, "actuator_id", 0) or 0)
        if actuator_id > 0:
            amount = getattr(comm, "amount", None)
            deal_id = getattr(comm, "deal_id", None)
            offer_id = getattr(comm, "offer_id", None)
            reservation_id = getattr(comm, "reservation_id", None)

            # 금액 문구 구성
            amount_text = f"{int(amount)}원" if isinstance(amount, (int, float)) else "커미션"

            create_notification(
                db,
                user_id=actuator_id,
                type="actuator_commission_paid",
                title="추천 보상이 지급되었습니다.",
                message=(
                    f"딜 #{deal_id or '-'} / 오퍼 #{offer_id or '-'} / 예약 #{reservation_id or '-'} "
                    f"관련 {amount_text}이(가) 정산되었습니다."
                ),
                meta={
                    "role": "actuator",
                    "deal_id": deal_id,
                    "offer_id": offer_id,
                    "reservation_id": reservation_id,
                    "commission_id": comm.id,
                    "amount": amount,
                },
            )
    except Exception as notify_err:
        import logging
        logging.exception(
            "failed to create actuator_commission_paid notification",
            exc_info=notify_err,
        )

    return comm


# --------------------------------------------
# 💸 [ADMIN/DEV] 지급 시점이 지난 커미션 일괄 지급
# --------------------------------------------

@router.post(
    "/commissions/payout-due",
    summary="[ADMIN/DEV] ready_at 지난 액츄에이터 커미션 일괄 지급 처리",
)
def payout_due_actuator_commissions(
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    - status = 'PENDING'
    - (ready_at 컬럼이 있을 경우에만) ready_at <= now 조건으로 지급
    - ready_at 컬럼이 없으면 200 + 아무 것도 지급하지 않음(노트 반환)
    """
    now = datetime.now(timezone.utc)

    # ✅ 모델에 ready_at 컬럼이 없으면 안전하게 no-op
    has_ready_at = hasattr(models.ActuatorCommission, "ready_at")
    if not has_ready_at:
        return {
            "paid_count": 0,
            "paid_ids": [],
            "note": "ActuatorCommission.ready_at 컬럼이 없어 지급 처리 스킵됨. 모델/마이그레이션 추가 필요."
        }

    q = (
        db.query(models.ActuatorCommission)
          .filter(
              models.ActuatorCommission.status == "PENDING",
              models.ActuatorCommission.ready_at.isnot(None),
              models.ActuatorCommission.ready_at <= now,
          )
          .order_by(models.ActuatorCommission.id)
          .limit(limit)
    )
    rows = q.all()

    if not rows:
        return {"paid_count": 0, "paid_ids": []}

    paid_ids = []
    for comm in rows:
        comm.status = "PAID"
        comm.paid_at = now
        paid_ids.append(comm.id)

    db.commit()

    return {"paid_count": len(paid_ids), "paid_ids": paid_ids}

# ---------------------------------------------
# 액츄에이터 커미션 요약
# ---------------------------------------------
@router.get(
    "/{actuator_id}/commissions/summary",
    summary="액츄에이터 커미션 요약",
)
def get_actuator_commission_summary(
    actuator_id: int,
    db: Session = Depends(get_db),
):
    """
    커미션 요약:
    - total_count/amount
    - pending_count/amount
    - (ready_at 컬럼이 있을 때만) ready_count/amount
    - paid_count/amount
    """
    now = datetime.now(timezone.utc)
    base_q = db.query(models.ActuatorCommission).filter(
        models.ActuatorCommission.actuator_id == actuator_id
    )

    # 전체
    total_count = base_q.count()
    total_amount = (
        base_q.with_entities(func.coalesce(func.sum(models.ActuatorCommission.amount), 0))
             .scalar() or 0
    )

    # PENDING
    pending_q = base_q.filter(models.ActuatorCommission.status == "PENDING")
    pending_count = pending_q.count()
    pending_amount = (
        pending_q.with_entities(func.coalesce(func.sum(models.ActuatorCommission.amount), 0))
                 .scalar() or 0
    )

    # ✅ ready(지급 가능): ready_at 컬럼이 있을 때만 계산
    has_ready_at = hasattr(models.ActuatorCommission, "ready_at")
    if has_ready_at:
        ready_q = pending_q.filter(
            models.ActuatorCommission.ready_at.isnot(None),
            models.ActuatorCommission.ready_at <= now,
        )
        ready_count = ready_q.count()
        ready_amount = (
            ready_q.with_entities(func.coalesce(func.sum(models.ActuatorCommission.amount), 0))
                   .scalar() or 0
        )
    else:
        ready_count = 0
        ready_amount = 0

    # PAID
    paid_q = base_q.filter(models.ActuatorCommission.status == "PAID")
    paid_count = paid_q.count()
    paid_amount = (
        paid_q.with_entities(func.coalesce(func.sum(models.ActuatorCommission.amount), 0))
              .scalar() or 0
    )

    return {
        "actuator_id": actuator_id,
        "total_count": total_count,
        "total_amount": int(total_amount or 0),
        "pending_count": pending_count,
        "pending_amount": int(pending_amount or 0),
        "ready_count": ready_count,
        "ready_amount": int(ready_amount or 0),
        "paid_count": paid_count,
        "paid_amount": int(paid_amount or 0),
        "note": None if has_ready_at else "ready_at 컬럼이 없어 ready 통계를 0으로 반환했습니다.",
    }

#----------------------------------------------
# 모집 Seller의 Offer 현황
#----------------------------------------------
@router.get(
    "/{actuator_id}/sellers",
    response_model=List[schemas.ActuatorSellerSummaryOut],
    summary="액츄에이터가 모집한 셀러 리스트 + 오퍼 현황",
)
def list_actuator_sellers(
    actuator_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    sellers = (
        db.query(models.Seller)
          .filter(models.Seller.actuator_id == actuator_id)
          .all()
    )

    results: List[schemas.ActuatorSellerSummaryOut] = []

    for s in sellers:
        offers = (
            db.query(models.Offer)
              .filter(models.Offer.seller_id == s.id)
              .all()
        )
        total_offers = len(offers)
        confirmed_offers = sum(1 for o in offers if getattr(o, "is_confirmed", False))
        active_offers = sum(1 for o in offers if getattr(o, "is_active", False))
        total_sold_qty = sum(int(getattr(o, "sold_qty", 0) or 0) for o in offers)

        results.append(
            schemas.ActuatorSellerSummaryOut(
                seller_id=s.id,
                name=getattr(s, "name", None),
                total_offers=total_offers,
                confirmed_offers=confirmed_offers,
                active_offers=active_offers,
                total_sold_qty=total_sold_qty,
            )
        )

    return results
