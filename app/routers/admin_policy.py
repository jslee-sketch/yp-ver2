# app/routers/admin_policy.py
# Admin Policy Management (Dev: NO-AUTH version)
# Writer: Jeong Sang Lee (dev-tuned)
# Date: 2025-11-18

from __future__ import annotations

from typing import Annotated, Dict, Any, Optional
from datetime import time

from fastapi import APIRouter, HTTPException, Query, Body

from app.config import time_policy, project_rules as R  # <- deposit 정책은 project_rules에 존재

router = APIRouter(prefix="/admin/policy", tags=["🛠 Admin • Policy Control (NO-AUTH DEV)"])

# ─────────────────────────────────────────────────────────────────────
# ⚠️ 주의: 이 라우터는 개발 편의용으로 "무인증" 입니다.
# 운영 반영 시 반드시 인증/권한 체크를 붙이세요.
# ─────────────────────────────────────────────────────────────────────


# 내부 유틸
def _deadtime_to_str(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, time):
        return v.strftime("%H:%M")
    return str(v)


def _parse_deadtime_value(value: str) -> Any:
    """
    지원 포맷:
      - "true"/"false" (대소문자 무관)  → bool
      - "HH:MM" 또는 "HH:MM:SS"         → datetime.time
      - 그 외                          → 원문 문자열
    """
    lo = value.strip().lower()
    if lo in ("true", "false"):
        return lo == "true"
    # HH:MM[:SS]
    parts = value.split(":")
    if len(parts) in (2, 3) and all(p.isdigit() for p in parts):
        h = int(parts[0]); m = int(parts[1]); s = int(parts[2]) if len(parts) == 3 else 0
        if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59):
            raise HTTPException(status_code=400, detail="invalid time value (expect HH:MM or HH:MM:SS)")
        return time(hour=h, minute=m, second=s)
    return value


def _require_time_key(key: str) -> None:
    if key not in time_policy.TIME_POLICY:
        raise HTTPException(status_code=404, detail=f"'{key}' not found in TIME_POLICY")


def _require_deadtime_key(key: str) -> None:
    if key not in time_policy.DEAD_TIME_POLICY:
        raise HTTPException(status_code=404, detail=f"'{key}' not found in DEAD_TIME_POLICY")


# -------------------------------------------------------
# 1) 정책 요약 조회
# -------------------------------------------------------
@router.get(
    "/status",
    summary="📋 현재 정책 요약 조회 (NO-AUTH DEV)",
    description="개발용: 인증 없이 현재 TIME_POLICY/DEAD_TIME_POLICY를 조회합니다.",
)
def get_current_policies():
    # 문자열 직렬화(DeadTime)로 가독성 향상
    dead = {k: _deadtime_to_str(v) for k, v in time_policy.DEAD_TIME_POLICY.items()}
    return {
        "TIME_POLICY": dict(time_policy.TIME_POLICY),
        "DEAD_TIME_POLICY": dead,
        "verified_admin": "dev (no-auth)",
    }


# -------------------------------------------------------
# 2) Time Policy 단건 수정
# -------------------------------------------------------
@router.post(
    "/update-time",
    summary="⏱ 타임라인 정책 수정 (NO-AUTH DEV)",
    description="""
개발용: 인증 없이 TIME_POLICY의 값을 변경합니다.

예시:
- POST /admin/policy/update-time?key=DEAL_CREATION_WINDOW&hours=36
""",
)
def update_time_policy(
    key: Annotated[str, Query(
        description="수정할 TIME_POLICY 키",
        examples={"sample": {"value": "DEAL_CREATION_WINDOW"}},
    )],
    hours: Annotated[float, Query(
        description="새로운 시간값 (단위: 시간, float 가능)",
        examples={"sample": {"value": 36.0}},
    )],
):
    _require_time_key(key)

    old_value = time_policy.TIME_POLICY[key]
    time_policy.TIME_POLICY[key] = float(hours)

    return {
        "message": f"{key} updated successfully",
        "old_value": old_value,
        "new_value": float(hours),
        "unit": "hours",
        "updated_by": "dev (no-auth)",
    }


# -------------------------------------------------------
# 3) DeadTime 정책 단건 수정
# -------------------------------------------------------
@router.post(
    "/update-deadtime",
    summary="🌙 DeadTime 정책 수정 (NO-AUTH DEV)",
    description="""
개발용: 인증 없이 DEAD_TIME_POLICY 값을 변경합니다.

예시:
- POST /admin/policy/update-deadtime?key=weekday_end&value=19:00
- POST /admin/policy/update-deadtime?key=weekend_enabled&value=true
""",
)
def update_deadtime_policy(
    key: Annotated[str, Query(
        description="수정할 DEAD_TIME_POLICY 키",
        examples={"sample": {"value": "weekday_end"}},
    )],
    value: Annotated[str, Query(
        description="새 DeadTime 값 (true/false 또는 HH:MM / HH:MM:SS)",
        examples={"sample_time": {"value": "19:00"}, "sample_bool": {"value": "true"}},
    )],
):
    _require_deadtime_key(key)

    old_value = time_policy.DEAD_TIME_POLICY[key]
    parsed_value = _parse_deadtime_value(value)
    time_policy.DEAD_TIME_POLICY[key] = parsed_value

    return {
        "message": f"DeadTime '{key}' updated successfully",
        "old_value": _deadtime_to_str(old_value),
        "new_value": _deadtime_to_str(parsed_value),
        "updated_by": "dev (no-auth)",
    }


# -------------------------------------------------------
# 4) 일괄 수정 (선택, 편의)
#    body:
#    {
#      "time": {"DEAL_CREATION_WINDOW": 36, "...": ...},
#      "deadtime": {"weekday_end": "19:00", "weekend_enabled": "true"}
#    }
# -------------------------------------------------------
@router.post(
    "/bulk",
    summary="🧰 정책값 일괄 수정 (NO-AUTH DEV)",
)
def bulk_update_policies(
    payload: Annotated[Dict[str, Dict[str, Any]], Body(
        description="time/deadtime 섹션에 수정할 키-값 쌍을 담아 전송",
        examples={
            "sample": {
                "value": {
                    "time": {"DEAL_CREATION_WINDOW": 36.0},
                    "deadtime": {"weekday_end": "19:00", "weekend_enabled": "false"},
                }
            }
        },
    )],
):
    changed_time: Dict[str, Any] = {}
    changed_dead: Dict[str, str] = {}

    # time 섹션
    for k, v in (payload.get("time") or {}).items():
        _require_time_key(k)
        old = time_policy.TIME_POLICY[k]
        time_policy.TIME_POLICY[k] = float(v)
        changed_time[k] = {"old": old, "new": float(v), "unit": "hours"}

    # deadtime 섹션
    for k, v in (payload.get("deadtime") or {}).items():
        _require_deadtime_key(k)
        old = time_policy.DEAD_TIME_POLICY[k]
        parsed = _parse_deadtime_value(str(v))
        time_policy.DEAD_TIME_POLICY[k] = parsed
        changed_dead[k] = {"old": _deadtime_to_str(old), "new": _deadtime_to_str(parsed)}

    return {
        "message": "bulk update successful",
        "changed_time": changed_time,
        "changed_deadtime": changed_dead,
        "updated_by": "dev (no-auth)",
    }


# -------------------------------------------------------
# 5) 전체 초기화
# -------------------------------------------------------
@router.post(
    "/reset",
    summary="♻️ 정책값 전체 초기화 (NO-AUTH DEV)",
    description="개발용: 현재 정책을 기본값으로 복원합니다.",
)
def reset_policies():
    if hasattr(time_policy, "reset_to_default"):
        time_policy.reset_to_default()
        dead = {k: _deadtime_to_str(v) for k, v in time_policy.DEAD_TIME_POLICY.items()}
        return {
            "message": "All policies have been reset to default values (dev).",
            "TIME_POLICY": dict(time_policy.TIME_POLICY),
            "DEAD_TIME_POLICY": dead,
        }
    raise HTTPException(status_code=501, detail="reset_to_default() not implemented in time_policy.")


# -------------------------------------------------------
# 5️⃣ Deposit 정책 조회 (인증 없음)
# -------------------------------------------------------
@router.get(
    "/deposit/status",
    summary="💰 Deposit 정책 조회 (NO-AUTH DEV)",
)
def get_deposit_policy():
    from app.config import project_rules as PR
    return {
        "DEPOSIT_REQUIRE_ALWAYS": getattr(PR, "DEPOSIT_REQUIRE_ALWAYS", False),
        "DEPOSIT_MIN_AMOUNT": getattr(PR, "DEPOSIT_MIN_AMOUNT", 1),
        "DEPOSIT_SCOPE": getattr(PR, "DEPOSIT_SCOPE", "per_deal"),
        "DEPOSIT_REQUIRE_AFTER_RESERVATION": getattr(PR, "DEPOSIT_REQUIRE_AFTER_RESERVATION", True),
        "DEPOSIT_MAX_AGE_MINUTES": getattr(PR, "DEPOSIT_MAX_AGE_MINUTES", None),
        "DEPOSIT_AUTO_REFUND_ON_PAY": getattr(PR, "DEPOSIT_AUTO_REFUND_ON_PAY", True),
        "verified_admin": "dev (no-auth)",
    }

# -------------------------------------------------------
# 6️⃣ Deposit 정책 수정 (인증 없음)
# -------------------------------------------------------
@router.post(
    "/deposit/update",
    summary="🧭 Deposit 정책 수정 (NO-AUTH DEV)",
    description="""
예시:
POST /admin/policy/deposit/update?key=DEPOSIT_AUTO_REFUND_ON_PAY&value=true
POST /admin/policy/deposit/update?key=DEPOSIT_MAX_AGE_MINUTES&value=120
""",
)
def update_deposit_policy(
    key: Annotated[str, Query(description="수정할 키")],
    value: Annotated[str, Query(description="새 값 (true/false/숫자/문자열)")],
):
    from app.config import project_rules as PR

    allowed = {
        "DEPOSIT_REQUIRE_ALWAYS",
        "DEPOSIT_MIN_AMOUNT",
        "DEPOSIT_SCOPE",
        "DEPOSIT_REQUIRE_AFTER_RESERVATION",
        "DEPOSIT_MAX_AGE_MINUTES",
        "DEPOSIT_AUTO_REFUND_ON_PAY",
    }
    if key not in allowed:
        raise HTTPException(status_code=404, detail=f"'{key}' is not a modifiable deposit policy key")

    # 문자열 → bool/int/None 자동 변환
    v: object = value
    low = value.lower()
    if low in ("true", "false"):
        v = (low == "true")
    elif low in ("none", "null"):
        v = None
    else:
        try:
            if "." in value:
                v = float(value)
            else:
                v = int(value)
        except Exception:
            v = value  # 그대로 문자열

    old = getattr(PR, key, None)
    setattr(PR, key, v)
    return {"✅ message": f"{key} updated", "old_value": old, "new_value": v, "updated_by": "dev (no-auth)"}


def _parse_value(s: str):
    """bool/int/float/null을 관대하게 파싱; 그 외는 원문 문자열 반환"""
    if s is None:
        return None
    sl = s.strip().lower()
    if sl in ("true", "1", "on", "yes"):  return True
    if sl in ("false", "0", "off", "no"): return False
    if sl in ("null", "none"):            return None
    # int / float
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s

_DEPOSIT_KEYS = {
    "DEPOSIT_REQUIRE_ALWAYS",
    "DEPOSIT_MIN_AMOUNT",
    "DEPOSIT_MAX_AGE_MINUTES",
    "DEPOSIT_AUTO_REFUND_ON_PAY",
    "DEPOSIT_FRESHNESS_ANCHOR",  # "reservation"|"offer"|"deal"
}

@router.get(
    "/deposit/status",
    summary="💰 Deposit 정책 조회 (NO-AUTH DEV)",
    description="project_rules 모듈의 Deposit 관련 플래그를 조회합니다."
)
def deposit_status():
    return {
        "DEPOSIT_REQUIRE_ALWAYS":   getattr(R, "DEPOSIT_REQUIRE_ALWAYS", False),
        "DEPOSIT_MIN_AMOUNT":       getattr(R, "DEPOSIT_MIN_AMOUNT", 1),
        "DEPOSIT_MAX_AGE_MINUTES":  getattr(R, "DEPOSIT_MAX_AGE_MINUTES", None),
        "DEPOSIT_AUTO_REFUND_ON_PAY": getattr(R, "DEPOSIT_AUTO_REFUND_ON_PAY", False),
        "DEPOSIT_FRESHNESS_ANCHOR": getattr(R, "DEPOSIT_FRESHNESS_ANCHOR", "reservation"),
        "verified_admin": "dev (no-auth)",
    }

@router.post(
    "/deposit/update",
    summary="💡 Deposit 정책 값 변경 (NO-AUTH DEV)",
    description=(
        "예: /admin/policy/deposit/update?key=DEPOSIT_AUTO_REFUND_ON_PAY&value=false\n"
        "값 파싱 규칙: true/false/null, 정수/실수 자동 파싱, 나머지는 원문 문자열\n"
        "DEPOSIT_FRESHNESS_ANCHOR 는 reservation|offer|deal 중 하나를 권장"
    ),
)
def deposit_update(
    key: Annotated[str, Query(description="수정할 키 (DEPOSIT_*)")],
    value: Annotated[str, Query(description="새 값 (true|false|null|숫자|문자열)")],
):
    if key not in _DEPOSIT_KEYS:
        raise HTTPException(status_code=404, detail=f"'{key}' is not a supported deposit policy key")

    parsed = _parse_value(value)

    # 앵커 값 검증(권장)
    if key == "DEPOSIT_FRESHNESS_ANCHOR":
        allowed = {"reservation", "offer", "deal"}
        if isinstance(parsed, str) and parsed.lower() not in allowed:
            raise HTTPException(status_code=400, detail=f"DEPOSIT_FRESHNESS_ANCHOR must be one of {sorted(allowed)}")

    old = getattr(R, key, None)
    setattr(R, key, parsed)
    return {"✅ message": f"{key} updated", "old": old, "new": parsed, "updated_by": "dev (no-auth)"}


# ===== Deposit Policy (NO-AUTH DEV) under /admin/policy =====

def _parse_value(s: str):
    if s is None: return None
    sl = s.strip().lower()
    if sl in ("true","1","on","yes"): return True
    if sl in ("false","0","off","no"): return False
    if sl in ("null","none"): return None
    try:
        return int(s)
    except:
        try:
            return float(s)
        except:
            return s

_DEPOSIT_KEYS = {
    "DEPOSIT_REQUIRE_ALWAYS",
    "DEPOSIT_MIN_AMOUNT",
    "DEPOSIT_MAX_AGE_MINUTES",
    "DEPOSIT_AUTO_REFUND_ON_PAY",
    "DEPOSIT_FRESHNESS_ANCHOR",  # "reservation" | "offer" | "deal"
}

@router.get("/deposit/status", summary="💰 Deposit 정책 조회 (NO-AUTH)")
def deposit_status():
    return {
        "DEPOSIT_REQUIRE_ALWAYS":     getattr(R, "DEPOSIT_REQUIRE_ALWAYS", False),
        "DEPOSIT_MIN_AMOUNT":         getattr(R, "DEPOSIT_MIN_AMOUNT", 1),
        "DEPOSIT_MAX_AGE_MINUTES":    getattr(R, "DEPOSIT_MAX_AGE_MINUTES", None),
        "DEPOSIT_AUTO_REFUND_ON_PAY": getattr(R, "DEPOSIT_AUTO_REFUND_ON_PAY", False),
        "DEPOSIT_FRESHNESS_ANCHOR":   getattr(R, "DEPOSIT_FRESHNESS_ANCHOR", "reservation"),
        "verified_admin": "dev (no-auth)",
    }

@router.post("/deposit/update", summary="💡 Deposit 정책 수정 (NO-AUTH)")
def deposit_update(
    key: Annotated[str, Query(description="수정할 키 (DEPOSIT_*)")],
    value: Annotated[str, Query(description="새 값 (true|false|null|숫자|문자열)")],
):
    if key not in _DEPOSIT_KEYS:
        raise HTTPException(status_code=404, detail=f"'{key}' is not a supported deposit policy key")

    parsed = _parse_value(value)
    if key == "DEPOSIT_FRESHNESS_ANCHOR":
        allowed = {"reservation", "offer", "deal"}
        if not (isinstance(parsed, str) and parsed.lower() in allowed):
            raise HTTPException(status_code=400, detail=f"DEPOSIT_FRESHNESS_ANCHOR must be one of {sorted(allowed)}")

    old = getattr(R, key, None)
    setattr(R, key, parsed)
    return {"✅ message": f"{key} updated", "old": old, "new": parsed, "updated_by": "dev (no-auth)"}