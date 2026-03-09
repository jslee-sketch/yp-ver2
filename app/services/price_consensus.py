# app/services/price_consensus.py
"""
3중 소스 가격 합의 엔진
네이버 쇼핑 + 쿠팡 파트너스 + GPT-4o 추정 → 교차 검증 → 신뢰도 등급
"""

from __future__ import annotations

import re
from typing import Optional

from app.services.coupang_search import search_coupang_products
from app.services.gpt_price_estimator import estimate_price_with_gpt


# ── 필터 패턴 (deal_ai_helper와 동일) ──
_ACCESSORY_RE = re.compile(
    r"케이스|커버|필름|충전기|어댑터|거치대|파우치|스트랩|이어팁|리모컨|보호|캡|젤리|범퍼|강화유리",
    re.IGNORECASE,
)
_BUNDLE_RE = re.compile(r"세트|묶음|패키지|번들|기획전|합본", re.IGNORECASE)
_USED_RE = re.compile(r"중고|리퍼|반품|전시|매입|S급|A급|B급|재생|수리", re.IGNORECASE)

_SUSPICION_THRESHOLD = 0.01  # 목표가 대비 1% 미만이면 의심
_HIGH_AGREEMENT = 0.15  # 소스 간 15% 이내 → HIGH
_MED_AGREEMENT = 0.30  # 30% 이내 → MEDIUM


# ── 신뢰도 라벨 ──
_CONFIDENCE_MAP = {
    "high": {"emoji": "🟢", "label": "신뢰도 높음", "color": "#4ade80"},
    "medium": {"emoji": "🟡", "label": "신뢰도 보통", "color": "#f59e0b"},
    "low": {"emoji": "🔴", "label": "신뢰도 낮음", "color": "#ef4444"},
    "not_available": {"emoji": "⚫", "label": "온라인 판매 불가", "color": "#888"},
    "none": {"emoji": "⚫", "label": "정보 없음", "color": "#888"},
}


def build_price_consensus(
    product_name: str,
    brand: str = "",
    options: str = "",
    user_target_price: int = 0,
    naver_lowest: int = 0,
    naver_included_items: Optional[list] = None,
    naver_total_included: int = 0,
) -> dict:
    """
    3중 소스 가격 합의.
    Returns dict with: market_price, confidence, sources[], notice, fallback_price 등.
    """
    sources: list[dict] = []

    # ═══ 소스 1: 네이버 (이미 분석됨 — 호출자가 전달) ═══
    if naver_lowest and naver_lowest > 0:
        sources.append({
            "source": "naver",
            "source_label": "네이버쇼핑",
            "price": naver_lowest,
            "lowest_price": naver_lowest,
            "items": (naver_included_items or [])[:3],
            "count": naver_total_included,
        })

    # 모델번호 추출
    from app.routers.deal_ai_helper import _extract_model_numbers
    query_models = _extract_model_numbers(product_name)

    # ═══ 소스 2: 쿠팡 ═══
    try:
        sq = f"{brand} {product_name}".strip() if brand else product_name
        raw_items = search_coupang_products(sq, limit=10)
        filtered = _filter_items(raw_items, query_models=query_models)
        if filtered:
            filtered.sort(key=lambda x: x["price"])
            prices = [it["price"] for it in filtered]
            cp = prices[len(prices) // 2] if len(prices) >= 3 else prices[0]
            sources.append({
                "source": "coupang",
                "source_label": "쿠팡",
                "price": cp,
                "lowest_price": prices[0],
                "items": [
                    {"title": f["title"], "price": f["price"], "link": f.get("link", "")}
                    for f in filtered[:3]
                ],
                "count": len(filtered),
            })
    except Exception as e:
        print(f"[CONSENSUS] 쿠팡 에러: {e}", flush=True)

    # ═══ 소스 3: GPT-4o 추정 ═══
    gpt_result: dict = {}
    try:
        gpt_result = estimate_price_with_gpt(product_name, brand, options, user_target_price)
        gp = gpt_result.get("estimated_price", 0)
        if gp and gp > 0:
            sources.append({
                "source": "gpt",
                "source_label": "AI 추정",
                "price": gp,
                "lowest_price": gpt_result.get("price_range_min", gp),
                "items": [],
                "count": 0,
                "confidence": gpt_result.get("confidence", "low"),
                "reasoning": gpt_result.get("reasoning", ""),
                "is_online_purchasable": gpt_result.get("is_online_purchasable", True),
                "category_hint": gpt_result.get("category_hint", ""),
            })
    except Exception as e:
        print(f"[CONSENSUS] GPT 에러: {e}", flush=True)

    # ═══ 교차 검증 ═══
    # 목표가 대비 의심 체크
    for s in sources:
        if user_target_price > 0 and s["price"] > 0:
            ratio = s["price"] / user_target_price
            if ratio < _SUSPICION_THRESHOLD:
                s["suspicious"] = True
                s["suspicion_reason"] = (
                    f"목표가({user_target_price:,}원) 대비 {ratio*100:.1f}%"
                    " — 부품/액세서리 가격일 수 있음"
                )
                print(
                    f"[CONSENSUS] {s['source']} 의심: "
                    f"{s['price']:,}원 vs 목표가 {user_target_price:,}원",
                    flush=True,
                )

    clean = [s for s in sources if not s.get("suspicious")]
    clean_prices = [s["price"] for s in clean if s["price"] > 0]

    # 온라인 구매 불가
    gpt_src = next((s for s in sources if s["source"] == "gpt"), None)
    if gpt_src and gpt_src.get("is_online_purchasable") is False:
        gp = gpt_src["price"]
        return _build(
            "not_available", gp, sources,
            notice=f"이 제품은 온라인 쇼핑몰에서 판매하지 않는 제품입니다. AI 추정가: 약 {gp:,}원",
            fallback_price=user_target_price if user_target_price > 0 else gp,
            user_target_price=user_target_price,
        )

    if not clean_prices:
        # 모든 소스가 의심 또는 없음
        fb = (gpt_src["price"] if gpt_src and gpt_src["price"] > 0 else 0) or user_target_price
        return _build(
            "low", fb, sources,
            notice="온라인 쇼핑몰 검색 결과가 정확하지 않아 AI 추정가를 표시합니다." if fb else "시장가 정보를 찾을 수 없습니다.",
            fallback_price=fb,
            user_target_price=user_target_price,
        )

    # 소스 간 일치도
    if len(clean_prices) >= 2:
        avg = sum(clean_prices) / len(clean_prices)
        max_dev = max(abs(p - avg) / avg for p in clean_prices) if avg > 0 else 1
        if max_dev < _HIGH_AGREEMENT:
            conf = "high"
        elif max_dev < _MED_AGREEMENT:
            conf = "medium"
        else:
            conf = "low"
    else:
        conf = "medium"

    # 최종 시장가: 네이버 > 쿠팡 > GPT
    naver_s = next((s for s in clean if s["source"] == "naver"), None)
    coupang_s = next((s for s in clean if s["source"] == "coupang"), None)
    gpt_s = next((s for s in clean if s["source"] == "gpt"), None)

    if naver_s:
        mp = naver_s["price"]
    elif coupang_s:
        mp = coupang_s["price"]
    elif gpt_s:
        mp = gpt_s["price"]
    else:
        mp = clean_prices[0]

    return _build(conf, mp, sources, user_target_price=user_target_price)


# ── helpers ──

def _filter_items(items: list, query_models: list[str] | None = None) -> list:
    """액세서리/묶음/중고/모델 불일치 제외."""
    out = []
    for it in items:
        title = it.get("title", "")
        if _ACCESSORY_RE.search(title):
            continue
        if _BUNDLE_RE.search(title):
            continue
        if _USED_RE.search(title):
            continue
        # 모델번호 불일치 제외
        if query_models:
            from app.routers.deal_ai_helper import _model_matches
            if not _model_matches(query_models, title):
                continue
        out.append(it)
    return out


def _build(
    confidence: str,
    market_price: int,
    sources: list,
    notice: str | None = None,
    fallback_price: int | None = None,
    user_target_price: int = 0,
) -> dict:
    c = _CONFIDENCE_MAP.get(confidence, _CONFIDENCE_MAP["none"])
    return {
        "market_price": market_price,
        "confidence": confidence,
        "confidence_emoji": c["emoji"],
        "confidence_label": c["label"],
        "confidence_color": c["color"],
        "sources": [
            {
                "source": s["source"],
                "source_label": s["source_label"],
                "price": s["price"],
                "lowest_price": s.get("lowest_price", s["price"]),
                "items": s.get("items", [])[:3],
                "count": s.get("count", 0),
                "suspicious": s.get("suspicious", False),
                "suspicion_reason": s.get("suspicion_reason", ""),
            }
            for s in sources
        ],
        "source_count": len([s for s in sources if s["price"] > 0 and not s.get("suspicious")]),
        "notice": notice,
        "fallback_price": fallback_price,
        "user_target_price": user_target_price,
    }
