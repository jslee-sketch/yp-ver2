"""영업일 계산 유틸 — 토/일/공휴일 제외"""
from datetime import datetime, timedelta

# 한국 공휴일 (고정) — 매년 반복
_FIXED_HOLIDAYS = {
    (1, 1),   # 신정
    (3, 1),   # 삼일절
    (5, 5),   # 어린이날
    (6, 6),   # 현충일
    (8, 15),  # 광복절
    (10, 3),  # 개천절
    (10, 9),  # 한글날
    (12, 25), # 크리스마스
}


def is_working_day(dt: datetime) -> bool:
    if dt.weekday() >= 5:  # 토(5), 일(6)
        return False
    if (dt.month, dt.day) in _FIXED_HOLIDAYS:
        return False
    return True


def add_working_days(start: datetime, days: int) -> datetime:
    """start부터 N영업일 후 시각 반환"""
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if is_working_day(current):
            added += 1
    return current


def working_days_left(deadline: datetime) -> int:
    """현재부터 deadline까지 남은 영업일 수"""
    if not deadline:
        return 0
    now = datetime.utcnow()
    if now >= deadline:
        return 0
    current = now
    count = 0
    while current < deadline:
        current += timedelta(days=1)
        if is_working_day(current):
            count += 1
    return count
