# app/services/delivery_tracker.py
"""
택배 배송조회 서비스.
SWEETTRACKER_API_KEY 없으면 mock 모드.
"""
from __future__ import annotations

import os
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum


class DeliveryStatus(str, Enum):
    UNKNOWN = "unknown"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    FAILED = "failed"


@dataclass
class DeliveryResult:
    status: DeliveryStatus
    carrier_name: str
    tracking_number: str
    delivered_at: Optional[str] = None
    last_location: Optional[str] = None
    last_updated: Optional[str] = None
    raw_events: list = field(default_factory=list)


CARRIER_CODES: dict[str, str] = {
    "CJ대한통운": "04",
    "한진택배": "05",
    "롯데택배": "08",
    "우체국택배": "01",
    "로젠택배": "06",
    "경동택배": "23",
    "대신택배": "22",
}


async def track_delivery(carrier_name: str, tracking_number: str) -> DeliveryResult:
    """배송 상태 조회. API 키 없으면 mock 반환."""
    api_key = os.environ.get("SWEETTRACKER_API_KEY")

    if not api_key:
        return DeliveryResult(
            status=DeliveryStatus.UNKNOWN,
            carrier_name=carrier_name,
            tracking_number=tracking_number,
        )

    carrier_code = CARRIER_CODES.get(carrier_name)
    if not carrier_code:
        return DeliveryResult(
            status=DeliveryStatus.UNKNOWN,
            carrier_name=carrier_name,
            tracking_number=tracking_number,
        )

    try:
        import httpx
        url = "http://info.sweettracker.co.kr/api/v1/trackingInfo"
        params = {"t_key": api_key, "t_code": carrier_code, "t_invoice": tracking_number}
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
    except Exception as e:
        print(f"[DELIVERY_TRACKER] API error: {e}")
        return DeliveryResult(status=DeliveryStatus.UNKNOWN, carrier_name=carrier_name, tracking_number=tracking_number)

    events = data.get("trackingDetails", [])
    if not events:
        return DeliveryResult(status=DeliveryStatus.UNKNOWN, carrier_name=carrier_name, tracking_number=tracking_number)

    last_event = events[-1]
    is_delivered = any(e.get("level") == 6 for e in events)

    if is_delivered:
        d_event = [e for e in events if e.get("level") == 6][-1]
        return DeliveryResult(
            status=DeliveryStatus.DELIVERED,
            carrier_name=carrier_name,
            tracking_number=tracking_number,
            delivered_at=d_event.get("timeString"),
            last_location=d_event.get("where"),
            last_updated=d_event.get("timeString"),
            raw_events=events,
        )

    return DeliveryResult(
        status=DeliveryStatus.IN_TRANSIT,
        carrier_name=carrier_name,
        tracking_number=tracking_number,
        last_location=last_event.get("where"),
        last_updated=last_event.get("timeString"),
        raw_events=events,
    )
