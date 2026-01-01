# app/pg/client.py

from __future__ import annotations

import logging
from .types import (
    PgRefundRequest,
    PgRefundResult,
    PgPayRequest,
    PgPayResult,
)

logger = logging.getLogger(__name__)


def request_pg_refund(req: PgRefundRequest) -> PgRefundResult:
    """
    실제 PG 환불 API를 호출하는 자리.

    🔹 지금은 더미 구현:
      - 아무것도 안 하고 success=True 로 바로 성공 처리만 반환
    🔹 나중에:
      - PG사에서 준 문서 보고 HTTP 요청 보내고
      - 응답 JSON을 PgRefundResult 로 변환해서 반환

    refund_paid_reservation() 쪽에서는 이 함수만 호출하도록 해서
    나중에 PG 교체/연동할 때 이 파일만 고치면 되게 만든다.
    """
    logger.debug("[pg] dummy refund request: %s", req)

    # TODO: 여기에서 실제 PG REST API 호출 + 응답 파싱 로직 구현

    return PgRefundResult(
        success=True,
        pg_status="COMPLETED",
        pg_cancel_amount=req.amount,
        pg_raw={"dummy": True},
        pg_error_code=None,
        pg_error_message=None,
    )
    

def request_pg_pay(req: PgPayRequest) -> PgPayResult:
    """
    실제 PG 결제(승인) API를 호출하는 자리.

    지금은 더미 구현:
    - 항상 success=True, pg_status="COMPLETED" 인 것처럼 동작

    나중에 PG 연동할 때 이 함수 안에서
    실제 PG REST API / SDK 를 호출하도록만 바꾸면 됨.
    """
    logger.debug("[pg] dummy pay request: %s", req)

    return PgPayResult(
        success=True,
        pg_status="COMPLETED",
        pg_approved_amount=req.amount,
        pg_transaction_id=f"DUMMY_PAY_{req.merchant_uid}",
        pg_raw={
            "dummy": True,
            "amount": req.amount,
            "reservation_id": req.reservation_id,
            "buyer_id": req.buyer_id,
        },
        pg_error_code=None,
        pg_error_message=None,
    )