from __future__ import annotations

from app.policy.pricing_engine import (
    load_pricing_params,
    PriceInputs,
    compute_pricing,
    compute_offer_comparison,
)

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    params = load_pricing_params("app/policy/params/pricing.yaml")

    # 예시 입력: Anchor 없고 Base만 있는 상황 (실서비스 기본)
    inp = PriceInputs(
        p_anchor=None,
        p_base=92500,
        p_target=89000,
        q=7,
        q_target=10,
        category="default",
        ship_days=1,
        shipping_fee_krw=0,
        refund_grade=3,
        as_grade=3,
        seller_tier=3,
        seller_score=85,
        risk_level=1,
    )

    out = compute_pricing(params, inp)
    cmp = compute_offer_comparison(params, out, p_offer=89000)

    print("=== pricing smoke ===")
    print("base_used:", out.base_used)
    print("P_ref:", int(out.p_ref))
    print("P_group:", int(out.p_group))
    print("delta_cond:", round(out.delta_cond, 4))
    print("delta_price_equiv:", int(out.delta_price_equiv))
    print("--- offer ---")
    print("P_offer:", int(cmp.p_offer))
    print("P_expected(ref under offer cond):", int(cmp.p_expected))
    print("phrase_vs_expected:", cmp.phrase_vs_expected)
    print("phrase_vs_group:", cmp.phrase_vs_group)

if __name__ == "__main__":
    main()
