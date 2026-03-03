# app/routers/admin_users.py
"""
POST /admin/users/ban     — 차단/정지
POST /admin/users/unban   — 차단 해제
GET  /admin/users/banned  — 차단 목록
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app import models

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


# ─────────────────────────────
# 내부 헬퍼: 사용자 조회
# ─────────────────────────────
def _get_user(db: Session, user_type: str, user_id: int):
    t = user_type.lower()
    if t == "buyer":
        obj = db.query(models.Buyer).filter(models.Buyer.id == user_id).first()
    elif t == "seller":
        obj = db.query(models.Seller).filter(models.Seller.id == user_id).first()
    elif t == "actuator":
        obj = db.query(models.Actuator).filter(models.Actuator.id == user_id).first()
    else:
        raise HTTPException(
            status_code=422,
            detail="invalid_user_type: buyer, seller, actuator 중 하나여야 합니다.",
        )
    if not obj:
        raise HTTPException(status_code=404, detail=f"{t}_not_found")
    return obj


# ─────────────────────────────
# POST /admin/users/ban
# ─────────────────────────────
class BanRequest(BaseModel):
    user_id: int
    user_type: str  # "buyer" | "seller" | "actuator"
    ban_type: str   # "permanent" | "temporary"
    banned_until: Optional[datetime] = None
    reason: Optional[str] = None


@router.post(
    "/ban",
    summary="사용자 차단/정지",
)
def ban_user(body: BanRequest, db: Session = Depends(get_db)):
    obj = _get_user(db, body.user_type, body.user_id)

    setattr(obj, "is_banned", True)
    setattr(obj, "ban_reason", body.reason)

    if body.ban_type == "temporary":
        setattr(obj, "banned_until", body.banned_until)
    else:
        # permanent: banned_until은 None (무기한)
        setattr(obj, "banned_until", None)

    db.add(obj)
    db.commit()
    db.refresh(obj)

    return {
        "success": True,
        "user_id": body.user_id,
        "user_type": body.user_type,
        "ban_type": body.ban_type,
        "banned_until": getattr(obj, "banned_until", None),
        "ban_reason": getattr(obj, "ban_reason", None),
    }


# ─────────────────────────────
# POST /admin/users/unban
# ─────────────────────────────
class UnbanRequest(BaseModel):
    user_id: int
    user_type: str  # "buyer" | "seller" | "actuator"


@router.post(
    "/unban",
    summary="사용자 차단 해제",
)
def unban_user(body: UnbanRequest, db: Session = Depends(get_db)):
    obj = _get_user(db, body.user_type, body.user_id)

    setattr(obj, "is_banned", False)
    setattr(obj, "banned_until", None)

    db.add(obj)
    db.commit()
    db.refresh(obj)

    return {
        "success": True,
        "user_id": body.user_id,
        "user_type": body.user_type,
        "is_banned": False,
    }


# ─────────────────────────────
# GET /admin/users/banned
# ─────────────────────────────
class BannedUserOut(BaseModel):
    user_id: int
    user_type: str
    name: Optional[str] = None
    email: Optional[str] = None
    ban_reason: Optional[str] = None
    banned_until: Optional[datetime] = None

    class Config:
        from_attributes = True


def _build_banned_entry(obj, user_type: str) -> dict:
    return {
        "user_id": obj.id,
        "user_type": user_type,
        "name": getattr(obj, "name", None) or getattr(obj, "business_name", None),
        "email": getattr(obj, "email", None),
        "ban_reason": getattr(obj, "ban_reason", None),
        "banned_until": getattr(obj, "banned_until", None),
    }


@router.get(
    "/banned",
    summary="차단된 사용자 목록 조회",
    response_model=List[BannedUserOut],
)
def list_banned_users(
    user_type: Optional[str] = Query(None, description="buyer | seller (없으면 buyer+seller 합산)"),
    db: Session = Depends(get_db),
):
    result: list[dict] = []

    def _is_banned(obj) -> bool:
        return bool(getattr(obj, "is_banned", False))

    if user_type is None or user_type.lower() == "buyer":
        buyers = db.query(models.Buyer).all()
        for b in buyers:
            if _is_banned(b):
                result.append(_build_banned_entry(b, "buyer"))

    if user_type is None or user_type.lower() == "seller":
        sellers = db.query(models.Seller).all()
        for s in sellers:
            if _is_banned(s):
                result.append(_build_banned_entry(s, "seller"))

    if user_type is not None and user_type.lower() not in ("buyer", "seller"):
        raise HTTPException(
            status_code=422,
            detail="invalid_user_type: buyer 또는 seller 만 지원합니다.",
        )

    return result
