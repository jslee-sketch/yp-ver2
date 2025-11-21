# app/config/rules_v3_5.py
# v3.5 정책/룰 단일 모듈
# - DeadTime 대응용 타임라인/헬퍼
# - Deposit / Trust Tier
# - Buyer Points & 등급
# - Seller Level & 수수료
# - Offer 노출/제출 규칙

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
import math

# ---------------------------------------------------------------------
# 공통 시간 유틸
# ---------------------------------------------------------------------
KST = timezone(timedelta(hours=9))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_kst() -> datetime:
    return datetime.now(KST)


# 타임라인(시간 정책). 시간 단위 주의:
# - *_WINDOW 는 "시간" 단위(예: 0.5시간=30분)
# - *_MINUTES 는 "분" 단위
TIMELINE: dict[str, float] = {
    "SELLER_DECISION_WINDOW": 0.5,   # 판매자 의사결정 유예(시간)
    "BUYER_HOLD_MINUTES_DEFAULT": 5, # 예약 홀드 기본값(분)
}


def apply_deadtime_pause(start_utc: datetime, minutes: int) -> datetime:
    """
    DeadTime(야간/주말 등)을 고려해 마감시간을 뒤로 미루고 싶을 때 후킹되는 함수.
    현재는 단순 +minutes. 이후 필요 시 DeadTime 룰로 교체.
    """
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    return start_utc + timedelta(minutes=minutes)


# ---------------------------------------------------------------------
# Deposit / Trust Tier (v3.5)
#  - 이행률 = fulfillments / participations
#  - T5: 참여≥5 & 이행률≤20%  → 제한(참여 차단 플래그)
#  - 표에 맞춰 Deposit % 결정 (기본 10%)
#   * 퍼센트 값은 0.10 (10%)처럼 "비율"로 유지. 표시 시에는 x100 처리.
# ---------------------------------------------------------------------
DEPOSIT_DEFAULT_PERCENT: float = 0.10  # 10%

# (min_participations, min_fulfillment_rate, deposit_percent, name)
# 위에서부터 매칭되는 첫 항목을 채택
_DEPOSIT_TIERS: List[Tuple[int, float, float, str]] = [
    (10, 0.95, 0.00, "T1"),  # 골드
    (10, 0.86, 0.05, "T2"),  # 실버
    (10, 0.61, 0.08, "T3"),  # 브론즈
    (0,  0.00, 0.10, "T4"),  # 기본
]

DEPOSIT_TIER_5_RULE: dict[str, object] = {
    "min_participations": 5,
    "max_fulfillment_rate": 0.20,  # ≤ 20%
    "percent": 0.10,
    "restricted": True,            # 참여 제한 플래그
    "name": "T5",
}


def _fulfillment_rate(participations: int, fulfillments: int) -> float:
    if participations <= 0:
        return 0.0
    try:
        rate = fulfillments / float(participations)
    except Exception:
        return 0.0
    # [0,1] 범위로 클램핑
    return max(0.0, min(1.0, rate))


def trust_tier_for(participations: int, fulfillments: int) -> Tuple[str, float, bool]:
    """
    Returns: (tier_name, deposit_percent, restricted)
    - restricted=True 이면 참여 제한 대상(T5)
    - deposit_percent는 "비율" (예: 0.10 == 10%)
    """
    rate = _fulfillment_rate(participations, fulfillments)

    # Tier5 (제한) 우선 판정
    if (
        participations >= int(DEPOSIT_TIER_5_RULE["min_participations"])
        and rate <= float(DEPOSIT_TIER_5_RULE["max_fulfillment_rate"])
    ):
        return (
            str(DEPOSIT_TIER_5_RULE["name"]),
            float(DEPOSIT_TIER_5_RULE["percent"]),
            True,
        )

    # 일반 Tier
    for min_part, min_rate, percent, name in _DEPOSIT_TIERS:
        if participations >= min_part and rate >= min_rate:
            return (name, percent, False)

    # 안전망(도달 불가)
    return ("T4", DEPOSIT_DEFAULT_PERCENT, False)


def deposit_percent_for(participations: int, fulfillments: int) -> float:
    """티어 기준에 따른 디포짓 비율(예: 0.10 == 10%) 반환."""
    _, pct, _ = trust_tier_for(participations, fulfillments)
    return pct


# ---------------------------------------------------------------------
# Buyer Points & 등급 (표시/혜택 용도, v3.5)
# ---------------------------------------------------------------------
POINTS_REWARD_PAID: int = 20     # 결제 성공 시 +20
POINTS_REVOKE_REFUND: int = -20  # 환불/취소 시 -20 (사유 무관, PENDING 취소/만료는 0)

# (min_points, grade_name) 점수가 큰 것부터 매칭
_BUYER_POINTS_GRADES: List[Tuple[int, str]] = [
    (500, "PLATINUM"),
    (201, "GOLD"),
    (51,  "SILVER"),
    (0,   "BRONZE"),
]


def buyer_points_grade(points: int) -> str:
    for min_pts, grade in _BUYER_POINTS_GRADES:
        if points >= min_pts:
            return grade
    return "BRONZE"


# ---------------------------------------------------------------------
# Seller Level & 수수료 (누적 거래수/평점)
#  - (min_count, min_rating, fee_percent, level)
#  - 위에서부터 조건 만족하는 첫 항목을 채택
# ---------------------------------------------------------------------
_SELLER_LEVELS: List[Tuple[int, float, float, str]] = [
    (100, 4.5, 0.020, "Lv.1"),
    (100, 4.0, 0.025, "Lv.2"),
    (61,  4.0, 0.027, "Lv.3"),
    (41,  4.0, 0.028, "Lv.4"),
    (21,  4.0, 0.030, "Lv.5"),
    (0,   0.0, 0.035, "Lv.6"),
]


def seller_level_for(total_sales: int, rating_adjusted: Optional[float]) -> Tuple[str, float]:
    """
    Returns: (level_name, fee_percent)
    rating_adjusted가 None이면 0으로 간주.
    """
    r = rating_adjusted or 0.0
    for min_cnt, min_rating, fee, lvl in _SELLER_LEVELS:
        if total_sales >= min_cnt and r >= min_rating:
            return (lvl, fee)
    # 안전망
    return ("Lv.6", 0.035)


# ---------------------------------------------------------------------
# Offer 노출/제출 규칙
#  - wish_price(구매희망가) 대비 가격 수준에 따라
#    FULL(전면), PREMIUM(제한 노출), REJECT(제출 차단) 구분
# ---------------------------------------------------------------------
OFFER_EXPOSURE: dict[str, float] = {
    "premium_max_ratio": 1.10,  # 희망가 * 1.10 까지 PREMIUM 허용
}


class OfferExposure:
    FULL = "FULL"        # 전면 노출
    PREMIUM = "PREMIUM"  # 제한 노출(프리미엄 섹션)
    REJECT = "REJECT"    # 제출 차단


def classify_offer_price(wish_price: float, offer_price: float) -> str:
    # 비정상 값 방어
    if not (isinstance(wish_price, (int, float)) and isinstance(offer_price, (int, float))):
        return OfferExposure.REJECT
    if not (math.isfinite(wish_price) and math.isfinite(offer_price)):
        return OfferExposure.REJECT

    if wish_price <= 0:
        return OfferExposure.REJECT
    ratio = offer_price / float(wish_price)
    if ratio <= 1.0:
        return OfferExposure.FULL
    if ratio <= OFFER_EXPOSURE["premium_max_ratio"]:
        return OfferExposure.PREMIUM
    return OfferExposure.REJECT


# ---------------------------------------------------------------------
# 내보낼 심볼
# ---------------------------------------------------------------------
__all__: list[str] = [
    # 시간/타임라인
    "KST", "now_utc", "now_kst", "TIMELINE", "apply_deadtime_pause",
    # Deposit/Trust
    "DEPOSIT_DEFAULT_PERCENT", "DEPOSIT_TIER_5_RULE",
    "trust_tier_for", "deposit_percent_for",
    # Buyer Points
    "POINTS_REWARD_PAID", "POINTS_REVOKE_REFUND", "buyer_points_grade",
    # Seller Level
    "seller_level_for",
    # Offer 노출
    "OFFER_EXPOSURE", "OfferExposure", "classify_offer_price",
]