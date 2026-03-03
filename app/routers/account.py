# app/routers/account.py
"""
DELETE /account/withdraw  — 회원 탈퇴
  - 진행 중인 거래 있으면 409 반환
  - 개인정보 비식별화 + is_active=False
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.routers.notifications import create_notification

router = APIRouter(prefix="/account", tags=["account"])


# ─────────────────────────────
# 요청 스키마
# ─────────────────────────────
class WithdrawRequest(BaseModel):
    user_id: int
    user_type: str  # "buyer" | "seller" | "actuator"
    reason: Optional[str] = None


# ─────────────────────────────
# 내부 헬퍼: 진행 중인 거래 확인
# ─────────────────────────────
_ACTIVE_STATUSES = ("PENDING", "PAID")


def _check_active_reservations_buyer(db: Session, buyer_id: int) -> bool:
    """buyer에 진행 중인 예약(PENDING/PAID)이 있으면 True"""
    return (
        db.query(models.Reservation)
        .filter(
            models.Reservation.buyer_id == buyer_id,
            models.Reservation.status.in_(_ACTIVE_STATUSES),
        )
        .first()
        is not None
    )


def _check_active_reservations_seller(db: Session, seller_id: int) -> bool:
    """seller의 오퍼에 연결된 진행 중인 예약(PENDING/PAID)이 있으면 True"""
    offer_ids = (
        db.query(models.Offer.id)
        .filter(models.Offer.seller_id == seller_id)
        .subquery()
    )
    return (
        db.query(models.Reservation)
        .filter(
            models.Reservation.offer_id.in_(offer_ids),
            models.Reservation.status.in_(_ACTIVE_STATUSES),
        )
        .first()
        is not None
    )


# ─────────────────────────────
# DELETE /account/withdraw
# ─────────────────────────────
@router.delete(
    "/withdraw",
    summary="회원 탈퇴",
    description="진행 중인 거래가 있으면 409를 반환하고, 개인정보를 비식별화합니다.",
)
def withdraw_account(body: WithdrawRequest, db: Session = Depends(get_db)):
    user_id = body.user_id
    user_type = body.user_type.lower()
    now = datetime.now(timezone.utc)

    # ── 1. 사용자 조회 ──────────────────────────────────────────
    if user_type == "buyer":
        obj = db.query(models.Buyer).filter(models.Buyer.id == user_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="buyer_not_found")

        # 진행 중인 거래 확인
        if _check_active_reservations_buyer(db, user_id):
            raise HTTPException(
                status_code=409,
                detail="active_reservations_exist: 진행 중인 거래가 있어 탈퇴할 수 없습니다.",
            )

        # 개인정보 비식별화
        obj.name = f"탈퇴회원_{user_id}"
        obj.email = f"withdrawn_{user_id}@deleted"
        obj.phone = None
        obj.password_hash = ""
        setattr(obj, "is_active", False)
        setattr(obj, "withdrawn_at", now)

    elif user_type == "seller":
        obj = db.query(models.Seller).filter(models.Seller.id == user_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="seller_not_found")

        # 진행 중인 거래 확인
        if _check_active_reservations_seller(db, user_id):
            raise HTTPException(
                status_code=409,
                detail="active_reservations_exist: 진행 중인 거래가 있어 탈퇴할 수 없습니다.",
            )

        # 개인정보 비식별화
        obj.email = f"withdrawn_s_{user_id}@deleted"
        obj.phone = None
        obj.password_hash = ""
        setattr(obj, "is_active", False)
        setattr(obj, "withdrawn_at", now)

    elif user_type == "actuator":
        obj = db.query(models.Actuator).filter(models.Actuator.id == user_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="actuator_not_found")

        # actuator는 항상 탈퇴 허용
        obj.status = "WITHDRAWN"
        if getattr(obj, "email", None) is not None:
            obj.email = f"withdrawn_a_{user_id}@deleted"
        setattr(obj, "is_active", False)
        setattr(obj, "withdrawn_at", now)

    else:
        raise HTTPException(
            status_code=422,
            detail="invalid_user_type: buyer, seller, actuator 중 하나여야 합니다.",
        )

    # ── 2. DB 저장 ──────────────────────────────────────────────
    db.add(obj)
    db.commit()
    db.refresh(obj)

    # ── 3. 알림 발송 ────────────────────────────────────────────
    try:
        create_notification(
            db,
            user_id=user_id,
            type="account_withdrawn",
            title="회원 탈퇴가 완료되었습니다",
            message=f"회원 탈퇴 처리가 완료되었습니다. 사유: {body.reason or '미입력'}",
            meta={"user_type": user_type, "reason": body.reason},
        )
    except Exception:
        # 알림 실패는 탈퇴 자체를 막지 않음
        pass

    # ── 4. 응답 ─────────────────────────────────────────────────
    withdrawn_at_val = getattr(obj, "withdrawn_at", now)
    return {
        "success": True,
        "withdrawn_at": withdrawn_at_val,
    }
