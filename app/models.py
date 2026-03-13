# app/models.py
# v3.6 (models step-up for v3.5 rules) — DealRound/Reservation 유지 + 리뷰/집계/이벤트로그/검색지문 추가
from sqlalchemy import (
    Column, Integer, String, DateTime, Float, ForeignKey, Text, text, Boolean, func, 
    Enum as SAEnum, JSON, Index, UniqueConstraint, func, CheckConstraint
)

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import JSON #sqlite 등

    
from datetime import datetime
from .database import Base
import enum
from datetime import datetime, timezone
import json

# -------------------------------------------------------
# 🧩 User Model (인증/권한)
# -------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String(50), nullable=True)
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
    nickname = Column(String(30), nullable=True, unique=True, index=True)
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
    # 소셜 로그인
    payment_method = Column(String, nullable=True)  # 'card', 'bank' 등
    social_provider = Column(String(20), nullable=True)   # kakao|naver|google
    social_id       = Column(String(100), nullable=True, index=True)
    # 계정 상태 (탈퇴/차단)
    is_active = Column(Boolean, default=True, nullable=False, server_default="true")
    withdrawn_at = Column(DateTime, nullable=True)
    is_banned = Column(Boolean, default=False, nullable=False, server_default="false")
    banned_until = Column(DateTime, nullable=True)
    ban_reason = Column(Text, nullable=True)
    # 비밀번호 재설정 토큰
    reset_token = Column(String(64), nullable=True, index=True)
    reset_token_expires_at = Column(DateTime, nullable=True)

    # FCM 푸시 토큰
    fcm_token = Column(String(500), nullable=True)
    fcm_updated_at = Column(DateTime, nullable=True)

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
    nickname = Column(String(30), nullable=True, unique=True, index=True)
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

    # 계정 상태 (탈퇴/차단)
    is_active = Column(Boolean, default=True, nullable=False, server_default="true")
    withdrawn_at = Column(DateTime, nullable=True)
    is_banned = Column(Boolean, default=False, nullable=False, server_default="false")
    banned_until = Column(DateTime, nullable=True)
    ban_reason = Column(Text, nullable=True)

    # 생년월일 / 성별
    birth_date = Column(DateTime, nullable=True)
    gender = Column(String, nullable=True)

    # (NEW) 나를 데려온 Actuator (없을 수도 있음)
    actuator_id = Column(Integer, ForeignKey("actuators.id"), nullable=True)

    # 판매자 서류 (신규 — nullable)
    ecommerce_permit_number = Column(String(50), nullable=True)
    bank_name               = Column(String(50), nullable=True)
    account_number          = Column(String(50), nullable=True)
    account_holder          = Column(String(50), nullable=True)
    business_license_image  = Column(Text, nullable=True)
    ecommerce_permit_image  = Column(Text, nullable=True)
    bankbook_image          = Column(Text, nullable=True)

    # 외부 평점 (JSON 문자열)
    external_ratings = Column(Text, nullable=True)

    # 배송 정책 (JSON)
    shipping_policy = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)

    # 소셜 로그인
    social_provider = Column(String(20), nullable=True)
    social_id = Column(String(100), nullable=True)

    # 비밀번호 재설정 토큰
    reset_token = Column(String(64), nullable=True, index=True)
    reset_token_expires_at = Column(DateTime, nullable=True)

    # 세금계산서용 사업자 추가 정보
    representative_name = Column(String(50), nullable=True)    # 대표자명
    business_type = Column(String(100), nullable=True)         # 업태
    business_item = Column(String(100), nullable=True)         # 종목
    tax_invoice_email = Column(String(100), nullable=True)     # 세금계산서 수신 이메일
    business_verified = Column(Boolean, default=False)         # 사업자 인증 여부
    business_registered_at = Column(DateTime, nullable=True)   # 사업자 등록일
    business_updated_at = Column(DateTime, nullable=True)      # 사업자 정보 수정일

    # FCM 푸시 토큰
    fcm_token = Column(String(500), nullable=True)
    fcm_updated_at = Column(DateTime, nullable=True)

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
    password_hash = Column(String(255), nullable=True)
    nickname = Column(String(50), nullable=True)

    # 정산 계좌
    bank_name = Column(String(100), nullable=True)
    account_number = Column(String(100), nullable=True)
    account_holder = Column(String(100), nullable=True)
    bankbook_image = Column(Text, nullable=True)

    # 사업자 정보 (is_business=True 일 때만 유효)
    is_business = Column(Boolean, default=False, nullable=False, server_default="false")
    business_name = Column(String(255), nullable=True)
    business_number = Column(String(50), nullable=True)
    ecommerce_permit_number = Column(String(100), nullable=True)
    business_address = Column(String(500), nullable=True)
    business_zip_code = Column(String(20), nullable=True)
    company_phone = Column(String(50), nullable=True)
    business_license_image = Column(Text, nullable=True)
    ecommerce_permit_image = Column(Text, nullable=True)

    # 이 Actuator가 받은 커미션들
    commissions = relationship("ActuatorCommission", backref="actuator")

    # 소셜 로그인
    social_provider = Column(String(20), nullable=True)
    social_id = Column(String(100), nullable=True)

    # 비밀번호 재설정 토큰
    reset_token = Column(String(64), nullable=True, index=True)
    reset_token_expires_at = Column(DateTime, nullable=True)

    # 세금계산서용 사업자 추가 정보
    representative_name = Column(String(50), nullable=True)
    business_type = Column(String(100), nullable=True)
    business_item = Column(String(100), nullable=True)
    tax_invoice_email = Column(String(100), nullable=True)
    business_verified = Column(Boolean, default=False)

    # 위탁계약서 동의
    contract_agreed = Column(Boolean, default=False)
    contract_agreed_at = Column(DateTime, nullable=True)
    contract_version = Column(String(20), nullable=True)

    # 원천징수 (개인 액추에이터)
    withholding_tax_rate = Column(Float, default=0.033)
    resident_id_last = Column(String(10), nullable=True)

    # FCM 푸시 토큰
    fcm_token = Column(String(500), nullable=True)
    fcm_updated_at = Column(DateTime, nullable=True)

    # ACTIVE / SUSPENDED / CLOSED
    status = Column(String(20), nullable=False, default="ACTIVE")

    # 정산 관련 메모/계좌 정보 (단순 문자열로 저장해두고, 나중에 구조화해도 됨)
    settlement_info = Column(String(512), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    withdrawn_at = Column(DateTime, nullable=True)

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

    # --- pricing guardrail (Target vs Anchor) ---
    anchor_price = Column(Float, nullable=True)                 # async anchor, may be None
    market_price = Column(Float, nullable=True)                  # 시장가 (네이버/AI 기준)
    anchor_confidence = Column(Float, nullable=True, default=1.0)
    evidence_score = Column(Integer, nullable=True, default=0)  # 0~100

    # --- AI Helper 추출 필드 ---
    brand = Column(String, nullable=True)                       # 브랜드명 (AI Helper 추출)
    model_number = Column(String, nullable=True)                # 모델번호 (AI Helper 추출)
    options = Column(Text, nullable=True)                       # 옵션 JSON 문자열 (AI Helper 추출)

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

    # --- 신규 상품 정보 필드 ---
    category = Column(String, nullable=True)
    product_detail = Column(String, nullable=True)       # 제품명 (상세)
    product_code = Column(String, nullable=True)          # 제품코드/모델번호
    condition = Column(String, nullable=True, default="new")  # new/refurbished

    # --- 딜 조건 (DealConditions, AI Helper에서 추출) ---
    shipping_fee_krw = Column(Integer, nullable=True)   # 무료배송=0, null=미입력
    refund_days      = Column(Integer, nullable=True)   # 환불 가능 기간(일)
    warranty_months  = Column(Integer, nullable=True)   # 보증 기간(월)
    delivery_days    = Column(Integer, nullable=True)   # 배송 소요일
    extra_conditions = Column(Text,    nullable=True)   # 기타 조건 자유 텍스트

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
    price_evidence = Column(Text, nullable=True)  # JSON: 가격 근거 (채택/제외 상품 목록)


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
        server_default="false",
    )

    # JSON 메타 문자열 (role, deal_id, offer_id 등)
    meta_json = Column(Text)

    # 관련 엔티티 ID (검색/필터용)
    deal_id = Column(Integer, nullable=True)
    offer_id = Column(Integer, nullable=True)
    reservation_id = Column(Integer, nullable=True)
    settlement_id = Column(Integer, nullable=True)

    # 채널별 발송 결과
    sent_app = Column(Boolean, default=False, server_default="false")
    sent_push = Column(Boolean, default=False, server_default="false")
    sent_email = Column(Boolean, default=False, server_default="false")

    __table_args__ = (
        Index("ix_notif_user_read", "user_id", "is_read"),
        Index("ix_notif_user_created", "user_id", "created_at"),
    )

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
    blocked = Column(Boolean, nullable=False, default=False, server_default="false")
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
    delivered_at = Column(DateTime(timezone=True), nullable=True)           # 택배사 기준 "배달완료" 시각
    arrival_confirmed_at = Column(DateTime(timezone=True), nullable=True)   # 바이어가 "도착완료" 누른 시각
    # 배송 추적 확장
    delivery_status = Column(String(30), nullable=True)                     # READY/COLLECTING/IN_TRANSIT/OUT_FOR_DELIVERY/DELIVERED/FAILED
    delivery_last_detail = Column(Text, nullable=True)                      # 최근 배송 상세 (JSON)
    delivery_last_checked_at = Column(DateTime(timezone=True), nullable=True)  # 마지막 조회 시각
    auto_confirm_deadline = Column(DateTime(timezone=True), nullable=True)  # 자동 구매확정 기한
    # 🔼🔼🔼

        # ✅ 분쟁 상태 (SSOT 추천)
    is_disputed = Column(Boolean, nullable=False, default=False, server_default="false")
    dispute_opened_at = Column(DateTime(timezone=True), nullable=True)
    dispute_closed_at = Column(DateTime(timezone=True), nullable=True)
    dispute_reason = Column(String(500), nullable=True)
    dispute_resolution = Column(String(500), nullable=True)
    dispute_admin_id = Column(Integer, nullable=True)


    refund_type = Column(String(20), nullable=True)  # refund, return, exchange

    idempotency_key = Column(String, unique=True, index=True, nullable=True)

    # 주문번호 (YP-YYYYMMDD-NNNN)
    order_number = Column(String(20), unique=True, nullable=True, index=True)

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

    delivery_auto_confirmed = Column(Boolean, default=False, nullable=False, server_default="false")
    delivery_confirmed_source = Column(String(50), nullable=True)  # "batch_auto" | "buyer_manual"

    # ── 환불/교환 자동화 추가 필드 ──
    shipping_mode = Column(String(20), nullable=True, default="free")  # free / buyer_paid / conditional_free
    pg_transaction_id = Column(String(200), nullable=True)

    __table_args__ = (
        Index("ix_resv_offer_status", "offer_id", "status"),
        Index("ix_resv_buyer_status", "buyer_id", "status"),
        Index("ix_resv_deal_status", "deal_id", "status"),
        CheckConstraint("qty > 0", name="ck_reservation_qty_positive"),
    )


# ---- helpers: policy_snapshot_json을 dict로 다루기 ----
    def get_policy_snapshot(self) -> dict:
        raw = getattr(self, "policy_snapshot_json", None)
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            s = raw.strip()
            if not s:
                return {}
            try:
                return json.loads(s)
            except Exception:
                return {}
        return {}

    def set_policy_snapshot(self, data: dict) -> None:
        try:
            self.policy_snapshot_json = json.dumps(data, ensure_ascii=False)
        except Exception:
            # 최후 방어: 그래도 문자열로
            self.policy_snapshot_json = str(data)



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

    __table_args__ = (
        Index("ix_settlement_seller_status", "seller_id", "status"),
        Index("ix_settlement_status_created", "status", "created_at"),
    )


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


# -------------------------------------------------------
# 💬 CustomerInquiry (고객 문의)
# -------------------------------------------------------
class CustomerInquiry(Base):
    __tablename__ = "customer_inquiries"
    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("buyers.id"), nullable=False)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=True)
    category = Column(String(50), default="general")  # general, shipping, refund, product
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(20), default="open")  # open, answered, closed
    seller_reply = Column(Text, nullable=True)
    replied_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


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
    SETTLE_BATCH = "SETTLE_BATCH"
    SETTLE_BATCH_VIEW = "SETTLE_BATCH_VIEW"
    SETTLE_PAID = "SETTLE_PAID"
    SETTLE_REQUESTED = "SETTLE_REQUESTED"
    SETTLE_APPROVED = "SETTLE_APPROVED"
    SETTLE_FAILED = "SETTLE_FAILED"


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




# -------------------------------------------------------
# 👁 Spectator 관전자 시스템
# -------------------------------------------------------

class SpectatorPrediction(Base):
    __tablename__ = "spectator_predictions"

    id              = Column(Integer, primary_key=True, index=True)
    deal_id         = Column(Integer, ForeignKey("deals.id"), nullable=False)
    buyer_id        = Column(Integer, ForeignKey("buyers.id"), nullable=False)
    predicted_price = Column(Integer, nullable=False)
    comment         = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)

    # 판정 결과 (settle 후 채워짐)
    settled_price   = Column(Integer, nullable=True)
    error_pct       = Column(Float, nullable=True)
    tier_name       = Column(String(20), nullable=True)
    points_earned   = Column(Integer, default=0)
    settled_at      = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("deal_id", "buyer_id", name="uq_spectator_once_per_deal"),
        Index("ix_spectator_deal", "deal_id"),
        Index("ix_spectator_buyer", "buyer_id"),
    )


class SpectatorMonthlyStats(Base):
    __tablename__ = "spectator_monthly_stats"

    id                = Column(Integer, primary_key=True, index=True)
    buyer_id          = Column(Integer, ForeignKey("buyers.id"), nullable=False)
    year_month        = Column(String(7), nullable=False)   # "2026-02"
    total_points      = Column(Integer, default=0)
    predictions_count = Column(Integer, default=0)
    hits_count        = Column(Integer, default=0)
    exact_count       = Column(Integer, default=0)
    avg_error_pct     = Column(Float, nullable=True)
    rank_tier         = Column(String(20), nullable=True)
    bonus_points      = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("buyer_id", "year_month", name="uq_spectator_stats_monthly"),
        Index("ix_spectator_stats_ym", "year_month"),
    )


class SpectatorBadge(Base):
    __tablename__ = "spectator_badges"

    id         = Column(Integer, primary_key=True, index=True)
    buyer_id   = Column(Integer, ForeignKey("buyers.id"), nullable=False)
    badge_type = Column(String(30), nullable=False)
    year_month = Column(String(7), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("buyer_id", "badge_type", "year_month", name="uq_badge_monthly"),
    )


class DealViewer(Base):
    __tablename__ = "deal_viewers"

    id        = Column(Integer, primary_key=True, index=True)
    deal_id   = Column(Integer, ForeignKey("deals.id"), nullable=False)
    buyer_id  = Column(Integer, ForeignKey("buyers.id"), nullable=False)
    viewed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("deal_id", "buyer_id", name="uq_deal_viewer_once"),
        Index("ix_deal_viewer_deal", "deal_id"),
    )


# ── 신고/클레임 ──────────────────────────────────────────
class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    reporter_id = Column(Integer, nullable=False)
    reporter_type = Column(String(20), nullable=False)   # buyer/seller/actuator
    target_type = Column(String(20), nullable=False)     # deal/offer/seller/buyer/reservation
    target_id = Column(Integer, nullable=False)
    category = Column(String(30), nullable=False)        # fraud/abuse/defective/not_delivered/other
    description = Column(Text, nullable=True)
    status = Column(String(20), default="OPEN", nullable=False)  # OPEN/IN_REVIEW/RESOLVED/DISMISSED
    resolution = Column(Text, nullable=True)
    action_taken = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_report_reporter", "reporter_id", "reporter_type"),
        Index("ix_report_target", "target_type", "target_id"),
        Index("ix_report_status", "status"),
    )


# ── 파일 업로드 ───────────────────────────────────────────
class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(30), nullable=False)   # deal/offer/buyer/seller
    entity_id = Column(Integer, nullable=False)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    uploaded_by_id = Column(Integer, nullable=True)
    uploaded_by_type = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_uploaded_file_entity", "entity_type", "entity_id"),
    )


# ── 정산 지급 요청 ────────────────────────────────────────
class PayoutRequest(Base):
    __tablename__ = "payout_requests"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(50), nullable=False)
    settlement_id = Column(Integer, ForeignKey("reservation_settlements.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    bank_code = Column(String(10), nullable=True)
    account_number = Column(String(30), nullable=True)
    account_holder = Column(String(50), nullable=True)
    status = Column(String(20), default="PENDING", nullable=False)  # PENDING/REQUESTED/SUCCESS/FAILED
    requested_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    pg_transaction_id = Column(String(100), nullable=True)
    failure_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_payout_batch", "batch_id"),
        Index("ix_payout_status", "status"),
        Index("ix_payout_seller", "seller_id"),
    )


# ── 정책 제안서 ───────────────────────────────────────────
class PolicyProposal(Base):
    __tablename__ = "policy_proposals"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    proposal_type = Column(String(50), nullable=False)   # rate_change/threshold_change/new_rule/remove_rule
    target_param = Column(String(200), nullable=True)
    current_value = Column(Text, nullable=True)
    proposed_value = Column(Text, nullable=True)
    anomaly_alerts = Column(Text, nullable=True)          # JSON
    evidence_summary = Column(Text, nullable=True)
    status = Column(String(30), default="PROPOSED", nullable=False)  # PROPOSED/UNDER_REVIEW/APPROVED/APPLIED/REJECTED/ROLLED_BACK
    proposed_at = Column(DateTime, default=datetime.utcnow)
    proposed_by = Column(String(100), default="pingpong_auto")
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    review_note = Column(Text, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    rolled_back_at = Column(DateTime, nullable=True)
    rollback_reason = Column(Text, nullable=True)
    yaml_snapshot_before = Column(Text, nullable=True)
    yaml_snapshot_after = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_policy_proposal_status", "status"),
    )


def _json_type():
    """
    ✅ SQLite 등에서는 JSON, Postgres에서는 JSONB가 되도록 호환 타입 사용
    - 핵심: JSON().with_variant(JSONB(), "postgresql")
    """
    return JSON().with_variant(JSONB(), "postgresql")


class PingpongCase(Base):
    __tablename__ = "pingpong_cases"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    case_type = Column(String(16), nullable=False, default="qa")  # qa / outcome
    intent = Column(String(64), nullable=True, index=True)
    screen = Column(String(64), nullable=True, index=True)
    locale = Column(String(8), nullable=True)

    actor_kind = Column(String(16), nullable=True)

    # signature / outcome / safe_summary는 PII 없는 JSON
    signature_json = Column(_json_type(), nullable=True)
    outcome_json = Column(_json_type(), nullable=True)
    safe_summary_json = Column(_json_type(), nullable=True)

    fingerprint_text = Column(Text, nullable=True)

    # 임베딩(없으면 null). pgvector 없다고 가정 → float list를 JSON으로 저장
    embedding_json = Column(_json_type(), nullable=True)

    last_score = Column(Float, nullable=True)

    stage = Column(String(32), nullable=True, index=True)
    cancel_rule = Column(String(16), nullable=True, index=True)


# -------------------------------------------------------
# Announcement (공지사항)
# -------------------------------------------------------
class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    category = Column(String(30), default="general")
    is_pinned = Column(Boolean, default=False)
    is_published = Column(Boolean, default=False)
    target_role = Column(String(20), default="all")
    author = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# -------------------------------------------------------
# UserBehaviorLog (행동 수집)
# -------------------------------------------------------
class UserBehaviorLog(Base):
    __tablename__ = "user_behavior_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String(20))  # BUYER / SELLER / ACTUATOR
    user_id = Column(Integer, index=True)
    action = Column(String(50), index=True)
    target_type = Column(String(30), nullable=True)
    target_id = Column(Integer, nullable=True)
    target_name = Column(String(200), nullable=True)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)


# -------------------------------------------------------
# UserProfile (AI 프로파일링 결과)
# -------------------------------------------------------
class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String(20))
    user_id = Column(Integer, index=True)
    profile_json = Column(Text)
    analyzed_at = Column(DateTime, nullable=True)
    behavior_count = Column(Integer, server_default="0")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())


# -------------------------------------------------------
# 🧾 세금계산서 (Tax Invoice)
# -------------------------------------------------------
class TaxInvoiceStatus(str, enum.Enum):
    PENDING = "PENDING"       # 생성됨, 확인 대기
    CONFIRMED = "CONFIRMED"   # 판매자 확인 완료
    ISSUED = "ISSUED"         # 발행 완료
    CANCELLED = "CANCELLED"   # 취소


class TaxInvoice(Base):
    __tablename__ = "tax_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(30), unique=True, index=True)  # YP-YYYYMMDD-NNNNNN

    status = Column(SAEnum(TaxInvoiceStatus, name="taxinvoicestatus"),
                    default=TaxInvoiceStatus.PENDING, nullable=False)

    # 공급자 (텔러스테크 — 고정값)
    supplier_business_name = Column(String(100), nullable=False)
    supplier_business_number = Column(String(20), nullable=False)
    supplier_representative = Column(String(50), nullable=False)
    supplier_address = Column(String(200), nullable=False)
    supplier_email = Column(String(100), nullable=True)

    # 공급받는 자 (판매자/액추에이터)
    recipient_type = Column(String(10), nullable=False)  # "seller" / "actuator"
    recipient_id = Column(Integer, nullable=False)
    recipient_business_name = Column(String(100), nullable=True)
    recipient_business_number = Column(String(20), nullable=True)
    recipient_representative = Column(String(50), nullable=True)
    recipient_address = Column(String(200), nullable=True)
    recipient_email = Column(String(100), nullable=True)
    recipient_business_type = Column(String(100), nullable=True)
    recipient_business_item = Column(String(100), nullable=True)

    # 금액
    settlement_id = Column(Integer, ForeignKey("reservation_settlements.id"), nullable=False)
    total_amount = Column(Integer, nullable=False)    # 수수료 총액 (VAT 포함)
    supply_amount = Column(Integer, nullable=False)   # 공급가액
    tax_amount = Column(Integer, nullable=False)      # 세액

    # 날짜
    issued_at = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    notes = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_tax_invoice_recipient", "recipient_type", "recipient_id"),
        Index("ix_tax_invoice_status", "status"),
    )


# -------------------------------------------------------
# 📋 사업자 정보 변경 이력
# -------------------------------------------------------
class BusinessInfoChangeLog(Base):
    __tablename__ = "business_info_change_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_type = Column(String(20), nullable=False)   # "seller" / "actuator"
    user_id = Column(Integer, nullable=False)
    field_name = Column(String(50), nullable=False)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    changed_by = Column(String(50), nullable=True)   # "self" / "admin" / "ocr"
    changed_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_biz_change_log_user", "user_type", "user_id"),
    )


# -------------------------------------------------------
# 📌 UserInterest — 사용자 관심 카테고리/제품/모델
# -------------------------------------------------------
class UserInterest(Base):
    __tablename__ = "user_interests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    role = Column(String(20), nullable=True)           # buyer / seller / actuator
    level = Column(String(20), default="general")      # category / product / model / general
    value = Column(String(200), nullable=False)
    source = Column(String(10), default="custom")      # preset / custom
    priority = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_user_interest_user", "user_id"),
    )


# -------------------------------------------------------
# 🔔 NotificationSetting — 사용자별 알림 채널 설정
# -------------------------------------------------------
class NotificationSetting(Base):
    __tablename__ = "notification_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    channel_app = Column(Boolean, default=True)
    channel_push = Column(Boolean, default=False)
    channel_email = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_notif_setting_user_event", "user_id", "event_type", unique=True),
    )


# -------------------------------------------------------
# 📊 CustomReportTemplate — 커스텀 리포트 빌더 템플릿
# -------------------------------------------------------
class CustomReportTemplate(Base):
    __tablename__ = "custom_report_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    fields = Column(Text, nullable=False)  # JSON array of field keys
    created_by = Column(String(50), nullable=True)  # admin email or "system"
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


# -------------------------------------------------------
# 📧 PreRegister — 사전 등록 이메일 (출시 전 랜딩)
# -------------------------------------------------------
class PreRegister(Base):
    __tablename__ = "pre_registers"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(200), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# -------------------------------------------------------
# UserConditionOverride — 참여자별 예외 조건 (관리자 설정)
# -------------------------------------------------------
class UserConditionOverride(Base):
    __tablename__ = "user_condition_overrides"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    fee_rate_override = Column(Float, nullable=True)
    cooling_days_override = Column(Integer, nullable=True)
    settlement_days_override = Column(Integer, nullable=True)
    shipping_support = Column(Boolean, default=False)
    level_override = Column(Integer, nullable=True)

    pending_changes = Column(Text, nullable=True)
    effective_after = Column(String(50), nullable=True)

    modified_by = Column(Integer, nullable=True)
    modified_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


# -------------------------------------------------------
# EcountMapping — ECOUNT 거래처/품목 코드 매핑 (추후 API용)
# -------------------------------------------------------
class EcountMapping(Base):
    __tablename__ = "ecount_mappings"

    id = Column(Integer, primary_key=True, index=True)
    mapping_type = Column(String(20), nullable=False)  # 'partner' | 'item'
    internal_id = Column(Integer, nullable=False)
    ecount_code = Column(String(50), nullable=True)
    name = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================
# 돈쭐 (착한 가게 응원 시스템)
# ============================================================

class DonzzulActuator(Base):
    """돈쭐 히어로 (착한 가게 발굴 액츄에이터)"""
    __tablename__ = "donzzul_actuators"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("buyers.id"), nullable=False)
    actuator_id = Column(Integer, ForeignKey("actuators.id"), nullable=True)

    hero_level = Column(String(20), default="sprout")
    total_stores = Column(Integer, default=0)
    total_points = Column(Integer, default=0)

    status = Column(String(20), default="ACTIVE")
    banned_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DonzzulStore(Base):
    """돈쭐 가게 (착한 가게)"""
    __tablename__ = "donzzul_stores"

    id = Column(Integer, primary_key=True, index=True)

    store_name = Column(String(200), nullable=False)
    store_address = Column(String(500), nullable=False)
    store_phone = Column(String(20), nullable=False)
    store_lat = Column(Float, nullable=True)
    store_lng = Column(Float, nullable=True)
    store_photos = Column(Text, nullable=True)
    store_category = Column(String(50), nullable=True)

    owner_name = Column(String(50), nullable=False)
    owner_phone = Column(String(20), nullable=False)
    owner_consent = Column(Boolean, default=False)
    owner_consent_at = Column(DateTime, nullable=True)
    owner_consent_method = Column(String(20), nullable=True)
    owner_consent_revoked = Column(Boolean, default=False)
    owner_consent_revoked_at = Column(DateTime, nullable=True)

    business_number = Column(String(20), nullable=True)
    business_cert_image = Column(String(500), nullable=True)

    bank_name = Column(String(50), nullable=False)
    account_number = Column(String(50), nullable=False)
    account_holder = Column(String(50), nullable=False)
    account_verified = Column(Boolean, default=False)

    store_pin_hash = Column(String(200), nullable=True)
    store_pin_set_at = Column(DateTime, nullable=True)

    story_text = Column(Text, nullable=False)
    youtube_url = Column(String(500), nullable=True)

    registered_by = Column(Integer, ForeignKey("donzzul_actuators.id"), nullable=True)
    verified_by = Column(Integer, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verification_notes = Column(Text, nullable=True)

    status = Column(String(20), default="REVIEWING")

    vote_attempts = Column(Integer, default=0)
    consecutive_fails = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DonzzulDeal(Base):
    """돈쭐 딜 (착한 가게 응원 캠페인)"""
    __tablename__ = "donzzul_deals"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("donzzul_stores.id"), nullable=False)
    week_id = Column(Integer, ForeignKey("donzzul_vote_weeks.id"), nullable=True)

    title = Column(String(200), nullable=False)
    rank = Column(Integer, nullable=True)

    target_amount = Column(Integer, nullable=True)
    current_amount = Column(Integer, default=0)
    voucher_count = Column(Integer, default=0)

    starts_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    status = Column(String(20), default="OPEN")

    created_by = Column(Integer, ForeignKey("donzzul_actuators.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DonzzulVoucher(Base):
    """돈쭐 상품권"""
    __tablename__ = "donzzul_vouchers"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)

    deal_id = Column(Integer, ForeignKey("donzzul_deals.id"), nullable=False)
    store_id = Column(Integer, ForeignKey("donzzul_stores.id"), nullable=False)
    buyer_id = Column(Integer, nullable=False)

    amount = Column(Integer, nullable=False)
    remaining_amount = Column(Integer, nullable=False)

    pin_hash = Column(String(200), nullable=False)
    pin_attempts = Column(Integer, default=0)
    pin_locked_until = Column(DateTime, nullable=True)

    cheer_message = Column(String(200), nullable=True)

    gifted_to = Column(Integer, nullable=True)
    gifted_at = Column(DateTime, nullable=True)

    status = Column(String(20), default="ACTIVE")

    used_at = Column(DateTime, nullable=True)
    used_location_lat = Column(Float, nullable=True)
    used_location_lng = Column(Float, nullable=True)

    expires_at = Column(DateTime, nullable=False)

    pg_transaction_id = Column(String(100), nullable=True)
    pg_fee = Column(Integer, default=0)

    settlement_id = Column(Integer, ForeignKey("donzzul_settlements.id"), nullable=True)
    donated_at = Column(DateTime, nullable=True)
    last_warning_days = Column(Integer, nullable=True)

    refunded_at = Column(DateTime, nullable=True)
    refund_reason = Column(String(100), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class DonzzulVoteWeek(Base):
    """돈쭐 주간 투표"""
    __tablename__ = "donzzul_vote_weeks"

    id = Column(Integer, primary_key=True, index=True)

    week_label = Column(String(100), nullable=False)
    vote_start = Column(DateTime, nullable=False)
    vote_end = Column(DateTime, nullable=False)

    candidates = Column(Text, nullable=True)

    rank_1_store_id = Column(Integer, nullable=True)
    rank_2_store_id = Column(Integer, nullable=True)
    rank_3_store_id = Column(Integer, nullable=True)

    total_votes = Column(Integer, default=0)
    status = Column(String(20), default="UPCOMING")

    announced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DonzzulVote(Base):
    """돈쭐 투표"""
    __tablename__ = "donzzul_votes"

    id = Column(Integer, primary_key=True, index=True)
    week_id = Column(Integer, ForeignKey("donzzul_vote_weeks.id"), nullable=False)
    voter_id = Column(Integer, nullable=True)
    store_id = Column(Integer, nullable=True)
    weight = Column(Integer, default=1)

    voted_at = Column(DateTime, default=datetime.utcnow)


class DonzzulSettlement(Base):
    """돈쭐 정산"""
    __tablename__ = "donzzul_settlements"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("donzzul_stores.id"), nullable=False)

    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    period_from = Column(DateTime, nullable=True)
    period_to = Column(DateTime, nullable=True)

    total_amount = Column(Integer, default=0)
    total_sales = Column(Integer, default=0)
    total_vouchers = Column(Integer, default=0)
    voucher_count = Column(Integer, default=0)
    used_vouchers = Column(Integer, default=0)
    used_amount = Column(Integer, default=0)
    expired_donated = Column(Integer, default=0)
    donated_amount = Column(Integer, default=0)
    pg_fee_total = Column(Integer, default=0)
    platform_fee = Column(Integer, default=0)
    net_amount = Column(Integer, default=0)
    payout_amount = Column(Integer, default=0)

    top_cheer_messages = Column(Text, nullable=True)

    settled_at = Column(DateTime, nullable=True)
    approved_by = Column(Integer, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    bank_name = Column(String(50), nullable=True)
    account_number = Column(String(50), nullable=True)
    account_holder = Column(String(50), nullable=True)

    notified_via = Column(String(20), nullable=True)
    notified_at = Column(DateTime, nullable=True)

    tax_notice_included = Column(Boolean, default=True)

    status = Column(String(20), default="PENDING")

    created_at = Column(DateTime, default=datetime.utcnow)


class DonzzulChatMessage(Base):
    """돈쭐 응원방 채팅"""
    __tablename__ = "donzzul_chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    deal_id = Column(Integer, ForeignKey("donzzul_deals.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("buyers.id"), nullable=True)
    sender_nickname = Column(String(50), nullable=True)

    message_type = Column(String(20), default="CHEER")
    content = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)


# -------------------------------------------------------
# ⚖️ Dispute (2라운드 AI 중재)
# -------------------------------------------------------
class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, nullable=False)

    initiator_id = Column(Integer, nullable=False)
    respondent_id = Column(Integer, nullable=False)
    initiator_role = Column(String(20))

    category = Column(String(50))
    title = Column(String(200))
    description = Column(Text)
    evidence_urls = Column(Text, default="[]")
    requested_resolution = Column(String(50))
    requested_amount = Column(Integer, nullable=True)

    status = Column(String(30), default="FILED")
    current_round = Column(Integer, default=1)

    r1_respondent_reply = Column(Text, nullable=True)
    r1_respondent_evidence_urls = Column(Text, default="[]")
    r1_respondent_proposal_type = Column(String(50), nullable=True)
    r1_respondent_proposal_amount = Column(Integer, nullable=True)
    r1_respondent_proposal_text = Column(Text, nullable=True)
    r1_respondent_at = Column(DateTime, nullable=True)
    r1_respondent_deadline = Column(DateTime, nullable=True)

    r1_ai_opinion = Column(Text, nullable=True)
    r1_ai_recommendation = Column(String(50), nullable=True)
    r1_ai_recommendation_amount = Column(Integer, nullable=True)
    r1_ai_explanation = Column(Text, nullable=True)
    r1_ai_mediated_at = Column(DateTime, nullable=True)

    r1_initiator_decision = Column(String(20), nullable=True)
    r1_initiator_decision_at = Column(DateTime, nullable=True)
    r1_initiator_deadline = Column(DateTime, nullable=True)
    r1_respondent_decision = Column(String(20), nullable=True)
    r1_respondent_decision_at = Column(DateTime, nullable=True)
    r1_respondent_review_deadline = Column(DateTime, nullable=True)

    r2_rebuttal_by = Column(String(20), nullable=True)
    r2_initiator_rebuttal = Column(Text, nullable=True)
    r2_initiator_evidence_urls = Column(Text, default="[]")
    r2_initiator_proposal_type = Column(String(50), nullable=True)
    r2_initiator_proposal_amount = Column(Integer, nullable=True)
    r2_respondent_rebuttal = Column(Text, nullable=True)
    r2_respondent_evidence_urls = Column(Text, default="[]")
    r2_respondent_proposal_type = Column(String(50), nullable=True)
    r2_respondent_proposal_amount = Column(Integer, nullable=True)
    r2_rebuttal_deadline = Column(DateTime, nullable=True)
    r2_rebuttal_at = Column(DateTime, nullable=True)

    r2_ai_opinion = Column(Text, nullable=True)
    r2_ai_recommendation = Column(String(50), nullable=True)
    r2_ai_recommendation_amount = Column(Integer, nullable=True)
    r2_ai_explanation = Column(Text, nullable=True)
    r2_ai_mediated_at = Column(DateTime, nullable=True)

    r2_initiator_decision = Column(String(20), nullable=True)
    r2_initiator_decision_at = Column(DateTime, nullable=True)
    r2_initiator_deadline = Column(DateTime, nullable=True)
    r2_respondent_decision = Column(String(20), nullable=True)
    r2_respondent_decision_at = Column(DateTime, nullable=True)
    r2_respondent_deadline = Column(DateTime, nullable=True)

    resolution = Column(Text, nullable=True)
    resolution_amount = Column(Integer, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    closed_reason = Column(String(50), nullable=True)

    legal_guidance_sent = Column(Boolean, default=False)
    legal_guidance_sent_at = Column(DateTime, nullable=True)
    timeout_warned = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# -------------------------------------------------------
# 🏪 SellerExternalRating
# -------------------------------------------------------
class SellerExternalRating(Base):
    __tablename__ = "seller_external_ratings"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, nullable=False)
    platform_name = Column(String(50))
    platform_url = Column(String(500), nullable=False)

    claimed_rating = Column(Float, nullable=True)
    claimed_review_count = Column(Integer, nullable=True)
    verified_rating = Column(Float, nullable=True)
    verified_review_count = Column(Integer, nullable=True)
    verification_status = Column(String(20), default="PENDING")
    verification_raw_response = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)

    rating_gap = Column(Float, nullable=True)
    is_trusted = Column(Boolean, default=False)

    last_auto_check_at = Column(DateTime, nullable=True)
    next_auto_check_at = Column(DateTime, nullable=True)
    auto_check_fail_count = Column(Integer, default=0)

    url_dead_detected_at = Column(DateTime, nullable=True)
    url_dead_grace_deadline = Column(DateTime, nullable=True)
    url_dead_notified = Column(Boolean, default=False)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# -------------------------------------------------------
# 🏆 SellerVerificationScore
# -------------------------------------------------------
class SellerVerificationScore(Base):
    __tablename__ = "seller_verification_scores"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, nullable=False)

    score_age = Column(Float, default=0)
    score_rating = Column(Float, default=0)
    score_reviews = Column(Float, default=0)
    score_sentiment = Column(Float, default=0)
    score_trade_cert = Column(Float, default=0)
    score_account = Column(Float, default=0)
    score_biz = Column(Float, default=0)

    total_score = Column(Float, default=0)
    auto_decision = Column(String(30), nullable=True)
    reasons = Column(Text, default="[]")

    seller_message = Column(Text, nullable=True)
    admin_message = Column(Text, nullable=True)
    admin_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# -------------------------------------------------------
# 🔗 ActuatorSellerDisconnection
# -------------------------------------------------------
class ActuatorSellerDisconnection(Base):
    __tablename__ = "actuator_seller_disconnections"

    id = Column(Integer, primary_key=True, index=True)
    actuator_id = Column(Integer, nullable=False)
    seller_id = Column(Integer, nullable=False)

    requested_by = Column(String(20))
    reason = Column(String(50))
    reason_detail = Column(Text, nullable=True)

    status = Column(String(20), default="PENDING")
    grace_period_ends = Column(DateTime, nullable=True)
    cooldown_ends = Column(DateTime, nullable=True)

    confirmed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    agreement_accepted = Column(Boolean, default=False)
    agreement_accepted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)


# -------------------------------------------------------
# 🎮 Arena Models (배틀 아레나 미니게임)
# -------------------------------------------------------

class ArenaPlayer(Base):
    """통합 플레이어 프로필 — 유저당 1행"""
    __tablename__ = "arena_players"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False)
    nickname = Column(String(30), nullable=True)

    # 위치/인구통계
    country = Column(String(10), default="KR")
    region = Column(String(50), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    age_group = Column(String(10), nullable=True)  # 10s, 20s, 30s ...
    gender = Column(String(10), nullable=True)

    # 통합 점수
    total_points = Column(Integer, default=0)
    arena_level = Column(String(20), default="rookie")  # rookie/fighter/champion/legend
    total_games = Column(Integer, default=0)

    # 가위바위보
    rps_wins = Column(Integer, default=0)
    rps_losses = Column(Integer, default=0)
    rps_draws = Column(Integer, default=0)
    rps_streak_best = Column(Integer, default=0)

    # 묵찌빠
    mjb_wins = Column(Integer, default=0)
    mjb_losses = Column(Integer, default=0)

    # 윷놀이
    yut_wins = Column(Integer, default=0)
    yut_losses = Column(Integer, default=0)

    # 수학배틀
    math_best_score = Column(Integer, default=0)
    math_games = Column(Integer, default=0)

    # 상식퀴즈
    quiz_best_score = Column(Integer, default=0)
    quiz_games = Column(Integer, default=0)

    # 반응속도
    reaction_best_ms = Column(Integer, default=0)
    reaction_games = Column(Integer, default=0)

    # 일일 제한
    daily_game_count = Column(Integer, default=0)
    daily_reset_date = Column(String(10), nullable=True)  # YYYY-MM-DD

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ArenaGame(Base):
    """개별 게임 기록"""
    __tablename__ = "arena_games"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("arena_players.id"), index=True, nullable=False)
    game_type = Column(String(20), nullable=False)  # rps, mjb, yut, math, quiz, reaction
    result = Column(String(10), nullable=False)  # win, lose, draw, score
    score = Column(Integer, default=0)
    detail = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    points_earned = Column(Integer, default=0)

    # 위치 (게임 시점 스냅샷)
    country = Column(String(10), nullable=True)
    region = Column(String(50), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    played_at = Column(DateTime, default=datetime.utcnow, index=True)

    player = relationship("ArenaPlayer", backref="games")


class ArenaRegionStats(Base):
    """지역별 집계 통계"""
    __tablename__ = "arena_region_stats"

    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), nullable=False)  # country, region
    country = Column(String(10), nullable=False, index=True)
    region = Column(String(50), nullable=True)

    total_games = Column(Integer, default=0)
    total_players = Column(Integer, default=0)

    # 게임별 승률
    rps_win_rate = Column(Float, default=0.0)
    mjb_win_rate = Column(Float, default=0.0)
    yut_win_rate = Column(Float, default=0.0)
    math_avg_score = Column(Float, default=0.0)
    quiz_avg_score = Column(Float, default=0.0)
    reaction_avg_ms = Column(Float, default=0.0)

    composite_score = Column(Float, default=0.0)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("level", "country", "region", name="uq_arena_region"),
    )


# -------------------------------------------------------
# 🔄 RefundRequest (단순 환불 요청)
# -------------------------------------------------------
class RefundRequest(Base):
    __tablename__ = "refund_requests"

    id = Column(Integer, primary_key=True, index=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False, index=True)
    buyer_id = Column(Integer, ForeignKey("buyers.id"), nullable=False, index=True)

    reason = Column(String(50), nullable=False)
    # buyer_change_mind, defective, wrong_item, damaged, not_delivered, description_mismatch, other
    reason_detail = Column(Text, nullable=True)
    evidence_urls = Column(Text, default="[]")

    status = Column(String(30), default="REQUESTED")
    # REQUESTED → SELLER_APPROVED / SELLER_REJECTED / AUTO_APPROVED
    # → CANCELLED (구매자 취소) / EXPIRED (반품 미발송)

    seller_response = Column(String(20), nullable=True)
    seller_reject_reason = Column(Text, nullable=True)
    seller_response_at = Column(DateTime, nullable=True)
    seller_response_deadline = Column(DateTime, nullable=True)

    resolution_action_id = Column(Integer, ForeignKey("resolution_actions.id", use_alter=True), nullable=True)
    dispute_id = Column(Integer, ForeignKey("disputes.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# -------------------------------------------------------
# ⚖️ ResolutionAction (환불/교환/보상 실행 — 12 시나리오)
# -------------------------------------------------------
class ResolutionAction(Base):
    __tablename__ = "resolution_actions"

    id = Column(Integer, primary_key=True, index=True)

    # 출처
    dispute_id = Column(Integer, ForeignKey("disputes.id"), nullable=True)
    refund_request_id = Column(Integer, ForeignKey("refund_requests.id"), nullable=True)
    reservation_id = Column(Integer, ForeignKey("reservations.id"), nullable=False, index=True)

    # 결과 유형
    resolution_type = Column(String(30), nullable=False)
    # FULL_REFUND, PARTIAL_REFUND, EXCHANGE, COMPENSATION, DISCOUNT, NO_ACTION, PENDING_LEGAL

    # ── 원본 정보 ──
    original_amount = Column(Integer, nullable=True)
    original_shipping_fee = Column(Integer, default=0)
    original_total = Column(Integer, nullable=True)
    shipping_mode = Column(String(20), nullable=True)
    delivery_status = Column(String(20), nullable=True)

    # ── 귀책 ──
    fault = Column(String(20), nullable=True)
    refund_reason = Column(String(50), nullable=True)

    # ── 배송비 ──
    return_shipping_cost = Column(Integer, default=0)
    original_shipping_deduction = Column(Integer, default=0)
    total_shipping_deduction = Column(Integer, default=0)
    shipping_payer = Column(String(20), nullable=True)

    # ── 감가 ──
    usage_deduction = Column(Integer, default=0)
    usage_deduction_rate = Column(Float, default=0)

    # ── 최종 금액 ──
    total_deduction = Column(Integer, default=0)
    buyer_refund_amount = Column(Integer, default=0)
    seller_deduction_amount = Column(Integer, default=0)
    seller_return_shipping_burden = Column(Integer, default=0)
    platform_fee_refund = Column(Integer, default=0)
    compensation_amount = Column(Integer, default=0)

    # ── 상태 머신 ──
    status = Column(String(30), default="PENDING")

    # ── 반품 물류 ──
    return_required = Column(Boolean, default=False)
    return_address = Column(Text, nullable=True)
    return_tracking_number = Column(String(100), nullable=True)
    return_carrier = Column(String(50), nullable=True)
    return_shipped_at = Column(DateTime, nullable=True)
    return_received_at = Column(DateTime, nullable=True)
    return_deadline = Column(DateTime, nullable=True)
    return_expired_notified = Column(Boolean, default=False)

    # ── 검수 ──
    inspection_result = Column(String(20), nullable=True)
    inspection_notes = Column(Text, nullable=True)
    inspected_at = Column(DateTime, nullable=True)

    # ── 교환 ──
    exchange_tracking_number = Column(String(100), nullable=True)
    exchange_carrier = Column(String(50), nullable=True)
    exchange_shipped_at = Column(DateTime, nullable=True)
    exchange_delivered_at = Column(DateTime, nullable=True)
    exchange_ship_deadline = Column(DateTime, nullable=True)

    # ── PG 환불 ──
    pg_refund_requested = Column(Boolean, default=False)
    pg_refund_tx_id = Column(String(200), nullable=True)
    pg_refund_status = Column(String(30), nullable=True)
    pg_refunded_at = Column(DateTime, nullable=True)
    pg_refund_method = Column(String(30), nullable=True)
    pg_refund_retry_count = Column(Integer, default=0)
    pg_refund_error = Column(Text, nullable=True)

    # ── 정산 조정 ──
    settlement_id = Column(Integer, ForeignKey("reservation_settlements.id"), nullable=True)
    settlement_adjusted = Column(Boolean, default=False)
    settlement_adjustment_type = Column(String(20), nullable=True)
    settlement_adjustment_amount = Column(Integer, default=0)
    settlement_before_payout = Column(Integer, nullable=True)
    settlement_after_payout = Column(Integer, nullable=True)

    # ── 세금계산서 ──
    tax_invoice_adjusted = Column(Boolean, default=False)
    tax_invoice_adjustment_note = Column(Text, nullable=True)

    # ── 관리자 ──
    admin_override = Column(Boolean, default=False)
    admin_notes = Column(Text, nullable=True)
    admin_processed_by = Column(Integer, nullable=True)
    escalation_reason = Column(String(200), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


# -------------------------------------------------------
# 💸 ClawbackRecord (이미 지급 정산 회수)
# -------------------------------------------------------
class ClawbackRecord(Base):
    __tablename__ = "clawback_records"

    id = Column(Integer, primary_key=True, index=True)
    settlement_id = Column(Integer, ForeignKey("reservation_settlements.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("sellers.id"), nullable=False, index=True)
    resolution_action_id = Column(Integer, ForeignKey("resolution_actions.id"), nullable=True)

    amount = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)

    status = Column(String(20), default="PENDING")
    # PENDING → DEDUCTED → COMPLETED
    # PENDING → INSUFFICIENT_BALANCE

    deducted_from_settlement_id = Column(Integer, nullable=True)
    remaining_amount = Column(Integer, default=0)
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)

    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)