# app/routers/buyers.py
# 🔧 무인증(DEV) 버전 - 인증 제거 완료
# Writer: Jeong Sang Lee
# Date: 2025-11-07

from fastapi import APIRouter, HTTPException, Depends, Path
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import crud, schemas, database

# --- (추가) Buyer 기본정보 출력용 ---
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

from app import models


router = APIRouter(
    prefix="/buyers",
    tags=["buyers (NO-AUTH DEV)"]
)

# -----------------------------------------------------
# 1️⃣ 로그인된 유저 정보 (무인증 대체 버전)
# -----------------------------------------------------
@router.get("/me")
def read_me():
    """
    ✅ 무인증 개발 모드:
    인증 절차 없이 항상 더미 유저(dev_buyer@yeokping.com)로 응답
    """
    return {"ok": True, "user": {"email": "dev_buyer@yeokping.com (no-auth)"}}

# -----------------------------------------------------
# 2️⃣ 신규 Buyer 생성
# -----------------------------------------------------
@router.post("/", response_model=schemas.BuyerOut)
def create_buyer(
    buyer: schemas.BuyerCreate,
    db: Session = Depends(database.get_db),
):
    try:
        return crud.create_buyer(db, buyer)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

# -----------------------------------------------------
# 3️⃣ Buyer 목록 조회
# -----------------------------------------------------
@router.get("/", response_model=list[schemas.BuyerOut])
def list_buyers(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(database.get_db),
):
    return crud.get_buyers(db, skip=skip, limit=limit)


class BuyerBasicOut(BaseModel):
    buyer_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None


@router.get("/{buyer_id}", response_model=BuyerBasicOut)
def get_buyer_basic(
    buyer_id: int = Path(..., ge=1),
    db: Session = Depends(database.get_db),
):
    """
    포털 카드용 최소 Buyer 프로필.
    - 기본값은 buyers 테이블(models.Buyer)의 값
    - 못 찾으면 예전처럼 "Buyer #id" 로 표기
    """
    row = db.query(models.Buyer).get(buyer_id)

    if row:
        return BuyerBasicOut(
            buyer_id=row.id,
            name=row.name,
            email=row.email,
            phone=row.phone,
            address=row.address,
            created_at=row.created_at,
        )

    # DB에 없을 때만 최소 정보 표기 (구버전 호환)
    return BuyerBasicOut(
        buyer_id=buyer_id,
        name=f"Buyer #{buyer_id}",  # 임시 표기
        email=None,
        phone=None,
        address=None,
        created_at=datetime.now(timezone.utc),
    )