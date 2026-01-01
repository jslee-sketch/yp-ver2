# app/routers/insights.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.logic import trust as T
from app.config import project_rules as R

# (선택) 포인트 조회용 CRUD가 있으면 활용
try:
    from app import crud
except Exception:
    crud = None  # type: ignore

router = APIRouter(prefix="/insights", tags=["📊 Insights (NO-AUTH)"])

class BuyerTrustOut(BaseModel):
    buyer_id: int
    tier: str
    restricted: bool
    stats: dict

class BuyerGradeOut(BaseModel):
    buyer_id: int
    points: int
    grade: str

class SellerLevelOut(BaseModel):
    seller_id: int
    level: str
    fee_percent: float
    sold_count: int
    rating: float

class SuggestDepositOut(BaseModel):
    total_price: float
    suggested_amount: int
    tier: str

def _get_points_balance(db: Session, buyer_id: int) -> int:
    # 가능한 시그니처 자동 탐색
    for name in ("get_buyer_points_balance", "buyer_points_balance", "get_points_balance_for_buyer"):
        fn = getattr(crud, name, None) if crud else None
        if callable(fn):
            try:
                return int(fn(db, buyer_id=buyer_id))
            except TypeError:
                try:
                    return int(fn(db, buyer_id))
                except Exception:
                    pass
    # 없으면 0
    return 0

@router.get("/buyer/{buyer_id}/trust", response_model=BuyerTrustOut)
def get_buyer_trust(
    buyer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    info = T.buyer_trust_tier_and_deposit_percent(db, buyer_id)
    return BuyerTrustOut(
        buyer_id=buyer_id,
        tier=str(info["tier"]),
        deposit_percent=float(info["deposit_percent"]),
        restricted=bool(info.get("restricted", False)),
        stats={k: info[k] for k in ("total", "paid", "fulfillment_rate")},
    )

@router.get("/buyer/{buyer_id}/grade", response_model=BuyerGradeOut)
def get_buyer_grade(
    buyer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    points_override: int | None = Query(None, description="(옵션) 포인트 수동 제공"),
):
    pts = int(points_override) if points_override is not None else _get_points_balance(db, buyer_id)
    grade = T.buyer_points_grade(pts)
    return BuyerGradeOut(buyer_id=buyer_id, points=pts, grade=grade)

@router.get("/seller/{seller_id}/level", response_model=SellerLevelOut)
def get_seller_level(
    seller_id: int = Path(..., ge=1),
    rating: float | None = Query(None, description="(옵션) 외부/집계 평점 직접 제공"),
    db: Session = Depends(get_db),
):
    # rating이 없으면 4.0 가정(내부 함수가 기본 보정)
    info = T.seller_level_and_fee(db, seller_id=seller_id, rating_adjusted=rating)
    return SellerLevelOut(
        seller_id=seller_id,
        level=str(info["level"]),
        fee_percent=float(info["fee_percent"]),
        sold_count=int(info["sold_count"]),
        rating=float(info["rating"]),
    )

@router.get("/buyer/{buyer_id}/deposit/suggest", response_model=SuggestDepositOut)
def suggest_deposit(
    buyer_id: int = Path(..., ge=1),
    total_price: float = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    info = T.buyer_trust_tier_and_deposit_percent(db, buyer_id)
    amt = T.suggested_deposit_amount(total_price, info)
    return SuggestDepositOut(
        total_price=float(total_price),
        deposit_percent=float(info["deposit_percent"]),
        suggested_amount=int(amt),
        tier=str(info["tier"]),
    )