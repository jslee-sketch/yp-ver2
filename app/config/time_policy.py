# app/config/time_policy.py
# 중앙 집중형 시간 정책 관리 모듈 (v3.6, robust)
# - Dead Time(평일 18~09, 주말/공휴일)에는 타이머가 '정지'되고, 근무시간에만 흐름이 진행됩니다.
# - 모든 반환값은 timezone-aware UTC(datetime)입니다. (DB 저장/비교에 안전)
# Author: Jeong Sang Lee (patch: robust tz fallback)

from __future__ import annotations

from datetime import datetime, time, timedelta, date, timezone
from typing import Iterable

# -------------------------------------------------------
# 🔹 타임존 (tzdata 없어도 절대 안 터지게)
# -------------------------------------------------------
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # py>=3.9
except Exception:
    ZoneInfo = None  # type: ignore
    class ZoneInfoNotFoundError(Exception):
        ...

def _get_tz(key: str, fallback_offset_hours: int = 0):
    """
    IANA 시간대(key)를 우선 시도하고, 실패 시 UTC 오프셋 기반 타임존으로 폴백.
    """
    if ZoneInfo is not None:
        try:
            return ZoneInfo(key)
        except ZoneInfoNotFoundError:
            pass
    return timezone(timedelta(hours=fallback_offset_hours))

UTC = timezone.utc
KST = _get_tz("Asia/Seoul", 9)  # tzdata 없으면 UTC+9로 폴백

# -------------------------------------------------------
# 🔹 Dead Time 정의
# -------------------------------------------------------
DEAD_TIME_POLICY = {
    "timezone": "KST (Asia/Seoul)",
    "weekday_start": time(9, 0),        # 근무 시작시간
    "weekday_end": time(18, 0),         # 근무 종료시간
    "pause_weekends": True,             # 주말 정지
    "pause_holidays": True,             # 공휴일 정지 (HOLIDAYS에 등록된 날)
}

# (선택) 공휴일 목록: 필요 시 운영에서 업데이트
HOLIDAYS: set[date] = set()

# -------------------------------------------------------
# 🔹 이벤트별 타임라인 정의 (단위: 시간)
# -------------------------------------------------------
TIME_POLICY = {
    "DEAL_CREATION_WINDOW": 24,
    "SELLER_VERIFICATION_WINDOW": 12,
    "OFFER_EDITABLE_WINDOW": 24,
    "BUYER_PAYMENT_WINDOW": 2,
    "SELLER_DECISION_WINDOW": 0.5,
}

# -------------------------------------------------------
# 🔹 유틸: 현재 시각 (테스트 오버라이드 지원) + 변환
# -------------------------------------------------------
from datetime import datetime

# 테스트/진단에서 현재시각을 고정하기 위한 오버라이드 저장소
_TEST_NOW_UTC: datetime | None = None

def set_now_utc_for_testing(dt: datetime | None) -> None:
    """
    dt가 None이면 오버라이드 해제. dt가 naive면 UTC로 간주.
    """
    global _TEST_NOW_UTC
    if dt is None:
        _TEST_NOW_UTC = None
    else:
        _TEST_NOW_UTC = dt if dt.tzinfo else dt.replace(tzinfo=UTC)

def is_now_overridden() -> bool:
    return _TEST_NOW_UTC is not None

def now_utc() -> datetime:
    """
    정책에서 사용하는 UTC now. 테스트 중이면 고정값을 반환.
    """
    if _TEST_NOW_UTC is not None:
        return _TEST_NOW_UTC
    return datetime.now(UTC)

def now_kst() -> datetime:
    return now_utc().astimezone(KST)

def ensure_aware_utc(dt: datetime) -> datetime:
    """naive면 UTC로 붙여서 반환, aware면 그대로 UTC로 변환."""
    return (dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC))

# -------------------------------------------------------
# 🔹 공휴일 관리(선택)
# -------------------------------------------------------
def set_holidays(dates: Iterable[date]) -> None:
    HOLIDAYS.clear()
    HOLIDAYS.update(dates)

def add_holidays(dates: Iterable[date]) -> None:
    HOLIDAYS.update(dates)

def _is_holiday_kst(kst_dt: datetime) -> bool:
    if not DEAD_TIME_POLICY.get("pause_holidays", True):
        return False
    return kst_dt.date() in HOLIDAYS

# -------------------------------------------------------
# 🔹 Dead Time 판별/복귀/가산
# -------------------------------------------------------
def is_deadtime_kst(dt: datetime) -> bool:
    """
    인자로 받은 dt(aware/naive 모두 허용)를 KST로 변환해 Dead Time 여부 판단.
    - 주말 전체
    - 평일 18:00~다음날 09:00
    - 공휴일 전체 (옵션)
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    kst = dt.astimezone(KST)

    # 주말
    if DEAD_TIME_POLICY.get("pause_weekends", True) and kst.weekday() >= 5:
        return True
    # 공휴일
    if _is_holiday_kst(kst):
        return True
    # 평일 근무시간 외
    start = DEAD_TIME_POLICY["weekday_start"]
    end = DEAD_TIME_POLICY["weekday_end"]
    t = kst.time()
    return not (start <= t < end)

def next_resume_kst(dt: datetime) -> datetime:
    """
    Dead Time인 시각 dt로부터 '근무 재개' 시각(=다음 근무일 09:00 KST)을 UTC로 반환.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    kst = dt.astimezone(KST)

    def _nine_oclock(d: date) -> datetime:
        return datetime(d.year, d.month, d.day, 9, 0, tzinfo=KST)

    cur = kst
    while True:
        # 주말/공휴일이면 다음날 09:00까지 건너뜀
        if (DEAD_TIME_POLICY.get("pause_weekends", True) and cur.weekday() >= 5) or _is_holiday_kst(cur):
            cur = _nine_oclock((cur + timedelta(days=1)).date())
            continue
        # 평일 근무시간 외 → 다음 09:00
        if cur.time() >= DEAD_TIME_POLICY["weekday_end"]:
            cur = _nine_oclock((cur + timedelta(days=1)).date())
            continue
        if cur.time() < DEAD_TIME_POLICY["weekday_start"]:
            cur = _nine_oclock(cur.date())
            continue
        # 근무시간 내
        return cur.astimezone(UTC)

def add_working_minutes(dt: datetime, minutes: int) -> datetime:
    """
    Dead Time을 건너뛰며 '근무시간 기준'으로 분을 더해 UTC로 반환.
    (효율적으로 블록 단위로 점프)
    """
    if minutes <= 0:
        return ensure_aware_utc(dt)

    cur = ensure_aware_utc(dt)
    while minutes > 0:
        if is_deadtime_kst(cur):
            cur = next_resume_kst(cur)
            continue

        # 현재 근무 블록 끝(KST 18:00)까지 남은 분
        kst = cur.astimezone(KST)
        end_block_kst = datetime(
            kst.year, kst.month, kst.day,
            DEAD_TIME_POLICY["weekday_end"].hour,
            DEAD_TIME_POLICY["weekday_end"].minute,
            tzinfo=KST,
        )
        span_min = int((end_block_kst.astimezone(UTC) - cur).total_seconds() // 60)
        if span_min <= 0:
            cur = next_resume_kst(cur)
            continue

        step = min(minutes, span_min)
        cur = cur + timedelta(minutes=step)
        minutes -= step

    return cur.astimezone(UTC)

def add_working_hours(dt: datetime, hours: float) -> datetime:
    mins = int(round(hours * 60))
    return add_working_minutes(dt, mins)

# -------------------------------------------------------
# 🔹 마감 계산 (기존 API와 호환)
# -------------------------------------------------------
def apply_deadtime_pause(start_time: datetime, duration_hours: float) -> datetime:
    """
    v3.4 호환 함수명. Dead Time을 고려해 종료시각(UTC)을 반환합니다.
    예) 금 17:00 + 24h → 월 00:00 UTC(=월 09:00 KST)
    """
    return add_working_hours(start_time, duration_hours)

def calc_deadline_with_deadtime(duration_hours: float, *, start: datetime | None = None) -> datetime:
    """
    근무시간 기준으로 duration_hours를 더한 'UTC' 데드라인을 반환.
    start가 없으면 현재 UTC 기준.
    """
    base = ensure_aware_utc(start or now_utc())
    return add_working_hours(base, duration_hours)

# -------------------------------------------------------
# 🔹 Exports
# -------------------------------------------------------
__all__ = [
    "KST", "UTC",
    "DEAD_TIME_POLICY", "TIME_POLICY", "HOLIDAYS",
    "set_holidays", "add_holidays",
    "now_utc", "now_kst",
    "is_deadtime_kst", "next_resume_kst",
    "add_working_minutes", "add_working_hours",
    "apply_deadtime_pause", "calc_deadline_with_deadtime",
    "ensure_aware_utc",
]