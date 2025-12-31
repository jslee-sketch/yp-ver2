# app/policy/api.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Literal, Optional

from app.policy.runtime import get_policy
from app.core.refund_policy import compute_cooling_state as _core_compute_cooling_state

CoolingState = Literal[
    "WITHIN_COOLING",
    "AFTER_COOLING",
    "BEFORE_SHIPPING",
    "SHIPPED_NOT_DELIVERED",
]


# =========================================================
# Basic getters (YAML SSOT)
# =========================================================

def payment_timeout_minutes() -> int:
    return int(get_policy().time.payment_timeout_minutes)

def cooling_days() -> int:
    return int(get_policy().time.cooling_days)

def seller_decision_timeout_hours() -> int:
    return int(get_policy().time.seller_decision_timeout_hours)

def deal_deadline_hours() -> int:
    return int(get_policy().time.deal_deadline_hours)

def offer_deadline_hours() -> int:
    return int(get_policy().time.offer_deadline_hours)

def platform_fee_rate_fallback() -> float:
    """money.platform_fee_rate (rate 0~1) fallback"""
    v = float(get_policy().money.platform_fee_rate or 0.0)
    return _normalize_rate(v)

def actuator_commission_rate() -> float:
    """(레거시) money.actuator_commission_rate (rate 0~1)"""
    v = float(get_policy().money.actuator_commission_rate or 0.0)
    return _normalize_rate(v)

def pg_fee_rate() -> float:
    """money.pg_fee_rate (rate 0~1)"""
    v = float(get_policy().money.pg_fee_rate or 0.0)
    return _normalize_rate(v)

def vat_rate() -> float:
    """money.vat_rate (rate 0~1). 없으면 0"""
    v = getattr(get_policy().money, "vat_rate", None)
    if v is None:
        return 0.0
    return _normalize_rate(float(v))

def points_earn_rate() -> float:
    """points_tier.points_earn_rate (rate 0~1)"""
    v = float(get_policy().points_tier.points_earn_rate or 0.0)
    return _normalize_rate(v)


# =========================================================
# Helpers
# =========================================================

def _normalize_rate(v: float) -> float:
    """
    rate 천하통일:
    - 정상: 0.033, 0.1, 0.005
    - 방어: 3.3 / 10 / 0.5(%) 같은 값이 들어오면 /100
    """
    if v < 0:
        return 0.0
    if v > 1.0:
        v = v / 100.0
    if v < 0:
        v = 0.0
    if v > 1.0:
        v = 1.0
    return float(v)

def _normalize_level_key(level: Any) -> str:
    """
    6 / "6" / "Lv.6" / "LV6" / "lv_6" -> "Lv.6"
    """
    if level is None:
        return "Lv.6"
    s = str(level).strip()
    if s.lower().startswith("lv"):
        digits = "".join(ch for ch in s if ch.isdigit())
        return f"Lv.{digits or 6}"
    digits = "".join(ch for ch in s if ch.isdigit())
    return f"Lv.{digits or 6}"


# =========================================================
# v3.5+ Seller policy (YAML 1순위, rules_v3_5 폴백)
# =========================================================

def seller_level_for(trade_count: int, rating: Optional[float] = None) -> str:
    """
    판매자 레벨 키 계산.
    - YAML seller.levels 있으면 1순위
    - 없으면 rules_v3_5 폴백
    """
    p = get_policy()
    seller = getattr(p, "seller", None)

    if seller and getattr(seller, "levels", None):
        levels = list(seller.levels)
        for rule in levels:
            if trade_count < int(rule.min_trades):
                continue
            if rule.max_trades is not None and trade_count > int(rule.max_trades):
                continue

            if rule.min_rating is not None:
                if rating is None:
                    continue
                if float(rating) < float(rule.min_rating):
                    continue

            return str(rule.level).strip() or "Lv.6"

        # 매칭 실패 -> default_level or 첫 레벨
        return str(getattr(seller, "default_level", None) or levels[0].level).strip() or "Lv.6"

    # legacy fallback
    try:
        from app.config.rules_v3_5 import seller_level_for as _legacy
        lvl, _fee = _legacy(trade_count, rating or 0.0)
        return str(lvl).strip() or "Lv.6"
    except Exception:
        return "Lv.6"


def platform_fee_rate_for_level(level_str: Optional[str]) -> float:
    """
    ✅ Seller Level 기반 플랫폼 수수료율 (rate 0~1).
    우선순위:
      1) YAML seller.levels[].platform_fee_rate
      2) YAML money.platform_fee_rate (fallback)
      3) rules_v3_5.SELLER_PLATFORM_FEE_RATE_BY_LEVEL (fallback)
      4) 최후: 0.035
    """
    key = _normalize_level_key(level_str)

    # 1) YAML
    try:
        p = get_policy()
        seller = getattr(p, "seller", None)
        if seller and getattr(seller, "levels", None):
            for rule in seller.levels:
                if _normalize_level_key(rule.level) == key:
                    return _normalize_rate(float(rule.platform_fee_rate))
    except Exception:
        pass

    # 2) money fallback
    try:
        r = platform_fee_rate_fallback()
        if 0 < r <= 1.0:
            return r
    except Exception:
        pass

    # 3) rules_v3_5 fallback
    try:
        from app.config import rules_v3_5 as RV
        table = getattr(RV, "SELLER_PLATFORM_FEE_RATE_BY_LEVEL", None) or {}
        if isinstance(table, dict) and table:
            return _normalize_rate(float(table.get(key, table.get("Lv.6", 0.035))))
    except Exception:
        pass

    return 0.035


def actuator_fee_rate_for_level(level_str: Optional[str]) -> float:
    """
    ✅ Actuator fee rate (0~1).
    우선순위:
      1) YAML seller.actuator_fee_by_level_rate  (0.005 = 0.5%)
      2) rules_v3_5.ACTUATOR_FEE_BY_LEVEL (레거시 percent 가능성 높음: 0.5=0.5%)
      3) 최후: 0.0
    """
    key = _normalize_level_key(level_str)

    # 1) YAML SSOT (rate)
    try:
        p = get_policy()
        seller = getattr(p, "seller", None)
        m = getattr(seller, "actuator_fee_by_level_rate", None) if seller else None
        if isinstance(m, dict) and m:
            v = m.get(key)
            if v is not None:
                return _normalize_rate(float(v))
    except Exception:
        pass

    # 2) legacy fallback: rules_v3_5는 "0.5 = 0.5%" 패턴일 수 있음 -> rate로 보정
    try:
        from app.config.rules_v3_5 import ACTUATOR_FEE_BY_LEVEL
        v = float(ACTUATOR_FEE_BY_LEVEL.get(key, 0.0))
        # legacy는 percent(0.5)로 저장했을 확률이 높아서:
        # 0 < v <= 1.0 이면 "퍼센트값"으로 간주 -> /100
        if 0 < v <= 1.0:
            v = v / 100.0
        return _normalize_rate(v)
    except Exception:
        return 0.0


# =========================================================
# Cooling / payment window
# =========================================================

def is_payment_window_valid(reserved_at: datetime, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(tz=reserved_at.tzinfo)
    limit = timedelta(minutes=payment_timeout_minutes())
    return (now - reserved_at) <= limit

def compute_cooling_state(
    paid_at: datetime,
    shipped_at: Optional[datetime],
    delivered_at: Optional[datetime],
    now: Optional[datetime] = None,
    arrival_confirmed_at: Optional[datetime] = None,
    cooling_days_override: Optional[int] = None,
) -> CoolingState:
    # 기존 core 로직이 있으면 그대로 위임(있다면 그게 SSOT)
    try:
        return _core_compute_cooling_state(
            paid_at=paid_at,
            shipped_at=shipped_at,
            delivered_at=delivered_at,
            now=now,
            arrival_confirmed_at=arrival_confirmed_at,
            cooling_days_override=cooling_days_override,
        )
    except TypeError:
        # core 시그니처가 예전이면 여기서 fallback
        return _fallback_compute_cooling_state(
            paid_at=paid_at,
            shipped_at=shipped_at,
            delivered_at=delivered_at,
            now=now,
            arrival_confirmed_at=arrival_confirmed_at,
            cooling_days_override=cooling_days_override,
        )

def _fallback_compute_cooling_state(
    paid_at: datetime,
    shipped_at: Optional[datetime],
    delivered_at: Optional[datetime],
    now: Optional[datetime] = None,
    arrival_confirmed_at: Optional[datetime] = None,
    cooling_days_override: Optional[int] = None,
) -> CoolingState:
    if now is None:
        tzinfo = None
        for dt in (arrival_confirmed_at, delivered_at, paid_at):
            if dt is not None and getattr(dt, "tzinfo", None) is not None:
                tzinfo = dt.tzinfo
                break
        now = datetime.now(tz=tzinfo)

    if shipped_at is None:
        return "BEFORE_SHIPPING"

    candidates = [dt for dt in (arrival_confirmed_at, delivered_at) if dt is not None]
    if not candidates:
        return "SHIPPED_NOT_DELIVERED"

    delivered_base = min(candidates)
    days = int(cooling_days_override if cooling_days_override is not None else cooling_days())
    cooling_ends_at = delivered_base + timedelta(days=days)
    return "WITHIN_COOLING" if now <= cooling_ends_at else "AFTER_COOLING"


# =========================================================
# Points utils
# =========================================================

def calc_points_earnable(amount_paid: int) -> int:
    return int(round(int(amount_paid or 0) * points_earn_rate()))

def buyer_paid_reward_points() -> int:
    p = get_policy()
    pts = getattr(p, "points", None)
    if pts and getattr(pts, "buyer_paid_reward_pt", None) is not None:
        return int(pts.buyer_paid_reward_pt)
    return 0

def buyer_refund_penalty_points() -> int:
    p = get_policy()
    pts = getattr(p, "points", None)
    if pts and getattr(pts, "buyer_refund_penalty_pt", None) is not None:
        return int(pts.buyer_refund_penalty_pt)
    return 0

def recommender_reward_points() -> int:
    p = get_policy()
    pts = getattr(p, "points", None)
    if pts and getattr(pts, "recommender_reward_pt", None) is not None:
        return int(pts.recommender_reward_pt)
    return 0


# =========================================================
# Settlement snapshot (rate SSOT)
# =========================================================

def calc_pg_fee_amount(paid_amount: int) -> int:
    amt = int(paid_amount or 0)
    if amt <= 0:
        return 0
    r = pg_fee_rate()
    return max(0, int(round(amt * r)))

def calc_platform_fee_amount(paid_amount: int, level_str: Optional[str] = None) -> int:
    amt = int(paid_amount or 0)
    if amt <= 0:
        return 0
    r = platform_fee_rate_for_level(level_str)
    return max(0, int(round(amt * r)))

def calc_vat_amount(taxable_amount: int) -> int:
    base = int(taxable_amount or 0)
    if base <= 0:
        return 0
    r = vat_rate()
    return max(0, int(round(base * r)))

def calc_settlement_snapshot(paid_amount: int, level_str: Optional[str] = None) -> Dict[str, int]:
    paid = int(paid_amount or 0)
    if paid <= 0:
        return {
            "paid_amount": 0,
            "pg_fee_amount": 0,
            "platform_fee": 0,
            "platform_fee_vat": 0,
            "seller_payout": 0,
        }

    pg_fee = calc_pg_fee_amount(paid)
    platform_fee = calc_platform_fee_amount(paid, level_str=level_str)
    platform_fee_vat = calc_vat_amount(platform_fee)

    payout = paid - pg_fee - platform_fee - platform_fee_vat
    if payout < 0:
        payout = 0

    return {
        "paid_amount": int(paid),
        "pg_fee_amount": int(pg_fee),
        "platform_fee": int(platform_fee),
        "platform_fee_vat": int(platform_fee_vat),
        "seller_payout": int(payout),
    }


def settlement_payout_delay_days_default() -> int:
    p = get_policy()
    st = getattr(p, "settlement", None)
    if st and getattr(st, "payout_delay_days_default", None) is not None:
        return int(st.payout_delay_days_default)
    return 30

def settlement_payout_delay_days_dispute_path() -> int:
    p = get_policy()
    st = getattr(p, "settlement", None)
    if st and getattr(st, "payout_delay_days_dispute_path", None) is not None:
        return int(st.payout_delay_days_dispute_path)
    return 30


# =========================================================
# Actuator reward snapshot (rate SSOT)
# =========================================================

def calc_actuator_reward_amount(gmv: int, level_str: Optional[str] = None) -> int:
    g = int(gmv or 0)
    if g <= 0:
        return 0
    r = actuator_fee_rate_for_level(level_str)
    return max(0, int(round(g * r)))

def calc_actuator_reward_snapshot(gmv: int, level_str: Optional[str] = None) -> Dict[str, int | float]:
    g = int(gmv or 0)
    if g <= 0:
        return {"fee_rate": 0.0, "fee_percent": 0.0, "reward_amount": 0}

    fee_rate = actuator_fee_rate_for_level(level_str)
    fee_percent = fee_rate * 100.0
    reward_amount = max(0, int(round(g * fee_rate)))

    return {
        "fee_rate": float(fee_rate),
        "fee_percent": float(fee_percent),
        "reward_amount": int(reward_amount),
    }


# =========================================================
# Backward-compatible aliases (혹시 기존 호출이 남아있을까봐)
# =========================================================

def platform_commission_rate_for_level(level_str: Optional[str]) -> float:
    return platform_fee_rate_for_level(level_str)

def calc_platform_commission_amount(buyer_paid_amount: int, level_str: Optional[str] = None) -> int:
    return calc_platform_fee_amount(int(buyer_paid_amount or 0), level_str=level_str)