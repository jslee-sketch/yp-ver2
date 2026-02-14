# app/policy/pricing_engine.py
from __future__ import annotations

import re
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import yaml

# -------------------------
# Data models
# -------------------------
@dataclass(frozen=True)
class PriceInputs:
    # reference price inputs
    p_anchor: Optional[float]  # async anchor, may be None
    p_base: float              # always present
    p_target: Optional[float]  # buyer proposed price, may be None

    # group state
    q: int                     # current group size >=1
    q_target: Optional[int]    # optional override

    # category
    category: str              # e.g. "electronics", "food", "default"

    # offer conditions (optional / may be partial)
    ship_days: Optional[float] = None
    shipping_fee_krw: Optional[float] = None
    refund_grade: Optional[int] = None    # 0..3
    as_grade: Optional[int] = None        # 0..3
    seller_tier: Optional[int] = None     # 0..3
    seller_score: Optional[float] = None  # 0..100
    risk_level: Optional[int] = None      # 0..3 (offer observed)


@dataclass(frozen=True)
class PriceOutputs:
    # which baseline we used
    base_used: str           # "anchor" | "base"
    p_ref: float             # reference price used for group baseline
    p_group: float           # group baseline price (P_group)

    # translation components
    delta_cond: float        # dimensionless (-0.12..0.18)
    delta_price_equiv: float # KRW equivalent (basis price * delta_cond)

    # convenience / UI-facing comparisons
    compare_base_label: str
    compare_base_amount_krw: int
    compare_group_label: str
    compare_group_amount_krw: int

    # debug
    details: Dict[str, Any]


# -------------------------
# Loader
# -------------------------
def load_pricing_params(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# -------------------------
# Helpers
# -------------------------
def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _norm_0_3_to_pm1(v: Optional[int], baseline: int = 2) -> float:
    # 0..3 -> [-1, +1] around baseline=1.5~2; keep it simple
    if v is None:
        v = baseline
    return _clamp((float(v) - 1.5) / 1.5, -1.0, 1.0)


def _norm_ship_speed(ship_days: Optional[float], baseline_days: float, lo: float, hi: float) -> float:
    # faster than baseline => positive
    if ship_days is None:
        ship_days = baseline_days
    if baseline_days <= 0:
        return 0.0
    raw = (baseline_days - float(ship_days)) / baseline_days
    return _clamp(raw, lo, hi)


def _norm_shipping_fee(fee: Optional[float], baseline_fee: float, scale: float) -> float:
    # higher fee than baseline => negative
    if fee is None:
        fee = baseline_fee
    raw = (baseline_fee - float(fee)) / max(1.0, float(scale))
    return _clamp(raw, -1.0, 1.0)


def _norm_seller_score(score: Optional[float], baseline_score: float, scale: float) -> float:
    if score is None:
        score = baseline_score
    raw = (float(score) - float(baseline_score)) / max(1.0, float(scale))
    return _clamp(raw, -1.0, 1.0)


def _pick_category(params: Dict[str, Any], category: str) -> Dict[str, Any]:
    cats = (params.get("categories") or {})
    if category in cats:
        return cats[category]
    return cats.get("default") or {}


def _label_for_delta(amount_krw: float, deadzone_krw: float = 500.0) -> str:
    # amount_krw: positive => expensive, negative => cheaper
    if abs(amount_krw) <= deadzone_krw:
        return "유사"
    return "비쌈" if amount_krw > 0 else "저렴"


def _sanitize_text(s: str) -> str:
    """
    Normalize whitespace to prevent broken Korean spacing like '기 준', double spaces, etc.
    """
    if not s:
        return s
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s

def _label_for_delta_with_ref(params: Dict[str, Any], delta_krw: float, ref_price: Optional[float]) -> str:
    """
    Decide label using BOTH:
      - absolute KRW threshold
      - percentage threshold vs reference price (expected/group)
    Uses SSOT:
      phrasing.similarity.similar_pct
      phrasing.similarity.min_similar_krw
    """
    # fallback to old behavior if ref missing
    ref = float(ref_price or 0.0)
    amt = abs(float(delta_krw))

    phr = (params.get("phrasing") or {})
    sim = (phr.get("similarity") or {})
    similar_pct = float(sim.get("similar_pct", 0.01) or 0.01)
    min_similar_krw = float(sim.get("min_similar_krw", 300) or 300)

    # percentage-based window (if ref is valid)
    pct_window = 0.0
    if ref > 0:
        pct_window = ref * similar_pct

    # use the larger window to avoid over-reacting on tiny prices
    similar_window = max(min_similar_krw, pct_window)

    if amt <= similar_window:
        return "유사"
    return "비쌈" if delta_krw > 0 else "저렴"




# -------------------------
# Core computations
# -------------------------
def compute_reference_price(p_anchor: Optional[float], p_base: float) -> Tuple[str, float]:
    if p_anchor is not None and p_anchor > 0:
        return "anchor", float(p_anchor)
    return "base", float(p_base)


def compute_group_price(
    params: Dict[str, Any],
    p_ref: float,
    q: int,
    q_target_override: Optional[int],
    category: str,
) -> Tuple[float, Dict[str, Any]]:
    q = max(1, int(q))
    cat = _pick_category(params, category)

    group_cfg = params.get("group_index") or {}
    eps = float(group_cfg.get("epsilon") or 1e-6)

    alpha_g = float(cat.get("alpha_g") or group_cfg.get("alpha_g_default") or 0.0)
    alpha_g = _clamp(alpha_g, float(group_cfg.get("alpha_g_min") or 0.0), float(group_cfg.get("alpha_g_max") or 0.15))

    q_target = int(q_target_override or cat.get("q_target") or group_cfg.get("q_target_default") or 10)
    q_target = max(1, q_target)

    # log saturation
    g = math.log(1.0 + q)
    g1 = math.log(2.0)  # q=1 => log(2)
    gt = math.log(1.0 + q_target)
    denom = max(eps, (gt - g1))
    g_norm = _clamp((g - g1) / denom, 0.0, 1.0)

    delta_g = alpha_g * g_norm  # 0..alpha_g
    p_group_raw = p_ref * (1.0 - delta_g)

    clamp_cfg = cat.get("clamp") or {}
    min_ratio = float(clamp_cfg.get("p_group_min_ratio") or (1.0 - float(group_cfg.get("alpha_g_max") or 0.15)))
    max_ratio = float(clamp_cfg.get("p_group_max_ratio") or 1.0)

    p_group = _clamp(p_group_raw, p_ref * min_ratio, p_ref * max_ratio)

    details = {
        "q": q,
        "q_target": q_target,
        "alpha_g": alpha_g,
        "g_norm": g_norm,
        "delta_g": delta_g,
        "p_group_raw": p_group_raw,
        "p_group": p_group,
        "clamp": {"min_ratio": min_ratio, "max_ratio": max_ratio},
    }
    return p_group, details


def compute_translation_delta(
    params: Dict[str, Any],
    inp: PriceInputs,
    category: str,
) -> Tuple[float, Dict[str, Any]]:
    cat = _pick_category(params, category)
    base = params.get("base_condition") or {}
    trans = params.get("translation") or {}
    weights = (trans.get("weights") or {})
    norm = (trans.get("normalization") or {})

    # baselines
    ship_base_days = float(((base.get("shipping") or {}).get("ship_days_baseline") or 3))
    ship_base_fee = float(((base.get("shipping") or {}).get("shipping_fee_baseline_krw") or 0))
    refund_base = int(((base.get("refund") or {}).get("refund_grade_baseline") or 2))
    as_base = int(((base.get("refund") or {}).get("as_grade_baseline") or 2))
    tier_base = int(((base.get("seller") or {}).get("seller_tier_baseline") or 2))
    score_base = float(((base.get("seller") or {}).get("seller_score_baseline") or 70))

    # risk baseline per category
    r0 = int(cat.get("r0_risk_level") or ((base.get("risk") or {}).get("risk_level_baseline") or 2))

    # normalize components (-1..+1)
    ship_speed = _norm_ship_speed(
        inp.ship_days,
        ship_base_days,
        float(norm.get("ship_speed_clamp_min") or -1.0),
        float(norm.get("ship_speed_clamp_max") or 1.0),
    )
    ship_fee = _norm_shipping_fee(
        inp.shipping_fee_krw,
        ship_base_fee,
        float(norm.get("shipping_fee_scale_krw") or 5000),
    )
    refund = _norm_0_3_to_pm1(inp.refund_grade, refund_base)
    asv = _norm_0_3_to_pm1(inp.as_grade, as_base)
    # combine refund/as (simple average)
    refund_as = _clamp((refund + asv) / 2.0, -1.0, 1.0)

    seller_tier = _norm_0_3_to_pm1(inp.seller_tier, tier_base)
    seller_score = _norm_seller_score(inp.seller_score, score_base, float(norm.get("seller_score_scale") or 30))
    seller_trust = _clamp((seller_tier + seller_score) / 2.0, -1.0, 1.0)

    risk_obs = inp.risk_level if inp.risk_level is not None else r0
    # ΔR normalized to [-1,+1] by simple scaling / clamp
    delta_r = _clamp(float(risk_obs - r0), float(norm.get("risk_delta_clamp_min") or -1.0), float(norm.get("risk_delta_clamp_max") or 1.0))
    # interpretation: higher risk => negative impact on willingness
    # (we keep sign in weight so it can flip later if needed)
    risk_component = _clamp(delta_r, -1.0, 1.0)

    # weights
    w_ship_speed = float(weights.get("shipping_speed") or 0.0)
    w_ship_fee = float(weights.get("shipping_fee") or 0.0)
    w_refund = float(weights.get("refund") or 0.0)
    w_seller = float(weights.get("seller_trust") or 0.0)
    w_risk = float(weights.get("risk") or 0.0)

    delta = (
        w_ship_speed * ship_speed +
        w_ship_fee * ship_fee +
        w_refund * refund_as +
        w_seller * seller_trust +
        w_risk * (-risk_component)  # higher risk => tends to lower willingness (negative premium)
    )

    # clamp delta_cond
    delta_min = float(trans.get("delta_cond_min") or -0.12)
    delta_max = float(trans.get("delta_cond_max") or 0.18)
    delta_clamped = _clamp(delta, delta_min, delta_max)

    details = {
        "baselines": {
            "ship_days": ship_base_days,
            "shipping_fee_krw": ship_base_fee,
            "refund_grade": refund_base,
            "as_grade": as_base,
            "seller_tier": tier_base,
            "seller_score": score_base,
            "r0_risk_level": r0,
        },
        "components": {
            "ship_speed": ship_speed,
            "ship_fee": ship_fee,
            "refund_as": refund_as,
            "seller_trust": seller_trust,
            "risk_obs": int(risk_obs),
            "risk_delta": float(risk_obs - r0),
            "risk_component": risk_component,
        },
        "weights": {
            "shipping_speed": w_ship_speed,
            "shipping_fee": w_ship_fee,
            "refund": w_refund,
            "seller_trust": w_seller,
            "risk": w_risk,
        },
        "delta_raw": delta,
        "delta_clamped": delta_clamped,
        "clamp": {"min": delta_min, "max": delta_max},
    }
    return delta_clamped, details


def compute_pricing(
    params: Dict[str, Any],
    inp: PriceInputs,
) -> PriceOutputs:
    base_used, p_ref = compute_reference_price(inp.p_anchor, inp.p_base)

    # group baseline
    p_group, group_details = compute_group_price(
        params=params,
        p_ref=p_ref,
        q=inp.q,
        q_target_override=inp.q_target,
        category=inp.category,
    )

    # condition translation delta (dimensionless)
    delta_cond, trans_details = compute_translation_delta(params=params, inp=inp, category=inp.category)

    # basis for KRW equivalent
    trans_cfg = params.get("translation") or {}
    basis_price = trans_cfg.get("basis_price") or "p0"
    basis = p_ref if basis_price == "p0" else p_group

    delta_price_equiv = basis * delta_cond

    # comparisons for UI (interpretation layer)
    # base compare: P_offer vs "expected baseline under offer conditions" is not computed here (needs offer price input)
    # Instead we provide "condition equivalent" and "group delta" comparisons for narrative.
    compare_base_label = _label_for_delta(delta_price_equiv)
    compare_base_amount = int(round(abs(delta_price_equiv)))

    # group compare is same delta but stated against group baseline if desired
    # (you can choose to base on p_group by setting basis_price=p_group)
    compare_group_label = compare_base_label
    compare_group_amount = compare_base_amount

    out = PriceOutputs(
        base_used=base_used,
        p_ref=float(p_ref),
        p_group=float(p_group),
        delta_cond=float(delta_cond),
        delta_price_equiv=float(delta_price_equiv),
        compare_base_label=compare_base_label,
        compare_base_amount_krw=compare_base_amount,
        compare_group_label=compare_group_label,
        compare_group_amount_krw=compare_group_amount,
        details={
            "group": group_details,
            "translation": trans_details,
            "basis_price": basis_price,
        },
    )
    return out


def render_compare_phrases(params: Dict[str, Any], out: PriceOutputs) -> Dict[str, str]:
    phr = (params.get("phrasing") or {})
    tpl = (phr.get("templates") or {})
    labels = (phr.get("labels") or {})

    def _label_word(label: str) -> str:
        if label == "비쌈":
            return labels.get("expensive") or "비쌈"
        if label == "저렴":
            return labels.get("cheaper") or "저렴"
        return labels.get("similar") or "유사"

    # Use our canonical "기준조건 대비 {amount}원 비쌈/저렴"
    base_phrase = (tpl.get("compare_base") or "기준조건 대비 {amount_krw}원 {label}").format(
        amount_krw=out.compare_base_amount_krw,
        label=_label_word(out.compare_base_label),
    )
    group_phrase = (tpl.get("compare_group") or "공동구매 기준 대비 {amount_krw}원 {label}").format(
        amount_krw=out.compare_group_amount_krw,
        label=_label_word(out.compare_group_label),
    )
    return {"compare_base": base_phrase, "compare_group": group_phrase}


# -------------------------
# Offer comparison (seller price stays fixed)
# -------------------------
@dataclass(frozen=True)
class OfferComparison:
    p_offer: float
    p_expected: float  # reference baseline under offer conditions (for comparison only)

    # signed deltas
    delta_offer_vs_expected: float  # >0 means offer is expensive vs expected
    delta_offer_vs_p0: float        # vs P_ref (optional, interpret carefully)
    delta_offer_vs_pgroup: float    # vs P_group (optional)

    # UI phrases (canonical)
    phrase_vs_expected: str
    phrase_vs_group: str

    details: Dict[str, Any]


def compute_offer_expected_price(out: PriceOutputs) -> float:
    """
    Compute comparison-only expected price under offer conditions.
    IMPORTANT: This does NOT change seller price. It's only a lens for interpretation.
    """
    return float(out.p_group * (1.0 + out.delta_cond))


def _phrase(label_prefix: str, amount_krw: float) -> str:
    """
    Canonical rendering (short & safe):
    - always show absolute amount (avoid '-' sign misread)
    - keep phrases short: "{prefix} {amt}원 비쌈/저렴/유사"
    - normalize whitespace to avoid "기준조건 대 비" artifacts
    """
    lbl = _label_for_delta(amount_krw)
    amt = int(round(abs(float(amount_krw or 0.0))))

    if lbl == "유사":
        # keep it crisp and consistent
        s = f"{label_prefix} {amt:,}원 유사" if amt > 0 else f"{label_prefix} 유사"
    else:
        s = f"{label_prefix} {amt:,}원 {lbl}"

    # whitespace normalize (protect against template/newline issues)
    return " ".join(str(s).split())


def compute_offer_comparison(
    params: Dict[str, Any],
    out: PriceOutputs,
    p_offer: float,
) -> OfferComparison:
    """
    Compare seller fixed offer price vs reference expectations.
    Returns interpretation strings; never mutates p_offer.
    """
    p_offer_f = float(p_offer)
    p_expected = compute_offer_expected_price(out)

    # primary comparison: offer vs expected (under offer conditions, on group baseline)
    delta_vs_expected = p_offer_f - p_expected

    # optional references (for debug / secondary UX)
    delta_vs_p0 = p_offer_f - out.p_ref
    delta_vs_pgroup = p_offer_f - out.p_group

    # Use SSOT phrasing templates if present
    phr = (params.get("phrasing") or {})
    tpl = (phr.get("templates") or {})

    prefix_base = "기준조건 대비"
    prefix_group = "공동구매 기준 대비"

    phrase_expected = _phrase(prefix_base, delta_vs_expected)
    phrase_group = _phrase(prefix_group, delta_vs_pgroup)

    if tpl.get("compare_base") and tpl.get("compare_group"):
        amt_expected = int(round(abs(delta_vs_expected)))
        amt_group = int(round(abs(delta_vs_pgroup)))

        lbl_expected = _label_for_delta_with_ref(params, delta_vs_expected, p_expected)
        lbl_group = _label_for_delta_with_ref(params, delta_vs_pgroup, out.p_group)

        if lbl_expected == "유사":
            phrase_expected = "기준조건 대비 유사"
        else:
            phrase_expected = tpl["compare_base"].format(amount_krw=amt_expected, label=lbl_expected)

        if lbl_group == "유사":
            phrase_group = "공동구매 기준 대비 유사"
        else:
            phrase_group = tpl["compare_group"].format(amount_krw=amt_group, label=lbl_group)

    # ✅ 최종 sanitize (어디서든 공백/줄바꿈 깨짐 방지)
    phrase_expected = _sanitize_text(phrase_expected)
    phrase_group = _sanitize_text(phrase_group)


    return OfferComparison(
        p_offer=p_offer_f,
        p_expected=float(p_expected),
        delta_offer_vs_expected=float(delta_vs_expected),
        delta_offer_vs_p0=float(delta_vs_p0),
        delta_offer_vs_pgroup=float(delta_vs_pgroup),
        phrase_vs_expected=phrase_expected,
        phrase_vs_group=phrase_group,
        details={
            "p_ref": out.p_ref,
            "p_group": out.p_group,
            "delta_cond": out.delta_cond,
            "delta_price_equiv": out.delta_price_equiv,
            "basis_price": out.details.get("basis_price"),
        },
    )
