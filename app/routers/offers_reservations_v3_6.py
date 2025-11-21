# app/routers/offers_reservations_v3_6.py
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    OfferCreate, OfferOut,
    ReservationCreate, ReservationOut,
    ReservationPayIn, ReservationCancelIn,
    SellerOfferConfirmIn, SellerOfferCancelIn,
)
from ..crud import (
    create_offer, get_offers,
    create_reservation, cancel_reservation, pay_reservation, expire_reservations,
    seller_confirm_offer, seller_cancel_offer,
    NotFoundError, ConflictError,
)
from ..models import Offer, Reservation

router = APIRouter(prefix="/v3_6", tags=["v3.6 offers/reservations"])

def _xlate(e: Exception):
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=str(e))
    raise HTTPException(status_code=500, detail="Internal error")

# -----------------------------
# Offers
# -----------------------------
@router.post("/offers", response_model=OfferOut, status_code=201, summary="오퍼 생성")
def api_create_offer(payload: OfferCreate, db: Session = Depends(get_db)):
    try:
        return create_offer(db, payload)
    except Exception as e:
        _xlate(e)

@router.get("/offers", response_model=List[OfferOut], summary="오퍼 목록")
def api_list_offers(
    deal_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    try:
        rows = get_offers(db)
        if deal_id is not None:
            rows = [o for o in rows if o.deal_id == deal_id]
        return rows
    except Exception as e:
        _xlate(e)

@router.post("/offers/{offer_id}/confirm", response_model=OfferOut, summary="셀러 오퍼 확정")
def api_confirm_offer(
    offer_id: int = Path(..., ge=1),
    body: SellerOfferConfirmIn = SellerOfferConfirmIn(),
    db: Session = Depends(get_db),
):
    try:
        return seller_confirm_offer(
            db,
            offer_id=offer_id,
            force=body.force,
            award_on_full=30,   # 정책 상수: 전량 판매 & pending 0건일 때 +30pt
        )
    except Exception as e:
        _xlate(e)

@router.post("/offers/{offer_id}/cancel", response_model=OfferOut, summary="셀러 오퍼 취소(부분 환불/포인트 롤백 포함)")
def api_cancel_offer(
    offer_id: int = Path(..., ge=1),
    body: SellerOfferCancelIn = SellerOfferCancelIn(),
    db: Session = Depends(get_db),
):
    try:
        return seller_cancel_offer(
            db,
            offer_id=offer_id,
            penalize=body.penalize,
            allow_paid=body.allow_paid,
            reverse_buyer_points=body.reverse_buyer_points,
            buyer_point_per_qty=body.buyer_point_per_qty,
        )
    except Exception as e:
        _xlate(e)

# -----------------------------
# Reservations
# -----------------------------
@router.post("/reservations", response_model=ReservationOut, status_code=201, summary="예약 생성(좌석 홀드)")
def api_create_reservation(payload: ReservationCreate, db: Session = Depends(get_db)):
    try:
        return create_reservation(
            db,
            deal_id=payload.deal_id,
            offer_id=payload.offer_id,
            buyer_id=payload.buyer_id,
            qty=payload.qty,
            hold_minutes=payload.hold_minutes,
        )
    except Exception as e:
        _xlate(e)

@router.post("/reservations/cancel", response_model=ReservationOut, summary="예약 취소")
def api_cancel_reservation(payload: ReservationCancelIn, db: Session = Depends(get_db)):
    try:
        return cancel_reservation(
            db,
            reservation_id=payload.reservation_id,
            buyer_id=payload.buyer_id,
        )
    except Exception as e:
        _xlate(e)

@router.post("/reservations/pay", response_model=ReservationOut, summary="예약 결제(확정)")
def api_pay_reservation(payload: ReservationPayIn, db: Session = Depends(get_db)):
    try:
        return pay_reservation(
            db,
            reservation_id=payload.reservation_id,
            buyer_id=payload.buyer_id,
            buyer_point_per_qty=payload.buyer_point_per_qty,
        )
    except Exception as e:
        _xlate(e)

@router.post("/maintenance/reservations/expire", summary="만료 스윕 실행", status_code=200)
def api_expire_reservations(db: Session = Depends(get_db)):
    try:
        count = expire_reservations(db)
        return {"expired": count}
    except Exception as e:
        _xlate(e)