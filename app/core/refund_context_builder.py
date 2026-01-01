# app/core/refund_context_builder.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app import models
from app.core.shipping_policy import (
    calc_shipping_fee,
    calc_shipping_breakdown,
    calc_shipping_refund_for_partial_qty,
)


@dataclass
class RefundDBSnapshot:
    reservation: models.Reservation
    offer: models.Offer
    deal: models.Deal
    settlement: Optional[models.ReservationSettlement]
    payment: Optional[models.ReservationPayment]
    computed: Dict[str, Any]  # shipping_total, shipping_breakdown, stage 등


def _utcnow() -> datetime:
    # 프로젝트 전반에서 utcnow()를 쓰고 있으면 맞춰주기
    return datetime.utcnow()


def resolve_reservation(
    db: Session,
    *,
    reservation_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    buyer_id: Optional[int] = None,
) -> models.Reservation:
    """
    우선순위:
    1) reservation_id 있으면 그걸로 확정
    2) deal_id + buyer_id 있으면 그 buyer의 해당 deal 예약 중 최신(생성일 desc)
    3) buyer_id만 있으면 최신 예약(운영 정책상 위험할 수 있으니 추후 제한 권장)
    """
    q = db.query(models.Reservation)

    if reservation_id:
        r = q.filter(models.Reservation.id == reservation_id).first()
        if not r:
            raise ValueError("reservation not found")
        return r

    if deal_id and buyer_id:
        r = (
            q.filter(models.Reservation.deal_id == deal_id)
            .filter(models.Reservation.buyer_id == buyer_id)
            .order_by(models.Reservation.created_at.desc())
            .first()
        )
        if not r:
            raise ValueError("reservation not found by deal_id+buyer_id")
        return r

    if buyer_id:
        r = (
            q.filter(models.Reservation.buyer_id == buyer_id)
            .order_by(models.Reservation.created_at.desc())
            .first()
        )
        if not r:
            raise ValueError("reservation not found by buyer_id")
        return r

    raise ValueError("one of reservation_id / (deal_id+buyer_id) / buyer_id is required")


def _infer_stage_from_reservation(r: models.Reservation) -> str:
    """
    환불 정책 판단을 위한 stage:
      - BEFORE_SHIPPING
      - AFTER_SHIPPING
      - AFTER_ARRIVAL
      - UNKNOWN
    가능한 경우 shipped_at/arrival_confirmed_at 같은 컬럼이 있으면 우선 사용.
    없으면 status 기반으로 fallback.
    """
    shipped_at = getattr(r, "shipped_at", None) or getattr(r, "marked_shipped_at", None)
    arrival_at = getattr(r, "arrival_confirmed_at", None) or getattr(r, "arrived_at", None)

    if arrival_at:
        return "AFTER_ARRIVAL"
    if shipped_at:
        return "AFTER_SHIPPING"

    st = (getattr(r, "status", None) or "").upper()

    # 프로젝트에서 쓰는 상태값이 더 있으면 여기에 추가
    if st in ("PAID", "RESERVED", "PAYMENT_CONFIRMED"):
        return "BEFORE_SHIPPING"
    if st in ("SHIPPED", "IN_DELIVERY", "DELIVERING"):
        return "AFTER_SHIPPING"
    if st in ("ARRIVAL_CONFIRMED", "COMPLETED", "DONE"):
        return "AFTER_ARRIVAL"

    return "UNKNOWN"


def _get_offer_shipping_fields(offer: models.Offer) -> Dict[str, Any]:
    """
    Offer에서 배송비 설정 필드를 안전하게 가져온다.
    (필드명 흔들림/레거시 대응 포함)
    """
    shipping_mode = getattr(offer, "shipping_mode", None)

    # ✅ 현재 모델(사진) 기준
    fee_per_reservation = getattr(offer, "shipping_fee_per_reservation", None)
    fee_per_qty = getattr(offer, "shipping_fee_per_qty", None)

    # ✅ 레거시/다른 이름 호환(혹시 있으면)
    if fee_per_reservation is None:
        fee_per_reservation = getattr(offer, "shipping_fee_base", None)
    if fee_per_qty is None:
        fee_per_qty = getattr(offer, "shipping_fee_per_item", None)

    return {
        "shipping_mode": shipping_mode,
        "fee_per_reservation": int(fee_per_reservation or 0),
        "fee_per_qty": int(fee_per_qty or 0),
    }


def build_refund_snapshot(
    db: Session,
    *,
    reservation_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    buyer_id: Optional[int] = None,
    now: Optional[datetime] = None,
) -> RefundDBSnapshot:
    """
    Refund 계산에 필요한 DB 스냅샷을 한 번에 구성.
    - shipping_total(주문 전체 배송비)
    - shipping_breakdown(부분환불 배정을 위한 per_qty_alloc/remainder 포함)
    - already_refunded_qty(이미 환불된 수량; 모델에 없으면 0)
    - stage(배송 전/후/도착후)
    """
    now = now or _utcnow()

    r = resolve_reservation(db, reservation_id=reservation_id, deal_id=deal_id, buyer_id=buyer_id)

    offer = db.query(models.Offer).filter(models.Offer.id == r.offer_id).first()
    if not offer:
        raise ValueError("offer not found")

    deal = db.query(models.Deal).filter(models.Deal.id == r.deal_id).first()
    if not deal:
        raise ValueError("deal not found")

    settlement = (
        db.query(models.ReservationSettlement)
        .filter(models.ReservationSettlement.reservation_id == r.id)
        .first()
    )

    payment = (
        db.query(models.ReservationPayment)
        .filter(models.ReservationPayment.reservation_id == r.id)
        .order_by(models.ReservationPayment.id.desc())
        .first()
    )

    qty_total = int(getattr(r, "qty", 0) or 0)

    # 이미 환불된 수량(모델 필드명 흔들림 대비)
    already_refunded_qty = int(
        getattr(r, "refunded_qty", None)
        or getattr(r, "refunded_qty_total", None)
        or 0
    )

    ship = _get_offer_shipping_fields(offer)
    shipping_total = int(
        calc_shipping_fee(
            mode=ship["shipping_mode"],
            fee_per_reservation=ship["fee_per_reservation"],
            fee_per_qty=ship["fee_per_qty"],
            qty=qty_total,
        )
    )

    shipping_breakdown = calc_shipping_breakdown(
        shipping_mode=ship["shipping_mode"],
        shipping_fee_per_reservation=ship["fee_per_reservation"],
        shipping_fee_per_qty=ship["fee_per_qty"],
        qty_total=qty_total,
    )

    stage = _infer_stage_from_reservation(r)

    computed: Dict[str, Any] = {
        "now": now.isoformat(),
        "qty_total": qty_total,
        "already_refunded_qty": already_refunded_qty,

        # ✅ 배송비(주문 전체) + 부분환불 배정용 breakdown
        "shipping_mode": ship["shipping_mode"],
        "shipping_fee_per_reservation": ship["fee_per_reservation"],
        "shipping_fee_per_qty": ship["fee_per_qty"],
        "shipping_total": shipping_total,
        "shipping_breakdown": shipping_breakdown,

        # ✅ stage
        "stage": stage,

        # ✅ 부분환불 시 “이번 환불 수량(refund_qty)”을 넣으면 계산할 수 있는 규칙 안내용
        #    실제 환불 API에서 refund_qty를 받아 아래 함수를 호출해 금액 계산하면 됨.
        "how_to_calc_partial_shipping_refund": {
            "fn": "calc_shipping_refund_for_partial_qty(shipping_breakdown, refund_qty, already_refunded_qty)"
        },
    }

    return RefundDBSnapshot(
        reservation=r,
        offer=offer,
        deal=deal,
        settlement=settlement,
        payment=payment,
        computed=computed,
    )


def compute_partial_refund_shipping_fee(
    *,
    shipping_breakdown: Dict[str, Any],
    refund_qty: int,
    already_refunded_qty: int,
) -> int:
    """
    ✅ 실제 환불 로직(서비스/라우터)에서 호출하기 편하게 wrapper 제공.
    """
    return int(
        calc_shipping_refund_for_partial_qty(
            shipping_breakdown=shipping_breakdown,
            refund_qty=int(refund_qty or 0),
            already_refunded_qty=int(already_refunded_qty or 0),
        )
    )