# app/routers/admin_settlements.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="/admin/settlements",
    tags=["admin_settlements"],
)


@router.get(
    "/by_reservation/{reservation_id}",
    response_model=schemas.ReservationSettlementOut,
    summary="[ADMIN] 특정 예약(reservation_id)의 정산 레코드 조회",
)
def api_get_settlement_by_reservation(
    reservation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    - ReservationSettlement 테이블에서
      reservation_id 기준으로 1건 조회
    - 없으면 404
    """
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