# app/pingpong/evidence/build_actuator_create_v1.py
from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.pingpong.evidence.spec import (
    utcnow_iso,
    safe_int,
    base_context,
    base_trace,
)


def build_actuator_create_v1(
    db: Session,
    *,
    actuator: Any,
    actor: str = "system_create_actuator",
    expected_source: Optional[str] = "routers.actuators.create_actuator",
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Evidence Pack: actuator_create_v1
    - Actuator 등록 시점의 SSOT 근거 묶음
    """
    before = before or {}

    act_id = safe_int(getattr(actuator, "id", None))

    evidence = {
        "evidence_pack_version": "actuator_create_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="actuator_create", channel="server"),
        "policy_context": {
            "expected_source": expected_source,
        },
        "entities": {
            "actuator": {
                "id": act_id,
                "name": getattr(actuator, "name", None),
                "email": getattr(actuator, "email", None),
                "phone": getattr(actuator, "phone", None),
                "status": getattr(actuator, "status", None),
            }
        },
        "checks": {},
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
    }
    return evidence