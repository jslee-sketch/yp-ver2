# app/pingpong/evidence/build_offer_create_v1.py
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


def build_offer_create_v1(
    db: Session,
    *,
    offer: Any,
    actor: str = "seller_create_offer",
    expected_source: Optional[str] = "crud.create_offer",
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Evidence Pack: offer_create_v1
    - 오퍼가 생성되는 시점의 SSOT 근거 묶음
    - price/shipping/total_available_qty 같은 '처음 약속'을 기록
    """
    before = before or {}

    offer_id = safe_int(getattr(offer, "id", None))
    deal_id = safe_int(getattr(offer, "deal_id", None))
    seller_id = safe_int(getattr(offer, "seller_id", None))

    evidence = {
        "evidence_pack_version": "offer_create_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="offer_create", channel="server"),
        "policy_context": {
            "expected_source": expected_source,
        },
        "entities": {
            "offer": {
                "id": offer_id,
                "deal_id": deal_id,
                "seller_id": seller_id,
                "price": safe_float(getattr(offer, "price", 0.0)),
                "total_available_qty": safe_int(getattr(offer, "total_available_qty", 0)),
                "delivery_days": safe_int(getattr(offer, "delivery_days", None)),
                "comment": getattr(offer, "comment", None),

                "shipping_mode": getattr(offer, "shipping_mode", None),
                "shipping_fee_per_reservation": safe_int(getattr(offer, "shipping_fee_per_reservation", 0)),
                "shipping_fee_per_qty": safe_int(getattr(offer, "shipping_fee_per_qty", 0)),

                "created_at": (getattr(offer, "created_at", None).isoformat()
                               if getattr(offer, "created_at", None) is not None else None),
                "deadline_at": (getattr(offer, "deadline_at", None).isoformat()
                                if getattr(offer, "deadline_at", None) is not None else None),

                "is_confirmed": bool(getattr(offer, "is_confirmed", False)),
                "sold_qty": safe_int(getattr(offer, "sold_qty", 0)),
                "reserved_qty": safe_int(getattr(offer, "reserved_qty", 0)),
            },
            "deal": {"id": deal_id} if deal_id else None,
            "seller": {"id": seller_id} if seller_id else None,
        },
        "amounts": {},
        "checks": {},
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
        "before": before,
    }
    return evidence