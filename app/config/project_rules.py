# app/config/project_rules.py
from __future__ import annotations

from datetime import datetime, time, timezone, timedelta
from typing import Optional

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

# ---------------- 기타 정책 상수(기존 호환) ----------------
BUYER_POINT_PER_QTY = 20
BUYER_POINT_ON_PAID = BUYER_POINT_PER_QTY   # 레거시 호환
SELLER_POINT_ON_CONFIRM = 30

# ── Deposit 정책 ──────────────────────────────────────────────────────────
# 디파짓을 무조건 요구할지 여부(티어/신뢰도 무시)
DEPOSIT_REQUIRE_ALWAYS: bool = False

# 최소 디파짓 금액(원). 1 이상이면 그 미만 금액은 불인정
DEPOSIT_MIN_AMOUNT: int = 1

# 디파짓 유효기간(분). None이면 비활성화.
# 숫자면 결제 시 검증 시점 기준으로 '최대 경과 시간(분)' 이내만 인정.
DEPOSIT_MAX_AGE_MINUTES: int | None = None

# 결제 성공 시 자동 환불 여부
# True  → 결제 직후 해당 예약 이후 생성된 최신 HELD 1건만 환불(메인 흐름에는 영향 없음)
# False → 결제 이후에도 HELD가 남아 운영자가 수동 정리
DEPOSIT_AUTO_REFUND_ON_PAY: bool = True

# 신선도 앵커(디파짓 인정 기준 시점)
# - "reservation": 예약 created_at 이후 생성된 디파짓만 인정(권장/현재 구현과 일치)
# - "offer"      : 오퍼 생성 이후
# - "deal"       : 딜 생성 이후
DEPOSIT_FRESHNESS_ANCHOR: str = "reservation"   # "reservation" | "offer" | "deal"

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

__all__ = [
    "now_utc", "now_kst",
    "is_deadtime",
    "apply_deadtime_pause",
    "set_test_now_utc", "_set_now_utc", "_clear_now_utc", "is_test_time_overridden",
    "BUYER_POINT_PER_QTY", "BUYER_POINT_ON_PAID", "SELLER_POINT_ON_CONFIRM",
    "DEPOSIT_REQUIRE_ALWAYS", "DEPOSIT_MIN_AMOUNT", "DEPOSIT_MAX_AGE_MINUTES",
    "DEPOSIT_AUTO_REFUND_ON_PAY", "DEPOSIT_FRESHNESS_ANCHOR",
    "DEV_DEBUG_ERRORS",
]