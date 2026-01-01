# app/routers/activity_log.py
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict, List
import json
import hashlib

from fastapi import APIRouter, Depends, Query, Path, Body, status
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, Float, String, Text, DateTime, Index
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db

router = APIRouter(prefix="/activity", tags=["📜 Activity Log (NO-AUTH)"])


# ─────────────────────────────────────────────────────────
# ✅ Utilities
# ─────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _short_key(s: Optional[str], limit: int = 64) -> Optional[str]:
    """
    DB 컬럼 길이(64) 초과 방지.
    길면 앞부분 + sha1(16)로 축약.
    """
    if not s:
        return None
    s = str(s)
    if len(s) <= limit:
        return s
    h = hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]
    return s[: (limit - 17)] + ":" + h


def _apply_days_filter(q, days: Optional[int]):
    if days and days > 0:
        cutoff = _now() - timedelta(days=int(days))
        q = q.filter(ActivityLog.created_at >= cutoff)
    return q


# ─────────────────────────────────────────────────────────
# Model
# ─────────────────────────────────────────────────────────
class ActivityLog(Base):  # type: ignore
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    event_type = Column(String(64), nullable=False)  # 예: evidence, RESERVATION_PAID ...
    actor_type = Column(String(16), nullable=True)   # BUYER | SELLER | ADMIN | SYSTEM
    actor_id = Column(Integer, nullable=True)

    buyer_id = Column(Integer, nullable=True, index=True)
    seller_id = Column(Integer, nullable=True, index=True)
    deal_id = Column(Integer, nullable=True, index=True)
    offer_id = Column(Integer, nullable=True, index=True)
    reservation_id = Column(Integer, nullable=True, index=True)

    amount = Column(Float, nullable=True)  # 금액/포인트 등 수치
    qty = Column(Integer, nullable=True)   # 수량 등
    reason = Column(String(200), nullable=True)
    idempotency_key = Column(String(64), nullable=True, index=True)

    meta = Column(Text, nullable=True)  # JSON 문자열
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )


Index("ix_activity_event_type", ActivityLog.event_type)

# ✅ insights_overview 가 ActivityEvent 를 import 하는 경우를 위한 호환 별칭
ActivityEvent = ActivityLog

# (선택) 테이블이 아직 없을 수 있어 생성. 이미 있으면 no-op.
Base.metadata.create_all(bind=engine)


# ─────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────
class ActivityIn(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=64)
    actor_type: Optional[str] = Field(None, pattern="^(BUYER|SELLER|ADMIN|SYSTEM)?$")
    actor_id: Optional[int] = None

    buyer_id: Optional[int] = None
    seller_id: Optional[int] = None
    deal_id: Optional[int] = None
    offer_id: Optional[int] = None
    reservation_id: Optional[int] = None

    amount: Optional[float] = None
    qty: Optional[int] = None
    reason: Optional[str] = Field(None, max_length=200)
    idempotency_key: Optional[str] = Field(None, max_length=64)

    meta: Optional[Dict[str, Any]] = None


class ActivityOut(BaseModel):
    id: int
    event_type: str
    actor_type: Optional[str]
    actor_id: Optional[int]
    buyer_id: Optional[int]
    seller_id: Optional[int]
    deal_id: Optional[int]
    offer_id: Optional[int]
    reservation_id: Optional[int]
    amount: Optional[float]
    qty: Optional[int]
    reason: Optional[str]
    idempotency_key: Optional[str]
    meta: Optional[Dict[str, Any]]
    created_at: datetime


# ─────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────
def _to_out(row: ActivityLog) -> ActivityOut:
    meta_obj = None
    if row.meta:
        try:
            meta_obj = json.loads(row.meta)
        except Exception:
            meta_obj = None

    return ActivityOut(
        id=row.id,
        event_type=row.event_type,
        actor_type=row.actor_type,
        actor_id=row.actor_id,
        buyer_id=row.buyer_id,
        seller_id=row.seller_id,
        deal_id=row.deal_id,
        offer_id=row.offer_id,
        reservation_id=row.reservation_id,
        amount=row.amount,
        qty=row.qty,
        reason=row.reason,
        idempotency_key=row.idempotency_key,
        meta=meta_obj,
        created_at=row.created_at,
    )


def log_event(
    db: Session,
    *,
    event_type: str,
    actor_type: Optional[str] = None,
    actor_id: Optional[int] = None,
    buyer_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    offer_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
    amount: Optional[float] = None,
    qty: Optional[int] = None,
    reason: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> int:
    """
    ✅ 핵심 변경:
    - 기본은 commit=False (트랜잭션 깨지지 않게 flush만)
    - API에서는 commit=True로 호출
    """
    # 길이 가드
    event_type = (event_type or "").strip()
    if len(event_type) > 64:
        # event_type은 축약이 위험해서(분류가 깨짐) 강제로 해시 형태로 바꿈
        # (권장: event_type은 원래 짧게 쓰자)
        event_type = _short_key(event_type, 64) or "event"

    safe_idem = _short_key(idempotency_key, 64)

    row = ActivityLog(
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        deal_id=deal_id,
        offer_id=offer_id,
        reservation_id=reservation_id,
        amount=amount,
        qty=qty,
        reason=reason,
        idempotency_key=safe_idem,
        meta=json.dumps(meta or {}, ensure_ascii=False),
    )
    db.add(row)

    if commit:
        db.commit()
    else:
        db.flush()  # ✅ id 확보 / 트랜잭션 유지

    db.refresh(row)
    return int(row.id)


def log_evidence_pack(
    db: Session,
    *,
    evidence_pack_version: str,
    actor_type: str = "SYSTEM",
    actor_id: Optional[int] = None,
    buyer_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    deal_id: Optional[int] = None,
    offer_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Evidence Pack을 ActivityLog.meta에 저장하는 표준 함수(SSOT).
    - event_type: 항상 "evidence"
    - evidence 종류: meta["evidence_pack_version"] 로 구분
    """
    payload = dict(meta or {})
    payload.setdefault("evidence_pack_version", evidence_pack_version)

    return log_event(
        db,
        event_type="evidence",
        actor_type=actor_type,
        actor_id=actor_id,
        buyer_id=buyer_id,
        seller_id=seller_id,
        deal_id=deal_id,
        offer_id=offer_id,
        reservation_id=reservation_id,
        idempotency_key=idempotency_key,
        meta=payload,
    )
    
    
    
# ─────────────────────────────────────────────────────────
# API
# ─────────────────────────────────────────────────────────
@router.get("/ping")
def ping():
    return {"ok": True, "ts": _now().isoformat()}


@router.post("/log", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
def api_log_event(body: ActivityIn = Body(...), db: Session = Depends(get_db)):
    # 멱등키가 있으면 중복 방지
    if body.idempotency_key:
        exist = (
            db.query(ActivityLog)
            .filter(ActivityLog.idempotency_key == _short_key(body.idempotency_key, 64))
            .first()
        )
        if exist:
            return _to_out(exist)

    _id = log_event(db, **body.dict(), commit=True)
    row = db.query(ActivityLog).get(_id)  # type: ignore
    return _to_out(row)


@router.get("/recent", response_model=List[ActivityOut])
def recent(
    limit: int = Query(100, ge=1, le=500),
    after_id: Optional[int] = Query(None),
    days: Optional[int] = Query(None, ge=1, le=365, description="최근 N일만 조회"),
    db: Session = Depends(get_db),
):
    q = db.query(ActivityLog).order_by(ActivityLog.id.desc())
    if after_id:
        q = q.filter(ActivityLog.id < int(after_id))
    q = _apply_days_filter(q, days)
    rows = q.limit(limit).all()
    return [_to_out(r) for r in rows]


@router.get("/by-buyer/{buyer_id}", response_model=List[ActivityOut])
def by_buyer(
    buyer_id: int = Path(..., ge=1),
    limit: int = Query(100, ge=1, le=500),
    days: Optional[int] = Query(None, ge=1, le=365),
    db: Session = Depends(get_db),
):
    q = (
        db.query(ActivityLog)
        .filter(ActivityLog.buyer_id == buyer_id)
        .order_by(ActivityLog.id.desc())
    )
    q = _apply_days_filter(q, days)
    rows = q.limit(limit).all()
    return [_to_out(r) for r in rows]


@router.get("/by-seller/{seller_id}", response_model=List[ActivityOut])
def by_seller(
    seller_id: int = Path(..., ge=1),
    limit: int = Query(100, ge=1, le=500),
    days: Optional[int] = Query(None, ge=1, le=365),
    db: Session = Depends(get_db),
):
    q = (
        db.query(ActivityLog)
        .filter(ActivityLog.seller_id == seller_id)
        .order_by(ActivityLog.id.desc())
    )
    q = _apply_days_filter(q, days)
    rows = q.limit(limit).all()
    return [_to_out(r) for r in rows]


@router.get("/by-reservation/{reservation_id}", response_model=List[ActivityOut])
def by_reservation(
    reservation_id: int = Path(..., ge=1),
    limit: int = Query(100, ge=1, le=500),
    days: Optional[int] = Query(None, ge=1, le=365),
    db: Session = Depends(get_db),
):
    q = (
        db.query(ActivityLog)
        .filter(ActivityLog.reservation_id == reservation_id)
        .order_by(ActivityLog.id.desc())
    )
    q = _apply_days_filter(q, days)
    rows = q.limit(limit).all()
    return [_to_out(r) for r in rows]


@router.get("/by-deal/{deal_id}", response_model=List[ActivityOut])
def by_deal(
    deal_id: int = Path(..., ge=1),
    limit: int = Query(100, ge=1, le=500),
    days: Optional[int] = Query(None, ge=1, le=365),
    db: Session = Depends(get_db),
):
    q = (
        db.query(ActivityLog)
        .filter(ActivityLog.deal_id == deal_id)
        .order_by(ActivityLog.id.desc())
    )
    q = _apply_days_filter(q, days)
    rows = q.limit(limit).all()
    return [_to_out(r) for r in rows]


@router.get("/by-offer/{offer_id}", response_model=List[ActivityOut])
def by_offer(
    offer_id: int = Path(..., ge=1),
    limit: int = Query(100, ge=1, le=500),
    days: Optional[int] = Query(None, ge=1, le=365),
    db: Session = Depends(get_db),
):
    q = (
        db.query(ActivityLog)
        .filter(ActivityLog.offer_id == offer_id)
        .order_by(ActivityLog.id.desc())
    )
    q = _apply_days_filter(q, days)
    rows = q.limit(limit).all()
    return [_to_out(r) for r in rows]