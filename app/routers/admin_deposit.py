# app/routers/admin_deposit.py
# NO-AUTH 개발용 Deposit 정책 토글 라우터
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Query
from typing import Annotated
from app.config import project_rules as R

router = APIRouter(prefix="/admin/deposit", tags=["🛠 Admin • Deposit Policy (NO-AUTH DEV)"])

# 키 분류
NUM_KEYS  = {"DEPOSIT_MIN_AMOUNT", "DEPOSIT_MAX_AGE_MINUTES"}
BOOL_KEYS = {
    "DEPOSIT_REQUIRE_ALWAYS",
    "DEPOSIT_AUTO_REFUND_ON_PAY",
    "DEPOSIT_AUTO_REFUND_SWEEP_PRE_ANCHOR",   # ★ 추가 키
}
ANCHOR_KEY = "DEPOSIT_FRESHNESS_ANCHOR"
ANCHOR_ALLOWED = {"reservation", "offer", "deal"}

ALL_KEYS = NUM_KEYS | BOOL_KEYS | {ANCHOR_KEY}

def _coerce_value(key: str, raw: str):
    if raw is None:
        return None
    s = raw.strip()

    # 공통: null 처리
    if s == "" or s.lower() in {"null", "none"}:
        return None

    # 숫자 키
    if key in NUM_KEYS:
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"{key} must be a number or null")

    # 불리언 키
    if key in BOOL_KEYS:
        sl = s.lower()
        if sl in {"true", "on", "yes", "1"}:
            return True
        if sl in {"false", "off", "no", "0"}:
            return False
        raise HTTPException(status_code=400, detail=f"{key} must be a boolean (true/false)")

    # 앵커 키
    if key == ANCHOR_KEY:
        v = s.lower()
        if v not in ANCHOR_ALLOWED:
            raise HTTPException(status_code=400, detail=f"{ANCHOR_KEY} must be one of {sorted(ANCHOR_ALLOWED)}")
        return v

    return s

@router.get("/status", summary="💰 Deposit 정책 조회 (NO-AUTH)")
def deposit_status():
    return {
        "DEPOSIT_REQUIRE_ALWAYS":             getattr(R, "DEPOSIT_REQUIRE_ALWAYS", False),
        "DEPOSIT_MIN_AMOUNT":                 getattr(R, "DEPOSIT_MIN_AMOUNT", 1),
        "DEPOSIT_MAX_AGE_MINUTES":            getattr(R, "DEPOSIT_MAX_AGE_MINUTES", None),
        "DEPOSIT_AUTO_REFUND_ON_PAY":         getattr(R, "DEPOSIT_AUTO_REFUND_ON_PAY", False),
        "DEPOSIT_AUTO_REFUND_SWEEP_PRE_ANCHOR": getattr(R, "DEPOSIT_AUTO_REFUND_SWEEP_PRE_ANCHOR", False),  # ★ 표시
        "DEPOSIT_FRESHNESS_ANCHOR":           getattr(R, "DEPOSIT_FRESHNESS_ANCHOR", "reservation"),
        "verified_admin": "dev (no-auth)",
    }

@router.post("/update", summary="💡 Deposit 정책 수정 (NO-AUTH)")
def deposit_update(
    key: Annotated[str, Query(description="수정할 키")],
    value: Annotated[str, Query(description="새 값 (숫자/불리언/null/문자열)")],
):
    if key not in ALL_KEYS:
        raise HTTPException(status_code=404, detail=f"'{key}' is not a supported deposit policy key")

    new_val = _coerce_value(key, value)
    old_val = getattr(R, key, None)
    setattr(R, key, new_val)

    return {"✅ message": f"{key} updated", "old": old_val, "new": new_val, "updated_by": "dev (no-auth)"}