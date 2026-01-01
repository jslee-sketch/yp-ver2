# app/routers/deal_ai_helper.py
from __future__ import annotations

import json
import re
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud


from app.llm_client import get_client

router = APIRouter(
    prefix="/ai/deal_helper",
    tags=["AI Deal Helper"],
)

# -----------------------------
# Pydantic Schemas
# -----------------------------
class DealAIRequest(BaseModel):
    """
    프론트에서 보내는 요청

    - raw_title: 사용자가 입력한 제목/제품명
    - raw_free_text: 추가 설명(선택)
    """
    raw_title: str = Field(..., description="사용자가 입력한 제품명/제목 그대로")
    raw_free_text: Optional[str] = Field(
        None,
        description="사용자가 쓴 설명/요구사항 (선택)",
    )


class SuggestedOption(BaseModel):
    title: str
    values: List[str]


class PriceSuggestion(BaseModel):
    center_price: Optional[float] = None
    desired_price_suggestion: Optional[float] = None
    max_budget_suggestion: Optional[float] = None
    commentary: Optional[str] = None


class DealAIResponse(BaseModel):
    """
    LLM이 정리해서 돌려주는 결과
    """
    canonical_name: str
    model_name: str
    suggested_options: List[SuggestedOption] = []
    price: PriceSuggestion
    normalized_free_text: Optional[str] = None


# -----------------------------
# LLM 프롬프트 & 응답 파싱 유틸
# -----------------------------
def _build_prompt(raw_title: str, raw_free_text: str) -> str:
    """
    OpenAI Responses API에 넘길 프롬프트.
    답변은 반드시 JSON 하나만 나오도록 강하게 요구.
    """
    raw_title = raw_title.strip()
    raw_free_text = raw_free_text.strip()

    return f"""
너는 공동구매 플랫폼 '역핑'의 상품 정규화/옵션 추천 도우미야.

## 입력
- 제목(raw_title): {raw_title!r}
- 설명(raw_free_text): {raw_free_text!r}

## 역할
1. 사용자가 적은 제목과 설명을 보고,
   - 검색/중복 방지에 쓰기 좋은 정제된 제품명(canonical_name)
   - 사람에게 보여줄 대표 모델명(model_name)
   을 정리한다.

2. 색상/용량/모델명 같은 옵션 후보들을 뽑아서 suggested_options 로 내려준다.

3. 가격 정보를 대략적으로 해석해서,
   - center_price: 중심이 될만한 단가 (정보가 애매하면 null)
   - desired_price_suggestion: '이 정도에 사면 좋겠다' 수준의 단가 추천 (선택, 없으면 null)
   - max_budget_suggestion: '이 이상은 비싸다' 수준의 최대 예산 (선택, 없으면 null)
   - commentary: 가격에 대한 짧은 한국어 코멘트
   를 작성한다.

4. 설명은 normalized_free_text 에 짧게 정리한다.  
   설명이 거의 없으면 null 로 둔다.

## 출력 형식 (반드시 아래 JSON 한 개만 출력할 것)
아래는 예시이며, 실제 값은 상황에 맞게 채워라.

{{
  "canonical_name": "정제된 제품명 예: Apple AirPods Pro 2세대",
  "model_name": "사람에게 보여줄 대표 모델명 예: 애플 에어팟 프로 2세대",
  "normalized_free_text": "사용자가 적은 설명을 한두 문장으로 정리. 없으면 null",

  "suggested_options": [
    {{
      "title": "색상",
      "values": ["화이트", "블랙"]
    }},
    {{
      "title": "용량",
      "values": ["128GB", "256GB"]
    }}
  ],

  "price": {{
    "center_price": null,
    "desired_price_suggestion": null,
    "max_budget_suggestion": null,
    "commentary": "가격 정보가 부족합니다."
  }}
}}

⚠️ 매우 중요:
- 반드시 위 JSON 객체 하나만 응답해.
- JSON 바깥에 다른 글(설명, 코드블럭, ```json 같은 것)을 절대 넣지 마.
- null 이 들어갈 곳은 실제 JSON null 로 써라.
""".strip()


def _parse_json_safely(text: str) -> dict:
    """
    LLM이 가끔 ```json ... ``` 같은 형태로 줄 때를 대비해서
    JSON 부분만 깔끔하게 파싱하는 유틸.
    """
    raw = text.strip()

    # ```json ... ``` 형식 제거
    if raw.startswith("```"):
        raw = re.sub(r"^```json", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"^```", "", raw).strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    return json.loads(raw)


# -----------------------------
# 메인 엔드포인트
# -----------------------------
@router.post("", response_model=DealAIResponse)
def ai_deal_helper(
    body: DealAIRequest = Body(...),
    db: Session = Depends(get_db),
):
    try:
        raw_title = (body.raw_title or "").strip()
        raw_ft = (body.raw_free_text or "").strip()

        if not raw_title:
            raise HTTPException(status_code=400, detail="raw_title is required")

        prompt = _build_prompt(raw_title, raw_ft)

        # 여기서 client 가져오는 방식은 지금 잘 돌아가는 그대로 사용
        from app.llm_client import get_client
        client = get_client()

        resp = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )

        text = resp.output[0].content[0].text
        data = _parse_json_safely(text)

        result = DealAIResponse.model_validate(data)

        # 👉 로그 남기기 (buyer_id는 아직 없으니 None)
        crud.log_ai_event(
            db,
            endpoint="ai/deal_helper",
            buyer_id=None,
            request=body.model_dump(mode="json"),
            response=result.model_dump(mode="json"),
            deal_id=None,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        print("[ai_deal_helper] ERROR:", repr(e))
        raise HTTPException(status_code=500, detail="Internal error")