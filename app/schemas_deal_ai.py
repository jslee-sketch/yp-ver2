# app/schemas_deal_ai.py
from __future__ import annotations

from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class DealAiNormalizeIn(BaseModel):
    """
    Buyer가 대충 입력한 Deal 생성 정보
    - 최소 요구: product_name
    - 나머지는 있으면 참고용 힌트
    """
    product_name: str = Field(..., min_length=1, max_length=200)
    free_text: Optional[str] = Field(
        None,
        description="추가 설명 (사용자가 적은 자유 텍스트)",
    )
    # 이미 입력한 옵션 타이틀/값이 있으면 넘겨도 됨 (AI가 보정/추가)
    option_titles: Optional[List[str]] = Field(
        default=None,
        description="이미 사용자가 적어둔 옵션 타이틀들 (예: ['색상', '용량'])",
    )
    # 키=옵션타이틀, 값=사용자가 적은 후보 값들
    option_values: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="옵션 타이틀별 값 목록",
    )


class DealAiOptionSuggestion(BaseModel):
    """
    옵션 한 축에 대한 추천 정보
    """
    title: str
    values: List[str]


class DealAiPriceSuggestion(BaseModel):
    """
    가격 관련 제안
    """
    center_price: Optional[float] = Field(
        None,
        description="AI가 추정한 기준가 (있으면)",
    )
    desired_price_suggestion: Optional[float] = None
    max_budget_suggestion: Optional[float] = None
    # 참고용 메시지 (예: '중고 시세 상단 기준입니다' 같은)
    commentary: Optional[str] = None


class DealAiNormalizeOut(BaseModel):
    """
    Deal 생성 화면에서 바로 쓸 수 있는 정규화 결과
    """
    canonical_name: str = Field(
        ...,
        description="정규화된 제품명 (예: 'Apple iPhone 15 Pro 256GB Blue')",
    )

    # AI가 추천하는 주요 옵션(타이틀 + 값 리스트)
    suggested_options: List[DealAiOptionSuggestion] = Field(default_factory=list)

    # 가격 가이드
    price: DealAiPriceSuggestion

    # 원문 텍스트를 기반으로 한 요약 설명 (딜 free_text에 바로 써도 되는 수준)
    normalized_free_text: Optional[str] = None