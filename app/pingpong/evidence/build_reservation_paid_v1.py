# app/pingpong/evidence/build_reservation_paid_v1.py
from __future__ import annotations

from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.pingpong.evidence.spec import (
    utcnow_iso,
    safe_int,
    safe_float,
    base_context,
    base_trace,
)


def build_reservation_paid_v1(
    db: Session,
    *,
    reservation: Any,
    offer: Any,
    actor: str = "system_pay",
    paid_amount: int,
    amount_total_ssot: int,
    paid_amount_diff: int = 0,
    paid_amount_allowed_diff: int = 0,
    snapshot_mismatch: Optional[bool] = None,
    snapshot_backfilled: Optional[bool] = None,
    db_amount_goods: Optional[int] = None,
    db_amount_shipping: Optional[int] = None,
    db_amount_total: Optional[int] = None,
    calc_amount_goods: Optional[int] = None,
    calc_amount_shipping: Optional[int] = None,
    calc_amount_total: Optional[int] = None,
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Evidence Pack: reservation_paid_v1
    - 결제 완료 시점의 SSOT 스냅샷(Reservation.amount_*)과 계산값 비교
    - backfill/mismatch 여부, paid_amount diff까지 포함
    """
    before = before or {}

    resv_id = safe_int(getattr(reservation, "id", None))
    buyer_id = safe_int(getattr(reservation, "buyer_id", None))
    offer_id = safe_int(getattr(reservation, "offer_id", None))
    qty = safe_int(getattr(reservation, "qty", 0))

    status_after = getattr(reservation, "status", None)
    status_before = before.get("status_before", None)

    deal_id = safe_int(getattr(offer, "deal_id", None))
    seller_id = safe_int(getattr(offer, "seller_id", None))

    evidence = {
        "evidence_pack_version": "reservation_paid_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="reservation_paid", channel="server"),
        "entities": {
            "reservation": {
                "id": resv_id,
                "buyer_id": buyer_id,
                "offer_id": offer_id,
                "qty": qty,
                "status_before": status_before,
                "status_after": str(status_after) if status_after is not None else None,
                "paid_at": (
                    getattr(reservation, "paid_at", None).isoformat()
                    if getattr(reservation, "paid_at", None) is not None
                    else None
                ),
            },
            "offer": {
                "id": safe_int(getattr(offer, "id", None)),
                "deal_id": deal_id,
                "seller_id": seller_id,
                "price": safe_float(getattr(offer, "price", 0.0)),
                "shipping_mode": getattr(offer, "shipping_mode", None),
                "shipping_fee_per_reservation": safe_int(getattr(offer, "shipping_fee_per_reservation", 0)),
                "shipping_fee_per_qty": safe_int(getattr(offer, "shipping_fee_per_qty", 0)),
                "sold_qty_after": safe_int(getattr(offer, "sold_qty", 0)),
                "reserved_qty_after": safe_int(getattr(offer, "reserved_qty", 0)),
            },
            "deal": {"id": deal_id} if deal_id else None,
            "seller": {"id": seller_id} if seller_id else None,
        },
        "amounts": {
            "paid_amount": safe_int(paid_amount),
            "amount_total_ssot": safe_int(amount_total_ssot),
            "paid_amount_diff": safe_int(paid_amount_diff),
            "paid_amount_allowed_diff": safe_int(paid_amount_allowed_diff),
            "paid_amount_mismatch": bool(safe_int(paid_amount_diff) > safe_int(paid_amount_allowed_diff)),
            "snapshot": {
                "snapshot_mismatch": bool(snapshot_mismatch) if snapshot_mismatch is not None else None,
                "snapshot_backfilled": bool(snapshot_backfilled) if snapshot_backfilled is not None else None,
                "db_amount_goods": safe_int(db_amount_goods) if db_amount_goods is not None else None,
                "db_amount_shipping": safe_int(db_amount_shipping) if db_amount_shipping is not None else None,
                "db_amount_total": safe_int(db_amount_total) if db_amount_total is not None else None,
                "calc_amount_goods": safe_int(calc_amount_goods) if calc_amount_goods is not None else None,
                "calc_amount_shipping": safe_int(calc_amount_shipping) if calc_amount_shipping is not None else None,
                "calc_amount_total": safe_int(calc_amount_total) if calc_amount_total is not None else None,
            },
        },
        "checks": {},
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
    }
    return evidence