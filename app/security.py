# app/security.py
# Author: Jeong Sang Lee
# Date: 2025-11-03

print("✅ SECURITY MODULE LOADED:", __file__)

import os
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from typing import Optional

from app.database import get_db
from app import models

# -----------------------------------------------------
# 🔧 기본 설정 (환경변수 기반)
# -----------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY") or os.environ.get("JWT_SECRET_KEY") or "dev-only-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# 개발용 우회 모드 — 프로덕션에서는 반드시 false
DEV_BYPASS = os.environ.get("DEV_BYPASS", "true").lower() == "true"

if DEV_BYPASS:
    print("⚠️  [SECURITY] DEV_BYPASS=True — 인증 우회 활성화. 프로덕션에서는 DEV_BYPASS=false로 설정하세요.")
if SECRET_KEY == "dev-only-change-in-production":
    print("⚠️  [SECURITY] SECRET_KEY 기본값 사용 중 — 프로덕션에서는 반드시 변경하세요.")

# -----------------------------------------------------
# 🔑 비밀번호 해싱 관련
# -----------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# -----------------------------------------------------
# 🪙 OAuth2 스키마 (Swagger Authorize와 연결)
# -----------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# -----------------------------------------------------
# 👤 현재 로그인한 유저 확인 (DEV_BYPASS 모드)
# -----------------------------------------------------
def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
):
    """
    ✅ DEV_BYPASS=True 시에는 Swagger Authorization 없어도 admin 인증 우회됨.
    ✅ Swagger의 'Authorize' 버튼으로 입력된 토큰이 있을 경우 JWT 인증 수행.
    """
    # 🔹 Step 1: 개발용 우회 (Swagger 등 토큰 없이도 작동)
    if DEV_BYPASS:
        print("⚠️ [SECURITY] DEV_BYPASS 활성화됨 → 관리자(admin@yeokping.com)로 인증됨")
        return type("User", (), {"email": "admin@yeokping.com", "id": 1})()

    # 🔹 Step 2: JWT 인증 수행
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (token missing)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(models.Buyer).filter(models.Buyer.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user

# -----------------------------------------------------
# 🧾 JWT 생성 (로그인용)
# -----------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    로그인 시 JWT 토큰을 발급하는 함수.
    DEV_BYPASS=True 일 때도 import 호환을 위해 유지됨.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt