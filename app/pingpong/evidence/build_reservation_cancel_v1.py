# app/pingpong/evidence/build_reservation_cancel_v1.py
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


def _dt_iso(dt: Any) -> Optional[str]:
    """
    Defensive datetime -> ISO8601 string.
    - dt may be None
    - dt may be naive/aware datetime
    - if dt has isoformat(), use it
    """
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return None


def build_reservation_cancel_v1(
    db: Session,
    *,
    reservation: Any,
    offer: Any,
    actor: str,  # "buyer_cancel" | "seller_cancel" | "admin_cancel" | "system_cancel" | "dispute_resolve"
    cancel_stage: str,  # "BEFORE_SHIPPING" | "SHIPPED_NOT_DELIVERED" | "WITHIN_COOLING" | "AFTER_COOLING" | "UNKNOWN"
    cancel_case: str,   # "PARTIAL" | "FULL" | "UNKNOWN"
    refunded_qty_delta: int,
    amount_total_refund_delta: int,
    amount_total: int,
    amount_shipping: int,
    expected_source: Optional[str] = None,
    preview_amount_total_refund: Optional[int] = None,
    fallback_amount_total_refund: Optional[int] = None,
    decision_supported: Optional[bool] = None,
    meta_supported: Optional[bool] = None,
    invariants_ok: Optional[bool] = None,
    before: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None,
    request_id: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """
    Evidence Pack: reservation_cancel_v1

    - 예약 취소(부분/전체) 발생 시점의 SSOT 근거 묶음
    - 환불/수량 변화, 정책 소스(preview/meta/fallback), stage 정보까지 포함

    NOTE:
    - db는 향후 policy_snapshot(param/rule/version) 첨부를 위해 유지
    """
    before = before or {}

    resv_id = safe_int(getattr(reservation, "id", None))
    buyer_id = safe_int(getattr(reservation, "buyer_id", None))
    offer_id = safe_int(getattr(reservation, "offer_id", None))
    qty = safe_int(getattr(reservation, "qty", 0))

    status_after = getattr(reservation, "status", None)
    status_before = before.get("status_before", None)

    refunded_qty_before = safe_int(
        before.get("refunded_qty", getattr(reservation, "refunded_qty", None))
    )
    refunded_amount_before = safe_int(
        before.get("refunded_amount_total", getattr(reservation, "refunded_amount_total", None))
    )

    refunded_qty_after = safe_int(getattr(reservation, "refunded_qty", None))
    refunded_amount_after = safe_int(getattr(reservation, "refunded_amount_total", None))

    deal_id = safe_int(getattr(offer, "deal_id", None))
    seller_id = safe_int(getattr(offer, "seller_id", None))

    evidence: Dict[str, Any] = {
        "evidence_pack_version": "reservation_cancel_v1",
        "event_time": utcnow_iso(),
        "context": base_context(actor=actor, reason="reservation_cancel", channel="server"),
        "policy_context": {
            "stage": cancel_stage,
            "case": cancel_case,
            "expected_source": expected_source,
            "meta_supported": bool(meta_supported) if meta_supported is not None else None,
            "decision_supported": bool(decision_supported) if decision_supported is not None else None,
        },
        # 다음 단계(Proposal/승인루프)에서 필요해지는 SSOT 스냅샷 자리
        # - 지금은 placeholder로 두고, 나중에 project_rules / params / rules hash 등을 넣으면 됨
        "policy_snapshot": {
            "policy_version": None,
            "params_hash": None,
            "rules_hash": None,
        },
        "entities": {
            "reservation": {
                "id": resv_id,
                "buyer_id": buyer_id,
                "offer_id": offer_id,
                "qty": qty,
                "status_before": status_before,
                "status_after": str(status_after) if status_after is not None else None,
                "paid_at": _dt_iso(getattr(reservation, "paid_at", None)),
                "cancelled_at": _dt_iso(getattr(reservation, "cancelled_at", None)),
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
            "amount_total": safe_int(amount_total),
            "amount_shipping": safe_int(amount_shipping),
            "refund": {
                "refunded_qty_delta": safe_int(refunded_qty_delta),
                "amount_total_refund_delta": safe_int(amount_total_refund_delta),
                "refunded_qty_before": safe_int(refunded_qty_before),
                "refunded_qty_after": safe_int(refunded_qty_after),
                "refunded_amount_total_before": safe_int(refunded_amount_before),
                "refunded_amount_total_after": safe_int(refunded_amount_after),
            },
            "source": {
                "preview_amount_total_refund": safe_int(preview_amount_total_refund)
                if preview_amount_total_refund is not None
                else None,
                "fallback_amount_total_refund": safe_int(fallback_amount_total_refund)
                if fallback_amount_total_refund is not None
                else None,
            },
        },
        "checks": {
            "invariants_ok": bool(invariants_ok) if invariants_ok is not None else None,
        },
        "trace": base_trace(run_id=run_id, request_id=request_id, notes=notes),
    }

    return evidence