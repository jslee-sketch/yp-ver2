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
# 함수명/시그니처가 환경에 따라 다를 수 있어서 안전하게 래핑
_is_deadtime_fn = getattr(_tp, "is_deadtime", None) or getattr(_tp, "is_deadtime_kst", None)
_apply_deadtime_fn = getattr(_tp, "apply_deadtime_pause", None) or getattr(_tp, "apply_deadtime_pause_kst", None)

def is_deadtime(dt: datetime) -> bool:
    if _is_deadtime_fn is None:
        # 최후 수단: DeadTime 비활성 취급
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
        # DeadTime 비고려 fallback
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

# 기본 타임라인 + 프로젝트 설정 병합
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
# Deposit / Trust Tier (v3.5)
# ─────────────────────────────────────────────────────────
# 기본 비율
DEPOSIT_DEFAULT_PERCENT: float = 0.10  # 10%

# 정책 사전(레퍼런스용)
DEPOSIT_RULES: Dict[str, Any] = {
    "default_rate": DEPOSIT_DEFAULT_PERCENT,
    "tier_rates": {
        "TIER_1": 0.00,
        "TIER_2": 0.05,
        "TIER_3": 0.08,
        "TIER_4": 0.10,
        "TIER_5": 0.10,
    },
    "deposit_deadline": "before_deal_closing",
    "refund_policy": {
        "success": "immediate_refund",  # 판매자 수락/철회 마감 시 즉시 반환
        "failure": "immediate_refund",
    },
    "non_payment_action": "auto_remove_from_deal",
    "purpose": "prevent_fake_participation",
}

# (min_participations, min_fulfillment_rate, deposit_percent, name)
# 위에서부터 매칭되는 첫 항목을 채택
_DEPOSIT_TIERS: List[Tuple[int, float, float, str]] = [
    (10, 0.95, 0.00, "T1"),  # 골드
    (10, 0.86, 0.05, "T2"),  # 실버
    (10, 0.61, 0.08, "T3"),  # 브론즈
    (0,  0.00, 0.10, "T4"),  # 기본
]

# ★ 하위호환: logic.trust 에서 참조하는 심볼
DEPOSIT_TIER_5_RULE: Dict[str, Any] = {
    "min_participations": 5,
    "max_fulfillment_rate": 0.20,  # ≤ 20%
    "percent": 0.10,
    "restricted": True,            # 참여 제한 플래그
    "name": "T5",
}

# 신규 규칙 테이블(문서화용)
BUYER_TRUST_TIER_RULES: Dict[str, Any] = {
    "tiers": [
        {"name": "TIER_1", "min_participation": 10, "min_rate": 0.95, "deposit_rate": 0.00, "badge": "GOLD"},
        {"name": "TIER_2", "min_participation": 10, "min_rate": 0.86, "max_rate": 0.95, "deposit_rate": 0.05, "badge": "SILVER"},
        {"name": "TIER_3", "min_participation": 10, "min_rate": 0.61, "max_rate": 0.85, "deposit_rate": 0.08, "badge": "BRONZE"},
        {"name": "TIER_4", "min_participation": 0,  "min_rate": 0.00, "max_rate": 1.00, "deposit_rate": 0.10, "badge": None},
        {"name": "TIER_5", "min_participation": 5,  "max_rate": 0.20, "deposit_rate": 0.10, "restricted": True},
    ],
    "recompute_policy": "daily_or_event_driven",
}

def _fulfillment_rate(participations: int, fulfillments: int) -> float:
    if participations <= 0:
        return 0.0
    return max(0.0, min(1.0, fulfillments / float(participations)))

def trust_tier_for(participations: int, fulfillments: int) -> Tuple[str, float, bool]:
    """
    Returns: (tier_name, deposit_percent, restricted)
    - restricted=True 이면 참여 제한 대상(T5)
    """
    rate = _fulfillment_rate(participations, fulfillments)

    # Tier5 (제한) 우선 판정 — 하위호환 심볼 사용
    if (
        participations >= int(DEPOSIT_TIER_5_RULE["min_participations"])
        and rate <= float(DEPOSIT_TIER_5_RULE["max_fulfillment_rate"])
    ):
        return (str(DEPOSIT_TIER_5_RULE["name"]), float(DEPOSIT_TIER_5_RULE["percent"]), True)

    # 일반 Tier
    for min_part, min_rate, percent, name in _DEPOSIT_TIERS:
        if participations >= min_part and rate >= min_rate:
            return (name, percent, False)

    # 안전망(도달 불가)
    return ("T4", DEPOSIT_DEFAULT_PERCENT, False)

def deposit_percent_for(participations: int, fulfillments: int) -> float:
    """티어 기준에 따른 디포짓 비율 반환."""
    _, pct, _ = trust_tier_for(participations, fulfillments)
    return pct


# ─────────────────────────────────────────────────────────
# Buyer 포인트 규칙 (v3.5 확정)
# ─────────────────────────────────────────────────────────
# 신규/설명용 명칭
BUYER_POINT_ON_PAID: int = 20
BUYER_POINT_ON_REFUND: int = -20
# 하위호환(기존 코드가 참조할 수 있는 명칭)
POINTS_REWARD_PAID: int = BUYER_POINT_ON_PAID
POINTS_REVOKE_REFUND: int = BUYER_POINT_ON_REFUND

# ★ 하위호환: logic.trust 가 참조하는 공개 상수 (리스트 튜플 형식)
BUYER_POINTS_GRADES: List[Tuple[int, str]] = [
    (500, "PLATINUM"),
    (201, "GOLD"),
    (51,  "SILVER"),
    (0,   "BRONZE"),
]
# 문서용/표현용 dict (기존에 사용 중일 수도 있어서 함께 제공)
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
# Seller 레벨 & 수수료
# ─────────────────────────────────────────────────────────
SELLER_LEVELS: Dict[str, Any] = {
    "levels": [
        {"name": "Lv.6", "min_orders": 0,   "max_orders": 20,  "min_rating": None, "fee_rate": 0.035},
        {"name": "Lv.5", "min_orders": 21,  "max_orders": 40,  "min_rating": 4.0,  "fee_rate": 0.030},
        {"name": "Lv.4", "min_orders": 41,  "max_orders": 60,  "min_rating": 4.0,  "fee_rate": 0.028},
        {"name": "Lv.3", "min_orders": 61,  "max_orders": 100, "min_rating": 4.0,  "fee_rate": 0.027},
        {"name": "Lv.2", "min_orders": 101, "max_orders": None,"min_rating": 4.0,  "fee_rate": 0.025},
        {"name": "Lv.1", "min_orders": 101, "max_orders": None,"min_rating": 4.5,  "fee_rate": 0.020},
    ],
    "rating_source": "bayesian_adjusted",
}

def seller_level_for(total_sales: int, rating_adjusted: Optional[float]) -> Tuple[str, float]:
    """
    Returns: (level_name, fee_percent)
    rating_adjusted가 None이면 0으로 간주.
    """
    r = rating_adjusted or 0.0
    # 조건 충족하는 첫 항목 반환(상위 레벨 우선)
    for lvl in SELLER_LEVELS["levels"]:
        min_orders = int(lvl.get("min_orders") or 0)
        max_orders = lvl.get("max_orders")
        min_rating = lvl.get("min_rating")
        if total_sales >= min_orders and (max_orders is None or total_sales <= max_orders):
            if min_rating is None or r >= float(min_rating):
                return (str(lvl["name"]), float(lvl["fee_rate"]))
    # 안전망
    return ("Lv.6", 0.035)


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

# 하위호환(기존 메소드 사용 대비)
OFFER_EXPOSURE = {"premium_max_ratio": 1.10}

class OfferExposure:
    FULL = "FULL"        # 전면 노출
    PREMIUM = "PREMIUM"  # 제한 노출(프리미엄 섹션)
    REJECT = "REJECT"    # 제출 차단

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
    # 부분수량 판매(일부 PAID): 30분 내 철회 가능, 미응답 자동 철회
    "partial_paid": {"seller_can_withdraw_within_min": int(TIMELINE.get("SELLER_DECISION_WINDOW", 0) * 60) or 30},
    # 전량 판매(전량 PAID): 철회 불가, 자동 수락(확정)
    "full_paid": {"forced_accept": True, "auto_confirm": True},
    # 결제 미발생: 철회 가능
    "no_payment": {"seller_can_withdraw_within_min": int(TIMELINE.get("SELLER_DECISION_WINDOW", 0) * 60) or 30},
    # 타임아웃: 자동 철회
    "auto_on_timeout": {"withdraw": True},
}

# ─────────────────────────────────────────────────────────
# 리뷰 시스템 핵심 파라미터(요약)
# ─────────────────────────────────────────────────────────
REVIEW_POLICY: Dict[str, Any] = {
    "verified_only": True,
    "dimensions": ["price_fairness", "quality", "shipping", "communication", "accuracy"],  # 1~5점
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

__all__ = [
    # 메타/시간
    "PROJECT_META", "TIMELINE", "DEAD_TIME", "is_deadtime", "apply_deadtime_pause",
    "KST", "now_utc", "now_kst",
    # Deposit/Trust
    "DEPOSIT_DEFAULT_PERCENT", "DEPOSIT_RULES",
    "DEPOSIT_TIER_5_RULE", "BUYER_TRUST_TIER_RULES",
    "trust_tier_for", "deposit_percent_for",
    # Buyer Points
    "BUYER_POINT_ON_PAID", "BUYER_POINT_ON_REFUND",
    "POINTS_REWARD_PAID", "POINTS_REVOKE_REFUND",
    "BUYER_POINTS_GRADES", "BUYER_POINT_BADGES", "buyer_points_grade",
    # Seller Level
    "SELLER_LEVELS", "seller_level_for",
    # Offer 노출
    "OFFER_RULES", "OFFER_EXPOSURE", "OfferExposure", "classify_offer_price",
    # 판매자 의사결정
    "OfferDecisionState", "OFFER_ACCEPTANCE_RULES",
    # 리뷰
    "REVIEW_POLICY",
]