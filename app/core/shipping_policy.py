# app/core/shipping_policy.py
from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any


class ShippingMode(str, Enum):
    """
    v3.6 배송비 모드

    - INCLUDED: 상품가에 배송비 포함(추가 배송비 0)
    - PER_RESERVATION: 예약 1건(주문)당 고정 배송비
    - PER_QTY: 수량 1개당 배송비
    """
    INCLUDED = "INCLUDED"
    PER_RESERVATION = "PER_RESERVATION"
    PER_QTY = "PER_QTY"


def calc_shipping_fee(
    *,
    mode: Optional[str],
    fee_per_reservation: Optional[int],
    fee_per_qty: Optional[int],
    qty: int,
) -> int:
    """
    오퍼(Offer) 배송비 정책 + 예약 수량(qty) 기반으로 "주문 전체 배송비" 계산.
    """
    qty = int(qty or 0)
    if qty <= 0:
        return 0

    mode_raw = (mode or ShippingMode.INCLUDED.value)
    if not isinstance(mode_raw, str):
        mode_raw = ShippingMode.INCLUDED.value
    mode_raw = mode_raw.strip().upper()

    try:
        mode_enum = ShippingMode(mode_raw)
    except ValueError:
        mode_enum = ShippingMode.INCLUDED

    fee_per_reservation = int(fee_per_reservation or 0)
    fee_per_qty = int(fee_per_qty or 0)

    if mode_enum == ShippingMode.INCLUDED:
        return 0
    if mode_enum == ShippingMode.PER_RESERVATION:
        return max(0, fee_per_reservation)
    if mode_enum == ShippingMode.PER_QTY:
        return max(0, fee_per_qty * qty)

    return 0


def calc_shipping_breakdown(
    *,
    shipping_mode: Optional[str],
    fee_per_reservation: int,
    fee_per_qty: int,
    qty_total: int,
) -> Dict[str, Any]:
    """
    Offer 정책(모드/요금) -> 주문 전체 배송비 계산 후,
    부분환불에 쓰기 위한 breakdown 생성.
    """
    qty_total = max(0, int(qty_total or 0))

    total = int(
        calc_shipping_fee(
            mode=shipping_mode,
            fee_per_reservation=int(fee_per_reservation or 0),
            fee_per_qty=int(fee_per_qty or 0),
            qty=qty_total,
        ) or 0
    )

    return calc_shipping_breakdown_from_total(
        total_shipping=total,
        qty_total=qty_total,
    )


def calc_shipping_breakdown_from_total(
    *,
    total_shipping: int,
    qty_total: int,
) -> Dict[str, Any]:
    """
    ✅ SSOT(Reservation.amount_shipping)에 저장된 "총 배송비(total_shipping)"를
    부분환불에 일관되게 쪼개기 위한 breakdown 생성.

    반환:
      - total
      - qty_total
      - per_qty_alloc
      - remainder (앞쪽 item부터 1원씩 추가 배정)
    """
    qty_total = max(0, int(qty_total or 0))
    total_shipping = max(0, int(total_shipping or 0))

    if qty_total <= 0:
        return {"total": total_shipping, "qty_total": 0, "per_qty_alloc": 0, "remainder": 0}

    per_qty_alloc = total_shipping // qty_total
    remainder = total_shipping - (per_qty_alloc * qty_total)

    return {
        "total": total_shipping,
        "qty_total": qty_total,
        "per_qty_alloc": per_qty_alloc,
        "remainder": remainder,
    }


def calc_shipping_refund_for_partial_qty(
    *,
    shipping_breakdown: Dict[str, Any],
    refund_qty: int,
    already_refunded_qty: int,
) -> int:
    """
    부분환불 시, "이번에 환불하는 수량(refund_qty)"에 해당하는 배송비 배정액(최대치)을 계산.

    - remainder는 index 0..remainder-1 항목에 1원씩 추가 배정
    - already_refunded_qty 기준으로 이번 환불을 [start, start+refund_qty)로 간주
    - 반환값은 0..total 범위로 clamp
    """
    refund_qty = max(0, int(refund_qty or 0))
    already_refunded_qty = max(0, int(already_refunded_qty or 0))

    total = int(shipping_breakdown.get("total") or 0)
    qty_total = int(shipping_breakdown.get("qty_total") or 0)
    per_qty_alloc = int(shipping_breakdown.get("per_qty_alloc") or 0)
    remainder = int(shipping_breakdown.get("remainder") or 0)

    if qty_total <= 0 or refund_qty <= 0:
        return 0

    start = already_refunded_qty
    end_exclusive = already_refunded_qty + refund_qty  # [start, end_exclusive)

    base = per_qty_alloc * refund_qty

    # extra: i in [start, end_exclusive) where i < remainder
    extra = 0
    if remainder > 0:
        extra = max(0, min(end_exclusive, remainder) - start)

    out = base + extra
    if out < 0:
        out = 0
    if out > total:
        out = total
    return out