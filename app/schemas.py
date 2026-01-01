# ===== v3.6 Schemas (DealRound / Offers / Reservations / Points) =====
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator

# Pydantic v2 우선, v1 자동 호환
try:
    from pydantic import BaseModel, Field, ConfigDict, EmailStr
    _V2 = True
except Exception:  # Pydantic v1
    from pydantic import BaseModel, Field  # type: ignore
    from pydantic.networks import EmailStr  # type: ignore
    ConfigDict = dict  # type: ignore
    _V2 = False

# 모델 Enum 재사용 (중복 정의/중복 import 방지)
from app.models import DealRoundStatus, ReservationStatus

from .core.refund_policy import (
    FaultParty,
    RefundTrigger,
    SettlementState,
    CoolingState,
)


# ─────────────────────────────────────────────────────────
# 공통 ORM 베이스: v2는 from_attributes, v1은 orm_mode
# ─────────────────────────────────────────────────────────
if _V2:
    class ORMModel(BaseModel):
        model_config = ConfigDict(from_attributes=True)
else:
    class ORMModel(BaseModel):  # type: ignore[misc]
        class Config:
            from_attributes = True  # orm_mode 대신


# ---------------- Buyer ----------------
class BuyerBase(BaseModel):
    email: EmailStr
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[datetime] = None


class BuyerCreate(BuyerBase):
    password: str
    # (NEW)
    recommender_buyer_id: Optional[int] = Field(
        None,
        description="추천인 Buyer의 ID (선택)"
    )    

class BuyerOut(ORMModel):
    id: int
    created_at: datetime
    points: int
    # BuyerBase 필드도 응답에 포함
    email: EmailStr
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[datetime] = None


# ---------------- Seller ----------------
class SellerBase(BaseModel):
    email: EmailStr
    business_name: str
    business_number: str
    phone: Optional[str] = None
    company_phone: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    established_date: Optional[datetime] = None



class SellerCreate(BaseModel):
    email: EmailStr
    business_name: str
    business_number: str
    phone: str
    company_phone: Optional[str] = None
    address: str
    zip_code: str
    established_date: datetime
    password: str

    # (NEW) 나를 데려온 Actuator ID (선택)
    actuator_id: Optional[int] = Field(
        None,
        description="(선택) 이 판매자를 모집한 Actuator ID",
    )


class SellerOut(BaseModel):
    id: int
    created_at: datetime
    email: EmailStr
    business_name: str
    business_number: str
    phone: str
    company_phone: Optional[str] = None
    address: str
    zip_code: str
    established_date: datetime
    verified_at: Optional[datetime] = None
    level: int
    points: int

    # (NEW)
    actuator_id: Optional[int] = None

    class Config:
        from_attributes = True  # orm_mode 대신
    

#-------------Actuator -----------------------
class ActuatorBase(BaseModel):
    name: str = Field(..., description="표시명 / 상호명")
    email: Optional[str] = Field(None, description="연락 이메일")
    phone: Optional[str] = Field(None, description="연락처(휴대폰 등)")
    settlement_info: Optional[str] = Field(None, description="정산 계좌/메모 등")


class ActuatorCreate(ActuatorBase):
    """Actuator 생성용 입력 스키마"""
    pass


class ActuatorOut(ActuatorBase):
    """응답용 스키마"""
    id: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True  # orm_mode 대신

# ---------- Actuator Commission ----------

class ActuatorCommissionOut(BaseModel):
    id: int
    actuator_id: int
    seller_id: int
    reservation_id: int
    gmv: int
    rate_percent: float
    amount: int
    created_at: datetime

    class Config:
        from_attributes = True  # orm_mode 대체


class ActuatorSellerWithOfferStatsOut(BaseModel):
    # /actuators/{actuator_id}/sellers 응답에서 쓰는 구조
    seller_id: int
    name: Optional[str] = None
    total_offers: int
    confirmed_offers: int
    active_offers: int
    total_sold_qty: int


class ActuatorRewardOut(BaseModel):
    id: int
    actuator_id: int
    seller_id: int
    reservation_id: int
    gmv: int
    fee_percent: float
    reward_amount: int
    created_at: datetime

    class Config:
        from_attributes = True


class ActuatorCommissionSummaryOut(BaseModel):
    # 커미션 요약
    pending_count: int
    pending_amount: int
    ready_count: int
    ready_amount: int
    paid_count: int
    paid_amount: int
    upcoming_ready_dates: Optional[List[datetime]] = None  # 선택


class ActuatorSellerSummaryOut(BaseModel):
    seller_id: int
    name: Optional[str] = None
    total_offers: int
    confirmed_offers: int
    active_offers: int
    total_sold_qty: int
    

# ------------------------------------------------
# Actuator 커미션 관련 스키마
# ------------------------------------------------

class ActuatorCommissionOut(BaseModel):
    id: int
    actuator_id: int
    seller_id: Optional[int] = None
    reservation_id: Optional[int] = None
    amount: int              # 커미션 금액
    status: str              # "PENDING" / "PAID" 등
    ready_at: Optional[datetime] = None  # 정산 가능일
    paid_at: Optional[datetime] = None   # 실제 지급일
    created_at: datetime

    class Config:
        orm_mode = True   # 기존 스키마들 스타일 맞추기


class ActuatorCommissionSummaryOut(BaseModel):
    # 개수 집계
    total_pending: int
    total_ready: int
    total_paid: int

    # 금액 집계
    pending_amount: int
    ready_amount: int
    paid_amount: int

    # 개별 커미션 리스트
    commissions: List[ActuatorCommissionOut] = []

    class Config:
        orm_mode = True



# ---------- DealRound ----------
class DealRoundBase(BaseModel):
    round_no: int = Field(ge=1, description="라운드 번호(1부터 시작 권장)")
    meta: Optional[Dict[str, Any]] = Field(
        default=None, description="라운드별 정책/가이드/가중치 등"
    )
    if _V2:
        model_config = ConfigDict(extra="ignore")
    else:
        class Config:
            extra = "ignore"


class DealRoundCreate(BaseModel):
    round_no: int = Field(..., ge=1)
    meta: Optional[Dict[str, Any]] = None
    if _V2:
        model_config = ConfigDict(extra="ignore")
    else:
        class Config:
            extra = "ignore"


class DealRoundUpdate(BaseModel):
    status: Optional[DealRoundStatus] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    meta: Optional[Dict[str, Any]] = None
    if _V2:
        model_config = ConfigDict(extra="ignore")
    else:
        class Config:
            extra = "ignore"


class DealRoundOut(ORMModel):
    id: int
    deal_id: int
    status: DealRoundStatus
    round_no: int
    meta: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# -------- Deal --------
class DealCreate(BaseModel):
    product_name: str
    creator_id: int
    desired_qty: int = 1
    target_price: Optional[float] = None
    max_budget: Optional[float] = None

    option1_title: Optional[str] = None
    option1_value: Optional[str] = None
    option2_title: Optional[str] = None
    option2_value: Optional[str] = None
    option3_title: Optional[str] = None
    option3_value: Optional[str] = None
    option4_title: Optional[str] = None
    option4_value: Optional[str] = None
    option5_title: Optional[str] = None
    option5_value: Optional[str] = None

    free_text: Optional[str] = None


class DealOut(ORMModel):
    id: int
    product_name: str
    creator_id: int
    desired_qty: int = 1
    target_price: Optional[float] = None
    max_budget: Optional[float] = None
    rounds: List["DealRoundOut"] = Field(default_factory=list)  # forward ref 안전
    created_at: datetime

    # 옵션/자유 텍스트
    option1_title: Optional[str] = None
    option1_value: Optional[str] = None
    option2_title: Optional[str] = None
    option2_value: Optional[str] = None
    option3_title: Optional[str] = None
    option3_value: Optional[str] = None
    option4_title: Optional[str] = None
    option4_value: Optional[str] = None
    option5_title: Optional[str] = None
    option5_value: Optional[str] = None
    free_text: Optional[str] = None


class DealDetail(DealOut):
    # crud.get_deal(s) 에서 반환하는 필드명과 정합성 유지
    current_total_qty: int = 0


# -------- Deal 참여자 --------
class DealParticipantCreate(BaseModel):
    deal_id: int
    buyer_id: int
    qty: int


class DealParticipantOut(ORMModel):
    id: int
    deal_id: int
    buyer_id: int
    qty: int
    created_at: datetime


# Deal 채팅----------------------------------------------------
class DealChatMessageCreate(BaseModel):
    buyer_id: int = Field(..., description="메시지 작성 buyer id")
    text: str = Field(..., max_length=1000, description="채팅 메시지 (최대 1000자)")


class DealChatMessageOut(BaseModel):
    id: int
    deal_id: int
    buyer_id: int

    # 실명 대신 닉네임만 노출
    sender_nickname: str

    text: str
    blocked: bool
    blocked_reason: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True


class DealChatMessageListOut(BaseModel):
    items: List[DealChatMessageOut]
    total: int


# -------- Offer --------
class OfferBase(BaseModel):
    price: float
    total_available_qty: int = Field(..., ge=1)
    # 설명 텍스트: 모델에 comment/free_text 혼재 → 입력은 둘 다 수용
    free_text: Optional[str] = None
    comment: Optional[str] = None


class OfferCreate(OfferBase):
    deal_id: int
    seller_id: int
    delivery_days: Optional[int] = None
    cooling_days: int | None = None


    # ✅ 레거시 호환:
    # - 입력 "NONE" 허용 (기존 클라/스크립트 안 깨짐)
    # - 내부적으로 "INCLUDED"로 표준화해서 내려보냄
    shipping_mode: Optional[str] = Field(
        "NONE",
        description="INCLUDED|PER_RESERVATION|PER_QTY (레거시: NONE도 허용, INCLUDED로 처리)",
    )

    shipping_fee_per_reservation: Optional[int] = Field(
        0,
        ge=0,
        description="PER_RESERVATION일 때 주문당 배송비(0 이상)",
    )
    shipping_fee_per_qty: Optional[int] = Field(
        0,
        ge=0,
        description="PER_QTY일 때 수량당 배송비(0 이상)",
    )

    @field_validator("shipping_mode", mode="before")
    @classmethod
    def _normalize_shipping_mode(cls, v):
        s = (v or "INCLUDED")
        if not isinstance(s, str):
            return "INCLUDED"
        s = s.strip().upper()
        if s in ("NONE", "UNKNOWN", "NULL", ""):
            return "INCLUDED"
        return s

    @model_validator(mode="after")
    def _normalize_shipping_fees(self):
        # None 방어
        self.shipping_fee_per_reservation = int(self.shipping_fee_per_reservation or 0)
        self.shipping_fee_per_qty = int(self.shipping_fee_per_qty or 0)

        mode = (self.shipping_mode or "INCLUDED").upper()

        # ✅ 모드별 정합성 정리
        if mode == "INCLUDED":
            self.shipping_fee_per_reservation = 0
            self.shipping_fee_per_qty = 0
        elif mode == "PER_RESERVATION":
            self.shipping_fee_per_qty = 0
        elif mode == "PER_QTY":
            self.shipping_fee_per_reservation = 0
        else:
            raise ValueError(f"Invalid shipping_mode: {mode}")

        return self


class OfferOut(ORMModel):
    id: int
    deal_id: int
    seller_id: int
    price: float
    total_available_qty: int
    reserved_qty: int = 0
    sold_qty: int = 0
    is_active: bool = True
    is_confirmed: bool = False
    delivery_days: Optional[int] = None
    comment: Optional[str] = None
    created_at: datetime
    deadline_at: Optional[datetime] = None
    shipping_mode: Optional[str] = None
    shipping_fee_per_reservation: Optional[int] = None
    shipping_fee_per_qty: Optional[int] = None


# 하위호환: 기존 코드가 OfferOutExtended를 참조한다면 그대로 동작
class OfferOutExtended(OfferOut):
    pass


#-------------------------------------------------------------
#Offer(오퍼) 취소,반품, 환불 정책 관련
#--------------------------------------------------------------
class OfferPolicyBase(BaseModel):
    """
    오퍼 취소 정책 기본 스키마

    - cancel_rule:
      * A1: 발송 전까지 취소 가능
      * A2: 발송 후 취소 불가
      * A3: 발송 후 X일 이내 취소 가능
      * A4: Seller 커스텀 규칙 (텍스트 참고)
    - cancel_within_days:
      * A3일 때만 1~30 사이 정수
    - extra_text:
      * 최대 1000자, 셀러가 텍스트로 정책 설명
    """

    cancel_rule: Literal["A1", "A2", "A3", "A4"] = Field(
        ...,
        description="A1/A2/A3/A4 취소 규칙 코드",
    )
    cancel_within_days: Optional[int] = Field(
        None,
        ge=1,
        le=30,
        description="A3(발송 후 X일 이내 취소 가능)일 때만 1~30 입력",
    )
    extra_text: Optional[str] = Field(
        None,
        max_length=1000,
        description="추가 취소/환불 정책 텍스트 (최대 1000자)",
    )


class OfferPolicyCreate(OfferPolicyBase):
    """오퍼 정책 생성/수정용 입력 스키마"""
    pass


class OfferPolicyOut(OfferPolicyBase):
    """오퍼 정책 조회 응답 스키마"""

    id: int
    offer_id: int
    created_at: datetime

    class Config:
        orm_mode = True  # v2에서도 from_attributes로 자동 매핑


class ReservationRefundIn(BaseModel):
    reservation_id: int
    quantity_refund: Optional[int] = None
    reason: str = Field(..., max_length=200)
    requested_by: Literal["BUYER", "SELLER", "ADMIN"] = "BUYER"

    # ✅ 추가: 배송비 환불 override (관리자만 허용할 예정)
    shipping_refund_override: Optional[int] = Field(
        None,
        ge=0,
        description="배송비 환불액 override(원). ADMIN만 사용 권장",
    )
    shipping_refund_override_reason: Optional[str] = Field(
        None,
        max_length=200,
        description="override 사유(감사/분쟁 대비)",
    )

    
class RefundPreviewContextOut(BaseModel):
    reservation_id: int
    deal_id: Optional[int]
    offer_id: Optional[int]
    buyer_id: int
    seller_id: Optional[int]

    amount_total: int
    amount_goods: int
    amount_shipping: int

    quantity_total: int
    quantity_refund: int

    fault_party: FaultParty
    trigger: RefundTrigger
    settlement_state: SettlementState
    cooling_state: CoolingState

    pg_fee_rate: float
    platform_fee_rate: float

    class Config:
        orm_mode = True


class RefundPreviewDecisionOut(BaseModel):
    use_pg_refund: bool

    pg_fee_burden: Optional[FaultParty]
    platform_fee_burden: Optional[FaultParty]

    revoke_buyer_points: bool
    revoke_seller_points: bool

    need_settlement_recovery: bool
    settlement_recovery_from_seller: bool

    note: str = ""

    class Config:
        orm_mode = True


class RefundPreviewOut(BaseModel):
    reservation_id: int
    context: RefundPreviewContextOut
    decision: RefundPreviewDecisionOut

    class Config:
        orm_mode = True


class ReservationRefundPreviewIn(BaseModel):
    reservation_id: int
    actor: str = "buyer_cancel"
    # ★ 부분환불 수량 (옵션, 없으면 전체환불로 간주)
    quantity_refund: Optional[int] = None



class ReservationPolicySnapshot(BaseModel):
    """
    Reservation 에 저장된 policy_snapshot_json 을 파싱해서 내려줄 스키마.
    구조는 OfferPolicyOut 과 거의 동일하지만, created_at 은 문자열일 수도 있음.
    """

    cancel_rule: Literal["A1", "A2", "A3", "A4"]
    cancel_within_days: Optional[int] = None
    extra_text: Optional[str] = None

    # 정보 보존용 필드들 (optional)
    id: Optional[int] = None
    offer_id: Optional[int] = None
    created_at: Optional[datetime] = None



# ==== Reservation Schemas ====
class ReservationCreate(BaseModel):
    deal_id: int
    offer_id: int
    buyer_id: int
    qty: int = Field(..., gt=0)
    hold_minutes: Optional[int] = None  #이거 꼭 있어야 위 스크립트 payload가 먹힘.



class ReservationOut(ORMModel):
    id: int
    deal_id: int
    offer_id: int
    buyer_id: int
    qty: int

    status: ReservationStatus
    created_at: datetime
    expires_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None

    # 🔹 배송 정보
    shipping_carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    arrival_confirmed_at: Optional[datetime] = None

    # --- 정책 동의 정보 ---
    policy_id: Optional[int] = None
    policy_agreed_at: Optional[datetime] = None
    policy: Optional[ReservationPolicySnapshot] = None

    # 🆕 상태 단계 정보 (status + 배송정보를 합친 논리 상태)
    phase: Optional[str] = None

    # 💰 금액 정보
    amount_total: int = 0

    # 🧾 부분환불 누적 정보
    refunded_qty: Optional[int] = None
    refunded_amount_total: Optional[int] = None

    class Config:
        orm_mode = True



class ReservationPayIn(BaseModel):
    reservation_id: int
    buyer_id: int
    buyer_point_per_qty: int = 1  # 결제 시 바이어 포인트 기본 +1/수량


class ReservationCancelIn(BaseModel):
    """
    PENDING 예약 취소용 입력 모델
    - buyer_id: 바이어 본인이 취소할 때는 필수로 전달
                운영자 취소면 None 허용
    """
    reservation_id: int
    buyer_id: Optional[int] = None
    # reason 같은 건 있어도 되고 없어도 됨. 지금 로직에는 안 쓰니 생략 가능.


class ReservationShipIn(BaseModel):
    """
    셀러가 '발송 완료' 처리할 때 쓰는 입력 스키마.
    - seller_id 는 선택 (셀러 소유 여부 검증에만 사용)
    """
    seller_id: Optional[int] = None


class ReservationArrivalConfirmIn(BaseModel):
    """
    바이어가 '도착 확인' 버튼 누를 때 쓰는 입력 스키마.
    - buyer_id 는 필수: 본인 예약인지 검증용
    """
    buyer_id: int




# ---------------------------------------------------------
# Reservation Settlement Output
# ---------------------------------------------------------
class ReservationSettlementOut(BaseModel):
    id: int
    reservation_id: int
    seller_id: int

    paid_amount: int
    pg_fee_amount: int
    platform_fee: int
    platform_fee_vat: int
    seller_payout: int

    calc_at: datetime
    status: str

    class Config:
        orm_mode = True


class ReservationRefundSummary(BaseModel):
    reservation_id: int
    status: ReservationStatus

    qty: int                    # 전체 예약 수량
    refunded_qty: int           # 지금까지 환불된 수량
    refundable_qty: int         # 아직 환불 가능한 수량 (max 0..qty)

    unit_price: int             # 단가 (offer.price)
    amount_goods_total: int     # 상품 총액 (qty * unit_price)
    amount_shipping_total: int  # 전체 기준 배송비
    amount_paid_total: int      # 상품 + 배송 총액

    refunded_amount_total: int  # 지금까지 환불된 금액
    refundable_amount_max: int  # 남은 수량 전체를 환불한다고 가정했을 때 최대 환불 금액




# ---- Seller Offer Control DTOs ----
class SellerOfferConfirmIn(BaseModel):
    # True면 전량 판매가 아니어도 확정(포인트는 부여 안 함)
    force: bool = False


class SellerOfferCancelIn(BaseModel):
    # 셀러 -30pt 부여 여부
    penalize: bool = True
    # 결제건이 있어도 취소 허용(내부 롤백 및 포인트 상쇄)
    allow_paid: bool = True
    # 바이어에게 적립된 포인트를 음수 트랜잭션으로 상쇄할지
    reverse_buyer_points: bool = True
    # 상쇄 시 사용할 1EA당 포인트
    buyer_point_per_qty: int = 1


# -------- Point 관련 --------
class PointTransactionCreate(BaseModel):
    user_type: str  # "buyer" | "seller"
    user_id: int
    amount: int      # +적립 / -차감
    reason: Optional[str] = None


class PointTransactionOut(ORMModel):
    id: int
    user_type: str
    user_id: int
    amount: int
    reason: Optional[str]
    created_at: datetime


class PointTransactionBalance(BaseModel):
    user_type: str
    user_id: int
    balance: int


# ---------- 라운드 제어 DTO ----------
class DealRoundAction(str):
    OPEN = "OPEN"
    FINALIZE = "FINALIZE"
    CLOSE = "CLOSE"
    CANCEL = "CANCEL"


class RoundProgressIn(BaseModel):
    action: Literal["OPEN", "FINALIZE", "CLOSE", "CANCEL"]
    round_no: Optional[int] = Field(
        default=None,
        description="미지정 시 활성(OPEN) 라운드 대상으로 처리",
    )
    params: Optional[Dict[str, Any]] = None
    if _V2:
        model_config = ConfigDict(extra="ignore")
    else:
        class Config:
            extra = "ignore"


class ReservationOutLite(ORMModel):
    id: int
    deal_id: int
    offer_id: int
    buyer_id: int
    qty: int
    status: ReservationStatus
    created_at: datetime
    expires_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
# ● 배송 정보
    shipping_carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    arrival_confirmed_at: Optional[datetime] = None
    # ● 신규: 정책 등의 정보 …
    policy_id: Optional[int] = None
    policy_agreed_at: Optional[datetime] = None
    policy: Optional[ReservationPolicySnapshot] = None
    # 🆕 여기 추가: 상태 + 배송정보를 합친 “단계” 정보
    phase: Optional[str] = None


    class Config:
        orm_mode = True    
    

# ---------------------------------------------------------
# 💰 ReservationSettlement Out 스키마
# ---------------------------------------------------------
class ReservationSettlementOut(BaseModel):
    id: int
    reservation_id: int

    deal_id: int
    offer_id: int
    seller_id: int
    buyer_id: int

    buyer_paid_amount: int
    pg_fee_amount: int
    platform_commission_amount: int
    seller_payout_amount: int

    status: str
    currency: str

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True  # SQLAlchemy ORM → Pydantic 변환 허용


# -------------------------------------------------------
# 🔔 Notifications (내부 알림센터용 스키마)
# -------------------------------------------------------

class NotificationOut(BaseModel):
    id: int
    user_id: int
    event_type: str
    title: str
    message: str

    deal_id: Optional[int] = None
    offer_id: Optional[int] = None
    reservation_id: Optional[int] = None
    seller_id: Optional[int] = None
    buyer_id: Optional[int] = None
    actuator_id: Optional[int] = None

    meta: Optional[dict] = None

    is_read: bool
    created_at: datetime

    class Config:
        orm_mode = True

class NotificationCreateIn(BaseModel):
    """
    서버 내부에서 create_notification(...) 헬퍼로 직접 쓰는 용도라,
    외부 API로 노출할 계획이 없으면 안 써도 됨.
    """
    user_id: int
    type: str
    title: str
    message: str
    link_url: Optional[str] = None  
    event_time: Optional[datetime] = None
    meta: Optional[Dict[str, Any]] = None


class NotificationReadIn(BaseModel):
    user_id: int = Field(..., ge=1, description="알림을 읽는 사용자 ID")


class NotificationReadAllIn(BaseModel):
    user_id: int = Field(..., ge=1, description="알림을 모두 읽음 처리할 사용자 ID")  