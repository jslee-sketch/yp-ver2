# app/policy/params/loader.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

from app.policy.params.schema import (
    MoneyPolicy,
    PointsPolicy,
    PointsTierPolicy,
    PolicyBundle,
    ReviewPolicy,
    SellerLevelRule,
    SellerPolicy,
    TimePolicy,
)
from app.policy.params.guardrails import validate_policy


_DEPOSIT_KEYS = {
    "deposit", "deposits", "deposit_policy", "depositpolicy",
    "buyer_deposit", "buyer_deposits",
    "deposit_rules", "deposit_tier_table", "deposit_tier_5_rule",
}


def _strip_deposit_keys(obj: Any) -> Any:
    """
    ✅ 구버전 정책 YAML에 남아있는 deposit 관련 블록을 모두 제거.
    - schema에서 DepositPolicy를 완전히 제거하더라도 로더가 절대 실패하지 않게 함.
    """
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            if str(k).strip().lower() in _DEPOSIT_KEYS:
                obj.pop(k, None)
        for v in list(obj.values()):
            _strip_deposit_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            _strip_deposit_keys(v)
    return obj


def _deep_get(d: dict, key: str) -> Any:
    if key not in d:
        raise KeyError(f"Missing key: {key}")
    return d[key]


def _normalize_actuator_fee_to_percent(v: Any) -> float:
    """
    actuator fee는 "퍼센트 단위"로 SSOT 유지:
      - 0.5  => 0.5% (percent)
      - 0.005 => 0.5% (rate로 들어온 케이스를 percent로 변환)
    휴리스틱:
      - v <= 0.05 이면 rate로 보고 *100
      - 그 외는 percent로 본다
    """
    try:
        x = float(v)
    except Exception:
        return 0.0
    if x < 0:
        return 0.0
    if x <= 0.05:   # 0.005(=0.5%) 같은 rate 입력
        return x * 100.0
    return x        # 0.5(=0.5%) 같은 percent 입력


def load_policy_yaml(path: str | None = None) -> PolicyBundle:
    """
    Loads policy bundle from YAML.
    - default: app/policy/params/defaults.yaml
    - override path by env POLICY_YAML_PATH or param
    """
    if path is None:
        path = os.environ.get("POLICY_YAML_PATH")

    if path is None:
        base = Path(__file__).resolve().parent
        path = str(base / "defaults.yaml")

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Policy YAML not found: {p}")

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    raw = _strip_deposit_keys(raw)

    money_raw = _deep_get(raw, "money")
    time_raw = _deep_get(raw, "time")
    points_tier_raw = _deep_get(raw, "points_tier")

    bundle = PolicyBundle(
        money=MoneyPolicy(
            platform_fee_rate=float(_deep_get(money_raw, "platform_fee_rate")),
            actuator_commission_rate=float(_deep_get(money_raw, "actuator_commission_rate")),
            pg_fee_rate=float(_deep_get(money_raw, "pg_fee_rate")),
            vat_rate=float(money_raw["vat_rate"]) if money_raw.get("vat_rate") is not None else None,
        ),
        time=TimePolicy(
            payment_timeout_minutes=int(_deep_get(time_raw, "payment_timeout_minutes")),
            cooling_days=int(_deep_get(time_raw, "cooling_days")),
            seller_decision_timeout_hours=int(_deep_get(time_raw, "seller_decision_timeout_hours")),
            deal_deadline_hours=int(_deep_get(time_raw, "deal_deadline_hours")),
            offer_deadline_hours=int(_deep_get(time_raw, "offer_deadline_hours")),
        ),
        points_tier=PointsTierPolicy(
            points_earn_rate=float(_deep_get(points_tier_raw, "points_earn_rate")),
            points_expire_days=int(_deep_get(points_tier_raw, "points_expire_days")),
            tier_window_days=int(_deep_get(points_tier_raw, "tier_window_days")),
            tier_min_gmv=int(_deep_get(points_tier_raw, "tier_min_gmv")),
        ),
    )

    # -------------------------------
    # Optional sections (v3.5+)
    # -------------------------------

    # seller
    seller_raw = raw.get("seller")
    if isinstance(seller_raw, dict) and seller_raw:
        levels: list[SellerLevelRule] = []
        levels_raw = seller_raw.get("levels") or []
        if isinstance(levels_raw, list):
            for it in levels_raw:
                if not isinstance(it, dict):
                    continue
                levels.append(
                    SellerLevelRule(
                        level=str(it.get("level") or "").strip(),
                        min_trades=int(it.get("min_trades") or 0),
                        max_trades=(int(it["max_trades"]) if it.get("max_trades") is not None else None),
                        min_rating=(float(it["min_rating"]) if it.get("min_rating") is not None else None),
                        platform_fee_rate=float(it.get("platform_fee_rate") or 0.0),
                    )
                )

        # actuator fee: YAML 키 이름이 흔들려도 흡수
        af_dict = (
            seller_raw.get("actuator_fee_by_level_percent")
            or seller_raw.get("actuator_fee_by_level")
            or seller_raw.get("actuator_fee_by_level_rate")
            or {}
        )

        actuator_fee_by_level_percent: Dict[str, float] = {}
        if isinstance(af_dict, dict):
            for k, v in af_dict.items():
                actuator_fee_by_level_percent[str(k)] = _normalize_actuator_fee_to_percent(v)

        bundle = PolicyBundle(
            money=bundle.money,
            time=bundle.time,
            points_tier=bundle.points_tier,
            seller=SellerPolicy(
                levels=levels,
                actuator_fee_by_level_percent=actuator_fee_by_level_percent,
                default_level=str(seller_raw.get("default_level") or "").strip() or None,
            ),
            points=bundle.points,
            review=bundle.review,
        )

    # points (event points)
    points_raw = raw.get("points")
    if isinstance(points_raw, dict) and points_raw:
        bundle = PolicyBundle(
            money=bundle.money,
            time=bundle.time,
            points_tier=bundle.points_tier,
            seller=bundle.seller,
            review=bundle.review,
            points=PointsPolicy(
                # 키 흔들림 방어: buyer_pay_reward_pt(오타/구키)도 흡수
                buyer_paid_reward_pt=int(points_raw.get("buyer_paid_reward_pt") or points_raw.get("buyer_pay_reward_pt") or 0),
                buyer_refund_penalty_pt=int(points_raw.get("buyer_refund_penalty_pt") or 0),
                recommender_reward_pt=int(points_raw.get("recommender_reward_pt") or 0),
            ),
        )

    # review
    review_raw = raw.get("review")
    if isinstance(review_raw, dict) and review_raw:
        bundle = PolicyBundle(
            money=bundle.money,
            time=bundle.time,
            points_tier=bundle.points_tier,
            seller=bundle.seller,
            points=bundle.points,
            review=ReviewPolicy(
                review_window_days=int(review_raw.get("review_window_days") or 0),
                verified_purchase_only=bool(review_raw.get("verified_purchase_only", True)),
            ),
        )

    validate_policy(bundle)
    return bundle