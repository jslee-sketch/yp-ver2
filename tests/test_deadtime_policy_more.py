# tests/test_deadtime_policy_more.py
from datetime import datetime, timezone, timedelta
import pytest

from app.config import project_rules as R

KST = timezone(timedelta(hours=9))

def kst(y, M, d, h, m=0, s=0):
    return datetime(y, M, d, h, m, s, tzinfo=KST)

# 1) DeadTime 경계 테스트 (정확히 18:00, 09:00)
@pytest.mark.parametrize("ts, expected", [
    (kst(2025, 11, 7, 17, 59, 59), False),  # 금 17:59:59
    (kst(2025, 11, 7, 18, 0, 0),   True),   # 금 18:00:00
    (kst(2025, 11, 10, 8, 59, 59), True),   # 월 08:59:59
    (kst(2025, 11, 10, 9, 0, 0),   False),  # 월 09:00:00
])
def test_is_deadtime_boundaries(ts, expected):
    assert R.is_deadtime(ts) is expected

# 2) 주말은 항상 DeadTime
@pytest.mark.parametrize("ts", [
    kst(2025, 11, 8, 12, 0, 0),  # 토 12:00
    kst(2025, 11, 9, 15, 0, 0),  # 일 15:00
])
def test_is_deadtime_weekend(ts):
    assert R.is_deadtime(ts) is True

# 3) 금 17:30 + 2h => 월 10:30 KST
def test_apply_deadtime_pause_fri_1730_plus_2h():
    start = kst(2025, 11, 7, 17, 30, 0)                        # Fri 17:30
    end = R.apply_deadtime_pause(start, hours=2)               # +2h (야간·주말 정지)
    assert end.astimezone(KST) == kst(2025, 11, 10, 10, 30, 0) # Mon 10:30

# 4) 금 17:30 + 30m => 금 18:00 (경계로 딱 멈춤)
def test_apply_deadtime_pause_fri_1730_plus_30m():
    start = kst(2025, 11, 7, 17, 30, 0)
    end = R.apply_deadtime_pause(start, minutes=30)
    assert end.astimezone(KST) == kst(2025, 11, 7, 18, 0, 0)

# 5) 토 12:00 + 1h => 월 10:00 (주말 전체 정지)
def test_apply_deadtime_pause_sat_noon_plus_1h():
    start = kst(2025, 11, 8, 12, 0, 0)                         # Sat 12:00
    end = R.apply_deadtime_pause(start, hours=1)
    assert end.astimezone(KST) == kst(2025, 11, 10, 10, 0, 0)  # Mon 10:00

# 6) 단위 동치성: 90분 == 1시간30분 == 5400초
@pytest.mark.parametrize("kw", [
    dict(minutes=90),
    dict(hours=1, minutes=30),
    dict(seconds=5400),
])
def test_apply_deadtime_pause_unit_equivalence(kw):
    base = kst(2025, 11, 10, 10, 0, 0)  # 월 10:00 (영업시간)
    e1 = R.apply_deadtime_pause(base, **kw)
    e2 = R.apply_deadtime_pause(base, minutes=90)
    assert e1 == e2

# 7) 영업시간 구간 내에서는 선형 (DeadTime 미개입 시)
def test_apply_deadtime_pause_linear_inside_business_hours():
    base = kst(2025, 11, 10, 10, 0, 0)      # Mon 10:00
    a = R.apply_deadtime_pause(base, minutes=20)
    b = R.apply_deadtime_pause(a, minutes=10)
    direct = R.apply_deadtime_pause(base, minutes=30)
    assert a.astimezone(KST) == kst(2025, 11, 10, 10, 20, 0)
    assert b == direct  # DeadTime이 끼지 않으면 선형적으로 합산