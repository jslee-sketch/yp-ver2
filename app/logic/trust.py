# app/logic/trust.py
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Tuple, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Reservation, ReservationStatus, Offer
from app.config import project_rules as R


# ─────────────────────────────────────────────────────────
# 내부 유틸
# ─────────────────────────────────────────────────────────
def _safe_div(a: int, b: int) -> float:
    return (a / b) if b else 0.0


def _norm_tier_name(name: str) -> str:
    """
    다양한 표기를 T1~T5로 통일:
    "Tier1" / "TIER_1" / "TIER1" / "tier5" → "T1" / "T5"
    """
    s = (name or "").strip().upper()
    s = s.replace("_", "")
    if s.startswith("TIER"):
        s = "T" + s[4:]
    if not s.startswith("T"):
        return name  # 알 수 없는 경우 그대로
    return s


def _get(name: str, default: Any = None) -> Any:
    """project_rules(R)에서 안전하게 꺼내기"""
    return getattr(R, name, default)


# ─────────────────────────────────────────────────────────
# 규칙 소스 정규화 (R이 옛/새 포맷 어느 쪽이든 대응)
# ─────────────────────────────────────────────────────────
def _resolve_deposit_defaults() -> float:
    """
    기본 디파짓 비율:
    - 우선 R.DEPOSIT_DEFAULT_PERCENT
    - 다음 R.DEPOSIT_RULES['default_rate']
    - 없으면 0.10
    """
    val = _get("DEPOSIT_DEFAULT_PERCENT")
    if isinstance(val, (int, float)):
        return float(val)
    rules = _get("DEPOSIT_RULES", {})
    if isinstance(rules, dict):
        dr = rules.get("default_rate")
        if isinstance(dr, (int, float)):
            return float(dr)
    return 0.10


def _resolve_tier5_rule() -> Dict[str, Any]:
    """
    Tier5 제한 규칙을 R에서 찾아서 통일된 dict로 돌려줌.
    표준 키: min_participations, max_fulfillment_rate, percent, restricted, name
    """
    # 1) 구버전 호환
    t5 = _get("DEPOSIT_TIER_5_RULE")
    if isinstance(t5, dict) and "min_participations" in t5:
        return {
            "min_participations": int(t5.get("min_participations", 5)),
            "max_fulfillment_rate": float(t5.get("max_fulfillment_rate", 0.20)),
            "percent": float(t5.get("percent", _resolve_deposit_defaults())),
            "restricted": bool(t5.get("restricted", True)),
            "name": _norm_tier_name(str(t5.get("name", "T5"))),
        }

    # 2) 신버전 규칙에서 추출 (BUYER_TRUST_TIER_RULES.tiers)
    tiers = _get("BUYER_TRUST_TIER_RULES", {}).get("tiers", [])
    if isinstance(tiers, list):
        for t in tiers:
            nm = _norm_tier_name(str(t.get("name", "")))
            restricted = bool(t.get("restricted", False))
            # 이름이 T5이거나 restricted=True 인 항목을 Tier5로 간주
            if nm == "T5" or restricted:
                return {
                    "min_participations": int(t.get("min_participation", t.get("min_participations", 5))),
                    "max_fulfillment_rate": float(t.get("max_rate", 0.20)),
                    "percent": float(t.get("deposit_rate", _resolve_deposit_defaults())),
                    "restricted": True,
                    "name": "T5",
                }

    # 3) 안전망
    return {
        "min_participations": 5,
        "max_fulfillment_rate": 0.20,
        "percent": _resolve_deposit_defaults(),
        "restricted": True,
        "name": "T5",
    }


def _resolve_tier_table() -> List[Tuple[int, float, float, str]]:
    """
    Tier1~4 규칙을 [(min_participations, min_rate, percent, name), ...] 형태로 정규화.
    우선순위:
    - R.DEPOSIT_TIER_TABLE (구형)
    - R.BUYER_TRUST_TIER_RULES['tiers'] (신형)에서 T1~T4 변환
    - 기본표 (문서의 v3.5 표)
    """
    table = _get("DEPOSIT_TIER_TABLE")
    if isinstance(table, list) and table and isinstance(table[0], (list, tuple)):
        # 구버전 형태: [(10,0.95,0.00,"T1"), ...] 또는 이름 없이 3튜플일 수도 있음
        norm: List[Tuple[int, float, float, str]] = []
        for row in table:
            if len(row) == 4:
                min_part, min_rate, pct, name = row
                norm.append((int(min_part), float(min_rate), float(pct), _norm_tier_name(str(name))))
            elif len(row) == 3:
                min_part, min_rate, pct = row
                # name 추론
                name = "T1" if float(pct) == 0.0 else "T2" if float(pct) == 0.05 else "T3" if float(pct) == 0.08 else "T4"
                norm.append((int(min_part), float(min_rate), float(pct), name))
        # min_part desc, min_rate desc 로 정렬(상단 매칭 우선)
        return sorted(norm, key=lambda x: (x[0], x[1]), reverse=True)

    # 신버전
    rules = _get("BUYER_TRUST_TIER_RULES", {})
    tiers = rules.get("tiers", [])
    norm2: List[Tuple[int, float, float, str]] = []
    if isinstance(tiers, list) and tiers:
        for t in tiers:
            nm = _norm_tier_name(str(t.get("name", "")))
            if nm == "T5":
                continue  # T5는 별도 처리
            min_part = int(t.get("min_participation", t.get("min_participations", 0)))
            min_rate = float(t.get("min_rate", 0.0))
            pct = float(t.get("deposit_rate", _resolve_deposit_defaults()))
            norm2.append((min_part, min_rate, pct, nm or "T4"))
        if norm2:
            return sorted(norm2, key=lambda x: (x[0], x[1]), reverse=True)

    # 기본표
    return [
        (10, 0.95, 0.00, "T1"),
        (10, 0.86, 0.05, "T2"),
        (10, 0.61, 0.08, "T3"),
        (0,  0.00, 0.10, "T4"),
    ]


def _resolve_buyer_points_grades() -> List[Tuple[int, str]]:
    """
    points → 등급 맵:
    - 우선 R.BUYER_POINTS_GRADES ([(min, "GRADE"), ...])
    - 다음 R.BUYER_POINT_BADGES ({"GRADE": {"min":..}}) → 내림차순 변환
    - 없으면 기본표
    """
    lst = _get("BUYER_POINTS_GRADES")
    if isinstance(lst, list) and lst:
        # [(min, "GRADE"), ...] 형태 기대
        items: List[Tuple[int, str]] = []
        for row in lst:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                items.append((int(row[0]), str(row[1])))
        if items:
            return sorted(items, key=lambda x: x[0], reverse=True)

    badges = _get("BUYER_POINT_BADGES")
    if isinstance(badges, dict) and badges:
        tmp: List[Tuple[int, str]] = []
        for name, rng in badges.items():
            try:
                mn = int(rng.get("min", 0))
            except Exception:
                mn = 0
            tmp.append((mn, str(name)))
        if tmp:
            return sorted(tmp, key=lambda x: x[0], reverse=True)

    return [(500, "PLATINUM"), (201, "GOLD"), (51, "SILVER"), (0, "BRONZE")]


def _resolve_seller_levels() -> List[Tuple[int, float, float, str]]:
    """
    판매자 레벨 표:
    - 우선 R.SELLER_LEVELS 가 list[tuple] 이면 그대로 정규화
    - dict{"levels":[{...}]}면 (min_orders, min_rating, fee_rate, name) 튜플로 변환
    """
    lv = _get("SELLER_LEVELS")
    if isinstance(lv, list) and lv and isinstance(lv[0], (list, tuple)):
        out: List[Tuple[int, float, float, str]] = []
        for row in lv:
            if len(row) >= 4:
                out.append((int(row[0]), float(row[1]), float(row[2]), str(row[3])))
        return sorted(out, key=lambda x: (x[0], x[1]), reverse=True)

    if isinstance(lv, dict) and "levels" in lv:
        out = []
        for d in lv["levels"]:
            out.append((
                int(d.get("min_orders", 0)),
                float(d.get("min_rating", 0.0)) if d.get("min_rating") is not None else 0.0,
                float(d.get("fee_rate", 0.035)),
                str(d.get("name", "Lv.6")),
            ))
        return sorted(out, key=lambda x: (x[0], x[1]), reverse=True)

    # 기본표
    return [
        (100, 4.5, 0.020, "Lv.1"),
        (100, 4.0, 0.025, "Lv.2"),
        (61,  4.0, 0.027, "Lv.3"),
        (41,  4.0, 0.028, "Lv.4"),
        (21,  4.0, 0.030, "Lv.5"),
        (0,   0.0, 0.035, "Lv.6"),
    ]


def _resolve_premium_max_ratio() -> float:
    """
    노출 정책에서 프리미엄 허용 상한 비율:
    - 우선 R.OFFER_EXPOSURE / R.OFFER_EXPOSURE_RULE 의 "premium_max_ratio"
    - 다음 R.OFFER_RULES["max_above_buyer_price"] + 1.0
    - 없으면 1.10
    """
    exp = _get("OFFER_EXPOSURE") or _get("OFFER_EXPOSURE_RULE") or {}
    if isinstance(exp, dict) and "premium_max_ratio" in exp:
        try:
            return float(exp["premium_max_ratio"])
        except Exception:
            pass

    rules = _get("OFFER_RULES") or {}
    if isinstance(rules, dict) and "max_above_buyer_price" in rules:
        try:
            return 1.0 + float(rules["max_above_buyer_price"])
        except Exception:
            pass

    return 1.10


# ─────────────────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────────────────
def buyer_participation_stats(db: Session, buyer_id: int) -> dict:
    """
    참여/이행 집계:
      - total: 해당 buyer의 전체 참여(=Reservation 수)
      - paid:  결제 완료(PAID)
      - fulfillment_rate: paid / total
    [참고] '판매자 철회로 무산'을 이행으로 간주하려면 별도 reason/actor 컬럼이 필요.
    """
    q = db.query(Reservation).filter(Reservation.buyer_id == buyer_id)
    total = q.count()

    paid = (
        db.query(func.count(Reservation.id))
          .filter(Reservation.buyer_id == buyer_id, Reservation.status == ReservationStatus.PAID)
          .scalar()
        or 0
    )
    return {"total": total, "paid": int(paid), "fulfillment_rate": _safe_div(int(paid), int(total))}


def buyer_trust_tier_and_deposit_percent(db: Session, buyer_id: int) -> dict:
    """
    티어/디파짓 비율을 R의 포맷과 무관하게 계산해 반환.
    항상 {"tier": "T1~T5", "deposit_percent": float, "restricted": bool, ...} 형태.
    """
    st = buyer_participation_stats(db, buyer_id)
    total = st["total"]
    fr = st["fulfillment_rate"]

    # Tier5 우선 판정
    t5 = _resolve_tier5_rule()
    if total >= int(t5["min_participations"]) and fr <= float(t5["max_fulfillment_rate"]):
        return {
            "tier": "T5",
            "deposit_percent": float(t5["percent"]),
            "restricted": True,
            **st,
        }

    # Tier1~4 매칭: 상단(조건 가장 엄격)부터 탐색
    table = _resolve_tier_table()  # [(min_part, min_rate, pct, name), ...], desc 정렬됨
    for min_part, min_rate, pct, name in table:
        if total >= min_part and fr >= min_rate:
            return {
                "tier": _norm_tier_name(name),
                "deposit_percent": float(pct),
                "restricted": False,
                **st,
            }

    # Fallback (T4)
    return {
        "tier": "T4",
        "deposit_percent": _resolve_deposit_defaults(),
        "restricted": False,
        **st,
    }


def buyer_points_grade(points_balance: int) -> str:
    """
    포인트 등급: R가 어떤 포맷이든 동작하도록 정규화.
    """
    grades = _resolve_buyer_points_grades()  # [(min_pts, "GRADE"), ...] desc
    for min_pt, grade in grades:
        if points_balance >= min_pt:
            return grade
    return "BRONZE"


def seller_level_and_fee(db: Session, seller_id: int, rating_adjusted: float | None = None) -> dict:
    """
    판매자 레벨/수수료:
      - 판매량: 셀러의 Offer.sold_qty 합
      - 평점: 주어지지 않으면 4.0 가정(임시)
    """
    sold_count = (
        db.query(func.coalesce(func.sum(Offer.sold_qty), 0))
          .filter(Offer.seller_id == seller_id)
          .scalar()
        or 0
    )
    rating = float(rating_adjusted) if rating_adjusted is not None else 4.0

    levels = _resolve_seller_levels()  # [(min_cnt, min_rating, fee, level)], desc
    for min_cnt, min_rating, fee, level in levels:
        if int(sold_count) >= min_cnt and rating >= min_rating:
            return {
                "level": level,
                "fee_percent": float(fee),
                "sold_count": int(sold_count),
                "rating": float(rating),
            }

    # 안전망
    last = levels[-1]
    return {
        "level": last[3],
        "fee_percent": float(last[2]),
        "sold_count": int(sold_count),
        "rating": float(rating),
    }


def offer_price_exposure_category(wish_price: int | float, offer_price: int | float) -> dict:
    """
    노출/제출 규칙 분류:
      - ratio <= 1.0          → FRONT(전면)
      - ratio <= premium_max  → PREMIUM(제한)
      - else                  → BLOCK(제출 차단)
    premium_max은 규칙에서 자동 파생.
    """
    ratio = (offer_price / wish_price) if wish_price else 10.0
    premium_max = _resolve_premium_max_ratio()

    if ratio <= 1.0:
        category = "FRONT"
        allowed = True
    elif ratio <= premium_max:
        category = "PREMIUM"
        allowed = True
    else:
        category = "BLOCK"
        allowed = False

    return {"allowed": allowed, "category": category, "ratio": float(ratio), "premium_max": float(premium_max)}