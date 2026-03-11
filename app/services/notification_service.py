# app/services/notification_service.py
"""통합 알림 발송 서비스 — 사용자 설정에 따라 앱/푸시/이메일 채널별 발송"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services.notification_templates import get_event_defaults, render_notification

logger = logging.getLogger(__name__)


def send_notification(
    db: Session,
    *,
    user_id: int,
    role: str = "buyer",
    event_type: str,
    variables: dict | None = None,
    # Override title/message (if not using templates)
    title: str | None = None,
    message: str | None = None,
    link: str | None = None,
    deal_id: int | None = None,
    offer_id: int | None = None,
    reservation_id: int | None = None,
    settlement_id: int | None = None,
) -> models.UserNotification | None:
    """통합 알림 발송"""
    variables = variables or {}

    # 1. 템플릿 렌더링
    rendered = render_notification(event_type, variables)
    final_title = title or rendered["title"]
    final_message = message or rendered["message"]
    final_link = link or rendered["link"]

    # 2. 사용자 알림 설정 확인
    setting = db.query(models.NotificationSetting).filter(
        models.NotificationSetting.user_id == user_id,
        models.NotificationSetting.event_type == event_type,
    ).first()

    if setting:
        send_app = setting.channel_app
        send_push = setting.channel_push
        send_email = setting.channel_email
    else:
        defaults = get_event_defaults(event_type, role)
        send_app = defaults.get("app", True)
        send_push = defaults.get("push", False)
        send_email = defaults.get("email", False)

    # 3. 앱 내 알림 저장
    sent_app = False
    notif = None
    if send_app:
        import json
        meta = {"role": role, "event_type": event_type}
        if deal_id:
            meta["deal_id"] = deal_id
        if offer_id:
            meta["offer_id"] = offer_id

        notif = models.UserNotification(
            user_id=user_id,
            type=event_type,
            title=final_title,
            message=final_message,
            link_url=final_link,
            event_time=datetime.now(timezone.utc),
            meta_json=json.dumps(meta, ensure_ascii=False),
            deal_id=deal_id,
            offer_id=offer_id,
            reservation_id=reservation_id,
            settlement_id=settlement_id,
            sent_app=True,
        )
        db.add(notif)
        sent_app = True

    # 4. FCM 푸시
    sent_push = False
    if send_push:
        try:
            token = _get_fcm_token(db, user_id, role)
            if token:
                from app.services.fcm_push import send_push as fcm_send
                sent_push = fcm_send(token, final_title, final_message, {
                    "type": event_type,
                    "link": final_link or "",
                })
        except Exception as e:
            logger.warning("[NOTIFY] FCM push failed: %s", e)

    # 5. 이메일 (placeholder — actual email service integration)
    sent_email = False
    if send_email:
        # TODO: integrate actual email sending
        logger.info("[NOTIFY] Email would be sent to user=%d: %s", user_id, final_title)

    # 6. 발송 결과 기록
    if notif:
        notif.sent_push = sent_push
        notif.sent_email = sent_email

    try:
        db.commit()
        if notif:
            db.refresh(notif)
    except Exception:
        db.rollback()

    logger.info(
        "[NOTIFY] user=%d event=%s app=%s push=%s email=%s",
        user_id, event_type, sent_app, sent_push, sent_email,
    )
    return notif


def notify_interest_match_on_deal_create(deal, db: Session):
    """새 딜 생성 시 → 관심 등록된 사용자에게 알림"""
    product = (deal.product_name or "").lower()
    if not product:
        return

    interests = db.query(models.UserInterest).all()

    for interest in interests:
        val = (interest.value or "").lower()
        if val not in product and product not in val:
            continue

        role = interest.role or "buyer"
        event_map = {
            "seller": "DEAL_MATCH_INTEREST",
            "actuator": "INTEREST_DEAL_CREATED",
            "buyer": "NUDGE_INTEREST_DEAL",
        }
        event_type = event_map.get(role, "NUDGE_INTEREST_DEAL")

        send_notification(
            db,
            user_id=interest.user_id,
            role=role,
            event_type=event_type,
            variables={
                "matched_interest": interest.value,
                "product_name": deal.product_name,
                "deal_id": str(deal.id),
                "target_price": f"{deal.target_price:,.0f}" if deal.target_price else "",
            },
            deal_id=deal.id,
        )


def _get_fcm_token(db: Session, user_id: int, role: str) -> Optional[str]:
    """역할에 따라 FCM 토큰 조회"""
    if role == "seller":
        row = db.query(models.Seller).filter(models.Seller.id == user_id).first()
    elif role == "actuator":
        row = db.query(models.Actuator).filter(models.Actuator.id == user_id).first()
    else:
        row = db.query(models.Buyer).filter(models.Buyer.id == user_id).first()
    return getattr(row, "fcm_token", None) if row else None
