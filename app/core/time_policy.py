# app/core/time_policy.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _load_from_yaml() -> dict:
    """defaults.yaml에서 time 섹션을 로드 (실패 시 빈 dict)."""
    try:
        from pathlib import Path
        import yaml
        p = Path(__file__).resolve().parent.parent / "policy" / "params" / "defaults.yaml"
        if p.exists():
            raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            return raw.get("time", {})
    except Exception:
        pass
    return {}


@dataclass
class TimePolicy:
    """
    시간 관련 전역 정책 모음.

    SSOT: app/policy/params/defaults.yaml → time 섹션.
    여기의 기본값은 yaml 로드 실패 시 fallback.
    """
    # 1) 예약 결제 가능 시간 (분 단위) — yaml: payment_timeout_minutes
    reservation_pay_window_minutes: int = 5

    # 2) 방장 우선 결제 시간 (분 단위)
    host_priority_minutes: int = 15

    # 3) 도착 후 쿨링타임 (일 단위) — yaml: cooling_days
    cooling_days: int = 7

    # 4) 액츄에이터 커미션: 쿨링 종료 후 추가 버퍼 (일 단위)
    actuator_payout_after_cooling_days: int = 30


def _build_time_policy() -> TimePolicy:
    """yaml SSOT에서 값을 읽어 TimePolicy 인스턴스 생성."""
    y = _load_from_yaml()
    return TimePolicy(
        reservation_pay_window_minutes=int(y.get("payment_timeout_minutes", 5)),
        host_priority_minutes=15,
        cooling_days=int(y.get("cooling_days", 7)),
        actuator_payout_after_cooling_days=30,
    )


# 전역 싱글톤 인스턴스 (yaml SSOT 반영)
TIME_POLICY = _build_time_policy()


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