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


# ── 참여자 조건 관리 ─────────────────────────────────────
class UserConditionsUpdate(BaseModel):
    fee_rate_override: float | None = None
    cooling_days_override: int | None = None
    settlement_days_override: int | None = None
    shipping_support: bool | None = None
    level_override: int | None = None

    class Config:
        from_attributes = True


@router.get("/{user_id}/conditions", summary="참여자 조건 조회")
def get_user_conditions(user_id: int, db: Session = Depends(get_db)):
    from app.models import UserConditionOverride, Seller, Actuator
    from app.policy.api import policy_time, policy_money

    # 기본값
    defaults = {
        "fee_rate": policy_money("platform_fee_rate") * 100 if policy_money("platform_fee_rate") else 3.0,
        "cooling_days": policy_time("cooling_period_days") or 7,
        "settlement_days": policy_time("settlement_days") or 7,
        "shipping_support": False,
        "level": None,
    }

    # 사용자 정보
    seller = db.query(Seller).filter(Seller.id == user_id).first()
    actuator = db.query(Actuator).filter(Actuator.id == user_id).first()

    user_info = {}
    if seller:
        user_info = {
            "type": "seller",
            "name": seller.business_name or seller.nickname or f"Seller-{user_id}",
            "level": seller.level,
        }
        defaults["level"] = seller.level
    elif actuator:
        user_info = {
            "type": "actuator",
            "name": getattr(actuator, "business_name", None) or getattr(actuator, "nickname", None) or f"Actuator-{user_id}",
        }

    # 오버라이드
    override = db.query(UserConditionOverride).filter(
        UserConditionOverride.user_id == user_id
    ).first()

    current = {
        "fee_rate": override.fee_rate_override if (override and override.fee_rate_override is not None) else defaults["fee_rate"],
        "cooling_days": override.cooling_days_override if (override and override.cooling_days_override is not None) else defaults["cooling_days"],
        "settlement_days": override.settlement_days_override if (override and override.settlement_days_override is not None) else defaults["settlement_days"],
        "shipping_support": override.shipping_support if (override and override.shipping_support is not None) else defaults["shipping_support"],
        "level": override.level_override if (override and override.level_override is not None) else defaults["level"],
    }

    return {
        "user_id": user_id,
        "user_info": user_info,
        "defaults": defaults,
        "current": current,
        "has_override": override is not None,
        "modified_by": override.modified_by if override else None,
        "modified_at": override.modified_at.isoformat() if (override and override.modified_at) else None,
    }


@router.put("/{user_id}/conditions", summary="참여자 조건 수정 (관리자 전용)")
def update_user_conditions(
    user_id: int,
    body: UserConditionsUpdate,
    admin_id: int = Query(0, description="관리자 ID"),
    db: Session = Depends(get_db),
):
    from app.models import UserConditionOverride

    override = db.query(UserConditionOverride).filter(
        UserConditionOverride.user_id == user_id
    ).first()

    if not override:
        override = UserConditionOverride(user_id=user_id)
        db.add(override)

    if body.fee_rate_override is not None:
        override.fee_rate_override = body.fee_rate_override
    if body.cooling_days_override is not None:
        override.cooling_days_override = body.cooling_days_override
    if body.settlement_days_override is not None:
        override.settlement_days_override = body.settlement_days_override
    if body.shipping_support is not None:
        override.shipping_support = body.shipping_support
    if body.level_override is not None:
        override.level_override = body.level_override

    override.modified_by = admin_id
    db.commit()
    db.refresh(override)

    return {"ok": True, "user_id": user_id, "message": "조건이 수정되었습니다."}


@router.delete("/{user_id}/conditions", summary="참여자 조건 초기화 (기본값 복원)")
def reset_user_conditions(user_id: int, db: Session = Depends(get_db)):
    from app.models import UserConditionOverride

    override = db.query(UserConditionOverride).filter(
        UserConditionOverride.user_id == user_id
    ).first()
    if override:
        db.delete(override)
        db.commit()

    return {"ok": True, "user_id": user_id, "message": "기본값으로 초기화되었습니다."}
