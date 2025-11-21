from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from .. import database, models
from ..security import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """
    이메일 + 비밀번호로 로그인하고 JWT 토큰 발급
    (admin은 User 테이블, 일반 구매자는 Buyer 테이블에서 조회)
    """
    # 1️⃣ 우선 User(관리자) 테이블에서 찾기
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if user and verify_password(form_data.password, user.hashed_password):
        role = getattr(user, "role", "admin")
    else:
        # 2️⃣ Buyer(일반 사용자) 테이블에서 찾기
        buyer = db.query(models.Buyer).filter(models.Buyer.email == form_data.username).first()
        if buyer and verify_password(form_data.password, buyer.password_hash):
            user = buyer
            role = "buyer"
        else:
            raise HTTPException(status_code=401, detail="Invalid email or password")

    # 3️⃣ JWT 토큰 발급
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id), "role": role},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}