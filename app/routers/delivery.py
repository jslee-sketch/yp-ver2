# app/routers/delivery.py
"""
GET /delivery/track/{reservation_id}  — 배송 상태 조회
GET /delivery/carriers                — 지원 택배사 목록
"""
from __future__ import annotations

import asyncio
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import Reservation
from app.services.delivery_tracker import track_delivery, CARRIER_CODES

router = APIRouter(prefix="/delivery", tags=["delivery"])


class TrackResult(BaseModel):
    reservation_id: int
    carrier: str
    tracking_number: str
    status: str
    last_location: str = ""
    last_updated: str = ""
    delivered_at: str = ""


@router.get("/track/{reservation_id}", response_model=TrackResult)
def track_reservation(reservation_id: int, db: Session = Depends(get_db)):
    resv = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not resv:
        raise HTTPException(404, "예약을 찾을 수 없습니다")
    carrier = getattr(resv, "shipping_carrier", None)
    tracking = getattr(resv, "tracking_number", None)
    if not carrier or not tracking:
        raise HTTPException(400, "배송 정보가 없습니다")

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(track_delivery(carrier, tracking))
    finally:
        loop.close()
    return TrackResult(
        reservation_id=reservation_id,
        carrier=carrier,
        tracking_number=tracking,
        status=result.status.value,
        last_location=result.last_location or "",
        last_updated=result.last_updated or "",
        delivered_at=result.delivered_at or "",
    )


@router.get("/carriers")
def list_carriers() -> List[Dict[str, str]]:
    return [{"name": name, "code": code} for name, code in CARRIER_CODES.items()]
