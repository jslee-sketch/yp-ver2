# app/core/rules_loader.py
# 역핑 (YeokPing) 정책 엔진 로더
# Version: v3.4 - Working Hour-Aware Edition
# Author: Jeong Sang Lee

import datetime
from typing import Optional
from app.config import project_rules_v3_4 as RULES


class RuleLoader:
    """역핑 정책 매니저 — project_rules_v3_4.py 의 상수를 해석하여 제공"""

    def __init__(self):
        self.rules = RULES

    # ---------------------------------------------------
    # 🔹 Timezone / DeadTime 관련
    # ---------------------------------------------------
    def get_current_kst(self) -> datetime.datetime:
        """현재 시간을 KST 기준으로 반환"""
        return datetime.datetime.utcnow() + datetime.timedelta(hours=RULES.UTC_OFFSET)

    def is_deadtime(self, check_time: Optional[datetime.datetime] = None) -> bool:
        """DeadTime 여부 판단"""
        now = check_time or self.get_current_kst()
        weekday = now.weekday()  # 0=월, 6=일
        return RULES.is_deadtime(now.time(), weekday)

    def apply_deadtime_pause(self, start_time: datetime.datetime, duration_hours: int) -> datetime.datetime:
        """
        DeadTime을 고려하여 실제 종료시간 계산
        ex) 금요일 17시 + 24시간 = 월요일 9시
        """
        remaining = datetime.timedelta(hours=duration_hours)
        current = start_time

        while remaining.total_seconds() > 0:
            current += datetime.timedelta(minutes=15)
            if not self.is_deadtime(current):
                remaining -= datetime.timedelta(minutes=15)
        return current

    # ---------------------------------------------------
    # 🔹 Offer 관련 규칙
    # ---------------------------------------------------
    def validate_offer_price(self, offer_price: float, buyer_price: float) -> bool:
        """Offer가 구매희망가 +10%를 초과하는지 검증"""
        limit_price = buyer_price * (1 + RULES.OFFER_RULES["max_above_buyer_price"])
        return offer_price <= limit_price

    def offer_visibility(self, offer_price: float, buyer_price: float) -> str:
        """Offer 노출 섹션 결정"""
        ratio = offer_price / buyer_price
        if ratio <= 1:
            return RULES.OFFER_RULES["visibility"]["below_or_equal"]
        elif ratio <= 1.1:
            return RULES.OFFER_RULES["visibility"]["within_10_percent"]
        else:
            return RULES.OFFER_RULES["visibility"]["above_10_percent"]

    # ---------------------------------------------------
    # 🔹 Deposit 관련
    # ---------------------------------------------------
    def get_deposit_rate(self, trust_tier: int) -> float:
        """Trust Tier에 따른 Deposit 비율 반환"""
        return RULES.DEPOSIT_RULES["tier_rates"].get(trust_tier, RULES.DEPOSIT_RULES["default_rate"])

    # ---------------------------------------------------
    # 🔹 타임라인 관련
    # ---------------------------------------------------
    def get_timeline_hours(self, event: str) -> Optional[float]:
        """Deal, Offer, Payment 등 이벤트별 타임라인 반환"""
        return RULES.TIMELINE.get(event)

    # ---------------------------------------------------
    # 🔹 트리거 포인트 및 후속작업
    # ---------------------------------------------------
    def get_trigger_description(self, trigger: str) -> str:
        """Trigger Point 설명 반환"""
        return RULES.TRIGGERS.get(trigger, "No such trigger defined.")

    # ---------------------------------------------------
    # 🔹 확장 기능 관련
    # ---------------------------------------------------
    def get_future_features(self) -> dict:
        """예정된 확장기능 목록 반환"""
        return RULES.FUTURE_FEATURES

    # ---------------------------------------------------
    # 🔹 메타정보
    # ---------------------------------------------------
    def get_project_meta(self) -> dict:
        """프로젝트 버전/작성자 등 메타정보 반환"""
        return RULES.PROJECT_META


# ---------------------------------------------------
# ✅ Singleton Instance (전역에서 import 가능)
# ---------------------------------------------------
rules = RuleLoader()


# ---------------------------------------------------
# 🔹 사용 예시
# ---------------------------------------------------
"""
from app.core.rules_loader import rules

# Offer 가격 검증
if not rules.validate_offer_price(offer_price, buyer_price):
    raise HTTPException(status_code=400, detail="Offer exceeds +10% threshold")

# Deal 마감시간 계산 (DeadTime 반영)
deadline = rules.apply_deadtime_pause(start_time=datetime.datetime.now(), duration_hours=24)

# Deposit 비율 가져오기
deposit_rate = rules.get_deposit_rate(trust_tier=2)

# DeadTime 체크
if rules.is_deadtime():
    print("현재는 Dead Time 입니다.")
"""