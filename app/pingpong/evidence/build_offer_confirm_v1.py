# app/pingpong/evidence/build_offer_confirm_v1.py
from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.pingpong.evidence.spec import utcnow_iso, safe_int, safe_float, base_context, base_trace


def build_offer_confirm_v1(
    db: Session,
    *,
    offer: Any,
    actor: str,  # e.g. "seller_confirm" | "admin_force_confirm" | "system_auto_confirm"
    force: bool,
    award_on_full: int,
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Evidence Pack: offer_confirm_v1
    - 'offer'는 SQLAlchemy Offer 객체(Any로 둠)
    - before에는 확정 직전 값(변경 전 스냅샷)을 넘겨주면 before/after가 깔끔해짐
    """

    before = before or {}

    deal_id = safe_int(getattr(offer, "deal_id", None))
    offer_id = safe_int(getattr(offer, "id", None))
    seller_id = safe_int(getattr(offer, "seller_id", None))

    total = safe_int(getattr(offer, "total_available_qty", 0))
    sold = safe_int(getattr(offer, "sold_qty", 0))

    price = safe_float(getattr(offer, "price", 0.0))
    shipping_mode = getattr(offer, "shipping_mode", None)
    ship_fee_resv = safe_int(getattr(offer, "shipping_fee_per_reservation", 0))
    ship_fee_qty = safe_int(getattr(offer, "shipping_fee_per_qty", 0))

    is_confirmed_after = bool(getattr(offer, "is_confirmed", False))
    is_confirmed_before = bool(before.get("is_confirmed", False))

    # (있으면) offer policy id 같은 것들도 담아두면 나중에 policy snapshot 추적이 쉬움
    policy_id = getattr(offer, "policy_id", None)

    evidence = {
        "evidence_pack_version": "offer_confirm_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="offer_confirm", channel="server"),
        "entities": {
            "deal": {"id": deal_id},
            "offer": {
                "id": offer_id,
                "deal_id": deal_id,
                "seller_id": seller_id,
                "price": price,
                "shipping_mode": shipping_mode,
                "shipping_fee_per_reservation": ship_fee_resv,
                "shipping_fee_per_qty": ship_fee_qty,
                "policy_id": policy_id,
                "total_available_qty": total,
                "sold_qty": sold,
                "is_confirmed_before": is_confirmed_before,
                "is_confirmed_after": is_confirmed_after,
            },
            "seller": {"id": seller_id} if seller_id else None,
        },
        "decision": {
            "force": bool(force),
            "award_on_full": safe_int(award_on_full),
        },
        "policy_snapshot": {
            # 지금 당장 다 못 채워도 OK (나중에 채우면 됨)
            "policy_version": "v0",
            "offer_exposure_policy_version": None,
            "params_version": None,
            "rules_version": None,
            "notes": "fill later if needed",
        },
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
    }
    return evidence