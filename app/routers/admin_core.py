# app/routers/admin_core.py
"""Admin core APIs: deals/offers/reservations/stats/notifications listing + broadcast"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import get_db
from app import models

router = APIRouter(prefix="/admin", tags=["admin-core"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── GET /admin/stats/counts — 초경량 카운트 전용 ─────────
@router.get("/stats/counts")
def admin_stats_counts(db: Session = Depends(get_db)):
    """DB 실제 COUNT만 반환. 대시보드 KPI용."""
    from sqlalchemy import cast, String as SAString
    result: dict = {}
    try:
        result["buyers"] = db.query(sa_func.count(models.Buyer.id)).scalar() or 0
    except Exception:
        result["buyers"] = 0
    try:
        result["sellers"] = db.query(sa_func.count(models.Seller.id)).scalar() or 0
    except Exception:
        result["sellers"] = 0
    try:
        result["deals"] = db.query(sa_func.count(models.Deal.id)).scalar() or 0
    except Exception:
        result["deals"] = 0
    try:
        result["offers"] = db.query(sa_func.count(models.Offer.id)).scalar() or 0
    except Exception:
        result["offers"] = 0
    try:
        result["reservations"] = db.query(sa_func.count(models.Reservation.id)).scalar() or 0
    except Exception:
        result["reservations"] = 0
    try:
        result["actuators"] = db.query(sa_func.count(models.Actuator.id)).scalar() or 0
    except Exception:
        result["actuators"] = 0
    try:
        result["pending_sellers"] = (
            db.query(sa_func.count(models.Seller.id))
            .filter(models.Seller.verified_at.is_(None))
            .scalar() or 0
        )
    except Exception:
        result["pending_sellers"] = 0
    try:
        result["pending_settlement"] = (
            db.query(sa_func.count(models.ReservationSettlement.id))
            .filter(models.ReservationSettlement.status.in_(["HOLD", "READY"]))
            .scalar() or 0
        )
    except Exception:
        result["pending_settlement"] = 0
    try:
        result["disputed"] = (
            db.query(sa_func.count(models.Reservation.id))
            .filter(models.Reservation.is_disputed == True)
            .scalar() or 0
        )
    except Exception:
        result["disputed"] = 0
    try:
        status_str = cast(models.Reservation.status, SAString)
        rows = db.query(status_str, sa_func.count(models.Reservation.id)).group_by(status_str).all()
        result["reservation_status"] = {str(r[0]): r[1] for r in rows}
    except Exception:
        result["reservation_status"] = {}
    try:
        sett_q = db.query(models.ReservationSettlement)
        result["settlement_summary"] = {
            "HOLD": sett_q.filter(models.ReservationSettlement.status == "HOLD").count(),
            "READY": sett_q.filter(models.ReservationSettlement.status == "READY").count(),
            "APPROVED": sett_q.filter(models.ReservationSettlement.status == "APPROVED").count(),
            "PAID": sett_q.filter(models.ReservationSettlement.status == "PAID").count(),
        }
    except Exception:
        result["settlement_summary"] = {}
    try:
        status_str = cast(models.Reservation.status, SAString)
        paid_row = (
            db.query(
                sa_func.coalesce(sa_func.sum(models.Reservation.amount_total), 0),
                sa_func.count(models.Reservation.id),
            )
            .filter(status_str.in_(["PAID", "SHIPPED", "ARRIVED", "CONFIRMED"]))
            .first()
        )
        result["gmv"] = int(paid_row[0]) if paid_row else 0
        paid_cnt = int(paid_row[1]) if paid_row else 0
        result["aov"] = round(result["gmv"] / paid_cnt) if paid_cnt > 0 else 0
    except Exception:
        result["gmv"] = 0
        result["aov"] = 0
    return result


# ── GET /admin/deals ─────────────────────────────────────
@router.get("/deals")
def admin_list_deals(
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(models.Deal)
    if keyword:
        q = q.filter(models.Deal.product_name.ilike(f"%{keyword}%"))
    if status:
        q = q.filter(models.Deal.status == status)
    if date_from:
        try:
            q = q.filter(models.Deal.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(models.Deal.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass
    items = q.order_by(models.Deal.id.desc()).limit(limit).all()

    # offer count per deal
    offer_counts: dict[int, int] = {}
    if items:
        deal_ids = [d.id for d in items]
        rows = (
            db.query(models.Offer.deal_id, sa_func.count(models.Offer.id))
            .filter(models.Offer.deal_id.in_(deal_ids))
            .group_by(models.Offer.deal_id)
            .all()
        )
        offer_counts = {r[0]: r[1] for r in rows}

    result = []
    for d in items:
        result.append({
            "id": d.id,
            "product_name": getattr(d, "product_name", ""),
            "creator_id": getattr(d, "creator_id", None),
            "target_price": getattr(d, "target_price", None),
            "market_price": getattr(d, "market_price", None),
            "status": getattr(d, "status", ""),
            "created_at": str(getattr(d, "created_at", "")),
            "offer_count": offer_counts.get(d.id, 0),
        })
    total = db.query(sa_func.count(models.Deal.id)).scalar() or 0
    return {"items": result, "total": total}


# ── GET /admin/offers ────────────────────────────────────
@router.get("/offers")
def admin_list_offers(
    deal_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(models.Offer)
    if deal_id:
        q = q.filter(models.Offer.deal_id == deal_id)
    if seller_id:
        q = q.filter(models.Offer.seller_id == seller_id)
    if status:
        q = q.filter(models.Offer.status == status)

    items = q.order_by(models.Offer.id.desc()).limit(limit).all()

    # join info
    deal_ids = list({o.deal_id for o in items if o.deal_id})
    seller_ids = list({o.seller_id for o in items if o.seller_id})

    deal_map: dict = {}
    if deal_ids:
        for d in db.query(models.Deal).filter(models.Deal.id.in_(deal_ids)).all():
            deal_map[d.id] = getattr(d, "product_name", "")

    seller_map: dict = {}
    if seller_ids:
        for s in db.query(models.Seller).filter(models.Seller.id.in_(seller_ids)).all():
            seller_map[s.id] = getattr(s, "business_name", "")

    result = []
    for o in items:
        result.append({
            "id": o.id,
            "deal_id": o.deal_id,
            "product_name": deal_map.get(o.deal_id, ""),
            "seller_id": o.seller_id,
            "business_name": seller_map.get(o.seller_id, ""),
            "price": getattr(o, "price", None),
            "shipping_fee": getattr(o, "shipping_fee", None),
            "quantity": getattr(o, "quantity", None),
            "status": getattr(o, "status", ""),
            "created_at": str(getattr(o, "created_at", "")),
        })
    total = db.query(sa_func.count(models.Offer.id)).scalar() or 0
    return {"items": result, "total": total}


# ── GET /admin/reservations ──────────────────────────────
@router.get("/reservations")
def admin_list_reservations(
    buyer_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    status: Optional[str] = None,
    is_disputed: Optional[bool] = None,
    shipped: Optional[bool] = None,
    refund: Optional[bool] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(models.Reservation)
    if buyer_id:
        q = q.filter(models.Reservation.buyer_id == buyer_id)
    if seller_id:
        q = q.filter(models.Reservation.seller_id == seller_id)
    if status:
        q = q.filter(models.Reservation.status == status)
    if is_disputed is True:
        q = q.filter(models.Reservation.is_disputed == True)
    if is_disputed is False:
        q = q.filter(models.Reservation.is_disputed == False)
    if shipped is True:
        q = q.filter(models.Reservation.shipped_at.isnot(None))
    if shipped is False:
        q = q.filter(models.Reservation.shipped_at.is_(None))
    if refund is True:
        q = q.filter(models.Reservation.status.in_(["CANCELLED"]))

    items = q.order_by(models.Reservation.id.desc()).limit(limit).all()

    # join maps
    deal_ids = list({getattr(r, "deal_id", None) for r in items if getattr(r, "deal_id", None)})
    offer_ids = list({getattr(r, "offer_id", None) for r in items if getattr(r, "offer_id", None)})
    buyer_ids = list({r.buyer_id for r in items if r.buyer_id})

    deal_map: dict = {}
    if deal_ids:
        for d in db.query(models.Deal).filter(models.Deal.id.in_(deal_ids)).all():
            deal_map[d.id] = getattr(d, "product_name", "")

    # offer → seller_id 매핑
    offer_seller_map: dict = {}
    if offer_ids:
        for o in db.query(models.Offer).filter(models.Offer.id.in_(offer_ids)).all():
            offer_seller_map[o.id] = getattr(o, "seller_id", None)

    seller_ids = list({sid for sid in offer_seller_map.values() if sid})
    buyer_map: dict = {}
    if buyer_ids:
        for b in db.query(models.Buyer).filter(models.Buyer.id.in_(buyer_ids)).all():
            buyer_map[b.id] = getattr(b, "nickname", getattr(b, "email", ""))

    seller_map: dict = {}
    if seller_ids:
        for s in db.query(models.Seller).filter(models.Seller.id.in_(seller_ids)).all():
            seller_map[s.id] = getattr(s, "business_name", "")

    result = []
    for r in items:
        sid = offer_seller_map.get(getattr(r, "offer_id", None))
        result.append({
            "id": r.id,
            "deal_id": getattr(r, "deal_id", None),
            "offer_id": getattr(r, "offer_id", None),
            "product_name": deal_map.get(getattr(r, "deal_id", None), ""),
            "buyer_id": r.buyer_id,
            "buyer_name": buyer_map.get(r.buyer_id, ""),
            "seller_id": sid,
            "seller_name": seller_map.get(sid, "") if sid else "",
            "amount": getattr(r, "amount_total", 0),
            "status": getattr(r.status, "value", str(r.status)) if r.status else "",
            "is_disputed": getattr(r, "is_disputed", False),
            "dispute_reason": getattr(r, "dispute_reason", None),
            "dispute_resolution": getattr(r, "dispute_resolution", None),
            "dispute_opened_at": str(r.dispute_opened_at) if getattr(r, "dispute_opened_at", None) else None,
            "dispute_closed_at": str(r.dispute_closed_at) if getattr(r, "dispute_closed_at", None) else None,
            "shipped_at": str(r.shipped_at) if getattr(r, "shipped_at", None) else None,
            "carrier": getattr(r, "shipping_carrier", None),
            "tracking_number": getattr(r, "tracking_number", None),
            "refund_type": getattr(r, "refund_type", None),
            "refunded_qty": getattr(r, "refunded_qty", 0),
            "refunded_amount_total": getattr(r, "refunded_amount_total", 0),
            "created_at": str(getattr(r, "created_at", "")),
        })
    total = db.query(sa_func.count(models.Reservation.id)).scalar() or 0
    return {"items": result, "total": total}


# ── GET /admin/stats ─────────────────────────────────────
@router.get("/stats")
def admin_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from sqlalchemy import text as sa_text, cast, String as SAString

    dt_from = None
    dt_to = None
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
        except ValueError:
            pass

    # ── reservation stats ──
    total_reservations = 0
    gmv = 0
    refunded = 0
    aov = 0
    status_counts: dict = {}
    try:
        rq = db.query(models.Reservation)
        if dt_from:
            rq = rq.filter(models.Reservation.created_at >= dt_from)
        if dt_to:
            rq = rq.filter(models.Reservation.created_at <= dt_to)
        total_reservations = rq.count()

        # Use cast to string to avoid PostgreSQL enum issues
        status_str = cast(models.Reservation.status, SAString)

        # GMV: sum of amount_total for paid-like statuses
        paid_sum_row = (
            rq.with_entities(
                sa_func.coalesce(sa_func.sum(models.Reservation.amount_total), 0),
                sa_func.count(models.Reservation.id),
            )
            .filter(status_str.in_(["PAID", "SHIPPED", "ARRIVED", "CONFIRMED"]))
            .first()
        )
        gmv = int(paid_sum_row[0]) if paid_sum_row else 0
        paid_count = int(paid_sum_row[1]) if paid_sum_row else 0
        aov = round(gmv / paid_count, 0) if paid_count > 0 else 0

        refunded = rq.filter(status_str.in_(["REFUNDED", "CANCELLED"])).count()
    except Exception:
        pass
    refund_rate = round(refunded / total_reservations * 100, 2) if total_reservations > 0 else 0

    # reservation status summary (cast enum to string for JSON keys)
    try:
        status_str = cast(models.Reservation.status, SAString)
        rows = (
            db.query(status_str, sa_func.count(models.Reservation.id))
            .group_by(status_str)
            .all()
        )
        status_counts = {str(r[0]): r[1] for r in rows}
    except Exception:
        pass

    # ── deal stats ──
    deal_count = 0
    deal_success_rate = 0
    try:
        deal_count = db.query(sa_func.count(models.Deal.id)).scalar() or 0
        completed_deals = db.query(sa_func.count(models.Deal.id)).filter(models.Deal.status == "CLOSED").scalar() or 0
        deal_success_rate = round(completed_deals / deal_count * 100, 2) if deal_count > 0 else 0
    except Exception:
        pass

    # ── settlement summary ──
    settlement_summary: dict = {}
    try:
        sett_q = db.query(models.ReservationSettlement)
        hold = sett_q.filter(models.ReservationSettlement.status == "HOLD").count()
        ready = sett_q.filter(models.ReservationSettlement.status == "READY").count()
        approved = sett_q.filter(models.ReservationSettlement.status == "APPROVED").count()
        paid_s = sett_q.filter(models.ReservationSettlement.status == "PAID").count()
        settlement_summary = {"HOLD": hold, "READY": ready, "APPROVED": approved, "PAID": paid_s}
    except Exception:
        pass

    # ── platform fee / take rate ──
    total_platform_fee = 0
    try:
        fee_sum = db.query(sa_func.sum(models.ReservationSettlement.platform_fee)).scalar()
        total_platform_fee = fee_sum or 0
    except Exception:
        pass
    take_rate = round(total_platform_fee / gmv * 100, 2) if gmv > 0 else 0

    # ── entity counts (dashboard KPI) ──
    buyer_count = 0
    seller_count = 0
    offer_count = 0
    actuator_count = 0
    pending_sellers = 0
    pending_settlement = 0
    disputed_count = 0
    try:
        buyer_count = db.query(sa_func.count(models.Buyer.id)).scalar() or 0
    except Exception:
        pass
    try:
        seller_count = db.query(sa_func.count(models.Seller.id)).scalar() or 0
        pending_sellers = db.query(sa_func.count(models.Seller.id)).filter(models.Seller.verified_at.is_(None)).scalar() or 0
    except Exception:
        pass
    try:
        offer_count = db.query(sa_func.count(models.Offer.id)).scalar() or 0
    except Exception:
        pass
    try:
        actuator_count = db.query(sa_func.count(models.Actuator.id)).scalar() or 0
    except Exception:
        pass
    try:
        pending_settlement = (
            db.query(sa_func.count(models.ReservationSettlement.id))
            .filter(models.ReservationSettlement.status.in_(["HOLD", "READY"]))
            .scalar() or 0
        )
    except Exception:
        pass
    try:
        disputed_count = (
            db.query(sa_func.count(models.Reservation.id))
            .filter(models.Reservation.is_disputed == True)
            .scalar() or 0
        )
    except Exception:
        pass

    return {
        "gmv": gmv,
        "total_reservations": total_reservations,
        "refund_rate": refund_rate,
        "deal_count": deal_count,
        "deal_success_rate": deal_success_rate,
        "aov": aov,
        "take_rate": take_rate,
        "settlement_summary": settlement_summary,
        "reservation_status": status_counts,
        "buyer_count": buyer_count,
        "seller_count": seller_count,
        "offer_count": offer_count,
        "actuator_count": actuator_count,
        "pending_sellers": pending_sellers,
        "pending_settlement": pending_settlement,
        "disputed_count": disputed_count,
    }


# ── GET /admin/notifications/all ─────────────────────────
@router.get("/notifications/all")
def admin_list_notifications(
    user_id: Optional[int] = None,
    type: Optional[str] = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(models.UserNotification)
    if user_id:
        q = q.filter(models.UserNotification.user_id == user_id)
    if type:
        q = q.filter(models.UserNotification.type == type)

    items = q.order_by(models.UserNotification.id.desc()).limit(limit).all()
    result = []
    for n in items:
        result.append({
            "id": n.id,
            "user_id": getattr(n, "user_id", None),
            "type": getattr(n, "type", ""),
            "title": getattr(n, "title", ""),
            "message": getattr(n, "message", ""),
            "is_read": getattr(n, "is_read", False),
            "created_at": str(getattr(n, "created_at", "")),
        })
    total = db.query(sa_func.count(models.UserNotification.id)).scalar() or 0
    return {"items": result, "total": total}


# ── POST /admin/notifications/broadcast ──────────────────
@router.post("/notifications/broadcast")
def admin_broadcast_notification(
    payload: dict,
    db: Session = Depends(get_db),
):
    title = payload.get("title", "")
    message = payload.get("message", "")
    target_role = payload.get("target_role", "all")

    if not title or not message:
        raise HTTPException(status_code=422, detail="title and message required")

    # find target users
    users_q = db.query(models.User)
    if target_role and target_role != "all":
        users_q = users_q.filter(models.User.role == target_role)
    users = users_q.all()

    created = 0
    for u in users:
        notif = models.UserNotification(
            user_id=u.id,
            type="broadcast",
            title=title,
            message=message,
        )
        db.add(notif)
        created += 1

    db.commit()
    return {"sent": created, "target_role": target_role}


# ── POST /admin/refund-simulate ──────────────────────────
@router.post("/refund-simulate")
def refund_simulate(body: dict, db: Session = Depends(get_db)):
    """환불 시뮬레이션: 수동 조건 입력 또는 실제 예약 기반"""
    from app.core.refund_policy import (
        FaultParty, RefundTrigger, CoolingState, SettlementState,
        RefundContext, RefundPolicyEngine,
        is_shipping_refundable_by_policy, decide_shipping_refund_cap,
    )
    from app.policy.api import pg_fee_rate as get_pg_fee_rate, platform_fee_rate_fallback

    mode = body.get("mode", "manual")

    # ── by_reservation: 실제 예약 기반 ──
    if mode == "by_reservation":
        reservation_id = body.get("reservation_id")
        if not reservation_id:
            raise HTTPException(422, "reservation_id 필요")
        resv = db.query(models.Reservation).filter(models.Reservation.id == reservation_id).first()
        if not resv:
            raise HTTPException(404, "예약을 찾을 수 없습니다")
        offer = db.query(models.Offer).filter(models.Offer.id == resv.offer_id).first()
        try:
            from app.crud import preview_refund_for_reservation
            # actor 매핑: fault_party → crud actor 문자열
            fp = body.get("fault_party", "BUYER").upper()
            actor_map = {"BUYER": "buyer_cancel", "SELLER": "seller_fault", "SYSTEM": "system_error", "DISPUTE": "dispute_resolve"}
            actor = actor_map.get(fp, "buyer_cancel")
            result = preview_refund_for_reservation(
                db, reservation_id=resv.id,
                actor=actor,
                quantity_refund=body.get("refund_quantity") or body.get("quantity_refund"),
            )
            return {
                "mode": "by_reservation",
                "reservation_id": reservation_id,
                "result": result if isinstance(result, dict) else str(result),
                "reservation_info": {
                    "offer_id": resv.offer_id,
                    "amount_total": resv.amount_total,
                    "amount_goods": getattr(resv, "amount_goods", 0),
                    "amount_shipping": getattr(resv, "amount_shipping", 0),
                    "qty": resv.qty,
                    "refunded_qty": getattr(resv, "refunded_qty", 0),
                    "status": getattr(resv.status, "value", str(resv.status)) if resv.status else "",
                    "shipped_at": str(resv.shipped_at) if getattr(resv, "shipped_at", None) else None,
                    "arrival_confirmed_at": str(resv.arrival_confirmed_at) if getattr(resv, "arrival_confirmed_at", None) else None,
                },
                "offer_info": {
                    "price": getattr(offer, "price", None),
                    "shipping_fee": getattr(offer, "shipping_fee_standard", getattr(offer, "shipping_fee", None)),
                } if offer else None,
            }
        except Exception as e:
            return {"mode": "by_reservation", "error": str(e)}

    # ── manual: 수동 시뮬레이션 ──
    product_price = int(body.get("product_price", 0))
    shipping_fee = int(body.get("shipping_fee", 0))
    quantity = int(body.get("quantity", 1))
    refund_quantity = int(body.get("refund_quantity", quantity))

    fault_party = FaultParty(body.get("fault_party", "BUYER"))
    trigger = RefundTrigger(body.get("trigger", "BUYER_CANCEL"))
    cooling_state = CoolingState(body.get("cooling_state", "BEFORE_SHIPPING"))
    settlement_state = SettlementState(body.get("settlement_state", "NOT_SETTLED"))

    # 금액 계산
    goods_refund = product_price * refund_quantity
    shipping_auto_max = round(shipping_fee * refund_quantity / quantity) if quantity > 0 else 0

    # 배송비 환불 상한 결정
    shipping_cap = decide_shipping_refund_cap(
        fault_party=fault_party, trigger=trigger,
        cooling_state=cooling_state,
        auto_max_shipping_refund=shipping_auto_max,
    )
    shipping_refund = min(shipping_auto_max, shipping_cap)
    total_refund = goods_refund + shipping_refund

    # 수수료율
    pfr = get_pg_fee_rate()
    plr = platform_fee_rate_fallback()

    # 정책 엔진 실행
    ctx = RefundContext(
        reservation_id=0, deal_id=None, offer_id=None, buyer_id=0, seller_id=None,
        amount_total=total_refund,
        amount_goods=goods_refund,
        amount_shipping=shipping_refund,
        quantity_total=quantity,
        quantity_refund=refund_quantity,
        fault_party=fault_party, trigger=trigger,
        settlement_state=settlement_state, cooling_state=cooling_state,
        pg_fee_rate=pfr, platform_fee_rate=plr,
    )
    engine = RefundPolicyEngine()
    decision = engine.decide_for_paid_reservation(ctx)
    plan = engine.build_financial_plan(ctx, decision)

    # 정산 영향 계산
    total_paid = product_price * quantity + shipping_fee
    seller_payout_original = round(total_paid * (1 - pfr - plr))
    remaining_paid = product_price * (quantity - refund_quantity) + (shipping_fee - shipping_refund)
    seller_payout_after = round(remaining_paid * (1 - pfr - plr))

    return {
        "mode": "manual",
        "input": {
            "product_price": product_price,
            "shipping_fee": shipping_fee,
            "quantity": quantity,
            "refund_quantity": refund_quantity,
            "fault_party": fault_party.value,
            "trigger": trigger.value,
            "cooling_state": cooling_state.value,
            "settlement_state": settlement_state.value,
        },
        "breakdown": {
            "goods_refund": goods_refund,
            "shipping_auto_max": shipping_auto_max,
            "shipping_cap_by_policy": shipping_cap,
            "shipping_refund": shipping_refund,
            "total_refund": total_refund,
        },
        "fees": {
            "pg_fee_rate": pfr,
            "pg_fee_amount": plan.pg_fee_amount,
            "pg_fee_bearer": plan.pg_fee_charge_to.value if plan.pg_fee_charge_to else None,
            "platform_fee_rate": plr,
            "platform_fee_amount": plan.platform_fee_amount,
            "platform_fee_bearer": plan.platform_fee_charge_to.value if plan.platform_fee_charge_to else None,
        },
        "decision": {
            "use_pg_refund": decision.use_pg_refund,
            "need_settlement_recovery": decision.need_settlement_recovery,
            "revoke_buyer_points": decision.revoke_buyer_points,
            "revoke_seller_points": decision.revoke_seller_points,
            "note": decision.note,
        },
        "settlement_impact": {
            "total_paid": total_paid,
            "seller_payout_original": seller_payout_original,
            "seller_payout_after_refund": seller_payout_after,
            "seller_impact": seller_payout_after - seller_payout_original,
        },
        "policy_notes": [
            f"배송 상태: {cooling_state.value}",
            f"귀책: {fault_party.value}",
            f"배송비 환불 {'가능' if shipping_refund > 0 else '불가'} (정책 cap: {shipping_cap}원)",
            f"PG수수료({pfr*100:.1f}%) {plan.pg_fee_charge_to.value if plan.pg_fee_charge_to else '?'} 부담",
            f"플랫폼수수료({plr*100:.1f}%) {plan.platform_fee_charge_to.value if plan.platform_fee_charge_to else '?'} 부담",
            decision.note,
        ],
    }
