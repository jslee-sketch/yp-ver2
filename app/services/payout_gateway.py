# app/services/payout_gateway.py
"""
정산 지급 게이트웨이 인터페이스.
Phase 1: MockGateway (로그만)
Phase 3: 실제 PG 연동 예정
"""
from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
from enum import Enum


class PayoutStatus(str, Enum):
    PENDING = "PENDING"
    REQUESTED = "REQUESTED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


@dataclass
class PayoutItem:
    settlement_id: int
    seller_id: int
    amount: int
    bank_code: str
    account_number: str
    account_holder: str


@dataclass
class PayoutResult:
    settlement_id: int
    status: PayoutStatus
    pg_transaction_id: Optional[str] = None
    failure_reason: Optional[str] = None


class PayoutGateway(ABC):
    @abstractmethod
    async def request_payout(self, items: List[PayoutItem]) -> List[PayoutResult]:
        pass

    @abstractmethod
    async def check_status(self, pg_transaction_id: str) -> PayoutResult:
        pass

    @abstractmethod
    async def cancel_payout(self, pg_transaction_id: str) -> bool:
        pass


class MockPayoutGateway(PayoutGateway):
    async def request_payout(self, items: List[PayoutItem]) -> List[PayoutResult]:
        results = []
        for item in items:
            print(f"[MOCK_PAYOUT] seller#{item.seller_id} -> {item.amount:,}원 -> {item.bank_code} {item.account_number}")
            results.append(PayoutResult(
                settlement_id=item.settlement_id,
                status=PayoutStatus.SUCCESS,
                pg_transaction_id=f"MOCK_{item.settlement_id}_{int(time.time())}",
            ))
        return results

    async def check_status(self, pg_transaction_id: str) -> PayoutResult:
        return PayoutResult(settlement_id=0, status=PayoutStatus.SUCCESS, pg_transaction_id=pg_transaction_id)

    async def cancel_payout(self, pg_transaction_id: str) -> bool:
        return True


class TossPayoutGateway(PayoutGateway):
    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    async def request_payout(self, items: List[PayoutItem]) -> List[PayoutResult]:
        raise NotImplementedError("Phase 3에서 구현 예정")

    async def check_status(self, pg_transaction_id: str) -> PayoutResult:
        raise NotImplementedError("Phase 3에서 구현 예정")

    async def cancel_payout(self, pg_transaction_id: str) -> bool:
        raise NotImplementedError("Phase 3에서 구현 예정")


def get_payout_gateway() -> PayoutGateway:
    provider = os.environ.get("PAYOUT_GATEWAY", "mock")
    if provider == "toss":
        return TossPayoutGateway(secret_key=os.environ["TOSS_SECRET_KEY"])
    return MockPayoutGateway()
