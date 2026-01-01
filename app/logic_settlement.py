# app/logic_settlement.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app import models


@dataclass
class SettlementResult:
    """
    예약 1건 기준 정산 결과 (임시/예시용)

    지금은 PG, 수수료, VAT 등은 아직 본격 계산 안 하고
    '기본 구조'만 잡아놓는 상태.
    """
    reservation_id: int
    deal_id: int
    offer_id: int
    seller_id: int

    # 금액 단위: 원
    buyer_paid_amount: int          # Buyer가 PG에 결제한 총액 (임시)
    pg_fee_amount: int              # PG 수수료 (임시: 0)
    platform_commission_amount: int # 역핑 수수료 (임시: 0)
    seller_payout_amount: int       # Seller에게 정산될 금액 (임시: buyer_paid_amount)

    calculated_at: datetime


def calc_settlement_for_reservation(
    db: Session,
    reservation: models.Reservation,
) -> SettlementResult:
    """
    ✅ PG/정산 설계가 아직 확정 전이라,
    지금은 '구조만 맞춘 더미 구현'으로 둔다.

    나중에:
    - PG 실제 결제금액
    - PG 수수료율
    - 역핑 3.5% 수수료 + VAT
    등을 여기에 반영하면 된다.
    """
    # 1) 관련 엔티티 로드 (필요 시)
    deal = db.get(models.Deal, reservation.deal_id)
    offer = db.get(models.Offer, reservation.offer_id)

    # 2) 임시로 "buyer가 낸 돈 = offer.price × qty" 라고 간주
    unit_price = int(getattr(offer, "price", 0) or 0)
    qty = int(getattr(reservation, "qty", 1) or 1)
    buyer_paid_amount = unit_price * qty

    # 3) 아직 PG/수수료 설계가 확정이 아니므로 0으로 두고,
    #    seller_payout_amount 를 buyer_paid_amount 로 둔다.
    pg_fee_amount = 0
    platform_commission_amount = 0
    seller_payout_amount = buyer_paid_amount

    return SettlementResult(
        reservation_id=reservation.id,
        deal_id=reservation.deal_id,
        offer_id=reservation.offer_id,
        seller_id=offer.seller_id if offer else 0,
        buyer_paid_amount=buyer_paid_amount,
        pg_fee_amount=pg_fee_amount,
        platform_commission_amount=platform_commission_amount,
        seller_payout_amount=seller_payout_amount,
        calculated_at=datetime.utcnow(),
    )