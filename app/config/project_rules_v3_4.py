# app/config/project_rules_v3_4.py
# YeokPing (역핑) 거래정책 v3.4 — Working Hour-Aware Edition
# Writer: Jeong Sang Lee
# Date: 2025-11-02

from enum import Enum
from app.config import time_policy

# -------------------------------------------------------
# 🔹 시스템 타임라인 (KST = UTC+9)
# -------------------------------------------------------

UTC_OFFSET = 9  # KST 기준
TIMELINE = time_policy.TIME_POLICY  # 모든 이벤트 시간 정책
DEAD_TIME = time_policy.DEAD_TIME_POLICY  # Dead Time 정책
is_deadtime = time_policy.is_deadtime  # Dead Time 판별 함수
apply_deadtime_pause = time_policy.apply_deadtime_pause  # Dead Time 고려 종료시간 계산기

# -------------------------------------------------------
# 🔹 Deposit 정책
# -------------------------------------------------------

DEPOSIT_RULES = {
    "default_rate": 0.10,
    "tier_rates": {  # Trust Tier별 차등
        1: 0.10,
        2: 0.05,
        3: 0.00,
        4: 0.00,
    },
    "deposit_deadline": "before_deal_closing",
    "refund_policy": {
        "success": "immediate_refund",
        "failure": "immediate_refund",
    },
    "non_payment_action": "auto_remove_from_deal",
    "purpose": "prevent_fake_participation",
}

# -------------------------------------------------------
# 🔹 Trust Tier 정의
# -------------------------------------------------------

class TrustTier(Enum):
    ROOKIE = 1
    SOLID = 2
    ELITE = 3
    LEGEND = 4

TRUST_TIER_RULES = {
    TrustTier.ROOKIE: {
        "min_success_rate": 0.0,
        "max_success_rate": 0.6,
        "deposit_rate": 0.10,
        "benefits": ["기본 참여 가능"],
    },
    TrustTier.SOLID: {
        "min_success_rate": 0.6,
        "max_success_rate": 0.85,
        "deposit_rate": 0.05,
        "benefits": ["신뢰 뱃지 부여"],
    },
    TrustTier.ELITE: {
        "min_success_rate": 0.85,
        "max_success_rate": 0.95,
        "deposit_rate": 0.0,
        "benefits": ["Deposit 면제", "우선초대"],
    },
    TrustTier.LEGEND: {
        "min_success_rate": 0.95,
        "max_success_rate": 1.0,
        "min_transactions": 50,
        "deposit_rate": 0.0,
        "benefits": ["특별딜 우선권", "리워드 제공"],
    },
}

# -------------------------------------------------------
# 🔹 Offer 정책
# -------------------------------------------------------

OFFER_RULES = {
    "max_above_buyer_price": 0.10,  # 구매희망가 +10% 초과시 Offer 불가
    "visibility": {
        "below_or_equal": "public",
        "within_10_percent": "premium_section",
        "above_10_percent": "not_allowed",
    },
    "editable_until": "offer_deadline",  # Offer 생성 후 마감 전까지 수정 가능
}

# -------------------------------------------------------
# 🔹 Offer 수락 및 철회 규칙
# -------------------------------------------------------

OFFER_ACCEPTANCE_RULES = [
    {
        "buyer_price_relation": "≤",
        "full_sellout": True,
        "seller_action": "auto_accept",
        "status": "confirmed",
    },
    {
        "buyer_price_relation": "≤",
        "full_sellout": False,
        "seller_action": "accept_or_withdraw_within_30m",
        "status": "pending",
    },
    {
        "buyer_price_relation": ">",
        "full_sellout": True,
        "seller_action": "auto_accept",
        "status": "confirmed",
    },
    {
        "buyer_price_relation": ">",
        "full_sellout": False,
        "seller_action": "accept_or_withdraw_within_30m",
        "status": "pending",
    },
]

# -------------------------------------------------------
# 🔹 Trigger Points
# -------------------------------------------------------

TRIGGERS = {
    "deal_close": f"{TIMELINE['DEAL_CREATION_WINDOW']}h_after_creation_excluding_deadtime",
    "offer_start": "immediate_after_deal_close",
    "offer_close": f"{TIMELINE['OFFER_EDITABLE_WINDOW']}h_after_offer_start_excluding_deadtime",
    "buyer_payment_window": f"starts_after_offer_close_for_{TIMELINE['BUYER_PAYMENT_WINDOW']}h",
    "seller_decision_window": f"{TIMELINE['SELLER_DECISION_WINDOW']}h_after_buyer_payment_window",
    "trust_tier_update": "weekly_scheduler",
    "new_seller_verification": f"admin_approval_within_{TIMELINE['SELLER_VERIFICATION_WINDOW']}h",
}

# -------------------------------------------------------
# 🔹 확장 기능 계획
# -------------------------------------------------------

FUTURE_FEATURES = {
    "ai_option_autofill": True,    # 옵션 자동매칭
    "ai_offer_suggestion": True,   # AI Offer 가이드
    "chat_layer": True,            # 실시간 상담
    "seller_trust_index": True,    # 판매자 평판점수
    "deal_analysis_report": True,  # 실패딜 분석 리포트
    "multi_region_deadtime": True, # 글로벌 DeadTime 대응
}

# -------------------------------------------------------
# ✅ 요약 메타정보
# -------------------------------------------------------

PROJECT_META = {
    "version": "v3.4",
    "codename": "Working Hour-Aware Edition",
    "author": "Jeong Sang Lee",
    "timezone": DEAD_TIME["timezone"],
    "last_update": "2025-11-02",
}