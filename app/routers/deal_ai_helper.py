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


# ─────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────

class DealAIRequest(BaseModel):
    """프론트에서 보내는 요청"""
    raw_title: str = Field(..., description="사용자가 입력한 제품명/제목 그대로")
    raw_free_text: Optional[str] = Field(None, description="사용자가 쓴 설명/요구사항 (선택)")


class SuggestedOption(BaseModel):
    title: str
    selected_value: Optional[str] = None  # 입력에서 명시된 구체적 값 (없으면 null)
    values: List[str] = []


class PriceSuggestion(BaseModel):
    center_price: Optional[float] = None
    desired_price_suggestion: Optional[float] = None
    max_budget_suggestion: Optional[float] = None
    commentary: Optional[str] = None
    # ── 네이버 시장가 ──────────────────
    naver_lowest_price: Optional[int] = None
    naver_product_name: Optional[str] = None
    naver_product_url: Optional[str] = None
    naver_mall_name: Optional[str] = None
    naver_brand: Optional[str] = None
    price_source: Optional[str] = None  # "naver" | "llm_estimate"


class DealConditions(BaseModel):
    """딜 조건 (배송비, 환불, 보증 등 — free text에서 추출)"""
    shipping_fee_krw: Optional[int] = None     # 무료배송=0
    refund_days: Optional[int] = None
    warranty_months: Optional[int] = None
    delivery_days: Optional[int] = None
    extra_conditions: Optional[str] = None    # 기타 조건 (자유 텍스트)


class DealAIResponse(BaseModel):
    """LLM + 네이버 API가 정리해서 돌려주는 결과"""
    canonical_name: str
    model_name: str
    brand: Optional[str] = None
    suggested_options: List[SuggestedOption] = []
    price: PriceSuggestion
    conditions: Optional[DealConditions] = None
    normalized_free_text: Optional[str] = None
    # ── 3-stage 파이프라인 추가 필드 (Optional) ──
    search_keyword: Optional[str] = None
    category: Optional[str] = None
    expected_price_range: Optional[List[float]] = None


# ─────────────────────────────────────────────
# LLM 프롬프트 & 응답 파싱 유틸
# ─────────────────────────────────────────────

def _build_prompt(raw_title: str, raw_free_text: str) -> str:
    """1단계 LLM: 제품 구조화 + 검색어 + 카테고리 + 예상가격대."""
    return f"""
너는 공동구매 플랫폼 '역핑'의 상품 정규화/옵션 추천 도우미야.

## 입력
- 제목(raw_title): {raw_title!r}
- 설명(raw_free_text): {raw_free_text!r}

## 역할

### 1. 제품 정규화
- canonical_name: 검색/중복 방지용 정제된 제품명 (영문 포함, 예: "Apple AirPods Pro 2nd Gen")
- model_name: 사용자에게 보여줄 한국어 대표 모델명 (예: "애플 에어팟 프로 2세대")
- brand: 브랜드명 (예: "Apple", "삼성", "LG", "다이슨"). 모르면 null.

### 2. 검색 최적화 (네이버쇼핑 본품 검색용)
- search_keyword: 이 제품의 본품을 네이버쇼핑에서 정확히 찾기 위한 검색어.
  브랜드명 + 정확한 모델명을 포함. 액세서리/케이스/호환품이 아닌 본품만 검색되도록 구성.
  예: "Apple 에어팟 프로 2세대 본체", "LG 그램 17Z90S 1TB", "삼성 갤럭시 S25 256GB 자급제"
- category: 이 제품의 대분류 카테고리 (한국어).
  예: "무선이어폰", "노트북", "스마트폰", "쌀", "청소기", "게임기"
- expected_price_range: [최소가격, 최대가격] (원 단위, 정수).
  이 제품의 한국 시장에서의 일반적인 가격 범위. 넉넉히 잡을 것.
  예: 에어팟 프로 2세대 → [250000, 450000]
  예: LG 그램 17인치 → [1500000, 3500000]
  예: 쌀 20kg → [30000, 80000]

### 3. 옵션 자동 추출 (최대 10개)
사용자 입력에서 의미 있는 옵션을 최대 10개까지 추출.
각 옵션마다:
- selected_value: 사용자가 입력에서 명시한 구체적 값. 없으면 null.
- values: 이 옵션에서 가능한 후보 값 목록.

### 4. 가격 (LLM 추정)
center_price, desired_price_suggestion, max_budget_suggestion을 LLM이 아는 범위에서 추정.
commentary에 "LLM 추정치" 라고 반드시 명시.

### 5. 조건 추출 (free text에서)
- shipping_fee_krw, refund_days, warranty_months, delivery_days, extra_conditions. 언급 없으면 null.

### 6. 설명 정리
normalized_free_text: 사용자 설명을 한두 문장으로 정리. 없으면 null.

## 출력 (반드시 JSON 1개만, 바깥에 다른 글 절대 없이)

{{
  "canonical_name": "Apple AirPods Pro 2nd Gen",
  "model_name": "애플 에어팟 프로 2세대",
  "brand": "Apple",
  "search_keyword": "Apple 에어팟 프로 2세대 본체",
  "category": "무선이어폰",
  "expected_price_range": [250000, 450000],
  "normalized_free_text": "화이트 색상, 30만원 이하 희망",
  "suggested_options": [
    {{"title": "색상", "selected_value": "화이트", "values": ["화이트", "블랙"]}},
    {{"title": "연결방식", "selected_value": null, "values": ["Lightning", "USB-C"]}}
  ],
  "price": {{
    "center_price": 350000,
    "desired_price_suggestion": 300000,
    "max_budget_suggestion": 380000,
    "commentary": "LLM 추정치입니다. 실제 시장가와 다를 수 있습니다."
  }},
  "conditions": {{
    "shipping_fee_krw": null,
    "refund_days": null,
    "warranty_months": null,
    "delivery_days": null,
    "extra_conditions": null
  }}
}}

⚠️ JSON 1개만 출력. 바깥에 다른 글 절대 금지. null은 JSON null로.
""".strip()


def _parse_json_safely(text: str) -> dict:
    """LLM이 ```json ... ``` 형태로 줄 때를 대비한 파싱 유틸."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```json", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"^```", "", raw).strip()
        if raw.endswith("```"):
            raw = raw[:-3].strip()
    # 그래도 실패하면 첫 { ~ 마지막 } 추출
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        i = raw.find("{")
        j = raw.rfind("}")
        if i != -1 and j > i:
            return json.loads(raw[i : j + 1])
        raise


# ─────────────────────────────────────────────
# 2단계: 네이버 쇼핑 API → 원시 결과 리스트
# ─────────────────────────────────────────────

def _fetch_naver_items(query: str, display: int = 10) -> list:
    """네이버 쇼핑 API 호출 → 원시 items 리스트 반환."""
    try:
        from app.utils.naver_shopping import _get_creds
        import requests
        cid, sec = _get_creds()
        if not cid or not sec:
            return []
        resp = requests.get(
            "https://openapi.naver.com/v1/search/shop.json",
            headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec},
            params={"query": query, "display": display, "sort": "sim"},
            timeout=5,
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("items", [])
    except Exception as e:
        print(f"[deal_ai_helper] 네이버 API 에러: {e}")
        return []


# ─────────────────────────────────────────────
# 3단계: LLM 본품 선별
# ─────────────────────────────────────────────

def _select_best_product(query_info: dict, naver_items: list) -> Optional[dict]:
    """
    네이버 검색 결과 중에서 사용자가 원하는 본품을 LLM으로 선별.
    Returns: {product_name, lowest_price, mall_name, link, brand} 또는 None
    """
    if not naver_items:
        return None

    # 네이버 결과를 간결하게 정리 (LLM 토큰 절약)
    candidates = []
    for i, item in enumerate(naver_items[:10]):
        title = re.sub(r"<[^>]+>", "", item.get("title", ""))
        candidates.append({
            "index": i,
            "title": title,
            "price": int(item.get("lprice", 0)),
            "brand": item.get("brand", ""),
            "category": f"{item.get('category1', '')}/{item.get('category2', '')}/{item.get('category3', '')}",
            "mall": item.get("mallName", ""),
        })

    system_prompt = """너는 쇼핑 검색 결과에서 사용자가 원하는 본품을 골라내는 전문가다.

주어진 검색 결과 목록에서, 사용자가 찾는 제품의 **본품**(정품, 새 제품)에 해당하는 것만 골라라.
아래에 해당하는 것은 제외하라:
- 액세서리 (케이스, 이어팁, 충전기, 필름, 거치대 등)
- 호환품 / 비정품 / 서드파티
- 중고 / 리퍼 / B급
- 전혀 다른 제품

반드시 아래 JSON 형식으로만 응답하라. 다른 텍스트 없이 JSON만:
{"selected_index": 0}

본품이 하나도 없으면:
{"selected_index": -1}

여러 개의 본품이 있으면 그 중 최저가의 index를 반환하라."""

    ep_range = query_info.get("expected_price_range", [])
    user_prompt = f"""사용자가 찾는 제품:
- 제품명: {query_info.get('canonical_name', '')}
- 브랜드: {query_info.get('brand', '')}
- 카테고리: {query_info.get('category', '')}
- 예상 가격대: {ep_range}

네이버 쇼핑 검색 결과:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

위 검색 결과 중 사용자가 찾는 본품의 index를 골라라."""

    try:
        client = get_client()
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=50,
            temperature=0,
            timeout=10,
        )
        text = (resp.choices[0].message.content or "").strip()
        result = _parse_json_safely(text)

        idx = result.get("selected_index", -1)
        if isinstance(idx, int) and 0 <= idx < len(naver_items):
            selected = naver_items[idx]
            return {
                "product_name": re.sub(r"<[^>]+>", "", selected.get("title", "")),
                "lowest_price": int(selected.get("lprice", 0)),
                "highest_price": int(selected.get("hprice", 0) or 0),
                "mall_name": selected.get("mallName", ""),
                "link": selected.get("link", ""),
                "brand": re.sub(r"<[^>]+>", "", selected.get("brand", "")),
            }
    except Exception as e:
        print(f"[deal_ai_helper] 본품 선별 LLM 에러: {e}")

    return None


# ─────────────────────────────────────────────
# 핵심 로직: 3-stage pipeline
# ─────────────────────────────────────────────

def _run_ai_deal_helper(raw_title: str, raw_free_text: str) -> DealAIResponse:
    """
    LLM(구조화) → 네이버(검색) → LLM(본품선별) → 가격 병합.
    """
    # ━━━ 1단계: LLM 제품 구조화 ━━━
    prompt = _build_prompt(raw_title, raw_free_text)
    client = get_client()
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        timeout=30,
        max_tokens=800,
    )
    text = resp.choices[0].message.content or ""
    data = _parse_json_safely(text)

    # ━━━ 2단계: 네이버 API 검색 ━━━
    search_query = data.get("search_keyword") or data.get("model_name") or raw_title
    naver_items = _fetch_naver_items(search_query, display=10)

    # search_keyword로 결과가 부족하면 fallback 검색
    if len(naver_items) < 2:
        fallback_q = data.get("model_name") or raw_title
        if fallback_q != search_query:
            more = _fetch_naver_items(fallback_q, display=10)
            if len(more) > len(naver_items):
                naver_items = more

    # ━━━ 3단계: LLM 본품 선별 ━━━
    naver = None
    if naver_items:
        query_info = {
            "canonical_name": data.get("canonical_name", raw_title),
            "brand": data.get("brand", ""),
            "category": data.get("category", ""),
            "expected_price_range": data.get("expected_price_range", []),
        }
        naver = _select_best_product(query_info, naver_items)

    # ━━━ 4단계: 가격 병합 ━━━
    price_data: dict = data.get("price") or {}

    if naver and naver["lowest_price"] > 0:
        price_data["center_price"] = float(naver["lowest_price"])
        price_data["naver_lowest_price"] = naver["lowest_price"]
        price_data["naver_product_name"] = naver["product_name"]
        price_data["naver_product_url"] = naver["link"]
        price_data["naver_mall_name"] = naver["mall_name"]
        price_data["naver_brand"] = naver["brand"] or None
        price_data["price_source"] = "naver"

        price_data["commentary"] = (
            f"네이버 최저가 {naver['lowest_price']:,}원 기준"
            + (f" ({naver['mall_name']})" if naver.get("mall_name") else "")
            + ". 실시간 가격과 다를 수 있습니다."
        )

        if not price_data.get("desired_price_suggestion"):
            price_data["desired_price_suggestion"] = round(
                naver["lowest_price"] * 0.95, -2
            )
        if not price_data.get("max_budget_suggestion"):
            price_data["max_budget_suggestion"] = round(
                naver["lowest_price"] * 1.05, -2
            )

        # 브랜드 보강
        if not data.get("brand") and naver.get("brand"):
            data["brand"] = naver["brand"]

    else:
        price_data["price_source"] = "llm_estimate"
        if not price_data.get("commentary"):
            price_data["commentary"] = (
                "네이버에서 정확한 본품 가격을 찾지 못해 LLM 추정가입니다."
            )

    data["price"] = price_data

    # ── 스키마 검증 + 옵션 10개 상한 ────────────────────
    opts = data.get("suggested_options") or []
    data["suggested_options"] = opts[:10]

    return DealAIResponse.model_validate(data)


# ─────────────────────────────────────────────
# 메인 엔드포인트
# ─────────────────────────────────────────────

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

        result = _run_ai_deal_helper(raw_title, raw_ft)

        # ── 로그 ─────────────────────────────────────────────
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
    except RuntimeError as e:
        # OPENAI_API_KEY missing or openai not installed
        print("[ai_deal_helper] CONFIG ERROR:", repr(e))
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        print("[ai_deal_helper] ERROR:", repr(e))
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"AI helper error: {e.__class__.__name__}")
