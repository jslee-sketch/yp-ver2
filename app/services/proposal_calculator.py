"""B. 금액 자동 계산 유틸 — 정액/정률 → 실제 금액"""


def calculate_proposal_amount(
    amount_type: str,     # "fixed" or "rate"
    amount_value: float,  # 정액이면 원, 정률이면 %
    total_amount: int,    # 원래 결제 금액
) -> int:
    """정액/정률 → 실제 금액 계산"""
    if amount_value is None:
        return 0
    if amount_type == "rate":
        pct = min(amount_value, 100)  # 100% 초과 클램프
        calculated = int(total_amount * pct / 100)
    else:
        calculated = int(amount_value)
    # 금액은 0 이상, 결제금액 이하
    return max(0, min(calculated, total_amount))
