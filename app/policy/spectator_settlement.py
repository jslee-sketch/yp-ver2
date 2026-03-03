# app/policy/spectator_settlement.py
"""
관전자 적중 판정 로직.
settle_deal_predictions(db, deal_id, settled_price) 를 라우터에서 호출하면
해당 딜의 미판정 예측에 대해 tier 판정 → 포인트 적립 → 월간 통계 업데이트를 수행.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import yaml
from pathlib import Path
from sqlalchemy.orm import Session

from app import crud
from app.models import SpectatorPrediction

# YAML 파라미터 로딩
_YAML_PATH = Path(__file__).parent / "params" / "spectator.yaml"


def _load_params() -> dict:
    with open(_YAML_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["spectator"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── 헬퍼 ──────────────────────────────────────────────────

def get_prediction_config() -> dict:
    """YAML prediction 섹션 반환."""
    return _load_params()["prediction"]


def get_settlement_config() -> dict:
    """YAML settlement 섹션 반환."""
    return _load_params()["settlement"]


def compute_error_pct(predicted: int, settled: int) -> float:
    return abs(predicted - settled) / settled * 100


def judge_rank_tier(rank: int, predictions: int, rank_tiers: list) -> tuple[str, str, int]:
    """
    (tier_name, label, bonus_points) 반환.
    YAML ranks.tiers 순회.
    """
    for t in rank_tiers:
        if "condition_rank_lte" in t and rank <= t["condition_rank_lte"]:
            return t["name"], t.get("label", t["name"]), t.get("bonus_points", 0)
        if "condition_predictions_gte" in t and predictions >= t["condition_predictions_gte"]:
            return t["name"], t.get("label", t["name"]), t.get("bonus_points", 0)
    return "none", "", 0


# ── 핵심 판정 ─────────────────────────────────────────────

def judge_tier(error_pct: float, tiers: list) -> tuple[str, int, str]:
    """
    YAML scoring.tiers 순회 (exact → close → good → participate 순, 좁은 구간 우선).
    반환: (tier_name, points, label)
    """
    for tier in tiers:
        if error_pct <= tier["max_error_pct"]:
            return tier["name"], tier["points"], tier.get("label", tier["name"])
    return "miss", 0, "미스"


def get_settled_price(db: Session, deal_id: int) -> Optional[int]:
    """
    Reservation.status IN target_statuses 기준으로 Offer 가격 결정.
    pick: first(첫 번째) | lowest(최소) | average(평균)
    """
    params = _load_params()
    cfg = params["settlement"]
    target_statuses = cfg.get("target_status", ["PAID"])
    pick = cfg.get("pick", "first")

    from app.models import Reservation, Offer

    paid_offers = (
        db.query(Offer)
        .join(Reservation, Reservation.offer_id == Offer.id)
        .filter(
            Reservation.deal_id == deal_id,
            Reservation.status.in_(target_statuses),
        )
        .distinct()
        .order_by(Offer.created_at)
        .all()
    )
    if not paid_offers:
        return None

    prices = [int(o.price) for o in paid_offers]
    if pick == "lowest":
        return min(prices)
    if pick == "average":
        return round(sum(prices) / len(prices))
    return prices[0]  # "first"


def settle_deal_predictions(db: Session, deal_id: int, settled_price: int) -> int:
    """
    해당 딜의 모든 미판정 예측에 대해:
      1. 오차율 계산
      2. tier 판정
      3. points_earned 저장
      4. PointTransaction 적립 (idempotent)
      5. SpectatorMonthlyStats 업데이트
    반환: 처리된 예측 건수
    """
    params = _load_params()
    tiers = params["scoring"]["tiers"]

    # 미판정 예측만 처리 (settled_at is None)
    predictions = (
        db.query(SpectatorPrediction)
        .filter(
            SpectatorPrediction.deal_id == deal_id,
            SpectatorPrediction.settled_at.is_(None),
        )
        .all()
    )

    now = _utcnow()
    processed = 0

    for pred in predictions:
        error_pct = (
            compute_error_pct(pred.predicted_price, settled_price)
            if settled_price > 0
            else 0.0
        )
        tier_name, points, _label = judge_tier(error_pct, tiers)

        pred.settled_price = settled_price
        pred.error_pct = round(error_pct, 4)
        pred.tier_name = tier_name
        pred.points_earned = points
        pred.settled_at = now
        db.add(pred)

        # 포인트 적립 (idempotent)
        if points > 0:
            crud._add_points(
                db,
                user_type="buyer",
                user_id=pred.buyer_id,
                amount=points,
                reason=f"spectator_hit:{tier_name}",
                idempotency_key=f"spectator:deal:{deal_id}:buyer:{pred.buyer_id}",
            )

        # 월간 통계 업데이트
        year_month = now.strftime("%Y-%m")
        is_hit = points > 0
        is_exact = tier_name == "exact"

        from app.policy.spectator_ranking import update_monthly_stats
        update_monthly_stats(
            db,
            buyer_id=pred.buyer_id,
            year_month=year_month,
            points=points,
            error_pct=error_pct,
            is_hit=is_hit,
            is_exact=is_exact,
        )

        processed += 1

    db.flush()
    return processed
