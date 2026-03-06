import os
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from .. import database, models
from ..security import (verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES,
                        get_password_hash, SECRET_KEY, ALGORITHM, oauth2_scheme)
from ..utils.email_service import send_reset_email
from jose import jwt as jose_jwt, JWTError

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")

router = APIRouter(prefix="/auth", tags=["auth"])


# ─────────────────────────────────────────────────────────────
# GET /auth/check-email
# ─────────────────────────────────────────────────────────────


@router.get("/check-email", summary="이메일 중복 확인")
def check_email(
    email: str = Query(..., description="확인할 이메일"),
    db: Session = Depends(database.get_db),
):
    """Buyer + Seller + Actuator 테이블에서 이메일 중복 여부를 확인합니다."""
    email_lower = email.strip().lower()
    buyer = db.query(models.Buyer).filter(models.Buyer.email == email_lower).first()
    if buyer:
        return {"available": False}
    seller = db.query(models.Seller).filter(models.Seller.email == email_lower).first()
    if seller:
        return {"available": False}
    actuator = db.query(models.Actuator).filter(models.Actuator.email == email_lower).first()
    if actuator:
        return {"available": False}
    return {"available": True}


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """
    통합 로그인 — User(admin) → Buyer → Seller → Actuator 순서로 조회
    """
    email = form_data.username.strip().lower()
    pw = form_data.password
    user = None
    role = ""
    extra_claims: dict = {}

    # 1. User(관리자) 테이블
    u = db.query(models.User).filter(models.User.email == email).first()
    if u and verify_password(pw, u.hashed_password):
        user, role = u, getattr(u, "role", "admin")

    # 2. Buyer
    if not user:
        b = db.query(models.Buyer).filter(models.Buyer.email == email).first()
        if b and verify_password(pw, b.password_hash):
            user, role = b, "buyer"

    # 3. Seller (승인 여부와 무관하게 로그인 허용, 오퍼 제출만 제한)
    if not user:
        s = db.query(models.Seller).filter(models.Seller.email == email).first()
        if s and verify_password(pw, s.password_hash):
            user, role = s, "seller"
            extra_claims["seller_id"] = s.id
            extra_claims["verified"] = bool(s.verified_at)

    # 4. Actuator
    if not user:
        a = db.query(models.Actuator).filter(
            models.Actuator.email == email
        ).first()
        if a and verify_password(pw, a.password_hash):
            user, role = a, "actuator"
            extra_claims["actuator_id"] = a.id

    if not user:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

    # JWT 토큰 발급
    access_token = create_access_token(
        data={"sub": str(user.id), "role": role, **extra_claims},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
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
# POST /auth/reset-password  — 비밀번호 재설정 요청 (이메일 발송)
# ─────────────────────────────────────────────────────────────
class ResetPasswordRequest(BaseModel):
    email: str


def _find_user_by_email(db: Session, email: str):
    """Buyer → Seller → Actuator 순서로 이메일 조회. (user_obj, user_type) 반환."""
    b = db.query(models.Buyer).filter(models.Buyer.email == email).first()
    if b:
        return b, "buyer"
    s = db.query(models.Seller).filter(models.Seller.email == email).first()
    if s:
        return s, "seller"
    a = db.query(models.Actuator).filter(models.Actuator.email == email).first()
    if a:
        return a, "actuator"
    return None, None


def _find_user_by_token(db: Session, token: str):
    """reset_token으로 사용자 조회. (user_obj, user_type) 반환."""
    b = db.query(models.Buyer).filter(models.Buyer.reset_token == token).first()
    if b:
        return b, "buyer"
    s = db.query(models.Seller).filter(models.Seller.reset_token == token).first()
    if s:
        return s, "seller"
    a = db.query(models.Actuator).filter(models.Actuator.reset_token == token).first()
    if a:
        return a, "actuator"
    return None, None


@router.post(
    "/reset-password",
    summary="비밀번호 재설정 요청",
)
def reset_password(
    body: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db),
):
    """
    이메일로 비밀번호 재설정 링크를 발송합니다.
    열거 공격 방지: 이메일 존재 여부와 무관하게 동일 응답 반환.
    """
    email = body.email.strip().lower()

    user, _ = _find_user_by_email(db, email)

    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.add(user)
        db.commit()

        reset_url = f"{FRONTEND_URL}/reset-password?token={token}"
        background_tasks.add_task(send_reset_email, email, reset_url)

    return {
        "success": True,
        "message": "비밀번호 재설정 안내가 이메일로 발송되었습니다.",
    }


# ─────────────────────────────────────────────────────────────
# GET /auth/reset-password/verify  — 토큰 사전 검증
# ─────────────────────────────────────────────────────────────
@router.get(
    "/reset-password/verify",
    summary="재설정 토큰 유효성 확인",
)
def verify_reset_token(
    token: str = Query(..., description="재설정 토큰"),
    db: Session = Depends(database.get_db),
):
    user, _ = _find_user_by_token(db, token)
    if not user:
        raise HTTPException(status_code=400, detail="invalid_token")
    if user.reset_token_expires_at is None:
        raise HTTPException(status_code=400, detail="invalid_token")

    expires = user.reset_token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="token_expired")

    return {"valid": True}


# ─────────────────────────────────────────────────────────────
# POST /auth/reset-password/confirm  — 새 비밀번호 설정
# ─────────────────────────────────────────────────────────────
class ResetPasswordConfirm(BaseModel):
    token: str
    new_password: str


@router.post(
    "/reset-password/confirm",
    summary="비밀번호 재설정 확정",
)
def confirm_reset_password(
    body: ResetPasswordConfirm,
    db: Session = Depends(database.get_db),
):
    user, _ = _find_user_by_token(db, body.token)
    if not user:
        raise HTTPException(status_code=400, detail="invalid_token")
    if user.reset_token_expires_at is None:
        raise HTTPException(status_code=400, detail="invalid_token")

    expires = user.reset_token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="token_expired")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="password_too_short")

    user.password_hash = get_password_hash(body.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.add(user)
    db.commit()

    return {"success": True, "message": "비밀번호가 성공적으로 변경되었습니다."}


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

    access_token = create_access_token(
        data={"sub": str(seller.id), "role": "seller", "seller_id": seller.id, "verified": bool(seller.verified_at)},
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