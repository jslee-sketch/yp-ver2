# ===== v3.6 Schemas (DealRound / Offers / Reservations / Points) =====
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict, List, Literal

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


# ─────────────────────────────────────────────────────────
# 공통 ORM 베이스: v2는 from_attributes, v1은 orm_mode
# ─────────────────────────────────────────────────────────
if _V2:
    class ORMModel(BaseModel):
        model_config = ConfigDict(from_attributes=True)
else:
    class ORMModel(BaseModel):  # type: ignore[misc]
        class Config:
            orm_mode = True


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


class SellerCreate(SellerBase):
    password: str


class SellerOut(ORMModel):
    id: int
    created_at: datetime
    email: EmailStr
    business_name: str
    business_number: str
    phone: Optional[str] = None
    company_phone: Optional[str] = None
    address: Optional[str] = None
    zip_code: Optional[str] = None
    established_date: Optional[datetime] = None


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


# ─────────────────────────────────────────────────────────
# Deposit (보증금) Schemas
# ─────────────────────────────────────────────────────────
class DepositHoldIn(BaseModel):
    amount: int = Field(..., ge=1, description="디파짓 홀드 금액(원)")


class DepositOut(ORMModel):
    deposit_id: int
    deal_id: int
    buyer_id: int
    amount: int
    status: Literal["HELD", "REFUNDED"]
    created_at: datetime
    refunded_at: Optional[datetime] = None


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
    # comment/free_text 중 하나만 와도 허용 (crud에서 comment 우선 사용)


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


# 하위호환: 기존 코드가 OfferOutExtended를 참조한다면 그대로 동작
class OfferOutExtended(OfferOut):
    pass


# ==== Reservation Schemas ====
class ReservationCreate(BaseModel):
    deal_id: int
    offer_id: int
    buyer_id: int
    qty: int = Field(..., gt=0)
    hold_minutes: int = Field(5, ge=1, le=60)


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


class ReservationPayIn(BaseModel):
    reservation_id: int
    buyer_id: int
    buyer_point_per_qty: int = 1  # 결제 시 바이어 포인트 기본 +1/수량


class ReservationCancelIn(BaseModel):
    reservation_id: int
    # 바이어가 자기 예약만 취소하게 할 경우 전달; 운영자 취소면 None 허용
    buyer_id: Optional[int] = None


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