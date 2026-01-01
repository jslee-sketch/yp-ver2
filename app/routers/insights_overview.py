# app/routers/insights_overview.py
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional, List, TYPE_CHECKING, Any, Dict

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import project_rules as R
from app.config import rules_v3_5 as RV
from app.logic import trust as T
import json

# ─────────────────────────────────────────────────────────
# Reviews 모델 로드 (없으면 요약은 빈값 처리)
# ─────────────────────────────────────────────────────────
try:
    from app.routers.reviews import Review  # runtime 모델
    HAS_REVIEW_MODEL = True
except Exception:
    Review = None  # type: ignore[assignment]
    HAS_REVIEW_MODEL = False

# ─────────────────────────────────────────────────────────
# Activity 모델 동적 로드 (여러 이름 지원: ActivityEvent / Activity / ActivityLog)
# ─────────────────────────────────────────────────────────
def _load_activity_model():
    try:
        from app.routers.activity_log import ActivityEvent as _M  # type: ignore
        return _M
    except Exception:
        pass
    try:
        from app.routers.activity_log import Activity as _M  # type: ignore
        return _M
    except Exception:
        pass
    try:
        from app.routers.activity_log import ActivityLog as _M  # type: ignore
        return _M
    except Exception:
        return None

_ActivityModel = _load_activity_model()

# 타입체커 전용 (런타임 의존성 제거)
if TYPE_CHECKING:
    from app.routers.reviews import Review as ReviewModel
else:
    ReviewModel = Any  # 힌트용

router = APIRouter(prefix="/insights", tags=["📊 Insights Overview (NO-AUTH)"])

def _now() -> datetime:
    try:
        return R.now_utc()
    except Exception:
        return datetime.now(timezone.utc)

# ─────────────────────────────────────────────────────────
# 공통 스키마
# ─────────────────────────────────────────────────────────
class BuyerStatsOut(BaseModel):
    total: int
    paid: int
    fulfillment_rate: float

class BuyerTrustOut(BaseModel):
    tier: str
    deposit_percent: float
    restricted: bool

class ActivityOut(BaseModel):
    id: Optional[int] = None
    event_type: Optional[str] = None
    actor_type: Optional[str] = None
    actor_id: Optional[int] = None
    buyer_id: Optional[int] = None
    seller_id: Optional[int] = None
    deal_id: Optional[int] = None
    offer_id: Optional[int] = None
    reservation_id: Optional[int] = None
    amount: Optional[float] = None
    qty: Optional[int] = None
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

class BasicInfoOut(BaseModel):
    # 모델이 없으면 None으로 내려갈 수 있음 (optional 사용)
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None

class BuyerOverviewOut(BaseModel):
    buyer_id: int
    stats: BuyerStatsOut
    trust: BuyerTrustOut
    points: Optional[int] = None
    grade: Optional[str] = None
    deposit_suggested: Optional[int] = None
    basic: Optional[BasicInfoOut] = None
    recent_activity: List[ActivityOut] = Field(default_factory=list)
    activity_count: int = 0

class SellerReviewSummaryOut(BaseModel):
    count: int = 0
    raw_avg: float = 0.0
    adjusted_rating: float = 0.0
    last_30d_count: int = 0

class SellerOverviewOut(BaseModel):
    seller_id: int
    level: str
    fee_percent: float
    sold_count: int
    rating: float
    review_summary: SellerReviewSummaryOut
    basic: Optional[BasicInfoOut] = None
    recent_activity: List[ActivityOut] = Field(default_factory=list)
    activity_count: int = 0

# ─────────────────────────────────────────────────────────
# 내부: 리뷰 요약(가중+베이지안) 계산
# ─────────────────────────────────────────────────────────
def _tier_weight(tier: str) -> float:
    w = RV.REVIEW_POLICY["weights"]["tier_weighting"]
    key = {"T1":"TIER_1","T2":"TIER_2","T3":"TIER_3","T4":"TIER_4","T5":"TIER_5"}.get(tier, "TIER_4")
    return float(w.get(key, 1.0))

def _media_bonus(mc: int) -> float:
    step = float(RV.REVIEW_POLICY["weights"]["media_bonus_per_item"])
    cap  = float(RV.REVIEW_POLICY["weights"]["media_bonus_cap"])
    return min(cap, step * max(0, int(mc)))

def _time_weight(created_at: datetime) -> float:
    half = float(RV.REVIEW_POLICY["weights"]["half_life_days"])
    when = created_at or _now()
    age_days = max(0.0, (_now() - when).total_seconds() / 86400.0)
    return pow(0.5, age_days / half) if half > 0 else 1.0

def _dim_avg(r: Any) -> float:
    return (r.price_fairness + r.quality + r.shipping + r.communication + r.accuracy) / 5.0

def _review_summary(db: Session, seller_id: int) -> SellerReviewSummaryOut:
    if not HAS_REVIEW_MODEL:
        return SellerReviewSummaryOut()

    rows: List[ReviewModel] = (
        db.query(Review)
          .filter(Review.seller_id == seller_id)
          .order_by(Review.id.desc())
          .all()
    )
    if not rows:
        return SellerReviewSummaryOut()

    prior_mean = float(RV.REVIEW_POLICY["weights"]["bayesian_prior_mean"])
    prior_weight = float(RV.REVIEW_POLICY["weights"]["bayesian_prior_weight"])

    sum_w = 0.0
    sum_ws = 0.0
    raw_sum = 0.0

    for r in rows:
        raw = _dim_avg(r)
        raw_sum += raw
        try:
            info = T.buyer_trust_tier_and_deposit_percent(db, r.buyer_id)
            tier = str(info.get("tier", "T4"))
        except Exception:
            tier = "T4"
        w = _tier_weight(tier) * (1.0 + _media_bonus(getattr(r, "media_count", 0))) * _time_weight(getattr(r, "created_at", _now()))
        sum_w += w
        sum_ws += w * raw

    raw_avg = raw_sum / len(rows)
    weighted = (sum_ws / sum_w) if sum_w > 0 else raw_avg
    effective_w = (sum_w if sum_w > 0 else 0.0)
    adjusted = (prior_mean * prior_weight + weighted * effective_w) / (prior_weight + effective_w if (prior_weight + effective_w) > 0 else 1.0)

    now = _now()
    last_30 = [r for r in rows if (now - (getattr(r, "created_at", now))).days <= 30]

    return SellerReviewSummaryOut(
        count=len(rows),
        raw_avg=round(raw_avg, 3),
        adjusted_rating=round(adjusted, 3),
        last_30d_count=len(last_30),
    )

# ─────────────────────────────────────────────────────────
# 내부: 기본정보 로더 (있으면 채워주고, 없으면 None)
# ─────────────────────────────────────────────────────────
def _get_basic_info_buyer(db: Session, buyer_id: int) -> Optional[BasicInfoOut]:
    # 존재할 만한 모델명을 순차 시도
    candidates = []
    try:
        import app.models as M  # type: ignore
        candidates = [getattr(M, n, None) for n in ("Buyer", "Buyers", "User", "Users")]
    except Exception:
        candidates = []
    for Model in candidates:
        if Model is None:
            continue
        try:
            row = db.query(Model).get(buyer_id)  # type: ignore
            if not row:
                continue
            return BasicInfoOut(
                name=getattr(row, "name", None) or getattr(row, "full_name", None) or getattr(row, "username", None),
                phone=getattr(row, "phone", None),
                email=getattr(row, "email", None),
                gender=getattr(row, "gender", None),
                address=getattr(row, "address", None),
            )
        except Exception:
            continue
    return None

def _get_basic_info_seller(db: Session, seller_id: int) -> Optional[BasicInfoOut]:
    candidates = []
    try:
        import app.models as M  # type: ignore
        candidates = [getattr(M, n, None) for n in ("Seller", "Sellers", "User", "Users")]
    except Exception:
        candidates = []
    for Model in candidates:
        if Model is None:
            continue
        try:
            row = db.query(Model).get(seller_id)  # type: ignore
            if not row:
                continue
            return BasicInfoOut(
                name=getattr(row, "name", None) or getattr(row, "company_name", None),
                phone=getattr(row, "phone", None),
                email=getattr(row, "email", None),
                gender=getattr(row, "gender", None),
                address=getattr(row, "address", None),
            )
        except Exception:
            continue
    return None

# ─────────────────────────────────────────────────────────
# 내부: 최근 활동 로그 조회 (+기간/개수 필터)
# ─────────────────────────────────────────────────────────
def _recent_activity_for(
    db: Session,
    *,
    buyer_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    limit: int = 10,
    days: Optional[int] = None,
) -> List[ActivityOut]:
    if _ActivityModel is None:
        return []
    try:
        q = db.query(_ActivityModel).order_by(_ActivityModel.id.desc())  # type: ignore[attr-defined]
        if buyer_id is not None:
            q = q.filter(getattr(_ActivityModel, "buyer_id") == buyer_id)
        if seller_id is not None:
            q = q.filter(getattr(_ActivityModel, "seller_id") == seller_id)
        if days and days > 0 and hasattr(_ActivityModel, "created_at"):
            cutoff = _now() - timedelta(days=int(days))
            q = q.filter(getattr(_ActivityModel, "created_at") >= cutoff)
        rows = q.limit(limit).all()
    except Exception:
        return []

    out: List[ActivityOut] = []
    for r in rows:
        # meta 안전 변환
        raw_meta = getattr(r, "meta", None)
        if isinstance(raw_meta, dict):
            meta_obj: Optional[Dict[str, Any]] = raw_meta
        elif isinstance(raw_meta, str):
            try:
                _obj = json.loads(raw_meta)
                meta_obj = _obj if isinstance(_obj, dict) else {"raw": _obj}
            except Exception:
                meta_obj = {"raw": raw_meta}
        else:
            meta_obj = None

        # 수치 타입 안전 변환
        try:
            amt = getattr(r, "amount", None)
            amount_val = float(amt) if amt is not None else None
        except Exception:
            amount_val = None

        try:
            qv = getattr(r, "qty", None)
            qty_val = int(qv) if qv is not None else None
        except Exception:
            qty_val = None

        out.append(ActivityOut(
            id=getattr(r, "id", None),
            event_type=getattr(r, "event_type", None),
            actor_type=getattr(r, "actor_type", None),
            actor_id=getattr(r, "actor_id", None),
            buyer_id=getattr(r, "buyer_id", None),
            seller_id=getattr(r, "seller_id", None),
            deal_id=getattr(r, "deal_id", None),
            offer_id=getattr(r, "offer_id", None),
            reservation_id=getattr(r, "reservation_id", None),
            amount=amount_val,
            qty=qty_val,
            reason=getattr(r, "reason", None),
            idempotency_key=getattr(r, "idempotency_key", None),
            meta=meta_obj,
            created_at=getattr(r, "created_at", None),
        ))
    return out

# ─────────────────────────────────────────────────────────
# Buyer Overview
# ─────────────────────────────────────────────────────────
@router.get("/buyer/{buyer_id}/overview", response_model=BuyerOverviewOut)
def buyer_overview(
    buyer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    points_override: Optional[int] = Query(None, description="포인트 미보유 테스트용"),
    preview_total_price: Optional[float] = Query(None, description="권장 디파짓 계산용 총액 미리보기"),
    include_activity: bool = Query(False, description="최근 활동 포함"),
    activity_days: Optional[int] = Query(None, ge=1, le=365, description="최근 N일만 포함"),
    activity_limit: int = Query(10, ge=1, le=100, description="최근 활동 최대 N건"),
):
    trust_info = T.buyer_trust_tier_and_deposit_percent(db, buyer_id)
    stats = BuyerStatsOut(**{k: trust_info[k] for k in ("total","paid","fulfillment_rate")})
    trust = BuyerTrustOut(
        tier=trust_info["tier"],
        deposit_percent=trust_info["deposit_percent"],
        restricted=bool(trust_info["restricted"])
    )

    pts = points_override
    grade = T.buyer_points_grade(pts or 0) if pts is not None else None

    suggested = None
    if preview_total_price is not None:
        suggested = T.suggested_deposit_amount(float(preview_total_price), {"deposit_percent": trust.deposit_percent})

    activities: List[ActivityOut] = []
    if include_activity:
        activities = _recent_activity_for(db, buyer_id=buyer_id, limit=activity_limit, days=activity_days)

    basic = _get_basic_info_buyer(db, buyer_id)

    return BuyerOverviewOut(
        buyer_id=buyer_id,
        stats=stats,
        trust=trust,
        points=pts,
        grade=grade,
        deposit_suggested=suggested,
        basic=basic,
        recent_activity=activities,
        activity_count=len(activities),
    )

# ─────────────────────────────────────────────────────────
# Seller Overview
# ─────────────────────────────────────────────────────────
@router.get("/seller/{seller_id}/overview", response_model=SellerOverviewOut)
def seller_overview(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    rating: Optional[float] = Query(None, description="임시/외부 보정평점(없으면 4.0 가정)"),
    include_activity: bool = Query(False, description="최근 활동 포함 여부"),
    activity_days: Optional[int] = Query(None, ge=1, le=365, description="최근 N일만 포함"),
    activity_limit: int = Query(10, ge=1, le=100, description="최근 활동 최대 N건"),
):
    lv = T.seller_level_and_fee(db, seller_id=seller_id, rating_adjusted=rating)

    # 리뷰 요약은 방어적으로
    try:
        summary = _review_summary(db, seller_id)
    except Exception:
        summary = SellerReviewSummaryOut()  # 빈 요약

    recent: List[ActivityOut] = []
    if include_activity:
        recent = _recent_activity_for(db, seller_id=seller_id, limit=activity_limit, days=activity_days)

    basic = _get_basic_info_seller(db, seller_id)

    return SellerOverviewOut(
        seller_id=seller_id,
        level=lv["level"],
        fee_percent=lv["fee_percent"],
        sold_count=lv["sold_count"],
        rating=lv["rating"],
        review_summary=summary,
        basic=basic,
        recent_activity=recent,
        activity_count=len(recent),
    )