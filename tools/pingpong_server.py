# tools/pingpong_server.py
"""
Sidecar AI agent — web server wrapper.

Wraps step_once() from pingpong_sidecar_openai.py as a FastAPI endpoint
so the frontend can use the full sidecar capabilities (7-intent classification,
KB search, external APIs, multi-turn conversation) via HTTP.

Architecture:
  Frontend → main app /v3_6/pingpong/ask (proxy) → THIS server /ask → step_once()
  step_once() may call brain at main app /v3_6/pingpong/brain/ask (no loop)
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure sibling import works regardless of cwd
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn
from openai import OpenAI

# Import sidecar module (__main__ guard prevents CLI from starting)
import pingpong_sidecar_openai as sidecar

# ──────────────────────────────────────────────────────────
# Monkey-patch: redirect brain calls to /brain/ask
#   Prevents circular proxy loop:
#     /ask (proxy) → sidecar → call_pingpong_ask → /ask (proxy) → ∞
#   With patch:
#     /ask (proxy) → sidecar → call_pingpong_ask → /brain/ask (direct) ✓
# ──────────────────────────────────────────────────────────

def _brain_ask(
    *,
    screen: str = "DEAL_ROOM",
    role: str = "BUYER",
    question: str = "",
    mode: str = "read_only",
    max_chat_messages: int = 10,
    context: Optional[Dict[str, Any]] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """call_pingpong_ask replacement that hits /brain/ask instead of /ask."""
    payload = {
        "screen": screen or "DEAL_ROOM",
        "role": (role or "BUYER").upper(),
        "question": (question or "").strip(),
        "mode": mode or "read_only",
        "max_chat_messages": int(max_chat_messages or 10),
        "context": context or {},
    }
    ask_timeout = timeout or float(
        os.environ.get("YP_ASK_TIMEOUT") or 0
    ) or max(1.5, sidecar.HTTP_TIMEOUT / 2.0)

    try:
        r = sidecar.HTTP.post(
            f"{sidecar.YP_SERVER_URL}/v3_6/pingpong/brain/ask",
            json=payload,
            timeout=ask_timeout,
        )
        try:
            obj = r.json()
        except Exception:
            obj = {"detail": (r.text or "").strip()}
        if isinstance(obj, dict):
            obj["_http_status"] = r.status_code
            return obj
        return {"detail": str(obj), "_http_status": r.status_code}
    except Exception as e:
        return {"error": "OFFLINE", "detail": repr(e), "_http_status": 0}


sidecar.call_pingpong_ask = _brain_ask

# ──────────────────────────────────────────────────────────
# Session management
# ──────────────────────────────────────────────────────────

_client: Optional[OpenAI] = None
_lock = threading.Lock()
_sessions: Dict[str, sidecar.ConversationState] = {}
_MAX_SESSIONS = 200


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def _evict_oldest_sessions() -> None:
    """Simple eviction: drop oldest sessions when over limit."""
    if len(_sessions) <= _MAX_SESSIONS:
        return
    keys = list(_sessions.keys())
    for k in keys[: len(keys) - _MAX_SESSIONS]:
        _sessions.pop(k, None)


# ──────────────────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────────────────

app = FastAPI(title="Pingpong Sidecar Server", version="1.0")


class ContextIn(BaseModel):
    deal_id: Optional[int] = None
    reservation_id: Optional[int] = None
    offer_id: Optional[int] = None


class AskRequest(BaseModel):
    """Accepts the same shape as PingpongAskIn for transparent proxying."""
    question: str = Field(..., description="User question")
    user_id: Optional[int] = Field(None)
    role: Optional[str] = Field(None)
    screen: str = Field("GENERAL")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    mode: str = Field("read_only")
    locale: str = Field("ko")
    max_chat_messages: int = Field(10)


@app.on_event("startup")
def startup():
    # Auto-detect main app URL on Railway (PORT env is set by platform)
    if not os.environ.get("YP_SERVER_URL") and os.environ.get("PORT"):
        sidecar.YP_SERVER_URL = f"http://localhost:{os.environ['PORT']}"

    sidecar.load_kb()
    sidecar.load_time_values_from_defaults()
    print(f"[sidecar-server] KB={len(sidecar.KB)} files, "
          f"SSOT_TIME={len(sidecar.SSOT_TIME)} keys, "
          f"YP_SERVER_URL={sidecar.YP_SERVER_URL}")


@app.post("/ask")
def ask(req: AskRequest):
    """
    Main endpoint — wraps sidecar step_once().
    Sync handler so FastAPI runs it in thread pool automatically.
    """
    started = time.time()
    answer = _process(req)
    latency_ms = int((time.time() - started) * 1000)
    return {
        "answer": answer or "",
        "used_policies": [],
        "actions": [],
        "debug": {
            "engine": "sidecar",
            "latency_ms": latency_ms,
        },
    }


def _process(req: AskRequest) -> str:
    question = (req.question or "").strip()
    if not question:
        return ""

    user_id = req.user_id or 1
    role = (req.role or "BUYER").upper()
    session_id = f"u{user_id}_{role}"

    ctx = req.context or {}

    with _lock:
        _evict_oldest_sessions()

        # Get or create session state
        if session_id not in _sessions:
            state = sidecar.ConversationState(
                role=role,
                user_id=user_id,
            )
            _sessions[session_id] = state
        else:
            state = _sessions[session_id]

        # Update session with request params
        state.role = role
        state.user_id = user_id

        # Set entity IDs from context
        if isinstance(ctx, dict):
            for key in ("deal_id", "offer_id", "reservation_id"):
                v = ctx.get(key)
                if v is not None:
                    try:
                        state.last_ids[key] = int(v)
                    except (ValueError, TypeError):
                        pass

        # Swap global state → session state
        sidecar.S = state

        # Run core logic
        client = _get_client()
        answer = sidecar.step_once(question, client)

        # Save back (step_once modifies S in place)
        _sessions[session_id] = sidecar.S

    return answer


@app.get("/health")
def health():
    return {
        "status": "ok",
        "kb_loaded": sidecar._KB_LOADED,
        "kb_count": len(sidecar.KB),
        "sessions": len(_sessions),
    }


if __name__ == "__main__":
    port = int(os.environ.get("SIDECAR_PORT", "9100"))
    print(f"[sidecar-server] Starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, workers=1)
