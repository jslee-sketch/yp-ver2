# app/routers/deal_ai_helper.py
from __future__ import annotations

import base64
import json
import re
import urllib.parse
from typing import List, Optional

from fastapi import APIRouter, Body, File, HTTPException, Depends, UploadFile
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
    recalc_price: bool = Field(False, description="True면 가격만 재계산 (네이버 검색)")
    selected_options: Optional[str] = Field(None, description="선택된 옵션 텍스트 (가격 재계산용)")
    brand: Optional[str] = Field(None, description="브랜드명 (가격 재계산 시 검색 필터용)")


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


class PriceAnalysisItem(BaseModel):
    title: str
    price: int
    link: Optional[str] = None
    mall: Optional[str] = None
    reason: Optional[str] = None   # 제외 사유 (excluded에만)

class PriceAnalysis(BaseModel):
    lowest_price: Optional[int] = None
    included_items: List[PriceAnalysisItem] = []
    excluded_items: List[PriceAnalysisItem] = []
    total_searched: int = 0
    total_included: int = 0
    total_excluded: int = 0
    notice: Optional[str] = None           # 고가 제품 등 특수 안내
    fallback_price: Optional[int] = None   # 시장가 없을 때 목표가 기반 대체값

class DealAIResponse(BaseModel):
    """LLM + 네이버 API가 정리해서 돌려주는 결과"""
    canonical_name: str
    model_name: str
    brand: Optional[str] = None
    brands: List[str] = []                  # 브랜드 후보 리스트
    product_code: Optional[str] = None      # 제품코드/모델번호
    product_detail: Optional[str] = None    # 상세 제품명
    suggested_options: List[SuggestedOption] = []
    price: PriceSuggestion
    price_analysis: Optional[PriceAnalysis] = None  # 가격 근거 상세
    price_consensus: Optional[dict] = None           # 3중 소스 합의 결과
    conditions: Optional[DealConditions] = None
    normalized_free_text: Optional[str] = None
    # ── 3-stage 파이프라인 추가 필드 (Optional) ──
    search_keyword: Optional[str] = None
    category: Optional[str] = None
    expected_price_range: Optional[List[float]] = None


def _naver_search_url(query: str) -> str:
    """봇 차단 안 당하는 네이버 쇼핑 검색 URL."""
    return f"https://search.shopping.naver.com/search/all?query={urllib.parse.quote(query)}"


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
- brands: 이 제품의 브랜드 후보 리스트 (1~5개). 확실한 브랜드가 1개이면 그것만. 식품 등 여러 브랜드가 가능하면 최대 5개.
  예: ["Apple"], ["종가집", "비비고", "풀무원", "처갓집", "피코크"]
- product_code: 이 제품의 모델번호/제품코드 (식별 가능하면). 없으면 null.
  예: "SM-S936N", "MTJV3KH/A", null
- product_detail: 구체적 제품명 (브랜드+모델+용량 등 포함).
  예: "종가집 포기김치 2.5kg", "삼성 갤럭시 S25 울트라 256GB 자급제"
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

⚠️ 중요: 브랜드 일관성
- brand 필드에 설정한 브랜드와 옵션의 values는 반드시 일치해야 한다.
- 예: brand가 "오뚜기"이면, "종류" 옵션 values에 오뚜기 제품만 넣어라 ("오뚜기 진라면", "오뚜기 참깨라면" 등).
  다른 브랜드 제품 ("신라면", "삼양라면" 등)을 넣지 마라.
- 예: brand가 "종가집"이면, "종류" 옵션에 종가집 제품만 넣어라. "비비고 김치"를 넣지 마라.
- 브랜드 옵션("브랜드" title)이 필요하면, brands 리스트와 동일하게 구성하라.

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
  "brands": ["Apple"],
  "product_code": "MTJV3KH/A",
  "product_detail": "애플 에어팟 프로 2세대 USB-C MagSafe",
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
# 가격 필터링 (부품/액세서리 제외)
# ─────────────────────────────────────────────

def _get_reliable_market_price(
    naver_items: list,
    expected_price_range: list | None = None,
) -> Optional[dict]:
    """
    네이버 검색 결과에서 부품/액세서리를 제외한 신뢰할 수 있는 시장가 추출.
    중앙값 기반 이상치 제거.
    """
    priced = [it for it in naver_items if int(it.get("lprice", 0)) > 0]
    if not priced:
        return None

    prices = sorted([int(it["lprice"]) for it in priced])

    # expected_price_range가 있으면 그 범위의 30% 미만 제거
    if expected_price_range and len(expected_price_range) == 2:
        ep_min = float(expected_price_range[0])
        threshold = ep_min * 0.3
        filtered_items = [it for it in priced if int(it["lprice"]) >= threshold]
        if filtered_items:
            priced = filtered_items
            prices = sorted([int(it["lprice"]) for it in priced])

    # 중앙값의 30% 미만인 이상치(부품/액세서리) 제거
    if len(prices) >= 3:
        median = prices[len(prices) // 2]
        filtered = [(it, int(it["lprice"])) for it in priced if int(it["lprice"]) >= median * 0.3]
        if filtered:
            priced = [f[0] for f in filtered]
            prices = sorted([f[1] for f in filtered])

    # 중앙값 위치의 상품 선택 (최저가가 아닌 중앙값 → 부품 가격 회피)
    median_idx = len(prices) // 2
    median_price = prices[median_idx]

    # 중앙값 가격에 가장 가까운 상품 찾기
    best = min(priced, key=lambda it: abs(int(it["lprice"]) - median_price))
    best_title = re.sub(r"<[^>]+>", "", best.get("title", ""))
    return {
        "product_name": best_title,
        "lowest_price": int(best["lprice"]),
        "highest_price": int(best.get("hprice", 0) or 0),
        "mall_name": best.get("mallName", ""),
        "link": _naver_search_url(best_title),
        "brand": re.sub(r"<[^>]+>", "", best.get("brand", "")),
    }


# ─────────────────────────────────────────────
# 가격 근거 분석 (채택/제외 분류)
# ─────────────────────────────────────────────

_ACCESSORY_KW = re.compile(
    r'케이스|커버|필름|충전기|어댑터|거치대|파우치|스트랩|이어팁|리모컨|보호|캡|젤리|범퍼|강화유리',
    re.IGNORECASE,
)
_BUNDLE_KW = re.compile(r'세트|묶음|패키지|번들|기획전|합본', re.IGNORECASE)
_USED_KW = re.compile(r'중고|리퍼|반품|전시|매입|S급|A급|B급|재생|수리', re.IGNORECASE)


# ── 브랜드 별칭 매핑 (한/영) ──────────────────────
_BRAND_ALIASES: dict[str, list[str]] = {
    'samsung':   ['삼성', 'samsung', '갤럭시', 'galaxy'],
    'apple':     ['애플', 'apple', '아이폰', 'iphone', '아이패드', 'ipad', '맥북', 'macbook', '에어팟', 'airpods'],
    'lg':        ['lg', '엘지', '그램', 'gram'],
    'sony':      ['소니', 'sony', '플레이스테이션', 'playstation', 'ps5'],
    'dyson':     ['다이슨', 'dyson'],
    'nintendo':  ['닌텐도', 'nintendo'],
    'xiaomi':    ['샤오미', 'xiaomi', '미', 'redmi'],
    'lenovo':    ['레노버', 'lenovo', '씽크패드', 'thinkpad'],
    'hp':        ['hp', '에이치피'],
    'dell':      ['dell', '델'],
    'asus':      ['에이수스', 'asus', '아수스'],
    'nike':      ['나이키', 'nike'],
    'adidas':    ['아디다스', 'adidas'],
}

_ALL_KNOWN_BRANDS: list[str] = []
for _aliases in _BRAND_ALIASES.values():
    _ALL_KNOWN_BRANDS.extend(_aliases)


def _get_brand_aliases(brand: str) -> list[str]:
    """주어진 브랜드의 모든 별칭(소문자) 반환."""
    bl = brand.lower().strip()
    for aliases in _BRAND_ALIASES.values():
        lower_aliases = [a.lower() for a in aliases]
        if bl in lower_aliases:
            return lower_aliases
    return [bl]


_HIGH_VALUE_KEYWORDS = [
    '자동차', '차량', 'suv', '세단', '전기차', 'ev ', 'eqs', 's클래스', 'e클래스', 'c클래스',
    '벤츠', 'bmw', '아우디', '포르쉐', '테슬라', '렉서스', '제네시스', '볼보', '재규어',
    '랜드로버', '람보르기니', '페라리', '마세라티', '벤틀리', '롤스로이스',
    '부동산', '아파트', '빌라', '오피스텔', '토지',
]


def _is_high_value_product(query: str) -> bool:
    """자동차/부동산 등 네이버쇼핑에서 본체 가격을 찾기 어려운 고가 제품인지 확인."""
    q = query.lower()
    return any(kw in q for kw in _HIGH_VALUE_KEYWORDS)


_MODEL_PATTERNS = [
    re.compile(r'[SsZz]\d{1,3}(?:\s*(?:FE|fe))?', re.IGNORECASE),   # S23, S25 Ultra, Z Flip5, S23 FE
    re.compile(r'\d{1,2}\s*[Pp]ro(?:\s*[Mm]ax)?'),                    # 16 Pro, 15 Pro Max
    re.compile(r'\d{1,2}\s*[Uu]ltra'),                                 # 25 Ultra
    re.compile(r'\d{1,2}\s*[Pp]lus'),                                  # 16 Plus
    re.compile(r'[Vv]\d{1,3}'),                                        # V15, V50
    re.compile(r'[Mm]\d{1,2}'),                                        # M4, M3
    re.compile(r'[Aa]ir\s*\d*'),                                       # Air, Air 5
    re.compile(r'[Mm]ini\s*\d*'),                                      # Mini, Mini 6
    re.compile(r'\d{1,2}세대'),                                         # 10세대
]


def _extract_model_numbers(text: str) -> list[str]:
    """텍스트에서 모델 번호들을 추출. 예: 'S23', '16 Pro', 'V15' 등."""
    found = []
    for pat in _MODEL_PATTERNS:
        for m in pat.finditer(text):
            found.append(m.group().strip().upper())
    return found


def _model_matches(query_models: list[str], item_text: str) -> bool:
    """검색 쿼리의 모델번호가 아이템에도 존재하는지 확인."""
    if not query_models:
        return True  # 모델번호 없으면 필터 안 함
    item_models = _extract_model_numbers(item_text)
    if not item_models:
        return True  # 아이템에 모델번호 없으면 통과 (일반 상품)
    # 쿼리 모델 중 하나라도 아이템에 포함되면 OK
    for qm in query_models:
        for im in item_models:
            if qm in im or im in qm:
                return True
    return False


def _analyze_market_prices(
    naver_items: list,
    expected_price_range: list | None = None,
    brand: str | None = None,
    user_target_price: int | float | None = None,
    search_query: str | None = None,
) -> PriceAnalysis:
    """네이버 검색 결과를 채택/제외로 분류하고 근거를 반환."""
    total_searched = len(naver_items)
    included: list[PriceAnalysisItem] = []
    excluded: list[PriceAnalysisItem] = []

    # 고가 제품 감지 (자동차/부동산 등)
    if search_query and _is_high_value_product(search_query):
        if user_target_price and user_target_price > 10_000_000:
            return PriceAnalysis(
                lowest_price=None,
                included_items=[],
                excluded_items=[],
                total_searched=total_searched,
                total_included=0,
                total_excluded=total_searched,
                notice=f"자동차/고가 제품은 네이버쇼핑에서 정확한 시장가를 제공하기 어렵습니다. "
                       f"공식 딜러 가격이나 전문 사이트를 참고해주세요.",
                fallback_price=int(user_target_price),
            )

    # 브랜드 별칭 준비
    my_aliases: list[str] = []
    if brand:
        my_aliases = _get_brand_aliases(brand)

    # 모델번호 추출 (쿼리에서)
    query_models = _extract_model_numbers(search_query) if search_query else []

    # 중앙값 계산 (이상치 기준)
    prices_all = sorted([int(it.get("lprice", 0)) for it in naver_items if int(it.get("lprice", 0)) > 0])
    median_price = prices_all[len(prices_all) // 2] if prices_all else 0

    for item in naver_items:
        price = int(item.get("lprice", 0))
        if price <= 0:
            continue
        title = re.sub(r"<[^>]+>", "", item.get("title", ""))
        title_lower = title.lower()
        link = item.get("link", "")
        mall = item.get("mallName", "")
        reason = None

        # 제외 규칙 체크
        if _ACCESSORY_KW.search(title):
            reason = "액세서리"
        elif _BUNDLE_KW.search(title):
            reason = "묶음상품"
        elif _USED_KW.search(title):
            reason = "중고/리퍼"
        elif median_price > 0 and price < median_price * 0.3:
            reason = "가격 이상치"
        elif expected_price_range and len(expected_price_range) == 2:
            ep_min = float(expected_price_range[0])
            if price < ep_min * 0.3:
                reason = "가격 이상치"

        # 브랜드 불일치 제외
        if not reason and my_aliases:
            has_my_brand = any(alias in title_lower for alias in my_aliases)
            if not has_my_brand:
                has_other = any(
                    ob in title_lower
                    for ob in _ALL_KNOWN_BRANDS
                    if ob not in my_aliases
                )
                if has_other:
                    reason = "다른 브랜드 상품"

        # 모델번호 불일치 제외
        if not reason and query_models:
            if not _model_matches(query_models, title):
                item_models = _extract_model_numbers(title)
                item_label = '/'.join(item_models) if item_models else '?'
                query_label = '/'.join(query_models)
                reason = f"다른 모델 ({item_label} ≠ {query_label})"

        if reason:
            excluded.append(PriceAnalysisItem(title=title, price=price, reason=reason))
        else:
            included.append(PriceAnalysisItem(title=title, price=price, link=_naver_search_url(title), mall=mall))

    # 채택 목록은 가격 순 정렬
    included.sort(key=lambda x: x.price)

    # === 구매자 목표가 대비 이상치 감지 ===
    if user_target_price and user_target_price > 0 and included:
        market_median = included[len(included) // 2].price if included else 0
        if market_median > 0:
            ratio = market_median / user_target_price
            # 시장가가 목표가의 10% 미만이면 → 부품/액세서리 가격일 가능성 높음
            if ratio < 0.1:
                refiltered = [it for it in included if it.price >= user_target_price * 0.3]
                if refiltered:
                    excluded.extend([it for it in included if it not in refiltered])
                    for it in excluded:
                        if not it.reason:
                            it.reason = "가격 이상치 (목표가 대비)"
                    included = refiltered
                else:
                    # 네이버에 본체 가격 없음 → fallback
                    return PriceAnalysis(
                        lowest_price=None,
                        included_items=[],
                        excluded_items=excluded[:5],
                        total_searched=total_searched,
                        total_included=0,
                        total_excluded=len(excluded),
                        notice=f"이 제품의 시장가를 찾을 수 없습니다. 네이버쇼핑에 해당 제품이 등록되어 있지 않을 수 있습니다.",
                        fallback_price=int(user_target_price),
                    )

    lowest = included[0].price if included else None

    return PriceAnalysis(
        lowest_price=lowest,
        included_items=included[:5],
        excluded_items=excluded[:5],
        total_searched=total_searched,
        total_included=len(included),
        total_excluded=len(excluded),
    )


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
아래에 해당하는 것은 반드시 제외하라:
- 액세서리 (케이스, 이어팁, 충전기, 필름, 거치대, 리모컨, 부품 등)
- 호환품 / 비정품 / 서드파티
- 중고 / 리퍼 / B급
- 전혀 다른 제품
- 예상 가격대보다 지나치게 싼 제품 (부품/액세서리일 가능성 높음)

**가격 판단 기준**: 예상 가격대가 주어진 경우, 그 범위의 30% 미만인 상품은 부품/액세서리로 간주하라.
예: 예상 가격대 [800000, 1500000]인데 가격이 100000원이면 부품이다.

반드시 아래 JSON 형식으로만 응답하라. 다른 텍스트 없이 JSON만:
{"selected_index": 0}

본품이 하나도 없으면:
{"selected_index": -1}

여러 개의 본품이 있으면 그 중 최저가의 index를 반환하라."""

    ep_range = query_info.get("expected_price_range", [])
    ep_hint = ""
    if ep_range and len(ep_range) == 2:
        ep_hint = f"\n- 예상 가격대: {int(ep_range[0]):,}원 ~ {int(ep_range[1]):,}원 (이 범위의 30% 미만 가격은 부품/액세서리)"
    else:
        ep_hint = f"\n- 예상 가격대: {ep_range}" if ep_range else ""

    user_prompt = f"""사용자가 찾는 제품:
- 제품명: {query_info.get('canonical_name', '')}
- 브랜드: {query_info.get('brand', '')}
- 카테고리: {query_info.get('category', '')}{ep_hint}

네이버 쇼핑 검색 결과:
{json.dumps(candidates, ensure_ascii=False, indent=2)}

위 검색 결과 중 사용자가 찾는 본품의 index를 골라라. 부품/액세서리 가격을 본품으로 고르지 마라."""

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
            sel_price = int(selected.get("lprice", 0))

            # 가격 sanity check: expected_price_range의 30% 미만이면 부품/액세서리
            if sel_price > 0 and ep_range and len(ep_range) == 2:
                ep_min = float(ep_range[0])
                if sel_price < ep_min * 0.3:
                    print(f"[deal_ai_helper] LLM selected idx={idx} price={sel_price} "
                          f"< expected_min*0.3={ep_min*0.3:.0f}, rejected as accessory")
                    # fallback: 중앙값 기반 가격
                    fallback = _get_reliable_market_price(naver_items, ep_range)
                    if fallback:
                        return fallback
                    return None

            product_title = re.sub(r"<[^>]+>", "", selected.get("title", ""))
            return {
                "product_name": product_title,
                "lowest_price": sel_price,
                "highest_price": int(selected.get("hprice", 0) or 0),
                "mall_name": selected.get("mallName", ""),
                "link": _naver_search_url(product_title),
                "brand": re.sub(r"<[^>]+>", "", selected.get("brand", "")),
            }
    except Exception as e:
        print(f"[deal_ai_helper] 본품 선별 LLM 에러: {e}")

    # LLM 실패 시에도 중앙값 fallback 시도
    fallback = _get_reliable_market_price(naver_items, ep_range)
    if fallback:
        return fallback
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

    # ── 가격 근거 분석 ────────────────────────────────
    analysis = None
    if naver_items:
        analysis = _analyze_market_prices(
            naver_items, data.get("expected_price_range"),
            brand=data.get("brand"),
            search_query=search_query,
        )
        data["price_analysis"] = analysis.model_dump()

    # ── 3중 소스 합의 엔진 ────────────────────────────
    try:
        from app.services.price_consensus import build_price_consensus
        pa = analysis.model_dump() if analysis else {}
        consensus = build_price_consensus(
            product_name=data.get("canonical_name") or raw_title,
            brand=data.get("brand", ""),
            options="",
            user_target_price=0,
            naver_lowest=pa.get("lowest_price") or 0,
            naver_included_items=[
                {"title": it.title, "price": it.price, "link": it.link or "", "mall": it.mall or ""}
                for it in (analysis.included_items if analysis else [])
            ],
            naver_total_included=pa.get("total_included", 0),
        )
        data["price_consensus"] = consensus

        # 합의 결과로 가격 보정
        if consensus.get("confidence") in ("not_available", "low", "none"):
            cp = consensus.get("market_price", 0)
            if cp > 0:
                price_data = data.get("price") or {}
                if not price_data.get("center_price") or (price_data["center_price"] < cp * 0.1):
                    price_data["center_price"] = float(cp)
                    price_data["price_source"] = "consensus"
                    price_data["commentary"] = consensus.get("notice") or "AI 추정가 기준입니다."
                    data["price"] = price_data
    except Exception as e:
        print(f"[CONSENSUS] 합의 엔진 에러: {e}", flush=True)
        import traceback; traceback.print_exc()

    # ── brands 리스트 보강 ────────────────────────────
    brands = data.get("brands") or []
    if data.get("brand") and data["brand"] not in brands:
        brands.insert(0, data["brand"])
    if naver and naver.get("brand") and naver["brand"] not in brands:
        brands.append(naver["brand"])
    data["brands"] = brands[:5]

    # ── 스키마 검증 + 옵션 10개 상한 ────────────────────
    opts = data.get("suggested_options") or []
    data["suggested_options"] = opts[:10]

    # ── 브랜드 일관성 후처리 ────────────────────────────
    main_brand = (data.get("brand") or "").strip()
    if main_brand:
        for opt in data["suggested_options"]:
            # "브랜드" 옵션이면 brands 리스트와 동기화
            if isinstance(opt, dict) and (opt.get("title") or "").strip() in ("브랜드", "brand", "Brand"):
                opt["values"] = data["brands"][:5] if data.get("brands") else [main_brand]
                if main_brand in opt["values"]:
                    opt["selected_value"] = main_brand

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

        # ── 가격 재계산 모드 (옵션 변경 시 네이버 검색만) ──
        if body.recalc_price:
            recalc_brand = (body.brand or "").strip()
            # 브랜드를 검색 쿼리에 포함
            parts = []
            if recalc_brand and recalc_brand.lower() not in raw_title.lower():
                parts.append(recalc_brand)
            parts.append(raw_title)
            if body.selected_options:
                parts.append(body.selected_options)
            search_q = " ".join(parts)
            naver_items = _fetch_naver_items(search_q, display=10)
            naver = None
            if naver_items:
                naver = _select_best_product(
                    {"canonical_name": raw_title, "brand": recalc_brand, "category": "", "expected_price_range": []},
                    naver_items,
                )
            price_data: dict = {}
            if naver and naver["lowest_price"] > 0:
                price_data["center_price"] = float(naver["lowest_price"])
                price_data["naver_lowest_price"] = naver["lowest_price"]
                price_data["naver_product_name"] = naver["product_name"]
                price_data["naver_product_url"] = naver["link"]
                price_data["naver_mall_name"] = naver["mall_name"]
                price_data["price_source"] = "naver"
                price_data["commentary"] = (
                    f"네이버 최저가 {naver['lowest_price']:,}원 기준"
                    + (f" ({naver['mall_name']})" if naver.get("mall_name") else "")
                    + ". 옵션 반영 재계산 결과입니다."
                )
                price_data["desired_price_suggestion"] = round(naver["lowest_price"] * 0.95, -2)
                price_data["max_budget_suggestion"] = round(naver["lowest_price"] * 1.05, -2)
            else:
                price_data["price_source"] = "llm_estimate"
                price_data["commentary"] = "해당 옵션의 정확한 시장가를 찾지 못했어요."

            # 가격 근거 분석 (브랜드 필터 포함)
            analysis = _analyze_market_prices(
                naver_items, brand=recalc_brand or None,
                search_query=search_q,
            ) if naver_items else None

            # 3중 소스 합의
            consensus = None
            try:
                from app.services.price_consensus import build_price_consensus
                pa = analysis.model_dump() if analysis else {}
                consensus = build_price_consensus(
                    product_name=raw_title,
                    brand=recalc_brand,
                    options=body.selected_options or "",
                    naver_lowest=pa.get("lowest_price") or 0,
                    naver_included_items=[
                        {"title": it.title, "price": it.price, "link": it.link or "", "mall": it.mall or ""}
                        for it in (analysis.included_items if analysis else [])
                    ],
                    naver_total_included=pa.get("total_included", 0),
                )
            except Exception as e:
                print(f"[CONSENSUS] recalc 에러: {e}", flush=True)

            recalc_result = DealAIResponse(
                canonical_name=raw_title,
                model_name=raw_title,
                suggested_options=[],
                price=PriceSuggestion(**price_data),
                price_analysis=analysis,
                price_consensus=consensus,
            )
            return recalc_result

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


# ─────────────────────────────────────────────
# 이미지 인식 엔드포인트 (GPT-4o Vision)
# ─────────────────────────────────────────────

class ImageRecognizeResponse(BaseModel):
    product_name: str = ""
    brand: Optional[str] = None
    model_name: Optional[str] = None
    specs: Optional[str] = None
    confidence: str = "low"  # "high" | "medium" | "low"


@router.post("/image-recognize", response_model=ImageRecognizeResponse)
async def image_recognize(file: UploadFile = File(...)):
    """
    사진에서 제품을 인식하고 상품명/브랜드/모델/스펙을 반환.
    GPT-4o Vision API 사용.
    """
    # ── 파일 검증 ──
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="이미지 파일만 업로드할 수 있습니다.")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10MB 제한
        raise HTTPException(status_code=400, detail="파일 크기는 10MB 이하여야 합니다.")

    # ── base64 인코딩 ──
    b64 = base64.b64encode(contents).decode("utf-8")
    mime = file.content_type or "image/jpeg"
    data_url = f"data:{mime};base64,{b64}"

    # ── GPT-4o Vision 호출 ──
    try:
        client = get_client()
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "이 사진에서 상품을 인식해주세요. "
                                "반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만:\n"
                                '{"product_name": "한국어 상품명", '
                                '"brand": "브랜드명 또는 null", '
                                '"model_name": "모델명 또는 null", '
                                '"specs": "주요 스펙 한줄 또는 null", '
                                '"confidence": "high 또는 medium 또는 low"}'
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url, "detail": "low"},
                        },
                    ],
                }
            ],
            max_tokens=200,
            temperature=0,
            timeout=15,
        )
        text = (resp.choices[0].message.content or "").strip()
        data = _parse_json_safely(text)
        return ImageRecognizeResponse(**data)

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        print(f"[image-recognize] ERROR: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"이미지 인식 실패: {e.__class__.__name__}")


# ─────────────────────────────────────────────
# 음성 인식 엔드포인트 (Whisper STT + GPT Parse)
# ─────────────────────────────────────────────

class VoiceRecognizeResponse(BaseModel):
    success: bool = True
    transcript: str = ""
    product_query: Optional[str] = None
    brand: Optional[str] = None
    product_name: Optional[str] = None
    target_price: Optional[int] = None
    quantity: Optional[int] = None
    options: Optional[List[str]] = None
    confidence: str = "low"  # "high" | "medium" | "low"


@router.post("/voice-recognize", response_model=VoiceRecognizeResponse)
async def voice_recognize(file: UploadFile = File(...)):
    """
    음성 파일 → Whisper STT → GPT-4o-mini 파싱 → 구조화된 딜 정보 반환.
    지원 형식: webm, mp4, wav, m4a, ogg, mp3
    """
    import io, traceback

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    print(f"[VOICE-API] === 음성 인식 시작 ===", flush=True)
    print(f"[VOICE-API] filename={file.filename} content_type={file.content_type} parsed={content_type}", flush=True)

    allowed_types = {
        "audio/webm", "audio/mp4", "audio/wav", "audio/x-wav",
        "audio/m4a", "audio/ogg", "audio/mpeg", "audio/mp3",
        "video/webm",  # MediaRecorder가 video/webm으로 보낼 수 있음
        "application/octet-stream",  # fallback
    }
    if content_type not in allowed_types:
        print(f"[VOICE-API] 지원하지 않는 형식: {content_type}", flush=True)
        raise HTTPException(status_code=400, detail=f"지원하지 않는 오디오 형식입니다: {content_type}")

    contents = await file.read()
    print(f"[VOICE-API] file size={len(contents)} bytes", flush=True)

    if len(contents) > 25 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="파일 크기는 25MB 이하여야 합니다.")

    if len(contents) < 100:
        print(f"[VOICE-API] 파일 너무 작음", flush=True)
        return VoiceRecognizeResponse(
            success=False, transcript="",
            confidence="low",
        )

    transcript = ""  # 에러 핸들링용 미리 선언
    try:
        client = get_client()

        # ── 1단계: Whisper STT ──
        # 확장자 결정 (content_type 또는 파일명 기준)
        fname = (file.filename or "").lower()
        ext = "webm"
        if "wav" in content_type or fname.endswith(".wav"):
            ext = "wav"
        elif "mp4" in content_type or "m4a" in content_type or fname.endswith(".mp4") or fname.endswith(".m4a"):
            ext = "m4a"
        elif "ogg" in content_type or fname.endswith(".ogg"):
            ext = "ogg"
        elif "mpeg" in content_type or "mp3" in content_type or fname.endswith(".mp3"):
            ext = "mp3"
        print(f"[VOICE-API] ext={ext}", flush=True)

        audio_file = io.BytesIO(contents)
        audio_file.name = f"voice.{ext}"

        print(f"[VOICE-API] calling Whisper...", flush=True)
        whisper_resp = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="ko",
        )
        transcript = (whisper_resp.text or "").strip()
        print(f"[VOICE-API] transcript: '{transcript}'", flush=True)

        if not transcript or len(transcript) < 2:
            print(f"[VOICE-API] 빈/짧은 transcript", flush=True)
            return VoiceRecognizeResponse(
                success=False,
                transcript=transcript,
                confidence="low",
            )

        # ── 2단계: GPT 구조화 파싱 ──
        print(f"[VOICE-API] GPT 파싱 시작...", flush=True)
        parse_prompt = (
            "사용자가 음성으로 공동구매 딜을 만들려고 합니다.\n"
            "아래 음성 텍스트에서 상품 정보를 추출해 JSON으로 응답하세요.\n"
            "반드시 JSON만 응답하세요. 다른 텍스트 없이:\n\n"
            f"음성 텍스트: \"{transcript}\"\n\n"
            "JSON 형식:\n"
            "{\n"
            '  "product_query": "검색에 사용할 상품명 (예: 에어팟 프로 2세대)",\n'
            '  "brand": "브랜드명 또는 null",\n'
            '  "product_name": "정식 상품명 또는 null",\n'
            '  "target_price": 희망가격(숫자) 또는 null,\n'
            '  "quantity": 수량(숫자) 또는 null,\n'
            '  "options": ["색상:화이트", "용량:256GB"] 또는 [],\n'
            '  "confidence": "high" 또는 "medium" 또는 "low"\n'
            "}\n\n"
            "규칙:\n"
            "- product_query는 반드시 채워주세요\n"
            "- 가격 언급이 있으면 target_price에 숫자로 (만원 → ×10000)\n"
            "- 수량 언급이 없으면 quantity는 null\n"
            "- 옵션(색상, 용량, 사이즈 등) 언급이 있으면 options에\n"
            "- confidence: 상품이 명확하면 high, 애매하면 medium, 알 수 없으면 low"
        )

        parse_resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": parse_prompt}],
            temperature=0.1,
            max_tokens=300,
            timeout=15,
        )
        parse_text = (parse_resp.choices[0].message.content or "").strip()
        print(f"[VOICE-API] GPT raw: {parse_text[:200]}", flush=True)
        parsed = _parse_json_safely(parse_text)
        print(f"[VOICE-API] parsed: {parsed}", flush=True)

        # product_query가 없으면 transcript를 fallback
        if not parsed.get("product_query"):
            parsed["product_query"] = transcript

        result = VoiceRecognizeResponse(
            success=True,
            transcript=transcript,
            product_query=parsed.get("product_query"),
            brand=parsed.get("brand"),
            product_name=parsed.get("product_name"),
            target_price=parsed.get("target_price"),
            quantity=parsed.get("quantity"),
            options=parsed.get("options", []),
            confidence=parsed.get("confidence", "medium"),
        )
        print(f"[VOICE-API] 최종 결과: success={result.success} product_query={result.product_query}", flush=True)
        return result

    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        print(f"[VOICE-API] ERROR: {e}", flush=True)
        traceback.print_exc()
        return VoiceRecognizeResponse(
            success=False,
            transcript=transcript,
            confidence="low",
        )
