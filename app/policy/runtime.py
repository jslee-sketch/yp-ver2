# app/policy/runtime.py
from __future__ import annotations
from functools import lru_cache
from app.policy.params.loader import load_policy_yaml
from app.policy.params.schema import PolicyBundle


@lru_cache(maxsize=1)
def get_policy() -> PolicyBundle:
    """
    앱 전역에서 사용하는 정책 접근자.
    - 최초 1회만 YAML 로드 (lru_cache)
    - 프로세스 재시작 전까지 캐시됨
    """
    return load_policy_yaml()


def reload_policy_cache() -> PolicyBundle:
    """테스트나 운영 중 재로드가 필요할 때 호출 (드물게)."""
    get_policy.cache_clear()  # type: ignore[attr-defined]
    return get_policy()