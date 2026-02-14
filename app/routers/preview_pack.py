# app/routers/preview_pack v1.1.py
from __future__ import annotations
from pathlib import Path

from app.policy.pricing_engine import (
    load_pricing_params,
    PriceInputs,
    compute_pricing,
    compute_offer_comparison,
)
from app.policy.pingpong_pricing_explain import normalize_pricing_phrases
from app.policy.pingpong_pricing_explain import render_pingpong_pricing_explain
from app.policy.pricing_guardrail_hook import (
    run_pricing_guardrail,
    attach_guardrail_to_pack,
)

import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.database import get_db
from app import models

router = APIRouter(prefix="/preview", tags=["Preview Pack"])

# -----------------------------
# Reason codes (SSOT)
# -----------------------------
RC_OK = "OK"
RC_NOT_FOUND = "NOT_FOUND"
RC_DENIED = "DENIED"
RC_MISSING_DATA = "MISSING_DATA"
RC_TIMEOUT = "TIMEOUT"
RC_UPSTREAM_FAIL = "UPSTREAM_FAIL"

KST = ZoneInfo("Asia/Seoul")


# -----------------------------
# Small helpers
# -----------------------------
def _now_kst() -> datetime:
    return datetime.now(KST)


def _fmt_dt(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        return v[:16]
    if isinstance(v, datetime):
        try:
            if v.tzinfo is not None:
                v = v.astimezone(KST)
        except Exception:
            pass
        return v.strftime("%Y-%m-%d %H:%M")
    return str(v)


def _enum_to_str(v: Any) -> Any:
    if v is None:
        return None
    try:
        if isinstance(v, Enum):
            return v.name
    except Exception:
        pass
    s = str(v)
    # "ReservationStatus.PAID" -> "PAID"
    if "." in s and s.count(".") >= 1:
        tail = s.split(".")[-1]
        if tail.isupper():
            return tail
    return s


def _latency_ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def _resolve_actor_ctx(db: Session, user_id: int, role: str) -> Dict[str, Any]:
    role_u = (role or "BUYER").upper()

    # try a few known locations
    for mod in ("app.pingpong.access", "app.pingpong.actor", "app.pingpong.security"):
        try:
            m = __import__(mod, fromlist=["resolve_actor"])
            resolve_actor = getattr(m, "resolve_actor", None)
            if callable(resolve_actor):
                a = resolve_actor(db, user_id=user_id, role_hint=role_u)
                return {
                    "kind": str(getattr(a, "kind", role_u) or role_u).upper(),
                    "buyer_id": getattr(a, "buyer_id", None),
                    "seller_id": getattr(a, "seller_id", None),
                    "actuator_id": getattr(a, "actuator_id", None),
                    "admin_user_id": getattr(a, "admin_user_id", None),
                }
        except Exception:
            pass

    # fallback (dev)
    return {
        "kind": role_u,
        "buyer_id": user_id if role_u == "BUYER" else None,
        "seller_id": user_id if role_u == "SELLER" else None,
        "actuator_id": user_id if role_u == "ACTUATOR" else None,
        "admin_user_id": user_id if role_u == "ADMIN" else None,
    }


def _fail(entity: str, _id: int, reason_code: str, actor: Dict[str, Any], err: str, t0: float) -> Dict[str, Any]:
    return {
        "ok": False,
        "reason_code": reason_code,
        "entity": entity,
        "id": _id,
        "actor": actor,
        "error": err,
        "latency_ms": _latency_ms(t0),
    }


def _ok(entity: str, _id: int, actor: Dict[str, Any], pack: Dict[str, Any], times: Dict[str, Any], t0: float) -> Dict[str, Any]:
    return {
        "ok": True,
        "reason_code": RC_OK,
        "entity": entity,
        "id": _id,
        "actor": actor,
        "times": times,
        "pack": pack,
        "latency_ms": _latency_ms(t0),
    }


def _extract_entity_times(obj: Any) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {}
    if obj is None:
        return out
    keys: List[str] = []
    try:
        mapper = obj.__mapper__
        cols = [c.key for c in mapper.column_attrs]
        keys = [k for k in cols if k.endswith("_at") or k in ("created_at", "updated_at", "deleted_at")]
    except Exception:
        keys = []
    for k in sorted(set(keys)):
        try:
            out[k] = _fmt_dt(getattr(obj, k, None))
        except Exception:
            out[k] = None
    return out


def _event_table_name() -> str:
    try:
        return str(getattr(models.EventLog, "__tablename__", "event_logs"))
    except Exception:
        return "event_logs"


def _fetch_events_raw(
    db: Session,
    *,
    buyer_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    offer_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    ✅ Enum mismatch(SETTLE_PAID 등)로 ORM이 터지는 걸 피하려 raw SQL 사용
    """
    conds: List[str] = []
    params: Dict[str, Any] = {"limit": int(limit)}

    if buyer_id is not None:
        conds.append("buyer_id = :buyer_id")
        params["buyer_id"] = int(buyer_id)
    if seller_id is not None:
        conds.append("seller_id = :seller_id")
        params["seller_id"] = int(seller_id)
    if deal_id is not None:
        conds.append("deal_id = :deal_id")
        params["deal_id"] = int(deal_id)
    if offer_id is not None:
        conds.append("offer_id = :offer_id")
        params["offer_id"] = int(offer_id)
    if reservation_id is not None:
        conds.append("reservation_id = :reservation_id")
        params["reservation_id"] = int(reservation_id)

    if not conds:
        return []

    table = _event_table_name()
    sql = f"""
SELECT
  id,
  event_type,
  created_at as at,
  actor_type,
  actor_id,
  buyer_id,
  seller_id,
  deal_id,
  offer_id,
  reservation_id,
  amount,
  qty,
  reason,
  idempotency_key
FROM {table}
WHERE {" OR ".join(conds)}
ORDER BY created_at DESC
LIMIT :limit
""".strip()

    rows = db.execute(text(sql), params).mappings().all()
    out: List[Dict[str, Any]] = []
    seen: set[int] = set()

    for r in rows:
        eid = int(r.get("id") or 0)
        if eid and eid in seen:
            continue
        if eid:
            seen.add(eid)

        ev = dict(r)
        ev["at"] = _fmt_dt(ev.get("at"))

        # scope tagging
        scope = "unknown"
        if reservation_id is not None and ev.get("reservation_id") == reservation_id:
            scope = "reservation"
        elif offer_id is not None and ev.get("offer_id") == offer_id:
            scope = "offer"
        elif deal_id is not None and ev.get("deal_id") == deal_id:
            scope = "deal"
        elif seller_id is not None and ev.get("seller_id") == seller_id:
            scope = "seller"
        elif buyer_id is not None and ev.get("buyer_id") == buyer_id:
            scope = "buyer"
        ev["scope"] = scope

        out.append(ev)

    return out


def _times(as_of: datetime, entity_obj: Any, events: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "as_of": _fmt_dt(as_of),
        "entity": _extract_entity_times(entity_obj),
        "events": events,
    }


def _pack_reservation(r: Any) -> Dict[str, Any]:
    return {
        "id": getattr(r, "id", None),
        "status": _enum_to_str(getattr(r, "status", None)) or "UNKNOWN",
        "deal_id": getattr(r, "deal_id", None),
        "offer_id": getattr(r, "offer_id", None),
        "buyer_id": getattr(r, "buyer_id", None),
        "seller_id": getattr(r, "seller_id", None),
        "qty": getattr(r, "qty", None),
        "amount_total": getattr(r, "amount_total", None),
        "amount_shipping": getattr(r, "amount_shipping", None),
        "refunded_qty": getattr(r, "refunded_qty", None),
        "refunded_amount_total": getattr(r, "refunded_amount_total", None),
        "created_at": _fmt_dt(getattr(r, "created_at", None)),
        "expires_at": _fmt_dt(getattr(r, "expires_at", None)),
        "paid_at": _fmt_dt(getattr(r, "paid_at", None)),
        "cancelled_at": _fmt_dt(getattr(r, "cancelled_at", None)),
        "shipped_at": _fmt_dt(getattr(r, "shipped_at", None)),
        "arrival_confirmed_at": _fmt_dt(getattr(r, "arrival_confirmed_at", None)),
        "dispute_opened_at": _fmt_dt(getattr(r, "dispute_opened_at", None)),
        "dispute_closed_at": _fmt_dt(getattr(r, "dispute_closed_at", None)),
    }

def _get_deal_room_qty(db: Session, deal_id: int) -> int:
    """
    DealParticipant.qty 합계로 '딜방 총 수량(q_room)'을 계산.
    qty_target이 없을 때 fallback으로 사용.
    """
    try:
        total = (
            db.query(func.sum(models.DealParticipant.qty))
              .filter(models.DealParticipant.deal_id == deal_id)
              .scalar()
        )
        return int(total or 0)
    except Exception:
        return 0


# -----------------------------
# Pricing (SSOT) — offer preview only (minimal)
# -----------------------------
_PRICING_PARAMS = None

def _get_pricing_params():
    """
    pricing.yaml 로드 (캐시)
    - 후보 경로를 2개(레거시/신규) 모두 시도해서 환경에 따라 안 깨지게 함.
    """
    global _PRICING_PARAMS
    if _PRICING_PARAMS is not None:
        return _PRICING_PARAMS

    try:
        repo_root = Path(__file__).resolve().parents[2]  # .../<repo>
        candidates = [
            # ✅ (추천) repo/app/policy/params/pricing.yaml
            repo_root / "app" / "policy" / "params" / "pricing.yaml",
            # ✅ (레거시/실수 대비) repo/policy/params/pricing.yaml
            repo_root / "policy" / "params" / "pricing.yaml",
        ]

        yaml_path = None
        for p in candidates:
            if p.exists():
                yaml_path = p
                break

        if yaml_path is None:
            _PRICING_PARAMS = None
            return None

        _PRICING_PARAMS = load_pricing_params(str(yaml_path))
        return _PRICING_PARAMS

    except Exception:
        _PRICING_PARAMS = None
        return None


def _maybe_pack_pricing_for_offer(db: Session, offer: Any, deal: Any) -> Optional[Dict[str, Any]]:
    """
    ✅ 핵심 원칙
    - 판매자 가격은 바꾸지 않는다(P_offer 고정)
    - 공동구매 기준선은 offer-cap 수량 기준으로 계산한다:
        Q_offer = min(Q_room, offer.total_available_qty)
    - 출력은 '기준조건 대비 ○원 비쌈/저렴' 문장 중심
    - ✅ 개선: deal.anchor_price(있으면) -> p_anchor로 연결해서 pricing.reference.p_anchor가 null이 아니게 함
    """
    params = _get_pricing_params()
    if not params:
        return None
    if offer is None or deal is None:
        return None

    try:
        # -------------------------------------------------
        # deal 기준
        # -------------------------------------------------
        p_target = getattr(deal, "target_price", None)

        # ✅ anchor 연결 (있으면 사용, 없으면 None)
        p_anchor = getattr(deal, "anchor_price", None)
        p_anchor = float(p_anchor) if p_anchor is not None else None
        if p_anchor is not None and p_anchor <= 0:
            p_anchor = None

        qty_room = int(getattr(deal, "qty_target", 0) or 0)
        if qty_room <= 0:
            deal_id = int(getattr(deal, "id", 0) or 0)
            if deal_id > 0:
                qty_room = _get_deal_room_qty(db, deal_id)

        qty_room = max(1, int(qty_room or 0))

        # -------------------------------------------------
        # offer 기준
        # -------------------------------------------------
        p_offer = float(getattr(offer, "price", 0) or 0)
        if p_offer <= 0:
            return None

        offer_cap = int(getattr(offer, "total_available_qty", 0) or 0)
        offer_cap = max(1, offer_cap)

        # ✅ offer-cap 반영
        q_offer = min(qty_room, offer_cap)

        # -------------------------------------------------
        # 기준조건(표준조건) 기준가 (base)
        # -------------------------------------------------
        # - deal.target_price 있으면 그 값을 기준조건(p_base)으로 사용 (UX 기준축 통일)
        # - 없으면 offer.price 를 기준조건으로 사용 (fallback)
        p_base = float(p_target) if p_target is not None else float(p_offer)

        # 조건값(없으면 baseline 사용)
        ship_days = getattr(offer, "delivery_days", None)  # offers.py에 delivery_days 흔적 있음
        shipping_fee = getattr(offer, "shipping_fee", None)

        inp = PriceInputs(
            p_anchor=p_anchor,  # ✅ 핵심 개선: anchor 연결
            p_base=p_base,
            p_target=float(p_target) if p_target is not None else None,
            q=q_offer,
            q_target=qty_room,
            category=getattr(deal, "category", None) or "default",  # TODO: deal.category 필드 있으면 연결
            ship_days=float(ship_days) if ship_days is not None else None,
            shipping_fee_krw=float(shipping_fee) if shipping_fee is not None else None,
            refund_grade=None,
            as_grade=None,
            seller_tier=None,
            seller_score=None,
            risk_level=None,
        )

        out = compute_pricing(params, inp)
        cmp = compute_offer_comparison(params, out, p_offer=p_offer)

        # --- numbers (int) ---
        p_group = int(round(out.p_group))
        p_expected = int(round(cmp.p_expected))

        # q_room이 None/0이면, cap 기준으로만 계산한 걸 명시 (UX 혼란 방지)
        q_room_effective = int(qty_room or 0)
        if q_room_effective <= 0:
            q_room_effective = int(q_offer)

        return {
            "as_of": _fmt_dt(datetime.now(tz=KST)),
            "reference": {
                "label": "역핑 표준조건(기준조건) 기준",
                "p_base": int(round(p_base)),
                "p_target": int(round(p_target)) if p_target is not None else None,
                "p_anchor": int(round(p_anchor)) if p_anchor is not None else None,  # ✅ 개선
            },
            "groupbuy": {
                "p_group": p_group,
                "q_room": q_room_effective,      # ✅ 0/None이면 cap으로라도 의미 있게
                "q_offer": int(q_offer),
                "offer_cap_qty": int(offer_cap),
                "note": (
                    "공동구매가는 '이 오퍼가 소화 가능한 수량(q_offer=min(q_room, cap))' 기준으로 계산됩니다."
                    if int(offer_cap) > 0 else
                    "공동구매가는 오퍼 cap 정보가 없어 기본값 기준으로 계산됩니다."
                ),
            },
            "offer_evaluation": {
                "seller_offer_price": int(round(p_offer)),
                "expected_price_under_offer_conditions": p_expected,

                # ✅ 표준 문구 키 (너가 원하던 형태)
                "phrases": {
                    "vs_expected": cmp.phrase_vs_expected,         # "기준조건 대비 n원 비쌈/저렴"
                    "vs_groupbuy_offer_cap": cmp.phrase_vs_group,  # "공동구매 기준 대비 n원 비쌈/저렴"
                    # --- backward compat (기존 키도 유지) ---
                    "vs_base": cmp.phrase_vs_expected,
                    "vs_group": cmp.phrase_vs_group,
                },
            },

            # (선택) 설명용: 너무 길면 지워도 됨
            "why": [
                "판매자 가격은 고정입니다. 역핑은 비교만 제공합니다.",
                "조건(배송/환불/신뢰/리스크)에 따라 결과가 달라질 수 있습니다.",
            ],
        }

    except Exception:
        return None


def _pack_offer(o: Any) -> Dict[str, Any]:
    if o is None:
        return {}
    status = getattr(o, "status", None)
    status_s = _enum_to_str(status) or "UNKNOWN"
    return {
        "id": getattr(o, "id", None),
        "status": status_s,
        "deal_id": getattr(o, "deal_id", None),
        "seller_id": getattr(o, "seller_id", None),
        "price": getattr(o, "price", None),
        "shipping_fee": getattr(o, "shipping_fee", None),
        "created_at": _fmt_dt(getattr(o, "created_at", None)),
        "deadline_at": _fmt_dt(getattr(o, "deadline_at", None)),
        "decision_deadline_at": _fmt_dt(getattr(o, "decision_deadline_at", None)),
        "decision_made_at": _fmt_dt(getattr(o, "decision_made_at", None)),
    }


def _pack_deal(d: Any) -> Dict[str, Any]:
    if d is None:
        return {}
    return {
        "id": getattr(d, "id", None),
        "status": _enum_to_str(getattr(d, "status", None)) or "UNKNOWN",
        "title": getattr(d, "title", None),
        "buyer_id": getattr(d, "buyer_id", None),
        "target_price": getattr(d, "target_price", None),
        "qty_target": getattr(d, "qty_target", None),
        "created_at": _fmt_dt(getattr(d, "created_at", None)),
        "deadline_at": _fmt_dt(getattr(d, "deadline_at", None)),
        "closed_at": _fmt_dt(getattr(d, "closed_at", None)),
    }


def _safe_points_balance(db: Session, buyer_id: int) -> Optional[int]:
    try:
        PT = models.PointTransaction
        amount_col = None
        for name in ("amount", "points", "pt"):
            if hasattr(PT, name):
                amount_col = getattr(PT, name)
                break
        if amount_col is None:
            return None
        id_col = None
        for name in ("buyer_id", "user_id"):
            if hasattr(PT, name):
                id_col = getattr(PT, name)
                break
        if id_col is None:
            return None
        v = db.query(func.coalesce(func.sum(amount_col), 0)).filter(id_col == int(buyer_id)).scalar()
        return int(v or 0)
    except Exception:
        return None


def _safe_recent_points(db: Session, buyer_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    try:
        PT = models.PointTransaction
        id_col = None
        for name in ("buyer_id", "user_id"):
            if hasattr(PT, name):
                id_col = getattr(PT, name)
                break
        if id_col is None:
            return []
        q = db.query(PT).filter(id_col == int(buyer_id))
        if hasattr(PT, "id"):
            q = q.order_by(getattr(PT, "id").desc())
        rows = q.limit(int(limit)).all()
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append({
                "id": getattr(r, "id", None),
                "amount": getattr(r, "amount", None) if hasattr(r, "amount") else getattr(r, "points", None),
                "reason": getattr(r, "reason", None),
                "created_at": _fmt_dt(getattr(r, "created_at", None)),
            })
        return out
    except Exception:
        return []


@router.get("/reservation/{reservation_id}")
def preview_reservation(
    reservation_id: int,
    user_id: int = Query(...),
    role: str = Query("BUYER"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    t0 = time.time()
    actor = _resolve_actor_ctx(db, user_id=user_id, role=role)

    try:
        r = db.query(models.Reservation).filter(models.Reservation.id == int(reservation_id)).first()
        if not r:
            return _fail("reservation", reservation_id, RC_NOT_FOUND, actor, "reservation not found", t0)

        offer = None
        deal = None

        oid = getattr(r, "offer_id", None)
        if oid:
            offer = db.query(models.Offer).filter(models.Offer.id == int(oid)).first()

        did = getattr(r, "deal_id", None) or (getattr(offer, "deal_id", None) if offer is not None else None)
        if did:
            deal = db.query(models.Deal).filter(models.Deal.id == int(did)).first()

        events = _fetch_events_raw(
            db,
            buyer_id=getattr(r, "buyer_id", None),
            seller_id=(getattr(offer, "seller_id", None) if offer is not None else None),
            deal_id=did,
            offer_id=oid,
            reservation_id=int(reservation_id),
            limit=50,
        )

        times = _times(_now_kst(), r, events)
        pack = {
            "reservation": _pack_reservation(r),
            "offer": _pack_offer(offer) if offer is not None else None,
            "deal": _pack_deal(deal) if deal is not None else None,
        }
        return _ok("reservation", reservation_id, actor, pack, times, t0)

    except Exception as e:
        return _fail("reservation", reservation_id, RC_UPSTREAM_FAIL, actor, repr(e), t0)


@router.get("/offer/{offer_id}")
def preview_offer(
    offer_id: int,
    user_id: int = Query(...),
    role: str = Query("BUYER"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    t0 = time.time()
    actor = _resolve_actor_ctx(db, user_id=user_id, role=role)

    try:
        o = db.query(models.Offer).filter(models.Offer.id == int(offer_id)).first()
        if not o:
            return _fail("offer", offer_id, RC_NOT_FOUND, actor, "offer not found", t0)

        deal = None
        did = getattr(o, "deal_id", None)
        if did:
            deal = db.query(models.Deal).filter(models.Deal.id == int(did)).first()

        events = _fetch_events_raw(
            db,
            buyer_id=None,
            seller_id=getattr(o, "seller_id", None),
            deal_id=did,
            offer_id=int(offer_id),
            reservation_id=None,
            limit=50,
        )

        times = _times(_now_kst(), o, events)
        pack = {"offer": _pack_offer(o), "deal": _pack_deal(deal) if deal is not None else None}
        pricing = _maybe_pack_pricing_for_offer(db, o, deal)
        if pricing is not None:
            pack["pricing"] = pricing

            # ✅ pricing이 있을 때만 guardrail을 붙인다
            # (pricing_guardrail_hook.attach_guardrail_to_pack는 pricing 없으면 no-op)
            try:
                result = run_pricing_guardrail(
                    deal_id=int(getattr(deal, "id", 0) or 0),
                    category=getattr(deal, "category", None),
                    target_price=getattr(deal, "target_price", None),
                    anchor_price=getattr(deal, "anchor_price", None),
                    evidence_score=getattr(deal, "evidence_score", 0) or 0,
                    anchor_confidence=getattr(deal, "anchor_confidence", 1.0) or 1.0,
                )
                pack = attach_guardrail_to_pack(pack, result)
            except Exception:
                pass

        return _ok("offer", offer_id, actor, pack, times, t0)

    except Exception as e:
        return _fail("offer", offer_id, RC_UPSTREAM_FAIL, actor, repr(e), t0)




@router.get("/deal/{deal_id}")
def preview_deal(
    deal_id: int,
    user_id: int = Query(...),
    role: str = Query("BUYER"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    t0 = time.time()
    actor = _resolve_actor_ctx(db, user_id=user_id, role=role)

    try:
        d = db.query(models.Deal).filter(models.Deal.id == int(deal_id)).first()
        if not d:
            return _fail("deal", deal_id, RC_NOT_FOUND, actor, "deal not found", t0)

        events = _fetch_events_raw(
            db,
            buyer_id=getattr(d, "buyer_id", None),
            seller_id=None,
            deal_id=int(deal_id),
            offer_id=None,
            reservation_id=None,
            limit=50,
        )

        times = _times(_now_kst(), d, events)
        pack = {"deal": _pack_deal(d), "pricing": {}, }

        result = run_pricing_guardrail(
            deal_id=int(getattr(d, "id", 0) or 0),
            category=getattr(d, "category", None),
            target_price=getattr(d, "target_price", None),
            anchor_price=getattr(d, "anchor_price", None),
            evidence_score=getattr(d, "evidence_score", 0) or 0,
            anchor_confidence=getattr(d, "anchor_confidence", 1.0) or 1.0,
        )
        pack = attach_guardrail_to_pack(pack, result)
        return _ok("deal", deal_id, actor, pack, times, t0)

    except Exception as e:
        return _fail("deal", deal_id, RC_UPSTREAM_FAIL, actor, repr(e), t0)


@router.get("/buyer/{buyer_id}")
def preview_buyer(
    buyer_id: int,
    user_id: int = Query(...),
    role: str = Query("BUYER"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    t0 = time.time()
    actor = _resolve_actor_ctx(db, user_id=user_id, role=role)

    try:
        b = db.query(models.Buyer).filter(models.Buyer.id == int(buyer_id)).first()
        if not b:
            return _fail("buyer", buyer_id, RC_NOT_FOUND, actor, "buyer not found", t0)

        points_balance = _safe_points_balance(db, int(buyer_id))
        points_recent = _safe_recent_points(db, int(buyer_id), limit=20)

        events = _fetch_events_raw(db, buyer_id=int(buyer_id), seller_id=None, deal_id=None, offer_id=None, reservation_id=None, limit=50)

        times = _times(_now_kst(), b, events)
        pack = {
            "buyer": {"id": getattr(b, "id", None), "status": _enum_to_str(getattr(b, "status", None))},
            "points": {"balance": points_balance, "recent": points_recent},
        }
        return _ok("buyer", buyer_id, actor, pack, times, t0)

    except Exception as e:
        return _fail("buyer", buyer_id, RC_UPSTREAM_FAIL, actor, repr(e), t0)


@router.get("/seller/{seller_id}")
def preview_seller(
    seller_id: int,
    user_id: int = Query(...),
    role: str = Query("SELLER"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    t0 = time.time()
    actor = _resolve_actor_ctx(db, user_id=user_id, role=role)

    try:
        s = db.query(models.Seller).filter(models.Seller.id == int(seller_id)).first()
        if not s:
            return _fail("seller", seller_id, RC_NOT_FOUND, actor, "seller not found", t0)

        rating = None
        try:
            if hasattr(models, "SellerRatingAggregate"):
                rating = db.query(models.SellerRatingAggregate).filter(models.SellerRatingAggregate.seller_id == int(seller_id)).first()
        except Exception:
            rating = None

        events = _fetch_events_raw(db, buyer_id=None, seller_id=int(seller_id), deal_id=None, offer_id=None, reservation_id=None, limit=50)

        times = _times(_now_kst(), s, events)
        pack = {
            "seller": {"id": getattr(s, "id", None), "status": _enum_to_str(getattr(s, "status", None))},
            "rating_agg": None if rating is None else {
                "seller_id": getattr(rating, "seller_id", None),
                "avg_rating": getattr(rating, "avg_rating", None),
                "count_reviews": getattr(rating, "count_reviews", None),
            },
        }
        return _ok("seller", seller_id, actor, pack, times, t0)

    except Exception as e:
        return _fail("seller", seller_id, RC_UPSTREAM_FAIL, actor, repr(e), t0)


@router.get("/actuator/{actuator_id}")
def preview_actuator(
    actuator_id: int,
    user_id: int = Query(...),
    role: str = Query("ACTUATOR"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    t0 = time.time()
    actor = _resolve_actor_ctx(db, user_id=user_id, role=role)

    try:
        a = db.query(models.Actuator).filter(models.Actuator.id == int(actuator_id)).first()
        if not a:
            return _fail("actuator", actuator_id, RC_NOT_FOUND, actor, "actuator not found", t0)

        times = {"as_of": _fmt_dt(_now_kst()), "entity": _extract_entity_times(a), "events": []}
        pack = {"actuator": {"id": getattr(a, "id", None), "status": _enum_to_str(getattr(a, "status", None))}}
        return _ok("actuator", actuator_id, actor, pack, times, t0)

    except Exception as e:
        return _fail("actuator", actuator_id, RC_UPSTREAM_FAIL, actor, repr(e), t0)


@router.get("/me")
def preview_me(
    user_id: int = Query(...),
    role: str = Query("BUYER"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    t0 = time.time()
    actor = _resolve_actor_ctx(db, user_id=user_id, role=role)
    kind = (actor.get("kind") or "BUYER").upper()

    try:
        if kind == "BUYER" and actor.get("buyer_id"):
            return preview_buyer(int(actor["buyer_id"]), user_id=user_id, role=role, db=db)
        if kind == "SELLER" and actor.get("seller_id"):
            return preview_seller(int(actor["seller_id"]), user_id=user_id, role=role, db=db)
        if kind == "ACTUATOR" and actor.get("actuator_id"):
            return preview_actuator(int(actor["actuator_id"]), user_id=user_id, role=role, db=db)

        times = {"as_of": _fmt_dt(_now_kst()), "entity": {}, "events": []}
        return _ok("me", int(user_id), actor, {"me": actor}, times, t0)

    except Exception as e:
        return _fail("me", int(user_id), RC_UPSTREAM_FAIL, actor, repr(e), t0)