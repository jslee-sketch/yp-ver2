# app/routers/reservations.py
from __future__ import annotations

from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from .. import schemas
from ..models import ReservationStatus as ReservationStatusEnum
from ..crud import (
    NotFoundError,
    ConflictError,
    get_offer_remaining_capacity,
    create_reservation,
    cancel_reservation,
    expire_reservations,
    pay_reservation_v35,
    refund_paid_reservation,
    get_reservation as crud_get_reservation,   # ✅ 결제 전 deal_id 얻기용
    search_reservations as crud_search_reservations,
)

# ✅ 결제 직전 디파짓 가드 유틸
from app.routers.deposits import ensure_deposit_before_pay

router = APIRouter(prefix="/reservations", tags=["reservations v3.5"])

def _translate_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")

# -------------------------------------------------------------------
# 예약 생성 (좌석 홀드)
# -------------------------------------------------------------------
@router.post(
    "",
    response_model=schemas.ReservationOut,
    status_code=status.HTTP_201_CREATED,
    summary="예약 생성(PENDING) — 재고 홀드",
    operation_id="Reservations__Create",
)
def reservations_create(
    body: schemas.ReservationCreate = Body(...),
    db: Session = Depends(get_db),
):
    try:
        return create_reservation(
            db,
            deal_id=body.deal_id,
            offer_id=body.offer_id,
            buyer_id=body.buyer_id,
            qty=body.qty,
            hold_minutes=body.hold_minutes,
        )
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 예약 결제 — v3.5 고정 포인트(+20/건) + ✅ 디파짓 가드
# -------------------------------------------------------------------
@router.post(
    "/pay",
    response_model=schemas.ReservationOut,
    summary="예약 결제 — reserved→sold, buyer 포인트(+20 고정, 디파짓 가드 포함)",
    operation_id="Reservations__PayV35",
)
def reservations_pay_v35(
    body: schemas.ReservationPayIn = Body(...),
    db: Session = Depends(get_db),
):
    try:
        # 1) 결제 대상 예약 조회(가드에 필요한 deal_id 확보)
        resv = crud_get_reservation(db, body.reservation_id)

        # 2) ✅ 결제 직전 디파짓 가드 (필요 시 409)
        ensure_deposit_before_pay(db, deal_id=resv.deal_id, buyer_id=body.buyer_id)

        # 3) 결제 수행 (CRUD는 v3.5 규칙으로 +20 고정 적립)
        return pay_reservation_v35(
            db,
            reservation_id=body.reservation_id,
            buyer_id=body.buyer_id,
        )
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 예약 취소 — 홀드 해제 (PENDING → CANCELLED)
# -------------------------------------------------------------------
@router.post(
    "/cancel",
    response_model=schemas.ReservationOut,
    summary="예약 취소 — reserved 복구 (PENDING 전용)",
    operation_id="Reservations__CancelPending",
)
def reservations_cancel(
    body: schemas.ReservationCancelIn = Body(...),
    db: Session = Depends(get_db),
):
    try:
        return cancel_reservation(
            db,
            reservation_id=body.reservation_id,
            buyer_id=body.buyer_id,
        )
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 결제 후 환불(=취소) 처리 (PAID → CANCELLED, 바이어 포인트 -20 회수)
# -------------------------------------------------------------------
class ReservationRefundIn(BaseModel):
    reservation_id: int
    actor: str = "buyer_cancel"

@router.post(
    "/refund",
    response_model=schemas.ReservationOut,
    summary="결제 후 환불 — PAID → CANCELLED, buyer 포인트 -20 롤백",
    operation_id="Reservations__RefundPaid",
)
def reservations_refund_paid(
    body: ReservationRefundIn = Body(...),
    db: Session = Depends(get_db),
):
    try:
        return refund_paid_reservation(
            db,
            reservation_id=body.reservation_id,
            actor=body.actor,
        )
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 만료 스윕 — EXPIRED로 전환 & reserved 복구
# -------------------------------------------------------------------
@router.post(
    "/expire",
    summary="만료 스윕 — 기한 지난 PENDING → EXPIRED",
    operation_id="Reservations__ExpireSweep",
)
def reservations_expire(
    db: Session = Depends(get_db),
):
    try:
        n = expire_reservations(db)
        return {"expired": n}
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 예약 단건 조회 (by id)
# -------------------------------------------------------------------
@router.get(
    "/by-id/{reservation_id}",
    response_model=schemas.ReservationOut,
    summary="예약 단건 조회(by id)",
    operation_id="Reservations__GetById",
)
def reservations_get_by_id(
    reservation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        return crud_get_reservation(db, reservation_id)
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 예약 검색 (buyer_id / deal_id / offer_id / status/ after_id)
# -------------------------------------------------------------------
@router.get(
    "/search",
    response_model=List[schemas.ReservationOut],
    summary="예약 검색(필터: reservation_id / deal_id / offer_id / buyer_id / status, 커서 after_id)",
    operation_id="Reservations__Search",
)
def reservations_search(
    reservation_id: Optional[int] = Query(None, ge=1),
    deal_id: Optional[int] = Query(None, ge=1),
    offer_id: Optional[int] = Query(None, ge=1),
    buyer_id: Optional[int] = Query(None, ge=1),
    status: Optional[str] = Query(None, description="PENDING | PAID | CANCELLED | EXPIRED"),
    after_id: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        enum_status = None
        if status is not None:
            s = status.strip().upper()
            try:
                if s in ReservationStatusEnum.__members__:
                    enum_status = ReservationStatusEnum[s]
                else:
                    enum_status = ReservationStatusEnum(s)
            except Exception:
                valid = ", ".join(ReservationStatusEnum.__members__.keys())
                raise HTTPException(status_code=400, detail=f"invalid status: {status}. use one of [{valid}]")

        rows = crud_search_reservations(
            db,
            reservation_id=reservation_id,
            deal_id=deal_id,
            offer_id=offer_id,
            buyer_id=buyer_id,
            status=enum_status,
            after_id=after_id,
            limit=limit,
        )
        return rows
    except HTTPException:
        raise
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 예약 검색(커서 페이징) — 응답에 next_cursor 포함
# -------------------------------------------------------------------
def _to_dict(r: Any) -> dict:
    return {
        "id": r.id,
        "deal_id": r.deal_id,
        "offer_id": r.offer_id,
        "buyer_id": r.buyer_id,
        "qty": r.qty,
        "status": r.status.name if hasattr(r.status, "name") else str(r.status),
        "created_at": r.created_at,
        "expires_at": r.expires_at,
        "paid_at": r.paid_at,
        "cancelled_at": r.cancelled_at,
        "expired_at": r.expired_at,
    }

@router.get(
    "/search_page",
    summary="예약 검색(커서 페이징)",
    operation_id="Reservations__SearchCursor",
)
def reservations_search_page(
    reservation_id: Optional[int] = Query(None),
    deal_id:       Optional[int] = Query(None),
    offer_id:      Optional[int] = Query(None),
    buyer_id:      Optional[int] = Query(None),
    status:        Optional[str] = Query(None, description="PENDING | PAID | CANCELLED | EXPIRED"),
    cursor:        Optional[int] = Query(None, description="이 ID보다 작은 항목부터 조회"),
    limit:         int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        enum_status = None
        if status is not None:
            s = status.strip().upper()
            try:
                if s in ReservationStatusEnum.__members__:
                    enum_status = ReservationStatusEnum[s]
                else:
                    enum_status = ReservationStatusEnum(s)
            except Exception:
                valid = ", ".join(ReservationStatusEnum.__members__.keys())
                raise HTTPException(status_code=400, detail=f"invalid status: {status}. use one of [{valid}]")

        items = crud_search_reservations(
            db,
            reservation_id=reservation_id,
            deal_id=deal_id,
            offer_id=offer_id,
            buyer_id=buyer_id,
            status=enum_status,
            after_id=cursor,
            limit=limit,
        )
        payload = [_to_dict(x) for x in items]
        next_cursor = items[-1].id if len(items) == limit else None
        return {"count": len(payload), "items": payload, "next_cursor": next_cursor}
    except HTTPException:
        raise
    except Exception as e:
        _translate_error(e)