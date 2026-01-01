from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Path, Body, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, Float, String, Text, DateTime, Boolean
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import Base, engine, get_db
from app.config import rules_v3_5 as RV
from app.config import project_rules as R
from app.logic import trust as T



REVIEW_WINDOW_DAYS = getattr(R, "REVIEW_WINDOW_DAYS", 30)

# (예약/오퍼 검증용; 없으면 베이직 검증)
try:
    from app.models import Reservation, ReservationStatus, Offer
except Exception:
    Reservation = None  # type: ignore
    ReservationStatus = None  # type: ignore
    Offer = None  # type: ignore

router = APIRouter(prefix="/reviews", tags=["⭐ Reviews (NO-AUTH)"])

# ── Model ────────────────────────────────────────────────
class Review(Base):  # type: ignore
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, autoincrement=True)
    reservation_id = Column(Integer, nullable=False)
    seller_id = Column(Integer, nullable=False)
    buyer_id = Column(Integer, nullable=False)
    price_fairness = Column(Integer, nullable=False)
    quality = Column(Integer, nullable=False)
    shipping = Column(Integer, nullable=False)
    communication = Column(Integer, nullable=False)
    accuracy = Column(Integer, nullable=False)
    media_count = Column(Integer, default=0)
    comment = Column(Text, nullable=True)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

# ── Schemas ──────────────────────────────────────────────
class ReviewIn(BaseModel):
    reservation_id: int = Field(..., ge=1)
    seller_id: int = Field(..., ge=1)
    buyer_id: int = Field(..., ge=1)
    price_fairness: int = Field(..., ge=1, le=5)
    quality: int = Field(..., ge=1, le=5)
    shipping: int = Field(..., ge=1, le=5)
    communication: int = Field(..., ge=1, le=5)
    accuracy: int = Field(..., ge=1, le=5)
    media_count: int = Field(0, ge=0, le=20)
    comment: Optional[str] = None

class ReviewOut(BaseModel):
    id: int
    reservation_id: int
    seller_id: int
    buyer_id: int
    scores: dict
    media_count: int
    verified: bool
    comment: Optional[str]
    created_at: datetime

def _dim_avg(r: Review) -> float:
    return (r.price_fairness + r.quality + r.shipping + r.communication + r.accuracy) / 5.0

def _now() -> datetime:
    try:
        return R.now_utc()
    except Exception:
        return datetime.now(timezone.utc)


def _tier_weight(tier: str) -> float:
    try:
        weights = (getattr(RV, "REVIEW_POLICY", {}) or {}).get("weights", {}) or {}
        tw = weights.get("tier_weighting", {}) or {}
        key = {"T1": "TIER_1", "T2": "TIER_2", "T3": "TIER_3", "T4": "TIER_4", "T5": "TIER_5"}.get(tier, "TIER_4")
        return float(tw.get(key, 1.0))
    except Exception:
        return 1.0

def _media_bonus(mc: int) -> float:
    try:
        weights = (getattr(RV, "REVIEW_POLICY", {}) or {}).get("weights", {}) or {}
        step = float(weights.get("media_bonus_per_item", 0.05))
        cap  = float(weights.get("media_bonus_cap", 0.25))
        return min(cap, step * max(0, int(mc)))
    except Exception:
        return 0.0


def _ensure_aware(dt: datetime) -> datetime:
    """DB에서 naive로 올라올 수 있으니 UTC로 보정."""
    if dt is None:
        return _now()
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _time_weight(created_at: datetime) -> float:
    try:
        weights = (getattr(RV, "REVIEW_POLICY", {}) or {}).get("weights", {}) or {}
        half = float(weights.get("half_life_days", 365))
        c = _ensure_aware(created_at)
        age_days = max(0.0, (_now() - c).total_seconds() / 86400.0)
        return pow(0.5, age_days / half) if half > 0 else 1.0
    except Exception:
        return 1.0


def _to_out(r: Review) -> ReviewOut:
    return ReviewOut(
        id=r.id,
        reservation_id=r.reservation_id,
        seller_id=r.seller_id,
        buyer_id=r.buyer_id,
        scores={
            "price_fairness": r.price_fairness,
            "quality": r.quality,
            "shipping": r.shipping,
            "communication": r.communication,
            "accuracy": r.accuracy,
            "avg": round(_dim_avg(r), 3),
        },
        media_count=r.media_count,
        verified=bool(r.verified),
        comment=r.comment,
        created_at=r.created_at,
    )


@router.post("", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def create_review(body: ReviewIn = Body(...), db: Session = Depends(get_db)):
    """
    리뷰 생성 규칙 (v3.5):
    - 동일 reservation_id 로는 1회만 작성 가능
    - Reservation / Offer 모델이 있는 환경에서는:
        * Reservation 이 실제 존재해야 함
        * buyer_id / seller_id 가 예약 정보와 일치해야 함
        * 상태가 PAID 또는 (결제 후 셀러 철회로) CANCELLED 여야 함
        * shipped_at 이 있어야 함 (셀러가 발송표시 완료)
        * arrival_confirmed_at 이 있어야 함 (바이어 수령확인 완료)
        * arrival_confirmed_at 기준 REVIEW_WINDOW_DAYS 이내에만 작성 가능
    - 위 조건을 모두 만족하면 verified=True 로 저장
    - 모델이 없는 라이트/테스트 환경에서는 기존처럼 verified=False 로만 저장
    """
    # 0) 중복 방지: 동일 예약 1회
    exists = db.query(Review).filter(Review.reservation_id == body.reservation_id).first()
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="review already exists for this reservation",
        )

    verified = False

    # 1) Reservation / Offer / Status 모델이 있을 때만 강한 검증 수행
    if Reservation is not None and Offer is not None:
        res = db.query(Reservation).filter(Reservation.id == body.reservation_id).first()
        if not res:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reservation not found")

        # 1-1) buyer / seller 일치 여부
        if int(getattr(res, "buyer_id", 0)) != int(body.buyer_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="buyer_id does not match reservation",
            )

        off_id = getattr(res, "offer_id", None)
        off = db.query(Offer).filter(Offer.id == off_id).first() if off_id else None
        if not off or int(getattr(off, "seller_id", 0)) != int(body.seller_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="seller_id does not match reservation offer",
            )

        # 1-2) 상태 체크: PAID 또는 (결제 후 셀러 철회로) CANCELLED 만 허용
        status_val = getattr(res, "status", None)
        name = getattr(status_val, "name", None) or str(status_val)
        if name not in {"PAID", "CANCELLED"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"reservation not reviewable in status={name}",
            )

        # 1-3) 배송/도착 확인 순서 체크
        shipped_at = getattr(res, "shipped_at", None)
        if shipped_at is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cannot review before seller marked shipped",
            )

        arrival_at = getattr(res, "arrival_confirmed_at", None)
        if arrival_at is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cannot review before buyer arrival confirmation",
            )

        # 1-4) 도착 확인 후 REVIEW_WINDOW_DAYS 이내만 허용
        now = _now()
        arrival_at = _ensure_aware(arrival_at)
        delta_days = (now - arrival_at).total_seconds() / 86400.0
        if delta_days < 0:
            # 미래시간이면 이상 데이터지만, 일단 리뷰는 막기
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="invalid arrival_confirmed_at in future",
            )

        window_days = float(REVIEW_WINDOW_DAYS or 30)
        if delta_days > window_days:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"review window ({int(window_days)} days after arrival) has expired",
            )
        # 위 모든 조건 통과 → verified 리뷰
        verified = True

# 2) 리뷰 생성
    r = Review(
        reservation_id=body.reservation_id,
        seller_id=body.seller_id,
        buyer_id=body.buyer_id,
        price_fairness=body.price_fairness,
        quality=body.quality,
        shipping=body.shipping,
        communication=body.communication,
        accuracy=body.accuracy,
        media_count=body.media_count,
        comment=body.comment,
        verified=verified,
    )
    db.add(r)

    db.commit()
    db.refresh(r)

    # 🆕 3) 추천인 리워드 포인트 적립 시도 (에러 나도 리뷰 생성은 살려둔다)
    try:
        _maybe_reward_recommender_after_review(db, r)
    except Exception as e:
        print("[recommender_reward] ERROR:", repr(e))

    return _to_out(r)

############Seller 평점 집계 헬퍼 함수 추가 ########################
#------------------------------------------------------------------
def _compute_seller_aggregates(db: Session, seller_id: int):
    """
    Seller 하나에 대한:
    - rows           : Review 리스트
    - raw_avg        : 단순 평균
    - adjusted       : 가중+베이지안 보정 평점
    - last_30d_count : 최근 30일 리뷰 수
    """
    rows: List[Review] = (
        db.query(Review)
          .filter(Review.seller_id == seller_id)
          .order_by(Review.id.desc())
          .all()
    )
    if not rows:
        return {
            "rows": [],
            "raw_avg": 0.0,
            "adjusted": 0.0,
            "last_30d_count": 0,
        }

# 가중 평균 + 베이지안 보정 (REVIEW_POLICY 미설정 시 안전한 디폴트 사용)
    try:
        weights = (getattr(RV, "REVIEW_POLICY", {}) or {}).get("weights", {}) or {}
        prior_mean = float(weights.get("bayesian_prior_mean", 4.3))
        prior_weight = float(weights.get("bayesian_prior_weight", 5))
    except Exception:
        prior_mean = 4.3
        prior_weight = 5.0

    sum_w = 0.0
    sum_ws = 0.0
    raw_sum = 0.0

    for r in rows:
        raw = _dim_avg(r)
        raw_sum += raw
        try:
            info = T.buyer_trust_tier(db, r.buyer_id)
            tier = str(info.get("tier", "T4"))
        except Exception:
            tier = "T4"

        w = _tier_weight(tier) * (1.0 + _media_bonus(r.media_count)) * _time_weight(r.created_at or _now())
        sum_w += w
        sum_ws += w * raw

    raw_avg = raw_sum / len(rows)
    weighted = (sum_ws / sum_w) if sum_w > 0 else raw_avg
    obs_weight = sum_w if sum_w > 0 else float(len(rows))
    adjusted = (prior_mean * prior_weight + weighted * obs_weight) / (prior_weight + obs_weight)

    # 최근 30일 카운트
    now = _now()
    last_30 = [r for r in rows if (now - _ensure_aware(r.created_at)).days <= 30]

    return {
        "rows": rows,
        "raw_avg": raw_avg,
        "adjusted": adjusted,
        "last_30d_count": len(last_30),
    }



class ReviewSummaryOut(BaseModel):
    seller_id: int
    count: int
    raw_avg: float
    adjusted_rating: float
    last_30d_count: int


### Seller review summary###------------------------------------------------
@router.get("/seller/{seller_id}/summary", response_model=ReviewSummaryOut)
def seller_review_summary(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    # ✅ Verified 리뷰만 집계에 사용
    rows: List[Review] = (
        db.query(Review)
          .filter(
              Review.seller_id == seller_id,
              Review.verified == True  # noqa: E712
          )
          .order_by(Review.id.desc())
          .all()
    )

    if not rows:
        # Verified 리뷰가 하나도 없으면 평점 0 처리
        return ReviewSummaryOut(
            seller_id=seller_id,
            count=0,
            raw_avg=0.0,
            adjusted_rating=0.0,
            last_30d_count=0,
        )

    # 가중 평균 + 베이지안 보정
    try:
        weights = (getattr(RV, "REVIEW_POLICY", {}) or {}).get("weights", {}) or {}
        prior_mean = float(weights.get("bayesian_prior_mean", 4.3))
        prior_weight = float(weights.get("bayesian_prior_weight", 5))
    except Exception:
        prior_mean = 4.3
        prior_weight = 5.0

    sum_w = 0.0
    sum_ws = 0.0
    raw_sum = 0.0

    for r in rows:
        raw = _dim_avg(r)
        raw_sum += raw

        # 구매자 티어 가중
        try:
            info = T.buyer_trust_tier(db, r.buyer_id)
            tier = str(info.get("tier", "T4"))
        except Exception:
            tier = "T4"

        w = (
            _tier_weight(tier)
            * (1.0 + _media_bonus(r.media_count))
            * _time_weight(r.created_at or _now())
        )
        sum_w += w
        sum_ws += w * raw

    raw_avg = raw_sum / len(rows)
    weighted = (sum_ws / sum_w) if sum_w > 0 else raw_avg
    obs_weight = sum_w if sum_w > 0 else float(len(rows))
    adjusted = (prior_mean * prior_weight + weighted * obs_weight) / (prior_weight + obs_weight)

    # 최근 30일 Verified 리뷰 개수
    now = _now()
    last_30 = [
        r for r in rows
        if (now - _ensure_aware(r.created_at)).days <= 30
    ]

    return ReviewSummaryOut(
        seller_id=seller_id,
        count=len(rows),
        raw_avg=round(raw_avg, 3),
        adjusted_rating=round(adjusted, 3),
        last_30d_count=len(last_30),
    )

@router.get("/seller/{seller_id}", response_model=List[ReviewOut])
def list_seller_reviews(
    seller_id: int = Path(..., ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Review)
          .filter(Review.seller_id == seller_id)
          .order_by(Review.id.desc())
          .limit(limit)
          .all()
    )
    return [_to_out(r) for r in rows]



################ Seller 성공 거래수 + 레벨 매핑 헬퍼 ################
#-------------------------------------------------------------------------

def _get_seller_success_order_count(db: Session, seller_id: int) -> int:
    """
    Seller 누적 거래 수 계산.
    - Reservation.status 가 PAID 인 건만 카운트 (완료된 거래 기준)
    - Reservation / Offer 모델이 없으면 0 리턴
    """
    if not Reservation or not Offer:
        return 0

    q = (
        db.query(Reservation)
          .join(Offer, Reservation.offer_id == Offer.id)
          .filter(Offer.seller_id == seller_id)
    )

    # 상태 필터 (Enum/str 양쪽 대응)
    if hasattr(Reservation, "status"):
        if ReservationStatus is not None and hasattr(ReservationStatus, "PAID"):
            q = q.filter(Reservation.status == ReservationStatus.PAID)
        else:
            q = q.filter(Reservation.status.in_(("PAID", "paid")))
    return int(q.count())



def _select_seller_level_rule(order_count: int, rating: float) -> dict:
    """
    project_rules.SELLER_LEVEL_RULES 기반으로
    조건에 맞는 가장 높은 레벨 하나 선택.
    """
    rules = getattr(R, "SELLER_LEVEL_RULES", None)
    if not rules:
        # 안전한 기본값 (문서 기준)
        rules = [
            {"level": "Lv.1", "min_orders": 100, "min_rating": 4.5, "fee_percent": 2.0},
            {"level": "Lv.2", "min_orders": 100, "min_rating": 4.0, "fee_percent": 2.5},
            {"level": "Lv.3", "min_orders": 61,  "min_rating": 4.0, "fee_percent": 2.7},
            {"level": "Lv.4", "min_orders": 41,  "min_rating": 4.0, "fee_percent": 2.8},
            {"level": "Lv.5", "min_orders": 21,  "min_rating": 4.0, "fee_percent": 3.0},
            {"level": "Lv.6", "min_orders": 0,   "min_rating": 0.0, "fee_percent": 3.5},
        ]

    for rule in rules:
        if order_count >= int(rule.get("min_orders", 0)) and rating >= float(rule.get("min_rating", 0.0)):
            return rule

    return rules[-1]  # 아무 것도 안 맞으면 최하위 레벨


######Seller 레벨 조회용 스키마 + 앤드포인트 #################
############################################################

class SellerLevelOut(BaseModel):
    seller_id: int
    level: str
    fee_percent: float
    rating_adjusted: float
    rating_count: int
    total_orders: int


@router.get("/seller/{seller_id}/level", response_model=SellerLevelOut)
def seller_level_info(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    Seller 레벨/수수료/평점/거래수 조회용 앤드포인트.
    내부 로직은 compute_seller_level_infor핼퍼에 위임.
    """
    return compute_seller_level_info(db, seller_id)


def compute_seller_level_info(db: Session, seller_id: int) -> SellerLevelOut:
    """
    Seller 레벨/수수료/평점/거래수 계산 공용 헬퍼.
    - _compute_seller_aggregates: 평점 집계 (가중+베이지안)
    - _get_seller_success_order_count: 성공 거래 수
    - _select_seller_level_rule: project_rules.SELLER_LEVEL_RULES 적용
    """
    # 1) 평점 집계 (가중 + 베이지안 보정)
    agg = _compute_seller_aggregates(db, seller_id)
    rating = float(agg["adjusted"])
    rating_count = len(agg["rows"])

    # 2) 누적 성공 거래수 (PAID 예약 기준)
    total_orders = _get_seller_success_order_count(db, seller_id)

    # 3) 레벨 규칙에 매핑
    rule = _select_seller_level_rule(total_orders, rating)
    level = str(rule.get("level", "Lv.6"))
    fee = float(rule.get("fee_percent", 3.5))

    return SellerLevelOut(
        seller_id=seller_id,
        level=level,
        fee_percent=fee,
        rating_adjusted=round(rating, 3),
        rating_count=rating_count,
        total_orders=total_orders,
    )

@router.get(
    "/seller/{seller_id}/level",
    response_model=SellerLevelOut,
    summary="Seller 레벨 및 수수료 정보 조회",
)
def get_seller_level_api(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    ✅ Seller 레벨/수수료 API
    - compute_seller_level_info() 를 thin wrapper 로 감싼 것
    - 리뷰와 누적 주문 수를 기반으로 레벨/fee_percent 계산
    """
    return compute_seller_level_info(db, seller_id)


############ 추천인 포인트 적립 핼퍼 ################################
def _maybe_reward_recommender_after_review(db: Session, review: Review) -> None:
    """
    Recommender 리워드 정책(SSOT):
      - 추천받은 Buyer의 Reservation이 PAID
      - 해당 Offer가 Confirmed
      - Review 작성 완료(= 여기)
      - recommender_buyer_id + reservation_id 조합으로 1회만 지급(멱등)

    안전장치(테스트 나중에):
      - verified 조건은 플래그로 토글 가능 (R.RECOMMENDER_REQUIRE_VERIFIED_REVIEW, 기본 True)
      - ActivityLog.idempotency_key 선조회로 중복 지급 완화
      - 어떤 예외가 나도 리뷰 생성 흐름을 깨지 않게 무조건 return
    """
    try:
        # -------------------------------------------------
        # 0) verified 가드(정책 플래그로 토글)
        # -------------------------------------------------
        require_verified = bool(getattr(R, "RECOMMENDER_REQUIRE_VERIFIED_REVIEW", True))
        if require_verified and not bool(getattr(review, "verified", False)):
            return

        # -------------------------------------------------
        # 1) reservation id 확보
        # -------------------------------------------------
        reservation_id = int(getattr(review, "reservation_id", 0) or 0)
        if reservation_id <= 0:
            return

        # -------------------------------------------------
        # 2) 모델 로드 (프로젝트 경로 차이 방어)
        # -------------------------------------------------
        try:
            from app.models import Reservation, Offer, Buyer  # 프로젝트에 맞게 필요시 수정
        except Exception:
            return

        resv = db.get(Reservation, reservation_id)
        if not resv:
            return

        # -------------------------------------------------
        # 3) 예약 상태: PAID만 인정
        # -------------------------------------------------
        status_val = getattr(resv, "status", None)
        status_name = getattr(status_val, "name", None) or str(status_val)
        if status_name != "PAID":
            return

        # -------------------------------------------------
        # 4) buyer -> recommender 확인
        # -------------------------------------------------
        buyer_id = int(getattr(resv, "buyer_id", 0) or 0)
        if buyer_id <= 0:
            return

        buyer = db.get(Buyer, buyer_id)
        if not buyer:
            return

        recommender_id = getattr(buyer, "recommender_buyer_id", None)
        if recommender_id is None:
            return
        recommender_id = int(recommender_id or 0)
        if recommender_id <= 0:
            return

        # 자기 추천 금지
        if recommender_id == buyer_id:
            return

        recommender = db.get(Buyer, recommender_id)
        if not recommender:
            return

        # -------------------------------------------------
        # 5) offer confirmed 체크 (정책 SSOT)
        # -------------------------------------------------
        offer_id = getattr(resv, "offer_id", None)
        if not offer_id:
            return

        offer = db.get(Offer, int(offer_id))
        if not offer:
            return

        if not bool(getattr(offer, "is_confirmed", False)):
            return

        # -------------------------------------------------
        # 6) 지급 포인트 resolve
        #    - 정책값 우선, fallback 20
        # -------------------------------------------------
        try:
            from app.policy import api as policy_api
            reward_pt = int(getattr(policy_api, "recommender_reward_points", lambda: 20)())
        except Exception:
            reward_pt = int(getattr(R, "RECOMMENDER_REWARD_PT", 20) or 20)

        if reward_pt <= 0:
            return

        # -------------------------------------------------
        # 7) 멱등키(포인트/이벤트 공통)
        # -------------------------------------------------
        idempotency_key = f"pt:recommender:reward_v1:resv:{reservation_id}:rec:{recommender_id}"

        # -------------------------------------------------
        # 8) ✅ 중복 방지(완화): ActivityLog 선조회
        # -------------------------------------------------
        try:
            from app.routers.activity_log import ActivityLog
            exist = (
                db.query(ActivityLog)
                  .filter(ActivityLog.idempotency_key == idempotency_key)
                  .first()
            )
            if exist:
                return
        except Exception:
            # 조회 실패해도 흐름은 계속(최악: 중복 가능성만 남음)
            pass

        # -------------------------------------------------
        # 9) 포인트 지급 (crud._add_points 사용)
        # -------------------------------------------------
        try:
            from app import crud as crud_module
            crud_module._add_points(
                db,
                user_type="buyer",
                user_id=recommender_id,
                amount=reward_pt,
                reason=f"recommender reward for reservation {reservation_id} (buyer {buyer_id})",
                idempotency_key=idempotency_key,
            )
        except Exception:
            # 포인트 지급 실패는 리뷰 생성 흐름을 깨지 않도록
            return

        # -------------------------------------------------
        # 10) Evidence Pack (best-effort)
        # -------------------------------------------------
        try:
            from app.routers.activity_log import log_event as activity_log_event
            from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

            evidence_pack = build_evidence_pack_v0(
                db,
                kind="recommender_reward_v1",
                payload={
                    "reservation": resv,
                    "offer": offer,
                    "review": review,
                    "actor": "system_recommender_reward",
                    "recommender_buyer_id": recommender_id,
                    "reward_points": reward_pt,
                    "expected_source": "reviews.create_review",
                    "before": {},
                    "run_id": None,
                    "request_id": None,
                    "notes": [],
                },
            )

            activity_log_event(
                db,
                event_type="evidence_pack.recommender_reward_v1",
                actor_type="SYSTEM",
                actor_id=None,
                buyer_id=buyer_id,
                seller_id=getattr(offer, "seller_id", None),
                deal_id=getattr(offer, "deal_id", None),
                offer_id=getattr(offer, "id", None),
                reservation_id=getattr(resv, "id", None),
                meta=evidence_pack,
                # ✅ 포인트 멱등키와 동일하게 맞춰서 “로그가 중복을 막는 기준”이 되게 함
                idempotency_key=idempotency_key,
            )
        except Exception:
            pass

    except Exception:
        # 최상위 방어: 어떤 예외도 리뷰 생성 흐름을 깨면 안 됨
        return


class ReviewPatch(BaseModel):
    price_fairness: Optional[int] = Field(None, ge=1, le=5)
    quality: Optional[int] = Field(None, ge=1, le=5)
    shipping: Optional[int] = Field(None, ge=1, le=5)
    communication: Optional[int] = Field(None, ge=1, le=5)
    accuracy: Optional[int] = Field(None, ge=1, le=5)
    media_count: Optional[int] = Field(None, ge=0, le=20)
    comment: Optional[str] = None

@router.patch("/by-reservation/{reservation_id}", response_model=ReviewOut)
def patch_review_by_reservation(
    reservation_id: int = Path(..., ge=1),
    body: ReviewPatch = Body(...),
    db: Session = Depends(get_db),
):
    r = db.query(Review).filter(Review.reservation_id == reservation_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="review not found")

    for field in [
        "price_fairness",
        "quality",
        "shipping",
        "communication",
        "accuracy",
        "media_count",
        "comment",
    ]:
        v = getattr(body, field)
        if v is not None:
            setattr(r, field, v)

    db.commit()
    db.refresh(r)
    return _to_out(r)