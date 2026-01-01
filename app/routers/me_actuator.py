from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, crud


router = APIRouter(
    prefix="/actuators/me",      # 최종 경로: /actuators/me/commissions 같이 나감
    tags=["me_actuator"],
)


# ---------------------------------------------------------
# 내부 헬퍼: 액츄에이터 존재 여부 체크
# ---------------------------------------------------------
def _get_actuator_or_404(db: Session, actuator_id: int) -> "models.Actuator":
    """
    actuator_id 로 Actuator 가 실제 존재하는지 확인.
    (지금은 인증 없이 query param 으로 받으므로 최소 방어용)
    """
    actuator = db.get(models.Actuator, actuator_id)
    if actuator is None:
        raise HTTPException(status_code=404, detail="Actuator not found")
    return actuator


# ---------------------------------------------------------
# 1) 나의 커미션 현황 조회
#    - ready_at 이 None 이어도 그대로 보여줌 (기대심리용 😄)
# ---------------------------------------------------------
@router.get("/commissions")
def get_my_commissions(
    actuator_id: int = Query(..., ge=1, description="(임시) 현재 액츄에이터 ID"),
    db: Session = Depends(get_db),
):
    """
    액츄에이터 본인의 커미션 리스트 + 요약 정보 조회.

    - status = 'PENDING' / 'PAID'
    - ready_at 가 None 이면 "아직 정산일 미세팅" 상태로 그대로 내려줌
    """
    _get_actuator_or_404(db, actuator_id)

    rows: List[models.ActuatorCommission] = (
        db.query(models.ActuatorCommission)
        .filter(models.ActuatorCommission.actuator_id == actuator_id)
        .order_by(models.ActuatorCommission.id.desc())
        .all()
    )

    now = datetime.now(timezone.utc)

    pending_total = 0
    pending_count = 0
    ready_total = 0
    ready_count = 0
    paid_total = 0
    paid_count = 0

    items = []

    for c in rows:
        amount = int(getattr(c, "amount", 0) or 0)
        status = getattr(c, "status", None)
        ready_at: Optional[datetime] = getattr(c, "ready_at", None)
        paid_at: Optional[datetime] = getattr(c, "paid_at", None)

        if status == "PENDING":
            pending_total += amount
            pending_count += 1
            # ready_at 이 있고, now 기준으로 이미 도래한 건 'ready' 로 집계
            if ready_at is not None and ready_at <= now:
                ready_total += amount
                ready_count += 1
        elif status == "PAID":
            paid_total += amount
            paid_count += 1

        items.append(
            {
                "id": c.id,
                "reservation_id": getattr(c, "reservation_id", None),
                "seller_id": getattr(c, "seller_id", None),
                "amount": amount,
                "status": status,
                "ready_at": ready_at,
                "paid_at": paid_at,
            }
        )

    summary = {
        "actuator_id": actuator_id,
        "pending_count": pending_count,
        "pending_total_amount": pending_total,
        "ready_count": ready_count,
        "ready_total_amount": ready_total,
        "paid_count": paid_count,
        "paid_total_amount": paid_total,
    }

    return {
        "summary": summary,
        "items": items,
    }


# ---------------------------------------------------------
# 2) 나의 커미션 일괄 정산 (수동 트리거)
#    - crud.settle_actuator_commissions_for_actuator 사용
# ---------------------------------------------------------
@router.post("/commissions/settle")
def settle_my_commissions(
    actuator_id: int = Query(..., ge=1, description="(임시) 현재 액츄에이터 ID"),
    db: Session = Depends(get_db),
):
    """
    액츄에이터가 직접 '정산받기' 누른다고 가정한 수동 정산 API.

    - crud.settle_actuator_commissions_for_actuator() 를 호출
    - 해당 액츄에이터의 status='PENDING' 인 커미션 전부 PAID 로 변경
    - ready_at 이 안 온 것도 함께 정산되는 구조 (운영 정책에 따라 나중에 조정 가능)
    """
    _get_actuator_or_404(db, actuator_id)

    paid_count, total_amount, paid_ids = crud.settle_actuator_commissions_for_actuator(
        db, actuator_id=actuator_id
    )

    return {
        "actuator_id": actuator_id,
        "paid_count": paid_count,
        "paid_total_amount": total_amount,
        "paid_ids": paid_ids,
    }


# ---------------------------------------------------------
# 3) 내가 모집한 셀러 & 각 셀러 오퍼 현황
#    - actuator 입장에서 한 눈에 보는 대시보드용
# ---------------------------------------------------------
@router.get("/sellers")
def get_my_sellers_and_offers(
    actuator_id: int = Query(..., ge=1, description="(임시) 현재 액츄에이터 ID"),
    db: Session = Depends(get_db),
):
    """
    액츄에이터가 모집한 Seller 목록과 각 셀러의 Offer 현황.

    - Seller.actuator_id = actuator_id 인 셀러들 조회
    - 각 셀러에 대해 Offer 목록을 붙여서 내려줌
    """
    _get_actuator_or_404(db, actuator_id)

    sellers: List[models.Seller] = (
        db.query(models.Seller)
        .filter(models.Seller.actuator_id == actuator_id)
        .order_by(models.Seller.id)
        .all()
    )

    seller_items = []

    for s in sellers:
        offers: List[models.Offer] = (
            db.query(models.Offer)
            .filter(models.Offer.seller_id == s.id)
            .order_by(models.Offer.id.desc())
            .all()
        )

        offer_items = []
        for o in offers:
            offer_items.append(
                {
                    "offer_id": o.id,
                    "deal_id": getattr(o, "deal_id", None),
                    "price": getattr(o, "price", None),
                    "total_available_qty": getattr(o, "total_available_qty", None),
                    "reserved_qty": getattr(o, "reserved_qty", None),
                    "sold_qty": getattr(o, "sold_qty", None),
                    "is_active": getattr(o, "is_active", None),
                    "is_confirmed": getattr(o, "is_confirmed", None),
                    "created_at": getattr(o, "created_at", None),
                    "deadline_at": getattr(o, "deadline_at", None),
                }
            )

        seller_items.append(
            {
                "seller_id": s.id,
                "name": getattr(s, "name", None),
                "level": getattr(s, "level", None),
                "actuator_id": getattr(s, "actuator_id", None),
                "offers": offer_items,
            }
        )

    return {
        "actuator_id": actuator_id,
        "sellers": seller_items,
    }