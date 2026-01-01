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


def build_recommender_reward_v1(
    db: Session,
    *,
    reservation: Any,
    offer: Any,
    review: Any,
    actor: str,
    recommender_buyer_id: int,
    reward_points: int,
    expected_source: Optional[str] = None,
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    before = before or {}

    reservation_id = safe_int(getattr(reservation, "id", None))
    buyer_id = safe_int(getattr(reservation, "buyer_id", None))
    offer_id = safe_int(getattr(reservation, "offer_id", None))
    seller_id = safe_int(getattr(offer, "seller_id", None))
    deal_id = safe_int(getattr(offer, "deal_id", None))

    status_val = getattr(reservation, "status", None)
    status_name = getattr(status_val, "name", None) or str(status_val)

    evidence = {
        "evidence_pack_version": "recommender_reward_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="recommender_reward", channel="server"),
        "policy_context": {
            "expected_source": expected_source,
            "rule": "PAID + OFFER_CONFIRMED + REVIEW_CREATED",
        },
        "entities": {
            "reservation": {
                "id": reservation_id,
                "buyer_id": buyer_id,
                "offer_id": offer_id,
                "status": status_name,
                "paid_at": (getattr(reservation, "paid_at", None).isoformat()
                            if getattr(reservation, "paid_at", None) is not None else None),
            },
            "offer": {
                "id": safe_int(getattr(offer, "id", None)),
                "deal_id": deal_id,
                "seller_id": seller_id,
                "is_confirmed": bool(getattr(offer, "is_confirmed", False)),
                "price": safe_float(getattr(offer, "price", 0.0)),
            },
            "review": {
                "id": safe_int(getattr(review, "id", None)),
                "verified": bool(getattr(review, "verified", False)),
            },
            "recommender": {
                "buyer_id": safe_int(recommender_buyer_id),
            },
            "deal": {"id": deal_id} if deal_id else None,
            "seller": {"id": seller_id} if seller_id else None,
        },
        "rewards": {
            "points": safe_int(reward_points),
        },
        "checks": {},
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
    }
    return evidence