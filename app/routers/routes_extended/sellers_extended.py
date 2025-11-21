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
    offers = db.query(models.Offer).filter(models.Offer.seller_id == current_user.id).all()
    deals = db.query(models.Deal).filter(models.Deal.seller_id == current_user.id).all()
    buyers = db.query(models.Buyer).join(models.Deal).filter(models.Deal.seller_id == current_user.id).all()

    return {
        "role": "seller",
        "email": current_user.email,
        "offers": offers,
        "deals": deals,
        "buyers": buyers
    }
    
@router.get("/{seller_id}/level", summary="판매자 레벨 및 수수료(간이 집계)")
def api_seller_level(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    data = seller_level_and_fee(db, seller_id)
    return {"seller_id": seller_id, **data}