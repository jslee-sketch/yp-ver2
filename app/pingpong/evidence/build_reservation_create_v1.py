# app/pingpong/evidence/build_reservation_create_v1.py
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


def build_reservation_create_v1(
    db: Session,
    *,
    reservation: Any,
    offer: Any,
    actor: str = "buyer_create_reservation",
    expected_source: Optional[str] = "crud.create_reservation",
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Evidence Pack: reservation_create_v1
    - 예약(PENDING)이 생성되는 시점의 SSOT 근거 묶음
    - expires_at, qty, amount_* snapshot, policy_snapshot_json 등
    """
    before = before or {}

    resv_id = safe_int(getattr(reservation, "id", None))
    buyer_id = safe_int(getattr(reservation, "buyer_id", None))
    offer_id = safe_int(getattr(reservation, "offer_id", None))
    deal_id = safe_int(getattr(reservation, "deal_id", None)) or safe_int(getattr(offer, "deal_id", None))
    seller_id = safe_int(getattr(offer, "seller_id", None))
    qty = safe_int(getattr(reservation, "qty", 0))

    expires_at = getattr(reservation, "expires_at", None)
    created_at = getattr(reservation, "created_at", None)

    policy_snapshot_json = getattr(reservation, "policy_snapshot_json", None)
    policy_id = getattr(reservation, "policy_id", None)

    evidence = {
        "evidence_pack_version": "reservation_create_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="reservation_create", channel="server"),
        "policy_context": {
            "expected_source": expected_source,
            "policy_id": safe_int(policy_id) if policy_id is not None else None,
            "policy_snapshot_json": policy_snapshot_json,
        },
        "entities": {
            "reservation": {
                "id": resv_id,
                "buyer_id": buyer_id,
                "offer_id": offer_id,
                "deal_id": deal_id,
                "qty": qty,
                "status_after": str(getattr(reservation, "status", None)),
                "created_at": created_at.isoformat() if created_at is not None else None,
                "expires_at": expires_at.isoformat() if expires_at is not None else None,
            },
            "offer": {
                "id": safe_int(getattr(offer, "id", None)),
                "deal_id": deal_id,
                "seller_id": seller_id,
                "price": safe_float(getattr(offer, "price", 0.0)),
                "shipping_mode": getattr(offer, "shipping_mode", None),
                "shipping_fee_per_reservation": safe_int(getattr(offer, "shipping_fee_per_reservation", 0)),
                "shipping_fee_per_qty": safe_int(getattr(offer, "shipping_fee_per_qty", 0)),
                "sold_qty_after": safe_int(getattr(offer, "sold_qty", 0)),
                "reserved_qty_after": safe_int(getattr(offer, "reserved_qty", 0)),
            },
            "deal": {"id": deal_id} if deal_id else None,
            "seller": {"id": seller_id} if seller_id else None,
            "buyer": {"id": buyer_id} if buyer_id else None,
        },
        "amounts": {
            "amount_goods": safe_int(getattr(reservation, "amount_goods", 0) or 0),
            "amount_shipping": safe_int(getattr(reservation, "amount_shipping", 0) or 0),
            "amount_total": safe_int(getattr(reservation, "amount_total", 0) or 0),
        },
        "checks": {},
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
        "before": before,
    }
    return evidence