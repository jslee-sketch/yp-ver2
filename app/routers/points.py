# app/routers/points.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import crud, schemas, database

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