from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.security import get_current_user
from app import models
from app.logic.trust import seller_level_and_fee

router = APIRouter(prefix="/sellers/me", tags=["sellers-extended"])

@router.get("/summary")
def get_seller_summary(
    db: Session = Depends(get_db),
    current_user: models.Seller = Depends(get_current_user)
):
    seller_id = getattr(current_user, "id", None)
    offers_q = db.query(models.Offer).filter(models.Offer.seller_id == seller_id).all() if seller_id else []
    # Deal에는 seller_id가 없음 → offers를 통해 deal_id 목록 수집
    deal_ids = list({o.deal_id for o in offers_q if o.deal_id})
    deals_q  = db.query(models.Deal).filter(models.Deal.id.in_(deal_ids)).all() if deal_ids else []

    return {
        "role": "seller",
        "email": getattr(current_user, "email", None),
        "seller_id": seller_id,
        "offer_count": len(offers_q),
        "deal_count":  len(deals_q),
        "offers": [{"id": o.id, "price": o.price, "status": getattr(o,"status","?")} for o in offers_q],
        "deals":  [{"id": d.id, "product_name": d.product_name} for d in deals_q],
    }
    
@router.get("/{seller_id}/level", summary="판매자 레벨 및 수수료(간이 집계)")
def api_seller_level(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    data = seller_level_and_fee(db, seller_id)
    return {"seller_id": seller_id, **data}