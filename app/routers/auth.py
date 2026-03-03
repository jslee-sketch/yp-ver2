import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import timedelta
from .. import database, models
from ..security import (verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES,
                        get_password_hash, SECRET_KEY, ALGORITHM, oauth2_scheme)
from jose import jwt as jose_jwt, JWTError

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """
    이메일 + 비밀번호로 로그인하고 JWT 토큰 발급
    (admin은 User 테이블, 일반 구매자는 Buyer 테이블에서 조회)
    """
    # 1 우선 User(관리자) 테이블에서 찾기
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if user and verify_password(form_data.password, user.hashed_password):
        role = getattr(user, "role", "admin")
    else:
        # 2 Buyer(일반 사용자) 테이블에서 찾기
        buyer = db.query(models.Buyer).filter(models.Buyer.email == form_data.username).first()
        if buyer and verify_password(form_data.password, buyer.password_hash):
            user = buyer
            role = "buyer"
        else:
            raise HTTPException(status_code=401, detail="Invalid email or password")

    # 3 JWT 토큰 발급
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": role},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


# ─────────────────────────────────────────────────────────────
# POST /auth/change-password
# ─────────────────────────────────────────────────────────────
class ChangePasswordRequest(BaseModel):
    user_id: int
    user_type: str  # "buyer" | "seller" | "actuator"
    current_password: str
    new_password: str


@router.post(
    "/change-password",
    summary="비밀번호 변경",
)
def change_password(body: ChangePasswordRequest, db: Session = Depends(database.get_db)):
    """
    현재 비밀번호를 검증한 후 새 비밀번호로 변경합니다.
    """
    user_type = body.user_type.lower()

    # 1. 사용자 조회
    if user_type == "buyer":
        obj = db.query(models.Buyer).filter(models.Buyer.id == body.user_id).first()
    elif user_type == "seller":
        obj = db.query(models.Seller).filter(models.Seller.id == body.user_id).first()
    elif user_type == "actuator":
        obj = db.query(models.Actuator).filter(models.Actuator.id == body.user_id).first()
    else:
        raise HTTPException(
            status_code=422,
            detail="invalid_user_type: buyer, seller, actuator 중 하나여야 합니다.",
        )

    if not obj:
        raise HTTPException(status_code=404, detail=f"{user_type}_not_found")

    # 2. 현재 비밀번호 검증
    stored_hash = getattr(obj, "password_hash", None) or ""
    if not verify_password(body.current_password, stored_hash):
        raise HTTPException(status_code=401, detail="wrong_current_password")

    # 3. 새 비밀번호 길이 확인
    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="password_too_short")

    # 4. 비밀번호 갱신
    obj.password_hash = get_password_hash(body.new_password)
    db.add(obj)
    db.commit()

    return {"success": True}


# ─────────────────────────────────────────────────────────────
# POST /auth/reset-password
# ─────────────────────────────────────────────────────────────
class ResetPasswordRequest(BaseModel):
    email: str


@router.post(
    "/reset-password",
    summary="비밀번호 재설정 요청",
)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(database.get_db)):
    """
    이메일로 비밀번호 재설정 토큰을 발급합니다 (개발모드: 콘솔에 출력).
    """
    email = body.email.strip().lower()

    # 1. Buyer / Seller 에서 이메일 조회
    user = db.query(models.Buyer).filter(models.Buyer.email == email).first()
    if not user:
        user = db.query(models.Seller).filter(models.Seller.email == email).first()

    if not user:
        raise HTTPException(status_code=404, detail="email_not_found")

    # 2. 임시 토큰 생성
    token = f"RESET_{user.id}_{int(time.time())}"

    # 3. 콘솔 출력 (개발 모드)
    print(f"[PASSWORD_RESET] token={token} email={email}")

    return {
        "success": True,
        "message": "비밀번호 재설정 링크가 발송되었습니다 (개발모드: 콘솔 확인)",
    }


# ─────────────────────────────────────────────────────────────
# POST /auth/seller/login
# ─────────────────────────────────────────────────────────────
@router.post("/seller/login")
def seller_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db)
):
    """판매자 전용 로그인 — sellers 테이블 조회, 승인된 seller만 토큰 발급"""
    seller = db.query(models.Seller).filter(
        models.Seller.email == form_data.username
    ).first()

    if not seller or not verify_password(form_data.password, seller.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

    if not seller.verified_at:
        raise HTTPException(status_code=403,
            detail="승인 대기 중입니다. 관리자 승인 후 로그인 가능합니다.")

    access_token = create_access_token(
        data={"sub": str(seller.id), "role": "seller", "seller_id": seller.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ─────────────────────────────────────────────────────────────
# GET /auth/seller/me
# ─────────────────────────────────────────────────────────────
@router.get("/seller/me")
def get_seller_me(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db)
):
    """seller 토큰으로 내 정보 조회"""
    try:
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if payload.get("role") != "seller":
        raise HTTPException(status_code=403, detail="판매자 전용 API입니다.")

    seller = db.query(models.Seller).filter(
        models.Seller.id == payload.get("seller_id")
    ).first()
    if not seller:
        raise HTTPException(status_code=404, detail="판매자를 찾을 수 없습니다.")
    return seller