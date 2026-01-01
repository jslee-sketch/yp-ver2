from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.pingpong.evidence.spec import utcnow_iso, safe_int, base_context, base_trace


def build_buyer_register_v1(
    db: Session,
    *,
    buyer: Any,
    actor: str = "buyer_register",
    expected_source: Optional[str] = "auth.register_buyer",
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    before = before or {}

    buyer_id = safe_int(getattr(buyer, "id", None))
    email = getattr(buyer, "email", None)
    phone = getattr(buyer, "phone", None)
    name = getattr(buyer, "name", None)

    return {
        "evidence_pack_version": "buyer_register_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="buyer_register", channel="server"),
        "policy_context": {"expected_source": expected_source},
        "entities": {
            "buyer": {
                "id": buyer_id,
                "email": email,
                "phone": phone,
                "name": name,
                "created_at": (getattr(buyer, "created_at", None).isoformat()
                               if getattr(buyer, "created_at", None) is not None else None),
            }
        },
        "checks": {},
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
    }