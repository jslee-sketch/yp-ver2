from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import crud, models, database

router = APIRouter(
    prefix="/payments",
    tags=["payments"]
)

get_db = database.get_db


# -------------------
# 구매자 결제 (성공 처리)
# -------------------
@router.post("/checkout/{buyer_id}/{deal_id}")
def checkout_payment(buyer_id: int, deal_id: int, db: Session = Depends(get_db)):
    """
    Buyer 결제 완료 → 포인트 +20
    """
    deal = db.query(models.Deal).filter(models.Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    crud.reward_buyer_payment(db, buyer_id=buyer_id)

    return {
        "message": "결제 성공! Buyer에게 +20 포인트 적립",
        "buyer_id": buyer_id,
        "deal_id": deal_id
    }


# -------------------
# 구매자 결제 취소
# -------------------
@router.post("/cancel/{buyer_id}/{deal_id}")
def cancel_payment(buyer_id: int, deal_id: int, db: Session = Depends(get_db)):
    """
    Buyer 결제 취소 → 포인트 -20
    """
    deal = db.query(models.Deal).filter(models.Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    crud.penalize_buyer_cancel(db, buyer_id=buyer_id)

    return {
        "message": "결제 취소됨! Buyer 포인트 -20 차감",
        "buyer_id": buyer_id,
        "deal_id": deal_id
    }


# -------------------
# 판매자 거래 확정 (정산 처리)
# -------------------
@router.post("/settlement/{seller_id}/{offer_id}")
def settle_payment(seller_id: int, offer_id: int, db: Session = Depends(get_db)):
    """
    Offer 확정 → Seller 포인트 +30
    """
    offer = db.query(models.Offer).filter(models.Offer.id == offer_id).first()
    if not offer or offer.seller_id != seller_id:
        raise HTTPException(status_code=404, detail="Offer not found or Seller mismatch")

    crud.reward_seller_success(db, seller_id=seller_id)

    return {
        "message": "거래 성사! Seller에게 +30 포인트 적립",
        "seller_id": seller_id,
        "offer_id": offer_id
    }