# app/routers/points.py
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import crud, schemas, models, database

router = APIRouter(prefix="/points", tags=["points"])
get_db = database.get_db


# ---------------------------
# 📋 특정 유저의 포인트 내역 조회
# ---------------------------
@router.get("/{user_type}/{user_id}/transactions", response_model=List[schemas.PointTransactionOut])
def read_point_transactions(
    user_type: str,
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    user_type: 'buyer' 또는 'seller'
    user_id: 해당 유저의 고유 ID
    """
    if user_type not in ["buyer", "seller"]:
        raise HTTPException(status_code=400, detail="Invalid user_type")
    transactions = crud.get_point_transactions(db, user_type=user_type, user_id=user_id)
    return transactions


# ---------------------------
# 💰 특정 유저의 포인트 잔액 조회
# ---------------------------
@router.get("/{user_type}/{user_id}/balance", response_model=schemas.PointTransactionBalance)
def read_point_balance(
    user_type: str,
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    user_type: 'buyer' 또는 'seller'
    user_id: 해당 유저의 고유 ID
    """
    if user_type not in ["buyer", "seller"]:
        raise HTTPException(status_code=400, detail="Invalid user_type")

    balance = crud.get_user_balance(db, user_type=user_type, user_id=user_id)
    return schemas.PointTransactionBalance(
        user_type=user_type,
        user_id=user_id,
        balance=balance
    )


# ---------------------------
# 💸 포인트 사용
# ---------------------------
@router.post("/use")
def use_points(
    body: dict = Body(..., examples=[{"user_type": "buyer", "user_id": 1, "amount": 100, "reason": "할인 적용"}]),
    db: Session = Depends(get_db),
):
    """포인트 사용 (차감). amount > 0 필수, 잔액 부족 시 400."""
    user_type = body.get("user_type", "buyer")
    user_id = body.get("user_id")
    amount = body.get("amount", 0)
    reason = body.get("reason", "포인트 사용")

    if user_type not in ("buyer", "seller"):
        raise HTTPException(400, "user_type은 buyer 또는 seller만 가능합니다")
    if not user_id or not isinstance(user_id, int) or user_id <= 0:
        raise HTTPException(400, "유효한 user_id가 필요합니다")
    if not isinstance(amount, (int, float)) or amount <= 0:
        raise HTTPException(400, "사용 포인트는 1 이상이어야 합니다")

    amount = int(amount)
    balance = crud.get_user_balance(db, user_type=user_type, user_id=user_id)
    if balance < amount:
        raise HTTPException(400, f"포인트 부족 (보유: {balance}, 요청: {amount})")

    pt = models.PointTransaction(
        user_type=user_type,
        user_id=user_id,
        amount=-amount,
        reason=reason,
    )
    db.add(pt)
    db.commit()
    return {"ok": True, "used": amount, "remaining": balance - amount}