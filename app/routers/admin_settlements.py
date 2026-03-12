# app/routers/admin_settlements.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Path, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="/admin/settlements",
    tags=["admin_settlements"],
)


# ---------------------------------------------------------
# 전체 정산 목록 조회 (관리자용)
# ---------------------------------------------------------
@router.get(
    "/",
    summary="[ADMIN] 전체 정산 목록 조회",
)
def api_admin_list_settlements(
    status: Optional[str] = Query(None, description="상태 필터 (HOLD/READY/APPROVED/PAID)"),
    seller_id: Optional[int] = Query(None, ge=1, description="판매자 ID 필터"),
    date_from: Optional[str] = Query(None, description="시작일 (ISO)"),
    date_to: Optional[str] = Query(None, description="종료일 (ISO)"),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    from datetime import datetime

    RS = models.ReservationSettlement
    S = models.Seller

    q = db.query(RS)
    if status:
        q = q.filter(RS.status == status)
    if seller_id:
        q = q.filter(RS.seller_id == seller_id)
    if date_from:
        try:
            q = q.filter(RS.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(RS.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    rows = q.order_by(RS.created_at.desc()).limit(limit).all()

    # seller_id → seller info cache
    seller_ids = {r.seller_id for r in rows}
    sellers = {}
    if seller_ids:
        for s in db.query(S).filter(S.id.in_(seller_ids)).all():
            sellers[s.id] = s

    # deal_id → product_name
    deal_ids = list({r.deal_id for r in rows if r.deal_id})
    deal_map: dict = {}
    if deal_ids:
        for d in db.query(models.Deal).filter(models.Deal.id.in_(deal_ids)).all():
            deal_map[d.id] = getattr(d, "product_name", "")

    # offer_id → quantity
    offer_ids = list({r.offer_id for r in rows if r.offer_id})
    offer_map: dict = {}
    if offer_ids:
        for o in db.query(models.Offer).filter(models.Offer.id.in_(offer_ids)).all():
            offer_map[o.id] = getattr(o, "quantity", None)

    # order_number 매핑
    resv_ids = list({r.reservation_id for r in rows if r.reservation_id})
    on_map: dict = {}
    if resv_ids:
        for rv in db.query(models.Reservation.id, models.Reservation.order_number).filter(models.Reservation.id.in_(resv_ids)).all():
            on_map[rv.id] = rv.order_number

    result = []
    for r in rows:
        seller = sellers.get(r.seller_id)
        result.append({
            "id": r.id,
            "reservation_id": r.reservation_id,
            "order_number": on_map.get(r.reservation_id),
            "deal_id": r.deal_id,
            "offer_id": r.offer_id,
            "seller_id": r.seller_id,
            "buyer_id": r.buyer_id,
            "seller_name": getattr(seller, "nickname", None) or f"S-{r.seller_id}",
            "seller_business_name": getattr(seller, "business_name", None) or "",
            "product_name": deal_map.get(r.deal_id, ""),
            "quantity": offer_map.get(r.offer_id),
            "total_amount": r.buyer_paid_amount,
            "pg_fee": r.pg_fee_amount,
            "platform_fee": r.platform_commission_amount,
            "payout_amount": r.seller_payout_amount,
            "settlement_amount": r.seller_payout_amount,
            "status": r.status,
            "currency": r.currency,
            "created_at": str(r.created_at) if r.created_at else None,
            "ready_at": str(r.ready_at) if r.ready_at else None,
            "approved_at": str(r.approved_at) if r.approved_at else None,
            "paid_at": str(r.paid_at) if r.paid_at else None,
        })

    return result


# ---------------------------------------------------------
# 정산 승인 (프론트엔드 /admin/settlements/{id}/approve)
# ---------------------------------------------------------
@router.post(
    "/{settlement_id}/approve",
    summary="[ADMIN] 정산 승인 (READY → APPROVED)",
)
def api_admin_approve_settlement(
    settlement_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    x_actor_id: int | None = Header(default=None, alias="X-Actor-Id"),
):
    from app.routers.settlements import approve_settlement
    return approve_settlement(settlement_id=settlement_id, db=db, x_actor_id=x_actor_id)


# ---------------------------------------------------------
# 예약ID 기준 정산 조회
# ---------------------------------------------------------
@router.get(
    "/by_reservation/{reservation_id}",
    response_model=schemas.ReservationSettlementOut,
    summary="[ADMIN] 특정 예약(reservation_id)의 정산 레코드 조회",
)
def api_get_settlement_by_reservation(
    reservation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    row = (
        db.query(models.ReservationSettlement)
        .filter(models.ReservationSettlement.reservation_id == reservation_id)
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Settlement not found for this reservation_id",
        )

    return row
