# app/pingpong/evidence/spec.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def safe_str(v: Any, default: str = "") -> str:
    try:
        s = str(v)
        return s
    except Exception:
        return default


def base_trace(*, run_id: Optional[str] = None, request_id: Optional[str] = None, notes: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "request_id": request_id,
        "notes": notes or [],
    }


def base_context(*, actor: str, reason: Optional[str] = None, channel: Optional[str] = None) -> Dict[str, Any]:
    return {
        "actor": actor,
        "reason": reason,
        "channel": channel,
    }