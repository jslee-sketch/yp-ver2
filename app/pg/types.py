# app/pg/types.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Literal


# ===================== 🔽 여기서부터 결제용 타입 추가 🔽 =====================

@dataclass
class PgPayRequest:
    """
    PG 결제(승인) 요청 모델.

    - 지금은 최소 필드만 정의해두고,
      나중에 PG 스펙에 맞춰 필드/구성을 조정하면 됨.
    """
    # 아직은 None 허용. 나중에 “사전 생성된 tid” 같은 게 필요하면 여기에.
    pg_transaction_id: Optional[str]

    # 가맹점(우리) 기준 주문/예약 번호
    merchant_uid: str  # 예: f"reservation:{reservation_id}"

    # 이번에 결제할 금액(원 단위)
    amount: int

    # 우리 쪽 부가 정보
    reservation_id: int
    buyer_id: Optional[int] = None

    # 선택: 결제 수단 / 할부개월 등 (나중에 실제 PG 스펙 맞출 때 활용)
    payment_method: Optional[str] = None
    installment_months: Optional[int] = None


@dataclass
class PgPayResult:
    """
    PG 결제(승인) 결과를 우리 내부 표현으로 통일한 모델.
    """
    success: bool

    # PG 측 상태 (예: "REQUESTED", "PAID", "FAILED" 등)
    pg_status: str

    # 실제 승인된 금액
    pg_approved_amount: int

    # PG 쪽 거래번호 (tid, imp_uid 등) — 나중에 환불 시 다시 사용
    pg_transaction_id: Optional[str]

    # 디버깅/로깅용 원본 응답
    pg_raw: Optional[dict[str, Any]] = None

    # 실패 시 에러코드/메시지
    pg_error_code: Optional[str] = None
    pg_error_message: Optional[str] = None




@dataclass
class PgRefundRequest:
    """
    PG 환불 요청에 우리 쪽에서 넘겨줄 정보 모델.

    지금은 최소한만 정의해두고,
    나중에 실제 PG 스펙(거래번호 필드명 등)에 맞춰서 필드 이름/구성을 조정하면 됨.
    """
    # PG 거래 고유번호 (예: imp_uid, tid 등) - 아직 없으면 None 허용
    pg_transaction_id: Optional[str]

    # 가맹점(우리) 기준 주문/예약 번호
    merchant_uid: str  # 예: f"resv:{reservation_id}"

    # 이번에 환불 요청하는 금액(원 단위)
    amount: int

    # 환불 사유(로그/PG 화면에 표시용)
    reason: Optional[str]

    # 부가 정보 (우리 쪽)
    reservation_id: int
    buyer_id: Optional[int] = None


@dataclass
class PgRefundResult:
    """
    PG 환불 결과를 우리 내부 표현으로 통일해둔 모델.
    실제 PG마다 필드명이 달라서, 여기서 한 번 정규화해서 crud 쪽에서는
    PG사별 차이를 모르도록 만든다.
    """
    success: bool

    # PG 측 상태 (예: "REQUESTED", "COMPLETED", "FAILED" 등)
    pg_status: str

    # 실제 취소된 금액 (PG 응답 기준)
    pg_cancel_amount: int

    # 디버깅/로깅용 원본 응답
    pg_raw: Optional[dict[str, Any]] = None

    # 실패 시 PG 에러 코드/메시지
    pg_error_code: Optional[str] = None
    pg_error_message: Optional[str] = None