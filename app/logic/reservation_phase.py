# app/logic/reservation_phase.py

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.sql import func

from app.models import Reservation, ReservationStatus
from app.core.refund_policy import CoolingState, compute_cooling_state
from app.core.time_policy import _utcnow


def compute_reservation_phase(resv: Reservation, *, now: Optional[datetime] = None) -> str:
    """
    Reservation 상태 + 배송정보를 합쳐서 프론트에서 쓰기 쉬운 '단계' 문자열을 생성.

    대략적인 규칙:

    - PENDING
      - 아직 만료 전: "PENDING"
      - 만료됨(상태가 EXPIRED로 바뀌면): "EXPIRED"
    - PAID
      - 발송 전: "PAID_WAIT_SHIP"
      - 발송 후 도착정보 없음: "SHIPPED"
      - 도착 후 cooling 기간 이내: "DELIVERED_COOLING"
      - 도착 후 cooling 기간 지남: "DELIVERED_AFTER_COOLING"
    - CANCELLED: "CANCELLED"
    - EXPIRED: "EXPIRED"
    """

    if now is None:
        now = _utcnow()

    status = resv.status

    # 1) 간단한 상태들 먼저
    if status == ReservationStatus.CANCELLED:
        return "CANCELLED"
    if status == ReservationStatus.EXPIRED:
        return "EXPIRED"

    if status == ReservationStatus.PENDING:
        # EXPIRED 상태로 이미 바뀌지 않은 '생존 PENDING'이면 그냥 PENDING 으로 둔다.
        if resv.expires_at and resv.expires_at < now:
            # 아직 cron 에 의해 EXPIRED 로 전환되기 전 PENDING 이라면,
            # 프론트 입장에서는 만료된 것으로 보일 수 있으니 별도 태그
            return "PENDING_EXPIRED"
        return "PENDING"

    # 2) PAID 계열
    if status == ReservationStatus.PAID:
        cooling_state = compute_cooling_state(
            shipped_at=resv.shipped_at,
            delivered_at=resv.delivered_at,
            arrival_confirmed_at=resv.arrival_confirmed_at,
            now=now,
        )

        if cooling_state == CoolingState.BEFORE_SHIPPING:
            return "PAID_WAIT_SHIP"
        if cooling_state == CoolingState.SHIPPED_NOT_DELIVERED:
            return "SHIPPED"
        if cooling_state == CoolingState.WITHIN_COOLING:
            return "DELIVERED_COOLING"
        if cooling_state == CoolingState.AFTER_COOLING:
            return "DELIVERED_AFTER_COOLING"

        # 혹시 enum 추가되면 대비해서 fallback
        return "PAID"

    # 예상 못한 상태값 fallback
    return str(status)