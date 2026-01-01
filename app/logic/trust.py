# app/logic/trust.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Reservation, ReservationStatus, Offer
from app.config import project_rules as R

# 선택: CRUD 집계 함수가 있으면 활용(없어도 동작)
try:
    from app import crud  # type: ignore
except Exception:
    crud = None  # type: ignore


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
    """
    project_rules(R) 또는 중앙 규칙(R.RV)에서 안전하게 꺼내기.
    RV가 있으면 우선 사용(운영 규칙 테이블 즉시 반영).
    """
    rv = getattr(R, "RV", None)
    if rv is not None and hasattr(rv, name):
        try:
            return getattr(rv, name)
        except Exception:
            pass
    return getattr(R, name, default)


# ─────────────────────────────────────────────────────────
# Buyer Trust Tier 규칙(디포짓 제거 버전)
# ─────────────────────────────────────────────────────────
def _resolve_buyer_trust_tier_rules() -> Dict[str, Any]:
    """
    v3.5 정책 기준을 기본으로 사용.
    (향후 RV에 BUYER_TRUST_TIER_RULES가 있으면 거기서 읽되,
     deposit_rate 같은 값은 무시하고 tier 판정에 필요한 값만 사용)
    반환 형태(표준):
      {
        "tiers": [
          {"name":"T1","min_participations":10,"min_rate":0.95,"restricted":False},
          ...
          {"name":"T5","min_participations":5,"max_rate":0.20,"restricted":True},
        ]
      }
    """
    rules = _get("BUYER_TRUST_TIER_RULES", None)
    if isinstance(rules, dict) and isinstance(rules.get("tiers"), list) and rules["tiers"]:
        out: List[Dict[str, Any]] = []
        for t in rules["tiers"]:
            if not isinstance(t, dict):
                continue
            nm = _norm_tier_name(str(t.get("name", "")))
            if not nm:
                continue
            # 다양한 키 대응
            min_part = int(t.get("min_participation", t.get("min_participations", 0)) or 0)
            min_rate = t.get("min_rate", None)
            max_rate = t.get("max_rate", t.get("max_fulfillment_rate", None))
            restricted = bool(t.get("restricted", False)) or (nm == "T5")

            row = {
                "name": nm,
                "min_participations": min_part,
                "restricted": restricted,
            }
            if min_rate is not None:
                try:
                    row["min_rate"] = float(min_rate)
                except Exception:
                    pass
            if max_rate is not None:
                try:
                    row["max_rate"] = float(max_rate)
                except Exception:
                    pass
            out.append(row)

        if out:
            return {"tiers": out}

    # ✅ 기본(v3.5 문서)
    return {
        "tiers": [
            {"name": "T1", "min_participations": 10, "min_rate": 0.95, "restricted": False},
            {"name": "T2", "min_participations": 10, "min_rate": 0.86, "restricted": False},
            {"name": "T3", "min_participations": 10, "min_rate": 0.61, "restricted": False},
            {"name": "T4", "min_participations": 0,  "min_rate": 0.00, "restricted": False},
            {"name": "T5", "min_participations": 5,  "max_rate": 0.20, "restricted": True},
        ]
    }


# ─────────────────────────────────────────────────────────
# Buyer Points grade
# ─────────────────────────────────────────────────────────
def _resolve_buyer_points_grades() -> List[Tuple[int, str]]:
    """
    points → 등급 맵:
    - BUYER_POINTS_GRADES ([(min, "GRADE"), ...])
    - BUYER_POINT_BADGES ({"GRADE": {"min":..}}) → 내림차순 변환
    - 없으면 기본표
    """
    lst = _get("BUYER_POINTS_GRADES")
    if isinstance(lst, list) and lst:
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


# ─────────────────────────────────────────────────────────
# Seller levels
# ─────────────────────────────────────────────────────────
def _resolve_seller_levels() -> List[Tuple[int, float, float, str]]:
    """
    판매자 레벨 표 정규화:
    - SELLER_LEVELS 가 list[tuple] 이면 그대로 변환
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

    # 기본표(v3.5)
    return [
        (100, 4.5, 0.020, "Lv.1"),
        (100, 4.0, 0.025, "Lv.2"),
        (61,  4.0, 0.027, "Lv.3"),
        (41,  4.0, 0.028, "Lv.4"),
        (21,  4.0, 0.030, "Lv.5"),
        (0,   0.0, 0.035, "Lv.6"),
    ]


# ─────────────────────────────────────────────────────────
# Offer exposure helper
# ─────────────────────────────────────────────────────────
def _resolve_premium_max_ratio() -> float:
    """
    노출 정책에서 프리미엄 허용 상한 비율:
    - OFFER_EXPOSURE / OFFER_EXPOSURE_RULE 의 "premium_max_ratio"
    - OFFER_RULES["max_above_buyer_price"] + 1.0
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
      - fulfillment_rate: (paid + seller_withdrawn_count) / total
    '판매자 철회로 무산'을 이행으로 간주하려면 관련 컬럼이 있을 때만 가산.
    """
    q_total = db.query(Reservation).filter(Reservation.buyer_id == buyer_id)
    total = int(q_total.count())

    paid = int(
        db.query(func.count(Reservation.id))
          .filter(Reservation.buyer_id == buyer_id, Reservation.status == ReservationStatus.PAID)
          .scalar()
        or 0
    )

    seller_withdrawn = 0
    try:
        q_cancel = db.query(Reservation).filter(
            Reservation.buyer_id == buyer_id,
            Reservation.status == ReservationStatus.CANCELLED,
        )
        if hasattr(Reservation, "cancel_actor"):
            q_sw = q_cancel.filter(func.lower(Reservation.cancel_actor).in_(("seller", "system_auto_withdraw")))
            seller_withdrawn = int(q_sw.count())
        elif hasattr(Reservation, "cancel_reason"):
            q_sw = q_cancel.filter(func.lower(Reservation.cancel_reason).in_(("seller_withdraw", "auto_withdraw")))
            seller_withdrawn = int(q_sw.count())
    except Exception:
        seller_withdrawn = 0

    fulfills = paid + seller_withdrawn
    return {"total": total, "paid": paid, "fulfillment_rate": _safe_div(fulfills, total)}


def buyer_trust_tier_and_deposit_percent(db: Session, buyer_id: int) -> Dict[str, Any]:
    """
    ✅ 디포짓(예치금) 완전 제거 버전의 '레거시 호환 함수'

    - tier는 v3.5 기준으로 계산해서 내려준다(표시/분석/리뷰 가중 등에 사용 가능)
    - deposit_percent는 정책상 항상 0.0 (디포짓 기능 제거)
    """
    st = buyer_participation_stats(db, buyer_id)
    total = int(st.get("total") or 0)
    rate = float(st.get("fulfillment_rate") or 0.0)

    # v3.5 판정(기본)
    tier = "T4"
    restricted = False
    reason = "default"

    # Tier5(차단): 참여>=5 AND 이행률<=20%
    if total >= 5 and rate <= 0.20:
        tier = "T5"
        restricted = True
        reason = "low_fulfillment_rate"

    # Tier1~3: 참여>=10 조건 + 이행률 구간
    elif total >= 10 and rate >= 0.95:
        tier = "T1"; reason = "high_fulfillment_rate"
    elif total >= 10 and 0.86 <= rate < 0.95:
        tier = "T2"; reason = "good_fulfillment_rate"
    elif total >= 10 and 0.61 <= rate < 0.86:
        tier = "T3"; reason = "medium_fulfillment_rate"
    else:
        tier = "T4"; reason = "new_or_low_participation"

    # 만약 RV/규칙에 BUYER_TRUST_TIER_RULES가 있으면, 그 규칙으로 덮어쓸 여지도 열어둠
    # (단, deposit 관련 값은 절대 사용하지 않음)
    try:
        rules = _resolve_buyer_trust_tier_rules()
        tiers = rules.get("tiers", [])
        # 규칙이 유효하면 위 기본판정 대신 "가장 높은 티어 매칭" 방식으로 재판정 가능
        # (지금은 기본판정을 우선 유지. 필요하면 여기서 규칙 기반으로 바꿀 수 있음)
        _ = tiers  # no-op
    except Exception:
        pass

    return {
        "buyer_id": buyer_id,
        "tier": tier,
        "restricted": restricted,
        "total": total,
        "paid": int(st.get("paid") or 0),
        "fulfillment_rate": rate,
        "deposit_percent": 0.0,  # ✅ 항상 0
        "reason": reason,
    }


def buyer_points_grade(points_balance: int) -> str:
    """
    포인트 등급: R/RV가 어떤 포맷이든 동작하도록 정규화.
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
      - 평점: rating_adjusted가 주어지지 않으면 CRUD 집계 함수(있을 때) 시도 → 없으면 4.0 폴백
    """
    sold_count = int(
        db.query(func.coalesce(func.sum(Offer.sold_qty), 0))
          .filter(Offer.seller_id == seller_id)
          .scalar()
        or 0
    )

    rating = None
    if rating_adjusted is not None:
        try:
            rating = float(rating_adjusted)
        except Exception:
            rating = None

    if rating is None and crud:
        for name in ("get_seller_rating_adjusted", "seller_rating_adjusted", "get_seller_rating"):
            fn = getattr(crud, name, None)
            if callable(fn):
                try:
                    v = fn(db, seller_id=seller_id)
                except TypeError:
                    v = fn(db, seller_id)
                try:
                    rating = float(v) if v is not None else None
                    break
                except Exception:
                    pass

    if rating is None:
        rating = 4.0  # 안전 기본

    levels = _resolve_seller_levels()  # [(min_cnt, min_rating, fee, level)], desc
    for min_cnt, min_rating, fee, level in levels:
        if sold_count >= min_cnt and rating >= min_rating:
            return {
                "level": level,
                "fee_percent": float(fee),
                "sold_count": sold_count,
                "rating": float(rating),
            }

    # 안전망
    last = levels[-1]
    return {
        "level": last[3],
        "fee_percent": float(last[2]),
        "sold_count": sold_count,
        "rating": float(rating),
    }


def offer_price_exposure_category(wish_price: int | float, offer_price: int | float) -> dict:
    """
    노출/제출 규칙 분류:
      - ratio <= 1.0          → FRONT(전면)
      - ratio <= premium_max  → PREMIUM(제한)
      - else                  → BLOCK(제출 차단)
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


# ─────────────────────────────────────────────────────────
# 레거시 호환: 과거 코드가 호출하면 항상 0원(디포짓 기능 제거)
# ─────────────────────────────────────────────────────────
def suggested_deposit_amount(total_price: float, buyer_tier_info: Dict[str, Any]) -> int:
    """
    ⚠️ 디포짓 기능 제거로 인해 항상 0 반환.
    (호출부가 남아있어도 서버가 터지지 않게 하기 위한 레거시 스텁)
    """
    return 0