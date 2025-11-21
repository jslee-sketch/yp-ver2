from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Deal
from ..logic.trust import offer_price_exposure_category

router = APIRouter(prefix="/offers", tags=["offers-policy"])

@router.get("/validate_price", summary="오퍼 가격 노출/제출 정책 검증")
def validate_offer_price(
    deal_id: int = Query(..., ge=1),
    price: float = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    deal = db.get(Deal, deal_id)
    if not deal:
        return {"ok": False, "error": "deal not found"}

    # Deal 모델에 'desired_price' 또는 유사 필드가 있다고 가정
    wish = getattr(deal, "desired_price", None)
    if not wish:
        return {"ok": False, "error": "deal.desired_price not set"}

    verdict = offer_price_exposure_category(float(wish), float(price))
    return {"ok": True, "deal_id": deal_id, "deal_desired_price": wish, "offer_price": price, **verdict}