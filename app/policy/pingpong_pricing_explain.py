#app/policy/pingpong_pricing_explain.py

# PINGPONG_PRICING_EXPLAIN_RULES_SSOT_v1 renderer
# ADMIN ONLY — BUYER/SELLER 응답 근거로 사용 금지
#
# 역할:
# - Preview Pack pricing payload를 "핑퐁이 4줄 템플릿"으로 안정적으로 렌더링
# - phrase key 정규화 (vs_groupbuy_offer_cap -> vs_group)
# - 숫자 포맷: 원 단위 정수 + 천단위 콤마
# - intent gate: pricing 질문이면 일반론/절차 설명으로 새지 않게(최소)

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


def _krw(n: Optional[float | int]) -> str:
    """원 단위 정수 + 콤마. None이면 '미정'."""
    if n is None:
        return "미정"
    try:
        return f"{int(round(float(n))):,}"
    except Exception:
        return "미정"


def _safe_get(d: Any, *path: str, default=None):
    cur = d
    for k in path:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(k)
        else:
            cur = getattr(cur, k, None)
    return default if cur is None else cur


def normalize_pricing_phrases(pricing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize phrase keys to SSOT canonical keys:
      - vs_expected
      - vs_group (optional)
    """
    if not isinstance(pricing, dict):
        return pricing

    oe = pricing.get("offer_evaluation") or {}
    phrases = (oe.get("phrases") or {}) if isinstance(oe, dict) else {}
    if not isinstance(phrases, dict):
        return pricing

    # canonical
    vs_expected = phrases.get("vs_expected") or phrases.get("vs_base")

    # group aliases we have seen in earlier payloads
    vs_group = (
        phrases.get("vs_group")
        or phrases.get("vs_groupbuy_offer_cap")
        or phrases.get("vs_groupbuy_offer_capability")
        or phrases.get("vs_groupbuy")
    )

    # rebuild phrases in canonical form (preserve other keys if needed)
    new_phrases = dict(phrases)
    if vs_expected is not None:
        new_phrases["vs_expected"] = vs_expected
    if vs_group is not None:
        new_phrases["vs_group"] = vs_group

    # write back
    new_oe = dict(oe) if isinstance(oe, dict) else {}
    new_oe["phrases"] = new_phrases
    pricing2 = dict(pricing)
    pricing2["offer_evaluation"] = new_oe
    return pricing2


@dataclass(frozen=True)
class PricingExplainLines:
    line1: str
    line2: str
    line3: str
    line4: str
    note: Optional[str] = None  # optional 5th line (guardrail notice only)

    def as_text(self, include_note: bool = True) -> str:
        if include_note and self.note:
            return "\n".join([self.line1, self.line2, self.line3, self.line4, self.note])
        return "\n".join([self.line1, self.line2, self.line3, self.line4])


def render_pingpong_pricing_explain(
    preview_pack: Dict[str, Any],
    *,
    include_group_phrase: bool = False,
    include_note: bool = True,
) -> PricingExplainLines:
    """
    Input: Preview Pack 전체 응답(pack 포함) 또는 pack dict.
    Expected shape:
      - pack.pricing.reference.p_target
      - pack.pricing.offer_evaluation.seller_offer_price
      - pack.pricing.offer_evaluation.expected_price_under_offer_conditions
      - pack.pricing.offer_evaluation.phrases.vs_expected
      - pack.pricing.offer_evaluation.phrases.vs_group (optional)
    """
    # accept either whole response or pack
    pack = preview_pack.get("pack") if isinstance(preview_pack, dict) else None
    if isinstance(pack, dict):
        p = pack
    else:
        p = preview_pack

    pricing = _safe_get(p, "pricing", default=None)
    if isinstance(pricing, dict):
        pricing = normalize_pricing_phrases(pricing)
    else:
        pricing = None

    p_offer = _safe_get(pricing, "offer_evaluation", "seller_offer_price", default=None)
    p_expected = _safe_get(pricing, "offer_evaluation", "expected_price_under_offer_conditions", default=None)
    p_target = _safe_get(pricing, "reference", "p_target", default=None)

    phrase_expected = _safe_get(pricing, "offer_evaluation", "phrases", "vs_expected", default=None)
    phrase_group = _safe_get(pricing, "offer_evaluation", "phrases", "vs_group", default=None)

    # Lines (SSOT 4-line template)
    line1 = f"판매자 제시가: {_krw(p_offer)}원 (고정)"
    line2 = f"목표가(딜방 입력): {_krw(p_target)}원" if p_target is not None else "목표가(딜방 입력): 아직 미정"
    line3 = f"표준조건 환산 기대가: {_krw(p_expected)}원"

    # Phrase line (do not invent; only use server phrases)
    parts = []
    if isinstance(phrase_expected, str) and phrase_expected.strip():
        parts.append(phrase_expected.strip())
    if include_group_phrase and isinstance(phrase_group, str) and phrase_group.strip():
        parts.append(phrase_group.strip())

    if parts:
        line4 = "한줄 해석: " + " / ".join(parts)
    else:
        # safe fallback: do not generate "싸다/비싸다"
        line4 = "한줄 해석: (비교 문구 준비중)"

    note = None
    if include_note:
        # keep it short, SSOT-safe
        note = "※ 판매자 가격은 고정이고, 역핑은 비교 기준만 제공합니다."

    return PricingExplainLines(line1=line1, line2=line2, line3=line3, line4=line4, note=note)


# -------------------------------------------------------
# Intent gate (minimal)
# -------------------------------------------------------
PRICING_INTENT_KEYWORDS = {
    "가격", "프리뷰", "preview", "랭킹", "ranked", "오퍼", "offer", "목표가", "기준가", "기대가", "공동구매"
}


def is_pricing_intent(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return any(k in t for k in PRICING_INTENT_KEYWORDS)
