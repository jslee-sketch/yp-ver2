# app/pingpong/evidence/build_evidence_pack_v0.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_refund_dispute_v1(
    *,
    event_time: Optional[str] = None,
    actor: str,
    stage: str,
    case: str,
    reservation: Dict[str, Any],
    offer: Dict[str, Any],
    amounts: Dict[str, Any],
    checks: Dict[str, Any],
    trace: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build Evidence Pack: refund_dispute_v1

    Inputs should be "already sanitized" (int/str/bool) and serializable.
    """
    pack = {
        "evidence_pack_version": "refund_dispute_v1",
        "event_time": event_time or _iso_now(),
        "context": {
            "actor": actor,
            "stage": stage,
            "case": case,
        },
        "entities": {
            "reservation": reservation,
            "offer": offer,
        },
        "amounts": amounts,
        "checks": checks,
        "trace": trace,
    }
    validate_refund_dispute_v1(pack)  # fail-fast
    return pack


def validate_refund_dispute_v1(pack: Dict[str, Any]) -> None:
    """
    Minimal schema validation (v1).
    - hard fail if required fields missing
    - keep it light; this is runtime code
    """
    def req(path: str, obj: Any) -> Any:
        cur = obj
        for key in path.split("."):
            if not isinstance(cur, dict) or key not in cur:
                raise ValueError(f"evidence_pack missing: {path}")
            cur = cur[key]
        return cur

    if pack.get("evidence_pack_version") != "refund_dispute_v1":
        raise ValueError("evidence_pack_version must be 'refund_dispute_v1'")

    req("event_time", pack)
    req("context.actor", pack)
    req("context.stage", pack)
    req("context.case", pack)

    # Entities
    req("entities.reservation", pack)
    req("entities.offer", pack)

    # Amounts
    req("amounts.amount_total", pack)
    req("amounts.amount_shipping", pack)
    req("amounts.refund.amount_total_refund", pack)
    req("amounts.refund.refunded_qty_delta", pack)
    req("amounts.source.expected_source", pack)
    req("amounts.source.preview_amount_total_refund", pack)
    req("amounts.source.fallback_amount_total_refund", pack)
    req("amounts.source.meta_supported", pack)

    # Checks
    req("checks.decision_supported", pack)
    req("checks.invariants_ok", pack)

    # Trace
    req("trace.pg_tid", pack)
    req("trace.run_id", pack)

    notes = pack.get("trace", {}).get("notes", [])
    if notes is None:
        pack["trace"]["notes"] = []
    elif not isinstance(notes, list):
        raise ValueError("trace.notes must be a list")