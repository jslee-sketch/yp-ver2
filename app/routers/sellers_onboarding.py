# app/routers/sellers_onboarding.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, status
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, Float, String, Text, DateTime, Index
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db

# 활동로그가 있으면 사용(없어도 동작)
try:
    from app.routers.activity_log import log_event  # optional
except Exception:
    def log_event(*args, **kwargs):  # type: ignore
        return -1

router = APIRouter(prefix="/onboarding", tags=["🧭 SellerOnboarding (NO-AUTH)"])

# ── DB Model ─────────────────────────────────────────────
class SellerOnboarding(Base):  # type: ignore
    __tablename__ = "sellers_onboarding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(Integer, nullable=False, index=True)
    company_name = Column(String(200), nullable=False)

    external_source = Column(String(50), nullable=True)   # 예: 'Naver', 'Coupang'
    external_url = Column(Text, nullable=True)
    external_rating = Column(Float, nullable=True)        # 0.0 ~ 5.0
    external_rating_count = Column(Integer, nullable=True, default=0)

    status = Column(String(20), nullable=False, default="PENDING")  # PENDING | APPROVED | REJECTED

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

Index("ix_onboarding_status", SellerOnboarding.status)

Base.metadata.create_all(bind=engine)

# ── Schemas ─────────────────────────────────────────────
class SellerOnboardingIn(BaseModel):
    seller_id: int = Field(..., ge=1)
    company_name: str = Field(..., min_length=1)
    external_source: Optional[str] = None
    external_url: Optional[str] = None
    external_rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    external_rating_count: Optional[int] = Field(0, ge=0)

class SellerOnboardingOut(BaseModel):
    id: int
    seller_id: int
    company_name: str
    external_source: Optional[str]
    external_url: Optional[str]
    external_rating: Optional[float]
    external_rating_count: Optional[int]
    status: str
    created_at: datetime
    decided_at: Optional[datetime]
    decided_by: Optional[str]
    notes: Optional[str]

class DecisionIn(BaseModel):
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    decided_by: str = Field(..., min_length=1)
    notes: Optional[str] = None

def _to_out(row: SellerOnboarding) -> SellerOnboardingOut:
    return SellerOnboardingOut(
        id=row.id,
        seller_id=row.seller_id,
        company_name=row.company_name,
        external_source=row.external_source,
        external_url=row.external_url,
        external_rating=row.external_rating,
        external_rating_count=row.external_rating_count,
        status=row.status,
        created_at=row.created_at,
        decided_at=row.decided_at,
        decided_by=row.decided_by,
        notes=row.notes,
    )

# ── Public (Seller) ─────────────────────────────────────
@router.post("/sellers", response_model=SellerOnboardingOut, status_code=status.HTTP_201_CREATED)
def create_request(body: SellerOnboardingIn = Body(...), db: Session = Depends(get_db)):
    exists = (
        db.query(SellerOnboarding)
          .filter(SellerOnboarding.seller_id == body.seller_id, SellerOnboarding.status == "PENDING")
          .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="pending request already exists for this seller")

    row = SellerOnboarding(
        seller_id=body.seller_id,
        company_name=body.company_name,
        external_source=body.external_source,
        external_url=body.external_url,
        external_rating=body.external_rating,
        external_rating_count=body.external_rating_count or 0,
        status="PENDING",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        log_event(
            db,
            event_type="SELLER_ONBOARDING_REQUESTED",
            actor_type="SELLER", actor_id=body.seller_id,
            seller_id=body.seller_id,
            meta={
                "company_name": body.company_name,
                "external": {
                    "source": body.external_source, "rating": body.external_rating,
                    "count": body.external_rating_count, "url": body.external_url
                }
            }
        )
    except Exception:
        pass

    return _to_out(row)

@router.get("/sellers/{req_id}", response_model=SellerOnboardingOut)
def get_request(req_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    row: Optional[SellerOnboarding] = db.query(SellerOnboarding).get(req_id)  # type: ignore
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return _to_out(row)

@router.get("/sellers/by-seller/{seller_id}", response_model=List[SellerOnboardingOut])
def list_requests_by_seller(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(SellerOnboarding)
          .filter(SellerOnboarding.seller_id == seller_id)
          .order_by(SellerOnboarding.id.desc())
          .all()
    )
    return [_to_out(r) for r in rows]

# ── Admin ───────────────────────────────────────────────
@router.get("/admin/sellers", response_model=List[SellerOnboardingOut])
def list_requests(
    status: Optional[str] = Query(None, pattern="^(PENDING|APPROVED|REJECTED)$"),
    limit: int = Query(100, ge=1, le=500),
    after_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(SellerOnboarding).order_by(SellerOnboarding.id.desc())
    if status:
        q = q.filter(SellerOnboarding.status == status)
    if after_id:
        q = q.filter(SellerOnboarding.id < int(after_id))
    rows = q.limit(limit).all()
    return [_to_out(r) for r in rows]

@router.post("/admin/sellers/{req_id}/decide", response_model=SellerOnboardingOut)
def decide_request(
    req_id: int = Path(..., ge=1),
    body: DecisionIn = Body(...),
    db: Session = Depends(get_db),
):
    row: Optional[SellerOnboarding] = db.query(SellerOnboarding).get(req_id)  # type: ignore
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    if row.status != "PENDING":
        raise HTTPException(status_code=409, detail="already decided")

    row.status = body.decision
    row.decided_at = datetime.now(timezone.utc)
    row.decided_by = body.decided_by
    row.notes = body.notes
    db.add(row)
    db.commit()
    db.refresh(row)

    try:
        log_event(
            db,
            event_type="SELLER_ONBOARDING_DECIDED",
            actor_type="ADMIN", actor_id=0,
            seller_id=row.seller_id,
            meta={"decision": row.status, "decided_by": row.decided_by, "req_id": row.id}
        )
    except Exception:
        pass

    return _to_out(row)