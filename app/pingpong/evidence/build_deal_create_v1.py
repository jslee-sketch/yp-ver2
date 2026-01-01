# app/pingpong/evidence/build_deal_create_v1.py
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


def build_deal_create_v1(
    db: Session,
    *,
    deal: Any,
    actor: str = "buyer_create_deal",
    expected_source: Optional[str] = "crud.create_deal",
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Evidence Pack: deal_create_v1
    - 딜 생성 시점의 SSOT 근거 묶음
    - deal의 주요 필드(제목/카테고리/옵션/마감/상태 등)를 기록
    """
    before = before or {}

    deal_id = safe_int(getattr(deal, "id", None))
    buyer_id = safe_int(getattr(deal, "buyer_id", None) or getattr(deal, "creator_id", None))
    
    evidence = {
        "evidence_pack_version": "deal_create_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="deal_create", channel="server"),
        "policy_context": {
            "expected_source": expected_source,
        },
        "entities": {
            "deal": {
                "id": deal_id,
                "buyer_id": buyer_id,
                "title": getattr(deal, "title", None),
                "status_after": str(getattr(deal, "status", None)),
                "category": getattr(deal, "category", None),
                "min_qty": safe_int(getattr(deal, "min_qty", None)),
                "max_qty": safe_int(getattr(deal, "max_qty", None)),
                "target_price": safe_float(getattr(deal, "target_price", None)),
                "created_at": (getattr(deal, "created_at", None).isoformat()
                               if getattr(deal, "created_at", None) is not None else None),
                "deadline_at": (getattr(deal, "deadline_at", None).isoformat()
                                if getattr(deal, "deadline_at", None) is not None else None),
            },
            "buyer": {"id": buyer_id} if buyer_id else None,
        },
        "amounts": {},
        "checks": {},
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
        "before": before,
    }
    return evidence