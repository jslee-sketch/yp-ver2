from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.pingpong.evidence.spec import utcnow_iso, safe_int, base_context, base_trace


def build_login_v1(
    db: Session,
    *,
    actor: str = "login",
    user_type: str,  # "buyer" | "seller" | "admin" | "system"
    user_id: int,
    expected_source: Optional[str] = "auth.login",
    meta: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    meta = meta or {}

    return {
        "evidence_pack_version": "login_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="login", channel="server"),
        "policy_context": {"expected_source": expected_source},
        "entities": {
            "user": {
                "type": user_type,
                "id": safe_int(user_id),
            }
        },
        "meta": meta,
        "checks": {},
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
    }