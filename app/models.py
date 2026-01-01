# app/models.py
# v3.6 (models step-up for v3.5 rules) — DealRound/Reservation 유지 + 리뷰/집계/이벤트로그/검색지문 추가
from sqlalchemy import (
    Column, Integer, String, DateTime, Float, ForeignKey, Text, text, Boolean, func, 
    Enum as SAEnum, JSON, Index, UniqueConstraint, func, CheckConstraint
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from .database import Base
import enum
from datetime import datetime, timezone


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
    # (NEW) 추천인
    recommender_buyer_id = Column(Integer, ForeignKey("buyers.id"), nullable=True)
    recommender = relationship("Buyer", remote_side=[id])
    # (NEW) 레벨 (티어와는 별개)
    level = Column(Integer, default=6, nullable=False)    
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

    # (NEW) 나를 데려온 Actuator (없을 수도 있음)
    actuator_id = Column(Integer, ForeignKey("actuators.id"), nullable=True)

    actuator = relationship("Actuator", back_populates="sellers")
    
    # (NEW) 이 Seller 거래로 발생한 Actuator 커미션들
    actuator_commissions = relationship("ActuatorCommission", backref="seller")


# -------------------------------------------------------
# 🧑‍💼 Actuator (Seller를 모집하는 집단)
# -------------------------------------------------------
class Actuator(Base):
    __tablename__ = "actuators"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    # 이 Actuator가 받은 커미션들
    commissions = relationship("ActuatorCommission", backref="actuator")

    # ACTIVE / SUSPENDED / CLOSED
    status = Column(String(20), nullable=False, default="ACTIVE")

    # 정산 관련 메모/계좌 정보 (단순 문자열로 저장해두고, 나중에 구조화해도 됨)
    settlement_info = Column(String(512), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 이 Actuator가 데려온 Sellers
    sellers = relationship("Seller", back_populates="actuator")


# -------------------------------------------------------
# 💰 Actuator 커미션 로그
# -------------------------------------------------------
class ActuatorCommission(Base):
    __tablename__ = "actuator_commissions"

    id = Column(Integer, primary_key=True, index=True)

    actuator_id = Column(Integer, ForeignKey("actuators.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)

    # 해당 거래(예약)의 총 거래금액 (원)
    gmv = Column(Integer, nullable=False)

    # 이 중 Actuator 수수료 (%)
    rate_percent = Column(Float, nullable=False)

    # 수수료 금액(원) = gmv * rate_percent / 100
    amount = Column(Integer, nullable=False)

    # 🆕 지급 상태 / 시각
    status = Column(String(20), nullable=False, default="PENDING")  # PENDING / PAID
        # ✅ 새로 추가
    ready_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# -------------------------------------------------------
# 💰 Actuator 수수료 적립 로그
# -------------------------------------------------------
class ActuatorRewardLog(Base):
    __tablename__ = "actuator_reward_logs"

    id = Column(Integer, primary_key=True, index=True)
    actuator_id = Column(Integer, ForeignKey("actuators.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False)

    # 거래 금액 원화 (qty * price)
    gmv = Column(Integer, nullable=False)

    # 수수료율(%) — 예: 0.5 → 0.5%
    fee_percent = Column(Float, nullable=False)

    # 최종 적립 금액 (fee 계산 후 정수)
    reward_amount = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    actuator = relationship("Actuator")
    seller = relationship("Seller")



# -------------------------------------------------------
# 🧾 Deal
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
    #   status: "open" / "closed" / "archived"
    deadline_at = Column(DateTime, nullable=True)
    status = Column(String, default="open", nullable=False)

    # v3.5: 검색/중복방지 지문
    product_norm = Column(String, nullable=True)
    options_norm = Column(String, nullable=True)
    fingerprint_hash = Column(String, index=True)

    # v3.6: LLM 기반 매칭용 키
    ai_product_key = Column(String, index=True, nullable=True)
    ai_parsed_intent = Column(Text, nullable=True)



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
        Index("ix_deal_ai_product_key", "ai_product_key"),        
    )



class DealAILog(Base):
    __tablename__ = "deal_ai_logs"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String(100), nullable=False)
    buyer_id = Column(Integer, nullable=True)
    deal_id = Column(Integer, nullable=True)

    # 요청/응답을 그대로 JSON 문자열로 저장
    request_json = Column(Text, nullable=False)
    response_json = Column(Text, nullable=True)

    extra = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
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
# 🔔 User Notification (내부 알림센터용)
# -------------------------------------------------------
class UserNotification(Base):
    __tablename__ = "user_notifications"

    id = Column(Integer, primary_key=True, index=True)

    # 어떤 유저의 알림인지
    user_id = Column(Integer, nullable=False, index=True)

    # 알림 종류 (deal_deadline_soon, seller_onboarded, deal_chat_message, ...)
    type = Column(String(50), nullable=False)

    # 제목 / 내용
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)

    # 선택: 알림을 눌렀을 때 이동할 링크 (웹/앱 내부 경로)
    link_url = Column(String(500))

    # 실제 이벤트가 발생한 시각 (선택)
    event_time = Column(DateTime)

    # 알림이 생성된 시각 (UTC)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # 읽은 시각 (읽지 않았으면 NULL)
    read_at = Column(DateTime(timezone=True))

    # 읽음 여부
    is_read = Column(
        Boolean,
        nullable=False,
        server_default=text("0"),
    )

    # JSON 메타 문자열 (role, deal_id, offer_id 등)
    meta_json = Column(Text)

#------------------------------------------------------
# Deal 채팅방
#------------------------------------------------------

class DealChatMessage(Base):
    __tablename__ = "deal_chat_messages"

    id = Column(Integer, primary_key=True, index=True)

    # 어떤 딜의 채팅인지
    deal_id = Column(
        Integer,
        ForeignKey("deals.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # 누가 썼는지 (buyer 기준)
    buyer_id = Column(
        Integer,
        ForeignKey("buyers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # 실제 텍스트
    text = Column(Text, nullable=False)

    # 모더레이션(욕설/개인정보 등)으로 숨긴 메시지
    blocked = Column(Boolean, nullable=False, default=False, server_default="0")
    blocked_reason = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())




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

    # =========================
    #  🚚 배송비 설정 (v1)
    # =========================
    # INCLUDED / PER_RESERVATION / PER_QTY
    shipping_mode = Column(String(32), nullable=True, default="INCLUDED")
    # PER_RESERVATION: 예약 1건당 고정 배송비
    shipping_fee_per_reservation = Column(Integer, nullable=False, default=0)
    # PER_QTY: 수량 1개당 배송비
    shipping_fee_per_qty = Column(Integer, nullable=False, default=0)

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


# ----------------------------------------------------
# Offer policy (취소,반품,환불 등)
#-----------------------------------------------------
class OfferPolicy(Base):
    __tablename__ = "offer_policies"

    id = Column(Integer, primary_key=True, index=True)

    # 어느 오퍼에 대한 정책인지 (1:1 관계 가정)
    offer_id = Column(
        Integer,
        ForeignKey("offers.id"),
        nullable=False,
        index=True,
        unique=True,  # 한 오퍼당 정책 1개
    )

    # 취소 규칙 코드: A1 / A2 / A3 / A4
    cancel_rule = Column(String(10), nullable=False)

    # A3일 때만 쓰이는 값 (배송완료 후 X일 이내 취소 가능)
    cancel_within_days = Column(Integer, nullable=True)

    # 셀러가 추가로 적는 상세 텍스트 (최대 1000자 정도 가정)
    extra_text = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # (선택) Offer 쪽에서 역참조 관계 걸고 싶으면:
    offer = relationship("Offer", backref="policy")


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
    # 💰 결제 금액 박제 (v1)
    amount_goods = Column(Integer, nullable=False, default=0)     # 상품 금액
    amount_shipping = Column(Integer, nullable=False, default=0)  # 배송비
    amount_total = Column(Integer, nullable=False, default=0)     # 총 결제 금액    

    # 부분환불 지원용 필드
    refunded_qty = Column(Integer, nullable=False, default=0)
    refunded_amount_total = Column(Integer, nullable=False, default=0)

    
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
    # 🔽🔽🔽 여기 추가
    shipping_carrier = Column(String(50), nullable=True)
    tracking_number = Column(String(100), nullable=True)
    shipped_at = Column(DateTime(timezone=True), nullable=True)              # 셀러가 "배송완료" 누른 시각
    delivered_at = Column(DateTime(timezone=True), nullable=True)           # 필요하면 택배사 기준 "배송완료"용(쓸지 안쓸지는 나중에)
    arrival_confirmed_at = Column(DateTime(timezone=True), nullable=True)   # 바이어가 "도착완료" 누른 시각
    # 🔼🔼🔼

        # ✅ 분쟁 상태 (SSOT 추천)
    is_disputed = Column(Boolean, nullable=False, default=False, server_default="false")
    dispute_opened_at = Column(DateTime(timezone=True), nullable=True)
    dispute_closed_at = Column(DateTime(timezone=True), nullable=True)


    idempotency_key = Column(String, unique=True, index=True, nullable=True)
    
# 🔹 배송/도착 관련 타임스탬프



    offer = relationship("Offer")
    buyer = relationship("Buyer")

    # --- 신규: 정책 동의 관련 필드 ---
    # 예약 시점에 참조한 OfferPolicy의 id (있으면)
    policy_id = Column(Integer, ForeignKey("offer_policies.id"), nullable=True)
    # 예약 시점 정책 내용을 JSON 문자열로 스냅샷 저장
    policy_snapshot_json = Column(Text, nullable=True)
    # Buyer가 정책에 동의한 시각
    policy_agreed_at = Column(DateTime, nullable=True)
    # (선택) 연관 관계 – 필요하면 추가
    policy = relationship("OfferPolicy", backref="reservations", lazy="joined")





    __table_args__ = (
        Index("ix_resv_offer_status", "offer_id", "status"),
        Index("ix_resv_buyer_status", "buyer_id", "status"),
        Index("ix_resv_deal_status", "deal_id", "status"),
        CheckConstraint("qty > 0", name="ck_reservation_qty_positive"),
    )


# ---------------------------------------------------------
# 💰 ReservationSettlement: 예약 1건에 대한 정산 결과
# ---------------------------------------------------------
class ReservationSettlement(Base):
    __tablename__ = "reservation_settlements"

    id = Column(Integer, primary_key=True, index=True)

    # 어떤 예약에 대한 정산인지
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False, unique=True)

    # 기본 매핑 정보
    deal_id = Column(Integer, nullable=False)
    offer_id = Column(Integer, nullable=False)
    seller_id = Column(Integer, nullable=False)
    buyer_id = Column(Integer, nullable=False)

    # 금액들 (원화 가정, 정수로)
    buyer_paid_amount = Column(Integer, nullable=False)
    pg_fee_amount = Column(Integer, nullable=False, default=0)
    platform_commission_amount = Column(Integer, nullable=False, default=0)
    seller_payout_amount = Column(Integer, nullable=False)

    # 상태/타입
    # 예: HOLD / READY / PAID / CANCELLED ...
    status = Column(String(20), nullable=False, default="PENDING")
    currency = Column(String(10), nullable=False, default="KRW")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # ✅ 정산 자동화 핵심 필드들 (A안)
    ready_at = Column(DateTime(timezone=True), nullable=True)               # 쿨링 종료(정산 가능 시점)
    approved_at = Column(DateTime(timezone=True), nullable=True)            # 관리자 승인 시각
    scheduled_payout_at = Column(DateTime(timezone=True), nullable=True)    # 지급 예정일(자동 지급 기준)
    paid_at = Column(DateTime(timezone=True), nullable=True)                # 실제 지급 처리 시각

    # ✅ 블록(홀드) 사유
    block_reason = Column(String(50), nullable=True)  # WITHIN_COOLING / DISPUTE / ...

    # ✅ 분쟁 메타
    dispute_opened_at = Column(DateTime(timezone=True), nullable=True)
    dispute_closed_at = Column(DateTime(timezone=True), nullable=True)

    # ✅ 운영자가 지급일을 수정할 수 있게(선택)
    payout_override_reason = Column(String(200), nullable=True)
    
    
    
#------------------------------------------
# PG 트랜잭션 기록용
#------------------------------------------

class ReservationPayment(Base):
    __tablename__ = "reservation_payments"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), index=True, nullable=False)
    pg_provider = Column(String(50), nullable=True)        # "KCP", "TossPayments" 등
    pg_tid = Column(String(100), nullable=True, unique=True)  # PG transaction id
    method = Column(String(50), nullable=True)             # "CARD", "VIRTUAL", ...
    paid_amount = Column(Integer, nullable=False)          # 총 결제 금액(부가세 포함)
    pg_fee_amount = Column(Integer, nullable=False, default=0)  # PG 수수료
    currency = Column(String(3), nullable=False, default="KRW")

    paid_at = Column(DateTime(timezone=True), nullable=True)
    raw_payload = Column(Text, nullable=True)              # PG webhook 전문(JSON) 저장용

    reservation = relationship("Reservation", backref="payments")


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
    

#--------------------------------
# 정책선언집
#-----------------------------------
class PolicyDeclaration(Base):
    __tablename__ = "policy_declarations"

    id = Column(Integer, primary_key=True, index=True)

    domain = Column(String, nullable=False, index=True)
    policy_key = Column(String, nullable=False, index=True)

    title = Column(String, nullable=False)
    description_md = Column(Text, nullable=False)

    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())



#----------------------------------
# Pingpong이 사용할 Log
#---------------------------------

class PingpongLog(Base):
    __tablename__ = "pingpong_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    user_id = Column(Integer, nullable=True)
    role = Column(String, nullable=True)
    locale = Column(String, nullable=False, default="ko")

    screen = Column(String, nullable=False)
    deal_id = Column(Integer, nullable=True)
    reservation_id = Column(Integer, nullable=True)
    offer_id = Column(Integer, nullable=True)

    mode = Column(String, nullable=False, default="read_only")
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    used_policy_keys_json = Column(Text, nullable=True)
    used_policy_ids_json = Column(Text, nullable=True)
    actions_json = Column(Text, nullable=True)
    context_json = Column(Text, nullable=True)
    request_json = Column(Text, nullable=True)
    response_json = Column(Text, nullable=True)

    llm_model = Column(String, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)

    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)