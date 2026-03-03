# app/policy/spectator_ranking.py
"""
관전자 월간 통계 / 랭킹 업데이트 로직.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import yaml
from pathlib import Path
from sqlalchemy.orm import Session

from app.models import SpectatorMonthlyStats, SpectatorBadge, Buyer

_YAML_PATH = Path(__file__).parent / "params" / "spectator.yaml"


def _load_params() -> dict:
    with open(_YAML_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["spectator"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── UPSERT 헬퍼 ──────────────────────────────────────────

def _get_or_create_stats(
    db: Session, buyer_id: int, year_month: str
) -> SpectatorMonthlyStats:
    stats = (
        db.query(SpectatorMonthlyStats)
        .filter(
            SpectatorMonthlyStats.buyer_id == buyer_id,
            SpectatorMonthlyStats.year_month == year_month,
        )
        .first()
    )
    if not stats:
        stats = SpectatorMonthlyStats(
            buyer_id=buyer_id,
            year_month=year_month,
            total_points=0,
            predictions_count=0,
            hits_count=0,
            exact_count=0,
            avg_error_pct=None,
            rank_tier=None,
            bonus_points=0,
        )
        db.add(stats)
    return stats


# ── 통계 업데이트 ─────────────────────────────────────────

def update_monthly_stats(
    db: Session,
    buyer_id: int,
    year_month: str,
    points: int,
    error_pct: float,
    is_hit: bool,
    is_exact: bool,
) -> None:
    """
    SpectatorMonthlyStats를 UPSERT (get_or_create 패턴).
    avg_error_pct는 가중 평균으로 갱신.
    """
    stats = _get_or_create_stats(db, buyer_id, year_month)

    # 가중 평균 오차율 계산
    old_count = stats.predictions_count
    old_avg = stats.avg_error_pct or 0.0
    new_count = old_count + 1
    new_avg = (old_avg * old_count + error_pct) / new_count

    stats.total_points += points
    stats.predictions_count = new_count
    stats.avg_error_pct = round(new_avg, 4)
    if is_hit:
        stats.hits_count += 1
    if is_exact:
        stats.exact_count += 1

    db.add(stats)


# ── 랭킹 계산 ─────────────────────────────────────────────

def compute_rankings(db: Session, year_month: str) -> List[dict]:
    """
    year_month 기준 전체 stats 조회 → 총점/적중률/참여횟수 순 정렬 → rank 번호 부여.
    반환: list of dict (rank, buyer_id, nickname, total_points, ...)
    """
    rows: List[SpectatorMonthlyStats] = (
        db.query(SpectatorMonthlyStats)
        .filter(SpectatorMonthlyStats.year_month == year_month)
        .all()
    )

    # Buyer name 일괄 조회
    buyer_ids = [s.buyer_id for s in rows]
    buyer_map = {
        b.id: b.name
        for b in db.query(Buyer).filter(Buyer.id.in_(buyer_ids)).all()
    }

    # Badge 일괄 조회
    badge_map = {
        b.buyer_id: b.badge_type
        for b in db.query(SpectatorBadge)
            .filter(
                SpectatorBadge.buyer_id.in_(buyer_ids),
                SpectatorBadge.year_month == year_month,
            )
            .all()
    }

    def sort_key(s: SpectatorMonthlyStats):
        hit_rate = s.hits_count / s.predictions_count if s.predictions_count > 0 else 0.0
        return (-s.total_points, -hit_rate, -s.predictions_count)

    rows_sorted = sorted(rows, key=sort_key)

    result = []
    for rank_idx, s in enumerate(rows_sorted, start=1):
        hit_rate = (
            round(s.hits_count / s.predictions_count * 100, 1)
            if s.predictions_count > 0
            else 0.0
        )
        result.append(
            {
                "rank": rank_idx,
                "buyer_id": s.buyer_id,
                "nickname": buyer_map.get(s.buyer_id, f"buyer_{s.buyer_id}"),
                "total_points": s.total_points,
                "predictions_count": s.predictions_count,
                "hits_count": s.hits_count,
                "hit_rate": hit_rate,
                "exact_count": s.exact_count,
                "avg_error_pct": s.avg_error_pct,
                "tier": s.rank_tier,
                "badge": badge_map.get(s.buyer_id),
                "bonus_points": s.bonus_points,
            }
        )
    return result


# ── 등급 할당 ─────────────────────────────────────────────

def assign_rank_tiers(db: Session, year_month: str) -> None:
    """
    rankings 계산 → rank_tier, bonus_points 업데이트 → SpectatorBadge 생성.
    월말 정산 시 호출.
    """
    params = _load_params()
    rank_tiers = params["ranks"]["tiers"]
    rankings = compute_rankings(db, year_month)
    now = _utcnow()

    for entry in rankings:
        rank = entry["rank"]
        buyer_id = entry["buyer_id"]
        predictions_count = entry["predictions_count"]

        stats = (
            db.query(SpectatorMonthlyStats)
            .filter(
                SpectatorMonthlyStats.buyer_id == buyer_id,
                SpectatorMonthlyStats.year_month == year_month,
            )
            .first()
        )
        if not stats:
            continue

        assigned_tier: str | None = None
        assigned_bonus = 0
        badge_type: str | None = None

        for tier_cfg in rank_tiers:
            tier_name = tier_cfg["name"]
            # rank-based conditions
            if "condition_rank_lte" in tier_cfg and rank <= tier_cfg["condition_rank_lte"]:
                assigned_tier = tier_name
                assigned_bonus = tier_cfg.get("bonus_points", 0)
                badge_type = tier_cfg.get("badge")
                break
            # prediction-count conditions
            if (
                "condition_predictions_gte" in tier_cfg
                and predictions_count >= tier_cfg["condition_predictions_gte"]
            ):
                assigned_tier = tier_name
                assigned_bonus = tier_cfg.get("bonus_points", 0)
                badge_type = tier_cfg.get("badge")
                break

        stats.rank_tier = assigned_tier
        stats.bonus_points = assigned_bonus
        db.add(stats)

        # SpectatorBadge 생성 (중복 방지는 UNIQUE 제약으로)
        if assigned_tier and badge_type:
            existing = (
                db.query(SpectatorBadge)
                .filter(
                    SpectatorBadge.buyer_id == buyer_id,
                    SpectatorBadge.badge_type == badge_type,
                    SpectatorBadge.year_month == year_month,
                )
                .first()
            )
            if not existing:
                badge = SpectatorBadge(
                    buyer_id=buyer_id,
                    badge_type=badge_type,
                    year_month=year_month,
                    created_at=now,
                )
                db.add(badge)

        # 보너스 포인트 적립
        if assigned_bonus > 0:
            from app import crud
            crud._add_points(
                db,
                user_type="buyer",
                user_id=buyer_id,
                amount=assigned_bonus,
                reason=f"spectator_rank_bonus:{assigned_tier}",
                idempotency_key=f"spectator:rank_bonus:{year_month}:buyer:{buyer_id}",
            )

    db.flush()
