# app/policy/params/guardrails.py
from __future__ import annotations

from app.policy.params.schema import PolicyBundle


class PolicyValidationError(ValueError):
    pass


def validate_policy(bundle: PolicyBundle) -> None:
    m = bundle.money
    t = bundle.time
    p = bundle.points_tier

    # --- money ---
    for name, v in [
        ("platform_fee_rate", m.platform_fee_rate),
        ("actuator_commission_rate", m.actuator_commission_rate),
        ("pg_fee_rate", m.pg_fee_rate),
    ]:
        if not (0.0 <= float(v) <= 1.0):
            raise PolicyValidationError(f"{name} must be between 0.0 and 1.0, got={v}")

    if m.platform_fee_rate + m.pg_fee_rate > 0.5:
        # 과도한 수수료 조합 방지 (가드레일 예시)
        raise PolicyValidationError(
            f"platform_fee_rate + pg_fee_rate too high: {m.platform_fee_rate}+{m.pg_fee_rate}"
        )

    # --- time ---
    if t.payment_timeout_minutes <= 0 or t.payment_timeout_minutes > 60:
        raise PolicyValidationError(
            f"payment_timeout_minutes must be 1~60, got={t.payment_timeout_minutes}"
        )
    # cooling_days는 전역 기본값(fallback)일 뿐이고,
    # 실제 쿨링은 offer_policies.cancel_within_days를 우선 사용한다.
    # 그래도 전역값은 운영상 말도 안 되게 큰 값만 막는다.
    if t.cooling_days < 0 or t.cooling_days > 365:
        raise PolicyValidationError(f"cooling_days must be 0~365, got={t.cooling_days}")




    for name, v in [
        ("seller_decision_timeout_hours", t.seller_decision_timeout_hours),
        ("deal_deadline_hours", t.deal_deadline_hours),
        ("offer_deadline_hours", t.offer_deadline_hours),
    ]:
        if v <= 0 or v > 24 * 30:
            raise PolicyValidationError(f"{name} out of range, got={v}")

    # --- points/tier ---
    if not (0.0 <= p.points_earn_rate <= 0.2):
        raise PolicyValidationError(f"points_earn_rate must be 0.0~0.2, got={p.points_earn_rate}")
    if p.points_expire_days < 0 or p.points_expire_days > 3650:
        raise PolicyValidationError(f"points_expire_days must be 0~3650, got={p.points_expire_days}")
    if p.tier_window_days <= 0 or p.tier_window_days > 365:
        raise PolicyValidationError(f"tier_window_days must be 1~365, got={p.tier_window_days}")
    if p.tier_min_gmv < 0:
        raise PolicyValidationError(f"tier_min_gmv must be >=0, got={p.tier_min_gmv}")