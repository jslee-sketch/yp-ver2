# app/config/rules_v3_5.py
# YeokPing (역핑) 거래정책 v3.5 — Working Hour-Aware Edition
# Writer: Jeong Sang Lee
# Date: 2025-11-12

from __future__ import annotations

from enum import Enum
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timedelta, timezone

# DeadTime/타임라인 계산기 모듈
from app.config import time_policy as _tp

# ─────────────────────────────────────────────────────────
# DeadTime 함수/정책 호환 래퍼
# ─────────────────────────────────────────────────────────
_is_deadtime_fn = getattr(_tp, "is_deadtime", None) or getattr(_tp, "is_deadtime_kst", None)
_apply_deadtime_fn = getattr(_tp, "apply_deadtime_pause", None) or getattr(_tp, "apply_deadtime_pause_kst", None)

def is_deadtime(dt: datetime) -> bool:
    if _is_deadtime_fn is None:
        return False
    return _is_deadtime_fn(dt)  # type: ignore[misc]

def apply_deadtime_pause(start: datetime, *, hours: int = 0, minutes: int = 0, seconds: int = 0) -> datetime:
    """
    DeadTime-aware 종료시각 계산 래퍼.
    서로 다른 시그니처들을 안전하게 지원:
      A) apply_deadtime_pause(start, hours=..., minutes=..., seconds=...)
      B) apply_deadtime_pause(start, total_hours: float)
      C) apply_deadtime_pause(start, delta: timedelta)
    """
    if _apply_deadtime_fn is None:
        return start + timedelta(hours=hours, minutes=minutes, seconds=seconds)

    total_hours = hours + minutes / 60.0 + seconds / 3600.0
    # 1) kwargs 스타일
    try:
        return _apply_deadtime_fn(start, hours=hours, minutes=minutes, seconds=seconds)  # type: ignore[misc]
    except TypeError:
        pass
    # 2) float 시간 인자
    try:
        return _apply_deadtime_fn(start, total_hours)  # type: ignore[misc]
    except TypeError:
        pass
    # 3) timedelta 인자
    delta = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    return _apply_deadtime_fn(start, delta)  # type: ignore[misc]


# ─────────────────────────────────────────────────────────
# 메타 / 타임라인
# ─────────────────────────────────────────────────────────
KST = timezone(timedelta(hours=9))

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def now_kst() -> datetime:
    return datetime.now(KST)

_BASE_TIMELINE: Dict[str, Any] = {
    "SELLER_DECISION_WINDOW": 0.5,   # 판매자 의사결정 유예(시간)
    "BUYER_HOLD_MINUTES_DEFAULT": 5, # 예약 홀드 기본값(분)
}
TIMELINE: Dict[str, Any] = {**_BASE_TIMELINE, **(getattr(_tp, "TIME_POLICY", {}) or {})}
DEAD_TIME: Dict[str, Any] = getattr(_tp, "DEAD_TIME_POLICY", {"timezone": "Asia/Seoul"})

PROJECT_META: Dict[str, Any] = {
    "version": "v3.5",
    "codename": "Working Hour-Aware Edition",
    "author": "Jeong Sang Lee",
    "timezone": DEAD_TIME.get("timezone", "Asia/Seoul"),
    "last_update": "2025-11-12",
}


# ─────────────────────────────────────────────────────────
# ✅ Deposit / 예치금: v3.5 이후 전면 제거 (SSOT)
# ─────────────────────────────────────────────────────────
# NOTE:
# - deposit 관련 상수/규칙/함수는 “어디에도 존재하면 안 됨”
# - 과거 코드 호환을 위해 남겨두는 것도 금지(요구사항)
# - 따라서 rules_v3_5.py 에서 deposit 관련 심볼은 전부 제거한다.


# ─────────────────────────────────────────────────────────
# Buyer 포인트 규칙 (v3.5 확정)
# ─────────────────────────────────────────────────────────
BUYER_POINT_ON_PAID: int = 20
BUYER_POINT_ON_REFUND: int = -20

# 추천인 리워드
RECOMMENDER_REWARD_PT: int = 20

# 하위호환(기존 코드가 참조할 수 있는 명칭)
POINTS_REWARD_PAID: int = BUYER_POINT_ON_PAID
POINTS_REVOKE_REFUND: int = BUYER_POINT_ON_REFUND

BUYER_POINTS_GRADES: List[Tuple[int, str]] = [
    (500, "PLATINUM"),
    (201, "GOLD"),
    (51,  "SILVER"),
    (0,   "BRONZE"),
]

BUYER_POINT_BADGES: Dict[str, Any] = {
    "BRONZE":   {"min": 0,   "max": 50},
    "SILVER":   {"min": 51,  "max": 200},
    "GOLD":     {"min": 201, "max": 500},
    "PLATINUM": {"min": 501, "max": None},
}

def buyer_points_grade(points: int) -> str:
    for min_pts, grade in BUYER_POINTS_GRADES:
        if points >= min_pts:
            return grade
    return "BRONZE"


# ─────────────────────────────────────────────────────────
# Seller 레벨 & 플랫폼 수수료 (v3.5 확정)
# ─────────────────────────────────────────────────────────
# ✅ SSOT(퍼센트 단위): offers.py 등에서는 이 테이블을 우선 사용
SELLER_FEE_BY_LEVEL: Dict[str, float] = {
    "Lv.6": 3.5,
    "Lv.5": 3.0,
    "Lv.4": 2.8,
    "Lv.3": 2.7,
    "Lv.2": 2.5,
    "Lv.1": 2.0,
}

# 문서화/분기용 레벨 조건(거래건수/평점)
SELLER_LEVELS: Dict[str, Any] = {
    "levels": [
        {"name": "Lv.6", "min_orders": 0,   "max_orders": 20,   "min_rating": None, "fee_percent": 3.5},
        {"name": "Lv.5", "min_orders": 21,  "max_orders": 40,   "min_rating": 4.0,  "fee_percent": 3.0},
        {"name": "Lv.4", "min_orders": 41,  "max_orders": 60,   "min_rating": 4.0,  "fee_percent": 2.8},
        {"name": "Lv.3", "min_orders": 61,  "max_orders": 100,  "min_rating": 4.0,  "fee_percent": 2.7},
        {"name": "Lv.2", "min_orders": 101, "max_orders": None, "min_rating": 4.0,  "fee_percent": 2.5},
        {"name": "Lv.1", "min_orders": 101, "max_orders": None, "min_rating": 4.5,  "fee_percent": 2.0},
    ],
    "rating_source": "bayesian_adjusted",
}

def seller_level_for(total_sales: int, rating_adjusted: Optional[float]) -> Tuple[str, float]:
    """
    Returns: (level_name, fee_percent)
    rating_adjusted가 None이면 0으로 간주.
    """
    r = rating_adjusted or 0.0
    for lvl in SELLER_LEVELS["levels"]:
        min_orders = int(lvl.get("min_orders") or 0)
        max_orders = lvl.get("max_orders")
        min_rating = lvl.get("min_rating")
        if total_sales >= min_orders and (max_orders is None or total_sales <= max_orders):
            if min_rating is None or r >= float(min_rating):
                return (str(lvl["name"]), float(lvl["fee_percent"]))
    return ("Lv.6", float(SELLER_FEE_BY_LEVEL["Lv.6"]))


# ─────────────────────────────────────────────────────────
# Offer 제출/노출 규칙
# ─────────────────────────────────────────────────────────
OFFER_RULES: Dict[str, Any] = {
    "max_above_buyer_price": 0.10,  # 희망가 +10% 초과 제출 불가
    "visibility": {
        "below_or_equal": "public",
        "within_10_percent": "premium_section",
        "above_10_percent": "not_allowed",
    },
    "editable_until": "offer_deadline",
}

OFFER_EXPOSURE = {"premium_max_ratio": 1.10}

class OfferExposure:
    FULL = "FULL"
    PREMIUM = "PREMIUM"
    REJECT = "REJECT"

def classify_offer_price(wish_price: float, offer_price: float) -> str:
    if wish_price <= 0:
        return OfferExposure.REJECT
    ratio = offer_price / float(wish_price)
    if ratio <= 1.0:
        return OfferExposure.FULL
    if ratio <= OFFER_EXPOSURE["premium_max_ratio"]:
        return OfferExposure.PREMIUM
    return OfferExposure.REJECT


# ─────────────────────────────────────────────────────────
# 판매자 수락/철회 정책
# ─────────────────────────────────────────────────────────
class OfferDecisionState(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    WITHDRAWN = "WITHDRAWN"
    AUTO_WITHDRAWN = "AUTO_WITHDRAWN"
    AUTO_CONFIRMED = "AUTO_CONFIRMED"

OFFER_ACCEPTANCE_RULES = {
    "partial_paid": {"seller_can_withdraw_within_min": int(TIMELINE.get("SELLER_DECISION_WINDOW", 0) * 60) or 30},
    "full_paid": {"forced_accept": True, "auto_confirm": True},
    "no_payment": {"seller_can_withdraw_within_min": int(TIMELINE.get("SELLER_DECISION_WINDOW", 0) * 60) or 30},
    "auto_on_timeout": {"withdraw": True},
}


# ─────────────────────────────────────────────────────────
# 리뷰 시스템 핵심 파라미터(요약)
# ─────────────────────────────────────────────────────────
REVIEW_POLICY: Dict[str, Any] = {
    "verified_only": True,
    "dimensions": ["price_fairness", "quality", "shipping", "communication", "accuracy"],
    "weights": {
        "tier_weighting": {"TIER_1": 1.10, "TIER_2": 1.05, "TIER_3": 1.00, "TIER_4": 0.95, "TIER_5": 0.90},
        "media_bonus_per_item": 0.05,
        "media_bonus_cap": 0.25,
        "half_life_days": 365,
        "bayesian_prior_mean": 4.3,
        "bayesian_prior_weight": 5,
    },
    "anti_abuse": {"one_review_per_reservation": True, "seller_reply_once": True, "wilson_ci_for_helpful": True},
}


# ============================================
# 🔮 AI Deal Helper 관련 기본 규칙
# ============================================
DEAL_AI_CONFIG = {
    "max_option_titles": 5,
    "max_option_values_per_title": 8,
    "price_margin_pct": 0.10,
    "min_price_multiplier": 0.3,
    "max_price_multiplier": 3.0,
}


# ============================================
# 🔮 ACTUATOR FEE (Seller Level에 따라 결정) - ✅ rate(0~1) SSOT
# ============================================
# 0.5% = 0.005
ACTUATOR_FEE_RATE_BY_LEVEL: Dict[str, float] = {
    "Lv.6": 0.005,  # 0.5%
    "Lv.5": 0.002,  # 0.2%
    "Lv.4": 0.001,  # 0.1%
    "Lv.3": 0.0,
    "Lv.2": 0.0,
    "Lv.1": 0.0,
}

# (하위호환) 과거 코드가 percent(0.5=0.5%)를 기대하면 이걸 참조하게 두되,
# 값은 rate에서 자동 파생되게 해서 "진짜 SSOT는 rate"로 고정한다.
ACTUATOR_FEE_BY_LEVEL: Dict[str, float] = {
    k: float(v * 100.0) for k, v in ACTUATOR_FEE_RATE_BY_LEVEL.items()
}


__all__ = [
    # 메타/시간
    "PROJECT_META", "TIMELINE", "DEAD_TIME", "is_deadtime", "apply_deadtime_pause",
    "KST", "now_utc", "now_kst",

    # Buyer Points
    "BUYER_POINT_ON_PAID", "BUYER_POINT_ON_REFUND",
    "POINTS_REWARD_PAID", "POINTS_REVOKE_REFUND",
    "RECOMMENDER_REWARD_PT",
    "BUYER_POINTS_GRADES", "BUYER_POINT_BADGES", "buyer_points_grade",

    # Seller Level / Fee
    "SELLER_LEVELS", "SELLER_FEE_BY_LEVEL", "seller_level_for",

    # Offer 노출
    "OFFER_RULES", "OFFER_EXPOSURE", "OfferExposure", "classify_offer_price",

    # 판매자 의사결정
    "OfferDecisionState", "OFFER_ACCEPTANCE_RULES",

    # 리뷰
    "REVIEW_POLICY",

    # AI
    "DEAL_AI_CONFIG",

    # Actuator fee
    "ACTUATOR_FEE_RATE_BY_LEVEL",
    "ACTUATOR_FEE_BY_LEVEL",
]