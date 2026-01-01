# app/schemas_ai.py
from __future__ import annotations

from typing import Optional, List, Literal
from pydantic import BaseModel, Field



# ==============================
# 1) 기본 Intent 관련 스키마들
# ==============================

class PriceExpectation(BaseModel):
    # type: exact | max | range | discount_rate
    type: Literal["exact", "max", "range", "discount_rate"]
    value: int                      # exact/max/discount_rate 값
    min_value: Optional[int] = None # type="range" 일 때 사용
    max_value: Optional[int] = None


class ShippingPref(BaseModel):
    area: Optional[str] = None          # "대한민국", "서울/경기" 등
    method: Optional[str] = None        # "택배", "직거래", "편의점픽업" 등
    note: Optional[str] = None          # 기타 메모


class PaymentPref(BaseModel):
    card_ok: bool = True
    installment_ok: bool = False
    cash_only: bool = False


class IntentOption(BaseModel):
    name: str          # "색상", "용량"
    value: str         # "티타늄", "256GB"


class BuyerIntentParsed(BaseModel):
    """
    LLM이 해석한 Buyer의 '방 만들기' 의도를 구조화한 결과.
    """
    title: str
    product_key: str                 # 중복 매칭용 정규화 키 (핵심)
    category: Optional[str] = None

    quantity_target: Optional[int] = None  # 목표 인원/수량
    price_expectation: Optional[PriceExpectation] = None

    shipping_pref: Optional[ShippingPref] = None
    payment_pref: Optional[PaymentPref] = None

    options: List[IntentOption] = []
    original_text: str               # 원본 프롬프트

    class Config:
        from_attributes = True


# ==============================
# 2) Deal resolve 관련 스키마
# ==============================

class DealResolveResult(BaseModel):
    """
    /deals/ai/resolve_from_intent 의 간단 응답 스키마

    - deal_id: 최종 매칭/생성된 deal ID
    - created: 이번 호출에서 새로 만든 deal 인지 여부
    - product_name: deal 대표 상품명
    - status: deal 상태 (open/closed 등)
    """
    deal_id: int
    created: bool
    product_name: str
    status: str


# 🔹 LLM이 넘겨주는 옵션 1~5를 포괄할 수 있는 구조화 타입
class DealIntentOption(BaseModel):
    title: str = Field(..., description="옵션 이름 (예: 색상, 사이즈 등)")
    value: str = Field(..., description="옵션 값 (예: 블랙, XL 등)")


# 🔹 LLM → 백엔드로 들어오는 구조화된 Intent
class DealResolveIn(BaseModel):
    """
    LLM이 분석한 '공동구매 방 개설 Intent'를 구조화한 입력.
    """
    product_name: str = Field(..., description="정규화된 상품명")
    desired_qty: int = Field(..., ge=1, description="희망 수량")

    target_price: Optional[float] = Field(
        default=None,
        description="희망 단가 (원 단위, 선택)",
    )
    max_budget: Optional[float] = Field(
        default=None,
        description="총 예산 상한 (원 단위, 선택)",
    )

    options: List[DealIntentOption] = Field(
        default_factory=list,
        description="옵션 1~N (색상, 사이즈 등)",
    )

    free_text: Optional[str] = Field(
        default=None,
        description="자유 텍스트 설명 (LLM이 요약한 원문 등)",
    )

    buyer_id: int = Field(..., description="방 개설자 buyer_id")




class DealResolveFromTextIn(BaseModel):
    """
    free text + buyer_id 를 받아서
    LLM → DealResolveIn 으로 파싱하기 위한 입력 스키마
    """
    buyer_id: int = Field(..., description="방 개설자 buyer_id")
    free_text: str = Field(..., description="LLM 에 넘길 원문 텍스트")



# 🔹 응답에서 deal을 간단 요약해서 내려줄 타입
class DealSummary(BaseModel):
    id: int
    product_name: str
    desired_qty: int
    status: str
    fingerprint_hash: Optional[str] = None


# 🔹 LLM Intent → (기존 방 매칭 or 새 방 생성) 결과
class DealResolveOut(BaseModel):
    """
    - matched=True  && existing_deal != None  → 기존 방으로 연결
    - matched=False && created_deal != None   → 새 Deal 생성됨
    """
    matched: bool = Field(..., description="기존 방 매칭 여부")
    reason: str = Field(..., description="매칭/생성 사유 설명(로그/디버깅용)")

    existing_deal: Optional[DealSummary] = None
    created_deal: Optional[DealSummary] = None


class DealResolveFromTextIn(BaseModel):
    """유저 프롬프트(자유 텍스트) + buyer_id"""
    buyer_id: int = Field(..., description="방 만드는 buyer_id")
    free_text: str = Field(..., description="유저가 그대로 입력한 문장")