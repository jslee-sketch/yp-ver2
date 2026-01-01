# app/routers/payments.py
from __future__ import annotations

from typing import List, Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Body
from sqlalchemy.orm import Session

from app import models, schemas, database
from pydantic import BaseModel, Field

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)

get_db = database.get_db


# ---------------------------------------------------------
# 공통: Settlement 모델 alias
# ---------------------------------------------------------
Settlement = models.ReservationSettlement


# ---------------------------------------------------------
# B단계: 특정 Seller의 정산 스냅샷 목록 조회
#   GET /payments/settlements/{seller_id}
# ---------------------------------------------------------
@router.get(
    "/settlements/{seller_id}",
    response_model=List[schemas.ReservationSettlementOut],
    summary="특정 Seller의 정산 스냅샷 목록 조회",
)
def get_seller_settlements(
    seller_id: int = Path(..., ge=1, description="정산을 조회할 판매자 ID"),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Settlement)
        .filter(Settlement.seller_id == seller_id)
        .order_by(Settlement.calc_at.desc())
        .all()
    )
    return rows


# ---------------------------------------------------------
# D-1단계: 미정산(또는 특정 상태) 정산 목록 조회 (관리자용)
#   GET /payments/settlements/pending
# ---------------------------------------------------------
@router.get(
    "/settlements",
    response_model=List[schemas.ReservationSettlementOut],
    summary="정산 목록 조회 (상태/셀러 필터)",
)
def list_settlements(
    status_filter: Optional[str] = Query(
        None,
        description="필터할 정산 상태(ex: PENDING / READY / PAID). 비우면 전체.",
    ),
    seller_id: Optional[int] = Query(
        None,
        ge=1,
        description="특정 Seller만 보고 싶으면 지정",
    ),
    db: Session = Depends(get_db),
):
    """
    - 관리자/운영자용:
        * 전체 정산 목록을 상태/셀러 기준으로 필터링해서 조회.
    - status_filter:
        * 예: 'PENDING', 'READY', 'PAID'
        * None이면 상태 조건 없이 전체.
    """
    q = db.query(Settlement)

    if seller_id is not None:
        q = q.filter(Settlement.seller_id == seller_id)

    if status_filter:
        q = q.filter(Settlement.status == status_filter)

    rows = (
        q.order_by(Settlement.calc_at.desc())
         .all()
    )
    return rows


# ---------------------------------------------------------
# C단계: 정산 1건 지급 완료 처리 (관리자용)
#   POST /payments/settlements/{settlement_id}/mark_paid
# ---------------------------------------------------------

class SettlementMarkPaidIn(BaseModel):   # ✅ schemas.BaseModel → BaseModel
    """
    정산 지급 완료 처리 입력값.
    - admin_id: 나중에 운영자 ID를 넣어 audit 용도로 쓸 수 있음(지금은 optional).
    """
    admin_id: Optional[int] = None


@router.post(
    "/settlements/{settlement_id}/mark_paid",
    response_model=schemas.ReservationSettlementOut,
    summary="정산 1건 지급 완료 처리 (status=PAID)",
)
def mark_settlement_paid(
    settlement_id: int = Path(..., ge=1, description="지급 처리할 정산 ID"),
    body: SettlementMarkPaidIn = Body(...),
    db: Session = Depends(get_db),
):
    """
    - Settlement.status 를 'PAID' 로 변경
    - paid_at 컬럼이 있으면 현재 시각으로 세팅 (없으면 무시)
    - 이미 PAID 인 경우에도 에러 없이 그대로 반환 (멱등)
    """
    st = db.query(Settlement).get(settlement_id)
    if not st:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Settlement not found",
        )

    # 이미 PAID면 그냥 그대로 리턴 (멱등 처리)
    if getattr(st, "status", None) == "PAID":
        return st

    # 상태 변경
    st.status = "PAID"

    # paid_at 이라는 컬럼이 모델에 있으면, 지금 시각으로 세팅
    now = datetime.now(timezone.utc)
    if hasattr(st, "paid_at"):
        setattr(st, "paid_at", now)

    db.add(st)
    db.commit()
    db.refresh(st)
    return st


# ---------------------------------------------------------
# D-2단계(선택): 특정 Seller의 'READY' 정산 일괄 지급 처리
#   POST /payments/settlements/bulk_mark_paid
# ---------------------------------------------------------
class SettlementBulkMarkPaidIn(BaseModel):   # ✅ 동일
    seller_id: int = Field(..., ge=1, description="일괄 지급할 Seller ID")
    status_from: str = Field(
        "READY",
        description="어떤 상태에서 PAID로 바꿀지 (기본: READY)",
    )
    admin_id: Optional[int] = None


@router.post(
    "/settlements/bulk_mark_paid",
    summary="특정 Seller의 정산들을 일괄 PAID 처리",
)
def bulk_mark_settlements_paid(
    body: SettlementBulkMarkPaidIn = Body(...),
    db: Session = Depends(get_db),
):
    """
    - 예: Seller #1의 READY 정산들을 한 번에 PAID로 바꾸고 싶을 때 사용.
    - 실제 송금은 오프라인에서 하고,
      이 API로 '정산 상태'만 일괄 업데이트한다고 보면 됨.
    """
    q = db.query(Settlement).filter(
        Settlement.seller_id == body.seller_id,
        Settlement.status == body.status_from,
    )

    now = datetime.now(timezone.utc)
    updated = 0

    for st in q.all():
        st.status = "PAID"
        if hasattr(st, "paid_at"):
            setattr(st, "paid_at", now)
        db.add(st)
        updated += 1

    if updated > 0:
        db.commit()

    return {"seller_id": body.seller_id, "updated": updated}


@router.post(
    "/settlements/refresh_due",
    summary="(배치) 쿨링 종료된 HOLD/PENDING 정산을 READY로 전환",
)
def refresh_due_settlements(
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    q = (
        db.query(Settlement)
        .filter(Settlement.status.in_(["HOLD", "PENDING"]))
        .filter(Settlement.ready_at.isnot(None))
        .filter(Settlement.ready_at <= now)
        .order_by(Settlement.id.asc())
        .limit(limit)
    )

    rows = q.all()
    if not rows:
        return {"updated": 0, "ready_ids": []}

    updated = 0
    ids = []

    # 정책값: 분쟁 종료 후 지급(별도 패스) 기본 딜레이
    def _dispute_delay_days():
        try:
            from app.policy import api as policy_api
            return int(policy_api.dispute_settlement_payout_delay_days())
        except Exception:
            return 30

    for st in rows:
        # 1) 분쟁이면 READY로 올리지 않음
        #    - Reservation.is_disputed를 SSOT로 보려면 reservation join 필요하지만,
        #      여기서는 Settlement.dispute_* 스냅샷 + block_reason로 1차 방어한다.
        if getattr(st, "block_reason", None) == "DISPUTE":
            continue

        # 2) 과거에 DISPUTE였다가 종료된 케이스를 별도 패스로 스케줄링하고 싶으면:
        #    - dispute_closed_at이 있으면 "분쟁 패스"로 scheduled_payout_at을 재산정
        d_closed = getattr(st, "dispute_closed_at", None)
        if d_closed is not None and getattr(st, "block_reason", None) in ("DISPUTE", "DISPUTE_PATH"):
            # 분쟁 종료 후 별도 패스
            st.status = "HOLD"
            st.block_reason = "DISPUTE_PATH"
            st.ready_at = d_closed
            st.scheduled_payout_at = d_closed + timedelta(days=max(0, min(_dispute_delay_days(), 365)))
            db.add(st)
            updated += 1
            ids.append(st.id)
            continue

        # 3) 정상 케이스: READY로 전환
        st.status = "READY"
        st.block_reason = None
        db.add(st)
        updated += 1
        ids.append(st.id)

    if updated > 0:
        db.commit()

    return {"updated": updated, "ready_ids": ids}


class SettlementApproveIn(BaseModel):
    admin_id: Optional[int] = None
    note: Optional[str] = None  # 승인 메모

@router.post(
    "/settlements/{settlement_id}/approve",
    response_model=schemas.ReservationSettlementOut,
    summary="(관리자) 정산 승인 처리 (approved_at 세팅)",
)
def approve_settlement(
    settlement_id: int = Path(..., ge=1),
    body: SettlementApproveIn = Body(...),
    db: Session = Depends(get_db),
):
    st = db.query(Settlement).get(settlement_id)
    if not st:
        raise HTTPException(status_code=404, detail="Settlement not found")

    # 분쟁이면 승인해도 지급은 막히게(정책상)
    if getattr(st, "block_reason", None) in ("DISPUTE", "DISPUTE_PATH"):
        # 승인 자체를 막을지/허용할지는 운영 철학인데,
        # 너 요구는 "승인은 미리 가능"이므로 승인 자체는 허용하되 payout 배치에서 막는다.
        pass

    # approved_at 멱등
    if getattr(st, "approved_at", None) is None:
        now = datetime.now(timezone.utc)
        st.approved_at = now

        # 상태를 명확히 하고 싶으면 APPROVED로 전환(추천)
        # READY가 아니어도 승인 가능: 지급 배치에서 조건으로 걸러짐
        st.status = "APPROVED" if getattr(st, "status", None) in ("READY", "HOLD", "PENDING") else st.status

        if body.note and hasattr(st, "payout_override_reason"):
            st.payout_override_reason = (body.note or "").strip()[:200]

        db.add(st)
        db.commit()
        db.refresh(st)

    return st


@router.post(
    "/settlements/payout_due",
    summary="(배치) 지급일 도래 + 승인된 정산을 PAID 처리",
)
def payout_due_settlements(
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """
    자동화 철학(너 요구):
    - 관리자는 지급일 이전 언제든 승인 가능
    - 지급일이 되면 승인된 건이 자동 지급(은행 연동/파일 생성/큐 적재)
    - 여기서는 MVP로: PAID 마킹(은행 연동은 다음 단계에서 hook)
    """
    now = datetime.now(timezone.utc)

    q = (
        db.query(Settlement)
        .filter(Settlement.approved_at.isnot(None))
        .filter(Settlement.scheduled_payout_at.isnot(None))
        .filter(Settlement.scheduled_payout_at <= now)
        .filter(Settlement.status.in_(["APPROVED", "READY"]))  # READY도 허용(운영 실수 방어)
        .order_by(Settlement.id.asc())
        .limit(limit)
    )
    rows = q.all()
    if not rows:
        return {"paid_count": 0, "paid_ids": []}

    paid_ids = []
    for st in rows:
        # ✅ 분쟁이면 지급 불가(해당 건만)
        if getattr(st, "block_reason", None) in ("DISPUTE", "DISPUTE_PATH"):
            continue

        st.status = "PAID"
        if hasattr(st, "paid_at"):
            st.paid_at = now
        db.add(st)
        paid_ids.append(st.id)

        # TODO(다음 단계):
        # - 은행 지급 파일 생성
        # - 은행 API 호출/큐 적재
        # - 지급 실패 시 RETRY 상태/에러코드 기록

    if paid_ids:
        db.commit()

    return {"paid_count": len(paid_ids), "paid_ids": paid_ids}