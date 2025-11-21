# app/routers/checkout.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import models, crud
from app.database import get_db

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.post("/checkout/{deal_id}")
def checkout_deal(deal_id: int, buyer_id: int, db: Session = Depends(get_db)):
    deal = db.query(models.Deal).get(deal_id)
    if not deal:
        raise HTTPException(404, "Deal not found")
    best_offer = crud.auto_select_best_offer(db, deal_id)
    if not best_offer:
        raise HTTPException(400, "No offers yet")
    crud.log_point_transaction(db, "buyer", buyer_id, -best_offer.price, "deal checkout")
    crud.log_point_transaction(db, "seller", best_offer.seller_id, best_offer.price, "deal sold")
    return {"message": "Checkout complete", "deal_id": deal_id}