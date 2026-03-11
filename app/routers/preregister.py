# app/routers/preregister.py
"""사전 등록 이메일 수집 (출시 전 랜딩 페이지)"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.database import get_db
from app import models

router = APIRouter(tags=["사전등록"])


@router.post("/api/preregister")
def preregister(body: dict, db: Session = Depends(get_db)):
    email = str(body.get("email", "")).strip().lower()
    if not email or "@" not in email or len(email) > 200:
        return {"error": "유효한 이메일을 입력하세요", "ok": False}

    existing = db.query(models.PreRegister).filter(models.PreRegister.email == email).first()
    if existing:
        return {"message": "이미 등록된 이메일입니다", "ok": True}

    db.add(models.PreRegister(email=email, created_at=datetime.now(timezone.utc)))
    db.commit()
    return {"message": "등록 완료", "ok": True}


@router.get("/api/preregister/count")
def preregister_count(db: Session = Depends(get_db)):
    """관리자용: 사전 등록 수 확인"""
    count = db.query(models.PreRegister).count()
    return {"count": count}
