# app/routers/dashboard.py
from __future__ import annotations
from typing import Dict, Any

from fastapi import APIRouter, Depends, Path
from sqlalchemy import func
from sqlalchemy.orm import Session

from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.logic import trust as T

# (있으면 활용)
try:
    from app.models import (
        Reservation,
        ReservationStatus,
        BuyerDeposit,
        Offer,
        PointTransaction,
        UserNotification,
        DealChatMessage,
        ReservationSettlement,
        Seller,
        ActuatorCommission,
        Actuator,
        Buyer,
    )
except Exception:
    Reservation = None  # type: ignore
    ReservationStatus = None  # type: ignore
    BuyerDeposit = None  # type: ignore
    Offer = None  # type: ignore
    PointTransaction = None  # type: ignore
    UserNotification = None  # type: ignore
    DealChatMessage = None  # type: ignore
    ReservationSettlement = None  # type: ignore
    Seller = None  # type: ignore
    ActuatorCommission = None  # type: ignore
    Actuator = None  # type: ignore
    Buyer = None  # type: ignore

router = APIRouter(prefix="/dashboard", tags=["📈 Dashboards (NO-AUTH)"])




def _safe_int(x) -> int:
    try:
        return int(x or 0)
    except Exception:
        return 0


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc(dt: datetime | None) -> datetime | None:
    """
    DB에서 나온 datetime이 naive/aware 섞여 있을 수 있으니,
    전부 UTC aware로 강제 변환하는 헬퍼.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # naive → UTC 기준으로 붙이기
        return dt.replace(tzinfo=timezone.utc)
    # 이미 타임존 있으면 UTC로 맞추기
    return dt.astimezone(timezone.utc)


#--------------------------------
# Buyers DASHBOARD
#----------------------------------

@router.get("/buyer/{buyer_id}")
def buyer_dashboard(
    buyer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    # ───────────────────────────────
    # 1) 프로필
    # ───────────────────────────────
    profile: Dict[str, Any] = {
        "name": None,
        "email": None,
        "created_at": None,
        "trust_tier": None,
        "level": 6,
    }
    if Buyer is not None:
        b = db.query(Buyer).filter(Buyer.id == buyer_id).first()
        if b:
            profile = {
                "name": getattr(b, "name", None),
                "email": getattr(b, "email", None),
                "created_at": getattr(b, "created_at", None),
                "trust_tier": getattr(b, "trust_tier", None),
                "level": getattr(b, "level", 6),
            }

    # ───────────────────────────────
    # 2) 신뢰/디파짓 퍼센트
    # ───────────────────────────────
    trust = T.buyer_trust_tier_and_deposit_percent(db, buyer_id)

    # ───────────────────────────────
    # 3) 예약/결제 집계 + 배송/환불 + SLA
    # ───────────────────────────────
    total = paid = cancelled = expired = 0
    paid_total_amt = cancelled_total_amt = 0

    shipping_pipeline = {
        "paid_not_shipped": 0,
        "shipped_not_arrived": 0,
        "arrived_confirmed": 0,
    }
    refunds_summary = {
        "cancelled_after_paid_count": 0,
    }
    sla = {
        "expected_delivery_days_avg": None,   # 약속된 배송일 평균 (delivery_days)
        "actual_delivery_days_avg": None,     # 실제 배송일 평균 (shipped→arrival_confirmed)
        "overdue_shipments_count": 0,         # 약속일이 지났는데 아직 배송 안 된 건
        "delayed_deliveries_count": 0,        # 약속일보다 늦게 도착한 건
    }
    recent_reservations = []

    if Reservation and ReservationStatus:
        rq = db.query(Reservation).filter(Reservation.buyer_id == buyer_id)
        total = rq.count()

        paid = (
            db.query(func.count(Reservation.id))
            .filter(Reservation.buyer_id == buyer_id, Reservation.status == ReservationStatus.PAID)
            .scalar()
            or 0
        )
        cancelled = (
            db.query(func.count(Reservation.id))
            .filter(Reservation.buyer_id == buyer_id, Reservation.status == ReservationStatus.CANCELLED)
            .scalar()
            or 0
        )
        expired = (
            db.query(func.count(Reservation.id))
            .filter(Reservation.buyer_id == buyer_id, Reservation.status == ReservationStatus.EXPIRED)
            .scalar()
            or 0
        )

        paid_total_amt = (
            db.query(func.coalesce(func.sum(Reservation.amount_total), 0))
            .filter(Reservation.buyer_id == buyer_id, Reservation.status == ReservationStatus.PAID)
            .scalar()
            or 0
        )
        cancelled_total_amt = (
            db.query(func.coalesce(func.sum(Reservation.amount_total), 0))
            .filter(Reservation.buyer_id == buyer_id, Reservation.status == ReservationStatus.CANCELLED)
            .scalar()
            or 0
        )

        # 배송 파이프라인 (PAID 기준)
        if hasattr(Reservation, "shipped_at") and hasattr(Reservation, "arrival_confirmed_at"):
            shipping_pipeline["paid_not_shipped"] = (
                db.query(func.count(Reservation.id))
                .filter(
                    Reservation.buyer_id == buyer_id,
                    Reservation.status == ReservationStatus.PAID,
                    Reservation.shipped_at.is_(None),
                )
                .scalar()
                or 0
            )
            shipping_pipeline["shipped_not_arrived"] = (
                db.query(func.count(Reservation.id))
                .filter(
                    Reservation.buyer_id == buyer_id,
                    Reservation.status == ReservationStatus.PAID,
                    Reservation.shipped_at.isnot(None),
                    Reservation.arrival_confirmed_at.is_(None),
                )
                .scalar()
                or 0
            )
            shipping_pipeline["arrived_confirmed"] = (
                db.query(func.count(Reservation.id))
                .filter(
                    Reservation.buyer_id == buyer_id,
                    Reservation.status == ReservationStatus.PAID,
                    Reservation.arrival_confirmed_at.isnot(None),
                )
                .scalar()
                or 0
            )

        # 환불성 요약: 결제까지 갔다가 취소된 예약 수
        refunds_summary["cancelled_after_paid_count"] = (
            db.query(func.count(Reservation.id))
            .filter(
                Reservation.buyer_id == buyer_id,
                Reservation.status == ReservationStatus.CANCELLED,
                Reservation.paid_at.isnot(None),
            )
            .scalar()
            or 0
        )

        # SLA 계산은 Python에서 (SQLite 날짜연산 회피)
        if Offer is not None:
            # 최근 N개(예: 200개)만 대상으로 계산
            rows = (
                rq.order_by(Reservation.id.desc())
                .limit(200)
                .all()
            )

            if rows:
                # 미리 offer들을 한 번에 로딩
                offer_ids = {r.offer_id for r in rows}
                offers_map = {
                    o.id: o
                    for o in db.query(Offer)
                    .filter(Offer.id.in_(offer_ids))
                    .all()
                }

                now = _now_utc()
                delivery_days_list: list[float] = []
                actual_days_list: list[float] = []
                overdue_count = 0
                delayed_count = 0

                for r in rows:
                    off = offers_map.get(r.offer_id)
                    if not off or off.delivery_days is None:
                        continue

                    try:
                        d_days = int(off.delivery_days)
                    except Exception:
                        continue

                    # 약속된 배송일 평균용
                    if d_days > 0:
                        delivery_days_list.append(d_days)

                    # overdue: 결제는 됐고 아직 shipped_at 없는데,
                    # paid_at + delivery_days < now
                    paid_at_utc = _to_utc(getattr(r, "paid_at", None))
                    shipped_at_utc = _to_utc(getattr(r, "shipped_at", None))

                    if paid_at_utc is not None and shipped_at_utc is None:
                        expected = paid_at_utc + timedelta(days=d_days)
                        expected_utc = _to_utc(expected)
                        if expected_utc is not None and expected_utc < now:
                            overdue_count += 1

                    # 실제 배송일 계산: shipped_at → arrival_confirmed_at
                    arrival_utc = _to_utc(getattr(r, "arrival_confirmed_at", None))
                    if shipped_at_utc is not None and arrival_utc is not None:
                        delta_days = (arrival_utc - shipped_at_utc).total_seconds() / 86400.0
                        if delta_days >= 0:
                            actual_days_list.append(delta_days)
                            if d_days > 0 and delta_days > d_days:
                                delayed_count += 1

                if delivery_days_list:
                    sla["expected_delivery_days_avg"] = sum(delivery_days_list) / len(delivery_days_list)
                if actual_days_list:
                    sla["actual_delivery_days_avg"] = sum(actual_days_list) / len(actual_days_list)

                sla["overdue_shipments_count"] = overdue_count
                sla["delayed_deliveries_count"] = delayed_count

        # 최근 예약 5개
        recent_reservations = [
            {
                "id": r.id,
                "deal_id": r.deal_id,
                "offer_id": r.offer_id,
                "qty": r.qty,
                "status": r.status.name if hasattr(r.status, "name") else str(r.status),
                "amount_total": getattr(r, "amount_total", 0),
                "created_at": r.created_at,
                "paid_at": getattr(r, "paid_at", None),
                "cancelled_at": getattr(r, "cancelled_at", None),
                "expired_at": getattr(r, "expired_at", None),
                "shipped_at": getattr(r, "shipped_at", None),
                "arrival_confirmed_at": getattr(r, "arrival_confirmed_at", None),
            }
            for r in rq.order_by(Reservation.id.desc()).limit(5).all()
        ]

    # ───────────────────────────────
    # 4) 포인트 집계
    # ───────────────────────────────
    point_stats = {
        "current_points": 0,
        "total_earned": 0,
        "total_used": 0,
        "transactions_count": 0,
    }
    if PointTransaction is not None:
        qpt = db.query(PointTransaction).filter(
            PointTransaction.user_type == "buyer",
            PointTransaction.user_id == buyer_id,
        )
        point_stats["transactions_count"] = qpt.count()

        earned = (
            db.query(func.coalesce(func.sum(PointTransaction.amount), 0))
            .filter(
                PointTransaction.user_type == "buyer",
                PointTransaction.user_id == buyer_id,
                PointTransaction.amount > 0,
            )
            .scalar()
            or 0
        )
        used_sum = (
            db.query(func.coalesce(func.sum(PointTransaction.amount), 0))
            .filter(
                PointTransaction.user_type == "buyer",
                PointTransaction.user_id == buyer_id,
                PointTransaction.amount < 0,
            )
            .scalar()
            or 0
        )
        current = _safe_int(earned) + _safe_int(used_sum)

        point_stats.update(
            current_points=current,
            total_earned=_safe_int(earned),
            total_used=abs(_safe_int(used_sum)),  # UI 용도로 양수
        )

    # ───────────────────────────────
    # 5) 디파짓 집계
    # ───────────────────────────────
    deposits = {
        "active_count": 0,
        "active_amount_total": 0,
        "refunded_count": 0,
        "refunded_amount_total": 0,
    }
    if BuyerDeposit is not None:
        active_q = db.query(BuyerDeposit).filter(
            BuyerDeposit.buyer_id == buyer_id,
            func.upper(BuyerDeposit.status).in_(("HELD", "HOLD", "ACTIVE")),
        )
        refunded_q = db.query(BuyerDeposit).filter(
            BuyerDeposit.buyer_id == buyer_id,
            func.upper(BuyerDeposit.status) == "REFUNDED",
        )

        deposits["active_count"] = active_q.count()
        deposits["active_amount_total"] = (
            db.query(func.coalesce(func.sum(BuyerDeposit.amount), 0))
            .filter(
                BuyerDeposit.buyer_id == buyer_id,
                func.upper(BuyerDeposit.status).in_(("HELD", "HOLD", "ACTIVE")),
            )
            .scalar()
            or 0
        )
        deposits["refunded_count"] = refunded_q.count()
        deposits["refunded_amount_total"] = (
            db.query(func.coalesce(func.sum(BuyerDeposit.amount), 0))
            .filter(
                BuyerDeposit.buyer_id == buyer_id,
                func.upper(BuyerDeposit.status) == "REFUNDED",
            )
            .scalar()
            or 0
        )

    # ───────────────────────────────
    # 6) 알림 / 채팅
    # ───────────────────────────────
    notif = {"total": 0, "unread": 0}
    if UserNotification is not None:
        notif["total"] = (
            db.query(func.count(UserNotification.id))
            .filter(UserNotification.user_id == buyer_id)
            .scalar()
            or 0
        )
        notif["unread"] = (
            db.query(func.count(UserNotification.id))
            .filter(
                UserNotification.user_id == buyer_id,
                func.coalesce(UserNotification.is_read, 0) == 0,
            )
            .scalar()
            or 0
        )

    chat = {"messages_count": 0}
    if DealChatMessage is not None:
        chat["messages_count"] = (
            db.query(func.count(DealChatMessage.id))
            .filter(DealChatMessage.buyer_id == buyer_id)
            .scalar()
            or 0
        )

    # ───────────────────────────────
    # 최종 응답
    # ───────────────────────────────
    return {
        "buyer_id": buyer_id,
        "profile": profile,
        "trust": {
            "tier": trust["tier"],
            "deposit_percent": trust["deposit_percent"],
            "restricted": trust.get("restricted", False),
            "fulfillment_rate": trust.get("fulfillment_rate", 0.0),
            "participations": _safe_int(trust.get("total", 0)),
            "fulfilled": _safe_int(trust.get("paid", 0)),
        },
        "stats": {
            "deals": {"participated": _safe_int(trust.get("total", 0))},
            "reservations": {
                "total": total,
                "by_status": {
                    "PENDING": total - paid - cancelled - expired,
                    "PAID": paid,
                    "CANCELLED": cancelled,
                    "EXPIRED": expired,
                },
                "amounts": {
                    "paid_total": _safe_int(paid_total_amt),
                    "cancelled_total": _safe_int(cancelled_total_amt),
                },
                "shipping_pipeline": shipping_pipeline,
                "refunds": refunds_summary,
                "sla": sla,
            },
            "points": point_stats,
            "deposits": deposits,
            "notifications": notif,
            "chat": chat,
        },
        "recent": {"reservations": recent_reservations},
    }

# =========================================
# SELLER DASHBOARD
# =========================================
@router.get("/seller/{seller_id}")
def seller_dashboard(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    # ───────────────────────────────
    # 1) 프로필
    # ───────────────────────────────
    profile = {
        "business_name": None,
        "email": None,
        "level": "Lv.6",
        "points": 0,
        "created_at": None,
    }
    if Seller is not None:
        s = db.query(Seller).filter(Seller.id == seller_id).first()
        if s:
            profile = {
                "business_name": getattr(s, "business_name", None),
                "email": getattr(s, "email", None),
                "level": f"Lv.{getattr(s, 'level', 6)}",
                "points": getattr(s, "points", 0),
                "created_at": getattr(s, "created_at", None),
            }

    # ───────────────────────────────
    # 2) 레벨/수수료
    # ───────────────────────────────
    level = T.seller_level_and_fee(db, seller_id, rating_adjusted=None)

    # ───────────────────────────────
    # 3) 오퍼 집계 + 최근 오퍼
    # ───────────────────────────────
    offers_total = active_offers = confirmed_offers = inactive_offers = 0
    sold_qty_sum = reserved_qty_sum = 0
    recent_offers = []

    if Offer is not None:
        oq = db.query(Offer).filter(Offer.seller_id == seller_id)
        offers_total = oq.count()
        active_offers = (
            db.query(func.count(Offer.id))
            .filter(Offer.seller_id == seller_id, Offer.is_active.is_(True))
            .scalar()
            or 0
        )
        confirmed_offers = (
            db.query(func.count(Offer.id))
            .filter(Offer.seller_id == seller_id, Offer.is_confirmed.is_(True))
            .scalar()
            or 0
        )
        inactive_offers = offers_total - active_offers

        sold_qty_sum = (
            db.query(func.coalesce(func.sum(Offer.sold_qty), 0))
            .filter(Offer.seller_id == seller_id)
            .scalar()
            or 0
        )
        reserved_qty_sum = (
            db.query(func.coalesce(func.sum(Offer.reserved_qty), 0))
            .filter(Offer.seller_id == seller_id)
            .scalar()
            or 0
        )

        recent_offers = [
            {
                "id": o.id,
                "deal_id": o.deal_id,
                "price": o.price,
                "total_available_qty": o.total_available_qty,
                "sold_qty": o.sold_qty,
                "reserved_qty": o.reserved_qty,
                "is_active": o.is_active,
                "is_confirmed": o.is_confirmed,
                "gmv_estimated": _safe_int((o.price or 0) * (o.sold_qty or 0)),
                "created_at": o.created_at,
                "deadline_at": o.deadline_at,
            }
            for o in oq.order_by(Offer.id.desc()).limit(5).all()
        ]

    # ───────────────────────────────
    # 4) 예약/금액 + 배송/환불 + SLA (셀러 관점)
    # ───────────────────────────────
    reservations_total = 0
    by_status = {"PENDING": 0, "PAID": 0, "CANCELLED": 0, "EXPIRED": 0}
    paid_total_amt = cancelled_total_amt = 0

    shipping_pipeline = {
        "paid_not_shipped": 0,
        "shipped_not_arrived": 0,
        "arrived_confirmed": 0,
    }
    refunds_summary = {"cancelled_after_paid_count": 0}
    sla = {
        "expected_delivery_days_avg": None,
        "actual_delivery_days_avg": None,
        "overdue_shipments_count": 0,
        "delayed_deliveries_count": 0,
    }
    recent_reservations = []

    if Reservation and ReservationStatus and Offer is not None:
        rq = (
            db.query(Reservation)
            .join(Offer, Offer.id == Reservation.offer_id)
            .filter(Offer.seller_id == seller_id)
        )
        reservations_total = rq.count()

        by_status["PENDING"] = (
            db.query(func.count(Reservation.id))
            .join(Offer, Offer.id == Reservation.offer_id)
            .filter(Offer.seller_id == seller_id, Reservation.status == ReservationStatus.PENDING)
            .scalar()
            or 0
        )
        by_status["PAID"] = (
            db.query(func.count(Reservation.id))
            .join(Offer, Offer.id == Reservation.offer_id)
            .filter(Offer.seller_id == seller_id, Reservation.status == ReservationStatus.PAID)
            .scalar()
            or 0
        )
        by_status["CANCELLED"] = (
            db.query(func.count(Reservation.id))
            .join(Offer, Offer.id == Reservation.offer_id)
            .filter(Offer.seller_id == seller_id, Reservation.status == ReservationStatus.CANCELLED)
            .scalar()
            or 0
        )
        by_status["EXPIRED"] = (
            db.query(func.count(Reservation.id))
            .join(Offer, Offer.id == Reservation.offer_id)
            .filter(Offer.seller_id == seller_id, Reservation.status == ReservationStatus.EXPIRED)
            .scalar()
            or 0
        )

        paid_total_amt = (
            db.query(func.coalesce(func.sum(Reservation.amount_total), 0))
            .join(Offer, Offer.id == Reservation.offer_id)
            .filter(Offer.seller_id == seller_id, Reservation.status == ReservationStatus.PAID)
            .scalar()
            or 0
        )
        cancelled_total_amt = (
            db.query(func.coalesce(func.sum(Reservation.amount_total), 0))
            .join(Offer, Offer.id == Reservation.offer_id)
            .filter(Offer.seller_id == seller_id, Reservation.status == ReservationStatus.CANCELLED)
            .scalar()
            or 0
        )

        # 배송 파이프라인
        if hasattr(Reservation, "shipped_at") and hasattr(Reservation, "arrival_confirmed_at"):
            shipping_pipeline["paid_not_shipped"] = (
                db.query(func.count(Reservation.id))
                .join(Offer, Offer.id == Reservation.offer_id)
                .filter(
                    Offer.seller_id == seller_id,
                    Reservation.status == ReservationStatus.PAID,
                    Reservation.shipped_at.is_(None),
                )
                .scalar()
                or 0
            )
            shipping_pipeline["shipped_not_arrived"] = (
                db.query(func.count(Reservation.id))
                .join(Offer, Offer.id == Reservation.offer_id)
                .filter(
                    Offer.seller_id == seller_id,
                    Reservation.status == ReservationStatus.PAID,
                    Reservation.shipped_at.isnot(None),
                    Reservation.arrival_confirmed_at.is_(None),
                )
                .scalar()
                or 0
            )
            shipping_pipeline["arrived_confirmed"] = (
                db.query(func.count(Reservation.id))
                .join(Offer, Offer.id == Reservation.offer_id)
                .filter(
                    Offer.seller_id == seller_id,
                    Reservation.status == ReservationStatus.PAID,
                    Reservation.arrival_confirmed_at.isnot(None),
                )
                .scalar()
                or 0
            )

        # 환불성 요약
        refunds_summary["cancelled_after_paid_count"] = (
            db.query(func.count(Reservation.id))
            .join(Offer, Offer.id == Reservation.offer_id)
            .filter(
                Offer.seller_id == seller_id,
                Reservation.status == ReservationStatus.CANCELLED,
                Reservation.paid_at.isnot(None),
            )
            .scalar()
            or 0
        )

        # SLA: Python 계산 (타임존 안전 버전)
        rows = (
            rq.order_by(Reservation.id.desc())
            .limit(200)
            .all()
        )
        if rows:
            offer_ids = {r.offer_id for r in rows}
            offers_map = {
                o.id: o
                for o in db.query(Offer)
                .filter(Offer.id.in_(offer_ids))
                .all()
            }

            now = _now_utc()
            delivery_days_list: list[float] = []
            actual_days_list: list[float] = []
            overdue_count = 0
            delayed_count = 0

            for r in rows:
                off = offers_map.get(r.offer_id)
                if not off or off.delivery_days is None:
                    continue

                try:
                    d_days = int(off.delivery_days)
                except Exception:
                    continue

                if d_days > 0:
                    delivery_days_list.append(d_days)

                paid_at_utc = _to_utc(getattr(r, "paid_at", None))
                shipped_at_utc = _to_utc(getattr(r, "shipped_at", None))

                # overdue: 결제는 됐고 아직 shipped_at 없는데,
                # paid_at + delivery_days < now
                if paid_at_utc is not None and shipped_at_utc is None:
                    expected = paid_at_utc + timedelta(days=d_days)
                    expected_utc = _to_utc(expected)
                    if expected_utc is not None and expected_utc < now:
                        overdue_count += 1

                # 실제 배송일 계산: shipped_at → arrival_confirmed_at
                arrival_utc = _to_utc(getattr(r, "arrival_confirmed_at", None))
                if shipped_at_utc is not None and arrival_utc is not None:
                    delta_days = (arrival_utc - shipped_at_utc).total_seconds() / 86400.0
                    if delta_days >= 0:
                        actual_days_list.append(delta_days)
                        if d_days > 0 and delta_days > d_days:
                            delayed_count += 1

            if delivery_days_list:
                sla["expected_delivery_days_avg"] = sum(delivery_days_list) / len(delivery_days_list)
            if actual_days_list:
                sla["actual_delivery_days_avg"] = sum(actual_days_list) / len(actual_days_list)

            sla["overdue_shipments_count"] = overdue_count
            sla["delayed_deliveries_count"] = delayed_count

        # 최근 예약 5개
        recent_reservations = [
            {
                "id": r.id,
                "deal_id": r.deal_id,
                "offer_id": r.offer_id,
                "buyer_id": r.buyer_id,
                "qty": r.qty,
                "status": r.status.name if hasattr(r.status, "name") else str(r.status),
                "amount_total": getattr(r, "amount_total", 0),
                "created_at": r.created_at,
                "paid_at": getattr(r, "paid_at", None),
                "cancelled_at": getattr(r, "cancelled_at", None),
                "shipped_at": getattr(r, "shipped_at", None),
                "arrival_confirmed_at": getattr(r, "arrival_confirmed_at", None),
            }
            for r in rq.order_by(Reservation.id.desc()).limit(5).all()
        ]

    # ───────────────────────────────
    # 5) 정산 요약
    # ───────────────────────────────
    settlement = {
        "settlements_count": 0,
        "buyer_paid_total": 0,
        "seller_payout_total": 0,
        "pg_fee_total": 0,
        "platform_commission_total": 0,
    }
    if ReservationSettlement is not None:
        sq = db.query(ReservationSettlement).filter(
            ReservationSettlement.seller_id == seller_id
        )
        settlement["settlements_count"] = sq.count()
        settlement["buyer_paid_total"] = (
            db.query(func.coalesce(func.sum(ReservationSettlement.buyer_paid_amount), 0))
            .filter(ReservationSettlement.seller_id == seller_id)
            .scalar()
            or 0
        )
        settlement["seller_payout_total"] = (
            db.query(func.coalesce(func.sum(ReservationSettlement.seller_payout_amount), 0))
            .filter(ReservationSettlement.seller_id == seller_id)
            .scalar()
            or 0
        )
        settlement["pg_fee_total"] = (
            db.query(func.coalesce(func.sum(ReservationSettlement.pg_fee_amount), 0))
            .filter(ReservationSettlement.seller_id == seller_id)
            .scalar()
            or 0
        )
        settlement["platform_commission_total"] = (
            db.query(func.coalesce(func.sum(ReservationSettlement.platform_commission_amount), 0))
            .filter(ReservationSettlement.seller_id == seller_id)
            .scalar()
            or 0
        )

    # ───────────────────────────────
    # 6) 포인트 요약
    # ───────────────────────────────
    point_stats = {
        "current_points": 0,
        "total_earned": 0,
        "total_used": 0,
    }
    if PointTransaction is not None:
        earned = (
            db.query(func.coalesce(func.sum(PointTransaction.amount), 0))
            .filter(
                PointTransaction.user_type == "seller",
                PointTransaction.user_id == seller_id,
                PointTransaction.amount > 0,
            )
            .scalar()
            or 0
        )
        used_sum = (
            db.query(func.coalesce(func.sum(PointTransaction.amount), 0))
            .filter(
                PointTransaction.user_type == "seller",
                PointTransaction.user_id == seller_id,
                PointTransaction.amount < 0,
            )
            .scalar()
            or 0
        )
        point_stats.update(
            total_earned=_safe_int(earned),
            total_used=abs(_safe_int(used_sum)),
            current_points=_safe_int(earned) + _safe_int(used_sum),
        )

    # ───────────────────────────────
    # 7) 액츄에이터 연결/커미션 요약
    # ───────────────────────────────
    relations = {}
    if Seller is not None and Actuator is not None:
        s = db.query(Seller).filter(Seller.id == seller_id).first()
        aid = getattr(s, "actuator_id", None) if s else None
        if aid:
            a = db.query(Actuator).filter(Actuator.id == aid).first()
            com_sum = {"total_commissions": 0, "total_amount": 0}
            if ActuatorCommission is not None:
                com_sum["total_commissions"] = (
                    db.query(func.count(ActuatorCommission.id))
                    .filter(
                        ActuatorCommission.actuator_id == aid,
                        ActuatorCommission.seller_id == seller_id,
                    )
                    .scalar()
                    or 0
                )
                com_sum["total_amount"] = (
                    db.query(func.coalesce(func.sum(ActuatorCommission.amount), 0))
                    .filter(
                        ActuatorCommission.actuator_id == aid,
                        ActuatorCommission.seller_id == seller_id,
                    )
                    .scalar()
                    or 0
                )
            relations = {
                "actuator": {
                    "id": getattr(a, "id", aid),
                    "name": getattr(a, "name", None),
                    "email": getattr(a, "email", None),
                    "status": getattr(a, "status", None),
                    "commission_summary": com_sum,
                }
            }

    # ───────────────────────────────
    # 8) 알림
    # ───────────────────────────────
    notif = {"total": 0, "unread": 0}
    if UserNotification is not None:
        notif["total"] = (
            db.query(func.count(UserNotification.id))
            .filter(UserNotification.user_id == seller_id)
            .scalar()
            or 0
        )
        notif["unread"] = (
            db.query(func.count(UserNotification.id))
            .filter(
                UserNotification.user_id == seller_id,
                func.coalesce(UserNotification.is_read, 0) == 0,
            )
            .scalar()
            or 0
        )

    # ───────────────────────────────
    # 최종 응답
    # ───────────────────────────────
    return {
        "seller_id": seller_id,
        "profile": profile,
        "pricing": {
            "fee_percent": level["fee_percent"],
            "sold_count_for_level": level["sold_count"],
            "rating_assumed": level["rating"],
        },
        "stats": {
            "offers": {
                "total_offers": offers_total,
                "active_offers": active_offers,
                "confirmed_offers": confirmed_offers,
                "inactive_offers": inactive_offers,
                "sold_qty_sum": sold_qty_sum,
                "reserved_qty_sum": reserved_qty_sum,
            },
            "reservations": {
                "total_reservations": reservations_total or 0,
                "by_status": by_status,
                "amounts": {
                    "paid_total": _safe_int(paid_total_amt),
                    "cancelled_total": _safe_int(cancelled_total_amt),
                },
                "shipping_pipeline": shipping_pipeline,
                "refunds": refunds_summary,
                "sla": sla,
            },
            "settlement": settlement,
            "points": point_stats,
            "reviews": {
                # 리뷰 집계 테이블 붙으면 여기 채우면 됨
                "reviews_count": 0,
                "rating_raw_mean": None,
                "rating_adjusted": None,
                "dimension_avg": {},
            },
            "notifications": notif,
        },
        "relations": relations,
        "recent": {
            "offers": recent_offers,
            "reservations": recent_reservations,
        },
    }