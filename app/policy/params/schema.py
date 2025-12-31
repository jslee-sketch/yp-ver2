from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict


class PolicyBase(BaseModel):
    # ✅ 구버전 yaml에 알 수 없는 키가 남아 있어도 무시(=파싱 성공)
    model_config = ConfigDict(extra="ignore")


ShippingMode = Literal["PER_RESERVATION", "PER_QTY"]


@dataclass(frozen=True)
class MoneyPolicy:
    """금전/수수료 정책."""

    # (레거시/기본) 플랫폼 수수료율 (rate: 0~1, 예: 0.035=3.5%)
    platform_fee_rate: float

    # (레거시/기본) 액추에이터 커미션율 (rate: 0~1)
    actuator_commission_rate: float

    # PG 수수료율 (rate: 0~1)
    pg_fee_rate: float

    # (선택) VAT 등 (rate: 0~1)
    vat_rate: Optional[float] = None


@dataclass(frozen=True)
class TimePolicy:
    payment_timeout_minutes: int
    cooling_days: int
    seller_decision_timeout_hours: int
    deal_deadline_hours: int
    offer_deadline_hours: int


@dataclass(frozen=True)
class PointsTierPolicy:
    """(레거시) 결제금액 비례 적립률/티어 정책."""
    points_earn_rate: float
    points_expire_days: int
    tier_window_days: int
    tier_min_gmv: int


# -------------------------
# v3.5+ 확장 정책
# -------------------------

@dataclass(frozen=True)
class SellerLevelRule:
    """판매자 레벨 판정 + 해당 레벨 플랫폼 수수료율."""
    level: str                  # 예: "Lv.6"
    min_trades: int
    max_trades: Optional[int]
    min_rating: Optional[float]
    platform_fee_rate: float    # rate: 0~1 (예: 0.035 = 3.5%)


@dataclass(frozen=True)
class SellerPolicy:
    """
    판매자 정책 SSOT.

    - levels: 레벨 판정 규칙(+레벨별 플랫폼 수수료율)
    - actuator_fee_by_level_percent: 레벨별 액추에이터 배분률(퍼센트 단위)
      예) 0.5 = 0.5%  (기존 rules_v3_5와 동일 단위)
    - default_level: 매칭 실패 시 기본 레벨
    """
    levels: List[SellerLevelRule]
    actuator_fee_by_level_percent: Dict[str, float]
    default_level: Optional[str] = None


@dataclass(frozen=True)
class PointsPolicy:
    """(v3.5) 이벤트 기반 포인트 정책."""
    buyer_paid_reward_pt: int
    buyer_refund_penalty_pt: int
    recommender_reward_pt: int


@dataclass(frozen=True)
class ReviewPolicy:
    review_window_days: int
    verified_purchase_only: bool = True


@dataclass(frozen=True)
class PolicyBundle:
    money: MoneyPolicy
    time: TimePolicy
    points_tier: PointsTierPolicy

    # v3.5+ (선택)
    seller: Optional[SellerPolicy] = None
    points: Optional[PointsPolicy] = None
    review: Optional[ReviewPolicy] = None