# app/core/refund_policy.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any
from datetime import datetime, timedelta

from app.core.time_policy import TIME_POLICY, _utcnow, _as_utc


class FaultParty(str, Enum):
    BUYER = "BUYER"
    SELLER = "SELLER"
    SYSTEM = "SYSTEM"      # 플랫폼/PG/시스템 문제
    DISPUTE = "DISPUTE"    # 분쟁 (귀책 불명확)


class RefundTrigger(str, Enum):
    BUYER_CANCEL = "BUYER_CANCEL"          # 쿨링타임 내 바이어 단순변심 / 일반 취소
    SELLER_CANCEL = "SELLER_CANCEL"        # 셀러 측 문제로 취소/환불
    ADMIN_FORCE = "ADMIN_FORCE"            # 운영자 강제 취소/환불
    SYSTEM_ERROR = "SYSTEM_ERROR"          # 시스템 장애 등
    DISPUTE_RESOLVE = "DISPUTE_RESOLVE"    # 분쟁 조정 결과에 따른 환불


class SettlementState(str, Enum):
    NOT_SETTLED = "NOT_SETTLED"
    SETTLED_TO_SELLER = "SETTLED_TO_SELLER"
    UNKNOWN = "UNKNOWN"


class CoolingState(str, Enum):
    """
    환불/쿨링 상태.

    - BEFORE_SHIPPING        : 결제는 되었지만 아직 발송 전
    - SHIPPED_NOT_DELIVERED  : 발송은 했지만 도착/구매자 확인 전
    - WITHIN_COOLING         : 도착(또는 도착확인) 후 쿨링 기간 이내
    - AFTER_COOLING          : 도착(또는 도착확인) 후 쿨링 기간 경과
    - UNKNOWN                : 판단 불가
    """
    BEFORE_SHIPPING = "BEFORE_SHIPPING"
    SHIPPED_NOT_DELIVERED = "SHIPPED_NOT_DELIVERED"
    WITHIN_COOLING = "WITHIN_COOLING"
    AFTER_COOLING = "AFTER_COOLING"
    UNKNOWN = "UNKNOWN"


DEFAULT_COOLING_DAYS: int = int(
    getattr(
        TIME_POLICY,
        "cooling_days",
        getattr(TIME_POLICY, "cooling_days_default", 7),
    ) or 7
)


def compute_cooling_state(
    *,
    shipped_at: Optional[datetime],
    delivered_at: Optional[datetime],
    arrival_confirmed_at: Optional[datetime],
    now: Optional[datetime] = None,
    cooling_days: Optional[int] = None,
) -> CoolingState:
    if now is None:
        now = _utcnow()

    shipped = _as_utc(shipped_at) if shipped_at else None
    delivered = _as_utc(delivered_at) if delivered_at else None
    arrival = _as_utc(arrival_confirmed_at) if arrival_confirmed_at else None

    if shipped is None:
        return CoolingState.BEFORE_SHIPPING

    # ✅ "수령확정일(arrival_confirmed_at) 기준 + N일"이 원칙
    #    arrival_confirmed_at이 있으면 그걸 base로 쓰고,
    #    없으면 delivered_at을 fallback으로 사용.
    delivered_base: Optional[datetime] = arrival or delivered

    if delivered_base is None:
        return CoolingState.SHIPPED_NOT_DELIVERED

    days = int(cooling_days if cooling_days is not None else DEFAULT_COOLING_DAYS)
    cooling_ends_at = delivered_base + timedelta(days=days)

    if now <= cooling_ends_at:
        return CoolingState.WITHIN_COOLING
    return CoolingState.AFTER_COOLING


def decide_shipping_refund_cap(
    *,
    fault_party: FaultParty,
    trigger: RefundTrigger,
    cooling_state: CoolingState,
    auto_max_shipping_refund: int,
) -> int:
    """
    ✅ v3.6로 '배송비를 환불 대상에 포함할지'를 고정하는 룰.

    입력:
      - auto_max_shipping_refund: (부분환불 자동배정 결과) 이번 환불에서 환불 가능한 배송비 상한

    반환:
      - 이번 환불에서 "정책상 허용되는 배송비 환불 상한(cap)"
        => 최종 배송비 환불액은 min(auto_max, cap) 으로 결정

    기본 원칙(보수적으로 시작):
      1) BEFORE_SHIPPING: 배송이 시작되지 않았으면 배송비 환불 허용(대부분 auto_max)
      2) SHIPPED_NOT_DELIVERED: 바이어 단순변심은 배송비 0, 셀러귀책/시스템은 허용
      3) WITHIN_COOLING: 바이어 단순변심은 배송비 0, 셀러귀책/시스템은 허용
      4) AFTER_COOLING: 분쟁 영역 -> 기본 0 (DISPUTE_RESOLVE 같은 확정 트리거에서만 별도 처리)
    """
    auto_max = max(0, int(auto_max_shipping_refund or 0))

    if auto_max <= 0:
        return 0

    # 4) AFTER_COOLING: 기본 0 (분쟁조정 결과면 별도 정책/케이스에서 override로 풀어줄 수 있음)
    if cooling_state == CoolingState.AFTER_COOLING:
        if trigger == RefundTrigger.DISPUTE_RESOLVE:
            # 분쟁조정에서 "배송비도 환불"로 합의/판정났을 때만 허용(여기서는 cap=auto_max)
            return auto_max
        return 0

    # 1) BEFORE_SHIPPING: 배송비 환불 허용(배송비가 실제로 소진되지 않았다는 가정)
    if cooling_state == CoolingState.BEFORE_SHIPPING:
        return auto_max

    # 2) SHIPPED_NOT_DELIVERED / 3) WITHIN_COOLING
    if fault_party == FaultParty.BUYER and trigger == RefundTrigger.BUYER_CANCEL:
        return 0

    if fault_party in (FaultParty.SELLER, FaultParty.SYSTEM):
        return auto_max

    # DISPUTE/UNKNOWN은 보수적으로 0
    return 0


@dataclass
class RefundContext:
    reservation_id: int
    deal_id: Optional[int]
    offer_id: Optional[int]
    buyer_id: int
    seller_id: Optional[int]

    amount_total: int
    amount_goods: int
    amount_shipping: int

    quantity_total: int
    quantity_refund: int

    fault_party: FaultParty
    trigger: RefundTrigger
    settlement_state: SettlementState
    cooling_state: CoolingState

    pg_fee_rate: float = 0.0
    platform_fee_rate: float = 0.0


@dataclass
class RefundDecision:
    use_pg_refund: bool

    pg_fee_burden: Optional[FaultParty]
    platform_fee_burden: Optional[FaultParty]

    revoke_buyer_points: bool
    revoke_seller_points: bool

    need_settlement_recovery: bool
    settlement_recovery_from_seller: bool

    note: str = ""


@dataclass
class RefundFinancialPlan:
    pg_should_refund: bool
    pg_refund_amount: int
    pg_fee_amount: int
    pg_fee_charge_to: Optional[FaultParty]

    platform_fee_amount: int
    platform_fee_charge_to: Optional[FaultParty]

    settlement_recovery_amount: int
    settlement_recovery_from_seller: bool


class RefundPolicyEngine:
    def decide_for_paid_reservation(self, ctx: RefundContext) -> RefundDecision:
        decision = RefundDecision(
            use_pg_refund=True,
            pg_fee_burden=FaultParty.SELLER,
            platform_fee_burden=FaultParty.SELLER,
            revoke_buyer_points=True,
            revoke_seller_points=True,
            need_settlement_recovery=False,
            settlement_recovery_from_seller=False,
            note="default fallback",
        )

        decision.revoke_buyer_points = True
        decision.revoke_seller_points = True

        if ctx.settlement_state == SettlementState.NOT_SETTLED:
            decision.use_pg_refund = True
            decision.need_settlement_recovery = False
            decision.settlement_recovery_from_seller = False

            if ctx.fault_party == FaultParty.BUYER:
                decision.pg_fee_burden = FaultParty.BUYER
                decision.platform_fee_burden = FaultParty.BUYER
                decision.note = "정산 전 + 바이어 귀책: PG/플랫폼 수수료는 바이어 부담"
            elif ctx.fault_party == FaultParty.SELLER:
                decision.pg_fee_burden = FaultParty.SELLER
                decision.platform_fee_burden = FaultParty.SELLER
                decision.note = "정산 전 + 셀러 귀책: PG/플랫폼 수수료는 셀러 부담"
            else:
                decision.pg_fee_burden = FaultParty.SYSTEM
                decision.platform_fee_burden = FaultParty.SYSTEM
                decision.note = "정산 전 + 시스템/분쟁: 수수료는 플랫폼 정책에 따름"

        elif ctx.settlement_state == SettlementState.SETTLED_TO_SELLER:
            decision.use_pg_refund = False
            decision.need_settlement_recovery = True
            decision.settlement_recovery_from_seller = True

            if ctx.fault_party == FaultParty.SELLER:
                decision.pg_fee_burden = FaultParty.SELLER
                decision.platform_fee_burden = FaultParty.SELLER
                decision.note = "정산 후 + 셀러 귀책: 셀러 직접환불, 수수료도 셀러 부담"
            elif ctx.fault_party == FaultParty.BUYER:
                decision.pg_fee_burden = FaultParty.BUYER
                decision.platform_fee_burden = FaultParty.BUYER
                decision.note = "정산 후 + 바이어 귀책: 바이어-셀러 직접 정산"
            else:
                decision.pg_fee_burden = FaultParty.SYSTEM
                decision.platform_fee_burden = FaultParty.SYSTEM
                decision.note = "정산 후 + 시스템/분쟁: 내부 정책에 따름"

        else:
            decision.note = "UNKNOWN settlement_state: 보수적 기본 정책 적용"

        if ctx.cooling_state == CoolingState.AFTER_COOLING:
            decision.note += " / 쿨링타임 이후: 분쟁성 케이스로 태깅 필요"

        return decision

    def build_financial_plan(self, ctx: RefundContext, decision: RefundDecision) -> RefundFinancialPlan:
        if decision.use_pg_refund:
            pg_refund_amount = int(ctx.amount_total or 0)
        else:
            pg_refund_amount = 0

        pg_fee_amount = int((ctx.amount_total or 0) * float(ctx.pg_fee_rate or 0.0))
        platform_fee_amount = int((ctx.amount_total or 0) * float(ctx.platform_fee_rate or 0.0))

        if decision.need_settlement_recovery and decision.settlement_recovery_from_seller:
            settlement_recovery_amount = int(ctx.amount_total or 0)
        else:
            settlement_recovery_amount = 0

        return RefundFinancialPlan(
            pg_should_refund=decision.use_pg_refund,
            pg_refund_amount=pg_refund_amount,
            pg_fee_amount=pg_fee_amount,
            pg_fee_charge_to=decision.pg_fee_burden,
            platform_fee_amount=platform_fee_amount,
            platform_fee_charge_to=decision.platform_fee_burden,
            settlement_recovery_amount=settlement_recovery_amount,
            settlement_recovery_from_seller=decision.settlement_recovery_from_seller,
        )


# app/core/refund_policy.py

def is_shipping_refundable_by_policy(
    *,
    cooling_state: Any,
    fault_party: Any,
    trigger: Any,
) -> bool:
    """
    ✅ v3.6 배송비 환불 포함 여부 최종 결정(gate) - 옵션B (SSOT)

    [정의]
    - 이 함수는 "배송비를 환불에 포함할지"만 결정한다(allowed gate).
    - 배송비의 "금액"은 preview_refund_for_paid_reservation에서
      Reservation.amount_shipping(SSOT) 기반 자동배정(+override cap)으로 계산된다.

    [옵션B 규칙]
    1) BEFORE_SHIPPING: 모든 trigger에 대해 배송비 환불 허용
    2) SHIPPED_NOT_DELIVERED / WITHIN_COOLING:
        - BUYER_CANCEL만 불허
        - SELLER_CANCEL / SYSTEM_ERROR / ADMIN_FORCE / DISPUTE_RESOLVE 는 허용
    3) AFTER_COOLING:
        - DISPUTE_RESOLVE만 허용
        - 그 외는 불허
    4) UNKNOWN/기타: 보수적으로 불허
    """


    def _val(x: Any) -> str:
        if x is None:
            return ""
        if hasattr(x, "value"):
            try:
                return str(x.value)
            except Exception:
                pass
        return str(x)

    cs = _val(cooling_state).upper()
    tr = _val(trigger).upper()

    # 0) 분쟁조정은 stage와 무관하게 허용(옵션B + 운영 안전)
    if tr == "DISPUTE_RESOLVE":
        return True

    # 1) 발송 전: 전부 허용
    if cs == "BEFORE_SHIPPING":
        return True

    # 2) 발송 후(도착 전) / 쿨링 내:
    #    buyer_cancel만 불허, 나머지는 허용
    if cs in ("SHIPPED_NOT_DELIVERED", "WITHIN_COOLING"):
        if tr == "BUYER_CANCEL":
            return False
        return True

    # 3) 쿨링 이후: 기본 불허(분쟁조정만 허용은 위에서 처리)
    if cs == "AFTER_COOLING":
        return False

    # 4) UNKNOWN 등: 보수적으로 불허
    return False



def is_shipping_refund_allowed_by_policy(
    *,
    cooling_state: CoolingState,
    fault_party: FaultParty,
    trigger: RefundTrigger,
) -> bool:
    """
    v3.6 배송비 환불 Gate — 옵션B (SSOT)

    - 배송비를 "환불에 포함할 수 있는지 여부"만 결정한다.
    - 실제 배송비 금액은 preview 단계에서
      Reservation.amount_shipping(SSOT) 기반 자동배정/override로 계산된다.

    옵션B 규칙:
      1) BEFORE_SHIPPING:
         - 모든 trigger 허용
      2) SHIPPED_NOT_DELIVERED / WITHIN_COOLING:
         - BUYER_CANCEL만 불허
         - 그 외(SELLER_CANCEL / SYSTEM_ERROR / ADMIN_FORCE / DISPUTE_RESOLVE) 허용
      3) AFTER_COOLING:
         - DISPUTE_RESOLVE만 허용
         - 그 외 불허
      4) UNKNOWN:
         - 불허
    """

    # 1) BEFORE_SHIPPING: 전부 허용
    if cooling_state == CoolingState.BEFORE_SHIPPING:
        return True

    # 2) 발송 후 ~ 쿨링 내
    if cooling_state in (CoolingState.SHIPPED_NOT_DELIVERED, CoolingState.WITHIN_COOLING):
        if trigger == RefundTrigger.BUYER_CANCEL:
            return False
        return True

    # 3) 쿨링 이후
    if cooling_state == CoolingState.AFTER_COOLING:
        return trigger == RefundTrigger.DISPUTE_RESOLVE

    # 4) UNKNOWN / 기타
    return False




REFUND_POLICY_ENGINE = RefundPolicyEngine()