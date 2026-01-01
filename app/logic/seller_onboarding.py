# 예: app/logic/seller_onboarding.py
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app import models
from app.config import project_rules as R

from app.logic.notifications_actuator import notify_actuator_seller_registered
from app.logic.notifications_actuator import notify_actuator_commission_rate_changed
from app.logic.notifications_actuator import notify_actuator_commission_paid


# 셀러 승인 완료 시
def approve_seller(db: Session, seller_id: int):
    seller = db.get(models.Seller, seller_id)
    # ... 심사 로직 ...
    seller.status = "APPROVED"
    db.add(seller)
    db.commit()
    db.refresh(seller)

    # 🔔 추천인에게 알림
    notify_actuator_seller_registered(db, seller)

    return seller

# 셀러레벨 업데잍 시
def update_seller_level(db: Session, seller_id: int, new_level: int):
    seller = db.get(models.Seller, seller_id)
    old_level = int(getattr(seller, "level", 6) or 6)
    seller.level = new_level
    db.add(seller)
    db.commit()
    db.refresh(seller)

    notify_actuator_commission_rate_changed(db, seller, old_level=old_level, new_level=new_level)
    return seller

# 셀러의 커미션 정산 배치 후
def mark_commission_paid(db: Session, commission_id: int):
    comm = db.get(models.ActuatorCommission, commission_id)
    # ... 실제 정산/송금 처리 ...
    comm.status = "PAID"
    comm.paid_at = now_utc()
    db.add(comm)
    db.commit()
    db.refresh(comm)

    seller = db.get(models.Seller, comm.seller_id) if comm.seller_id else None
    notify_actuator_commission_paid(db, comm, seller=seller)
    
    
def now_utc() -> datetime:
    """
    R.now_utc()가 정의되어 있으면 그걸 쓰고,
    없으면 datetime.now(timezone.utc)로 대체.
    """
    fn = getattr(R, "now_utc", None)
    if callable(fn):
        return fn()
    return datetime.now(timezone.utc)