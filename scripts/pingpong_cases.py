# scripts/pingpong_cases.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional

@dataclass(frozen=True)
class Case:
    name: str
    body: Dict[str, Any]
    expect_status: int = 200
    note: Optional[str] = None

DEFAULTS = {
    "user_id": 1,
    "role": "buyer",
    "screen": "REFUND_FLOW",
    "context": {"deal_id": None, "reservation_id": None, "offer_id": None},
    "locale": "ko",
    "mode": "read_only",
    "max_chat_messages": 10,
}

def make_body(question: str, **overrides: Any) -> Dict[str, Any]:
    b = dict(DEFAULTS)
    b["question"] = question
    for k, v in overrides.items():
        b[k] = v
    return b

# -------------------------
# Positive cases (200)
# -------------------------
POSITIVE_CASES = [
    Case(
        name="refund_fee_buyer_before_shipping",
        body=make_body("정산 전/발송 전 바이어 귀책 환불이면 수수료는 누가 부담해?"),
        expect_status=200,
    ),
    Case(
        name="refund_points_partial",
        body=make_body("부분 환불하면 포인트는 어떻게 돼?"),
        expect_status=200,
    ),
    Case(
        name="refund_after_shipping_buyer_fault",
        body=make_body("발송 후 바이어 귀책이면 환불 가능해?"),
        expect_status=200,
    ),
    Case(
        name="refund_fee_seller_before_shipping",
        body=make_body("정산 전/발송 전 셀러 귀책 환불이면 수수료는 누가 부담해?"),
        expect_status=200,
    ),
    Case(
        name="refund_shipping_fee_partial",
        body=make_body("부분환불이면 배송비는 환불돼?"),
        expect_status=200,
    ),
]

# -------------------------
# Negative cases (400/422)
# -------------------------
NEGATIVE_CASES = [
    Case(
        name="fail_empty_question",
        body=make_body(""),
        expect_status=400,
    ),
    Case(
        name="fail_whitespace_question",
        body=make_body("   "),
        expect_status=400,
    ),
    Case(
        name="fail_missing_question_field",
        body={k: v for k, v in DEFAULTS.items() if k != "question"},
        expect_status=422,
    ),
    Case(
        name="fail_bad_context_type",
        body=make_body("컨텍스트 타입 에러", context="NOT_A_DICT"),
        expect_status=422,
    ),
]