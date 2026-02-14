# app/config/project_rules.py
from __future__ import annotations

from datetime import datetime, time, timezone, timedelta
from typing import Optional
import os

# time_policy 유틸을 래핑
from app.config.time_policy import (
    now_utc as _now_utc,
    now_kst as _now_kst,
    add_working_minutes as _add_working_minutes,
    add_working_hours as _add_working_hours,
    apply_deadtime_pause as _apply_deadtime_pause_hours,  # (start_time, duration_hours)
    set_now_utc_for_testing as _set_now_utc_for_testing,
    is_now_overridden as _is_now_overridden,
)
import app.config.time_policy as TP



# [ADD] 중앙 규칙(표준값) 읽기 전용 참조 — 런타임 변화 없음
try:
    from app.config import rules_v3_5 as RV
except Exception:
    RV = None  # rules_v3_5 미배포 환경 대비




UTC = timezone.utc
KST = getattr(TP, "KST", timezone(timedelta(hours=9)))

# ---------------- now() 래퍼 & 테스트 후크 ----------------
def now_utc() -> datetime:
    return _now_utc()

def now_kst() -> datetime:
    return _now_kst()

def set_test_now_utc(dt: Optional[datetime]) -> None:
    """테스트용 현재시각 오버라이드(퍼블릭). None이면 해제."""
    _set_now_utc_for_testing(dt)

# (기존 내부 이름도 유지하고 싶다면 alias 남겨둠)
def _set_now_utc(dt: Optional[datetime]) -> None:  # backward-compat
    _set_now_utc_for_testing(dt)

def _clear_now_utc() -> None:
    _set_now_utc_for_testing(None)

def is_test_time_overridden() -> bool:
    try:
        return bool(_is_now_overridden())
    except Exception:
        return False

# ---------------- deadtime 판정 ----------------
def _to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(KST)

def is_deadtime(ts: Optional[datetime] = None) -> bool:
    """
    KST 기준 deadtime 여부.
    - 주말 전체 True
    - 평일: 09:00 미만 또는 18:00 이상 True
    time_policy.is_deadtime 가 있으면 그걸 신뢰/위임.
    """
    if hasattr(TP, "is_deadtime"):
        return bool(TP.is_deadtime(ts))

    dt_kst = _to_kst(ts or now_kst())
    wd = dt_kst.weekday()  # 0=Mon ... 6=Sun

    pol = TP.DEAD_TIME_POLICY if isinstance(getattr(TP, "DEAD_TIME_POLICY", {}), dict) else {}
    start: time = pol.get("weekday_start", time(9, 0))
    end:   time = pol.get("weekday_end",   time(18, 0))
    weekend_on: bool = pol.get("weekend_on", True)

    if weekend_on and wd >= 5:  # 토(5), 일(6)
        return True

    t = dt_kst.time()
    # 경계 포함: 18:00부터 deadtime, 09:00은 영업시간
    return t < start or t >= end

# ---------------- deadtime pause + 근무시간 가산 ----------------
def apply_deadtime_pause(*args, **kwargs) -> datetime:
    """
    단위 혼용 지원(모두 분으로 합산 후 근무분 가산):
      - apply_deadtime_pause(start_time, minutes=...)
      - apply_deadtime_pause(start_time, hours=...|duration_hours=...)
      - apply_deadtime_pause(start_time, seconds=...)
      - apply_deadtime_pause(start_time, hours=..., minutes=..., seconds=...)
      - apply_deadtime_pause(minutes|hours|seconds, start=...|start_time=...)
      - apply_deadtime_pause(duration_hours=...)           # base = now_utc()
      - apply_deadtime_pause(start_time, hours)            # 두 번째 위치인자
    반환: timezone-aware UTC(datetime)
    """
    # 1) 기준 시각
    base = kwargs.get("start_time") or kwargs.get("start")
    if base is None and len(args) >= 1:
        base = args[0]
    if base is None:
        base = now_utc()

    # 2) 단위 수집 (복합 단위 합산)
    minutes = kwargs.get("minutes", None)
    seconds = kwargs.get("seconds", None)

    hours = kwargs.get("duration_hours", None)
    if hours is None:
        hours = kwargs.get("hours", None)
    if hours is None and len(args) >= 2:
        hours = args[1]

    total_min = 0.0
    if hours is not None:
        total_min += float(hours) * 60.0
    if minutes is not None:
        total_min += float(minutes)
    if seconds is not None:
        total_min += float(seconds) / 60.0

    # 3) 합산된 분 단위가 있으면 minutes API로 수행
    if total_min > 0:
        return _add_working_minutes(base, int(round(total_min)))

    # 4) 혹시나 hours만 0으로 들어온 특수케이스 대응
    if hours is not None:
        return _apply_deadtime_pause_hours(base, float(hours))

    raise TypeError("apply_deadtime_pause() requires 'minutes' or 'hours/duration_hours' or 'seconds'")


# --------------------------------------------------
# Seller Level & Fee Policy  (§7-3)
# --------------------------------------------------
# 위에서부터 우선순위 적용 (Lv.1 먼저 검사, 안 맞으면 아래로 내려감)
SELLER_LEVEL_RULES = [
    # level, 최소 거래수, 최소 평점, 수수료(%)
    {"level": "Lv.1", "min_orders": 100, "min_rating": 4.5, "fee_percent": 2.0},
    {"level": "Lv.2", "min_orders": 100, "min_rating": 4.0, "fee_percent": 2.5},
    {"level": "Lv.3", "min_orders": 61,  "min_rating": 4.0, "fee_percent": 2.7},
    {"level": "Lv.4", "min_orders": 41,  "min_rating": 4.0, "fee_percent": 2.8},
    {"level": "Lv.5", "min_orders": 21,  "min_rating": 4.0, "fee_percent": 3.0},
    {"level": "Lv.6", "min_orders": 0,   "min_rating": 0.0, "fee_percent": 3.5},
]


# ---------------- 기타 정책 상수(기존 호환) ----------------
BUYER_POINT_PER_QTY = 20
BUYER_POINT_ON_PAID = BUYER_POINT_PER_QTY   # 레거시 호환
# Backward-compat alias (legacy code expects this name)
BUYER_POINT_ON_REFUND = -abs(BUYER_POINT_ON_PAID)
SELLER_POINT_ON_CONFIRM = 30

# ---------------------------------------------------------
# 🔒 Deposit 기능 OFF 설정
#   - 이제부터 시스템에서 디포짓은 사용하지 않는다.
#   - 관련 환경변수도 무시하고, 하드코딩된 기본값만 사용.
# ---------------------------------------------------------

# 항상 디포짓 요구 X
DEPOSIT_REQUIRE_ALWAYS: bool = False

# 최소 디포짓 금액 (원) – 0 이면 사실상 사용 안 함
DEPOSIT_MIN_AMOUNT: int = 0

# 디포짓 최대 유효 기간 (분) – None 이면 기간 제한 없음 (지금은 어차피 안 씀)
DEPOSIT_MAX_AGE_MINUTES: int | None = None

# 결제 시 자동 환불 기능도 전부 OFF
DEPOSIT_AUTO_REFUND_ON_PAY: bool = False
DEPOSIT_AUTO_REFUND_SWEEP_PRE_ANCHOR: bool = False

# ── 디버그 ────────────────────────────────────────────────────────────────
DEV_DEBUG_ERRORS: bool = False

# ── 내보낼 심볼(함수/상수) ───────────────────────────────────────────────
# * 아래 함수들은 상단에서 이미 정의되어 있어야 합니다:
#   - now_utc, now_kst, is_deadtime, apply_deadtime_pause
#   - _set_now_utc, _clear_now_utc, is_test_time_overridden
#   - set_test_now_utc (호환 alias: 없으면 아래와 같이 정의해 두세요)
try:
    set_test_now_utc  # type: ignore[name-defined]
except NameError:
    # 호환 alias: main.py에서 R.set_test_now_utc(None) 호출을 지원
    def set_test_now_utc(dt):
        _set_now_utc(dt)

# ── Environment overrides (optional, non-invasive) ─────────────────────────
def _env_bool(key: str, default: bool) -> bool:
    v = os.getenv(key)
    if v is None or v.strip() == "":
        return default
    s = v.strip().lower()
    if s in ("1", "true", "on", "yes"):  return True
    if s in ("0", "false", "off", "no"): return False
    return default

def _env_int_or_none(key: str, default: int | None) -> int | None:
    v = os.getenv(key)
    if v is None or v.strip() == "":
        return default
    s = v.strip().lower()
    if s in ("null", "none"):  return None
    try:
        return int(s)
    except ValueError:
        return default

def _env_str(key: str, default: str) -> str:
    v = os.getenv(key)
    if v is None or v.strip() == "":
        return default
    return v.strip()


__all__ = [
    "now_utc", "now_kst",
    "is_deadtime",
    "apply_deadtime_pause",
    "set_test_now_utc", "_set_now_utc", "_clear_now_utc", "is_test_time_overridden",
    "BUYER_POINT_PER_QTY", "BUYER_POINT_ON_PAID", "SELLER_POINT_ON_CONFIRM",
    # Deposit 정책 묶음
    #"DEPOSIT_REQUIRE_ALWAYS", "DEPOSIT_MIN_AMOUNT", "DEPOSIT_MAX_AGE_MINUTES",
    #"DEPOSIT_AUTO_REFUND_ON_PAY", "DEPOSIT_AUTO_REFUND_SWEEP_PRE_ANCHOR",
    #"DEPOSIT_FRESHNESS_ANCHOR",
    "DEV_DEBUG_ERRORS",
]

# =========================================================
# 💳 PG + 정산/환불 타임라인 규칙 (v0.1)
# =========================================================

#: Buyer가 "배송 후" 취소/환불을 요청할 수 있는 기간 (일 단위)
#: 예) 5 → shipped_at 이후 5일 이내에만 환불 요청 허용
BUYER_REFUND_WINDOW_DAYS: int = 5

#: 배송 완료(shipped_at) 이후, 이 거래를 "정산 대상"으로 올릴 수 있는 기준 시점
#: 예) 14 → shipped_at + 14일 이후에 seller 정산 ready 상태로 전환
SETTLEMENT_READY_DAYS_AFTER_SHIPPED: int = 14

#: 정산 ready 된 이후, 역핑이 셀러에게 정산을 실제로 송금해야 하는 기한 (일 단위)
#: 예) 7 → ready_at + 7일 이내에 seller 정산 지급
SETTLEMENT_PAY_WINDOW_DAYS: int = 7

#: 셀러 정산이 완료된 이후, 역핑이 Actuator에게 커미션을 송금해야 하는 기한 (일 단위)
#: 예) 7 → seller 정산 paid_at + 7일 이내에 actuator 커미션 지급
ACTUATOR_PAYOUT_WINDOW_DAYS: int = 7



# 역핑수수료 관련
PLATFORM_FEE_RATE = 0.035   # 3.5%
VAT_RATE = 0.10             # 10% (부가세)


# [ADD] 중앙 규칙 모듈 핸들(선택 공개)
__all__.extend(["RV"])



# 플랫폼(역핑) 수수료율 (공급가 기준)
PLATFORM_FEE_RATE = 0.035  # 3.5%

# PG 수수료율 (부가세 포함 전체 수수료율로 가정)
PG_FEE_RATE = 0.033  # 3.3%

# 부가가치세율 (플랫폼 수수료에만 적용)
VAT_RATE = 0.10  # 10%