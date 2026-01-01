# scripts/test_refund_policy_settlement_cases.py

import os
import sys

# ---------------------------------------
# 0) 프로젝트 루트를 sys.path에 추가
#    (scripts/ 상위 디렉토리: C:\Users\user\Desktop\yp-ver2)
# ---------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# 이제야 'app' 패키지를 import 할 수 있음
from app.core.refund_policy import (
    RefundContext,
    RefundDecision,
    FaultParty,
    RefundTrigger,
    SettlementState,
    CoolingState,
    REFUND_POLICY_ENGINE,
)


def make_ctx(
    *,
    settlement_state: SettlementState,
    fault_party: FaultParty,
    trigger: RefundTrigger,
) -> RefundContext:
    """
    정산 상태 + 귀책 조합에 따른 RefundContext 샘플 생성.
    금액/수량/배송비는 지금 서비스 상황에 맞게 대략 고정 값 사용.
    """
    return RefundContext(
        reservation_id=999,   # 그냥 샘플 번호
        deal_id=1,
        offer_id=1,
        buyer_id=1,
        seller_id=1,

        amount_total=105_000,     # 100,000(상품) + 5,000(배송) 가정
        amount_goods=100_000,
        amount_shipping=5_000,

        quantity_total=1,
        quantity_refund=1,        # v1: 항상 전체 환불

        fault_party=fault_party,
        trigger=trigger,
        settlement_state=settlement_state,
        cooling_state=CoolingState.WITHIN_COOLING,  # 쿨링 안이라고 가정

        pg_fee_rate=0.0,
        platform_fee_rate=0.0,
    )


def run_case(title: str, settlement_state: SettlementState, fault_party: FaultParty, trigger: RefundTrigger):
    ctx = make_ctx(
        settlement_state=settlement_state,
        fault_party=fault_party,
        trigger=trigger,
    )

    decision: RefundDecision = REFUND_POLICY_ENGINE.decide_for_paid_reservation(ctx)

    print("====================================")
    print(f"▶ {title}")
    print(f"- settlement_state : {ctx.settlement_state}")
    print(f"- fault_party      : {ctx.fault_party}")
    print(f"- trigger          : {ctx.trigger}")
    print("---- decision ----")
    print(f"use_pg_refund                     : {decision.use_pg_refund}")
    print(f"pg_fee_burden                    : {decision.pg_fee_burden}")
    print(f"platform_fee_burden              : {decision.platform_fee_burden}")
    print(f"revoke_buyer_points              : {decision.revoke_buyer_points}")
    print(f"revoke_seller_points             : {decision.revoke_seller_points}")
    print(f"need_settlement_recovery         : {decision.need_settlement_recovery}")
    print(f"settlement_recovery_from_seller  : {decision.settlement_recovery_from_seller}")
    print(f"note                             : {decision.note}")
    print()

    # (선택) 금융 플랜이 구현되어 있으면 같이 찍어보기
    try:
        plan = REFUND_POLICY_ENGINE.build_financial_plan(ctx, decision)
    except AttributeError:
        plan = None

    if plan is not None:
        print("---- financial_plan ----")
        for k, v in plan.__dict__.items():
            print(f"{k:35}: {v}")
        print()


def main():
    # ===== 정산 전 케이스들 =====
    run_case(
        "정산 전 + 바이어 귀책 (쿨링 안, BUYER_CANCEL)",
        SettlementState.NOT_SETTLED,
        FaultParty.BUYER,
        RefundTrigger.BUYER_CANCEL,
    )

    run_case(
        "정산 전 + 셀러 귀책 (SELLER_CANCEL)",
        SettlementState.NOT_SETTLED,
        FaultParty.SELLER,
        RefundTrigger.SELLER_CANCEL,
    )

    run_case(
        "정산 전 + 시스템/분쟁 (SYSTEM_ERROR)",
        SettlementState.NOT_SETTLED,
        FaultParty.SYSTEM,
        RefundTrigger.SYSTEM_ERROR,
    )

    # ===== 정산 후 케이스들 =====
    run_case(
        "정산 후 + 바이어 귀책 (BUYER_CANCEL)",
        SettlementState.SETTLED_TO_SELLER,
        FaultParty.BUYER,
        RefundTrigger.BUYER_CANCEL,
    )

    run_case(
        "정산 후 + 셀러 귀책 (SELLER_CANCEL)",
        SettlementState.SETTLED_TO_SELLER,
        FaultParty.SELLER,
        RefundTrigger.SELLER_CANCEL,
    )

    run_case(
        "정산 후 + 시스템/분쟁 (DISPUTE_RESOLVE)",
        SettlementState.SETTLED_TO_SELLER,
        FaultParty.SYSTEM,
        RefundTrigger.DISPUTE_RESOLVE,
    )


if __name__ == "__main__":
    main()