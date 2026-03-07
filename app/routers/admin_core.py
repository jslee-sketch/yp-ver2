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
        q = q.filter(models.Reservation.status.in_(["REFUNDED", "CANCELLED"]))

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
            "status": str(getattr(r, "status", "")),
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

    # base queries
    rq = db.query(models.Reservation)
    if dt_from:
        rq = rq.filter(models.Reservation.created_at >= dt_from)
    if dt_to:
        rq = rq.filter(models.Reservation.created_at <= dt_to)

    total_reservations = rq.count()
    paid_reservations = rq.filter(models.Reservation.status.in_(["PAID", "SHIPPED", "ARRIVED", "CONFIRMED"])).all()
    gmv = sum(getattr(r, "amount", 0) or 0 for r in paid_reservations)
    refunded = rq.filter(models.Reservation.status.in_(["REFUNDED", "CANCELLED"])).count()
    refund_rate = round(refunded / total_reservations * 100, 2) if total_reservations > 0 else 0

    deal_count = db.query(sa_func.count(models.Deal.id)).scalar() or 0
    completed_deals = db.query(sa_func.count(models.Deal.id)).filter(models.Deal.status == "CLOSED").scalar() or 0
    deal_success_rate = round(completed_deals / deal_count * 100, 2) if deal_count > 0 else 0
    aov = round(gmv / len(paid_reservations), 0) if paid_reservations else 0

    # settlement summary
    try:
        sett_q = db.query(models.ReservationSettlement)
        hold = sett_q.filter(models.ReservationSettlement.status == "HOLD").count()
        ready = sett_q.filter(models.ReservationSettlement.status == "READY").count()
        approved = sett_q.filter(models.ReservationSettlement.status == "APPROVED").count()
        paid_s = sett_q.filter(models.ReservationSettlement.status == "PAID").count()
        settlement_summary = {"HOLD": hold, "READY": ready, "APPROVED": approved, "PAID": paid_s}
    except Exception:
        settlement_summary = {}

    # reservation status summary
    status_counts = {}
    try:
        rows = db.query(models.Reservation.status, sa_func.count(models.Reservation.id)).group_by(models.Reservation.status).all()
        status_counts = {r[0]: r[1] for r in rows}
    except Exception:
        pass

    # platform_fee (take rate proxy)
    total_platform_fee = 0
    try:
        fee_sum = db.query(sa_func.sum(models.ReservationSettlement.platform_fee)).scalar()
        total_platform_fee = fee_sum or 0
    except Exception:
        pass
    take_rate = round(total_platform_fee / gmv * 100, 2) if gmv > 0 else 0

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
