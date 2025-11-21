# tests/test_deadtime_policy.py
from datetime import datetime, timezone, timedelta
from app.config import project_rules as R

KST = timezone(timedelta(hours=9))

def kst(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=KST)

def case(name, start_kst, expected_kst_str, **delta):
    end_utc = R.apply_deadtime_pause(start_kst, **delta)
    end_kst = end_utc.astimezone(KST)
    got = end_kst.strftime("%Y-%m-%d %H:%M")
    assert got == expected_kst_str, f"{name}: expected {expected_kst_str}, got {got}"

def test_deadtime_examples():
    case("Fri 17:30 + 2h",  kst(2025,11,7,17,30), "2025-11-10 10:30", hours=2)
    case("Fri 17:30 + 30m", kst(2025,11,7,17,30), "2025-11-07 18:00", minutes=30)
    case("Sat 12:00 + 1h",  kst(2025,11,8,12,0),  "2025-11-10 10:00", hours=1)
    case("Mon 08:50 + 30m", kst(2025,11,10,8,50), "2025-11-10 09:30", minutes=30)
    case("Mon 17:45 + 45m", kst(2025,11,10,17,45),"2025-11-11 09:30", minutes=45)