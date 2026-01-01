# scripts/verify_refund_execution_cooling_v36.py
# -*- coding: utf-8 -*-

"""
VERIFY SCRIPT FREEZE POLICY (v36)

- This script is frozen as a regression baseline.
- Verified OK on: 2025-12-22
- Coverage:
  - stages: BEFORE_SHIPPING / SHIPPED_NOT_DELIVERED / WITHIN_COOLING / AFTER_COOLING
  - actors: dispute_resolve
  - cases: PARTIAL + FULL (qty=3 template)
- Known failure modes (NOT logic bugs):
  - NotFoundError: Offer not found for deal
    -> Usually indicates invalid deal-offer relation / offer not exposed to deal context.
- If behavior changes are needed:
  -> copy to verify_refund_execution_cooling_v37.py and modify there.
"""
"""
Refund execution verifier (v3.6)
- Creates fresh PAID reservations cloned from a template reservation_id
- Sets stage timestamps (BEFORE_SHIPPING / SHIPPED_NOT_DELIVERED / WITHIN_COOLING / AFTER_COOLING)
- Executes refund (PARTIAL and optionally FULL on the SAME reservation)
- Asserts refunded_qty / refunded_amount_total deltas + offer.sold_qty delta (if available)
- Robust against preview return shape changes (2-tuple / 3-tuple) and pydantic model vs dict
- Strengthened patches:
  * preview amount extraction hardened (decision/meta/nested/meta-only) + amount_source tracking
  * fallback unit_price derived from reservation if offer.price missing
  * BEFORE_SHIPPING fallback shipping allocation uses reservation.amount_shipping remainder-aware split
  * log includes decision_supported/meta_supported separately

Usage examples:
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9 --actors=buyer_cancel,dispute_resolve
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9 --partial=2
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9 --full
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9 --full --actors=buyer_cancel
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9 --stages=BEFORE_SHIPPING,WITHIN_COOLING

NOTE (재고/수량 문제):
  템플릿 offer의 remain(가용재고)가 부족하면 create_reservation 단계에서 ConflictError가 납니다.
  offer_id=3 예시에서 올려야 하는 컬럼은 total_available_qty 입니다. (total 아님)
  예)
    $env:PYTHONPATH="."
    python -c "from app.database import SessionLocal; from app import models; db=SessionLocal(); o=db.get(models.Offer, 3); o.total_available_qty=max(o.total_available_qty, (o.sold_qty or 0)+(o.reserved_qty or 0)+1000); db.commit(); print('offer',o.id,'total_available_qty',o.total_available_qty,'sold',o.sold_qty,'reserved',o.reserved_qty); db.close()"
"""

import argparse
import json
from dataclasses import is_dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.database import SessionLocal
from app import models, crud
from sqlalchemy import text


DEFAULT_ACTORS = ["buyer_cancel", "seller_cancel", "admin_force", "system_error", "dispute_resolve"]
DEFAULT_STAGES = ["BEFORE_SHIPPING", "SHIPPED_NOT_DELIVERED", "WITHIN_COOLING", "AFTER_COOLING"]


def _utcnow() -> datetime:
    # timezone-aware UTC -> naive UTC (sqlite가 naive로 저장되는 케이스 방어)
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def _to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if is_dataclass(obj):
        try:
            return asdict(obj)
        except Exception:
            pass
    # pydantic v2
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    # pydantic v1
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    # 일반 객체
    if hasattr(obj, "__dict__"):
        try:
            return dict(obj.__dict__)
        except Exception:
            pass
    return {}


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _parse_csv_list(s: Optional[str]) -> Optional[List[str]]:
    if not s:
        return None
    items = [x.strip() for x in s.split(",") if x.strip()]
    return items or None


def _guess_cooling_days() -> int:
    try:
        from app.config import project_rules as R  # type: ignore

        if hasattr(R, "DEFAULT_COOLING_DAYS"):
            return _safe_int(getattr(R, "DEFAULT_COOLING_DAYS"), 14)

        for k in ["COOLING", "REFUND", "POLICY"]:
            if hasattr(R, k):
                v = getattr(R, k)
                if isinstance(v, dict):
                    for kk in ["DEFAULT_COOLING_DAYS", "cooling_days", "COOLING_DAYS"]:
                        if kk in v:
                            return _safe_int(v.get(kk), 14)
    except Exception:
        pass
    return 14




def _get_offer_policy_cooling_days(db, offer_id: int) -> int | None:
    """
    offer_policies.cancel_within_days 를 읽어 cooling_days로 사용한다.
    없으면 None.
    """
    try:
        row = db.execute(
            text("""
            SELECT cancel_within_days
            FROM offer_policies
            WHERE offer_id = :offer_id
            LIMIT 1
            """),
            {"offer_id": int(offer_id)},
        ).fetchone()
        if not row:
            return None
        v = row[0]
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def _set_stage_timestamps(db, reservation_id: int, stage: str, cooling_days: int) -> None:
    r = db.get(models.Reservation, reservation_id)
    if r is None:
        raise RuntimeError(f"reservation not found: {reservation_id}")

    now = _utcnow()

    # 안전 가드(스크립트 안에서도 한번 더)
    cd = int(cooling_days)
    if cd < 0:
        cd = 0
    if cd > 365:
        cd = 365

    if stage == "BEFORE_SHIPPING":
        r.shipped_at = None
        r.delivered_at = None
        r.arrival_confirmed_at = None

    elif stage == "SHIPPED_NOT_DELIVERED":
        r.shipped_at = now - timedelta(hours=1)
        r.delivered_at = None
        r.arrival_confirmed_at = None

    elif stage == "WITHIN_COOLING":
        # ✅ 핵심: 경계값(=cooling_days 딱 맞음)에서 AFTER로 떨어지는 걸 방지
        # now - arrived < cooling_days 가 확실하도록 "cd일 - 1시간"으로 맞춘다.
        # cd=1이면 arrived=now-23h (확실히 WITHIN)
        # cd=0이면 의미가 없으니 그냥 now-1h로 둔다(어쨌든 WITHIN으로 분류되도록)
        if cd <= 0:
            arrived = now - timedelta(hours=1)
        else:
            arrived = now - timedelta(days=cd) + timedelta(hours=1)  # (cd일 - 23시간)
        shipped = arrived - timedelta(hours=2)

        r.shipped_at = shipped
        r.delivered_at = arrived
        r.arrival_confirmed_at = arrived  # 핵심

    elif stage == "AFTER_COOLING":
        # ✅ 확실히 AFTER로 떨어지도록 버퍼( +3일 ) 유지
        arrived = now - timedelta(days=(cd + 3))
        shipped = arrived - timedelta(hours=2)

        r.shipped_at = shipped
        r.delivered_at = arrived
        r.arrival_confirmed_at = arrived  # 핵심

    else:
        raise ValueError(f"unknown stage: {stage}")

    db.add(r)
    db.commit()
    db.refresh(r)


def _compute_cooling_state_for_log(db, reservation_id: int, cooling_days: int) -> str:
    """
    로그용 cooling_state.
    preview(decision/meta)에 값이 없을 때 실제 reservation timestamp로 계산해서 찍는다.
    """
    try:
        r = db.get(models.Reservation, reservation_id)
        if r is None:
            return "UNKNOWN"

        from app.core.refund_policy import compute_cooling_state as _core_compute

        st = _core_compute(
            shipped_at=getattr(r, "shipped_at", None),
            delivered_at=getattr(r, "delivered_at", None),
            arrival_confirmed_at=getattr(r, "arrival_confirmed_at", None),
            now=_utcnow(),  # ✅ preview와 조건 맞춤
            cooling_days=int(cooling_days),
        )
        return str(getattr(st, "value", st))
    except Exception:
        return "UNKNOWN"


def _clone_paid_reservation(db, template_reservation_id: int) -> int:
    t = db.get(models.Reservation, template_reservation_id)
    if t is None:
        raise RuntimeError("template not found")

    # 1) create
    new_r = crud.create_reservation(
        db,
        deal_id=t.deal_id,
        offer_id=t.offer_id,
        buyer_id=t.buyer_id,
        qty=t.qty,
    )
    db.commit()
    db.refresh(new_r)

    # 2) shipping 강제 재계산 (타입/enum 차이까지 안전하게 처리)
    offer = db.get(models.Offer, new_r.offer_id)
    mode = getattr(offer.shipping_mode, "value", offer.shipping_mode) if offer else None

    if offer:
        if mode == "PER_RESERVATION":
            new_r.amount_shipping = int(offer.shipping_fee_per_reservation or 0)
        elif mode == "PER_QTY":
            new_r.amount_shipping = int((offer.shipping_fee_per_qty or 0) * new_r.qty)
        else:
            # 혹시 모드가 None/이상값이면 안전하게 0 또는 reservation 기존값 유지
            new_r.amount_shipping = int(new_r.amount_shipping or 0)

        new_r.amount_total = int((offer.price * new_r.qty) + new_r.amount_shipping)
        db.add(new_r)
        db.commit()
        db.refresh(new_r)

    # 3) pay (예외 처리 확실히)
    paid = None
    try:
        paid = crud.pay_reservation_v35(
            db,
            reservation_id=new_r.id,
            buyer_id=t.buyer_id,
        )
        db.commit()
        db.refresh(paid)
        return paid.id
    except Exception as e:
        db.rollback()
        # 여기서 paid를 참조하면 안 됨. 바로 예외 올려서 상위에서 FAIL 처리하게.
        raise RuntimeError(f"pay_reservation_v35 failed for reservation_id={new_r.id}: {e}") from e



def _call_preview(
    db, reservation_id: int, actor: str, quantity_refund: Optional[int]
) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """
    returns: (decision_dict, meta_dict, amount_source)
      - amount_source:
        - preview_decision
        - preview_decision_otherkey
        - preview_meta
        - preview_meta_nested
        - missing
    """
    out = crud.preview_refund_for_paid_reservation(
        db,
        reservation_id=reservation_id,
        actor=actor,
        quantity_refund=quantity_refund,
        return_meta=True,
        log_preview=False,
    )

    decision = None
    meta = None

    # return shape compatibility:
    # - (ctx, decision)
    # - (ctx, decision, meta)
    # - occasionally dict-only
    if isinstance(out, tuple):
        if len(out) == 2:
            _, decision = out
        elif len(out) >= 3:
            _, decision, meta = out[0], out[1], out[2]
        else:
            decision = None
            meta = None
    else:
        decision = out

    decision_d = _to_dict(decision)
    meta_d = _to_dict(meta)

    amount_source = "missing"

    def _is_nonzero(v: Any) -> bool:
        return v not in (None, 0, "0", "", False)

    def _get_nonzero(d: Dict[str, Any], keys: List[str]) -> Optional[Any]:
        for k in keys:
            if k in d and _is_nonzero(d.get(k)):
                return d.get(k)
        return None

    def _get_nested_amount(m: Dict[str, Any]) -> Optional[Any]:
        # meta 구조 흔들림 대비: 가능한 경로들을 넓게 잡음
        paths = [
            ("amount_total_refund",),
            ("refund", "amount_total_refund"),
            ("amounts", "amount_total_refund"),
            ("refund_amounts", "amount_total_refund"),
            ("result", "amount_total_refund"),
        ]
        for path in paths:
            cur: Any = m
            ok = True
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    ok = False
                    break
            if ok and _is_nonzero(cur):
                return cur
        return None

    # (1) decision에서 amount 후보 탐색
    if not _is_nonzero(decision_d.get("amount_total_refund")):
        v = _get_nonzero(decision_d, ["amount_total_refund"])
        if _is_nonzero(v):
            decision_d["amount_total_refund"] = v
            amount_source = "preview_decision"
        else:
            v2 = _get_nonzero(
                decision_d,
                ["refund_amount_total", "refund_total", "amount_refund_total", "amount_total"],
            )
            if _is_nonzero(v2):
                decision_d["amount_total_refund"] = v2
                amount_source = "preview_decision_otherkey"
    else:
        amount_source = "preview_decision"

    # (2) decision 금액이 없으면 meta에서 탐색
    if not _is_nonzero(decision_d.get("amount_total_refund")):
        mv = _get_nonzero(
            meta_d,
            ["amount_total_refund", "refund_amount_total", "refund_total", "amount_refund_total"],
        )
        if _is_nonzero(mv):
            decision_d["amount_total_refund"] = mv
            amount_source = "preview_meta"
        else:
            mv2 = _get_nested_amount(meta_d)
            if _is_nonzero(mv2):
                decision_d["amount_total_refund"] = mv2
                amount_source = "preview_meta_nested"

    # (3) cooling_state도 meta에만 있을 수 있음
    if "cooling_state" not in decision_d and "cooling_state" in meta_d:
        decision_d["cooling_state"] = meta_d.get("cooling_state")

    return decision_d, meta_d, amount_source


def _call_refund(db, reservation_id: int, actor: str, quantity_refund: Optional[int]) -> None:
    crud.refund_paid_reservation(
        db,
        reservation_id=reservation_id,
        actor=actor,
        quantity_refund=quantity_refund,
    )
    db.commit()


def _allocate_shipping_amount(amount_shipping: int, qty_total: int, qty_refund: int) -> int:
    """
    배송비를 qty_total에 균등분배 + remainder(나머지)를 앞쪽부터 1씩 배분한다고 가정.
    qty_refund개 환불 시, 환불 대상 배송비를 반환.
    """
    if qty_total <= 0 or qty_refund <= 0 or amount_shipping <= 0:
        return 0
    base = amount_shipping // qty_total
    rem = amount_shipping % qty_total
    extra = min(qty_refund, rem)
    return (base * qty_refund) + extra


def _infer_unit_price_and_shipping_per_qty(db, reservation_id: int) -> Tuple[int, int]:
    r = db.get(models.Reservation, reservation_id)
    if r is None:
        return 0, 0

    offer = None
    try:
        offer = db.get(models.Offer, r.offer_id)
    except Exception:
        offer = None

    unit_price = 0
    shipping_per_qty = 0

    # 1) offer 기반 시도
    if offer is not None and hasattr(offer, "price"):
        unit_price = _safe_int(getattr(offer, "price", 0), 0)

    if offer is not None and hasattr(offer, "shipping_fee_per_qty"):
        shipping_per_qty = _safe_int(getattr(offer, "shipping_fee_per_qty", 0), 0)

    # 2) reservation 기반 fallback (offer 필드가 비어도 동작)
    rq = _safe_int(getattr(r, "qty", 0), 0)
    at = _safe_int(getattr(r, "amount_total", 0), 0)
    rs = _safe_int(getattr(r, "amount_shipping", 0), 0)
    goods_total = max(0, at - rs)

    if unit_price <= 0 and rq > 0 and goods_total > 0:
        unit_price = max(0, goods_total // rq)

    if shipping_per_qty <= 0 and rq > 0 and rs > 0:
        shipping_per_qty = max(0, rs // rq)

    return unit_price, shipping_per_qty


def _expected_refund_amount_total_B(
    *,
    stage: str,
    actor: str,
    qty_refund: int,
    unit_price: int,
    shipping_fee_per_qty: int,
) -> int:
    """
    정책 B (네가 선택한 룰) 기준:
      - BEFORE_SHIPPING: 전 actor 배송비 환불 O
      - SHIPPED_NOT_DELIVERED/WITHIN_COOLING: buyer_cancel만 배송비 0, 나머지는 O
      - AFTER_COOLING: dispute_resolve만 배송비 O, 나머지는 0
    """
    goods = unit_price * qty_refund

    if stage == "BEFORE_SHIPPING":
        ship = shipping_fee_per_qty * qty_refund
    elif stage in ("SHIPPED_NOT_DELIVERED", "WITHIN_COOLING"):
        ship = 0 if actor == "buyer_cancel" else shipping_fee_per_qty * qty_refund
    elif stage == "AFTER_COOLING":
        ship = shipping_fee_per_qty * qty_refund if actor == "dispute_resolve" else 0
    else:
        ship = 0

    return goods + ship


def _assert_effects(
    *,
    before: Dict[str, Any],
    after: Dict[str, Any],
    expected_qty_delta: int,
    expected_amount_delta: int,
) -> Optional[str]:
    bq = _safe_int(before.get("refunded_qty"), 0)
    aq = _safe_int(after.get("refunded_qty"), 0)
    if (aq - bq) != expected_qty_delta:
        return f"refunded_qty mismatch: before={bq} after={aq} expected_delta={expected_qty_delta}"

    ba = _safe_int(before.get("refunded_amount_total"), 0)
    aa = _safe_int(after.get("refunded_amount_total"), 0)
    if (aa - ba) != expected_amount_delta:
        return f"refunded_amount_total mismatch: before={ba} after={aa} expected_delta={expected_amount_delta}"

    bs = before.get("offer_sold_qty")
    a_s = after.get("offer_sold_qty")
    if bs is not None and a_s is not None:
        bs_i = _safe_int(bs, 0)
        as_i = _safe_int(a_s, 0)
        if (as_i - bs_i) != (-expected_qty_delta):
            return f"offer_sold_qty mismatch: before={bs_i} after={as_i} expected_delta={-expected_qty_delta}"

    return None


def _run_one_actor_stage(
    *,
    db,
    template_reservation_id: int,
    stage: str,
    actor: str,
    partial_qty: int,
    do_full: bool,
    cooling_days: int,
) -> Tuple[int, int]:
    ok = 0
    total = 0

    reservation_id = _clone_paid_reservation(db, template_reservation_id)
    _set_stage_timestamps(db, reservation_id, stage, cooling_days)

    # ================
    # PARTIAL (always)
    # ================
    total += 1
    before = _reservation_snapshot(db, reservation_id)

    decision, meta, amount_source = _call_preview(db, reservation_id, actor, partial_qty)
    preview_amount = _safe_int(decision.get("amount_total_refund"), 0)

    # preview가 0/None을 주는 흔들림 방어: 정책 B로 fallback
    unit_price, ship_per_qty = _infer_unit_price_and_shipping_per_qty(db, reservation_id)
    fallback_amount = _expected_refund_amount_total_B(
        stage=stage,
        actor=actor,
        qty_refund=partial_qty,
        unit_price=unit_price,
        shipping_fee_per_qty=ship_per_qty,
    )

    # BEFORE_SHIPPING은 shipping remainder까지 정확히 배분(실제 reservation.amount_shipping 기반)
    r0 = db.get(models.Reservation, reservation_id)
    rq0 = _safe_int(getattr(r0, "qty", 0), 0) if r0 else 0
    rs0 = _safe_int(getattr(r0, "amount_shipping", 0), 0) if r0 else 0
    ship_alloc_partial = _allocate_shipping_amount(rs0, rq0, partial_qty)
    if stage == "BEFORE_SHIPPING":
        fallback_amount = (unit_price * partial_qty) + ship_alloc_partial

    expected_amount = preview_amount if preview_amount > 0 else fallback_amount
    expected_source = amount_source if preview_amount > 0 else "fallback_B"

    _call_refund(db, reservation_id, actor, partial_qty)
    after = _reservation_snapshot(db, reservation_id)

    err = _assert_effects(
        before=before,
        after=after,
        expected_qty_delta=partial_qty,
        expected_amount_delta=expected_amount,
    )
    if err:
        print(
            _json(
                {
                    "case": "PARTIAL",
                    "stage": stage,
                    "stage_scenario": stage,
                    "cooling_days_used": meta.get("cooling_days_used") if isinstance(meta, dict) else None,
                    "actor": actor,
                    "reservation_id": reservation_id,
                    "decision_supported": bool(decision),
                    "meta_supported": bool(meta),
                    "cooling_state": _log_cooling_state(decision, meta, stage),
                    "amount_total_refund": expected_amount,
                    "expected_source": expected_source,
                    "preview_amount_total_refund": preview_amount,
                    "fallback_amount_total_refund": fallback_amount,
                    "before": {
                        k: before.get(k)
                        for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                    },
                    "after": {
                        k: after.get(k)
                        for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                    },
                    "result": "FAIL",
                    "note": err,
                }
            )
        )
        return ok, total

    print(
        _json(
            {
                "case": "PARTIAL",
                "stage": stage,
                "stage_scenario": stage,
                "cooling_days_used": meta.get("cooling_days_used") if isinstance(meta, dict) else None,
                "actor": actor,
                "reservation_id": reservation_id,
                "decision_supported": bool(decision),
                "meta_supported": bool(meta),
                "cooling_state": _log_cooling_state(decision, meta, stage),
                "amount_total_refund": expected_amount,
                "expected_source": expected_source,
                "preview_amount_total_refund": preview_amount,
                "fallback_amount_total_refund": fallback_amount,
                "before": {
                    k: before.get(k)
                    for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                },
                "after": {
                    k: after.get(k)
                    for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                },
                "result": "OK",
            }
        )
    )
    ok += 1

    # ==================
    # FULL (optional)
    # ==================
    if do_full:
        total += 1
        before2 = _reservation_snapshot(db, reservation_id)
        remaining = _safe_int(before2.get("qty"), 0) - _safe_int(before2.get("refunded_qty"), 0)
        if remaining <= 0:
            print(
                _json(
                    {
                        "case": "FULL",
                        "stage": stage,
                        "actor": actor,
                        "reservation_id": reservation_id,
                        "result": "OK",
                        "note": "already fully refunded (skip)",
                    }
                )
            )
            ok += 1
            return ok, total

        decision2, meta2, amount_source2 = _call_preview(db, reservation_id, actor, None)
        preview_amount2 = _safe_int(decision2.get("amount_total_refund"), 0)

        unit_price2, ship_per_qty2 = _infer_unit_price_and_shipping_per_qty(db, reservation_id)
        fallback_amount2 = _expected_refund_amount_total_B(
            stage=stage,
            actor=actor,
            qty_refund=remaining,
            unit_price=unit_price2,
            shipping_fee_per_qty=ship_per_qty2,
        )

        # BEFORE_SHIPPING remainder-aware shipping allocation
        r2 = db.get(models.Reservation, reservation_id)
        rq2 = _safe_int(getattr(r2, "qty", 0), 0) if r2 else 0
        rs2 = _safe_int(getattr(r2, "amount_shipping", 0), 0) if r2 else 0
        ship_alloc_remaining = _allocate_shipping_amount(rs2, rq2, remaining)
        if stage == "BEFORE_SHIPPING":
            fallback_amount2 = (unit_price2 * remaining) + ship_alloc_remaining

        expected_amount2 = preview_amount2 if preview_amount2 > 0 else fallback_amount2
        expected_source2 = amount_source2 if preview_amount2 > 0 else "fallback_B"

        _call_refund(db, reservation_id, actor, None)
        after2 = _reservation_snapshot(db, reservation_id)

        err2 = _assert_effects(
            before=before2,
            after=after2,
            expected_qty_delta=remaining,
            expected_amount_delta=expected_amount2,
        )
        if err2:
            print(
                _json(
                    {
                        "case": "FULL",
                        "stage": stage,
                        "stage_scenario": stage,
                        "cooling_days_used": meta2.get("cooling_days_used") if isinstance(meta2, dict) else None,
                        "actor": actor,
                        "reservation_id": reservation_id,
                        "decision_supported": bool(decision2),
                        "meta_supported": bool(meta2),
                        "cooling_state": _log_cooling_state(decision2, meta2, stage),
                        "amount_total_refund": expected_amount2,
                        "expected_source": expected_source2,
                        "preview_amount_total_refund": preview_amount2,
                        "fallback_amount_total_refund": fallback_amount2,
                        "before": {
                            k: before2.get(k)
                            for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                        },
                        "after": {
                            k: after2.get(k)
                            for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                        },
                        "result": "FAIL",
                        "note": err2,
                    }
                )
            )
            return ok, total

        print(
            _json(
                {
                    "case": "FULL",
                    "stage": stage,
                    "stage_scenario": stage,
                    "cooling_days_used": meta2.get("cooling_days_used") if isinstance(meta2, dict) else None,
                    "actor": actor,
                    "reservation_id": reservation_id,
                    "decision_supported": bool(decision2),
                    "meta_supported": bool(meta2),
                    "cooling_state": _log_cooling_state(decision2, meta2, stage),
                    "amount_total_refund": expected_amount2,
                    "expected_source": expected_source2,
                    "preview_amount_total_refund": preview_amount2,
                    "fallback_amount_total_refund": fallback_amount2,
                    "before": {
                        k: before2.get(k)
                        for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                    },
                    "after": {
                        k: after2.get(k)
                        for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                    },
                    "result": "OK",
                }
            )
        )
        ok += 1

    return ok, total


# scripts/verify_refund_execution_cooling_v36.py
# -*- coding: utf-8 -*-

"""
VERIFY SCRIPT FREEZE POLICY (v36)

- This script is frozen as a regression baseline.
- Verified OK on: 2025-12-22
- Coverage:
  - stages: BEFORE_SHIPPING / SHIPPED_NOT_DELIVERED / WITHIN_COOLING / AFTER_COOLING
  - actors: dispute_resolve
  - cases: PARTIAL + FULL (qty=3 template)
- Known failure modes (NOT logic bugs):
  - NotFoundError: Offer not found for deal
    -> Usually indicates invalid deal-offer relation / offer not exposed to deal context.
- If behavior changes are needed:
  -> copy to verify_refund_execution_cooling_v37.py and modify there.
"""
"""
Refund execution verifier (v3.6)
- Creates fresh PAID reservations cloned from a template reservation_id
- Sets stage timestamps (BEFORE_SHIPPING / SHIPPED_NOT_DELIVERED / WITHIN_COOLING / AFTER_COOLING)
- Executes refund (PARTIAL and optionally FULL on the SAME reservation)
- Asserts refunded_qty / refunded_amount_total deltas + offer.sold_qty delta (if available)
- Robust against preview return shape changes (2-tuple / 3-tuple) and pydantic model vs dict
- Strengthened patches:
  * preview amount extraction hardened (decision/meta/nested/meta-only) + amount_source tracking
  * fallback unit_price derived from reservation if offer.price missing
  * BEFORE_SHIPPING fallback shipping allocation uses reservation.amount_shipping remainder-aware split
  * log includes decision_supported/meta_supported separately

Usage examples:
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9 --actors=buyer_cancel,dispute_resolve
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9 --partial=2
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9 --full
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9 --full --actors=buyer_cancel
  python .\\scripts\\verify_refund_execution_cooling_v36.py 9 --stages=BEFORE_SHIPPING,WITHIN_COOLING

NOTE (재고/수량 문제):
  템플릿 offer의 remain(가용재고)가 부족하면 create_reservation 단계에서 ConflictError가 납니다.
  offer_id=3 예시에서 올려야 하는 컬럼은 total_available_qty 입니다. (total 아님)
  예)
    $env:PYTHONPATH="."
    python -c "from app.database import SessionLocal; from app import models; db=SessionLocal(); o=db.get(models.Offer, 3); o.total_available_qty=max(o.total_available_qty, (o.sold_qty or 0)+(o.reserved_qty or 0)+1000); db.commit(); print('offer',o.id,'total_available_qty',o.total_available_qty,'sold',o.sold_qty,'reserved',o.reserved_qty); db.close()"
"""

import argparse
import json
from dataclasses import is_dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.database import SessionLocal
from app import models, crud
from sqlalchemy import text


DEFAULT_ACTORS = ["buyer_cancel", "seller_cancel", "admin_force", "system_error", "dispute_resolve"]
DEFAULT_STAGES = ["BEFORE_SHIPPING", "SHIPPED_NOT_DELIVERED", "WITHIN_COOLING", "AFTER_COOLING"]


def _utcnow() -> datetime:
    # timezone-aware UTC -> naive UTC (sqlite가 naive로 저장되는 케이스 방어)
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default


def _to_dict(obj: Any) -> Dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if is_dataclass(obj):
        try:
            return asdict(obj)
        except Exception:
            pass
    # pydantic v2
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    # pydantic v1
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    # 일반 객체
    if hasattr(obj, "__dict__"):
        try:
            return dict(obj.__dict__)
        except Exception:
            pass
    return {}


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _parse_csv_list(s: Optional[str]) -> Optional[List[str]]:
    if not s:
        return None
    items = [x.strip() for x in s.split(",") if x.strip()]
    return items or None


def _normalize_cooling_state(v: Any) -> Optional[str]:
    """
    decision/meta에서 오는 cooling_state가 None/"None"/Enum/문자열 등으로 흔들려도
    로그에는 깔끔하게 "BEFORE_SHIPPING|SHIPPED_NOT_DELIVERED|WITHIN_COOLING|AFTER_COOLING" 또는 None만 남긴다.
    """
    if v is None:
        return None

    # Enum이면 value 우선
    if hasattr(v, "value"):
        try:
            v = v.value
        except Exception:
            pass

    s = str(v).strip()
    if not s or s.lower() == "none":
        return None

    s = s.upper()
    # 혹시 "CoolingState.AFTER_COOLING" 같은 형태로 들어오면 뒤만 취함
    if "." in s:
        s = s.split(".")[-1]

    # 마지막으로 허용 값만 통과
    allowed = {"BEFORE_SHIPPING", "SHIPPED_NOT_DELIVERED", "WITHIN_COOLING", "AFTER_COOLING"}
    return s if s in allowed else s  # 모르는 값이라도 원문 유지(디버깅용)


def _log_cooling_state(decision: dict, meta: dict, stage: str) -> str:
    """
    로그에 찍을 cooling_state를 SSOT(meta/decision)에서 최대한 안정적으로 뽑는다.
    - stage: 스크립트 시나리오 라벨
    - cooling_state: 정책 SSOT(compute_cooling_state 결과)
    둘이 다를 수 있으므로, cooling_state가 비면 stage로 fallback.
    """
    def _get(d: dict, k: str):
        v = d.get(k)
        if v is None:
            return None
        if isinstance(v, str) and v.strip().lower() == "none":
            return None
        return v

    # meta가 SSOT에 더 가까운 편이라 meta 우선
    cs = _get(meta or {}, "cooling_state") or _get(decision or {}, "cooling_state")
    if cs is None:
        return str(stage)

    return str(cs)


def _guess_cooling_days() -> int:
    try:
        from app.config import project_rules as R  # type: ignore

        if hasattr(R, "DEFAULT_COOLING_DAYS"):
            return _safe_int(getattr(R, "DEFAULT_COOLING_DAYS"), 14)

        for k in ["COOLING", "REFUND", "POLICY"]:
            if hasattr(R, k):
                v = getattr(R, k)
                if isinstance(v, dict):
                    for kk in ["DEFAULT_COOLING_DAYS", "cooling_days", "COOLING_DAYS"]:
                        if kk in v:
                            return _safe_int(v.get(kk), 14)
    except Exception:
        pass
    return 14




def _get_offer_policy_cooling_days(db, offer_id: int) -> int | None:
    """
    offer_policies.cancel_within_days 를 읽어 cooling_days로 사용한다.
    없으면 None.
    """
    try:
        row = db.execute(
            text("""
            SELECT cancel_within_days
            FROM offer_policies
            WHERE offer_id = :offer_id
            LIMIT 1
            """),
            {"offer_id": int(offer_id)},
        ).fetchone()
        if not row:
            return None
        v = row[0]
        if v is None:
            return None
        return int(v)
    except Exception:
        return None




def _get_offer_sold_qty(offer: Any) -> Optional[int]:
    for k in ["sold_qty", "sold", "qty_sold", "soldQuantity", "sold_count"]:
        if hasattr(offer, k):
            v = getattr(offer, k)
            if v is not None:
                return _safe_int(v, None)  # type: ignore[arg-type]
    return None


def _reservation_snapshot(db, reservation_id: int) -> Dict[str, Any]:
    r = db.get(models.Reservation, reservation_id)
    if r is None:
        raise RuntimeError(f"reservation not found: {reservation_id}")

    offer_sold_qty = None
    try:
        offer = db.get(models.Offer, r.offer_id)
        if offer is not None:
            offer_sold_qty = _get_offer_sold_qty(offer)
    except Exception:
        offer_sold_qty = None

    return {
        "id": r.id,
        "qty": _safe_int(getattr(r, "qty", 0)),
        "status": str(getattr(r, "status", None)),
        "refunded_qty": _safe_int(getattr(r, "refunded_qty", 0)),
        "refunded_amount_total": _safe_int(getattr(r, "refunded_amount_total", 0)),
        "amount_shipping": _safe_int(getattr(r, "amount_shipping", 0)),
        "amount_total": _safe_int(getattr(r, "amount_total", 0)),
        "offer_id": _safe_int(getattr(r, "offer_id", 0)),
        "offer_sold_qty": offer_sold_qty,
    }


def _clone_paid_reservation(db, template_reservation_id: int) -> int:
    t = db.get(models.Reservation, template_reservation_id)
    if t is None:
        raise RuntimeError("template not found")

    # 1) create
    new_r = crud.create_reservation(
        db,
        deal_id=t.deal_id,
        offer_id=t.offer_id,
        buyer_id=t.buyer_id,
        qty=t.qty,
    )
    db.commit()
    db.refresh(new_r)

    # 2) shipping 강제 재계산 (타입/enum 차이까지 안전하게 처리)
    offer = db.get(models.Offer, new_r.offer_id)
    mode = getattr(offer.shipping_mode, "value", offer.shipping_mode) if offer else None

    if offer:
        if mode == "PER_RESERVATION":
            new_r.amount_shipping = int(offer.shipping_fee_per_reservation or 0)
        elif mode == "PER_QTY":
            new_r.amount_shipping = int((offer.shipping_fee_per_qty or 0) * new_r.qty)
        else:
            # 혹시 모드가 None/이상값이면 안전하게 0 또는 reservation 기존값 유지
            new_r.amount_shipping = int(new_r.amount_shipping or 0)

        new_r.amount_total = int((offer.price * new_r.qty) + new_r.amount_shipping)
        db.add(new_r)
        db.commit()
        db.refresh(new_r)

    # 3) pay (예외 처리 확실히)
    paid = None
    try:
        paid = crud.pay_reservation_v35(
            db,
            reservation_id=new_r.id,
            buyer_id=t.buyer_id,
        )
        db.commit()
        db.refresh(paid)
        return paid.id
    except Exception as e:
        db.rollback()
        # 여기서 paid를 참조하면 안 됨. 바로 예외 올려서 상위에서 FAIL 처리하게.
        raise RuntimeError(f"pay_reservation_v35 failed for reservation_id={new_r.id}: {e}") from e



def _call_preview(
    db, reservation_id: int, actor: str, quantity_refund: Optional[int]
) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """
    returns: (decision_dict, meta_dict, amount_source)
      - amount_source:
        - preview_decision
        - preview_decision_otherkey
        - preview_meta
        - preview_meta_nested
        - missing
    """
    out = crud.preview_refund_for_paid_reservation(
        db,
        reservation_id=reservation_id,
        actor=actor,
        quantity_refund=quantity_refund,
        return_meta=True,
        log_preview=False,
    )

    decision = None
    meta = None

    # return shape compatibility:
    # - (ctx, decision)
    # - (ctx, decision, meta)
    # - occasionally dict-only
    if isinstance(out, tuple):
        if len(out) == 2:
            _, decision = out
        elif len(out) >= 3:
            _, decision, meta = out[0], out[1], out[2]
        else:
            decision = None
            meta = None
    else:
        decision = out

    decision_d = _to_dict(decision)
    meta_d = _to_dict(meta)

    amount_source = "missing"

    def _is_nonzero(v: Any) -> bool:
        return v not in (None, 0, "0", "", False)

    def _get_nonzero(d: Dict[str, Any], keys: List[str]) -> Optional[Any]:
        for k in keys:
            if k in d and _is_nonzero(d.get(k)):
                return d.get(k)
        return None

    def _get_nested_amount(m: Dict[str, Any]) -> Optional[Any]:
        # meta 구조 흔들림 대비: 가능한 경로들을 넓게 잡음
        paths = [
            ("amount_total_refund",),
            ("refund", "amount_total_refund"),
            ("amounts", "amount_total_refund"),
            ("refund_amounts", "amount_total_refund"),
            ("result", "amount_total_refund"),
        ]
        for path in paths:
            cur: Any = m
            ok = True
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    ok = False
                    break
            if ok and _is_nonzero(cur):
                return cur
        return None

    # (1) decision에서 amount 후보 탐색
    if not _is_nonzero(decision_d.get("amount_total_refund")):
        v = _get_nonzero(decision_d, ["amount_total_refund"])
        if _is_nonzero(v):
            decision_d["amount_total_refund"] = v
            amount_source = "preview_decision"
        else:
            v2 = _get_nonzero(
                decision_d,
                ["refund_amount_total", "refund_total", "amount_refund_total", "amount_total"],
            )
            if _is_nonzero(v2):
                decision_d["amount_total_refund"] = v2
                amount_source = "preview_decision_otherkey"
    else:
        amount_source = "preview_decision"

    # (2) decision 금액이 없으면 meta에서 탐색
    if not _is_nonzero(decision_d.get("amount_total_refund")):
        mv = _get_nonzero(
            meta_d,
            ["amount_total_refund", "refund_amount_total", "refund_total", "amount_refund_total"],
        )
        if _is_nonzero(mv):
            decision_d["amount_total_refund"] = mv
            amount_source = "preview_meta"
        else:
            mv2 = _get_nested_amount(meta_d)
            if _is_nonzero(mv2):
                decision_d["amount_total_refund"] = mv2
                amount_source = "preview_meta_nested"

    # (3) cooling_state도 meta에만 있을 수 있음
    if "cooling_state" not in decision_d and "cooling_state" in meta_d:
        decision_d["cooling_state"] = meta_d.get("cooling_state")

    return decision_d, meta_d, amount_source


def _call_refund(db, reservation_id: int, actor: str, quantity_refund: Optional[int]) -> None:
    crud.refund_paid_reservation(
        db,
        reservation_id=reservation_id,
        actor=actor,
        quantity_refund=quantity_refund,
    )
    db.commit()


def _allocate_shipping_amount(amount_shipping: int, qty_total: int, qty_refund: int) -> int:
    """
    배송비를 qty_total에 균등분배 + remainder(나머지)를 앞쪽부터 1씩 배분한다고 가정.
    qty_refund개 환불 시, 환불 대상 배송비를 반환.
    """
    if qty_total <= 0 or qty_refund <= 0 or amount_shipping <= 0:
        return 0
    base = amount_shipping // qty_total
    rem = amount_shipping % qty_total
    extra = min(qty_refund, rem)
    return (base * qty_refund) + extra


def _infer_unit_price_and_shipping_per_qty(db, reservation_id: int) -> Tuple[int, int]:
    r = db.get(models.Reservation, reservation_id)
    if r is None:
        return 0, 0

    offer = None
    try:
        offer = db.get(models.Offer, r.offer_id)
    except Exception:
        offer = None

    unit_price = 0
    shipping_per_qty = 0

    # 1) offer 기반 시도
    if offer is not None and hasattr(offer, "price"):
        unit_price = _safe_int(getattr(offer, "price", 0), 0)

    if offer is not None and hasattr(offer, "shipping_fee_per_qty"):
        shipping_per_qty = _safe_int(getattr(offer, "shipping_fee_per_qty", 0), 0)

    # 2) reservation 기반 fallback (offer 필드가 비어도 동작)
    rq = _safe_int(getattr(r, "qty", 0), 0)
    at = _safe_int(getattr(r, "amount_total", 0), 0)
    rs = _safe_int(getattr(r, "amount_shipping", 0), 0)
    goods_total = max(0, at - rs)

    if unit_price <= 0 and rq > 0 and goods_total > 0:
        unit_price = max(0, goods_total // rq)

    if shipping_per_qty <= 0 and rq > 0 and rs > 0:
        shipping_per_qty = max(0, rs // rq)

    return unit_price, shipping_per_qty


def _expected_refund_amount_total_B(
    *,
    stage: str,
    actor: str,
    qty_refund: int,
    unit_price: int,
    shipping_fee_per_qty: int,
) -> int:
    """
    정책 B (네가 선택한 룰) 기준:
      - BEFORE_SHIPPING: 전 actor 배송비 환불 O
      - SHIPPED_NOT_DELIVERED/WITHIN_COOLING: buyer_cancel만 배송비 0, 나머지는 O
      - AFTER_COOLING: dispute_resolve만 배송비 O, 나머지는 0
    """
    goods = unit_price * qty_refund

    if stage == "BEFORE_SHIPPING":
        ship = shipping_fee_per_qty * qty_refund
    elif stage in ("SHIPPED_NOT_DELIVERED", "WITHIN_COOLING"):
        ship = 0 if actor == "buyer_cancel" else shipping_fee_per_qty * qty_refund
    elif stage == "AFTER_COOLING":
        ship = shipping_fee_per_qty * qty_refund if actor == "dispute_resolve" else 0
    else:
        ship = 0

    return goods + ship


def _assert_effects(
    *,
    before: Dict[str, Any],
    after: Dict[str, Any],
    expected_qty_delta: int,
    expected_amount_delta: int,
) -> Optional[str]:
    bq = _safe_int(before.get("refunded_qty"), 0)
    aq = _safe_int(after.get("refunded_qty"), 0)
    if (aq - bq) != expected_qty_delta:
        return f"refunded_qty mismatch: before={bq} after={aq} expected_delta={expected_qty_delta}"

    ba = _safe_int(before.get("refunded_amount_total"), 0)
    aa = _safe_int(after.get("refunded_amount_total"), 0)
    if (aa - ba) != expected_amount_delta:
        return f"refunded_amount_total mismatch: before={ba} after={aa} expected_delta={expected_amount_delta}"

    bs = before.get("offer_sold_qty")
    a_s = after.get("offer_sold_qty")
    if bs is not None and a_s is not None:
        bs_i = _safe_int(bs, 0)
        as_i = _safe_int(a_s, 0)
        if (as_i - bs_i) != (-expected_qty_delta):
            return f"offer_sold_qty mismatch: before={bs_i} after={as_i} expected_delta={-expected_qty_delta}"

    return None


def _run_one_actor_stage(
    *,
    db,
    template_reservation_id: int,
    stage: str,
    actor: str,
    partial_qty: int,
    do_full: bool,
    cooling_days: int,
) -> Tuple[int, int]:
    ok = 0
    total = 0

    reservation_id = _clone_paid_reservation(db, template_reservation_id)
    _set_stage_timestamps(db, reservation_id, stage, cooling_days)

    # ================
    # PARTIAL (always)
    # ================
    total += 1
    before = _reservation_snapshot(db, reservation_id)

    decision, meta, amount_source = _call_preview(db, reservation_id, actor, partial_qty)
    preview_amount = _safe_int(decision.get("amount_total_refund"), 0)

    # preview가 0/None을 주는 흔들림 방어: 정책 B로 fallback
    unit_price, ship_per_qty = _infer_unit_price_and_shipping_per_qty(db, reservation_id)
    fallback_amount = _expected_refund_amount_total_B(
        stage=stage,
        actor=actor,
        qty_refund=partial_qty,
        unit_price=unit_price,
        shipping_fee_per_qty=ship_per_qty,
    )

    # BEFORE_SHIPPING은 shipping remainder까지 정확히 배분(실제 reservation.amount_shipping 기반)
    r0 = db.get(models.Reservation, reservation_id)
    rq0 = _safe_int(getattr(r0, "qty", 0), 0) if r0 else 0
    rs0 = _safe_int(getattr(r0, "amount_shipping", 0), 0) if r0 else 0
    ship_alloc_partial = _allocate_shipping_amount(rs0, rq0, partial_qty)
    if stage == "BEFORE_SHIPPING":
        fallback_amount = (unit_price * partial_qty) + ship_alloc_partial

    expected_amount = preview_amount if preview_amount > 0 else fallback_amount
    expected_source = amount_source if preview_amount > 0 else "fallback_B"

    _call_refund(db, reservation_id, actor, partial_qty)
    after = _reservation_snapshot(db, reservation_id)

    err = _assert_effects(
        before=before,
        after=after,
        expected_qty_delta=partial_qty,
        expected_amount_delta=expected_amount,
    )
    if err:
        print(
            _json(
                {
                    "case": "PARTIAL",
                    "stage": stage,
                    "stage_scenario": stage,
                    "cooling_days_used": meta.get("cooling_days_used") if isinstance(meta, dict) else None,
                    "actor": actor,
                    "reservation_id": reservation_id,
                    "decision_supported": bool(decision),
                    "meta_supported": bool(meta),
                    "cooling_state": _log_cooling_state(decision, meta, stage),
                    "amount_total_refund": expected_amount,
                    "expected_source": expected_source,
                    "preview_amount_total_refund": preview_amount,
                    "fallback_amount_total_refund": fallback_amount,
                    "before": {
                        k: before.get(k)
                        for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                    },
                    "after": {
                        k: after.get(k)
                        for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                    },
                    "result": "FAIL",
                    "note": err,
                }
            )
        )
        return ok, total

    print(
        _json(
            {
                "case": "PARTIAL",
                "stage": stage,
                "stage_scenario": stage,
                "cooling_days_used": meta.get("cooling_days_used") if isinstance(meta, dict) else None,
                "actor": actor,
                "reservation_id": reservation_id,
                "decision_supported": bool(decision),
                "meta_supported": bool(meta),
                "cooling_state": _log_cooling_state(decision, meta, stage),
                "amount_total_refund": expected_amount,
                "expected_source": expected_source,
                "preview_amount_total_refund": preview_amount,
                "fallback_amount_total_refund": fallback_amount,
                "before": {
                    k: before.get(k)
                    for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                },
                "after": {
                    k: after.get(k)
                    for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                },
                "result": "OK",
            }
        )
    )
    ok += 1

    # ==================
    # FULL (optional)
    # ==================
    if do_full:
        total += 1
        before2 = _reservation_snapshot(db, reservation_id)
        remaining = _safe_int(before2.get("qty"), 0) - _safe_int(before2.get("refunded_qty"), 0)
        if remaining <= 0:
            print(
                _json(
                    {
                        "case": "FULL",
                        "stage": stage,
                        "actor": actor,
                        "reservation_id": reservation_id,
                        "result": "OK",
                        "note": "already fully refunded (skip)",
                    }
                )
            )
            ok += 1
            return ok, total

        decision2, meta2, amount_source2 = _call_preview(db, reservation_id, actor, None)
        preview_amount2 = _safe_int(decision2.get("amount_total_refund"), 0)

        unit_price2, ship_per_qty2 = _infer_unit_price_and_shipping_per_qty(db, reservation_id)
        fallback_amount2 = _expected_refund_amount_total_B(
            stage=stage,
            actor=actor,
            qty_refund=remaining,
            unit_price=unit_price2,
            shipping_fee_per_qty=ship_per_qty2,
        )

        # BEFORE_SHIPPING remainder-aware shipping allocation
        r2 = db.get(models.Reservation, reservation_id)
        rq2 = _safe_int(getattr(r2, "qty", 0), 0) if r2 else 0
        rs2 = _safe_int(getattr(r2, "amount_shipping", 0), 0) if r2 else 0
        ship_alloc_remaining = _allocate_shipping_amount(rs2, rq2, remaining)
        if stage == "BEFORE_SHIPPING":
            fallback_amount2 = (unit_price2 * remaining) + ship_alloc_remaining

        expected_amount2 = preview_amount2 if preview_amount2 > 0 else fallback_amount2
        expected_source2 = amount_source2 if preview_amount2 > 0 else "fallback_B"

        _call_refund(db, reservation_id, actor, None)
        after2 = _reservation_snapshot(db, reservation_id)

        err2 = _assert_effects(
            before=before2,
            after=after2,
            expected_qty_delta=remaining,
            expected_amount_delta=expected_amount2,
        )
        if err2:
            print(
                _json(
                    {
                        "case": "FULL",
                        "stage": stage,
                        "stage_scenario": stage,
                        "cooling_days_used": meta2.get("cooling_days_used") if isinstance(meta2, dict) else None,
                        "actor": actor,
                        "reservation_id": reservation_id,
                        "decision_supported": bool(decision2),
                        "meta_supported": bool(meta2),
                        "cooling_state": _log_cooling_state(decision2, meta2, stage),
                        "amount_total_refund": expected_amount2,
                        "expected_source": expected_source2,
                        "preview_amount_total_refund": preview_amount2,
                        "fallback_amount_total_refund": fallback_amount2,
                        "before": {
                            k: before2.get(k)
                            for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                        },
                        "after": {
                            k: after2.get(k)
                            for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                        },
                        "result": "FAIL",
                        "note": err2,
                    }
                )
            )
            return ok, total

        print(
            _json(
                {
                    "case": "FULL",
                    "stage": stage,
                    "stage_scenario": stage,
                    "cooling_days_used": meta2.get("cooling_days_used") if isinstance(meta2, dict) else None,
                    "actor": actor,
                    "reservation_id": reservation_id,
                    "decision_supported": bool(decision2),
                    "meta_supported": bool(meta2),
                    "cooling_state": _log_cooling_state(decision2, meta2, stage),
                    "amount_total_refund": expected_amount2,
                    "expected_source": expected_source2,
                    "preview_amount_total_refund": preview_amount2,
                    "fallback_amount_total_refund": fallback_amount2,
                    "before": {
                        k: before2.get(k)
                        for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                    },
                    "after": {
                        k: after2.get(k)
                        for k in ["refunded_qty", "refunded_amount_total", "status", "offer_sold_qty"]
                    },
                    "result": "OK",
                }
            )
        )
        ok += 1

    return ok, total


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("template_reservation_id", type=int)
    ap.add_argument("--actors", type=str, default=None, help="comma-separated (buyer_cancel,seller_cancel,...)")
    ap.add_argument("--stages", type=str, default=None, help="comma-separated (BEFORE_SHIPPING,WITHIN_COOLING,...)")
    ap.add_argument("--partial", type=int, default=1, help="partial refund qty (default=1)")
    ap.add_argument("--full", action="store_true", help="also run FULL refund after PARTIAL on same reservation")
    args = ap.parse_args(argv)

    actors = _parse_csv_list(args.actors) or DEFAULT_ACTORS
    stages = _parse_csv_list(args.stages) or DEFAULT_STAGES
    partial_qty = int(args.partial)
    do_full = bool(args.full)

    db = SessionLocal()
    try:
        tpl = db.get(models.Reservation, args.template_reservation_id)
        if tpl is None:
            print(f"[ERR] template reservation not found: {args.template_reservation_id}")
            return 2

        # ✅ 새 로직: tpl.offer_id -> offer_policies.cancel_within_days 우선
        cooling_days = _get_offer_policy_cooling_days(db, int(tpl.offer_id))
        if cooling_days is None:
            cooling_days = _guess_cooling_days()

        # ✅ 안전 가드
        cooling_days = int(cooling_days)
        if cooling_days < 0 or cooling_days > 365:
            raise ValueError(f"cooling_days out of range: {cooling_days}")

        print("=" * 100)
        print(f"[INFO] template reservation_id={tpl.id} offer_id={tpl.offer_id} buyer_id={tpl.buyer_id} qty={tpl.qty}")
        print(f"[INFO] template amount_shipping={getattr(tpl, 'amount_shipping', None)} amount_total={getattr(tpl, 'amount_total', None)}")
        print(f"[INFO] cooling_days(resolved)={cooling_days}")
        print("=" * 100)

        ok_cases = 0
        total_cases = 0

        for stage in stages:
            print("\n" + "#" * 110)
            print(f"# STAGE = {stage}")
            print("#" * 110)

            for actor in actors:
                try:
                    ok, total = _run_one_actor_stage(
                        db=db,
                        template_reservation_id=tpl.id,
                        stage=stage,
                        actor=actor,
                        partial_qty=partial_qty,
                        do_full=do_full,
                        cooling_days=cooling_days,
                    )
                    ok_cases += ok
                    total_cases += total
                except Exception as e:
                    db.rollback()
                    print(
                        _json(
                            {
                                "stage": stage,
                                "actor": actor,
                                "result": "FAIL",
                                "note": f"exception: {type(e).__name__}: {e}",
                            }
                        )
                    )
                    return 3

        print("\n" + "=" * 110)
        print(f"[OK] verify_refund_execution_cooling_v36 finished. ok_cases={ok_cases}/{total_cases}")
        print("=" * 110)
        return 0

    finally:
        db.close()

if __name__ == "__main__":
    raise SystemExit(main())