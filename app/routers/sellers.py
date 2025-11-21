# app/routers/sellers.py
# 🔧 무인증(DEV) 버전 - 인증 제거 완료
# Writer: Jeong Sang Lee
# Date: 2025-11-07

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import crud, schemas, database

router = APIRouter(
    prefix="/sellers",
    tags=["sellers (NO-AUTH DEV)"]
)

# -----------------------------------------------------
# 1️⃣ 로그인된 판매자 정보 (무인증 대체 버전)
# -----------------------------------------------------
@router.get("/me")
def read_me():
    """
    ✅ 무인증 개발 모드:
    인증 절차 없이 항상 더미 판매자(dev_seller@yeokping.com)로 응답
    """
    return {"ok": True, "user": {"email": "dev_seller@yeokping.com (no-auth)"}}

# -----------------------------------------------------
# 2️⃣ 신규 Seller 생성
# -----------------------------------------------------
@router.post("/", response_model=None)
def create_seller(seller: schemas.SellerCreate, db: Session = Depends(database.get_db)):
    try:
        return crud.create_seller(db, seller)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

# -----------------------------------------------------
# 3️⃣ Seller 목록 조회
# -----------------------------------------------------
@router.get("/", response_model=list[None])
def list_sellers(skip: int = 0, limit: int = 10, db: Session = Depends(database.get_db)):
    return crud.get_sellers(db, skip=skip, limit=limit)