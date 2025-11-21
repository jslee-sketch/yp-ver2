# app/models.py
# v3.6 (models step-up for v3.5 rules) — DealRound/Reservation 유지 + 리뷰/집계/이벤트로그/검색지문 추가
from sqlalchemy import (
    Column, Integer, String, DateTime, Float, ForeignKey, Text, Boolean,
    Enum as SAEnum, JSON, Index, UniqueConstraint, func, CheckConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import enum

# -------------------------------------------------------
# 🧩 User Model (인증/권한)
# -------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)  # 'user', 'admin' 등
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User(email='{self.email}', role='{self.role}', active={self.is_active})>"

# -------------------------------------------------------
# 🛒 Buyer / 🧾 PointTransaction
# -------------------------------------------------------
class Buyer(Base):
    __tablename__ = "buyers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    birth_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    points = Column(Integer, default=0, nullable=False)
    status = Column(String, default="active")
    # v3.5: 신뢰티어(누적 이행률 기반)
    trust_tier = Column(String, nullable=True)
    tier_computed_at = Column(DateTime, nullable=True)

    participants = relationship("DealParticipant", back_populates="buyer")
    deals = relationship("Deal", back_populates="creator")


class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String, nullable=False)   # 'buyer' or 'seller'
    user_id = Column(Integer, nullable=False)    # buyer_id or seller_id
    amount = Column(Integer, nullable=False)     # +적립, -차감
    reason = Column(String, nullable=True)
    idempotency_key = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_point_user_created", "user_type", "user_id", "created_at"),
    )

# -------------------------------------------------------
# 🧑‍💼 Seller
# -------------------------------------------------------
class Seller(Base):
    __tablename__ = "sellers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    business_name = Column(String, nullable=False)
    business_number = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    company_phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    zip_code = Column(String, nullable=True)
    established_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # v3.5: 검증/레벨/포인트
    verified_at = Column(DateTime, nullable=True)
    points = Column(Integer, default=0)
    level = Column(Integer, default=6, nullable=False)  # 1(최고)~6(new)

    offers = relationship("Offer", back_populates="seller")
    reviews = relationship("SellerReview", back_populates="seller", cascade="all, delete-orphan")
    rating_aggregate = relationship("SellerRatingAggregate", back_populates="seller", uselist=False, cascade="all, delete-orphan")

# -------------------------------------------------------
# 📦 Deal (+ 검색지문)
# -------------------------------------------------------
class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    product_name = Column(String, nullable=False)
    creator_id = Column(Integer, ForeignKey("buyers.id"))
    desired_qty = Column(Integer, nullable=False, default=1)
    current_qty = Column(Integer, default=0)
    target_price = Column(Float, nullable=True)
    max_budget = Column(Float, nullable=True)
    current_avg_price = Column(Float, default=0)

    # 옵션 1~5
    option1_title = Column(String, nullable=True)
    option1_value = Column(String, nullable=True)
    option2_title = Column(String, nullable=True)
    option2_value = Column(String, nullable=True)
    option3_title = Column(String, nullable=True)
    option3_value = Column(String, nullable=True)
    option4_title = Column(String, nullable=True)
    option4_value = Column(String, nullable=True)
    option5_title = Column(String, nullable=True)
    option5_value = Column(String, nullable=True)

    free_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # v3.5: 마감/상태
    deadline_at = Column(DateTime, nullable=True)
    status = Column(String, default="open", nullable=False)  # open/closed/archived

    # v3.5: 검색/중복방지 지문
    product_norm = Column(String, nullable=True)
    options_norm = Column(String, nullable=True)
    fingerprint_hash = Column(String, index=True)

    creator = relationship("Buyer", back_populates="deals")
    offers = relationship("Offer", back_populates="deal")
    participants = relationship("DealParticipant", back_populates="deal")
    rounds = relationship(
        "DealRound",
        back_populates="deal",
        cascade="all, delete-orphan",
        order_by="DealRound.round_no",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_deal_status_deadline", "status", "deadline_at"),
        Index("ix_deal_fingerprint", "fingerprint_hash"),
    )

# -------------------------------------------------------
# 👥 DealParticipant
# -------------------------------------------------------
class DealParticipant(Base):
    __tablename__ = "deal_participants"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id"))
    buyer_id = Column(Integer, ForeignKey("buyers.id"))
    qty = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    deal = relationship("Deal", back_populates="participants")
    buyer = relationship("Buyer", back_populates="participants")

    __table_args__ = (
        UniqueConstraint("deal_id", "buyer_id", name="uq_participation_once_per_deal"),
        Index("ix_participation_deal", "deal_id"),
    )

# -------------------------------------------------------
# 💰 Offer (+ 판매자 결정 창 상태/제약)
# -------------------------------------------------------
class OfferDecisionState(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    WITHDRAWN = "WITHDRAWN"
    AUTO_WITHDRAWN = "AUTO_WITHDRAWN"
    AUTO_CONFIRMED = "AUTO_CONFIRMED"

class Offer(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id", ondelete="CASCADE"))
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"))
    price = Column(Float, nullable=False)
    total_available_qty = Column(Integer, nullable=False)
    delivery_days = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)

    # 카운터
    sold_qty = Column(Integer, nullable=False, default=0, server_default="0")
    reserved_qty = Column(Integer, nullable=False, default=0, server_default="0")

    # Deal 옵션 복사
    option1_title = Column(String, nullable=True)
    option1_value = Column(String, nullable=True)
    option2_title = Column(String, nullable=True)
    option2_value = Column(String, nullable=True)
    option3_title = Column(String, nullable=True)
    option3_value = Column(String, nullable=True)
    option4_title = Column(String, nullable=True)
    option4_value = Column(String, nullable=True)
    option5_title = Column(String, nullable=True)
    option5_value = Column(String, nullable=True)

    free_text = Column(Text, nullable=True)

    # 상태/타임라인
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    deadline_at = Column(DateTime, nullable=True)
    is_confirmed = Column(Boolean, default=False)

    # v3.5: 판매자 결정창
    decision_state = Column(SAEnum(OfferDecisionState, name="offerdecisionstate"), nullable=True)
    decision_deadline_at = Column(DateTime, nullable=True)
    decision_made_at = Column(DateTime, nullable=True)
    decision_reason = Column(String, nullable=True)

    deal = relationship("Deal", back_populates="offers")
    seller = relationship("Seller", back_populates="offers")

    __table_args__ = (
        CheckConstraint("total_available_qty >= 0", name="ck_offer_total_nonneg"),
        CheckConstraint("sold_qty >= 0 AND reserved_qty >= 0", name="ck_offer_counters_nonneg"),
        CheckConstraint("sold_qty + reserved_qty <= total_available_qty", name="ck_offer_counters_not_over"),
        Index("ix_offer_deal_active_deadline", "deal_id", "is_active", "deadline_at"),
        Index("ix_offer_deal_confirmed", "deal_id", "is_confirmed"),
        Index("ix_offer_seller", "seller_id"),
    )

# -------------------------------------------------------
# 💳 BuyerDeposit (옵션)
# -------------------------------------------------------
class BuyerDepositStatus(str, enum.Enum):
    HELD = "HELD"
    REFUNDED = "REFUNDED"

class BuyerDeposit(Base):
    __tablename__ = "buyer_deposits"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    admin_note = Column(String, nullable=True)
    buyer_id = Column(Integer, ForeignKey("buyers.id"), nullable=True)
    amount = Column(Integer, nullable=False)
    status = Column(SAEnum(BuyerDepositStatus, name="buyerdepositstatus"), default=BuyerDepositStatus.HELD.value, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    refunded_at = Column(DateTime, nullable=True)
    refund_reason = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_deposit_deal_buyer", "deal_id", "buyer_id"),
    )

# -------------------------------------------------------
# 🔁 Deal Round
# -------------------------------------------------------
class DealRoundStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    OPEN = "OPEN"
    FINALIZING = "FINALIZING"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

class DealRound(Base):
    __tablename__ = "deal_rounds"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    round_no = Column(Integer, nullable=False)
    status = Column(SAEnum(DealRoundStatus, name="dealroundstatus"), nullable=False,
                    default=DealRoundStatus.PLANNED, server_default=DealRoundStatus.PLANNED.value)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    deal = relationship("Deal", back_populates="rounds")

    __table_args__ = (
        UniqueConstraint("deal_id", "round_no", name="uq_deal_round_deal_id_round_no"),
        Index("ix_deal_round_status", "status"),
        Index("ix_deal_round_deal_status", "deal_id", "status"),
        CheckConstraint("round_no >= 1", name="ck_deal_round_round_no_positive"),
    )

# -------------------------------------------------------
# 🧾 Reservation
# -------------------------------------------------------
class ReservationStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"

class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    offer_id = Column(Integer, ForeignKey("offers.id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("buyers.id", ondelete="CASCADE"), nullable=False, index=True)

    qty = Column(Integer, nullable=False)
    status = Column(
        SAEnum(ReservationStatus, name="reservationstatus"),
        nullable=False,
        server_default=ReservationStatus.PENDING.value,
    )

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)

    idempotency_key = Column(String, unique=True, index=True, nullable=True)

    offer = relationship("Offer")
    buyer = relationship("Buyer")

    __table_args__ = (
        Index("ix_resv_offer_status", "offer_id", "status"),
        Index("ix_resv_buyer_status", "buyer_id", "status"),
        Index("ix_resv_deal_status", "deal_id", "status"),
        CheckConstraint("qty > 0", name="ck_reservation_qty_positive"),
    )

# -------------------------------------------------------
# ⭐ 리뷰 & 평점 집계
# -------------------------------------------------------
class SellerReview(Base):
    __tablename__ = "seller_reviews"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("buyers.id", ondelete="CASCADE"), nullable=False, index=True)

    # 다차원 평점(1~5)
    price_fairness = Column(Integer, nullable=False)
    quality = Column(Integer, nullable=False)
    shipping = Column(Integer, nullable=False)
    communication = Column(Integer, nullable=False)
    accuracy = Column(Integer, nullable=False)

    comment = Column(Text, nullable=True)
    media_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=True)

    helpful_yes = Column(Integer, default=0)
    helpful_no = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    seller = relationship("Seller", back_populates="reviews")

    __table_args__ = (
        UniqueConstraint("reservation_id", "buyer_id", name="uq_review_once_per_buyer_reservation"),
        Index("ix_review_seller_created", "seller_id", "created_at"),
    )


class SellerRatingAggregate(Base):
    __tablename__ = "seller_rating_aggregates"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id", ondelete="CASCADE"), unique=True, nullable=False)

    reviews_count = Column(Integer, default=0)
    rating_raw_mean = Column(Float, default=0.0)
    rating_adjusted = Column(Float, default=0.0)
    last_computed_at = Column(DateTime, nullable=True)

    price_fairness_avg = Column(Float, default=0.0)
    quality_avg = Column(Float, default=0.0)
    shipping_avg = Column(Float, default=0.0)
    communication_avg = Column(Float, default=0.0)
    accuracy_avg = Column(Float, default=0.0)

    seller = relationship("Seller", back_populates="rating_aggregate")

# -------------------------------------------------------
# 🧭 이벤트 로그
# -------------------------------------------------------
class EventType(str, enum.Enum):
    DEAL_CREATED = "DEAL_CREATED"
    DEAL_CLOSED = "DEAL_CLOSED"
    ROUND_OPENED = "ROUND_OPENED"
    ROUND_CLOSED = "ROUND_CLOSED"
    OFFER_CREATED = "OFFER_CREATED"
    OFFER_CONFIRMED = "OFFER_CONFIRMED"
    OFFER_WITHDRAWN = "OFFER_WITHDRAWN"
    RESERVATION_CREATED = "RESERVATION_CREATED"
    RESERVATION_PAID = "RESERVATION_PAID"
    RESERVATION_CANCELLED = "RESERVATION_CANCELLED"
    RESERVATION_EXPIRED = "RESERVATION_EXPIRED"
    POINT_CREDIT = "POINT_CREDIT"
    POINT_DEBIT = "POINT_DEBIT"
    REVIEW_CREATED = "REVIEW_CREATED"
    REVIEW_FLAGGED = "REVIEW_FLAGGED"

class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(SAEnum(EventType, name="eventtype"), nullable=False)
    actor_type = Column(String, nullable=True)  # 'buyer' | 'seller' | 'system' | 'admin'
    actor_id = Column(Integer, nullable=True)

    deal_id = Column(Integer, nullable=True, index=True)
    round_id = Column(Integer, nullable=True, index=True)
    offer_id = Column(Integer, nullable=True, index=True)
    reservation_id = Column(Integer, nullable=True, index=True)
    seller_id = Column(Integer, nullable=True, index=True)
    buyer_id = Column(Integer, nullable=True, index=True)

    amount = Column(Float, nullable=True)
    qty = Column(Integer, nullable=True)
    reason = Column(String, nullable=True)
    idempotency_key = Column(String, nullable=True, index=True)
    meta = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_event_type_created", "event_type", "created_at"),
    )