# app/crud.py
from __future__ import annotations

import hashlib
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import asdict, dataclass
from app.core.time_policy import TIME_POLICY, _utcnow, _as_utc
from app.core.shipping_policy import (
    calc_shipping_fee,
    calc_shipping_breakdown_from_total,
    calc_shipping_refund_for_partial_qty,
)
from app.routers.activity_log import log_event

from app.database import Session
from app.core.refund_policy import (
    REFUND_POLICY_ENGINE,
    RefundContext,
    RefundDecision,
    FaultParty,
    RefundTrigger,
    SettlementState,
    CoolingState,
    RefundFinancialPlan,
    compute_cooling_state,
)
from pydantic import BaseModel
from app.models import ReservationStatus, Offer, Reservation, Deal
from app.schemas import ReservationRefundSummary
from app.schemas_ai import BuyerIntentParsed, DealResolveIn
from app.config import rules_v3_5 as RV

from sqlalchemy import select, and_, func, case, text
from sqlalchemy.orm import Session, selectinload, Session
from sqlalchemy.exc import IntegrityError
from passlib.hash import bcrypt
from app.routers.notifications import create_notification

# 내부 모듈
from app import models, schemas                               
from app.config.feature_flags import FEATURE_FLAGS
from app.config import project_rules as R
from fastapi import HTTPException
import json
import logging
import re

from app.pg.types import PgRefundRequest, PgRefundResult, PgPayRequest, PgPayResult
from app.pg.client import request_pg_refund, request_pg_pay
from app.schemas_ai import DealResolveIn

from app.policy.api import payment_timeout_minutes
from app.policy import api as policy_api

# ---------------------------------
# 커스텀 예외 클래스 (crud 로컬 정의)
# ---------------------------------
class NotFoundError(Exception):
    """리소스를 찾지 못했을 때 사용하는 도메인 예외."""
    pass


class ConflictError(Exception):
    """상태/비즈니스 충돌(409)에 사용하는 도메인 예외."""
    pass


class BadRequestError(Exception):
    """잘못된 입력/요청(400)에 사용하는 도메인 예외."""
    pass


# 모델 단축 import
from app.models import (
    Deal,
    DealParticipant,
    DealRound,
    DealRoundStatus,
    Seller,
    Offer,
    Reservation,
    ReservationStatus,
    OfferDecisionState,
    ReservationSettlement,
    PointTransaction,
    DealChatMessage, 
    Buyer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------
class NotFoundError(Exception):
    pass

class ConflictError(Exception):
    pass

# ---------------------------------------------------------------------
# 공용 유틸
# ---------------------------------------------------------------------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def _require_deal(db: Session, deal_id: int) -> Deal:
    deal = db.get(Deal, deal_id)
    if not deal:
        raise NotFoundError(f"Deal not found: {deal_id}")
    return deal

# DeadTime-aware 윈도우 예시(안전 디폴트)
def compute_payment_windows(offer_deadline_at: datetime) -> tuple[datetime, datetime, datetime]:
    payment_open_at   = R.apply_deadtime_pause(offer_deadline_at, minutes=0)
    buyer_window_h    = float(R.TIMELINE.get("BUYER_PAYMENT_WINDOW", 0))  # 기본 0h
    seller_dec_min_h  = float(R.TIMELINE.get("SELLER_DECISION_WINDOW", 0.5))  # 기본 0.5h = 30m
    payment_close_at  = R.apply_deadtime_pause(payment_open_at, hours=buyer_window_h)
    decision_deadline = R.apply_deadtime_pause(payment_close_at, hours=seller_dec_min_h)
    return payment_open_at, payment_close_at, decision_deadline

# idempotent 포인트 적립/차감
def _add_points(
    db: Session,
    *,
    user_type: str,
    user_id: int,
    amount: int,
    reason: str,
    idempotency_key: str | None = None
) -> None:
    if idempotency_key:
        exists = db.query(PointTransaction.id).filter(PointTransaction.idempotency_key == idempotency_key).first()
        if exists:
            return
    tx = PointTransaction(
        user_type=user_type,
        user_id=user_id,
        amount=amount,
        reason=reason,
        created_at=_utcnow(),
        idempotency_key=idempotency_key,
    )
    db.add(tx)

# =========================================================
# 👥 Buyer
# =========================================================
def create_buyer(db: Session, buyer: schemas.BuyerCreate):
    # 추천인 체크
    rec = None
    if buyer.recommender_buyer_id:
        rec = db.query(models.Buyer).filter(models.Buyer.id == buyer.recommender_buyer_id).first()
        if not rec:
            raise HTTPException(status_code=400, detail="Invalid recommender_buyer_id")

    hashed_pw = bcrypt.hash(buyer.password[:72])
    db_buyer = models.Buyer(
        email=buyer.email,
        password_hash=hashed_pw,
        recommender_buyer_id=buyer.recommender_buyer_id,
        name=buyer.name,
        phone=buyer.phone,
        address=buyer.address,
        zip_code=buyer.zip_code,
        gender=buyer.gender,
        birth_date=buyer.birth_date,
        created_at=_utcnow(),
    )

    db.add(db_buyer)
    db.commit()
    db.refresh(db_buyer)
    
    # 추천인에게 포인트 지급 (즉시 지급, 멱등 처리)
    if buyer.recommender_buyer_id:
        rec = db.query(models.Buyer).filter(models.Buyer.id == buyer.recommender_buyer_id).first()
        if not rec:
            # create 시점에 추천인 유효성 체크를 이미 했더라도 안전하게 한 번 더 가드
            return db_buyer

        # ✅ 멱등키: "신규 buyer 1명당 추천 보상 1번"
        idem = f"evidence:buyer_referral_reward_v1:new_buyer:{int(getattr(db_buyer, 'id', 0) or 0)}"

        try:
            from app.routers.activity_log import ActivityLog
            exist = db.query(ActivityLog).filter(ActivityLog.idempotency_key == idem).first()
            if exist:
                return db_buyer
        except Exception:
            # activity_log가 깨져도 가입은 진행(운영 안전)
            pass

        before_points = int(getattr(rec, "points", 0) or 0)
        rec.points = before_points + 500
        db.add(rec)
        db.commit()

        # ✅ Evidence Pack 기록 (best-effort)
        try:
            from app.routers.activity_log import log_event as activity_log_event
            from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

            evidence_pack = build_evidence_pack_v0(
                db,
                kind="buyer_referral_reward_v1",
                payload={
                    "new_buyer": db_buyer,
                    "recommender_buyer": rec,
                    "actor": "system_referral_reward",
                    "points_awarded": 500,
                    "expected_source": "crud.create_buyer",
                    "before": {
                        "recommender_points_before": before_points,
                        "recommender_points_after": int(getattr(rec, "points", 0) or 0),
                    },
                    "run_id": None,
                    "request_id": None,
                    "notes": [],
                },
            )

            activity_log_event(
                db,
                event_type="evidence.buyer_referral_reward_v1",
                actor_type="SYSTEM",
                actor_id=None,
                buyer_id=int(getattr(rec, "id", 0) or 0),  # 수혜자(추천인)
                meta=evidence_pack,
                idempotency_key=idem,
            )
        except Exception:
            pass

    # ---------------------------------------------------------
    # ✅ Evidence Pack: buyer_register_v1
    #    위치: db.commit(); db.refresh(db_buyer) 직후
    # ---------------------------------------------------------
    try:
        from app.routers.activity_log import log_evidence_pack
        from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

        evidence = build_evidence_pack_v0(
            db,
            kind="buyer_register_v1",
            payload={
                "buyer": db_buyer,
                "actor": "buyer_register",
                "expected_source": "crud.create_buyer",
                "before": {},
                "run_id": None,
                "request_id": None,
                "notes": [],
            },
        )

        bid = int(getattr(db_buyer, "id", 0) or 0)
        log_evidence_pack(
            db,
            evidence_pack_version="buyer_register_v1",
            actor_type="SYSTEM",
            actor_id=None,
            buyer_id=getattr(db_buyer, "id", None),
            meta=evidence,
            idempotency_key=f"evidence:buyer_register_v1:{bid}",
        )
    except Exception:
        pass

    # 추천인에게 포인트 지급 (예: 500P)
    if rec is not None:
        try:
            rec.points += 500
            db.add(rec)
            db.commit()
        except Exception:
            db.rollback()
            raise

    return db_buyer

def get_buyers(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Buyer).offset(skip).limit(limit).all()


# =========================================================
# 🏢 Seller
# =========================================================
def create_seller(db: Session, seller: schemas.SellerCreate):
    # ---------------------------------------
    # (NEW) Actuator 매핑 검증
    # ---------------------------------------
    actuator_id = seller.actuator_id  # SellerCreate 스키마에 추가했다고 가정

    if actuator_id is not None:
        act = db.query(models.Actuator).get(actuator_id)
        if not act or act.status != "ACTIVE":
            raise HTTPException(status_code=400, detail="Invalid actuator_id")

    # ---------------------------------------
    # 기존 Seller 생성 로직 그대로
    # ---------------------------------------
    hashed_pw = bcrypt.hash(seller.password[:72])

    db_seller = models.Seller(
        email=seller.email,
        password_hash=seller.password and hashed_pw,
        business_name=seller.business_name,
        business_number=seller.business_number,
        phone=seller.phone,
        company_phone=seller.company_phone,
        address=seller.address,
        zip_code=seller.zip_code,
        established_date=seller.established_date,
        created_at=_utcnow(),

        # (NEW) Actuator 연결
        actuator_id=actuator_id,
    )

    db.add(db_seller)
    db.commit()
    db.refresh(db_seller)

    # ---------------------------------------------------------
    # ✅ Evidence Pack: seller_register_v1
    #    위치: db.commit(); db.refresh(db_seller) 직후
    # ---------------------------------------------------------
    try:
        from app.routers.activity_log import log_evidence_pack
        from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

        evidence = build_evidence_pack_v0(
            db,
            kind="seller_register_v1",
            payload={
                "seller": db_seller,
                "actor": "seller_register",
                "expected_source": "crud.create_seller",
                "before": {},
                "run_id": None,
                "request_id": None,
                "notes": [],
            },
        )

        sid = int(getattr(db_seller, "id", 0) or 0)
        log_evidence_pack(
            db,
            evidence_pack_version="seller_register_v1",
            actor_type="SYSTEM",
            actor_id=None,
            seller_id=getattr(db_seller, "id", None),
            meta=evidence,
            idempotency_key=f"evidence:seller_register_v1:{sid}",
        )
    except Exception:
        pass

    return db_seller

def get_sellers(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Seller).offset(skip).limit(limit).all()

# ---------------------------------------
# Actuator 수수료 적립 함수
# ---------------------------------------

def log_actuator_commission(
    db: Session,
    *,
    reservation: models.Reservation,
    seller: models.Seller,
    offer: models.Offer
):
    """
    Actuator 수수료 적립:
    - Actuator 없는 Seller는 0 처리
    - Seller의 레벨 기반 수수료율
    - reward 로그 쌓기
    """
    # Seller에 actuator 연결 안 되어있으면 스킵
    if not seller.actuator_id:
        return None

    # 현재 Seller level 가져오기
    lvl = seller.level   # 숫자 (1~6)
    lvl_key = f"Lv.{lvl}"

    pct = R.ACTUATOR_FEE_BY_LEVEL.get(lvl_key, 0.0)
    if pct <= 0:
        return None

    # GMV 계산: qty * price
    gmv = int(reservation.qty * offer.price)

    # ✅ Actuator reward 계산은 전부 policy/api.py “한 방 함수”로 이동
    seller = db.get(models.Seller, reservation.seller_id) if getattr(reservation, "seller_id", None) else None
    if seller is None:
        seller = db.get(models.Seller, offer.seller_id) if getattr(offer, "seller_id", None) else None

    level_int = int(getattr(seller, "level", 6) or 6) if seller else 6
    level_str = f"Lv.{level_int}"

    snap = policy_api.calc_actuator_reward_snapshot(gmv=gmv, level_str=level_str)

    fee_rate = float(snap["fee_rate"])
    fee_percent = float(snap["fee_percent"])
    reward_amount = int(snap["reward_amount"])

    # ✅ 저장 필드 호환: 모델이 fee_rate를 갖고 있으면 rate 저장, 아니면 fee_percent(%) 저장
    log_kwargs = dict(
        actuator_id=seller.actuator_id if seller else None,
        seller_id=seller.id if seller else None,
        reservation_id=reservation.id,
        gmv=gmv,
        reward_amount=reward_amount,
    )

    if hasattr(models.ActuatorRewardLog, "fee_rate"):
        log_kwargs["fee_rate"] = fee_rate
    else:
        log_kwargs["fee_percent"] = fee_percent

    log = models.ActuatorRewardLog(**log_kwargs)

    db.add(log)
    db.commit()
    db.refresh(log)
    return log


# 🆕 액츄에이터 커미션 ready_at 계산 헬퍼
def _compute_actuator_commission_ready_at_for_reservation(
    db: Session,
    resv: models.Reservation,
) -> Optional[datetime]:
    """
    액츄에이터 커미션 지급가능일 계산:

    기준일 = arrival_confirmed_at or delivered_at or paid_at
    ready_at = 기준일 + (쿨링일수) + (TIME_POLICY.actuator_payout_after_cooling_days)

    - 쿨링일수는 우선 셀러/오퍼 정책에서 가져오고,
      없으면 TIME_POLICY.cooling_days fallback.
    """
    if not resv:
        return None

    # 1) 기준일 계산
    base: Optional[datetime] = None
    if resv.arrival_confirmed_at:
        base = _as_utc(resv.arrival_confirmed_at)
    elif resv.delivered_at:
        base = _as_utc(resv.delivered_at)
    elif resv.paid_at:
        base = _as_utc(resv.paid_at)

    if base is None:
        return None

    # 2) 쿨링 일수 가져오기 (우선 오퍼 정책 쪽에서)
    cooling_days: Optional[int] = None

    # (1) Offer에 cooling_days 같은 필드가 있다면 우선 사용
    offer = db.get(models.Offer, resv.offer_id) if resv.offer_id else None
    if offer is not None:
        cooling_days = getattr(offer, "cooling_days", None)

    # (2) 정책 테이블이 있다면, 필요 시 여기에서 확장 가능
    # policy = get_offer_policy(...) 이런 식으로.

    if not cooling_days:
        cooling_days = TIME_POLICY.cooling_days

    total_days = cooling_days + TIME_POLICY.actuator_payout_after_cooling_days
    return base + timedelta(days=total_days)


#----------------------------------------------------
# Actuator 미지급 Commission 검색 및 일괄지급
#----------------------------------------------------
def settle_actuator_commissions_for_actuator(
    db: Session,
    actuator_id: int,
) -> Tuple[int, int, List[int]]:
    """
    특정 Actuator 에 대해, 아직 지급되지 않은(PENDING) 커미션을 한 번에 지급 처리.
    - status='PENDING' 인 row 들을 모두 'PAID' 로 변경
    - paid_at = now(UTC)
    - 반환값: (지급 건수, 총 지급액, 지급된 commission.id 리스트)
    """
    # 1) 아직 지급 안 된 커미션들 조회
    rows: List[models.ActuatorCommission] = (
        db.query(models.ActuatorCommission)
          .filter(
              models.ActuatorCommission.actuator_id == actuator_id,
              models.ActuatorCommission.status == "PENDING",
          )
          .all()
    )

    if not rows:
        return 0, 0, []

    now = datetime.now(timezone.utc)

    total_amount = 0
    paid_ids: List[int] = []

    for row in rows:
        total_amount += int(row.amount or 0)
        row.status = "PAID"
        row.paid_at = now
        db.add(row)
        paid_ids.append(row.id)

    db.commit()

    return len(rows), total_amount, paid_ids


#------------------------------------------------
# Actuator 정산일 세팅 헬퍼 (Cooling+30days)
#------------------------------------------------

def mark_actuator_commissions_ready_for_reservation(
    db: Session,
    reservation: models.Reservation,
):
    """
    예약 기준으로 관련 ActuatorCommission들의 ready_at 을 세팅.

    전제:
    - reservation.arrival_confirmed_at 또는 delivered_at 이 있어야 함
    - reservation.cooling_days (7/14/30 등) 가 세팅되어 있어야 함

    규칙:
    - ready_at = 도착 기준일 + cooling_days + 30일
    - status='PENDING' 이고 ready_at 이 아직 None 인 row 들만 업데이트
    """
    comms = (
        db.query(models.ActuatorCommission)
          .filter(models.ActuatorCommission.reservation_id == reservation.id)
          .all()
    )
    if not comms:
        return

    # 도착 기준일: 도착확정 > 배송완료
    base = getattr(reservation, "arrival_confirmed_at", None) or getattr(reservation, "delivered_at", None)
    if not base:
        return

    cooling_days = getattr(reservation, "cooling_days", None)
    if cooling_days is None:
        return

    ready_at = base + timedelta(days=int(cooling_days) + 30)

    changed = False
    for comm in comms:
        if comm.status == "PENDING" and comm.ready_at is None:
            comm.ready_at = ready_at
            changed = True

    if changed:
        db.commit()




# =========================================================
# 🏢 Seller Approval
# =========================================================

APPROVAL_WINDOW_HOURS = 12


def seller_approval_status(seller: models.Seller) -> str:
    """
    Seller의 승인 상태를 계산:
    - APPROVED: verified_at 이 설정된 경우
    - PENDING : 생성 후 APPROVAL_WINDOW_HOURS 이내 & 아직 verified_at 없음
    - REJECTED: 생성 후 APPROVAL_WINDOW_HOURS 초과 & 아직 verified_at 없음
    """
    # 1) 이미 승인된 경우
    if seller.verified_at is not None:
        return "APPROVED"

    # 2) created_at 이 없으면 안전하게 REJECT 처리
    created = seller.created_at
    if created is None:
        return "REJECTED"

    # 3) created_at 을 UTC aware 로 정규화
    if created.tzinfo is None:
        created_utc = created.replace(tzinfo=timezone.utc)
    else:
        created_utc = created.astimezone(timezone.utc)

    # 4) now 도 UTC aware 로
    now_utc = datetime.now(timezone.utc)

    deadline = created_utc + timedelta(hours=APPROVAL_WINDOW_HOURS)

    if now_utc <= deadline:
        return "PENDING"
    return "REJECTED"


def approve_seller(db: Session, seller_id: int) -> models.Seller:
    """
    운영자 수동 승인:
    - 12시간 이내(PENDING) → APPROVED 로 변경
    - 이미 APPROVED → 그대로 반환
    - 이미 REJECTED → 400 에러
    """
    seller = db.query(models.Seller).get(seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    status = seller_approval_status(seller)

    if status == "REJECTED":
        raise HTTPException(
            status_code=400,
            detail="Seller is automatically rejected after 12 hours and cannot be approved.",
        )

    if status == "APPROVED":
        return seller

    # 여기까지 왔으면 PENDING → APPROVED 로 변경
    # 🔹 상태 필드도 APPROVED 로 업데이트 (Enum/str 둘 다 대응)
    try:
        from app.models import SellerStatus  # Enum 이 있을 수 있음
    except Exception:
        SellerStatus = None  # type: ignore

    if hasattr(seller, "status"):
        if SellerStatus is not None and hasattr(SellerStatus, "APPROVED"):
            # SQLAlchemy Enum(SellerStatus) 인 경우
            seller.status = SellerStatus.APPROVED
        else:
            # 그냥 문자열 컬럼인 경우
            seller.status = "APPROVED"

    # approval_status 같은 보조 필드가 있다면 맞춰줌 (있을 때만)
    if hasattr(seller, "approval_status"):
        seller.approval_status = "APPROVED"

    seller.verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(seller)
    return seller    


# =========================================================
# 📦 Deal
# =========================================================
def create_deal(db: Session, deal: schemas.DealCreate):
    db_deal = models.Deal(
        product_name=deal.product_name,
        creator_id=deal.creator_id,
        desired_qty=deal.desired_qty,
        target_price=deal.target_price,
        max_budget=deal.max_budget,

        # 🔹 옵션 필드 매핑
        option1_title=deal.option1_title,
        option1_value=deal.option1_value,
        option2_title=deal.option2_title,
        option2_value=deal.option2_value,
        option3_title=deal.option3_title,
        option3_value=deal.option3_value,
        option4_title=deal.option4_title,
        option4_value=deal.option4_value,
        option5_title=deal.option5_title,
        option5_value=deal.option5_value,

        free_text=deal.free_text,
        created_at=_utcnow(),
    )

    # 🔹 DEADLINE 설정 부분을 '안전하게' 처리 (TIMELINE 없어도 안 터지게)
    deadline_hours = 0.0
    try:
        if FEATURE_FLAGS.get("AUTO_SET_DEADLINES", False):
            timeline = getattr(R, "TIMELINE", {}) or {}
            raw = timeline.get("DEAL_CREATION_WINDOW", 0)
            deadline_hours = float(raw or 0)
    except Exception:
        deadline_hours = 0.0  # 잘못된 설정은 그냥 무시

    if deadline_hours > 0:
        db_deal.deadline_at = R.apply_deadtime_pause(
            db_deal.created_at,
            hours=deadline_hours,
        )

    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)

    # 🔹 방장 자동 참여
    db_participant = models.DealParticipant(
        deal_id=db_deal.id,
        buyer_id=deal.creator_id,
        qty=deal.desired_qty,
        created_at=_utcnow(),
    )
    db.add(db_participant)
    db.commit()

    # ✅ 최신 상태로 한 번 더 refresh (참여/집계 필드가 있으면 반영)
    try:
        db.refresh(db_deal)
    except Exception:
        pass

    # ---------------------------------------------------------
    # ✅ Evidence Pack (deal_create_v1)
    #    위치: 방장 자동 참여 commit 이후, return 직전
    # ---------------------------------------------------------
    try:
        from app.routers.activity_log import log_event as activity_log_event
        from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

        # buyer_id 호환 (buyer_id 없고 creator_id만 있을 때 대비)
        buyer_id_for_log = getattr(db_deal, "buyer_id", None) or getattr(db_deal, "creator_id", None)

        evidence_pack = build_evidence_pack_v0(
            db,
            kind="deal_create_v1",
            payload={
                "deal": db_deal,
                "actor": "buyer_create_deal",
                "expected_source": "crud.create_deal",
                "before": {},
                "run_id": None,
                "request_id": None,
                "notes": [],
            },
        )

        did = int(getattr(db_deal, "id", 0) or 0)
        activity_log_event(
            db,
            event_type="evidence.deal_create_v1",
            actor_type="SYSTEM",
            actor_id=None,
            buyer_id=buyer_id_for_log,
            deal_id=getattr(db_deal, "id", None),
            meta=evidence_pack,
            idempotency_key=f"evidence:deal_create_v1:{did}",
        )
    except Exception:
        pass

    return db_deal



def get_deal(db: Session, deal_id: int):
    deal = db.query(models.Deal).filter(models.Deal.id == deal_id).first()
    if not deal:
        return None

    total_qty_from_participants = (
        db.query(func.coalesce(func.sum(models.DealParticipant.qty), 0))
          .filter(models.DealParticipant.deal_id == deal.id)
          .scalar()
    )
    total_qty = (deal.desired_qty or 0) + (total_qty_from_participants or 0)

    # 🔹 옵션/텍스트까지 같이 내려주기
    return schemas.DealDetail(
        id=deal.id,
        product_name=deal.product_name,
        creator_id=deal.creator_id,
        desired_qty=deal.desired_qty,
        target_price=getattr(deal, "target_price", None),
        max_budget=getattr(deal, "max_budget", None),
        created_at=deal.created_at,
        option1_title=getattr(deal, "option1_title", None),
        option1_value=getattr(deal, "option1_value", None),
        option2_title=getattr(deal, "option2_title", None),
        option2_value=getattr(deal, "option2_value", None),
        option3_title=getattr(deal, "option3_title", None),
        option3_value=getattr(deal, "option3_value", None),
        option4_title=getattr(deal, "option4_title", None),
        option4_value=getattr(deal, "option4_value", None),
        option5_title=getattr(deal, "option5_title", None),
        option5_value=getattr(deal, "option5_value", None),
        free_text=getattr(deal, "free_text", None),
        current_total_qty=total_qty or 0,
    )


def get_deals(db: Session, skip: int = 0, limit: int = 10):
    deals = db.query(models.Deal).offset(skip).limit(limit).all()
    result = []
    for d in deals:
        total_qty = (
            db.query(func.coalesce(func.sum(models.DealParticipant.qty), 0))
              .filter(models.DealParticipant.deal_id == d.id)
              .scalar()
        )
        result.append(
            schemas.DealDetail(
                id=d.id,
                product_name=d.product_name,
                creator_id=d.creator_id,
                desired_qty=d.desired_qty,
                target_price=getattr(d, "target_price", None),
                max_budget=getattr(d, "max_budget", None),
                created_at=d.created_at,
                option1_title=getattr(d, "option1_title", None),
                option1_value=getattr(d, "option1_value", None),
                option2_title=getattr(d, "option2_title", None),
                option2_value=getattr(d, "option2_value", None),
                option3_title=getattr(d, "option3_title", None),
                option3_value=getattr(d, "option3_value", None),
                option4_title=getattr(d, "option4_title", None),
                option4_value=getattr(d, "option4_value", None),
                option5_title=getattr(d, "option5_title", None),
                option5_value=getattr(d, "option5_value", None),
                free_text=getattr(d, "free_text", None),
                current_total_qty=total_qty or 0,
            )
        )
    return result

# =========================================================
# 🙋 Deal Participants
# =========================================================
def add_participant(db: Session, participant: schemas.DealParticipantCreate):
    existing = (
        db.query(models.DealParticipant)
          .filter_by(deal_id=participant.deal_id, buyer_id=participant.buyer_id)
          .first()
    )
    if existing:
        raise ConflictError("이미 참여한 Buyer입니다.")

    db_participant = models.DealParticipant(
        deal_id=participant.deal_id,
        buyer_id=participant.buyer_id,
        qty=participant.qty,
        created_at=_utcnow(),
    )
    db.add(db_participant)
    db.commit()
    db.refresh(db_participant)
    return db_participant

def get_deal_participants(db: Session, deal_id: int):
    return db.query(models.DealParticipant).filter(models.DealParticipant.deal_id == deal_id).all()

def remove_participant(db: Session, participant_id: int):
    db_participant = db.query(models.DealParticipant).filter(models.DealParticipant.id == participant_id).first()
    if not db_participant:
        return None
    buyer_id = db_participant.buyer_id
    db.delete(db_participant)
    db.commit()
    return {"message": "참여 취소 완료", "buyer_id": buyer_id}


#---------------------------------
# Deal AI Matching
#-----------------------------------

def find_matching_deals_for_intent(
    db: Session,
    intent: DealResolveIn,
    *,
    min_similarity_fuzzy: float = 0.6,
) -> List["Deal"]:
    """
    # 옵션이 너무 다른데도 묶이는 것을 조절하려면, min_similarity_fuzzy를 0.7~0.8로 올린다. 
    # 1에 가까울 수록 더 엄격, 0에 가까울 수록 더 느슨.
    
    DealResolveIn 을 기준으로 기존 deal 들 중 "같은 방"으로 봐도 되는 후보를 찾는다.

    1단계: fingerprint_hash 완전 동일 (상품명 + 옵션 완전 일치) → 바로 반환
    2단계: 같은 product_norm 안에서 옵션 유사도(Jaccard) >= min_similarity_fuzzy 인 것만 반환
    """
    # 1) 기준 fingerprint / product_norm / options_norm 계산
    product_norm, options_norm, fingerprint_hash = _build_deal_fingerprint_components(
        intent.product_name,
        intent.options,
    )

    # 2) 1단계: fingerprint_hash 완전 동일 + 상태가 open 계열인 deal
    strict_q = (
        db.query(Deal)
        .filter(
            Deal.fingerprint_hash == fingerprint_hash,
            Deal.status.in_(["open", "OPEN", "recruiting", "RECRUITING"]),
        )
        .order_by(Deal.id.asc())
    )
    strict_matches = strict_q.all()
    if strict_matches:
        # 예전 동작과 100% 동일한 케이스는 그대로
        return strict_matches

    # 3) 2단계: 같은 product_norm 안에서 옵션 유사도 기반 fuzzy 매칭
    fuzzy_q = (
        db.query(Deal)
        .filter(
            Deal.product_norm == product_norm,
            Deal.status.in_(["open", "OPEN", "recruiting", "RECRUITING"]),
        )
    )
    rows = fuzzy_q.all()

    scored: list[tuple[float, Deal]] = []
    for d in rows:
        sim = _calc_option_similarity(options_norm, getattr(d, "options_norm", "") or "")
        if sim >= min_similarity_fuzzy:
            scored.append((sim, d))

    # 유사도 높은 순으로 정렬
    scored.sort(key=lambda x: x[0], reverse=True)

    return [d for sim, d in scored]

# ==========================================================
# LLM Intent 기반 Deal 생성 & 매칭
# ==========================================================

def create_deal_from_intent(
    db: Session,
    intent: DealResolveIn,
) -> Deal:
    """
    LLM이 분석한 DealResolveIn 을 받아서 Deal 1건을 생성하는 헬퍼.

    - product_name, desired_qty, target_price, max_budget, options, free_text, buyer_id 사용
    - fingerprint_hash, product_norm, options_norm 도 여기서 계산
    """

    # 1) fingerprint용 정규화 문자열 생성
    product_norm, options_norm, fingerprint_hash = _build_deal_fingerprint_components(
        intent.product_name,
        intent.options,   # DealIntentOption 리스트
    )

    # 2) 옵션 1~5 맵핑 (배열 길이 체크하면서)
    def _opt(idx: int):
        if len(intent.options) > idx:
            opt = intent.options[idx]
            return opt.title, opt.value
        return None, None

    o1_title, o1_value = _opt(0)
    o2_title, o2_value = _opt(1)
    o3_title, o3_value = _opt(2)
    o4_title, o4_value = _opt(3)
    o5_title, o5_value = _opt(4)

    # 3) Deal 인스턴스 생성
    d = Deal(
        product_name=intent.product_name,
        creator_id=intent.buyer_id,

        desired_qty=intent.desired_qty,
        target_price=intent.target_price,
        max_budget=intent.max_budget,
        current_qty=0,
        current_avg_price=0,

        option1_title=o1_title,
        option1_value=o1_value,
        option2_title=o2_title,
        option2_value=o2_value,
        option3_title=o3_title,
        option3_value=o3_value,
        option4_title=o4_title,
        option4_value=o4_value,
        option5_title=o5_title,
        option5_value=o5_value,

        free_text=intent.free_text,

        # v3.5 상태/지문
        status="open",
        deadline_at=None,
        product_norm=product_norm,
        options_norm=options_norm,
        fingerprint_hash=fingerprint_hash,

        # ai_* 컬럼은 아직 LLM에서 따로 안 넘기니까 None으로 둬도 됨
        # ai_product_key=None,
        # ai_parsed_intent=None,
    )

    db.add(d)
    db.commit()
    db.refresh(d)
    return d


# ============================================
# v3.5: Deal fingerprint + LLM intent 기반 방 생성/매칭
# ============================================

def _normalize_text_basic(s: Optional[str]) -> str:
    """
    간단 정규화: lower + strip + 공백 정리.
    (나중에 한글 형태소, 자모 분해 등 더 넣고 싶으면 여기만 고치면 됨.)
    """
    if not s:
        return ""
    s = s.strip().lower()
    # 연속 공백 → 한 칸
    return " ".join(s.split())


def _build_deal_fingerprint_components(
    product_name: str,
    options: Optional[List[Any]] = None,  # 👈 그냥 Any 리스트로 처리
) -> tuple[str, str, str]:
    """
    - product_norm: 상품명 정규화 문자열
    - options_norm: 옵션(title=value) 묶어서 정규화한 문자열
    - fingerprint_hash: 위 둘을 합쳐서 만든 해시 (중복 방 판별용)
    """
    product_norm = _normalize_text_basic(product_name)

    options_norm_list: List[str] = []
    if options:
        for opt in options:
            # opt.title, opt.value 를 둘 다 정규화해서 "title=value" 형태로
            t = _normalize_text_basic(getattr(opt, "title", None))
            v = _normalize_text_basic(getattr(opt, "value", None))
            if t or v:
                options_norm_list.append(f"{t}={v}")

    options_norm = " | ".join(sorted(options_norm_list)) if options_norm_list else ""

    # fingerprint 문자열 구성
    fingerprint_source = f"{product_norm} || {options_norm}"
    fingerprint_hash = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()[:32]

    return product_norm, options_norm, fingerprint_hash


# 옵션 정규화 문자열(options_norm) 간 Jaccard 유사도
def _calc_option_similarity(options1: str | None, options2: str | None) -> float:
    """
    options_norm: "색상=화이트 | 용량=256GB" 이런 문자열을
    집합으로 바꿔서 Jaccard 유사도 계산.

    - 둘 다 비어 있으면 1.0 (완전 동일)
    - 한쪽만 있으면 0.0
    """
    def to_set(s: str | None) -> set[str]:
        if not s:
            return set()
        return {
            piece.strip()
            for piece in s.split("|")
            if piece.strip()
        }

    s1 = to_set(options1)
    s2 = to_set(options2)

    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    inter = s1 & s2
    union = s1 | s2
    return len(inter) / len(union)



def find_similar_deal_by_fingerprint(
    db: Session,
    *,
    fingerprint_hash: str,
) -> Optional[Deal]:
    """
    fingerprint_hash 기준으로 '열려 있는(open) 딜' 중 같은 지문을 가진 방을 하나 찾는다.
    - 지금은 단순히 status='open' + fingerprint_hash 가 같은 마지막 딜만 조회
    - 나중에 'created_at 최근 것만', 'creator_id 동일' 등 추가 룰을 붙일 수 있음.
    """
    q = (
        db.query(Deal)
        .filter(
            Deal.fingerprint_hash == fingerprint_hash,
            Deal.status == "open",
        )
        .order_by(Deal.id.desc())
    )
    return q.first()


def resolve_deal_intent(
    db: Session,
    *,
    buyer_id: int,
    intent: DealResolveIn,
) -> dict:
    """
    LLM → DealResolveIn 이 들어오면,
    1) fingerprint 를 만든 다음
    2) 같은 fingerprint 를 가진 open 상태의 기존 방이 있는지 찾고
    3) 있으면 그 방으로 '매칭'
    4) 없으면 새 Deal 을 만들고 그걸 리턴

    반환 형식은 schemas_ai.DealResolveOut 이 dict 를 받아서 파싱하는 걸 전제로 한다.
    """
    product_norm, options_norm, fingerprint_hash = _build_deal_fingerprint_components(
        intent.product_name,
        intent.options,
    )

    existing = find_similar_deal_by_fingerprint(
        db,
        fingerprint_hash=fingerprint_hash,
    )

    # 공통 summary 만드는 헬퍼
    def _to_summary(d: Deal) -> dict:
        return {
            "id": d.id,
            "product_name": d.product_name,
            "desired_qty": d.desired_qty,
            "status": d.status,
            "fingerprint_hash": d.fingerprint_hash,
        }

    if existing:
        # ✅ 기존 방으로 매칭
        return {
            "matched": True,
            "reason": "기존에 동일/유사한 조건의 방이 있어 그 방으로 연결합니다.",
            "existing_deal": _to_summary(existing),
            "created_deal": None,
        }

    # ✅ 새 방 생성
    new_deal = create_deal_from_intent(
        db,
        buyer_id=buyer_id,
        intent=intent,
    )

    return {
        "matched": False,
        "reason": "기존에 동일한 fingerprint의 방이 없어 새 방을 생성했습니다.",
        "existing_deal": None,
        "created_deal": _to_summary(new_deal),
    }



def upsert_offer_policy(db, offer_id: int, cancel_rule: str, cancel_within_days: int, extra_text: str = "") -> int:
    """
    offer_policies(offer_id UNIQUE)를 기준으로 UPSERT.
    반환: policy_id
    """
    sql = text("""
    INSERT INTO offer_policies (offer_id, cancel_rule, cancel_within_days, extra_text)
    VALUES (:offer_id, :cancel_rule, :cancel_within_days, :extra_text)
    ON CONFLICT(offer_id) DO UPDATE SET
      cancel_rule=excluded.cancel_rule,
      cancel_within_days=excluded.cancel_within_days,
      extra_text=excluded.extra_text
    """)
    db.execute(sql, {
        "offer_id": offer_id,
        "cancel_rule": cancel_rule,
        "cancel_within_days": cancel_within_days,
        "extra_text": extra_text,
    })
    db.flush()

    # policy_id 조회
    row = db.execute(
        text("SELECT id FROM offer_policies WHERE offer_id = :offer_id"),
        {"offer_id": offer_id},
    ).fetchone()
    return int(row[0])


# =========================================================
# 💰 Offers
# =========================================================
def create_offer(db: Session, offer: schemas.OfferCreate):
    db_deal = db.query(models.Deal).filter(models.Deal.id == offer.deal_id).first()
    if not db_deal:
        raise NotFoundError("Deal not found")

    # ---------------------------------------------------------
    # ✅ 배송비 정책 저장(부분환불 자동배정의 전제)
    # ---------------------------------------------------------
    raw_mode = getattr(offer, "shipping_mode", None)
    shipping_mode = (raw_mode or "INCLUDED").strip().upper()

    if shipping_mode in ("NONE", "UNKNOWN", "NULL", ""):
        shipping_mode = "INCLUDED"

    if shipping_mode not in ("INCLUDED", "PER_RESERVATION", "PER_QTY"):
        raise ValueError(f"Invalid shipping_mode: {shipping_mode}")

    shipping_fee_per_reservation = int(getattr(offer, "shipping_fee_per_reservation", 0) or 0)
    shipping_fee_per_qty = int(getattr(offer, "shipping_fee_per_qty", 0) or 0)

    if shipping_fee_per_reservation < 0 or shipping_fee_per_qty < 0:
        raise ValueError("shipping fee cannot be negative")

    if shipping_mode == "INCLUDED":
        shipping_fee_per_reservation = 0
        shipping_fee_per_qty = 0
    elif shipping_mode == "PER_RESERVATION":
        shipping_fee_per_qty = 0
    elif shipping_mode == "PER_QTY":
        shipping_fee_per_reservation = 0

    # ---------------------------------------------------------
    # Offer 생성
    # ---------------------------------------------------------
    db_offer = models.Offer(
        deal_id=offer.deal_id,
        seller_id=offer.seller_id,
        price=offer.price,
        total_available_qty=offer.total_available_qty,
        delivery_days=getattr(offer, "delivery_days", None),
        comment=getattr(offer, "comment", None) or getattr(offer, "free_text", None),

        shipping_mode=shipping_mode,
        shipping_fee_per_reservation=shipping_fee_per_reservation,
        shipping_fee_per_qty=shipping_fee_per_qty,

        created_at=_utcnow(),
    )

    if FEATURE_FLAGS.get("AUTO_SET_DEADLINES"):
        timeline = getattr(R, "TIMELINE", {}) or {}
        try:
            hours = float(timeline.get("OFFER_EDITABLE_WINDOW", 0) or 0)
        except Exception:
            hours = 0.0
        db_offer.deadline_at = R.apply_deadtime_pause(db_offer.created_at, hours=hours)

    db.add(db_offer)

    # ✅ 운영 안정성: 커밋 실패시 rollback
    try:
        # ---------------------------------------------------------------------
        # ✅ [추가] offer.id를 먼저 확보
        # ---------------------------------------------------------------------
        db.flush()  # 여기서 db_offer.id 생성됨

        # ---------------------------------------------------------------------
        # ✅ [추가] 옵션 B: OfferPolicy(offer_policies) 자동 생성/업서트 (ORM 버전)
        # ---------------------------------------------------------------------
        cancel_rule = getattr(offer, "cancel_rule", None) or "COOLING"
        cancel_rule = str(cancel_rule).strip().upper()

        cancel_within_days = getattr(offer, "cancel_within_days", None)
        if cancel_within_days is None:
            # schemas에 필드가 아직 없을 수 있으니, 레거시 키도 한번 더 봄
            cancel_within_days = getattr(offer, "cooling_days", None)

        if cancel_within_days is not None:
            cancel_within_days = int(cancel_within_days)

        extra_text = getattr(offer, "policy_extra_text", None) or getattr(offer, "extra_text", None)

        # 기본값 seed (원하면 여기만 바꾸면 됨)
        if cancel_rule == "COOLING" and cancel_within_days is None:
            cancel_within_days = 7

        # 가드레일(음수 금지, 상한은 운영상 365 정도)
        if cancel_within_days is not None:
            if cancel_within_days < 0 or cancel_within_days > 365:
                raise ValueError(f"cancel_within_days must be 0~365, got={cancel_within_days}")

        existing = (
            db.query(models.OfferPolicy)
            .filter(models.OfferPolicy.offer_id == db_offer.id)
            .first()
        )

        if existing:
            existing.cancel_rule = cancel_rule
            existing.cancel_within_days = cancel_within_days
            if extra_text is not None:
                existing.extra_text = extra_text
        else:
            db.add(
                models.OfferPolicy(
                    offer_id=db_offer.id,
                    cancel_rule=cancel_rule,
                    cancel_within_days=cancel_within_days,
                    extra_text=extra_text,
                )
            )

        # ✅ 마지막에 커밋(Offer + OfferPolicy 같이)
        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(db_offer)
    
    # ---------------------------------------------------------
    # ✅ Evidence Pack (offer_create_v1)
    #    위치: db.refresh(db_offer) 직후, return 직전
    # ---------------------------------------------------------
    try:
        from app.routers.activity_log import log_event as activity_log_event
        from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

        evidence_pack = build_evidence_pack_v0(
            db,
            kind="offer_create_v1",
            payload={
                "offer": db_offer,
                "actor": "seller_create_offer",
                "expected_source": "crud.create_offer",
                "before": {},
                "run_id": None,
                "request_id": None,
                "notes": [],
            },
        )

        oid = int(getattr(db_offer, "id", 0) or 0)
        activity_log_event(
            db,
            event_type="evidence.offer_create_v1",
            actor_type="SYSTEM",
            actor_id=None,
            seller_id=getattr(db_offer, "seller_id", None),
            deal_id=getattr(db_offer, "deal_id", None),
            offer_id=getattr(db_offer, "id", None),
            meta=evidence_pack,
            idempotency_key=f"evidence:offer_create_v1:{oid}",
        )
    except Exception:
        pass    
    
    return db_offer


# =========================================================
# 💰 Offers (compat)
# =========================================================
def get_offers(db: Session, skip: int = 0, limit: int = 50):
    """
    ✅ 하위호환용: 일부 라우터에서 `from app.crud import get_offers` 를 사용한다.
    """
    if skip < 0:
        skip = 0
    if limit <= 0:
        limit = 50
    return db.query(models.Offer).offset(skip).limit(limit).all()



# =========================================================
# 💎 Points
# =========================================================
def create_point_transaction(db: Session, transaction: schemas.PointTransactionCreate):
    db_tx = PointTransaction(
        user_type=transaction.user_type,
        user_id=transaction.user_id,
        amount=transaction.amount,
        reason=transaction.reason,
        created_at=_utcnow(),
    )
    db.add(db_tx)
    db.commit()
    db.refresh(db_tx)
    return db_tx

def get_point_transactions(db: Session, user_type: str, user_id: int):
    return (
        db.query(PointTransaction)
          .filter(PointTransaction.user_type == user_type,
                  PointTransaction.user_id == user_id)
          .order_by(PointTransaction.created_at.desc())
          .all()
    )

def get_user_balance(db: Session, user_type: str, user_id: int):
    total = (
        db.query(func.coalesce(func.sum(PointTransaction.amount), 0))
          .filter(PointTransaction.user_type == user_type,
                  PointTransaction.user_id == user_id)
          .scalar()
    )
    return total or 0

def reward_buyer_payment(db: Session, buyer_id: int):
    return create_point_transaction(
        db,
        schemas.PointTransactionCreate(
            user_type="buyer", user_id=buyer_id, amount=R.BUYER_POINT_ON_PAID, reason="결제 완료 보상"
        ),
    )

def penalize_buyer_cancel(db: Session, buyer_id: int):
    return create_point_transaction(
        db,
        schemas.PointTransactionCreate(
            user_type="buyer", user_id=buyer_id, amount=R.BUYER_POINT_ON_REFUND, reason="결제 취소 차감"
        ),
    )

def reward_seller_success(db: Session, seller_id: int):
    return create_point_transaction(
        db,
        schemas.PointTransactionCreate(
            user_type="seller", user_id=seller_id, amount=30, reason="거래 성사 보상"
        ),
    )

def penalize_seller_cancel_offer(db: Session, seller_id: int):
    return create_point_transaction(
        db,
        schemas.PointTransactionCreate(
            user_type="seller", user_id=seller_id, amount=-30, reason="오퍼 취소 차감"
        ),
    )

# =========================================================
# 🔁 DealRound
# =========================================================
def get_round_by_no(db: Session, deal_id: int, round_no: int) -> DealRound:
    q = (
        select(DealRound)
        .options(selectinload(DealRound.deal))
        .where(and_(DealRound.deal_id == deal_id, DealRound.round_no == round_no))
    )
    row = db.execute(q).scalar_one_or_none()
    if not row:
        raise NotFoundError(f"DealRound not found: deal_id={deal_id}, round_no={round_no}")
    return row

def list_rounds(db: Session, deal_id: int) -> List[DealRound]:
    q = select(DealRound).where(DealRound.deal_id == deal_id).order_by(DealRound.round_no.asc())
    return list(db.execute(q).scalars())

def get_active_round(db: Session, deal_id: int) -> Optional[DealRound]:
    q = select(DealRound).where(and_(DealRound.deal_id == deal_id, DealRound.status == DealRoundStatus.OPEN)).limit(1)
    return db.execute(q).scalar_one_or_none()

def create_deal_round(db: Session, deal_id: int, round_no: int, meta: Optional[dict] = None) -> DealRound:
    _require_deal(db, deal_id)
    obj = DealRound(deal_id=deal_id, round_no=round_no, status=DealRoundStatus.PLANNED, meta=meta or {})
    db.add(obj)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError(f"Round already exists: deal_id={deal_id}, round_no={round_no}") from e
    db.refresh(obj)
    return obj

def get_or_create_next_round(db: Session, deal_id: int, meta: Optional[dict] = None) -> DealRound:
    next_no = (db.execute(select(func.coalesce(func.max(DealRound.round_no), 0)).where(DealRound.deal_id == deal_id)).scalar_one() or 0) + 1
    return create_deal_round(db, deal_id, next_no, meta=meta)

def open_round(db: Session, deal_id: int, round_no: Optional[int] = None) -> DealRound:
    existing = get_active_round(db, deal_id)
    if existing:
        raise ConflictError(f"Another round already OPEN: round_no={existing.round_no}")

    if round_no is None:
        r = get_or_create_next_round(db, deal_id)
    else:
        try:
            r = get_round_by_no(db, deal_id, round_no)
        except NotFoundError:
            r = create_deal_round(db, deal_id, round_no)

        if r.status != DealRoundStatus.PLANNED:
            raise ConflictError(f"Only PLANNED round can be opened (current={r.status}). Create a new round instead.")

    r.status = DealRoundStatus.OPEN
    r.started_at = _utcnow()
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def finalize_round(db: Session, deal_id: int, round_no: Optional[int] = None) -> DealRound:
    r = get_round_by_no(db, deal_id, round_no) if round_no is not None else get_active_round(db, deal_id)
    if not r:
        raise NotFoundError("No OPEN round to finalize" if round_no is None else f"Round not found: {round_no}")
    if r.status != DealRoundStatus.OPEN:
        raise ConflictError(f"Round must be OPEN to finalize. current={r.status}")

    r.status = DealRoundStatus.FINALIZING
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def _get_latest_finalizing_round(db: Session, deal_id: int) -> Optional[DealRound]:
    q = (
        select(DealRound)
        .where(and_(DealRound.deal_id == deal_id, DealRound.status == DealRoundStatus.FINALIZING))
        .order_by(DealRound.round_no.desc())
        .limit(1)
    )
    return db.execute(q).scalar_one_or_none()

def close_round(db: Session, deal_id: int, round_no: Optional[int] = None) -> DealRound:
    r = get_round_by_no(db, deal_id, round_no) if round_no is not None else (get_active_round(db, deal_id) or _get_latest_finalizing_round(db, deal_id))
    if not r:
        raise NotFoundError("No OPEN or FINALIZING round to close")
    if r.status not in (DealRoundStatus.OPEN, DealRoundStatus.FINALIZING):
        raise ConflictError(f"Round must be OPEN or FINALIZING to close. current={r.status}")

    r.status = DealRoundStatus.CLOSED
    r.ended_at = _utcnow()
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

def cancel_round(db: Session, deal_id: int, round_no: int) -> DealRound:
    r = get_round_by_no(db, deal_id, round_no)
    if r.status == DealRoundStatus.CLOSED:
        raise ConflictError("Closed round cannot be cancelled")

    r.status = DealRoundStatus.CANCELLED
    r.ended_at = _utcnow()
    db.add(r)
    db.commit()
    db.refresh(r)
    return r

class RoundAction(str):
    OPEN = "OPEN"
    FINALIZE = "FINALIZE"
    CLOSE = "CLOSE"
    CANCEL = "CANCEL"


def progress_round(db: Session, deal_id: int, action: str, round_no: Optional[int] = None) -> DealRound:
    action = action.upper()
    if action == RoundAction.OPEN:
        return open_round(db, deal_id, round_no=round_no)
    if action == RoundAction.FINALIZE:
        return finalize_round(db, deal_id, round_no=round_no)
    if action == RoundAction.CLOSE:
        return close_round(db, deal_id, round_no=round_no)
    if action == RoundAction.CANCEL:
        if round_no is None:
            raise ConflictError("cancel requires explicit round_no")
        return cancel_round(db, deal_id, round_no)
    raise ConflictError(f"Unknown action: {action}")

def assert_no_open_round(db: Session, deal_id: int) -> None:
    if get_active_round(db, deal_id):
        raise ConflictError("OPEN round already exists")

def ensure_round_exists(db: Session, deal_id: int, round_no: int) -> DealRound:
    try:
        return get_round_by_no(db, deal_id, round_no)
    except NotFoundError:
        return create_deal_round(db, deal_id, round_no)



# -------------------------------------------------------
# Deal 채팅
#--------------------------------------------------------- 
import re

# -----------------------------
#  욕설 / 개인정보 필터 설정
# -----------------------------

# 욕설 “뿌리” 단어들 (공백/기호 제거 후 포함 여부로 체크)
_BAD_WORD_STEMS = {
    # 씨발/시발 계열
    "씨발", "시발", "씨바", "시바", "씨빨", "씨뻘", "십알",
    "ㅅㅂ", "ㅆㅂ",

    # 좆/존나 계열
    "좆같", "좇같", "존나", "졸라", "존맛", "존싫",

    # 병신 계열
    "병신", "븅신", "병1신", "ㅄ",

    # 개새/썅/쌍년 계열
    "개새끼", "개색기", "개세끼", "개쉐", "개같은",
    "썅년", "쌍년", "걸레년",

    # 그 외 자주 나오는 것들
    "미친놈", "미친년", "미친새끼",
    "죽여버", "좆까", "꺼져", "닥쳐",
}

# 은행/계좌 관련 키워드 (이 단어 + 숫자 많이 → 계좌로 간주)
_BANK_KEYWORDS = {
    "계좌", "계좌번호", "통장",
    "국민은행", "기업은행", "신한은행", "우리은행",
    "농협", "농협은행", "하나은행", "카카오뱅크", "카뱅",
}

# 공백/기호 제거용
_NORMALIZE_SEP_RE = re.compile(r"[\s\-\_/.,~!@#$%^&*()\[\]{}<>|\\]+")

# 010-1234-5678 / 010 1234 5678 / +82 10 ... 등
_PHONE_PATTERNS = [
    re.compile(r"01[016789][\s\-]?\d{3,4}[\s\-]?\d{4}"),         # 010-XXXX-XXXX
    re.compile(r"\+82\s?1[016789][\s\-]?\d{3,4}[\s\-]?\d{4}"),   # +82 10-XXXX-XXXX
]

# 계좌 패턴: 2~4 - 2~4 - 2~6, 또는 10자리 이상 숫자
_ACCOUNT_PATTERN = re.compile(r"\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{2,6}")
_LONG_DIGITS_RE = re.compile(r"\d{10,}")  # 10자리 이상 숫자열 (계좌/전화 의심)


def _normalize_for_moderation(text: str) -> str:
    """공백/기호 제거 + 소문자화해서 욕설/패턴 탐지용으로 사용"""
    t = text.lower()
    t = _NORMALIZE_SEP_RE.sub("", t)
    return t


def _run_chat_guard(text: str) -> tuple[bool, Optional[str]]:
    """
    채팅 텍스트에 대한 1차 가드:

    - 길이 제한 (1000자 초과)
    - 전화번호(휴대폰 위주)
    - 계좌/은행 정보 (숫자 패턴 + 은행 키워드)
    - 다양한 욕설(띄어쓰기/기호 섞여도 잡도록 노멀라이즈 후 검사)

    차단되면 (True, REASON), 통과면 (False, None) 반환.
    """
    raw = (text or "").strip()
    if not raw:
        return True, "EMPTY"

    if len(raw) > 1000:
        return True, "TOO_LONG"

    norm = _normalize_for_moderation(raw)

    # 1) 휴대폰 번호 패턴
    for p in _PHONE_PATTERNS:
        if p.search(raw) or p.search(norm):
            return True, "PHONE_DETECTED"

    # 2) 계좌/은행 정보 ---------------------------------
    # (1) 123-45-67890 같은 형태: 하이픈/공백 섞인 전형적인 계좌 패턴
    if _ACCOUNT_PATTERN.search(raw) or _ACCOUNT_PATTERN.search(norm):
        return True, "ACCOUNT_DETECTED"

    # (2) 은행/계좌 키워드 + 긴 숫자(10자리 이상)가 같이 있을 때만 계좌로 판단
    has_bank_kw = any(kw in raw for kw in _BANK_KEYWORDS)
    if has_bank_kw and _LONG_DIGITS_RE.search(raw):
        return True, "ACCOUNT_DETECTED"
    # --------------------------------------------------

    # 3) 욕설: 공백/기호 제거한 문자열(norm)에 욕설 “뿌리”가 들어있는지 체크
    for stem in _BAD_WORD_STEMS:
        if stem in norm:
            return True, "PROFANITY"

    # 여기까지 통과하면 허용
    return False, None


class ForbiddenError(Exception):
    """권한 없을 때 쓰는 공통 에러 (이미 있으면 그거 써도 됨)"""
    pass


def _ensure_deal_participant(db: Session, *, deal_id: int, buyer_id: int) -> None:
    """
    해당 buyer 가 deal 의 참여자인지 검증.
    참여자가 아니면 ForbiddenError 발생.
    """
    row = (
        db.query(DealParticipant)
        .filter(
            DealParticipant.deal_id == deal_id,
            DealParticipant.buyer_id == buyer_id,
        )
        .first()
    )
    if not row:
        raise ForbiddenError("not a participant of this deal")



PHONE_PATTERN = re.compile(r"\d{2,3}-?\d{3,4}-?\d{4}")  # 아주 러프한 휴대폰 패턴
ACCOUNT_PATTERN = re.compile(r"\d{10,}")  # 10자리 이상 숫자 연속 (계좌/주민번호류 대충 막기)

#------------------------------------------------------
def get_buyer_nickname(db: Session, buyer_id: int) -> str:
    buyer = db.get(models.Buyer, buyer_id)
    if not buyer:
        return f"buyer-{buyer_id}"
    return _make_buyer_display_name(buyer)


#---------------------------------------------------------------
def _make_buyer_display_name(buyer: models.Buyer) -> str:
    """
    채팅에 노출할 buyer 이름 생성.

    - 실명(name)은 절대 사용하지 않는다.
    - nickname / handle 처럼 익명성 있는 필드가 있으면 그걸 우선 사용
    - 없으면 'buyer-{id}' 형태의 기본 핸들 부여
    """
    # 1) 닉네임 필드가 있다면 최우선 사용
    nick = getattr(buyer, "nickname", None)
    if nick:
        return nick

    # 2) 별도 핸들/유저네임 필드가 있다면 사용 (없으면 그냥 넘어감)
    handle = getattr(buyer, "handle", None)
    if handle:
        return handle

    # 3) 최종 fallback: id 기반 가명
    return f"buyer-{buyer.id}"

#----------------------------------------------------
def _sanitize_and_validate_chat_text(raw: str) -> str:
    """
    - 양쪽 공백 제거
    - 길이 0이면 에러
    - 1000자 초과면 에러 (스키마에도 max_length=1000 있음)
    - 휴대폰/계좌번호로 보이는 패턴은 허용하지 않음
    (이건 V1 최소 방어선, 나중에 더 강하게 교체 가능)
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("empty message")

    if len(text) > 1000:
        raise ValueError("message too long (max 1000 chars)")

    if PHONE_PATTERN.search(text):
        raise ValueError("phone numbers are not allowed in chat")

    if ACCOUNT_PATTERN.search(text):
        raise ValueError("looks like an account or personal id number; not allowed")

    # 욕설 필터는 나중에 리스트 만들어서 추가 가능
    return text

#---------------------------------------
def create_deal_chat_message(
    db: Session,
    *,
    deal_id: int,
    buyer_id: int,
    text: str,
) -> DealChatMessage:
    # 1) 딜 존재 확인
    deal = db.get(Deal, deal_id)
    if not deal:
        raise NotFoundError("Deal not found")

    # 2) 참여자 확인 (deal_participants 테이블 기준)
    is_participant = (
        db.query(DealParticipant)
        .filter(
            DealParticipant.deal_id == deal_id,
            DealParticipant.buyer_id == buyer_id,
        )
        .first()
    )
    if not is_participant:
        raise ConflictError("not a deal participant")

    # 3) 딜 상태에 따른 채팅 write 권한 체크
    can_read, can_write, status_code = _get_deal_chat_access(deal)
    if not can_write:
        # 메시지 내용은 저장도 안 하고 바로 에러
        raise ConflictError(
            f"chat is read-only or closed for this deal (status={status_code})"
        )

    # 4) 차단 검사 (욕설/개인정보 등)
    blocked, reason = _run_chat_guard(text)

    # 5) 저장
    msg = DealChatMessage(
        deal_id=deal_id,
        buyer_id=buyer_id,
        text=(text or "").strip(),
        blocked=blocked,
        blocked_reason=reason,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


#------------------------------------
def list_deal_chat_messages(
    db: Session,
    *,
    deal_id: int,
    buyer_id: int,
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = None,
) -> Tuple[List[DealChatMessage], int]:
    # 0) 딜 존재 확인
    deal = db.get(Deal, deal_id)
    if not deal:
        raise NotFoundError("Deal not found")

    # 1) 읽기 권한: 참여자만 (운영 정책상 완전 오픈이면 이 체크 제거)
    is_participant = (
        db.query(DealParticipant)
        .filter(
            DealParticipant.deal_id == deal_id,
            DealParticipant.buyer_id == buyer_id,
        )
        .first()
    )
    if not is_participant:
        raise ConflictError("not a deal participant")

    # 2) 딜 상태에 따른 read 권한 체크
    can_read, _can_write, status_code = _get_deal_chat_access(deal)
    if not can_read:
        # 딜 종료/취소 등으로 채팅 열람 자체가 막힌 상태
        raise ConflictError(
            f"chat is closed for this deal (status={status_code})"
        )

    # 3) 실제 조회
    base = db.query(DealChatMessage).filter(DealChatMessage.deal_id == deal_id)
    if q:
        base = base.filter(DealChatMessage.text.ilike(f"%{q}%"))

    total = base.with_entities(func.count(DealChatMessage.id)).scalar() or 0

    items = (
        base.order_by(DealChatMessage.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total



# ============================
#  💬 Deal Chat 접근 정책 헬퍼
# ============================

def _get_deal_chat_access(deal) -> tuple[bool, bool, str]:
    """
    deal.status 기준으로 채팅 read/write 허용 여부를 판단한다.

    return: (can_read, can_write, status_code_string)

    - 모집 중: 읽기/쓰기 허용
    - 모집 마감 후 ~ 딜 마무리 전: 읽기만 허용
    - 딜 종료/취소 후: 읽기/쓰기 모두 불가

    ⚠️ status 값은 프로젝트마다 다르므로,
       실제 사용하는 Deal.status 값에 맞게 아래 집합들을 조정하면 된다.
    """
    status = getattr(deal, "status", None)

    # status 가 없으면 일단 읽기/쓰기 다 허용 (초기단계 안전용)
    if status is None:
        return True, True, "NO_STATUS"

    # Enum 이든 문자열이든 모두 대문자 문자열로 통일
    raw = getattr(status, "value", status)
    status_str = str(raw).upper()

    # 1) 모집 중: 읽기 + 쓰기 허용
    #    예시: OPEN, COLLECTING, COLLECTING_BUYERS 등
    if status_str in {
        "OPEN",
        "COLLECTING",
        "COLLECTING_BUYERS",
        "RECRUITING",
    }:
        return True, True, status_str

    # 2) 모집 마감 후 ~ 딜 마무리 전: 읽기만 허용 (쓰기 금지)
    #    예시: MATCHING, OFFERING, PAYING, PENDING_CLOSE 등
    if status_str in {
        "MATCHING",
        "OFFERING",
        "PAYING",
        "PENDING_CLOSE",
        "READY_TO_CLOSE",
    }:
        return True, False, status_str

    # 3) 딜 종료/취소: 읽기/쓰기 모두 차단
    #    예시: FINISHED, DONE, CLOSED, CANCELLED 등
    if status_str in {
        "FINISHED",
        "DONE",
        "CLOSED",
        "CANCELLED",
        "ABORTED",
    }:
        return False, False, status_str

    # 4) 모르는 상태면: 읽기만 허용 (보수적으로 쓰기는 막는다)
    return True, False, status_str



# ---------------------------------------------------
# ===== Inventory Audit / Reconcile (Offer) =====
# ---------------------------------------------------
def _sum_qty_by_status(db: Session, offer_id: int) -> dict:
    row = db.query(
        func.coalesce(func.sum(case((Reservation.status == ReservationStatus.PENDING,   Reservation.qty), else_=0)), 0).label("pending_qty"),
        func.coalesce(func.sum(case((Reservation.status == ReservationStatus.PAID,      Reservation.qty), else_=0)), 0).label("paid_qty"),
        func.coalesce(func.sum(case((Reservation.status == ReservationStatus.CANCELLED, Reservation.qty), else_=0)), 0).label("cancelled_qty"),
        func.coalesce(func.sum(case((Reservation.status == ReservationStatus.EXPIRED,   Reservation.qty), else_=0)), 0).label("expired_qty"),
    ).filter(Reservation.offer_id == offer_id).one()
    return {
        "pending_qty":   int(row.pending_qty or 0),
        "paid_qty":      int(row.paid_qty or 0),
        "cancelled_qty": int(row.cancelled_qty or 0),
        "expired_qty":   int(row.expired_qty or 0),
    }

def get_offer_stats(db: Session, offer_id: int) -> dict:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError(f"Offer not found: {offer_id}")

    sums = _sum_qty_by_status(db, offer_id)
    total_available = int(offer.total_available_qty or 0)
    model_reserved  = int(offer.reserved_qty or 0)
    model_sold      = int(offer.sold_qty or 0)
    remaining       = total_available - model_reserved - model_sold

    return {
        "offer_id": offer_id,
        "total_available_qty": total_available,
        "reserved_qty(model)": model_reserved,
        "sold_qty(model)": model_sold,
        "remaining": remaining,
        "pending_qty(sum_reservations)":   sums["pending_qty"],
        "paid_qty(sum_reservations)":      sums["paid_qty"],
        "cancelled_qty(sum_reservations)": sums["cancelled_qty"],
        "expired_qty(sum_reservations)":   sums["expired_qty"],
        "is_confirmed": bool(offer.is_confirmed),
        "is_active": bool(offer.is_active),
        "deadline_at": offer.deadline_at,
        "created_at": offer.created_at,
    }

def audit_offer_inventory(db: Session, offer_id: int) -> dict:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError(f"Offer not found: {offer_id}")

    stats = get_offer_stats(db, offer_id)
    hints: list[str] = []

    if stats["reserved_qty(model)"] != stats["pending_qty(sum_reservations)"]:
        hints.append(
            f"reserved_qty mismatch: model={stats['reserved_qty(model)']} vs sum(PENDING)={stats['pending_qty(sum_reservations)']}"
        )
    if stats["sold_qty(model)"] != stats["paid_qty(sum_reservations)"]:
        hints.append(
            f"sold_qty mismatch: model={stats['sold_qty(model)']} vs sum(PAID)={stats['paid_qty(sum_reservations)']}"
        )
    if stats["remaining"] < 0:
        hints.append("remaining < 0 (over-allocated)")

    return {"ok": len(hints) == 0, "hints": hints, "stats": stats}

def reconcile_offer_inventory(db: Session, offer_id: int, apply: bool = False) -> dict:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError(f"Offer not found: {offer_id}")

    sums = _sum_qty_by_status(db, offer_id)
    before = {"reserved_qty": int(offer.reserved_qty or 0), "sold_qty": int(offer.sold_qty or 0)}
    after  = {"reserved_qty": sums["pending_qty"],          "sold_qty": sums["paid_qty"]}
    changed = (before != after)

    if apply and changed:
        offer.reserved_qty = after["reserved_qty"]
        offer.sold_qty     = after["sold_qty"]
        db.add(offer)
        db.commit()
        db.refresh(offer)

    stats = get_offer_stats(db, offer_id)
    return {"applied": bool(apply and changed), "changed": changed, "before": before,
            "after": {"reserved_qty": int(offer.reserved_qty or 0), "sold_qty": int(offer.sold_qty or 0)},
            "stats": stats}

# =========================================================
# 🧾 Offer Capacity & Reservations
# =========================================================
def get_offer_remaining_capacity(db: Session, offer_id: int) -> int:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError(f"Offer not found: {offer_id}")
    total = int(offer.total_available_qty or 0)
    sold = int(offer.sold_qty or 0)
    reserved = int(offer.reserved_qty or 0)
    return total - sold - reserved



# =========================================================
# 🧾 Reservation 생성
# =========================================================
import logging
logger = logging.getLogger(__name__)

logger.warning("[DEBUG] create_reservation() VERSION=2025-12-28 snapshot_cancel_rule=USE_POLICY_ROW")

def create_reservation(
    db: Session,
    *,
    deal_id: int,
    offer_id: int,
    buyer_id: int,
    qty: int,
    hold_minutes: Optional[int] = None,
) -> Reservation:
    """
    예약 생성 (좌석 홀드)

    ✅ v3.6 핵심:
    - 예약 생성 시점에 amount_goods / amount_shipping / amount_total 을 스냅샷 저장
    - 환불/정산의 SSOT는 Reservation.amount_* (+ policy_snapshot_json)
    """
    if qty <= 0:
        raise ConflictError("qty must be > 0")

    offer = db.get(Offer, offer_id)
    if not offer or offer.deal_id != deal_id:
        raise NotFoundError("Offer not found for deal")

    remain = get_offer_remaining_capacity(db, offer_id)
    if qty > remain:
        raise ConflictError(f"not enough capacity (remain={remain})")

    now = _utcnow()

    # ---------------------------------------------------------
    # ✅ D2: OfferPolicy 연결 + 스냅샷 저장 (SSOT)
    #  - reservation.policy_id: offer_policies.id (1:1)
    #  - reservation.policy_snapshot_json: 당시 정책 스냅샷
    #
    # ⚠️ 주의:
    # - cancel_rule은 반드시 A1/A2/A3/A4 중 하나여야 함 (ResponseValidationError 방지)
    # - 스냅샷은 policy_row 값을 그대로 복사 (불일치 금지)
    # ---------------------------------------------------------
    resv_policy_id = None
    snapshot = None

    try:
        policy_row = (
            db.query(models.OfferPolicy)
            .filter(models.OfferPolicy.offer_id == offer_id)
            .first()
        )

        # 정책이 없으면 전역 기본값으로 seed 생성 (운영 안전)
        if policy_row is None:
            try:
                from app.policy.api import cooling_days as _default_cooling_days
                cd = int(_default_cooling_days())
            except Exception:
                cd = 7  # 정책 모듈이 깨진 경우만 안전 fallback

            # ✅ cancel_rule은 반드시 A1~A4 중 하나
            # "무상환불기간(쿨링)" 의미로 쓰려면 A3(배송완료 후 X일)을 사용
            policy_row = models.OfferPolicy(
                offer_id=offer_id,
                cancel_rule="A3",
                cancel_within_days=cd,
                extra_text="[AUTO seed at create_reservation]",
            )
            db.add(policy_row)
            db.flush()  # policy_row.id 확보

        # ✅ reservation에 FK 연결
        resv_policy_id = int(getattr(policy_row, "id"))

        # ✅ 스냅샷은 policy_row 그대로 복사 (절대 임의값 넣지 않기)
        snapshot = {
            "offer_policy_id": resv_policy_id,
            "cancel_rule": getattr(policy_row, "cancel_rule", None),
            "cancel_within_days": getattr(policy_row, "cancel_within_days", None),
            "extra_text": getattr(policy_row, "extra_text", None),
        }

    except Exception:
        # 정책이 깨져도 예약 생성 자체가 완전 죽지 않게(운영 안전)
        resv_policy_id = None
        snapshot = None

    # ---------------------------------------------------------
    # ✅ D1: 결제 제한시간(분) SSOT = policy (hold_minutes 우선)
    # ---------------------------------------------------------
    if hold_minutes is not None:
        minutes = int(hold_minutes)
    else:
        try:
            from app.policy.api import payment_timeout_minutes
            minutes = int(payment_timeout_minutes())
        except Exception:
            minutes = int(
                getattr(
                    TIME_POLICY,
                    "payment_timeout_minutes",
                    getattr(TIME_POLICY, "reservation_pay_window_minutes", 5),
                )
            )

    if minutes < 1:
        minutes = 1
    if minutes > 24 * 60:
        minutes = 24 * 60

    expires_at = now + timedelta(minutes=minutes)

    # ---------------------------------------------------------
    # ✅ 금액 스냅샷 계산 (예약 생성 시점 SSOT)
    # ---------------------------------------------------------
    from app.core.shipping_policy import calc_shipping_fee

    unit_price = int(getattr(offer, "price", 0) or 0)
    amount_goods = unit_price * int(qty)

    amount_shipping = int(
        calc_shipping_fee(
            mode=getattr(offer, "shipping_mode", None),
            fee_per_reservation=getattr(offer, "shipping_fee_per_reservation", 0),
            fee_per_qty=getattr(offer, "shipping_fee_per_qty", 0),
            qty=int(qty),
        ) or 0
    )

    amount_total = int(amount_goods + amount_shipping)

    resv = Reservation(
        deal_id=deal_id,
        offer_id=offer_id,
        buyer_id=buyer_id,
        qty=qty,
        status=ReservationStatus.PENDING,
        created_at=now,
        expires_at=expires_at,

        policy_id=resv_policy_id,
        policy_snapshot_json=json.dumps(snapshot, ensure_ascii=False) if snapshot else None,
        policy_agreed_at=now if snapshot else None,

        idempotency_key=None,

        amount_goods=amount_goods,
        amount_shipping=amount_shipping,
        amount_total=amount_total,
    )

    offer.reserved_qty = int(offer.reserved_qty or 0) + qty

    db.add(resv)
    db.add(offer)
    db.commit()
    db.refresh(resv)

    # ---------------------------------------------------------
    # ✅ Evidence Pack (reservation_create_v1)
    # ---------------------------------------------------------
    try:
        from app.routers.activity_log import log_event as activity_log_event
        from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

        evidence_pack = build_evidence_pack_v0(
            db,
            kind="reservation_create_v1",
            payload={
                "reservation": resv,
                "offer": offer,
                "actor": "buyer_create_reservation",
                "expected_source": "crud.create_reservation",
                "before": {},
                "run_id": None,
                "request_id": None,
                "notes": [],
            },
        )

        rid = int(getattr(resv, "id", 0) or 0)
        activity_log_event(
            db,
            event_type="evidence.resv_create_v1",
            actor_type="SYSTEM",
            actor_id=None,
            buyer_id=getattr(resv, "buyer_id", None),
            seller_id=getattr(offer, "seller_id", None),
            deal_id=getattr(offer, "deal_id", None),
            offer_id=getattr(resv, "offer_id", None),
            reservation_id=getattr(resv, "id", None),
            meta=evidence_pack,
            idempotency_key=f"evidence:resv_create_v1:{rid}",
        )
    except Exception:
        pass

    return resv


# --------------------------------------------
# Reservation cancel
#-----------------------------------------------
def cancel_reservation(
    db: Session,
    *,
    reservation_id: int,
    buyer_id: Optional[int] = None,
    actor: str = "buyer_cancel",   # 누가 취소했는지 태깅용 (buyer/seller/admin...)
) -> Reservation:
    # 1) 예약 조회
    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")

    # 2) 소유자 가드 (buyer_id 를 넘겨준 경우에만 체크)
    if buyer_id is not None and resv.buyer_id != buyer_id:
        raise ConflictError("not owned by buyer")

    # 3) 상태별 분기
    # ------------------------------------------------------------------
    # (1) PENDING 예약 취소  → 기존 로직 그대로 유지
    # ------------------------------------------------------------------
    if resv.status == ReservationStatus.PENDING:
        offer = db.get(Offer, resv.offer_id)
        if not offer:
            raise NotFoundError("Offer not found")

        # 예약 좌석 해제
        offer.reserved_qty = max(0, int(offer.reserved_qty or 0) - resv.qty)

        resv.status = ReservationStatus.CANCELLED
        # phase 필드가 있다면 여기서 바꿔도 됨 (import 되어 있으면 사용)
        # resv.phase = ReservationPhase.CANCELLED
        resv.cancelled_at = _utcnow()

        db.add(resv)
        db.add(offer)
        db.commit()
        db.refresh(resv)
        
        # ---------------------------------------------------------
        # ✅ Evidence Pack (reservation_cancel_v1) - PENDING cancel
        #    위치: db.commit(); db.refresh(resv) 직후, return 직전
        # ---------------------------------------------------------
        try:
            from app.routers.activity_log import log_event as activity_log_event
            from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

            evidence_pack = build_evidence_pack_v0(
                db,
                kind="reservation_cancel_v1",
                payload={
                    "reservation": resv,
                    "offer": offer,
                    "actor": actor,
                    "cancel_stage": "BEFORE_SHIPPING",  # PENDING은 배송 전으로 취급
                    "cancel_case": "FULL",              # PENDING 취소는 전량 취소
                    "refunded_qty_delta": 0,
                    "amount_total_refund_delta": 0,
                    "amount_total": int(getattr(resv, "amount_total", 0) or 0),
                    "amount_shipping": int(getattr(resv, "amount_shipping", 0) or 0),
                    "expected_source": "pending_cancel",
                    "preview_amount_total_refund": None,
                    "fallback_amount_total_refund": None,
                    "decision_supported": True,
                    "meta_supported": True,
                    "invariants_ok": True,
                    "before": {
                        "status_before": "PENDING",
                        "refunded_qty": int(getattr(resv, "refunded_qty", 0) or 0),
                        "refunded_amount_total": int(getattr(resv, "refunded_amount_total", 0) or 0),
                    },
                    "run_id": None,
                    "request_id": None,
                    "notes": [],
                },
            )

            rid = int(getattr(resv, "id", 0) or 0)
            activity_log_event(
                db,
                event_type="evidence_pack.reservation_cancel_v1",
                actor_type="SYSTEM",
                actor_id=None,
                buyer_id=getattr(resv, "buyer_id", None),
                seller_id=getattr(offer, "seller_id", None),
                deal_id=getattr(offer, "deal_id", None),
                offer_id=getattr(resv, "offer_id", None),
                reservation_id=getattr(resv, "id", None),
                meta=evidence_pack,
                idempotency_key=f"evidence:reservation_cancel_v1:{rid}:PENDING:CANCELLED:{actor}",
            )
        except Exception:
            pass
        
        return resv

    # ------------------------------------------------------------------
    # (2) PAID 예약 취소 (환불)  → 환불정책 엔진 로깅만 추가
    # ------------------------------------------------------------------
    if resv.status == ReservationStatus.PAID:
        offer = db.get(Offer, resv.offer_id)
        if not offer:
            raise NotFoundError("Offer not found")

        # 이미 판매로 잡혀 있던 수량 롤백
        offer.sold_qty = max(0, int(offer.sold_qty or 0) - resv.qty)

        resv.status = ReservationStatus.CANCELLED
        # resv.phase = ReservationPhase.CANCELLED  # 필요하면 사용
        resv.cancelled_at = _utcnow()

        # 🔍 환불 정책 엔진 호출 (v1: 실제 돈/포인트는 안 건드리고 로그만 남김)
        try:
            _log_refund_policy_for_paid_reservation(
                db,
                resv,
                actor=actor,
            )
        except Exception as e:
            # 정책 엔진에서 에러가 나더라도 취소 흐름은 막지 않는다.
            logger.exception(
                "[REFUND_POLICY] failed for reservation_id=%s: %s",
                resv.id,
                e,
            )

        db.add(resv)
        db.add(offer)
        db.commit()
        db.refresh(resv)
        
        # ---------------------------------------------------------
        # ✅ Evidence Pack (reservation_cancel_v1) - PAID cancel
        #    위치: db.commit(); db.refresh(resv) 직후, return resv 직전
        # ---------------------------------------------------------
        try:
            from app.routers.activity_log import log_event as activity_log_event
            from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

            # PAID 취소는 "환불정책 엔진 로그"를 호출했지만,
            # 이 함수 자체는 refunded_qty/amount를 직접 바꾸지 않을 수 있어.
            # 그래서 delta는 일단 0으로 찍고,
            # 추후 환불 로직이 붙으면 여기 delta를 정확히 채우면 됨.
            evidence_pack = build_evidence_pack_v0(
                db,
                kind="reservation_cancel_v1",
                payload={
                    "reservation": resv,
                    "offer": offer,
                    "actor": actor,
                    "cancel_stage": "UNKNOWN",  # TODO: cooling_state 연결 가능
                    "cancel_case": "FULL",
                    "refunded_qty_delta": 0,
                    "amount_total_refund_delta": 0,
                    "amount_total": int(getattr(resv, "amount_total", 0) or 0),
                    "amount_shipping": int(getattr(resv, "amount_shipping", 0) or 0),
                    "expected_source": "paid_cancel",
                    "preview_amount_total_refund": None,
                    "fallback_amount_total_refund": None,
                    "decision_supported": True,
                    "meta_supported": True,
                    "invariants_ok": True,
                    "before": {
                        "status_before": "PAID",
                        "refunded_qty": int(getattr(resv, "refunded_qty", 0) or 0),
                        "refunded_amount_total": int(getattr(resv, "refunded_amount_total", 0) or 0),
                    },
                    "run_id": None,
                    "request_id": None,
                    "notes": [],
                },
            )

            rid = int(getattr(resv, "id", 0) or 0)
            activity_log_event(
                db,
                event_type="evidence_pack.reservation_cancel_v1",
                actor_type="SYSTEM",
                actor_id=None,
                buyer_id=getattr(resv, "buyer_id", None),
                seller_id=getattr(offer, "seller_id", None),
                deal_id=getattr(offer, "deal_id", None),
                offer_id=getattr(resv, "offer_id", None),
                reservation_id=getattr(resv, "id", None),
                meta=evidence_pack,
                idempotency_key=f"evidence:reservation_cancel_v1:{rid}:PAID:CANCELLED:{actor}",
            )
        except Exception:
            pass
        
        
        return resv
    

    # ------------------------------------------------------------------
    # (3) 그 외 상태 (이미 CANCELLED 등) → 409
    # ------------------------------------------------------------------
    raise ConflictError(f"cannot cancel reservation in status={resv.status}")



def expire_reservations(
    db: Session,
    *,
    deal_id: Optional[int] = None,
    offer_id: Optional[int] = None,
    older_than: Optional[datetime] = None
) -> int:
    """PENDING + 만료시간 경과 → EXPIRED, reserved_qty 원복"""
    now = _utcnow()
    ts = older_than or now

    q = db.query(Reservation).filter(
        Reservation.status == ReservationStatus.PENDING,
        Reservation.expires_at.isnot(None),
        Reservation.expires_at < ts,
    )
    if deal_id is not None:
        q = q.filter(Reservation.deal_id == deal_id)
    if offer_id is not None:
        q = q.filter(Reservation.offer_id == offer_id)

    rows: List[Reservation] = q.all()
    count = 0

    for r in rows:
        offer = db.get(Offer, r.offer_id)

        # before snapshot (최소)
        before_snapshot = {
            "status_before": str(getattr(r, "status", None)),
            "reserved_qty_before": int(getattr(offer, "reserved_qty", 0) or 0) if offer else None,
            "sold_qty_before": int(getattr(offer, "sold_qty", 0) or 0) if offer else None,
        }

        if offer:
            offer.reserved_qty = max(0, int(offer.reserved_qty or 0) - r.qty)
            db.add(offer)

        r.status = ReservationStatus.EXPIRED
        r.expired_at = now
        db.add(r)

        count += 1
        # ---------------------------------------------------------
        # ✅ Evidence Pack (reservation_expire_v1)
        #    위치: row 처리 직후(best-effort)
        #    ✅ 주의: app.routers.activity_log.log_event()는 내부에서 commit 하므로 사용 금지
        #           여기서는 ActivityLog row를 직접 add만 하고,
        #           함수 끝에서 1회 db.commit()으로 같이 커밋한다.
        # ---------------------------------------------------------
        try:
            import json
            from app.routers.activity_log import ActivityLog  # 모델 직접 사용
            from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

            if offer is not None:
                evidence_pack = build_evidence_pack_v0(
                    db,
                    kind="reservation_expire_v1",
                    payload={
                        "reservation": r,
                        "offer": offer,
                        "actor": "system_expire",
                        "expire_stage": "BEFORE_SHIPPING",
                        "expected_source": "expire_reservations",
                        "before": before_snapshot,
                        "run_id": None,
                        "request_id": None,
                        "notes": [],
                    },
                )

                rid = int(getattr(r, "id", 0) or 0)

                row = ActivityLog(
                    event_type="evidence.resv_expire_v1",
                    actor_type="SYSTEM",
                    actor_id=None,
                    buyer_id=getattr(r, "buyer_id", None),
                    seller_id=getattr(offer, "seller_id", None),
                    deal_id=getattr(offer, "deal_id", None),
                    offer_id=getattr(r, "offer_id", None),
                    reservation_id=getattr(r, "id", None),
                    idempotency_key=f"evidence:resv_expire_v1:{rid}",
                    meta=json.dumps(evidence_pack or {}, ensure_ascii=False),
                )
                db.add(row)
        except Exception:
            pass
        
        # ---------------------------------------------------------
        # ✅ Evidence Pack (reservation_expire_v1)
        #    위치: row 처리 직후(best-effort)
        #    ✅ 주의: app.routers.activity_log.log_event()는 내부에서 commit 하므로 사용 금지
        #           여기서는 ActivityLog row를 직접 add만 하고,
        #           함수 끝에서 1회 db.commit()으로 같이 커밋한다.
        # ---------------------------------------------------------
        try:
            import json
            from app.routers.activity_log import ActivityLog  # 모델 직접 사용
            from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

            if offer is not None:
                evidence_pack = build_evidence_pack_v0(
                    db,
                    kind="reservation_expire_v1",
                    payload={
                        "reservation": r,
                        "offer": offer,
                        "actor": "system_expire",
                        "expire_stage": "BEFORE_SHIPPING",
                        "expected_source": "expire_reservations",
                        "before": before_snapshot,
                        "run_id": None,
                        "request_id": None,
                        "notes": [],
                    },
                )

                rid = int(getattr(r, "id", 0) or 0)

                row = ActivityLog(
                    event_type="evidence.resv_expire_v1",
                    actor_type="SYSTEM",
                    actor_id=None,
                    buyer_id=getattr(r, "buyer_id", None),
                    seller_id=getattr(offer, "seller_id", None),
                    deal_id=getattr(offer, "deal_id", None),
                    offer_id=getattr(r, "offer_id", None),
                    reservation_id=getattr(r, "id", None),
                    idempotency_key=f"evidence:resv_expire_v1:{rid}",
                    meta=json.dumps(evidence_pack or {}, ensure_ascii=False),
                )
                db.add(row)
        except Exception:
            pass

    db.commit()
    return count



def pay_reservation(db: Session, reservation_id: int, paid_amount: int) -> Reservation:
    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")

    if resv.status != ReservationStatus.PENDING:
        raise ConflictError(f"cannot pay reservation: status={resv.status}")

    offer = db.get(Offer, resv.offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    if int(paid_amount or 0) <= 0:
        raise ConflictError("paid_amount must be positive")

    # ---------------------------------------------------------
    # ✅ 결제 시점 백필(구버전 데이터/깨진 스냅샷 보정)
    #  - 원칙 SSOT는 Reservation.amount_* (예약 생성 시점 스냅샷)
    #  - 다만 (amount_total <= 0) 등 비정상인 경우만 계산값으로 복구
    # ---------------------------------------------------------


    qty = int(getattr(resv, "qty", 0) or 0)
    if qty <= 0:
        raise ConflictError("reservation qty must be positive")

    unit_price = int(getattr(offer, "price", 0) or 0)

    calc_goods = unit_price * qty
    calc_shipping = int(
        calc_shipping_fee(
            mode=getattr(offer, "shipping_mode", None),
            fee_per_reservation=getattr(offer, "shipping_fee_per_reservation", 0),
            fee_per_qty=getattr(offer, "shipping_fee_per_qty", 0),
            qty=qty,
        ) or 0
    )
    if calc_shipping < 0:
        calc_shipping = 0
    calc_total = int(calc_goods + calc_shipping)

    db_goods = int(getattr(resv, "amount_goods", 0) or 0)
    db_shipping = int(getattr(resv, "amount_shipping", 0) or 0)
    db_total = int(getattr(resv, "amount_total", 0) or 0)

    mismatch = (db_goods != calc_goods) or (db_shipping != calc_shipping) or (db_total != calc_total)

    # ✅ 백필 조건(보수적): DB 스냅샷이 비정상(0/음수)이면 복구
    backfilled = False
    if db_total <= 0 or db_goods < 0 or db_shipping < 0:
        resv.amount_goods = calc_goods
        resv.amount_shipping = calc_shipping
        resv.amount_total = calc_total
        backfilled = True

        # 백필 후 최신값 재조회용 변수도 동기화
        db_goods = int(resv.amount_goods or 0)
        db_shipping = int(resv.amount_shipping or 0)
        db_total = int(resv.amount_total or 0)

    # ✅ 결제 기준 금액(SSOT)
    amount_total = int(db_total or 0)
    if amount_total <= 0:
        # 백필 후에도 0이면 데이터/정책 문제
        raise ConflictError("payment amount must be positive")

    # paid_amount mismatch(일단은 경고/로그만)
    paid_amount_i = int(paid_amount or 0)
    diff = abs(paid_amount_i - amount_total)
    # ✅ 허용오차(원 단위): 추후 정책으로 조정 가능
    allowed_diff = 0

    # ---------------------------------------------------------
    # 결제 처리
    # ---------------------------------------------------------
    resv.status = ReservationStatus.PAID
    resv.paid_at = _utcnow()

    pay = models.ReservationPayment(
        reservation_id=resv.id,
        amount_paid=paid_amount_i,
        paid_at=resv.paid_at,
    )
    db.add(pay)

    # 수량 이동
    offer.sold_qty = int(offer.sold_qty or 0) + int(resv.qty or 0)
    offer.reserved_qty = max(0, int(offer.reserved_qty or 0) - int(resv.qty or 0))

    db.add(resv)
    db.add(offer)
    db.commit()
    db.refresh(resv)

    
    # ---------------------------------------------------------
    # ✅ Evidence Pack (reservation_paid_v1)
    #    위치: db.commit(); db.refresh(resv) 직후, return 직전
    # ---------------------------------------------------------
    try:
        from app.routers.activity_log import log_event as activity_log_event
        from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

        # before snapshot (최소)
        before_snapshot = {
            "status_before": "PENDING",
        }

        evidence_pack = build_evidence_pack_v0(
            db,
            kind="reservation_paid_v1",
            payload={
                "reservation": resv,
                "offer": offer,
                "actor": "system_pay",
                "paid_amount": int(paid_amount_i),
                "amount_total_ssot": int(amount_total),
                "paid_amount_diff": int(diff),
                "paid_amount_allowed_diff": int(allowed_diff),
                "snapshot_mismatch": bool(mismatch),
                "snapshot_backfilled": bool(backfilled),
                "db_amount_goods": int(db_goods),
                "db_amount_shipping": int(db_shipping),
                "db_amount_total": int(db_total),
                "calc_amount_goods": int(calc_goods),
                "calc_amount_shipping": int(calc_shipping),
                "calc_amount_total": int(calc_total),
                "before": before_snapshot,
                "run_id": None,
                "request_id": None,
                "notes": [],
            },
        )

        rid = int(getattr(resv, "id", 0) or 0)
        activity_log_event(
            db,
            event_type="evidence.resv_paid_v1",
            actor_type="SYSTEM",
            actor_id=None,
            buyer_id=getattr(resv, "buyer_id", None),
            seller_id=getattr(offer, "seller_id", None),
            deal_id=getattr(offer, "deal_id", None),
            offer_id=getattr(resv, "offer_id", None),
            reservation_id=getattr(resv, "id", None),
            meta=evidence_pack,
            # 결제는 예약당 1번이 SSOT
            idempotency_key=f"evidence:resv_paid_v1:{rid}",
        )
    except Exception:
        pass

    return resv


#--------------------------------
# Reservation pending 예약취소
#--------------------------------
class CrudNotFoundError(Exception):
    pass
class CrudInvalidStatusError(Exception):
    pass

def cancel_pending_reservation(
    db: Session,
    reservation_id: int,
    actor: str = "buyer_cancel",
) -> models.Reservation:
    """
    PENDING 상태의 예약을 취소한다.
    - 재고 영향: Offer.reserved_qty 감소
    - Reservation.status: PENDING → CANCELLED
    """
    resv = (
        db.query(models.Reservation)
        .filter(models.Reservation.id == reservation_id)
        .with_for_update()
        .first()
    )
    if not resv:
        raise CrudNotFoundError(f"Reservation {reservation_id} not found")

    status_val = getattr(resv, "status", None)
    name = getattr(status_val, "name", None) or str(status_val)

    if name != "PENDING":
        raise CrudInvalidStatusError(f"cannot cancel PENDING: status={name}")

    # 연결된 Offer 로드
    offer = (
        db.query(models.Offer)
        .filter(models.Offer.id == resv.offer_id)
        .with_for_update()
        .first()
    )
    if not offer:
        raise CrudNotFoundError(f"Offer {resv.offer_id} not found for reservation")

    qty = int(getattr(resv, "qty", 0) or 0)

    # 🔹 재고 처리: reserved_qty 감소, sold_qty 는 그대로
    cur_reserved = int(getattr(offer, "reserved_qty", 0) or 0)
    new_reserved = max(0, cur_reserved - qty)
    offer.reserved_qty = new_reserved

    # 예약 상태 변경
    resv.status = "CANCELLED"  # Enum이면 models.ReservationStatus.CANCELLED 쓰면 됨
    resv.cancelled_at = datetime.now(timezone.utc)

    db.add(offer)
    db.add(resv)
    db.commit()
    db.refresh(resv)
    return resv


def mark_reservation_shipped(
    db: Session,
    *,
    reservation_id: int,
    seller_id: int | None = None,
) -> models.Reservation:
    """
    셀러가 '발송 완료' 처리.
    - 상태는 PAID 여야 함.
    - (선택) seller_id를 넘겨주면 해당 셀러의 offer인지 검증.
    """
    resv = db.get(models.Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")

    # 상태 체크
    status_val = getattr(resv, "status", None)
    name = getattr(status_val, "name", None) or str(status_val)
    if name != "PAID":
        raise ConflictError(f"cannot mark shipped: status={name}")

    # seller_id 검증 (필요할 때만)
    if seller_id is not None:
        offer = db.get(models.Offer, resv.offer_id)
        if not offer or int(getattr(offer, "seller_id", 0)) != int(seller_id):
            raise ConflictError("reservation does not belong to this seller")

    # 최초 1회만 shipped_at 세팅
    if resv.shipped_at is None:
        resv.shipped_at = _utcnow()
    # delivered_at / arrival_confirmed_at 은 여기서는 건드리지 않음

    db.add(resv)
    db.commit()
    db.refresh(resv)
    return resv




def _map_refund_actor(actor: str) -> tuple[FaultParty, RefundTrigger]:
    """
    actor 문자열(라우터/스크립트에서 넘어오는 값)을 FaultParty/RefundTrigger로 표준화.

    지원 예:
      - buyer_cancel
      - seller_cancel
      - admin_force
      - system_error
      - dispute_resolve
    """
    a = (actor or "").strip().lower()

    # buyer
    if a.startswith("buyer") or a in ("buyer_cancel", "cancel_by_buyer"):
        return FaultParty.BUYER, RefundTrigger.BUYER_CANCEL

    # seller
    if a.startswith("seller") or a in ("seller_cancel", "cancel_by_seller"):
        return FaultParty.SELLER, RefundTrigger.SELLER_CANCEL

    # admin
    if a.startswith("admin") or a in ("admin_force", "force_refund"):
        return FaultParty.SYSTEM, RefundTrigger.ADMIN_FORCE

    # dispute  ✅ 여기가 핵심(기존 누락/오매핑 케이스 방지)
    if "dispute" in a or a in ("dispute_resolve", "dispute", "resolve_dispute"):
        return FaultParty.DISPUTE, RefundTrigger.DISPUTE_RESOLVE

    # system
    if "system" in a or a in ("system_error", "pg_error", "platform_error"):
        return FaultParty.SYSTEM, RefundTrigger.SYSTEM_ERROR

    # fallback
    return FaultParty.SYSTEM, RefundTrigger.SYSTEM_ERROR


#--------------------------------------------
# 예약 / 결제 후 환불
#--------------------------------------------
def refund_paid_reservation(
    db: Session,
    *,
    reservation_id: int,
    actor: str = "buyer_cancel",
    quantity_refund: int | None = None,  # 부분환불 수량(옵션)
    shipping_refund_override: int | None = None,  # ✅ 배송비 환불 override(SELLER/ADMIN만)
    shipping_refund_override_reason: str | None = None,
) -> Reservation:
    """
    PAID 상태 예약에 대해 실제 환불을 실행하는 함수 (v3.6).

    ✅ 원칙:
    - preview_refund_for_paid_reservation()의 결과(ctx/decision)가 "정책/계산 SSOT"
    - 실행 단계는 DB 업데이트 + PG환불(필요시) + 로그/알림만 수행
    - preview와 execute가 1도 어긋나면 안 되므로, 여기서 금액을 재계산하지 않는다.

    quantity_refund:
      - None => 남은 수량 전체 환불
      - 1..remaining => 부분 환불 (PAID 유지, sold_qty 일부 롤백 + refunded_* 누적)

    shipping_refund_override:
      - SELLER/ADMIN actor만 허용
      - preview에서 정책 cap + auto_max 상한 내로 이미 clamp됨
      - execute에서는 preview 결과의 amount_shipping을 그대로 사용
    """
    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")

    if resv.status != ReservationStatus.PAID:
        raise ConflictError(f"cannot refund: reservation status={resv.status}")

    offer = db.get(Offer, resv.offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    now = _utcnow()

    # -------------------------------------------------
    # 0) SELLER/ADMIN만 override 허용 (buyer는 불가)
    # -------------------------------------------------
    actor_u = (actor or "").lower()
    override_allowed = ("seller" in actor_u) or ("admin" in actor_u)
    if shipping_refund_override is not None and not override_allowed:
        raise BadRequestError("shipping_refund_override is allowed for SELLER/ADMIN actor only")

    # -------------------------------------------------
    # 1) preview 로직 재사용 → RefundContext + RefundDecision
    #    - 여기서 이미:
    #      * 잔여수량 검증
    #      * 배송비 자동배정(SSOT: Reservation.amount_shipping)
    #      * v3.6 정책 cap 적용
    #      * override(SELLER/ADMIN) clamp
    #      * 로그(refund.preview.v36) 남김
    # -------------------------------------------------
    ctx, decision = preview_refund_for_paid_reservation(
        db,
        reservation_id=reservation_id,
        actor=actor,
        quantity_refund=quantity_refund,
        shipping_refund_override=shipping_refund_override,
        shipping_refund_override_reason=shipping_refund_override_reason,
        log_preview=True,
    )

    # context에서 다시 꺼내 쓰기 (정합성 유지)
    fault_party = ctx.fault_party
    trigger = ctx.trigger
    settlement_state = ctx.settlement_state
    cooling_state = ctx.cooling_state

    quantity_total = int(getattr(ctx, "quantity_total", 0) or 0)
    qr = int(getattr(ctx, "quantity_refund", 0) or 0)
    if quantity_total <= 0 or qr <= 0:
        raise ConflictError("invalid quantities in refund context")

    # 이미 환불된 수량
    already_refunded = int(getattr(resv, "refunded_qty", 0) or 0)

    # 추가 방어
    if already_refunded + qr > quantity_total:
        raise ConflictError(
            f"refund quantity exceeds reservation qty "
            f"(qty={quantity_total}, refunded={already_refunded}, requested={qr})"
        )

    is_full_refund = (already_refunded + qr >= quantity_total)

    # 이번 환불 금액(SSOT: ctx)
    refund_amount_total = int(getattr(ctx, "amount_total", 0) or 0)
    refund_amount_goods = int(getattr(ctx, "amount_goods", 0) or 0)
    refund_amount_shipping = int(getattr(ctx, "amount_shipping", 0) or 0)

    # -------------------------------------------------
    # 1-1) 🧾 PG 환불 호출 (use_pg_refund == True)
    #     - PG 실패하면 DB 변경 없이 즉시 중단
    # -------------------------------------------------
    if decision.use_pg_refund:
        if refund_amount_total <= 0:
            raise ConflictError("PG refund requested but refund amount is not positive")

        pg_tx_id = getattr(resv, "pg_transaction_id", None)

        pg_req = PgRefundRequest(
            pg_transaction_id=pg_tx_id,
            merchant_uid=f"reservation:{resv.id}",
            amount=refund_amount_total,
            reason=f"refund reservation {resv.id} (actor={actor}, qty={qr})",
            reservation_id=resv.id,
            buyer_id=resv.buyer_id,
        )

        pg_result = request_pg_refund(pg_req)

        if not pg_result.success:
            logging.error(
                "[refund_paid_reservation] PG refund failed: code=%s, msg=%s, resv_id=%s",
                pg_result.pg_error_code,
                pg_result.pg_error_message,
                resv.id,
            )
            raise ConflictError("PG refund failed")

        # (선택) PG 응답 금액이 다르면 로그로만 남기고 정책적으로는 ctx를 SSOT로 유지
        try:
            pg_cancel_amount = int(getattr(pg_result, "pg_cancel_amount", 0) or 0)
        except Exception:
            pg_cancel_amount = 0

    else:
        pg_cancel_amount = 0

    # -------------------------------------------------
    # 2) financial_plan (있으면) 생성 (로그용)
    # -------------------------------------------------
    try:
        financial_plan = REFUND_POLICY_ENGINE.build_financial_plan(ctx, decision)
    except Exception:
        financial_plan = None

    # -------------------------------------------------
    # 3) DB 상태 업데이트 (offer.sold_qty, reservation status, refunded 누적)
    # -------------------------------------------------
    # 3-1) offer.sold_qty 롤백: 환불 수량만큼 차감
    current_sold = int(getattr(offer, "sold_qty", 0) or 0)
    offer.sold_qty = max(0, current_sold - qr)

    # 3-2) Reservation 상태/phase
    if is_full_refund:
        resv.status = ReservationStatus.CANCELLED
        if hasattr(resv, "phase"):
            try:
                from .models import ReservationPhase
                resv.phase = ReservationPhase.CANCELLED
            except Exception:
                resv.phase = "CANCELLED"
        resv.cancelled_at = now
    else:
        # 부분환불: PAID 유지
        resv.status = ReservationStatus.PAID

    # 3-3) refunded 누적
    prev_qty = int(getattr(resv, "refunded_qty", 0) or 0)
    resv.refunded_qty = prev_qty + qr

    prev_total = int(getattr(resv, "refunded_amount_total", 0) or 0)
    resv.refunded_amount_total = prev_total + refund_amount_total

    # (있으면) goods/shipping 누적도 저장 (컬럼 없으면 조용히 패스)
    if hasattr(resv, "refunded_amount_goods"):
        try:
            prev_goods = int(getattr(resv, "refunded_amount_goods", 0) or 0)
            setattr(resv, "refunded_amount_goods", prev_goods + refund_amount_goods)
        except Exception:
            pass

    if hasattr(resv, "refunded_amount_shipping"):
        try:
            prev_ship = int(getattr(resv, "refunded_amount_shipping", 0) or 0)
            setattr(resv, "refunded_amount_shipping", prev_ship + refund_amount_shipping)
        except Exception:
            pass

    # -------------------------------------------------
    # 4) 포인트 롤백 (바이어 포인트)
    # -------------------------------------------------
    if decision.revoke_buyer_points:
        try:
            rollback_amount = int(R.BUYER_POINT_ON_PAID) * qr
        except Exception:
            rollback_amount = 20 * qr

        if rollback_amount > 0:
            db.add(
                PointTransaction(
                    user_type="buyer",
                    user_id=resv.buyer_id,
                    amount=-rollback_amount,
                    reason=f"refund reservation {resv.id} (rollback points, actor={actor}, qty={qr})",
                    created_at=now,
                )
            )

    # (셀러 포인트 롤백은 추후 decision.revoke_seller_points로 확장)

    db.add(resv)
    db.add(offer)
    db.commit()
    db.refresh(resv)

    # -------------------------------------------------
    # 5) ✅ 실행 로그 (refund.execute.v36)
    # -------------------------------------------------
    try:
        from app.routers.activity_log import log_event

        log_event(
            db,
            event_type="refund.execute.v36",
            entity_type="reservation",
            entity_id=resv.id,
            actor=str(actor),
            metadata={
                "quantity_total": quantity_total,
                "already_refunded_qty": already_refunded,
                "quantity_refund": qr,
                "is_full_refund": bool(is_full_refund),

                "refund_amount_total": refund_amount_total,
                "refund_amount_goods": refund_amount_goods,
                "refund_amount_shipping": refund_amount_shipping,

                "use_pg_refund": bool(decision.use_pg_refund),
                "pg_cancel_amount": int(pg_cancel_amount or 0),

                "fault_party": str(fault_party),
                "trigger": str(trigger),
                "settlement_state": str(settlement_state),
                "cooling_state": str(cooling_state),
                "decision_note": str(getattr(decision, "note", "")),

                "financial_plan": getattr(financial_plan, "__dict__", None) if financial_plan else None,

                "override_input": int(shipping_refund_override) if shipping_refund_override is not None else None,
                "override_reason": (shipping_refund_override_reason or "").strip() or None,
            },
        )
    except Exception:
        pass

    # -------------------------------------------------
    # 6) 🔔 환불 알림 생성 (best-effort)
    # -------------------------------------------------
    try:
        def _safe_enum_value(x):
            if hasattr(x, "value"):
                return x.value
            return str(x)

        # 바이어 알림
        try:
            create_notification(
                db,
                user_id=resv.buyer_id,
                type="reservation_refunded",
                title=f"예약 #{resv.id} 환불이 처리되었습니다.",
                message=(
                    f"딜 #{resv.deal_id} / 오퍼 #{resv.offer_id} 예약이 환불 처리되었습니다. "
                    f"(환불 금액: {refund_amount_total}원, 환불 수량: {qr}/{quantity_total})"
                ),
                meta={
                    "role": "buyer",
                    "deal_id": resv.deal_id,
                    "offer_id": resv.offer_id,
                    "reservation_id": resv.id,
                    "amount_total": refund_amount_total,
                    "amount_goods": refund_amount_goods,
                    "amount_shipping": refund_amount_shipping,
                    "quantity_total": quantity_total,
                    "quantity_refund": qr,
                    "fault_party": _safe_enum_value(fault_party),
                    "trigger": _safe_enum_value(trigger),
                    "settlement_state": _safe_enum_value(settlement_state),
                    "cooling_state": _safe_enum_value(cooling_state),
                    "is_full_refund": is_full_refund,
                },
            )
        except Exception as buyer_notify_err:
            logging.exception("failed to create buyer refund notification", exc_info=buyer_notify_err)

        # 셀러 알림
        try:
            seller_id = getattr(offer, "seller_id", None)
            if seller_id:
                create_notification(
                    db,
                    user_id=seller_id,
                    type="reservation_refunded_on_offer",
                    title=f"오퍼 #{offer.id} 예약 환불이 발생했습니다.",
                    message=(f"딜 #{resv.deal_id}의 예약 #{resv.id}가 환불 처리되었습니다. "
                             f"(환불 수량: {qr}/{quantity_total})"),
                    meta={
                        "role": "seller",
                        "deal_id": resv.deal_id,
                        "offer_id": resv.offer_id,
                        "reservation_id": resv.id,
                        "buyer_id": resv.buyer_id,
                        "amount_total": refund_amount_total,
                        "amount_goods": refund_amount_goods,
                        "amount_shipping": refund_amount_shipping,
                        "quantity_total": quantity_total,
                        "quantity_refund": qr,
                        "fault_party": _safe_enum_value(fault_party),
                        "trigger": _safe_enum_value(trigger),
                        "settlement_state": _safe_enum_value(settlement_state),
                        "cooling_state": _safe_enum_value(cooling_state),
                        "is_full_refund": is_full_refund,
                    },
                )
        except Exception as seller_notify_err:
            logging.exception("failed to create seller refund notification", exc_info=seller_notify_err)

    except Exception as notify_err:
        logging.exception("refund notification flow failed", exc_info=notify_err)

    return resv



# ========= (호환용) admin_refund_preview 라우터용 래퍼 =========
def preview_refund_for_reservation(
    db: Session,
    *,
    reservation_id: int,
    actor: str = "buyer_cancel",
    quantity_refund: int | None = None,
    shipping_refund_override: int | None = None,
    shipping_refund_override_reason: str | None = None,
):
    """
    ✅ 기존 admin_refund_preview 라우터가 기대하는 함수 이름.
    내부적으로 preview_refund_for_paid_reservation 을 호출한 다음,
    admin 라우터가 쓰기 편하도록 dict 형태로 반환한다.

    - quantity_refund: 부분환불 수량 (옵션)
    - shipping_refund_override: 배송비 환불 override(ADMIN만 허용, 자동배정 범위 내로 캡)
    - shipping_refund_override_reason: override 사유
    """
    ctx, decision, meta = preview_refund_for_paid_reservation(
        db,
        reservation_id=reservation_id,
        actor=actor,
        quantity_refund=quantity_refund,
        shipping_refund_override=shipping_refund_override,
        shipping_refund_override_reason=shipping_refund_override_reason,
        log_preview=True,
    )

    # ctx/decision이 pydantic/dataclass/일반객체 어느 쪽이든 최대한 안전하게 dict화
    def _to_dict(x):
        if x is None:
            return None
        if isinstance(x, dict):
            return x
        if hasattr(x, "model_dump"):
            return x.model_dump()
        if hasattr(x, "dict"):
            return x.dict()
        if hasattr(x, "__dict__"):
            return dict(x.__dict__)
        return {"value": str(x)}

    return {
        "reservation_id": reservation_id,
        "actor": actor,
        "context": _to_dict(ctx),
        "decision": _to_dict(decision),
        "meta": meta,
    }



# ========= v3.5 / v3.6 공통: 환불 정책 미리보기 (부분환불 대응 + 배송비 자동배정/override/로그) =========
def preview_refund_for_paid_reservation(
    db: Session,
    *,
    reservation_id: int,
    actor: str = "buyer_cancel",
    quantity_refund: int | None = None,   # 부분환불 수량
    shipping_refund_override: int | None = None,  # 배송비 환불 override(권한은 호출 레이어에서 보장)
    shipping_refund_override_reason: str | None = None,
    return_meta: bool = False,  # ✅ 기본 False(호환 유지)
    log_preview: bool = True,
):
    """
    PAID 상태 예약에 대해:
      - DB는 건드리지 않고(환불 실행 X)
      - RefundPolicyEngine 의 결정을 미리보기

    ✅ v3.6 확장:
      - 배송비 부분환불 자동배정(Reservation.amount_shipping SSOT)
      - override(있으면 cap 적용) + reason 기록
      - meta 옵션 반환(호환 유지: 기본은 2개 반환)
      - preview 로그(best-effort)
    """
    from app.core.shipping_policy import (
        calc_shipping_fee,
        calc_shipping_breakdown_from_total,
        calc_shipping_refund_for_partial_qty,
    )

    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")

    if resv.status != ReservationStatus.PAID:
        raise ConflictError(f"cannot preview refund: reservation status={resv.status}")

    offer = db.get(Offer, resv.offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    
    # 1) actor → fault/trigger
    fault_party, trigger = _map_refund_actor(actor)

    # 2) 정산 상태
    settlement_state = _get_settlement_state_for_reservation(db, resv)

    # 3) 쿨링/배송 상태 (✅ SSOT: compute_cooling_state + cooling_days는 offer_policy 우선)
    from app.core.refund_policy import compute_cooling_state as _compute_cooling_state, DEFAULT_COOLING_DAYS
    from app.policy import api as policy_api

    _now = _utcnow()  # preview 시점 now (스코프 의존 제거)

    # cooling_days resolve (SSOT: offer_policies.cancel_within_days)
    _cooling_days: int | None = None

    # 1) reservation.policy_id 로 offer_policies 조회
    try:
        pid = getattr(resv, "policy_id", None)
        if pid:
            row = (
                db.query(models.OfferPolicy)
                .filter(models.OfferPolicy.id == int(pid))
                .first()
            )
            if row is not None:
                v = getattr(row, "cancel_within_days", None)
                if v is not None:
                    _cooling_days = int(v)
    except Exception:
        _cooling_days = None

    # 2) offer_id 로 offer_policies 조회
    if _cooling_days is None:
        try:
            oid = getattr(resv, "offer_id", None)
            if oid:
                row = (
                    db.query(models.OfferPolicy)
                    .filter(models.OfferPolicy.offer_id == int(oid))
                    .first()
                )
                if row is not None:
                    v = getattr(row, "cancel_within_days", None)
                    if v is not None:
                        _cooling_days = int(v)
        except Exception:
            _cooling_days = None

    # 3) policy.api.cooling_days() fallback
    if _cooling_days is None:
        try:
            _cooling_days = int(policy_api.cooling_days())
        except Exception:
            _cooling_days = None

    # 4) 최종 안전 fallback
    if _cooling_days is None:
        _cooling_days = int(DEFAULT_COOLING_DAYS)

    # 안전 가드 (음수 방지 + 과대 방지)
    if _cooling_days < 1:
        _cooling_days = 1
    if _cooling_days > 365:
        _cooling_days = 365

    cooling_state = _compute_cooling_state(
        shipped_at=getattr(resv, "shipped_at", None),
        delivered_at=getattr(resv, "delivered_at", None),
        arrival_confirmed_at=getattr(resv, "arrival_confirmed_at", None),
        now=_now,
        cooling_days=int(_cooling_days),
    )

    # 4) 수량
    quantity_total = int(getattr(resv, "qty", 0) or 0)
    if quantity_total <= 0:
        raise ConflictError("reservation qty must be positive for refund preview")

    already_refunded = int(getattr(resv, "refunded_qty", 0) or 0)
    remaining = quantity_total - already_refunded
    if remaining <= 0:
        raise ConflictError(
            f"no refundable quantity remains (total={quantity_total}, refunded={already_refunded})"
        )

    # 이번 환불 수량
    if quantity_refund is None:
        qr = remaining
    else:
        try:
            qr = int(quantity_refund)
        except Exception:
            raise BadRequestError("quantity_refund must be an integer")
        if qr <= 0:
            raise BadRequestError("quantity_refund must be >= 1")
        if qr > remaining:
            qr = remaining

    # 5) 금액(상품)
    # - SSOT는 reservation.amount_goods/amount_total이지만,
    #   unit_price는 offer.price를 쓰고(현행 코드 흐름 유지)
    unit_price = int(getattr(offer, "price", 0) or 0)
    amount_goods_refund = unit_price * qr

    # 6) 금액(배송비) - SSOT: Reservation.amount_shipping
    shipping_total_db = int(getattr(resv, "amount_shipping", 0) or 0)

    # (검증용) offer 기반 계산
    shipping_total_calc = int(
        calc_shipping_fee(
            mode=getattr(offer, "shipping_mode", None),
            fee_per_reservation=getattr(offer, "shipping_fee_per_reservation", 0),
            fee_per_qty=getattr(offer, "shipping_fee_per_qty", 0),
            qty=quantity_total,
        ) or 0
    )

    # 레거시 데이터 방어: DB가 0인데 calc가 있으면 calc를 기준으로 "미리보기" 계산만 보정
    shipping_total_effective = shipping_total_db
    if shipping_total_effective <= 0 and shipping_total_calc > 0:
        shipping_total_effective = shipping_total_calc

    shipping_mismatch = (shipping_total_db != shipping_total_calc)

    breakdown = calc_shipping_breakdown_from_total(
        total_shipping=shipping_total_effective,
        qty_total=quantity_total,
    )

    shipping_refund_auto = int(
        calc_shipping_refund_for_partial_qty(
            shipping_breakdown=breakdown,
            refund_qty=qr,
            already_refunded_qty=already_refunded,
        ) or 0
    )

    # 7) override 적용(있으면)
    override_applied = False
    override_input = None
    override_reason = (shipping_refund_override_reason or "").strip() or None

    shipping_refund_final = shipping_refund_auto
    if shipping_refund_override is not None:
        override_input = int(shipping_refund_override or 0)
        o = override_input
        if o < 0:
            o = 0
        # ✅ cap: 자동배정 범위 내로만 (실수/악용 방지)
        if o > shipping_refund_auto:
            o = shipping_refund_auto
        shipping_refund_final = o
        override_applied = True

    # ---------------------------------------------------------
    # ✅ v3.6 정책: 배송비를 환불에 포함할지 최종 결정(게이트)
    #    - cooling_state SSOT = 위에서 구한 compute_cooling_state 결과
    # ---------------------------------------------------------
    from app.core.refund_policy import is_shipping_refundable_by_policy

    shipping_refund_allowed_by_policy = is_shipping_refundable_by_policy(
        cooling_state=cooling_state,
        fault_party=fault_party,
        trigger=trigger,
    )

    if not shipping_refund_allowed_by_policy:
        # 정책상 배송비 환불 미포함이면 0으로 강제
        shipping_refund_final = 0
        override_applied = False  # 정책상 불가면 override도 적용 안 된 것으로 취급
        override_reason = None
        override_input = None
        override_blocked_by_policy = True
    else:
        override_blocked_by_policy = False

    amount_shipping_refund = int(shipping_refund_final or 0)
    amount_total_refund = int(amount_goods_refund + amount_shipping_refund)

    # 8) RefundContext
    ctx = RefundContext(
        reservation_id=resv.id,
        deal_id=resv.deal_id,
        offer_id=resv.offer_id,
        buyer_id=resv.buyer_id,
        seller_id=getattr(offer, "seller_id", None),

        amount_total=amount_total_refund,
        amount_goods=amount_goods_refund,
        amount_shipping=amount_shipping_refund,

        quantity_total=quantity_total,
        quantity_refund=qr,

        fault_party=fault_party,
        trigger=trigger,
        settlement_state=settlement_state,
        cooling_state=cooling_state,   # ✅ SSOT로 통일

        pg_fee_rate=0.0,
        platform_fee_rate=0.0,
    )

    decision = REFUND_POLICY_ENGINE.decide_for_paid_reservation(ctx)

    meta = {
        # ✅ 정책 태그(UX/로그용)
        "policy_version": "v3.6",
        "shipping_gate_rule": "OPTION_B",

        "reservation_id": resv.id,
        "actor": actor,
        "quantity_total": quantity_total,
        "already_refunded_qty": already_refunded,
        "quantity_refund": qr,

        "shipping_total_db": shipping_total_db,
        "shipping_total_calc": shipping_total_calc,
        "shipping_total_effective": shipping_total_effective,
        "shipping_mismatch": bool(shipping_mismatch),

        "shipping_breakdown": breakdown,
        "shipping_refund_auto": shipping_refund_auto,
        "shipping_refund_override_input": override_input,
        "shipping_refund_override_reason": override_reason,
        "shipping_refund_final": int(shipping_refund_final or 0),
        "shipping_refund_override_applied": bool(override_applied),
        "shipping_refund_override_blocked_by_policy": bool(override_blocked_by_policy),
        "shipping_refund_allowed_by_policy": bool(shipping_refund_allowed_by_policy),

        "amount_goods_refund": amount_goods_refund,
        "amount_shipping_refund": amount_shipping_refund,
        "amount_total_refund": amount_total_refund,

        "settlement_state": str(settlement_state),
        "cooling_state": str(getattr(cooling_state, "value", cooling_state)),
        "cooling_days_used": int(_cooling_days),
        "fault_party": getattr(fault_party, "value", str(fault_party)),
        "trigger": getattr(trigger, "value", str(trigger)),
        "decision_use_pg_refund": bool(getattr(decision, "use_pg_refund", False)),
        "decision_note": getattr(decision, "note", ""),
    }


    # 9) preview 로그(best-effort)
    if log_preview:
        try:
            from app.routers.activity_log import log_event

            # (A) 기존 preview meta 로그 (원하면 유지)
            log_event(
                db,
                event_type="refund.preview.v36",
                actor_type="SYSTEM",
                actor_id=None,
                buyer_id=resv.buyer_id,
                seller_id=getattr(offer, "seller_id", None),
                deal_id=resv.deal_id,
                offer_id=resv.offer_id,
                reservation_id=resv.id,
                meta=meta,
            )

            # (B) ✅ Evidence Pack v1 저장 (SSOT: ActivityLog.meta)
            # - event_type: evidence_pack.refund_dispute_v1
            # - meta: evidence_pack object
            evidence_pack = {
                "evidence_pack_version": "refund_dispute_v1",
                "event_time": _now.isoformat(),  # _now = _utcnow() 이미 위에서 만들었음
                "context": {
                    "actor": actor,
                    "stage": str(getattr(cooling_state, "value", cooling_state)),
                    "case": "PARTIAL" if qr < remaining else "FULL",
                },
                "entities": {
                    "reservation": {
                        "id": resv.id,
                        "buyer_id": resv.buyer_id,
                        "offer_id": resv.offer_id,
                        "qty": quantity_total,
                        "status_before": str(getattr(resv.status, "value", resv.status)),
                        "status_after": str(getattr(resv.status, "value", resv.status)),  # preview라 동일
                    },
                    "offer": {
                        "id": offer.id,
                        "deal_id": getattr(offer, "deal_id", None),
                        "seller_id": getattr(offer, "seller_id", None),
                        "price": float(getattr(offer, "price", 0) or 0),
                        "shipping_mode": str(getattr(offer, "shipping_mode", None)),
                        "shipping_fee_per_reservation": float(getattr(offer, "shipping_fee_per_reservation", 0) or 0),
                        "shipping_fee_per_qty": float(getattr(offer, "shipping_fee_per_qty", 0) or 0),
                        "sold_qty_before": getattr(offer, "sold_qty", None),
                        "sold_qty_after": getattr(offer, "sold_qty", None),  # preview라 동일
                    },
                },
                "amounts": {
                    "amount_total": int(getattr(resv, "amount_total", 0) or 0),
                    "amount_shipping": int(getattr(resv, "amount_shipping", 0) or 0),
                    "refund": {
                        "amount_total_refund": int(amount_total_refund),
                        "refunded_qty_delta": int(qr),
                    },
                    "source": {
                        "expected_source": "preview_meta",
                        "preview_amount_total_refund": int(amount_total_refund),
                        "fallback_amount_total_refund": None,
                        "meta_supported": True,
                    },
                },
                "checks": {
                    "decision_supported": bool(decision),
                    "invariants_ok": True,
                },
                "trace": {
                    "pg_tid": None,
                    "run_id": "preview_refund_for_paid_reservation",
                    "notes": [],
                },
            }

            log_event(
                db,
                event_type="evidence_pack.refund_dispute_v1",
                actor_type="SYSTEM",
                actor_id=None,
                buyer_id=resv.buyer_id,
                seller_id=getattr(offer, "seller_id", None),
                deal_id=resv.deal_id,
                offer_id=resv.offer_id,
                reservation_id=resv.id,
                meta=evidence_pack,
            )

        except Exception:
            pass

    # ✅ 반환(호환 유지)
    if return_meta:
        return ctx, decision, meta
    return ctx, decision




# ========= 환불 정책 프리뷰(미리보기) =========

def preview_refund_policy_for_reservation(
    db: Session,
    *,
    reservation_id: int,
    actor: str = "buyer_cancel",
) -> dict:
    """
    실제 환불(상태/포인트 변경) 없이,
    RefundContext + RefundDecision 만 계산해서 반환하는 진단용 함수.
    """
    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")

    offer = db.get(Offer, resv.offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    # 이미 refund_paid_reservation 에서 쓰는 로직 재사용
    # (너가 실제 코드에서 _build_refund_context / _map_refund_actor 이름이
    #  조금 다르다면 그걸 그대로 써도 됨)
    fault_party, trigger = _map_refund_actor(actor)

    now = _utcnow()

    # 쿨링타임 기준 시각
    base_ts = None
    if resv.arrival_confirmed_at:
        base_ts = _as_utc(resv.arrival_confirmed_at)
    elif resv.delivered_at:
        base_ts = _as_utc(resv.delivered_at)

    if base_ts is None:
        cooling_state = CoolingState.UNKNOWN
    else:
        delta = now - base_ts
        cooling_days = getattr(TIME_POLICY, "cooling_days", 0)
        if cooling_days and delta.total_seconds() > cooling_days * 86400:
            cooling_state = CoolingState.AFTER_COOLING
        else:
            cooling_state = CoolingState.WITHIN_COOLING

    # 정산 상태: v1 에서는 항상 NOT_SETTLED (추후 settlements 와 연동)
    settlement_state = SettlementState.NOT_SETTLED

    # 금액/수량 계산 (배송비는 아직 0)
    unit_price = int(offer.price or 0)
    quantity_total = int(resv.qty or 0)
    amount_goods = unit_price * quantity_total
    amount_shipping = 0
    amount_total = amount_goods + amount_shipping

    ctx = RefundContext(
        reservation_id=resv.id,
        deal_id=resv.deal_id,
        offer_id=resv.offer_id,
        buyer_id=resv.buyer_id,
        seller_id=offer.seller_id,

        amount_total=amount_total,
        amount_goods=amount_goods,
        amount_shipping=amount_shipping,

        quantity_total=quantity_total,
        quantity_refund=quantity_total,

        fault_party=fault_party,
        trigger=trigger,
        settlement_state=settlement_state,
        cooling_state=cooling_state,

        pg_fee_rate=0.0,
        platform_fee_rate=0.0,
    )

    decision = REFUND_POLICY_ENGINE.decide_for_paid_reservation(ctx)

    # dataclass → dict 로 변환해서 반환
    return {
        "reservation_id": resv.id,
        "actor": actor,
        "context": asdict(ctx),
        "decision": asdict(decision),
    }



def get_refund_summary_for_reservation(
    db: Session,
    *,
    reservation_id: int,
) -> ReservationRefundSummary:
    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")

    # 1) 기본 수량 정보
    try:
        qty_total = int(resv.qty or 0)
    except Exception:
        qty_total = 0

    try:
        already_refunded = int(getattr(resv, "refunded_qty", 0) or 0)
    except Exception:
        already_refunded = 0

    refundable_qty = max(qty_total - already_refunded, 0)

    # 2) offer / 가격 정보
    offer = db.get(Offer, resv.offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    unit_price = int(getattr(offer, "price", 0) or 0)

    amount_goods_total = unit_price * qty_total
    amount_shipping_total = calc_shipping_fee(
        mode=getattr(offer, "shipping_mode", None),
        fee_per_reservation=getattr(offer, "shipping_fee_per_reservation", 0),
        fee_per_qty=getattr(offer, "shipping_fee_per_qty", 0),
        qty=qty_total,
    )
    amount_paid_total = amount_goods_total + amount_shipping_total

    try:
        refunded_amount_total = int(getattr(resv, "refunded_amount_total", 0) or 0)
    except Exception:
        refunded_amount_total = 0

    # 3) PAID 상태가 아니거나, 환불 가능한 수량이 없으면 → 그냥 요약만 반환
    if resv.status != ReservationStatus.PAID or refundable_qty <= 0:
        return ReservationRefundSummary(
            reservation_id=resv.id,
            status=resv.status,
            qty=qty_total,
            refunded_qty=already_refunded,
            refundable_qty=0,
            unit_price=unit_price,
            amount_goods_total=amount_goods_total,
            amount_shipping_total=amount_shipping_total,
            amount_paid_total=amount_paid_total,
            refunded_amount_total=refunded_amount_total,
            refundable_amount_max=0,
        )

    # 4) 남은 수량 전체에 대해 "최대 환불 가능 금액" 계산
    #    → preview_refund_for_paid_reservation 한 번 호출
    ctx, _decision = preview_refund_for_paid_reservation(
        db,
        reservation_id=reservation_id,
        actor="buyer_cancel",      # 기본값 (필요하면 API에서 파라미터로 받게 바꿀 수 있음)
        quantity_refund=refundable_qty,
    )

    refundable_amount_max = int(ctx.amount_total or 0)

    return ReservationRefundSummary(
        reservation_id=resv.id,
        status=resv.status,
        qty=qty_total,
        refunded_qty=already_refunded,
        refundable_qty=refundable_qty,
        unit_price=unit_price,
        amount_goods_total=amount_goods_total,
        amount_shipping_total=amount_shipping_total,
        amount_paid_total=amount_paid_total,
        refunded_amount_total=refunded_amount_total,
        refundable_amount_max=refundable_amount_max,
    )


#------------------------------------------------
# Actuator 정산일 세팅 헬퍼 (Cooling + α days)
#------------------------------------------------

def mark_actuator_commissions_ready_for_reservation(
    db: Session,
    reservation: models.Reservation,
):
    """
    예약 기준으로 관련 ActuatorCommission들의 ready_at 을 세팅.

    - _compute_actuator_commission_ready_at_for_reservation() 를 사용해
      도착 기준일 + cooling_days + actuator_payout_after_cooling_days 를 계산.
    - status='PENDING' 이고 ready_at 이 아직 None 인 row 들만 업데이트.
    """
    # 이 예약과 연결된 커미션들 조회
    comms = (
        db.query(models.ActuatorCommission)
          .filter(models.ActuatorCommission.reservation_id == reservation.id)
          .all()
    )
    if not comms:
        return

    # 새 헬퍼로 ready_at 계산 (arrival_confirmed_at / delivered_at / paid_at 기반)
    ready_at = _compute_actuator_commission_ready_at_for_reservation(db, reservation)
    if not ready_at:
        # 기준일이 없거나, 정책상 계산이 안 되면 그냥 스킵
        return

    changed = False
    for comm in comms:
        if comm.status == "PENDING" and comm.ready_at is None:
            comm.ready_at = ready_at
            changed = True

    if changed:
        db.commit()



def confirm_reservation_arrival(
    db: Session,
    *,
    reservation_id: int,
    buyer_id: int,
    max_days_after: int = 30,
) -> models.Reservation:
    """
    바이어가 '도착 확인' 버튼 누르는 동작.
    - 상태는 PAID 여야 함.
    - buyer_id 본인만 가능.
    - shipped_at이 있어야 함.
    - arrival_confirmed_at은 최초 1회만 세팅.
    """
    resv = db.get(models.Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")

    # 본인 예약인지 검증
    if int(getattr(resv, "buyer_id", 0)) != int(buyer_id):
        raise ConflictError("not owned by buyer")

    # 상태 검증: 반드시 PAID 여야 함
    status_val = getattr(resv, "status", None)
    name = getattr(status_val, "name", None) or str(status_val)
    if name != "PAID":
        raise ConflictError(f"cannot confirm arrival: status={name}")

    # 배송 전에는 도착확인 불가
    if not resv.shipped_at:
        raise ConflictError("cannot confirm arrival before shipped")

    now = _utcnow()

    # 이미 도착확인 한 예약이면 그대로 반환 (idempotent)
    if resv.arrival_confirmed_at is not None:
        return resv

    # 도착확인 + 도착일 동시 세팅
    resv.arrival_confirmed_at = now
    resv.delivered_at = now

    # 🔁 액츄에이터 커미션 ready_at 세팅 시도
    try:
        mark_actuator_commissions_ready_for_reservation(db, resv)
    except Exception as e:
        # 커미션 쪽에서 에러나도, 도착확인 자체는 실패하지 않도록 방어
        logging.exception(
            "failed to mark actuator commissions ready_at for reservation %s",
            reservation_id,
            exc_info=e,
        )

    db.add(resv)
    db.commit()
    db.refresh(resv)
    return resv


#----------------------------------------
# Reservation 정산 스냅샷
#----------------------------------------
def create_settlement_for_paid_reservation(
    db: Session,
    *,
    reservation_id: int,
) -> models.ReservationSettlement | None:
    """
    결제(PAID)된 예약 1건에 대한 정산 스냅샷 생성.

    - Reservation.status 가 PAID 가 아니면 아무 것도 하지 않고 None 리턴
    - 이미 reservation_id 에 대한 settlement 가 있으면 그대로 리턴 (멱등)
    - 정산식:
        paid_amount      = offer.price * qty   (부포 기준)
        pg_fee_amount    = paid_amount * PG_FEE_RATE_BPS / 10000
        platform_fee     = paid_amount * platform_commission_rate_by_seller_level   (SSOT)
        platform_fee_vat = platform_fee * VAT_RATE_BPS / 10000
        seller_payout    = paid_amount - (pg_fee + platform_fee + vat)
    """
    # ✅ SSOT 정책 API (platform fee 계산)
    from app.policy import api as policy_api

    # 0) 예약 조회
    resv = db.get(Reservation, reservation_id)
    if not resv:
        return None

    # 상태 확인: PAID 가 아니면 스냅샷 안 만든다
    if resv.status != ReservationStatus.PAID:
        return None

    # 이미 settlement 가 있으면 재생성하지 않고 그대로 리턴 (멱등)
    existing = (
        db.query(ReservationSettlement)
        .filter(ReservationSettlement.reservation_id == resv.id)
        .first()
    )
    if existing:
        return existing

    # 1) 오퍼 조회 (가격, 셀러)
    offer = db.get(Offer, resv.offer_id)
    if not offer:
        return None

    unit_price = int(getattr(offer, "price", 0) or 0)
    qty = int(getattr(resv, "qty", 0) or 0)
    if unit_price <= 0 or qty <= 0:
        return None

    paid_amount = unit_price * qty  # BUYER 결제금액(부포 기준)

    # 2) 수수료/세금 계산 (✅ 전부 Policy(YAML) 기반, rate 단위)
    # - pg_fee_rate: 0.033 (3.3%)
    # - platform fee: seller level 기반 (예: Lv.6 -> 0.035)
    # - vat_rate: 0.10 (10%)

    # ✅ 정산 계산은 전부 policy/api.py “한 방 함수”로 이동
    seller = db.get(models.Seller, offer.seller_id) if getattr(offer, "seller_id", None) else None
    level_int = int(getattr(seller, "level", 6) or 6) if seller else 6
    level_str = f"Lv.{level_int}"

    snap = policy_api.calc_settlement_snapshot(paid_amount=paid_amount, level_str=level_str)

    pg_fee_amount = int(snap["pg_fee_amount"])
    platform_fee = int(snap["platform_fee"])
    platform_fee_vat = int(snap["platform_fee_vat"])
    seller_payout = int(snap["seller_payout"])

    now = datetime.now(timezone.utc)

    settlement = ReservationSettlement(
        reservation_id=resv.id,
        seller_id=offer.seller_id,
        paid_amount=paid_amount,
        pg_fee_amount=pg_fee_amount,
        platform_fee=platform_fee,
        platform_fee_vat=platform_fee_vat,
        seller_payout=seller_payout,
        calc_at=now,
        status="PENDING",
    )

    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement

# -------------------------
# 정산 스냅샷 핼퍼
#-----------------------------

def create_or_update_settlement_for_reservation(db: Session, resv: Reservation) -> ReservationSettlement:
    """
    Reservation(보통 PAID 상태)을 기준으로
    ReservationSettlement 스냅샷을 생성 또는 갱신한다.
    """
    # 기본 방어
    if not resv:
        raise ValueError("Reservation is required")

    offer: Offer | None = db.get(Offer, resv.offer_id)
    if not offer:
        raise ValueError(f"Offer not found for reservation {resv.id}")

    # 1) 결제 금액 계산 (단위: 원)
    unit_price = int(getattr(offer, "price", 0) or 0)
    qty = int(getattr(resv, "qty", 0) or 0)
    paid_amount = unit_price * qty

    if paid_amount <= 0:
        raise ValueError(f"Invalid paid_amount for reservation {resv.id}: {paid_amount}")

    # 2) 수수료율 세팅
    pg_rate = float(getattr(R, "PG_FEE_RATE", 0.0) or 0.0)
    platform_rate = float(getattr(R, "PLATFORM_FEE_RATE", 0.0) or 0.0)
    vat_rate = float(getattr(R, "VAT_RATE", 0.1) or 0.1)

    # 3) 금액 계산
    pg_fee_amount = int(round(paid_amount * pg_rate))
    platform_fee = int(round(paid_amount * platform_rate))
    platform_fee_vat = int(round(platform_fee * vat_rate))

    seller_payout = paid_amount - pg_fee_amount - platform_fee - platform_fee_vat
    if seller_payout < 0:
        seller_payout = 0  # 이론상 나오면 안 되지만 방어적으로 0으로 보정

    # 4) 기존 settlement 있는지 확인
    settlement = (
        db.query(ReservationSettlement)
        .filter(ReservationSettlement.reservation_id == resv.id)
        .first()
    )

    now = datetime.now(timezone.utc)

    if settlement is None:
        settlement = ReservationSettlement(
            reservation_id=resv.id,
            seller_id=offer.seller_id,
            paid_amount=paid_amount,
            pg_fee_amount=pg_fee_amount,
            platform_fee=platform_fee,
            platform_fee_vat=platform_fee_vat,
            seller_payout=seller_payout,
            calc_at=now,
            status="PENDING",
        )
        db.add(settlement)
    else:
        # 재계산(멱등) — 값이 바뀌었을 때 갱신
        settlement.paid_amount = paid_amount
        settlement.pg_fee_amount = pg_fee_amount
        settlement.platform_fee = platform_fee
        settlement.platform_fee_vat = platform_fee_vat
        settlement.seller_payout = seller_payout
        settlement.calc_at = now
        # status 는 여기서는 건드리지 않음 (이미 READY/PAID 일 수 있음)

    db.flush()
    db.refresh(settlement)
    return settlement



def cancel_settlement_for_reservation(db: Session, reservation_id: int) -> None:
    """
    예약 취소/환불 시 해당 ReservationSettlement 를 취소 상태로 마킹.
    """
    settlement = (
        db.query(ReservationSettlement)
        .filter(ReservationSettlement.reservation_id == reservation_id)
        .first()
    )
    if not settlement:
        return

    settlement.status = "CANCELLED"
    settlement.seller_payout = 0
    db.add(settlement)
    db.flush()


# ===== 셀러 확정/철회 =====
def seller_confirm_offer(
    db: Session,
    *,
    offer_id: int,
    force: bool = False,
    award_on_full: int = 30
) -> Offer:
    """
    - force=False: 전량 판매 AND PENDING 0건일 때만 확정(+포인트)
    - force=True : 전량 미달이어도 확정(포인트 없음)
    - ✅ 오퍼가 처음으로 확정되는 순간, 해당 셀러를 데려온 Actuator에게 알림 발송
    """
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    total = int(offer.total_available_qty or 0)
    sold  = int(offer.sold_qty or 0)

    pending_cnt = db.query(func.count(Reservation.id)).filter(
        Reservation.offer_id == offer_id,
        Reservation.status == ReservationStatus.PENDING
    ).scalar() or 0

    if not force:
        if sold < total:
            raise ConflictError("offer not fully sold; cannot confirm")
        if pending_cnt > 0:
            raise ConflictError("cannot confirm while PENDING reservations exist")

    # 이전에 이미 확정된 오퍼면, 포인트/알림 아무 것도 하지 않고 바로 반환
    if offer.is_confirmed:
        return offer

    # 1) 확정 플래그 + (필요하면) 셀러 포인트 지급
    offer.is_confirmed = True
    db.add(offer)

    if not force and award_on_full:
        _add_points(
            db,
            user_type="seller",
            user_id=offer.seller_id,
            amount=award_on_full,
            reason=f"offer {offer.id} confirmed",
            idempotency_key=f"pt:seller:confirm:{offer.id}",
        )

    db.commit()
    db.refresh(offer)
    
    # ---------------------------------------------------------
    # ✅ Evidence Pack: offer_confirm_v1 (SSOT)
    #    - "처음 확정되는 순간"에만 1회 기록
    #    - 알림/포인트 등 부가효과와 분리: 로그는 여기서 먼저 남김
    # ---------------------------------------------------------
    try:
        from app.routers.activity_log import log_event
        from app.pingpong.evidence.build_evidence_pack_v0 import build_evidence_pack_v0

        # before 스냅샷 (필요한 최소만)
        before_snapshot = {
            "is_confirmed": False,  # 이 함수는 위에서 is_confirmed면 return 했으므로 여기선 False가 맞음
        }

        evidence_pack = build_evidence_pack_v0(
            db,
            kind="offer_confirm_v1",
            payload={
                "offer": offer,
                "actor": ("admin_force_confirm" if force else "seller_confirm"),
                "force": bool(force),
                "award_on_full": int(award_on_full or 0),
                "before": before_snapshot,
                "run_id": None,
                "request_id": None,
                "notes": [],
            },
        )

        # event_type은 64자 제한이 있으니 짧게 유지
        log_event(
            db,
            event_type="evidence_pack.offer_confirm_v1",
            actor_type="SYSTEM",
            actor_id=None,
            seller_id=getattr(offer, "seller_id", None),
            deal_id=getattr(offer, "deal_id", None),
            offer_id=getattr(offer, "id", None),
            meta=evidence_pack,
            # 멱등키(재실행/중복 방지). activity_log.py의 /log API는 멱등 처리하지만
            # log_event()는 자체 중복체크 안하니, 관례로 넣어두면 좋음.
            idempotency_key=f"evidence:offer_confirm_v1:offer:{getattr(offer, 'id', 0)}",
        )
    except Exception:
        # evidence 실패가 본 흐름을 깨면 안됨
        pass

 
    # 2) 🔔 Actuator 알림: “추천한 셀러의 오퍼가 확정되었어요”
    try:
        # seller → actuator_id 찾아서 알림
        seller = db.get(Seller, offer.seller_id) if offer.seller_id else None
        if seller:
            actuator_id = int(getattr(seller, "actuator_id", 0) or 0)
        else:
            actuator_id = 0

        if actuator_id > 0:
            create_notification(
                db,
                user_id=actuator_id,
                type="offer_confirmed_by_seller",
                title="추천한 셀러의 오퍼가 확정되었어요",
                message=(
                    f"추천하신 셀러 #{getattr(seller, 'id', offer.seller_id)} "
                    f"({getattr(seller, 'name', '')}) 의 오퍼 #{offer.id}가 확정되었습니다. "
                    f"(딜 #{offer.deal_id})"
                ),
                meta={
                    "role": "actuator",
                    "seller_id": getattr(seller, "id", offer.seller_id),
                    "offer_id": offer.id,
                    "deal_id": offer.deal_id,
                },
            )
    except Exception as notify_err:
        # 알림 실패로 오퍼 확정 자체가 깨지면 안 되므로, 로그만 남기고 무시
        logging.exception(
            "failed to create actuator offer_confirmed notification",
            exc_info=notify_err,
        )

    return offer


def _get_settlement_state_for_reservation(db: Session, resv: Reservation) -> SettlementState:
    """
    ✅ v1: 아주 심플한 버전
    - Settlement 테이블이 있다면 reservation_id 기준으로 찾고 상태를 매핑
    - 아직 정교하게 안 해도 되고, 일단 NOT_SETTLED / SETTLED_TO_SELLER 만 구분
    """

    # 1) Settlement 모델이 있다면, reservation_id 기반으로 조회
    #    => 네 스키마에 맞게 필드명/모델명 수정하기!
    SettlementModel = getattr(models, "Settlement", None)
    if SettlementModel is None:
        # 아직 Settlement 모델 안 붙였으면 그냥 NOT_SETTLED 로 가정
        return SettlementState.NOT_SETTLED

    row = (
        db.query(SettlementModel)
          .filter(SettlementModel.reservation_id == resv.id)
          .order_by(SettlementModel.id.desc())
          .first()
    )

    if row is None:
        return SettlementState.NOT_SETTLED

    # 예시: row.status 가 "PAID_TO_SELLER" 같은 enum/문자라고 가정
    raw_status = getattr(row, "status", None)
    name = getattr(raw_status, "name", None) or str(raw_status)
    name_upper = name.upper()

    # 네가 실제 사용하는 정산 상태 값에 맞춰서 수정하면 됨
    if name_upper in {"PAID", "PAID_TO_SELLER", "SETTLED"}:
        return SettlementState.SETTLED_TO_SELLER

    # 그 외에는 아직 정산 안 된 걸로 처리
    if name_upper in {"PENDING", "READY", "REQUESTED"}:
        return SettlementState.NOT_SETTLED

    # 모르는 값이면 방어적으로 UNKNOWN
    return SettlementState.UNKNOWN


def _resolve_cooling_days_for_reservation(db: Session, resv: Reservation) -> tuple[int, str]:
    """
    cooling_days SSOT resolver.

    우선순위(SSOT 철학):
      1) reservation.policy_id -> offer_policies.cancel_within_days
      2) reservation.offer_id  -> offer_policies.cancel_within_days
      3) app.policy.api.cooling_days()
      4) DEFAULT_COOLING_DAYS (최후 안전 fallback)

    Returns:
      (cooling_days, source_tag)
    """
    # 0) 최후 fallback
    try:
        from app.core.refund_policy import DEFAULT_COOLING_DAYS
        default_days = int(DEFAULT_COOLING_DAYS)
    except Exception:
        default_days = 7  # 정말 최후의 최후 안전값

    # 1) reservation.policy_id 우선
    try:
        pid = getattr(resv, "policy_id", None)
        if pid:
            row = (
                db.query(models.OfferPolicy)
                .filter(models.OfferPolicy.id == int(pid))
                .first()
            )
            if row is not None:
                v = int(getattr(row, "cancel_within_days", 0) or 0)
                if v > 0:
                    return v, "offer_policy_by_policy_id"
    except Exception:
        pass

    # 2) offer_id로 조회(옵션B 기본)
    try:
        oid = getattr(resv, "offer_id", None)
        if oid:
            row = (
                db.query(models.OfferPolicy)
                .filter(models.OfferPolicy.offer_id == int(oid))
                .first()
            )
            if row is not None:
                v = int(getattr(row, "cancel_within_days", 0) or 0)
                if v > 0:
                    return v, "offer_policy_by_offer_id"
    except Exception:
        pass

    # 3) 전역 정책 fallback
    try:
        from app.policy.api import cooling_days as _policy_cooling_days
        v = int(_policy_cooling_days() or 0)
        if v > 0:
            return v, "global_policy_time.cooling_days"
    except Exception:
        pass

    # 4) 최후 fallback
    return default_days, "DEFAULT_COOLING_DAYS"



def _get_cooling_state_for_reservation(db: Session, resv: Reservation) -> CoolingState:
    """
    Reservation 의 배송/도착 타임스탬프를 기반으로 CoolingState 를 계산한다.

    ✅ cooling_days 우선순위(옵션 B):
      1) reservation.policy_snapshot_json (있으면 그 안에서)
      2) reservation.policy_id -> offer_policies.cancel_within_days
      3) offer_policies (offer_id 기준)
      4) TIME_POLICY.cooling_days fallback
    """
    cooling_days = None

    # 1) policy_snapshot_json 우선 (예약 시점에 합의된 스냅샷이 있으면 그게 SSOT)
    snap = getattr(resv, "policy_snapshot_json", None)
    if snap:
        try:
            import json
            d = json.loads(snap) if isinstance(snap, str) else (snap or {})
            for k in ("cooling_days", "cancel_within_days", "cancelWithinDays"):
                if k in d and d[k] is not None:
                    cooling_days = int(d[k])
                    break
            if cooling_days is None and isinstance(d.get("time"), dict):
                for k in ("cooling_days", "cancel_within_days"):
                    if k in d["time"] and d["time"][k] is not None:
                        cooling_days = int(d["time"][k])
                        break
        except Exception:
            cooling_days = None


    # 2) reservation.policy_id 로 offer_policies 조회
    if cooling_days is None:
        pid = getattr(resv, "policy_id", None)
        if pid:
            row = (
                db.query(models.OfferPolicy)
                .filter(models.OfferPolicy.id == pid)
                .first()
            )
            if row is not None:
                v = getattr(row, "cancel_within_days", None)
                # ✅ None이면 아직 못 정한 것 -> 그대로 None 유지해서 다음 fallback으로 넘긴다
                if v not in (None, 0):
                    cooling_days = int(v)

    # 3) offer_id 로 offer_policies 조회 (옵션 B 기본)
    if cooling_days is None:
        oid = getattr(resv, "offer_id", None)
        if oid:
            row = (
                db.query(models.OfferPolicy)
                .filter(models.OfferPolicy.offer_id == oid)
                .first()
            )
            if row is not None:
                v = getattr(row, "cancel_within_days", None)
                if v not in (None, 0):
                    cooling_days = int(v)

    # 4) 전역 fallback (policy / TIME_POLICY)
    if cooling_days is None:
        try:
            from app.policy.api import cooling_days as _global_cooling_days
            cooling_days = int(_global_cooling_days())
        except Exception:
            cooling_days = int(getattr(TIME_POLICY, "cooling_days", 0) or 0)


# ---------------------------------------------------------------------------
# 환불 정책 미리 보기용 헬퍼
# ---------------------------------------------------------------------------

def preview_refund_policy_for_reservation(
    db: Session,
    *,
    reservation_id: int,
    actor: str = "buyer_cancel",
) -> dict:
    """
    실제 환불(상태/포인트 변경) 없이,
    RefundContext + RefundDecision 만 계산해서 반환하는 진단용 함수.

    내부적으로 preview_refund_for_paid_reservation(...) 를 그대로 호출하므로,
    금액/배송비/쿨링/정산 로직이 완전히 동일하게 유지된다.
    """
    ctx, decision = preview_refund_for_paid_reservation(
        db,
        reservation_id=reservation_id,
        actor=actor,
    )

    return {
        "reservation_id": reservation_id,
        "actor": actor,
        "context": asdict(ctx),
        "decision": asdict(decision),
    }


def seller_cancel_offer(
    db: Session,
    *,
    offer_id: int,
    penalize: bool = False,
    allow_paid: bool = False,
    reverse_buyer_points: bool = False,
    buyer_point_per_qty: int = 0,
) -> Offer:
    """
    v3.6 기준 셀러 오퍼 취소 로직

    - allow_paid = False 인데 PAID 예약이 하나라도 있으면 → 409
    - allow_paid = True 이면:
        - PENDING 예약: cancel_reservation() 재사용 (재고 복구 + 상태 CANCELLED)
        - PAID 예약: refund_paid_reservation() 재사용 (환불 + 포인트 롤백 + 상태 CANCELLED)

    ✅ 중요한 점:
    - 예약 레코드를 삭제하지 않고, 상태만 CANCELLED 로 남겨서
      /reservations/by-id/{id} 로 항상 조회 가능하게 유지
    """
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    # 이 오퍼에 매달린 모든 예약 조회
    resvs: list[Reservation] = (
        db.query(Reservation)
        .filter(Reservation.offer_id == offer_id)
        .all()
    )

    # PAID 예약 존재 여부 체크
    has_paid = any(r.status == ReservationStatus.PAID for r in resvs)
    if has_paid and not allow_paid:
        # 기존 bad_flow_seller_cancel_offer_v36.py 가 기대하던 메시지와 맞춤
        raise ConflictError("cannot cancel offer: has PAID reservations (set allow_paid=True to force)")

    # 각 예약 상태에 따라 적절한 CRUD 함수 호출
    for r in resvs:
        # 1) 결제 전 예약(PENDING) → 단순 취소(재고 복구)
        if r.status == ReservationStatus.PENDING:
            # buyer_id=None 으로 넣으면, cancel_reservation 내에서 소유자 체크는 스킵됨
            cancel_reservation(
                db,
                reservation_id=r.id,
                buyer_id=None,
            )

        # 2) 결제 완료 예약(PAID) → 환불(+포인트 롤백 포함)
        elif r.status == ReservationStatus.PAID and allow_paid:
            # 이미 v3.5 에서 쓰던 환불 로직 재사용
            # actor 는 나중에 정책 보고 바꿔도 됨
            refund_paid_reservation(
                db,
                reservation_id=r.id,
                actor="seller_cancel_offer",
            )

        # 그 외 상태(CANCELLED/EXPIRED 등)는 그대로 둠
        else:
            continue

    # 위에서 cancel_reservation / refund_paid_reservation 이 각각 commit 을 했을 수 있으니
    # 오퍼 객체를 최신 상태로 리프레시
    db.refresh(offer)

    now = _utcnow()

    # 오퍼 비활성화 + 의사결정 상태 기록
    offer.is_active = False
    try:
        # Enum 사용 (문자열 "CANCELLED" 금지!)
        offer.decision_state = OfferDecisionState.WITHDRAWN
    except Exception:
        # 혹시 Enum 매핑 문제 있을 경우를 위한 안전장치
        offer.decision_state = OfferDecisionState.PENDING
    offer.decision_made_at = now
    offer.decision_reason = "seller_cancel_offer"

    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer



def seller_decide_withdraw_or_confirm(db: Session, *, offer_id: int, action: str) -> Offer:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    total = int(offer.total_available_qty or 0)
    sold  = int(offer.sold_qty or 0)
    full_sell = (total > 0 and sold >= total)

    now = _utcnow()
    decision_deadline = getattr(offer, "decision_deadline_at", None)
    if decision_deadline and now > decision_deadline:
        return seller_cancel_offer(db, offer_id=offer_id, penalize=False, allow_paid=True)

    action = action.lower()
    if full_sell:
        if action != "confirm":
            raise ConflictError("FULL_SELL: withdraw not allowed; must confirm")
        return seller_confirm_offer(db, offer_id=offer_id, force=False, award_on_full=30)

    if action == "withdraw":
        return seller_cancel_offer(db, offer_id=offer_id, penalize=True, allow_paid=True)
    if action == "confirm":
        return seller_confirm_offer(db, offer_id=offer_id, force=True, award_on_full=0)

    raise ConflictError("Unknown seller action")

# (하위호환)
def confirm_offer_if_soldout(db: Session, *, offer_id: int, seller_point_on_confirm: int = 30) -> Offer:
    return seller_confirm_offer(db, offer_id=offer_id, force=False, award_on_full=seller_point_on_confirm)

def get_offer_snapshot(db: Session, offer_id: int) -> dict:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    pending_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.PENDING
    ).scalar() or 0
    paid_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.PAID
    ).scalar() or 0
    cancelled_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.CANCELLED
    ).scalar() or 0
    expired_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.EXPIRED
    ).scalar() or 0

    model_reserved = int(offer.reserved_qty or 0)
    model_sold     = int(offer.sold_qty or 0)
    remaining = int(offer.total_available_qty or 0) - model_sold - model_reserved

    return {
        "offer_id": offer.id,
        "total_available_qty": int(offer.total_available_qty or 0),
        "reserved_qty(model)": model_reserved,
        "sold_qty(model)": model_sold,
        "remaining": remaining,
        "pending_qty(sum_reservations)": int(pending_qty),
        "paid_qty(sum_reservations)": int(paid_qty),
        "cancelled_qty(sum_reservations)": int(cancelled_qty),
        "expired_qty(sum_reservations)": int(expired_qty),
        "is_confirmed": bool(offer.is_confirmed),
        "is_active": bool(offer.is_active),
        "deadline_at": offer.deadline_at,
        "created_at": offer.created_at,
    }

def resync_offer_counters(db: Session, offer_id: int) -> dict:
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    pending_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.PENDING
    ).scalar() or 0
    paid_qty = db.query(func.coalesce(func.sum(Reservation.qty), 0)).filter(
        Reservation.offer_id == offer_id, Reservation.status == ReservationStatus.PAID
    ).scalar() or 0

    offer.reserved_qty = int(pending_qty)
    offer.sold_qty     = int(paid_qty)
    db.add(offer)
    db.commit()

    return get_offer_snapshot(db, offer_id)

def update_offer_total_qty(
    db: Session,
    offer_id: int,
    *,
    total_available_qty: int,
    allow_unconfirm_on_increase: bool = True,
) -> Offer:
    """
    오퍼 총 공급량 변경.
    - 현재 sold + reserved 보다 작게 내릴 수 없음(409)
    - 총량을 '증가'시키는 경우 allow_unconfirm_on_increase=True면 자동 비확정 처리
    """
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError(f"Offer not found: {offer_id}")
    if total_available_qty < 0:
        raise ConflictError("total_available_qty must be >= 0")

    sold = int(offer.sold_qty or 0)
    reserved = int(offer.reserved_qty or 0)
    min_required = sold + reserved
    if total_available_qty < min_required:
        raise ConflictError(f"total_available_qty too small (min={min_required})")

    old_total = int(offer.total_available_qty or 0)
    increasing = total_available_qty > old_total

    # 증가 시 확정 자동 해제(옵션)
    if allow_unconfirm_on_increase and increasing and getattr(offer, "is_confirmed", False):
        offer.is_confirmed = False
        # 결정 상태 초기화(존재하면)
        for attr in ("decision_state", "decision_made_at", "decision_reason"):
            if hasattr(offer, attr):
                setattr(offer, attr, None)

    # 실제 총량 업데이트
    offer.total_available_qty = int(total_available_qty)

    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer

# ===== 조회 유틸
def get_reservation(db: Session, reservation_id: int) -> Reservation:
    obj = db.get(Reservation, reservation_id)
    if not obj:
        raise NotFoundError(f"Reservation not found: {reservation_id}")
    return obj
        
# ----------------------------------------------------
# OfferPolicy CRUD
# ----------------------------------------------------

def get_offer_policy(db: Session, offer_id: int) -> models.OfferPolicy | None:
    """
    해당 오퍼(offer_id)에 연결된 정책 1건 조회 (없으면 None)
    """
    return (
        db.query(models.OfferPolicy)
        .filter(models.OfferPolicy.offer_id == offer_id)
        .first()
    )


def upsert_offer_policy(
    db: Session,
    *,
    offer_id: int,
    data: schemas.OfferPolicyCreate,
) -> models.OfferPolicy:
    """
    OfferPolicy upsert:
    - 이미 있으면 update
    - 없으면 create
    """
    policy = (
        db.query(models.OfferPolicy)
        .filter(models.OfferPolicy.offer_id == offer_id)
        .first()
    )

    if policy is None:
        policy = models.OfferPolicy(
            offer_id=offer_id,
            cancel_rule=data.cancel_rule,
            cancel_within_days=data.cancel_within_days,
            extra_text=data.extra_text,
        )
        db.add(policy)
    else:
        policy.cancel_rule = data.cancel_rule
        policy.cancel_within_days = data.cancel_within_days
        policy.extra_text = data.extra_text

    db.commit()
    db.refresh(policy)
    return policy


#-----------------------------------
# Offer에서 환불정책 Snapshot
#-----------------------------------

def make_policy_snapshot(policy: Optional[models.OfferPolicy]) -> Optional[str]:
    """
    OfferPolicy ORM 객체를 JSON 문자열로 스냅샷.
    Reservation.policy_snapshot_json 에 저장할 용도.
    """
    if policy is None:
        return None

    try:
        data: Dict[str, Any] = {
            "id": policy.id,
            "offer_id": policy.offer_id,
            "cancel_rule": policy.cancel_rule,
            "cancel_within_days": policy.cancel_within_days,
            "extra_text": policy.extra_text,
            "created_at": (
                policy.created_at.isoformat()
                if getattr(policy, "created_at", None)
                else None
            ),
        }
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        # 실패해도 예약 자체는 막지 않기 위해
        return None



# ========= v3.5 전용 보강: 고정 포인트(+20 / -20) =========
def pay_reservation_v35(db: Session, *, reservation_id: int, buyer_id: int) -> Reservation:
    resv = db.get(Reservation, reservation_id)
    if not resv:
        raise NotFoundError("Reservation not found")

    now = _utcnow()

    # 1) 결제 만료 체크
    if resv.expires_at:
        expires_at_utc = _as_utc(resv.expires_at)
        if expires_at_utc and expires_at_utc < now:
            raise ConflictError("reservation expired")

    # 2) (옵션) 방장 우선권 가드
    deal = db.get(Deal, resv.deal_id) if resv.deal_id else None
    host_id = getattr(deal, "host_buyer_id", None)
    if host_id is not None:
        host_window_end = resv.created_at + timedelta(minutes=TIME_POLICY.host_priority_minutes)
        host_window_end_utc = _as_utc(host_window_end)
        if host_window_end_utc and now <= host_window_end_utc and buyer_id != host_id:
            raise ConflictError("host-only payment window")

    # 3) 상태/소유자 가드
    if resv.status != ReservationStatus.PENDING:
        raise ConflictError(f"cannot pay: status={resv.status}")
    if resv.buyer_id != buyer_id:
        raise ConflictError("not owned by buyer")

    offer = db.get(Offer, resv.offer_id)
    if not offer:
        raise NotFoundError("Offer not found")

    # -------------------------------------------------
    # ✅ 결제 금액 SSOT = Reservation.amount_total
    #   - 예약 생성 시점에 저장된 스냅샷이 원칙
    #   - 단, (0/음수/비정상)인 경우만 계산값으로 백필
    # -------------------------------------------------
    from app.core.shipping_policy import calc_shipping_fee
    from app.routers.activity_log import log_event

    qty = int(getattr(resv, "qty", 0) or 0)
    if qty <= 0:
        raise ConflictError("reservation qty must be positive")

    unit_price = int(getattr(offer, "price", 0) or 0)

    calc_goods = unit_price * qty
    calc_shipping = int(
        calc_shipping_fee(
            mode=getattr(offer, "shipping_mode", None),
            fee_per_reservation=getattr(offer, "shipping_fee_per_reservation", 0),
            fee_per_qty=getattr(offer, "shipping_fee_per_qty", 0),
            qty=qty,
        ) or 0
    )
    if calc_shipping < 0:
        calc_shipping = 0
    calc_total = int(calc_goods + calc_shipping)

    db_goods = int(getattr(resv, "amount_goods", 0) or 0)
    db_shipping = int(getattr(resv, "amount_shipping", 0) or 0)
    db_total = int(getattr(resv, "amount_total", 0) or 0)

    snapshot_mismatch = (db_goods != calc_goods) or (db_shipping != calc_shipping) or (db_total != calc_total)

    backfilled = False
    if db_total <= 0 or db_goods < 0 or db_shipping < 0:
        resv.amount_goods = calc_goods
        resv.amount_shipping = calc_shipping
        resv.amount_total = calc_total
        backfilled = True

        db_goods = int(resv.amount_goods or 0)
        db_shipping = int(resv.amount_shipping or 0)
        db_total = int(resv.amount_total or 0)

    amount_total = int(db_total or 0)
    if amount_total <= 0:
        raise ConflictError("payment amount must be positive")

    # -------------------------------------------------
    # 🧾 PG 결제 호출 (현재는 더미 구현)
    # -------------------------------------------------
    pg_req = PgPayRequest(
        pg_transaction_id=None,
        merchant_uid=f"reservation:{resv.id}",
        amount=amount_total,
        reservation_id=resv.id,
        buyer_id=resv.buyer_id,
        payment_method=None,
        installment_months=None,
    )

    pg_result = request_pg_pay(pg_req)

    if not pg_result.success:
        logging.error(
            "[pay_reservation_v35] PG pay failed: code=%s, msg=%s, resv_id=%s",
            pg_result.pg_error_code,
            pg_result.pg_error_message,
            resv.id,
        )
        raise ConflictError("PG payment failed")

    if hasattr(resv, "pg_transaction_id") and getattr(pg_result, "pg_transaction_id", None):
        try:
            resv.pg_transaction_id = pg_result.pg_transaction_id
        except Exception:
            logging.exception("failed to set pg_transaction_id on reservation")

    if getattr(pg_result, "pg_approved_amount", None) is not None and pg_result.pg_approved_amount != amount_total:
        logging.warning(
            "[pay_reservation_v35] PG approved amount mismatch: pg=%s, local=%s, resv_id=%s",
            pg_result.pg_approved_amount,
            amount_total,
            resv.id,
        )

    # -------------------------------------------------
    # ✅ 재고 이동 + 상태 변경 + 포인트 적립(기존 유지)
    # -------------------------------------------------
    offer.reserved_qty = max(0, int(offer.reserved_qty or 0) - int(resv.qty or 0))
    offer.sold_qty = int(offer.sold_qty or 0) + int(resv.qty or 0)

    resv.status = ReservationStatus.PAID
    resv.paid_at = _utcnow()

    db.add(
        PointTransaction(
            user_type="buyer",
            user_id=resv.buyer_id,
            amount=int(R.BUYER_POINT_ON_PAID),
            reason=f"reservation {resv.id} paid (v3.5 fixed point)",
            created_at=_utcnow(),
        )
    )

    db.add(resv)
    db.add(offer)
    db.commit()
    db.refresh(resv)

    # ✅ 결제 스냅샷 로그(미스매치/백필/PG 승인금액)
    try:
        log_event(
            db,
            event_type="reservation.pay.snapshot.v35",
            entity_type="reservation",
            entity_id=resv.id,
            actor="system",
            metadata={
                "buyer_id": buyer_id,
                "qty": qty,

                "db_amount_goods": db_goods,
                "db_amount_shipping": db_shipping,
                "db_amount_total": db_total,

                "calc_amount_goods": calc_goods,
                "calc_amount_shipping": calc_shipping,
                "calc_amount_total": calc_total,

                "snapshot_mismatch": bool(snapshot_mismatch),
                "snapshot_backfilled": bool(backfilled),

                "pg_tid": getattr(pg_result, "pg_transaction_id", None),
                "pg_approved_amount": getattr(pg_result, "pg_approved_amount", None),
                "local_amount_total": amount_total,
            },
        )
    except Exception:
        pass

    # (기존 디버그 로그 유지)
    logger.info(
        "[pay_reservation_v35] paid resv_id=%s buyer_id=%s amount_total=%s pg_tid=%s",
        resv.id,
        resv.buyer_id,
        amount_total,
        getattr(pg_result, "pg_transaction_id", None),
    )

    try:
        import json
        print(
            "[pay_reservation_v35] paid",
            json.dumps(
                {
                    "reservation_id": resv.id,
                    "buyer_id": resv.buyer_id,
                    "amount_total": amount_total,
                    "pg_tid": getattr(pg_result, "pg_transaction_id", None),
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        pass

    return resv



def seller_withdraw_offer_v35(
    db: Session,
    *,
    offer_id: int,
    reason: str | None = None,
    penalize_seller: bool = True
) -> Offer:
    """
    v3.5 고정 포인트 준수 철회:
      1) 철회 직전 PAID 예약 목록 수집
      2) 내부 취소 로직 호출(+바이어 포인트 자동회수 비활성화)
      3) 각 예약에 대해 고정 -20 보정 트랜잭션 추가
    """
    offer = db.get(Offer, offer_id)
    if not offer:
        raise NotFoundError("Offer not found")
    if offer.is_confirmed:
        raise ConflictError("cannot cancel: already confirmed offer")

    paid_before: List[Reservation] = db.query(Reservation).filter(
        Reservation.offer_id == offer_id,
        Reservation.status == ReservationStatus.PAID
    ).all()

    offer = seller_cancel_offer(
        db,
        offer_id=offer_id,
        penalize=penalize_seller,
        allow_paid=True,
        reverse_buyer_points=False,
    )

    if int(R.BUYER_POINT_ON_REFUND) != 0:
        now = _utcnow()
        for r in paid_before:
            db.add(PointTransaction(
                user_type="buyer",
                user_id=r.buyer_id,
                amount=int(R.BUYER_POINT_ON_REFUND),  # 보통 -20
                reason=f"refund after seller withdraw offer {offer_id} (reservation {r.id})",
                created_at=now,
            ))
        db.commit()

    if hasattr(offer, "decision_state"):
        offer.decision_state = "WITHDRAWN"
    if hasattr(offer, "decision_made_at"):
        offer.decision_made_at = _utcnow()
    if hasattr(offer, "decision_reason"):
        offer.decision_reason = reason or "seller_withdraw_v35"

    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer

def search_reservations(
    db: Session,
    *,
    reservation_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    offer_id: Optional[int] = None,
    buyer_id: Optional[int] = None,
    status: Optional[ReservationStatus] = None,
    after_id: Optional[int] = None,
    limit: int = 50,
) -> List[Reservation]:
    q = db.query(Reservation)
    if reservation_id is not None:
        q = q.filter(Reservation.id == reservation_id)
    if deal_id is not None:
        q = q.filter(Reservation.deal_id == deal_id)
    if offer_id is not None:
        q = q.filter(Reservation.offer_id == offer_id)
    if buyer_id is not None:
        q = q.filter(Reservation.buyer_id == buyer_id)
    if status is not None:
        q = q.filter(Reservation.status == status)
    if after_id is not None:
        q = q.filter(Reservation.id < after_id)

    return q.order_by(Reservation.id.desc()).limit(max(1, min(200, int(limit or 50)))).all()



def _map_actor_to_fault_party(actor: Optional[str]) -> FaultParty:
    """
    Reservation 취소 요청시 들어오는 actor 문자열을
    RefundPolicy 에서 쓰는 FaultParty 로 매핑.
    """
    if not actor:
        return FaultParty.DISPUTE

    a = actor.lower()

    # 예: "buyer_cancel", "buyer_change_mind" ...
    if a.startswith("buyer"):
        return FaultParty.BUYER

    # 예: "seller_fault", "seller_cancel" ...
    if "seller" in a:
        return FaultParty.SELLER

    # 예: "admin_cancel", "system_cancel" ...
    if "admin" in a or "system" in a:
        return FaultParty.SYSTEM

    # 애매하면 분쟁으로 태깅
    return FaultParty.DISPUTE



def _log_refund_policy_for_paid_reservation(
    db: Session,
    resv: Reservation,
    *,
    actor: Optional[str],
) -> RefundDecision:
    """
    PAID → CANCELLED 되는 예약에 대해
    RefundPolicyEngine 을 호출하고, 결과를 로그로만 남기는 v1 헬퍼.

    실제 PG/정산/포인트 처리에는 아직 개입하지 않는다.
    """

    # 1) 정산 상태 태깅
    settlement_state = _get_settlement_state_for_reservation(db, resv)

    # 2) 쿨링타임 상태 태깅
    cooling_state = _get_cooling_state_for_reservation(db, resv)

    # 3) 귀책 주체 매핑
    fault_party = _map_actor_to_fault_party(actor)

    # 4) 금액 정보 (지금은 "상품금액만" 간단히 계산)
    offer = db.get(Offer, resv.offer_id) if resv.offer_id else None
    unit_price = int(getattr(offer, "price", 0) or 0)
    amount_goods = unit_price * int(resv.qty or 0)
    amount_shipping = 0  # v1: 배송비는 아직 정책에 안 넣고 0 으로 둠
    amount_total = amount_goods + amount_shipping

    # 5) 트리거 판별 (대충 actor 기준으로만)
    if fault_party == FaultParty.BUYER:
        trigger = RefundTrigger.BUYER_CANCEL
    elif fault_party == FaultParty.SELLER:
        trigger = RefundTrigger.SELLER_CANCEL
    elif fault_party == FaultParty.SYSTEM:
        trigger = RefundTrigger.SYSTEM_ERROR
    else:
        trigger = RefundTrigger.DISPUTE_RESOLVE

    ctx = RefundContext(
        reservation_id=resv.id,
        deal_id=resv.deal_id,
        offer_id=resv.offer_id,
        buyer_id=resv.buyer_id,
        seller_id=getattr(offer, "seller_id", None) if offer else None,
        amount_total=amount_total,
        amount_goods=amount_goods,
        amount_shipping=amount_shipping,
        quantity_total=int(resv.qty or 0),
        quantity_refund=int(resv.qty or 0),  # v1: 항상 전체 환불로 간주

        fault_party=fault_party,
        trigger=trigger,
        settlement_state=settlement_state,
        cooling_state=cooling_state,

        # 아직은 참고용 숫자만 (0.0)
        pg_fee_rate=0.0,
        platform_fee_rate=0.0,
    )

    decision = REFUND_POLICY_ENGINE.decide_for_paid_reservation(ctx)

    # 👉 일단은 "로그만" 남김 (실제 돈 움직이지 않음)
    logger.info(
        "[REFUND_POLICY] resv_id=%s fault=%s trigger=%s "
        "settlement=%s cooling=%s decision=%s",
        ctx.reservation_id,
        ctx.fault_party,
        ctx.trigger,
        ctx.settlement_state,
        ctx.cooling_state,
        decision,
    )

    return decision



# ---------------------------------------------------------
# 💰 Reservation 1건에 대한 정산 레코드 생성 헬퍼
# ---------------------------------------------------------
def create_settlement_for_reservation(db: Session, resv: Reservation) -> ReservationSettlement:
    """
    - 같은 reservation_id 로 이미 정산 레코드가 있으면 그대로 반환 (멱등성)
    - 없으면 새로 만들어서 저장 후 반환
    - 금액 계산:
        * buyer_paid_amount = offer.price * qty
        * pg_fee_amount = buyer_paid_amount * PG_FEE_RATE
        * platform_commission_amount = buyer_paid_amount * PLATFORM_FEE_RATE
        * seller_payout_amount = buyer_paid_amount - pg_fee_amount - platform_commission_amount
    """

    # 0) 이미 있으면 그대로 리턴 (멱등성 보장)
    existing = (
        db.query(ReservationSettlement)
        .filter(ReservationSettlement.reservation_id == resv.id)
        .first()
    )
    if existing:
        return existing

    # 1) 연관 Offer 조회
    offer = db.get(Offer, resv.offer_id)
    if not offer:
        raise ValueError(f"Offer not found for reservation_id={resv.id}")

    # 2) 기본 금액 계산
    qty = int(getattr(resv, "qty", 0) or 0)
    unit_price = int(getattr(offer, "price", 0) or 0)
    buyer_paid_amount = qty * unit_price

    # 방어: 금액이 0 이하면 정산 만들 필요 없음
    if buyer_paid_amount <= 0:
        raise ValueError(f"Invalid buyer_paid_amount={buyer_paid_amount} for reservation_id={resv.id}")

    # 3) 수수료율 (rules 에 없으면 기본값 사용)
    pg_fee_rate = float(getattr(R, "PG_FEE_RATE", 0.033))          # 3.3% 가정
    platform_fee_rate = float(getattr(R, "PLATFORM_FEE_RATE", 0.035))  # 3.5% 가정

    pg_fee_amount = int(round(buyer_paid_amount * pg_fee_rate))
    platform_commission_amount = int(round(buyer_paid_amount * platform_fee_rate))

    seller_payout_amount = buyer_paid_amount - pg_fee_amount - platform_commission_amount
    if seller_payout_amount < 0:
        seller_payout_amount = 0

    # 4) ReservationSettlement 인스턴스 생성
    settlement = ReservationSettlement(
        reservation_id=resv.id,
        deal_id=resv.deal_id,
        offer_id=resv.offer_id,
        seller_id=resv.offer.seller_id if getattr(resv, "offer", None) else offer.seller_id,
        buyer_id=resv.buyer_id,
        buyer_paid_amount=buyer_paid_amount,
        pg_fee_amount=pg_fee_amount,
        platform_commission_amount=platform_commission_amount,
        seller_payout_amount=seller_payout_amount,
        status="READY",
        currency="KRW",
    )

    db.add(settlement)
    db.commit()
    db.refresh(settlement)
    return settlement

#------------------------
# AI Event Log (AI분석/User선택 등 결과값의 로그를 남김)
#---------------------

def log_ai_event(
    db,
    *,
    endpoint: str,
    buyer_id: int | None,
    request: dict,
    response: dict | None,
    deal_id: int | None = None,
    note: str | None = None,
) -> None:
    """
    deal_ai_logs 테이블에 한 줄 INSERT.

    - request / response 는 dict로 받아서 JSON 문자열로 저장.
    - 에러가 나도 메인 로직은 망가지지 않도록 내부에서만 처리.
    """
    try:
        request_json = json.dumps(request, ensure_ascii=False)
        response_json = json.dumps(response, ensure_ascii=False) if response is not None else "{}"

        db.execute(
            text(
                """
                INSERT INTO deal_ai_logs (
                    endpoint,
                    buyer_id,
                    deal_id,
                    request_json,
                    response_json,
                    note
                )
                VALUES (
                    :endpoint,
                    :buyer_id,
                    :deal_id,
                    :request_json,
                    :response_json,
                    :note
                )
                """
            ),
            {
                "endpoint": endpoint,
                "buyer_id": buyer_id,
                "deal_id": deal_id,
                "request_json": request_json,
                "response_json": response_json,
                "note": note,
            },
        )
        db.commit()
    except Exception as e:
        print(f"[log_ai_event] ERROR: {e!r}")
        try:
            db.rollback()
        except Exception:
            pass

# ---------------------------------
# AI Deal Intent 관련 로그 유틸
# ---------------------------------

def log_deal_ai_resolve(
    db: Session,
    *,
    endpoint: str,
    buyer_id: int | None,
    deal_id: int | None,
    request_obj: dict | None,
    response_obj: dict | None,
    note: str | None = None,
) -> None:
    """
    /deals/ai/resolve_from_intent 등 AI 관련 호출을
    deal_ai_logs 테이블에 1줄씩 기록한다.
    """
    try:
        req_json = json.dumps(request_obj, ensure_ascii=False) if request_obj is not None else None
        res_json = json.dumps(response_obj, ensure_ascii=False) if response_obj is not None else None

        db.execute(
            text("""
                INSERT INTO deal_ai_logs (
                    endpoint, buyer_id, deal_id,
                    request_json, response_json, note
                )
                VALUES (:endpoint, :buyer_id, :deal_id, :request_json, :response_json, :note)
            """),
            {
                "endpoint": endpoint,
                "buyer_id": buyer_id,
                "deal_id": deal_id,
                "request_json": req_json,
                "response_json": res_json,
                "note": note,
            },
        )
        db.commit()
    except Exception as e:
        # 로그 때문에 본 기능이 망가지면 안 되니까 일단 찍기만
        print("[log_deal_ai_resolve] ERROR:", repr(e))
        db.rollback()
        

#-----------------------------------------
# 정책 조회 + 로그 저장
#________________________________________
def get_active_policies(
    db: Session,
    domains: List[str],
    *,
    limit_total: int = 40,
) -> List[models.PolicyDeclaration]:
    if not domains:
        return []

    q = (
        db.query(models.PolicyDeclaration)
        .filter(
            models.PolicyDeclaration.domain.in_(domains),
            models.PolicyDeclaration.is_active == True,  # noqa: E712
        )
        .order_by(models.PolicyDeclaration.domain.asc(), models.PolicyDeclaration.id.asc())
    )

    if limit_total and limit_total > 0:
        q = q.limit(limit_total)

    return q.all()


def log_pingpong(
    db: Session,
    *,
    user_id: Optional[int],
    role: Optional[str],
    locale: str,
    screen: str,
    deal_id: Optional[int],
    reservation_id: Optional[int],
    offer_id: Optional[int],
    mode: str,
    question: str,
    answer: str,
    used_policy_keys: List[str],
    used_policy_ids: List[int],
    actions: List[Dict[str, Any]],
    context: Dict[str, Any],
    request_payload: Dict[str, Any],
    response_payload: Dict[str, Any],
    llm_model: Optional[str] = None,
    latency_ms: Optional[int] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    try:
        row = models.PingpongLog(
            user_id=user_id,
            role=role,
            locale=locale or "ko",

            screen=screen,
            deal_id=deal_id,
            reservation_id=reservation_id,
            offer_id=offer_id,

            mode=mode,
            question=question,
            answer=answer,

            used_policy_keys_json=json.dumps(used_policy_keys or [], ensure_ascii=False),
            used_policy_ids_json=json.dumps(used_policy_ids or [], ensure_ascii=False),
            actions_json=json.dumps(actions or [], ensure_ascii=False),
            context_json=json.dumps(context or {}, ensure_ascii=False),
            request_json=json.dumps(request_payload or {}, ensure_ascii=False),
            response_json=json.dumps(response_payload or {}, ensure_ascii=False),

            llm_model=llm_model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,

            error_code=error_code,
            error_message=error_message,
        )
        db.add(row)
        db.commit()
    except Exception:
        db.rollback()


def log_pingpong_event(
    db: Session,
    *,
    user_id: Optional[int],
    role: Optional[str],
    screen: str,
    context: Dict[str, Any],
    question: str,
    answer: str,
    used_policy_keys: Optional[List[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    구버전/간단 호출 호환용 wrapper.
    내부적으로는 log_pingpong(상세 로그)을 사용한다.
    """
    meta = meta or {}
    raw_ctx = context or {}
    raw_context = raw_ctx.get("raw_context") or {}

    deal_id = raw_context.get("deal_id")
    reservation_id = raw_context.get("reservation_id")
    offer_id = raw_context.get("offer_id")

    log_pingpong(
        db,
        user_id=user_id,
        role=role,
        locale=meta.get("locale", "ko"),
        screen=screen,
        deal_id=deal_id,
        reservation_id=reservation_id,
        offer_id=offer_id,
        mode=meta.get("mode", "read_only"),
        question=question,
        answer=answer,
        used_policy_keys=used_policy_keys or [],
        used_policy_ids=[],
        actions=[],
        context=context,
        request_payload=meta.get("request_payload", {}),
        response_payload=meta.get("response_payload", {}),
        llm_model=meta.get("model"),
        latency_ms=meta.get("latency_ms"),
        prompt_tokens=meta.get("prompt_tokens"),
        completion_tokens=meta.get("completion_tokens"),
        error_code=meta.get("error_code"),
        error_message=meta.get("error_message"),
    )
    


# 공개 심볼
__all__ = [
    # errors
    "NotFoundError", "ConflictError",
    # buyers/sellers/deals/participants
    "create_buyer", "get_buyers",
    "create_seller", "get_sellers",
    "create_deal", "get_deal", "get_deals",
    "add_participant", "get_deal_participants", "remove_participant",
    # offers / points
    "create_offer", "get_offers", "confirm_offer_and_reward",
    "create_point_transaction", "get_point_transactions", "get_user_balance",
    # rounds
    "get_round_by_no", "list_rounds", "get_active_round",
    "create_deal_round", "get_or_create_next_round",
    "open_round", "finalize_round", "close_round", "cancel_round",
    "RoundAction", "progress_round",
    "assert_no_open_round", "ensure_round_exists",
    # reservations & offer life-cycle
    "get_offer_remaining_capacity",
    "create_reservation", "cancel_reservation", "expire_reservations",
    "pay_reservation", "refund_paid_reservation",
    "seller_confirm_offer", "seller_cancel_offer", "seller_decide_withdraw_or_confirm",
    "confirm_offer_if_soldout", "get_offer_snapshot", "resync_offer_counters", "update_offer_total_qty",
    "get_reservation", "search_reservations",
    # v3.5 helpers
    "pay_reservation_v35", "seller_withdraw_offer_v35",
]