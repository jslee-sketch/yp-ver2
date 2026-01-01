# scripts/verify_policy_integration.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone

from app.policy.runtime import reload_policy_cache
from app.policy.api import (
    payment_timeout_minutes, cooling_days, points_earn_rate,
    is_payment_window_valid, compute_cooling_state, calc_points_earnable
)

def main():
    # 캐시 리로드 (테스트 편의)
    reload_policy_cache()

    print("payment_timeout_minutes:", payment_timeout_minutes())
    print("cooling_days:", cooling_days())
    print("points_earn_rate:", points_earn_rate())

    now = datetime.now(timezone.utc)
    reserved_at = now - timedelta(minutes=9)   # 기본 10분 제한이면 True여야 함
    print("is_payment_window_valid(9m):", is_payment_window_valid(reserved_at, now))

    paid_at = now - timedelta(days=6)
    shipped_at = paid_at + timedelta(days=1)
    delivered_at = paid_at + timedelta(days=2)
    print("cooling_state(6d since paid):", compute_cooling_state(paid_at, shipped_at, delivered_at, now))

    print("points on 315000:", calc_points_earnable(315000))

if __name__ == "__main__":
    main()