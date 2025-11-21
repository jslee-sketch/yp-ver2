# app/crud.py
from __future__ import annotations

from typing import List, Optional
from datetime import datetime, timezone

from sqlalchemy import select, and_, func, case
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.exc import IntegrityError
from passlib.hash import bcrypt

# 내부 모듈
from app import models, schemas
from app.config.feature_flags import FEATURE_FLAGS
from app.config import project_rules as R

# 모델 단축 import
from app.models import (
    Deal,
    DealParticipant,
    DealRound,
    DealRoundStatus,
    Offer,
    Reservation,
    ReservationStatus,
    PointTransaction,
)

# ---------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------
class NotFoundError(Exception):
    pass

class ConflictError(Exception):
    pass

# (디파짓 전용 예외)
class DepositConflict(ConflictError):
    pass

# ---------------------------------------------------------------------
# 공용 유틸
# ---------------------------------------------------------------------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def _require_deal(db: Session, deal_id: int) -> Deal:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise NotFoundError(f"Deal not found: {deal_id}")
    return deal

# DeadTime-aware 윈도우 예시(안전 디폴트)
def compute_payment_windows(offer_deadline_at: datetime) -> tuple[datetime, datetime, datetime]:
    payment_open_at   = R.apply_deadtime_pause(offer_deadline_at, minutes=0)
    buyer_window_h    = float(R.TIMELINE.get("BUYER_PAYMENT_WINDOW", 0))  # 기본 0h
    seller_dec_min_h  = float(R.TIMELINE.get("SELLER_DECISION_WINDOW", 0.5))  # 기본 0.5h = 30m
    payment_close_at  = R.apply_deadtime_pause(payment_open_at, hours=buyer_window_h)
    decision_deadline = R.apply_deadtime_pause(payment_close_at, hours=seller_dec_min_h)
    return payment_open_at, payment_close_at, decision_deadline

# idempotent 포인트 적립/차감
def _add_points(
    db: Session,
    *,
    user_type: str,
    user_id: int,
    amount: int,
    reason: str,
    idempotency_key: str | None = None
) -> None:
    if idempotency_key:
        exists = db.query(PointTransaction.id).filter(PointTransaction.idempotency_key == idempotency_key).first()
        if exists:
            return
    tx = PointTransaction(
        user_type=user_type,
        user_id=user_id,
        amount=amount,
        reason=reason,
        created_at=_utcnow(),
        idempotency_key=idempotency_key,
    )
    db.add(tx)

# =========================================================
# 👥 Buyer
# =========================================================
def create_buyer(db: Session, buyer: schemas.BuyerCreate):
    hashed_pw = bcrypt.hash(buyer.password[:72])
    db_buyer = models.Buyer(
        email=buyer.email,
        password_hash=hashed_pw,
        name=buyer.name,
        phone=buyer.phone,
        address=buyer.address,
        zip_code=buyer.zip_code,
        gender=buyer.gender,
        birth_date=buyer.birth_date,
        created_at=_utcnow(),
    )
    db.add(db_buyer)
    db.commit()
    db.refresh(db_buyer)
    return db_buyer

def get_buyers(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Buyer).offset(skip).limit(limit).all()

# =========================================================
# 🏢 Seller
# =========================================================
def create_seller(db: Session, seller: schemas.SellerCreate):
    hashed_pw = bcrypt.hash(seller.password[:72])
    db_seller = models.Seller(
        email=seller.email,
        password_hash=seller.password and hashed_pw,
        business_name=seller.business_name,
        business_number=seller.business_number,
        phone=seller.phone,
        company_phone=seller.company_phone,
        address=seller.address,
        zip_code=seller.zip_code,
        established_date=seller.established_date,
        created_at=_utcnow(),
    )
    if FEATURE_FLAGS.get("AUTO_VERIFY_SELLER"):
        db_seller.verified_at = _utcnow()

    db.add(db_seller)
    db.commit()
    db.refresh(db_seller)
    return db_seller

def get_sellers(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Seller).offset(skip).limit(limit).all()

# =========================================================
# 📦 Deal
# =========================================================
def create_deal(db: Session, deal: schemas.DealCreate):
    db_deal = models.Deal(
        product_name=deal.product_name,
        creator_id=deal.creator_id,
        desired_qty=deal.desired_qty,
        target_price=deal.target_price,
        max_budget=deal.max_budget,
        free_text=deal.free_text,
        created_at=_utcnow(),
    )
    if FEATURE_FLAGS.get("AUTO_SET_DEADLINES"):
        hours = float(R.TIMELINE.get("DEAL_CREATION_WINDOW", 0))
        db_deal.deadline_at = R.apply_deadtime_pause(db_deal.created_at, hours=hours)

    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)

    # 방장 자동 참여
    db_participant = models.DealParticipant(
        deal_id=db_deal.id,
        buyer_id=deal.creator_id,
        qty=deal.desired_qty,
        created_at=_utcnow(),
    )
    db.add(db_participant)
    db.commit()
    return db_deal

def get_deal(db: Session, deal_id: int):
    deal = db.query(models.Deal).filter(models.Deal.id == deal_id).first()
    if not deal:
        return None

    total_qty_from_participants = (
        db.query(func.coalesce(func.sum(models.DealParticipant.qty), 0))
          .filter(models.DealParticipant.deal_id == deal.id)
          .scalar()
    )
    total_qty = (deal.desired_qty or 0) + (total_qty_from_participants or 0)

    return schemas.DealDetail(
        id=deal.id,
        product_name=deal.product_name,
        creator_id=deal.creator_id,
        desired_qty=deal.desired_qty,
        created_at=deal.created_at,
        current_total_qty=total_qty or 0,
    )

def get_deals(db: Session, skip: int = 0, limit: int = 10):
    deals = db.query(models.Deal).offset(skip).limit(limit).all()
    result = []
    for d in deals:
        total_qty = (
            db.query(func.coalesce(func.sum(models.DealParticipant.qty), 0))
              .filter(models.DealParticipant.deal_id == d.id)
              .scalar()
        )
        result.append(
            schemas.DealDetail(
                id=d.id,
                product_name=d.product_name,
                creator_id=d.creator_id,
                desired_qty=d.desired_qty,
                created_at=d.created_at,
                current_total_qty=total_qty or 0,
            )
        )
    return result

# =========================================================
# 🙋 Deal Participants
# =========================================================
def add_participant(db: Session, participant: schemas.DealParticipantCreate):
    existing = (
        db.query(models.DealParticipant)
          .filter_by(deal_id=participant.deal_id, buyer_id=participant.buyer_id)
          .first()
    )
    if existing:
        raise ConflictError("이미 참여한 Buyer입니다.")

    db_participant = models.DealParticipant(
        deal_id=participant.deal_id,
        buyer_id=participant.buyer_id,
        qty=participant.qty,
        created_at=_utcnow(),
    )
    db.add(db_participant)
    db.commit()
    db.refresh(db_participant)
    return db_participant

def get_deal_participants(db: Session, deal_id: int):
    return db.query(models.DealParticipant).filter(models.DealParticipant.deal_id == deal_id).all()

def remove_participant(db: Session, participant_id: int):
    db_participant = db.query(models.DealParticipant).filter(models.DealParticipant.id == participant_id).first()
    if not db_participant:
        return None
    buyer_id = db_participant.buyer_id
    db.delete(db_participant)
    db.commit()
    return {"message": "참여 취소 완료", "buyer_id": buyer_id}

# =========================================================
# 💰 Offers
# =========================================================
def create_offer(db: Session, offer: schemas.OfferCreate):
    db_deal = db.query(models.Deal).filter(models.Deal.id == offer.deal_id).first()
    if not db_deal:
        raise NotFoundError("Deal not found")

    db_offer = models.Offer(
        deal_id=offer.deal_id,
        seller_id=offer.seller_id,
        price=offer.price,
        total_available_qty=offer.total_available_qty,
        delivery_days=getattr(offer, "delivery_days", None),
        comment=getattr(offer, "comment", None) or getattr(offer, "free_text", None),
        created_at=_utcnow(),
    )
    if FEATURE_FLAGS.get("AUTO_SET_DEADLINES"):
        hours = float(R.TIMELINE.get("OFFER_EDITABLE_WINDOW", 0))
        db_offer.deadline_at = R.apply_deadtime_pause(db_offer.created_at, hours=hours)

    db.add(db_offer)
    db.commit()
    db.refresh(db_offer)
    return db_offer

def get_offers(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Offer).offset(skip).limit(limit).all()

# (하위호환)
def confirm_offer_and_reward(db: Session, offer_id: int):
    return confirm_offer_if_soldout(db, offer_id=offer_id, seller_point_on_confirm=30)

# =========================================================
# 💎 Points
# =========================================================
def create_point_transaction(db: Session, transaction: schemas.PointTransactionCreate):
    db_tx = PointTransaction(
        user_type=transaction.user_type,
        user_id=transaction.user_id,
        amount=transaction.amount,
        reason=transaction.reason,
        created_at=_utcnow(),
    )
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx

def get_point_transactions(db: Session, user_type: str, user_id: int):
    return (
        db.query(PointTransaction)
          .filter(PointTransaction.user_type == user_type,
                  PointTransaction.user_id == user_id)
          .order_by(PointTransaction.created_at.desc())
          .all()
    )

def get_user_balance(db: Session, user_type: str, user_id: int):
    total = (
        db.query(func.coalesce(func.sum(PointTransaction.amount), 0))
          .filter(PointTransaction.user_type == user_type,
                  PointTransaction.user_id == user_id)
          .scalar()
    )
    return total or 0

def reward_buyer_payment(db: Session, buyer_id: int):
    return create_point_transaction(
        db,
        schemas.PointTransactionCreate(
            user_type="buyer", user_id=buyer_id, amount=R.BUYER_POINT_ON_PAID, reason="결제 완료 보상"
        ),
    )

def penalize_buyer_cancel(db: Session, buyer_id: int):
    return create_point_transaction(
        db,
        schemas.PointTransactionCreate(
            user_type="buyer", user_id=buyer_id, amount=R.BUYER_POINT_ON_REFUND, reason="결제 취소 차감"
        ),
    )

def reward_seller_success(db: Session, seller_id: int):
    return create_point_transaction(
        db,
        schemas.PointTransactionCreate(
            user_type="seller", user_id=seller_id, amount=30, reason="거래 성사 보상"
        ),
    )

def penalize_seller_cancel_offer(db: Session, seller_id: int):
    return create_point_transaction(
        db,
        schemas.PointTransactionCreate(
            user_type="seller", user_id=seller_id, amount=-30, reason="오퍼 취소 차감"
        ),
    )

# =========================================================
# 🔁 DealRound
# =========================================================
def get_round_by_no(db: Session, deal_id: int, round_no: int) -> DealRound:
    q = (
        select(DealRound)
        .options(selectinload(DealRound.deal))
        .where(and_(DealRound.deal_id == deal_id, DealRound.round_no == round_no))
    )
    row = db.execute(q).scalar_one_or_none()
    if not row:
        raise NotFoundError(f"DealRound not found: deal_id={deal_id}, round_no={round_no}")
    return row

def list_rounds(db: Session, deal_id: int) -> List[DealRound]:
    q = select(DealRound).where(DealRound.deal_id == deal_id).order_by(DealRound.round_no.asc())
    return list(db.execute(q).scalars())

def get_active_round(db: Session, deal_id: int) -> Optional[DealRound]:
    q = select(DealRound).where(and_(DealRound.deal_id == deal_id, DealRound.status == DealRoundStatus.OPEN)).limit(1)
    return db.execute(q).scalar_one_or_none()

def create_deal_round(db: Session, deal_id: int, round_no: int, meta: Optional[dict] = None) -> DealRound:
    _require_deal(db, deal_id)
    obj = DealRound(deal_id=deal_id, round_no=round_no, status=DealRoundStatus.PLANNED, meta=meta or {})
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError(f"Round already exists: deal_id={deal_id}, round_no={round_no}") from e
    db.refresh(obj)
    return obj

def get_or_create_next_round(db: Session, deal_id: int, meta: Optional[dict] = None) -> DealRound:
    next_no = (db.execute(select(func.coalesce(func.max(DealRound.round_no), 0)).where(DealRound.deal_id == deal_id)).scalar_one() or 0) + 1
    return create_deal_round(db, deal_id, next_no, meta=meta)

def open_round(db: Session, deal_id: int, round_no: Optional[int] = None) -> DealRound:
    existing = get_active_round(db, deal_id)
    if existing:
        raise ConflictError(f"Another round already OPEN: round_no={existing.round_no}")

    if round_no is None:
        r = get_or_create_next_round(db, deal_id)
    else:
        try:
            r = get_round_by_no(db, deal_id, round_no)
        except NotFoundError:
            r = create_deal_round(db, deal_id, round_no)

        if r.status != DealRoundStatus.PLANNED:
            raise ConflictError(f"Only PLANNED round can be opened (current={r.status}). Create a new round instead.")

    r.status = DealRoundStatus.OPEN
    r.started_at = _utcnow()
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def finalize_round(db: Session, deal_id: int, round_no: Optional[int] = None) -> DealRound:
    r = get_round_by_no(db, deal_id, round_no) if round_no is not None else get_active_round(db, deal_id)
    if not r:
        raise NotFoundError("No OPEN round to finalize" if round_no is None else f"Round not found: {round_no}")
    if r.status != DealRoundStatus.OPEN:
        raise ConflictError(f"Round must be OPEN to finalize. current={r.status}")

    r.status = DealRoundStatus.FINALIZING
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def _get_latest_finalizing_round(db: Session, deal_id: int) -> Optional[DealRound]:
    q = (
        select(DealRound)
        .where(and_(DealRound.deal_id == deal_id, DealRound.status == DealRoundStatus.FINALIZING))
        .order_by(DealRound.round_no.desc())
        .limit(1)
    )
    return db.execute(q).scalar_one_or_none()

def close_round(db: Session, deal_id: int, round_no: Optional[int] = None) -> DealRound:
    r = get_round_by_no(db, deal_id, round_no) if round_no is not None else (get_active_round(db, deal_id) or _get_latest_finalizing_round(db, deal_id))
    if not r:
        raise NotFoundError("No OPEN or FINALIZING round to close")
    if r.status not in (DealRoundStatus.OPEN, DealRoundStatus.FINALIZING):
        raise ConflictError(f"Round must be OPEN or FINALIZING to close. current={r.status}")

    r.status = DealRoundStatus.CLOSED
    r.ended_at = _utcnow()
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def cancel_round(db: Session, deal_id: int, round_no: int) -> DealRound:
    r = get_round_by_no(db, deal_id, round_no)
    if r.status == DealRoundStatus.CLOSED:
        raise ConflictError("Closed round cannot be cancelled")

    r.status = DealRoundStatus.CANCELLED
    r.ended_at = _utcnow()
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

class RoundAction(str):
    OPEN = "OPEN"
    FINALIZE = "FINALIZE"
    CLOSE = "CLOSE"
    CANCEL = "CANCEL"

def progress_round(db: Session, deal_id: int, action: str, round_no: Optional[int] = None) -> DealRound:
    action = action.upper()
    if action == RoundAction.OPEN:
        return open_round(db, deal_id, round_no=round_no)
    if action == RoundAction.FINALIZE:
        return finalize_round(db, deal_id, round_no=round_no)
    if action == RoundAction.CLOSE:
        return close_round(db, deal_id, round_no=round_no)
    if action == RoundAction.CANCEL:
        if round_no is None:
            raise ConflictError("cancel requires explicit round_no")
        return cancel_round(db, deal_id, round_no)
    raise ConflictError(f"Unknown action: {action}")

def assert_no_open_round(db: Session, deal_id: int) -> None:
    if get_active_round(db, deal_id):
        raise ConflictError("OPEN round already exists")

def ensure_round_exists(db: Session, deal_id: int, round_no: int) -> DealRound:
    try:
        return get_round_by_no(db, deal_id, round_no)
    except NotFoundError:
        return create_deal_round(db, deal_id, round_no)

# ---------------------------------------------------
# ===== Inventory Audit / Reconcile (Offer) =====
# ---------------------------------------------------
def _sum_qty_by_status(db: Session, offer_id: int) -> dict:
    row = db.query(
        func.coalesce(func.sum(case((Reservation.status == ReservationStatus.PENDING,   Reservation.qty), else_=0)), 0).label("pending_qty"),
        func.coalesce(func.sum(case((Reservation.status == ReservationStatus.PAID,      Reservation.qty), else_=0)), 0).label("paid_qty"),
        func.coalesce(func.sum(case((Reservation.status == ReservationStatus.CANCELLED, Reservation.qty), else_=0)), 0).label("cancelled_qty"),
        func.coalesce(func.sum(case((Reservation.status == ReservationStatus.EXPIRED,   Reservation.qty), else_=0)), 0).label("expired_qty"),
    ).filter(Reservation.offer_id == offer_id).one()
    return {
        "pending_qty":   int(row.pending_qty or 0),
        "paid_qty":      int(row.paid_qty or 0),
        "cancelled_qty": int(row.cancelled_qty or 0),
        "expired_qty":   int(row.expired_qty or 0),
    }

def get_offer_stats(db: Session, offer_id: int) -> dict:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError(f"Offer not found: {offer_id}")

    sums = _sum_qty_by_status(db, offer_id)
    total_available = int(offer.total_available_qty or 0)
    model_reserved  = int(offer.reserved_qty or 0)
    model_sold      = int(offer.sold_qty or 0)
    remaining       = total_available - model_reserved - model_sold

    return {
        "offer_id": offer_id,
        "total_available_qty": total_available,
        "reserved_qty(model)": model_reserved,
        "sold_qty(model)": model_sold,
        "remaining": remaining,
        "pending_qty(sum_reservations)":   sums["pending_qty"],
        "paid_qty(sum_reservations)":      sums["paid_qty"],
        "cancelled_qty(sum_reservations)": sums["cancelled_qty"],
        "expired_qty(sum_reservations)":   sums["expired_qty"],
        "is_confirmed": bool(offer.is_confirmed),
        "is_active": bool(offer.is_active),
        "deadline_at": offer.deadline_at,
        "created_at": offer.created_at,
    }

def audit_offer_inventory(db: Session, offer_id: int) -> dict:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError(f"Offer not found: {offer_id}")

    stats = get_offer_stats(db, offer_id)
    hints: list[str] = []

    if stats["reserved_qty(model)"] != stats["pending_qty(sum_reservations)"]:
        hints.append(
            f"reserved_qty mismatch: model={stats['reserved_qty(model)']} vs sum(PENDING)={stats['pending_qty(sum_reservations)']}"
        )
    if stats["sold_qty(model)"] != stats["paid_qty(sum_reservations)"]:
        hints.append(
            f"sold_qty mismatch: model={stats['sold_qty(model)']} vs sum(PAID)={stats['paid_qty(sum_reservations)']}"
        )
    if stats["remaining"] < 0:
        hints.append("remaining < 0 (over-allocated)")

    return {"ok": len(hints) == 0, "hints": hints, "stats": stats}

def reconcile_offer_inventory(db: Session, offer_id: int, apply: bool = False) -> dict:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError(f"Offer not found: {offer_id}")

    sums = _sum_qty_by_status(db, offer_id)
    before = {"reserved_qty": int(offer.reserved_qty or 0), "sold_qty": int(offer.sold_qty or 0)}
    after  = {"reserved_qty": sums["pending_qty"],          "sold_qty": sums["paid_qty"]}
    changed = (before != after)

    if apply and changed:
        offer.reserved_qty = after["reserved_qty"]
        offer.sold_qty     = after["sold_qty"]
        db.add(offer)
        db.commit()
        db.refresh(offer)

    stats = get_offer_stats(db, offer_id)
    return {"applied": bool(apply and changed), "changed": changed, "before": before,
            "after": {"reserved_qty": int(offer.reserved_qty or 0), "sold_qty": int(offer.sold_qty or 0)},
            "stats": stats}

# =========================================================
# 🧾 Offer Capacity & Reservations
# =========================================================
def get_offer_remaining_capacity(db: Session, offer_id: int) -> int:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError(f"Offer not found: {offer_id}")
    total = int(offer.total_available_qty or 0)
    sold = int(offer.sold_qty or 0)
    reserved = int(offer.reserved_qty or 0)
    return total - sold - reserved

def create_reservation(
    db: Session,
    *,
    deal_id: int,
    offer_id: int,
    buyer_id: int,
    qty: int,
    hold_minutes: int = 5
) -> Reservation:
    if qty <= 0:
        raise ConflictError("qty must be > 0")

    offer = db.get(Offer, offer_id)
    if not offer or offer.deal_id != deal_id:
        raise NotFoundError("Offer not found for deal")

    remain = get_offer_remaining_capacity(db, offer_id)
    if qty > remain:
        raise ConflictError(f"not enough capacity (remain={remain})")

    now = _utcnow()
    resv = Reservation(
        deal_id=deal_id,
        offer_id=offer_id,
        buyer_id=buyer_id,
        qty=qty,
        status=ReservationStatus.PENDING,
        created_at=now,
        expires_at=R.apply_deadtime_pause(now, minutes=hold_minutes),
        idempotency_key=None,
    )

    offer.reserved_qty = int(offer.reserved_qty or 0) + qty

    db.add(resv)
    db.add(offer)
    db.commit()
    db.refresh(resv)
    return resv

def cancel_reservation(db: Session, *, reservation_id: int, buyer_id: Optional[int] = None) -> Reservation:
    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")
    if resv.status != ReservationStatus.PENDING:
        raise ConflictError(f"cannot cancel: status={resv.status}")
    if buyer_id is not None and resv.buyer_id != buyer_id:
        raise ConflictError("not owned by buyer")

    offer = db.get(Offer, resv.offer_id)
    offer.reserved_qty = max(0, int(offer.reserved_qty or 0) - resv.qty)

    resv.status = ReservationStatus.CANCELLED
    resv.cancelled_at = _utcnow()

    db.add(resv)
    db.add(offer)
    db.commit()
    db.refresh(resv)
    return resv

def expire_reservations(
    db: Session,
    *,
    deal_id: Optional[int] = None,
    offer_id: Optional[int] = None,
    older_than: Optional[datetime] = None
) -> int:
    """PENDING + 만료시간 경과 → EXPIRED, reserved_qty 원복"""
    now = _utcnow()
    ts = older_than or now

    q = db.query(Reservation).filter(
        Reservation.status == ReservationStatus.PENDING,
        Reservation.expires_at.isnot(None),
        Reservation.expires_at < ts,
    )
    if deal_id is not None:
        q = q.filter(Reservation.deal_id == deal_id)
    if offer_id is not None:
        q = q.filter(Reservation.offer_id == offer_id)

    rows: List[Reservation] = q.all()
    count = 0
    for r in rows:
        offer = db.get(Offer, r.offer_id)
        if offer:
            offer.reserved_qty = max(0, int(offer.reserved_qty or 0) - r.qty)
            db.add(offer)
        r.status = ReservationStatus.EXPIRED
        r.expired_at = now
        db.add(r)
        count += 1

    db.commit()
    return count

def pay_reservation(
    db: Session,
    *,
    reservation_id: int,
    buyer_id: int,
    buyer_point_per_qty: int | None = None
) -> Reservation:
    """결제 성공: reserved -> sold, 바이어 +20pt/건 (v3.5 규칙)"""
    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")
    if resv.status != ReservationStatus.PENDING:
        raise ConflictError(f"cannot pay: status={resv.status}")
    if resv.buyer_id != buyer_id:
        raise ConflictError("not owned by buyer")

    expires_at_utc = _as_utc(resv.expires_at)
    if expires_at_utc and expires_at_utc < _utcnow():
        raise ConflictError("reservation expired")

    offer = db.get(Offer, resv.offer_id)
    if not offer:
        raise NotFoundError("Offer not found for reservation")

    offer.reserved_qty = max(0, int(offer.reserved_qty or 0) - resv.qty)
    offer.sold_qty     = int(offer.sold_qty or 0) + resv.qty

    resv.status = ReservationStatus.PAID
    resv.paid_at = _utcnow()

    _add_points(
        db,
        user_type="buyer",
        user_id=resv.buyer_id,
        amount=R.BUYER_POINT_ON_PAID,  # 보통 +20
        reason=f"PAID reservation {resv.id}",
        idempotency_key=f"pt:paid:{resv.id}",
    )

    db.add_all([offer, resv])
    db.commit()
    db.refresh(resv)
    return resv

def refund_paid_reservation(db: Session, *, reservation_id: int, actor: str = "buyer_cancel") -> Reservation:
    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")
    if resv.status != ReservationStatus.PAID:
        raise ConflictError(f"cannot refund: status={resv.status}")

    offer = db.get(Offer, resv.offer_id)
    offer.sold_qty = max(0, int(offer.sold_qty or 0) - resv.qty)

    resv.status = ReservationStatus.CANCELLED
    resv.cancelled_at = _utcnow()

    _add_points(
        db,
        user_type="buyer",
        user_id=resv.buyer_id,
        amount=R.BUYER_POINT_ON_REFUND,  # 보통 -20
        reason=f"REFUND reservation {resv.id} ({actor})",
        idempotency_key=f"pt:refund:{resv.id}",
    )

    db.add(offer)
    db.add(resv)
    db.commit()
    db.refresh(resv)
    return resv

# ===== 셀러 확정/철회 =====
def seller_confirm_offer(
    db: Session,
    *,
    offer_id: int,
    force: bool = False,
    award_on_full: int = 30
) -> Offer:
    """
    - force=False: 전량 판매 AND PENDING 0건일 때만 확정(+포인트)
    - force=True : 전량 미달이어도 확정(포인트 없음)
    """
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    total = int(offer.total_available_qty or 0)
    sold  = int(offer.sold_qty or 0)

    pending_cnt = db.query(func.count(Reservation.id)).filter(
        Reservation.offer_id == offer_id,
        Reservation.status == ReservationStatus.PENDING
    ).scalar() or 0

    if not force:
        if sold < total:
            raise ConflictError("offer not fully sold; cannot confirm")
        if pending_cnt > 0:
            raise ConflictError("cannot confirm while PENDING reservations exist")

    if not offer.is_confirmed:
        offer.is_confirmed = True
        db.add(offer)
        if not force and award_on_full:
            _add_points(
                db,
                user_type="seller",
                user_id=offer.seller_id,
                amount=award_on_full,
                reason=f"offer {offer.id} confirmed",
                idempotency_key=f"pt:seller:confirm:{offer.id}",
            )
        db.commit()
        db.refresh(offer)
    return offer

def seller_cancel_offer(
    db: Session,
    *,
    offer_id: int,
    penalize: bool = True,
    allow_paid: bool = True,
    reverse_buyer_points: bool = True,
) -> Offer:
    """
    셀러가 오퍼를 취소(거절).
    - 전량판매면 철회 불가
    - PENDING → CANCELLED, reserved_qty 복구
    - PAID    → allow_paid=True면 환불/취소 처리(+바이어 포인트 회수 여부는 reverse_buyer_points)
    - offer는 is_active=False, is_confirmed=False
    - penalize=True면 셀러 -30pt
    """
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")
    if offer.is_confirmed:
        raise ConflictError("cannot cancel: already confirmed offer")

    total = int(offer.total_available_qty or 0)
    sold  = int(offer.sold_qty or 0)
    if total > 0 and sold >= total:
        raise ConflictError("FULL_SELL: withdraw not allowed; must confirm")

    # 1) 대기(PENDING) 정리
    pendings: List[Reservation] = db.query(Reservation).filter(
        Reservation.offer_id == offer_id,
        Reservation.status == ReservationStatus.PENDING
    ).all()
    for r in pendings:
        offer.reserved_qty = max(0, int(offer.reserved_qty or 0) - r.qty)
        r.status = ReservationStatus.CANCELLED
        r.cancelled_at = _utcnow()
        db.add(r)

    # 2) 결제완료(PAID) 정리
    paids: List[Reservation] = db.query(Reservation).filter(
        Reservation.offer_id == offer_id,
        Reservation.status == ReservationStatus.PAID
    ).all()
    if paids and not allow_paid:
        raise ConflictError("cannot cancel: already has PAID reservations")

    for r in paids:
        offer.sold_qty = max(0, int(offer.sold_qty or 0) - r.qty)
        r.status = ReservationStatus.CANCELLED
        r.cancelled_at = _utcnow()
        db.add(r)

        if reverse_buyer_points:
            _add_points(
                db,
                user_type="buyer",
                user_id=r.buyer_id,
                amount=R.BUYER_POINT_ON_REFUND,  # 보통 -20
                reason=f"REFUND offer {offer.id} cancellation (reservation {r.id})",
                idempotency_key=f"pt:refund:{r.id}",
            )

    offer.is_active = False
    offer.is_confirmed = False
    db.add(offer)

    if penalize:
        _add_points(
            db,
            user_type="seller",
            user_id=offer.seller_id,
            amount=-30,
            reason=f"offer {offer.id} cancelled by seller",
            idempotency_key=f"pt:seller:withdraw:{offer.id}",
        )

    db.commit()
    db.refresh(offer)
    return offer

def seller_decide_withdraw_or_confirm(db: Session, *, offer_id: int, action: str) -> Offer:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    total = int(offer.total_available_qty or 0)
    sold  = int(offer.sold_qty or 0)
    full_sell = (total > 0 and sold >= total)

    now = _utcnow()
    decision_deadline = getattr(offer, "decision_deadline_at", None)
    if decision_deadline and now > decision_deadline:
        return seller_cancel_offer(db, offer_id=offer_id, penalize=False, allow_paid=True)

    action = action.lower()
    if full_sell:
        if action != "confirm":
            raise ConflictError("FULL_SELL: withdraw not allowed; must confirm")
        return seller_confirm_offer(db, offer_id=offer_id, force=False, award_on_full=30)

    if action == "withdraw":
        return seller_cancel_offer(db, offer_id=offer_id, penalize=True, allow_paid=True)
    if action == "confirm":
        return seller_confirm_offer(db, offer_id=offer_id, force=True, award_on_full=0)

    raise ConflictError("Unknown seller action")

# (하위호환)
def confirm_offer_if_soldout(db: Session, *, offer_id: int, seller_point_on_confirm: int = 30) -> Offer:
    return seller_confirm_offer(db, offer_id=offer_id, force=False, award_on_full=seller_point_on_confirm)

def get_offer_snapshot(db: Session, offer_id: int) -> dict:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    pending_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.PENDING
    ).scalar() or 0
    paid_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.PAID
    ).scalar() or 0
    cancelled_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.CANCELLED
    ).scalar() or 0
    expired_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.EXPIRED
    ).scalar() or 0

    model_reserved = int(offer.reserved_qty or 0)
    model_sold     = int(offer.sold_qty or 0)
    remaining = int(offer.total_available_qty or 0) - model_sold - model_reserved

    return {
        "offer_id": offer.id,
        "total_available_qty": int(offer.total_available_qty or 0),
        "reserved_qty(model)": model_reserved,
        "sold_qty(model)": model_sold,
        "remaining": remaining,
        "pending_qty(sum_reservations)": int(pending_qty),
        "paid_qty(sum_reservations)": int(paid_qty),
        "cancelled_qty(sum_reservations)": int(cancelled_qty),
        "expired_qty(sum_reservations)": int(expired_qty),
        "is_confirmed": bool(offer.is_confirmed),
        "is_active": bool(offer.is_active),
        "deadline_at": offer.deadline_at,
        "created_at": offer.created_at,
    }

def resync_offer_counters(db: Session, offer_id: int) -> dict:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    pending_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.PENDING
    ).scalar() or 0
    paid_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.PAID
    ).scalar() or 0

    offer.reserved_qty = int(pending_qty)
    offer.sold_qty     = int(paid_qty)
    db.add(offer)
    db.commit()

    return get_offer_snapshot(db, offer_id)

def update_offer_total_qty(
    db: Session,
    offer_id: int,
    *,
    total_available_qty: int,
    allow_unconfirm_on_increase: bool = True,
) -> Offer:
    """
    오퍼 총 공급량 변경.
    - 현재 sold + reserved 보다 작게 내릴 수 없음(409)
    - 총량을 '증가'시키는 경우 allow_unconfirm_on_increase=True면 자동 비확정 처리
    """
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError(f"Offer not found: {offer_id}")
    if total_available_qty < 0:
        raise ConflictError("total_available_qty must be >= 0")

    sold = int(offer.sold_qty or 0)
    reserved = int(offer.reserved_qty or 0)
    min_required = sold + reserved
    if total_available_qty < min_required:
        raise ConflictError(f"total_available_qty too small (min={min_required})")

    old_total = int(offer.total_available_qty or 0)
    increasing = total_available_qty > old_total

    # 증가 시 확정 자동 해제(옵션)
    if allow_unconfirm_on_increase and increasing and getattr(offer, "is_confirmed", False):
        offer.is_confirmed = False
        # 결정 상태 초기화(존재하면)
        for attr in ("decision_state", "decision_made_at", "decision_reason"):
            if hasattr(offer, attr):
                setattr(offer, attr, None)

    # 실제 총량 업데이트
    offer.total_available_qty = int(total_available_qty)

    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer

# ===== 조회 유틸
def get_reservation(db: Session, reservation_id: int) -> Reservation:
    obj = db.get(Reservation, reservation_id)
    if not obj:
        raise NotFoundError(f"Reservation not found: {reservation_id}")
    return obj

# ========= v3.5 전용 보강: 고정 포인트(+20 / -20) =========
def pay_reservation_v35(db: Session, *, reservation_id: int, buyer_id: int) -> Reservation:
    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")
    if resv.status != ReservationStatus.PENDING:
        raise ConflictError(f"cannot pay: status={resv.status}")
    if resv.buyer_id != buyer_id:
        raise ConflictError("not owned by buyer")
    if resv.expires_at and _as_utc(resv.expires_at) and _as_utc(resv.expires_at) < _utcnow():
        raise ConflictError("reservation expired")

    offer = db.get(Offer, resv.offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    offer.reserved_qty = max(0, int(offer.reserved_qty or 0) - resv.qty)
    offer.sold_qty     = int(offer.sold_qty or 0) + resv.qty

    resv.status = ReservationStatus.PAID
    resv.paid_at = _utcnow()

    db.add(PointTransaction(
        user_type="buyer",
        user_id=resv.buyer_id,
        amount=int(R.BUYER_POINT_ON_PAID),
        reason=f"reservation {resv.id} paid (v3.5 fixed point)",
        created_at=_utcnow(),
    ))

    db.add(resv)
    db.add(offer)
    db.commit()
    db.refresh(resv)
    return resv

def seller_withdraw_offer_v35(
    db: Session,
    *,
    offer_id: int,
    reason: str | None = None,
    penalize_seller: bool = True
) -> Offer:
    """
    v3.5 고정 포인트 준수 철회:
      1) 철회 직전 PAID 예약 목록 수집
      2) 내부 취소 로직 호출(+바이어 포인트 자동회수 비활성화)
      3) 각 예약에 대해 고정 -20 보정 트랜잭션 추가
    """
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")
    if offer.is_confirmed:
        raise ConflictError("cannot cancel: already confirmed offer")

    paid_before: List[Reservation] = db.query(Reservation).filter(
        Reservation.offer_id == offer_id,
        Reservation.status == ReservationStatus.PAID
    ).all()

    offer = seller_cancel_offer(
        db,
        offer_id=offer_id,
        penalize=penalize_seller,
        allow_paid=True,
        reverse_buyer_points=False,
    )

    if int(R.BUYER_POINT_ON_REFUND) != 0:
        now = _utcnow()
        for r in paid_before:
            db.add(PointTransaction(
                user_type="buyer",
                user_id=r.buyer_id,
                amount=int(R.BUYER_POINT_ON_REFUND),  # 보통 -20
                reason=f"refund after seller withdraw offer {offer_id} (reservation {r.id})",
                created_at=now,
            ))
        db.commit()

    if hasattr(offer, "decision_state"):
        offer.decision_state = "WITHDRAWN"
    if hasattr(offer, "decision_made_at"):
        offer.decision_made_at = _utcnow()
    if hasattr(offer, "decision_reason"):
        offer.decision_reason = reason or "seller_withdraw_v35"

    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer

def search_reservations(
    db: Session,
    *,
    reservation_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    offer_id: Optional[int] = None,
    buyer_id: Optional[int] = None,
    status: Optional[ReservationStatus] = None,
    after_id: Optional[int] = None,
    limit: int = 50,
) -> List[Reservation]:
    q = db.query(Reservation)
    if reservation_id is not None:
        q = q.filter(Reservation.id == reservation_id)
    if deal_id is not None:
        q = q.filter(Reservation.deal_id == deal_id)
    if offer_id is not None:
        q = q.filter(Reservation.offer_id == offer_id)
    if buyer_id is not None:
        q = q.filter(Reservation.buyer_id == buyer_id)
    if status is not None:
        q = q.filter(Reservation.status == status)
    if after_id is not None:
        q = q.filter(Reservation.id < after_id)

    return q.order_by(Reservation.id.desc()).limit(max(1, min(200, int(limit or 50)))).all()

# =========================================================
# 💵 Deposit (통합·정식)
# =========================================================
def _normalize_status(s: str | None) -> str:
    s_up = (s or "").upper()
    if s_up in {"ACTIVE", "HOLD"}:  # 혼용 대응
        return "HELD"
    return s_up

def _resolve_deposit_model():
    for name in ("BuyerDeposit", "Deposit", "BuyerDepositHold", "DepositHold"):
        M = getattr(models, name, None)
        if M is not None:
            return M
    return None

def create_buyer_deposit(
    db: Session,
    *,
    deal_id: int,
    buyer_id: int,
    amount: int
):
    Model = _resolve_deposit_model()
    if Model is None:
        return None  # 트래킹 비활성(프로젝트마다 다름)

    dep = Model(
        deal_id=deal_id,
        buyer_id=buyer_id,
        amount=amount,
        status="HELD",
        created_at=_utcnow(),
    )
    db.add(dep)
    db.commit()
    db.refresh(dep)
    return dep

def get_buyer_deposit(db: Session, deposit_id: int):
    Model = _resolve_deposit_model()
    if Model is None:
        return None
    return db.get(Model, deposit_id)

def get_active_deposit_for(db: Session, *, deal_id: int, buyer_id: int):
    """결제 가드용: 해당 딜/바이어의 활성(HELD) 디파짓 1건 조회"""
    Model = _resolve_deposit_model()
    if Model is None:
        return None
    return (
        db.query(Model)
          .filter(Model.deal_id == deal_id, Model.buyer_id == buyer_id)
          .filter(func.upper(func.coalesce(Model.status, ""))  # 안전 비교
                  .in_(("HELD", "ACTIVE", "HOLD")))
          .order_by(Model.id.desc())
          .first()
    )

def refund_buyer_deposit(db: Session, deposit_id: int):
    dep = get_buyer_deposit(db, deposit_id)
    if not dep:
        return None

    status_now = _normalize_status(getattr(dep, "status", None))
    if status_now == "REFUNDED":
        # 멱등 가드: 이미 환불됨
        raise DepositConflict("Deposit already refunded")
    if status_now not in {"HELD"}:
        # HELD 상태가 아니라면 비정상
        raise DepositConflict(f"invalid state for refund: {status_now}")

    setattr(dep, "status", "REFUNDED")
    if hasattr(dep, "refunded_at") and getattr(dep, "refunded_at", None) is None:
        setattr(dep, "refunded_at", _utcnow())

    db.add(dep)
    db.commit()
    db.refresh(dep)
    return dep

# 공개 심볼
__all__ = [
    # errors
    "NotFoundError", "ConflictError", "DepositConflict",
    # buyers/sellers/deals/participants
    "create_buyer", "get_buyers",
    "create_seller", "get_sellers",
    "create_deal", "get_deal", "get_deals",
    "add_participant", "get_deal_participants", "remove_participant",
    # offers / points
    "create_offer", "get_offers", "confirm_offer_and_reward",
    "create_point_transaction", "get_point_transactions", "get_user_balance",
    # rounds
    "get_round_by_no", "list_rounds", "get_active_round",
    "create_deal_round", "get_or_create_next_round",
    "open_round", "finalize_round", "close_round", "cancel_round",
    "RoundAction", "progress_round",
    "assert_no_open_round", "ensure_round_exists",
    # reservations & offer life-cycle
    "get_offer_remaining_capacity",
    "create_reservation", "cancel_reservation", "expire_reservations",
    "pay_reservation", "refund_paid_reservation",
    "seller_confirm_offer", "seller_cancel_offer", "seller_decide_withdraw_or_confirm",
    "confirm_offer_if_soldout", "get_offer_snapshot", "resync_offer_counters", "update_offer_total_qty",
    "get_reservation", "search_reservations",
    # v3.5 helpers
    "pay_reservation_v35", "seller_withdraw_offer_v35",
    # deposits
    "create_buyer_deposit", "get_buyer_deposit", "get_active_deposit_for", "refund_buyer_deposit",
]