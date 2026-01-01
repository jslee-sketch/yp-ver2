# app/pingpong/evidence/build_reservation_expire_v1.py
from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.pingpong.evidence.spec import (
    utcnow_iso,
    safe_int,
    safe_float,
    base_context,
    base_trace,
)


def build_reservation_expire_v1(
    db: Session,
    *,
    reservation: Any,
    offer: Any,
    actor: str = "system_expire",  # 자동만료는 system
    expire_stage: str = "BEFORE_SHIPPING",  # PENDING 만료는 배송 전으로 취급
    expected_source: Optional[str] = "expire_worker",
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Evidence Pack: reservation_expire_v1
    - PENDING 예약이 expires_at 경과로 EXPIRED 처리되는 시점의 근거 묶음
    - 자동취소(시스템)로 분류
    """
    before = before or {}

    resv_id = safe_int(getattr(reservation, "id", None))
    buyer_id = safe_int(getattr(reservation, "buyer_id", None))
    offer_id = safe_int(getattr(reservation, "offer_id", None))
    qty = safe_int(getattr(reservation, "qty", 0))

    status_after = getattr(reservation, "status", None)
    status_before = before.get("status_before", None)

    deal_id = safe_int(getattr(offer, "deal_id", None))
    seller_id = safe_int(getattr(offer, "seller_id", None))

    expires_at = getattr(reservation, "expires_at", None)
    expired_at = getattr(reservation, "expired_at", None)

    evidence = {
        "evidence_pack_version": "reservation_expire_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="reservation_expire", channel="server"),
        "policy_context": {
            "stage": expire_stage,
            "expected_source": expected_source,
        },
        "entities": {
            "reservation": {
                "id": resv_id,
                "buyer_id": buyer_id,
                "offer_id": offer_id,
                "qty": qty,
                "status_before": status_before,
                "status_after": str(status_after) if status_after is not None else None,
                "expires_at": expires_at.isoformat() if expires_at is not None else None,
                "expired_at": expired_at.isoformat() if expired_at is not None else None,
            },
            "offer": {
                "id": safe_int(getattr(offer, "id", None)),
                "deal_id": deal_id,
                "seller_id": seller_id,
                "price": safe_float(getattr(offer, "price", 0.0)),

                "sold_qty_before": safe_int(before.get("sold_qty_before", None)),
                "reserved_qty_before": safe_int(before.get("reserved_qty_before", None)),

                "sold_qty_after": safe_int(getattr(offer, "sold_qty", 0)),
                "reserved_qty_after": safe_int(getattr(offer, "reserved_qty", 0)),
            },
            "deal": {"id": deal_id} if deal_id else None,
            "seller": {"id": seller_id} if seller_id else None,
        },
        "amounts": {
            # PENDING 만료는 환불 없음(결제 전)
            "amount_total": safe_int(getattr(reservation, "amount_total", 0) or 0),
            "amount_shipping": safe_int(getattr(reservation, "amount_shipping", 0) or 0),
            "refund": {
                "refunded_qty_delta": 0,
                "amount_total_refund_delta": 0,
            },
        },
        "checks": {},
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
    }
    return evidence