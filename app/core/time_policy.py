# app/core/time_policy.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class TimePolicy:
    """
    시간 관련 전역 정책 모음 (v1).

    필요하면 여기 필드만 늘리고,
    비즈니스 로직에서는 TIME_POLICY.* 값만 참조하게 만든다.
    """
    # 1) 예약 결제 가능 시간 (분 단위)
    reservation_pay_window_minutes: int = 120  # 예: 2시간

    # 2) 방장 우선 결제 시간 (분 단위)
    host_priority_minutes: int = 15

    # 3) 도착 후 쿨링타임 (일 단위)
    cooling_days: int = 14

    # 🆕 4) 액츄에이터 커미션: 쿨링 종료 후 추가 버퍼 (일 단위)
    #    → ready_at = 기준일 + cooling_days + actuator_payout_after_cooling_days
    actuator_payout_after_cooling_days: int = 30



# 전역 싱글톤 인스턴스
TIME_POLICY = TimePolicy()


def _utcnow() -> datetime:
    """
    시스템 공용 UTC now 헬퍼.

    - 모든 비즈니스 로직에서 같은 함수를 쓰도록 강제해서
      타임존/테스트 일관성을 확보하기 위함.
    """
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    DB에서 나온 datetime 을 안전하게 UTC aware 로 바꿔주는 헬퍼.

    - dt 가 None 이면 None 리턴
    - naive datetime 이면 UTC 로 가정해서 tzinfo 붙임
    - 이미 tz 가 있으면 UTC 로 변환
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)