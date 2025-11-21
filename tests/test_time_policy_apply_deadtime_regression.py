import pytest
from datetime import datetime, timezone, timedelta

# 우리가 고친 호환 래퍼
from app.config.project_rules import apply_deadtime_pause

# 월요일 09:00 KST == 00:00 UTC 를 기준으로 사용
BASE = datetime(2025, 1, 6, 0, 0, tzinfo=timezone.utc)  # Mon 00:00 UTC

def _assert_tzaware(dt):
    assert dt.tzinfo is not None
    assert dt.tzinfo.utcoffset(dt) is not None

def test_minutes_keyword():
    got = apply_deadtime_pause(start_time=BASE, minutes=120)
    expect = BASE + timedelta(minutes=120)
    _assert_tzaware(got)
    assert got == expect

def test_minutes_with_start_alias():
    got = apply_deadtime_pause(start=BASE, minutes=30)
    expect = BASE + timedelta(minutes=30)
    _assert_tzaware(got)
    assert got == expect

def test_hours_keyword():
    got = apply_deadtime_pause(start_time=BASE, hours=2)
    expect = BASE + timedelta(hours=2)
    _assert_tzaware(got)
    assert got == expect

def test_duration_hours_keyword():
    got = apply_deadtime_pause(start_time=BASE, duration_hours=2)
    expect = BASE + timedelta(hours=2)
    _assert_tzaware(got)
    assert got == expect

def test_positional_hours():
    # (start_time, hours) 위치 인자 형태
    got = apply_deadtime_pause(BASE, 2)
    expect = BASE + timedelta(hours=2)
    _assert_tzaware(got)
    assert got == expect

def test_requires_param_error():
    # minutes나 hours/duration_hours가 하나도 없으면 TypeError
    with pytest.raises(TypeError):
        apply_deadtime_pause(start_time=BASE)
