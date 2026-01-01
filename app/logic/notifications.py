# app/logic/notifications.py

from typing import Optional, Dict, Any, Iterable
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app import models

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def create_notification(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    title: str,
    message: str,
    deal_id: Optional[int] = None,
    offer_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    buyer_id: Optional[int] = None,
    actuator_id: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
    auto_commit: bool = True,
) -> models.UserNotification:
    """
    단일 사용자 알림 생성 헬퍼.
    """
    notif = models.UserNotification(
        user_id=user_id,
        event_type=event_type,
        title=title,
        message=message,
        deal_id=deal_id,
        offer_id=offer_id,
        reservation_id=reservation_id,
        seller_id=seller_id,
        buyer_id=buyer_id,
        actuator_id=actuator_id,
        meta=meta or {},
        is_read=False,
        created_at=now_utc(),
    )
    db.add(notif)
    if auto_commit:
        db.commit()
        db.refresh(notif)
    return notif


def create_notifications_bulk(
    db: Session,
    *,
    user_ids: Iterable[int],
    event_type: str,
    title: str,
    message: str,
    deal_id: Optional[int] = None,
    offer_id: Optional[int] = None,
    reservation_id: Optional[int] = None,
    seller_id: Optional[int] = None,
    buyer_id: Optional[int] = None,
    actuator_id: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """
    여러 유저에게 같은 알림을 뿌릴 때 사용 (예: Deal 마감 1시간 전 참여자 전원).
    """
    base_meta = meta or {}
    for uid in user_ids:
        db.add(
            models.UserNotification(
                user_id=uid,
                event_type=event_type,
                title=title,
                message=message,
                deal_id=deal_id,
                offer_id=offer_id,
                reservation_id=reservation_id,
                seller_id=seller_id,
                buyer_id=buyer_id,
                actuator_id=actuator_id,
                meta=base_meta,
                is_read=False,
                created_at=now_utc(),
            )
        )
    db.commit()