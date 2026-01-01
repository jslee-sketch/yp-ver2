# app/pingpong/evidence/build_buyer_referral_reward_v1.py
from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.pingpong.evidence.spec import (
    utcnow_iso,
    safe_int,
    base_context,
    base_trace,
)


def build_buyer_referral_reward_v1(
    db: Session,
    *,
    new_buyer: Any,
    recommender_buyer: Any,
    actor: str = "system_referral_reward",
    points_awarded: int = 500,
    expected_source: Optional[str] = "crud.create_buyer",
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Evidence Pack: buyer_referral_reward_v1
    - 신규 Buyer 생성 성공 시점에 추천인(기존 Buyer)에게 포인트 지급 근거를 기록
    """
    before = before or {}

    new_id = safe_int(getattr(new_buyer, "id", None))
    rec_id = safe_int(getattr(recommender_buyer, "id", None))

    evidence = {
        "evidence_pack_version": "buyer_referral_reward_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="buyer_referral_reward", channel="server"),
        "policy_context": {
            "expected_source": expected_source,
            "rule": "new_buyer_create_success_immediate_reward",
        },
        "entities": {
            "new_buyer": {
                "id": new_id,
                "recommender_buyer_id": safe_int(getattr(new_buyer, "recommender_buyer_id", None)),
            },
            "recommender_buyer": {
                "id": rec_id,
            },
        },
        "amounts": {
            "points": {
                "points_awarded": safe_int(points_awarded),
                "recommender_points_before": safe_int(before.get("recommender_points_before")),
                "recommender_points_after": safe_int(before.get("recommender_points_after")),
            }
        },
        "checks": {},
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
    }
    return evidence