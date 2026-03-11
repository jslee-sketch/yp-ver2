# app/routers/notification_settings.py
"""알림 설정 + 관심 카테고리/제품/모델 API"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserInterest, NotificationSetting
from app.services.notification_templates import (
    ALL_EVENTS_BY_ROLE, PRESET_CATEGORIES, get_event_defaults,
)

router = APIRouter(tags=["notification-settings"])


# ───────────────────────────────────────────────────
# /users/me/interests (현재 사용자 편의 엔드포인트)
# ───────────────────────────────────────────────────

from app.security import get_current_user


@router.get("/users/me/interests")
def get_my_interests(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = getattr(current_user, "id", 0)
    items = db.query(UserInterest).filter(
        UserInterest.user_id == uid
    ).order_by(UserInterest.priority).all()
    return [
        {"value": i.value, "level": i.level, "source": i.source}
        for i in items
    ]


@router.post("/users/me/interests")
def set_my_interests(
    body: "InterestsBody",
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = getattr(current_user, "id", 0)
    if len(body.interests) > 10:
        raise HTTPException(400, "최대 10개까지 등록 가능합니다")

    db.query(UserInterest).filter(UserInterest.user_id == uid).delete()
    for i, item in enumerate(body.interests):
        val = item.value.strip()
        if not val:
            continue
        db.add(UserInterest(
            user_id=uid,
            role=body.role,
            level=item.level,
            value=val,
            source=item.source,
            priority=i,
        ))
    db.commit()
    return {"count": len(body.interests)}


# ───────────────────────────────────────────────────
# 관심 카테고리/제품/모델
# ───────────────────────────────────────────────────

class InterestItem(BaseModel):
    value: str
    level: str = "general"   # category / product / model / general
    source: str = "custom"   # preset / custom


class InterestsBody(BaseModel):
    interests: List[InterestItem]
    role: str = "buyer"


@router.get("/users/{user_id}/interests")
def get_interests(user_id: int, db: Session = Depends(get_db)):
    items = db.query(UserInterest).filter(
        UserInterest.user_id == user_id
    ).order_by(UserInterest.priority).all()
    return [
        {"value": i.value, "level": i.level, "source": i.source}
        for i in items
    ]


@router.post("/users/{user_id}/interests")
def set_interests(user_id: int, body: InterestsBody, db: Session = Depends(get_db)):
    role = body.role
    max_count = 10  # 전 역할 최대 10개

    if len(body.interests) > max_count:
        raise HTTPException(400, f"최대 {max_count}개까지 등록 가능합니다 ({role})")

    # 기존 삭제 후 재등록
    db.query(UserInterest).filter(UserInterest.user_id == user_id).delete()

    for i, item in enumerate(body.interests):
        val = item.value.strip()
        if not val:
            continue
        db.add(UserInterest(
            user_id=user_id,
            role=role,
            level=item.level,
            value=val,
            source=item.source,
            priority=i,
        ))

    db.commit()
    return {"count": len(body.interests)}


@router.get("/interests/presets")
def get_preset_categories():
    """프리셋 관심 카테고리 목록"""
    return {"categories": PRESET_CATEGORIES}


# ───────────────────────────────────────────────────
# 알림 설정 (채널 ON/OFF)
# ───────────────────────────────────────────────────

@router.get("/notification-settings/events")
def get_events_for_role(role: str = Query("buyer")):
    """역할별 이벤트 목록 + 기본 설정"""
    events = ALL_EVENTS_BY_ROLE.get(role, {})
    result = {}
    for key, evt in events.items():
        group = evt.get("group", "기타")
        result.setdefault(group, []).append({
            "key": key,
            "title": evt.get("title", key),
            "desc": evt.get("message", "")[:60],
            "default": evt.get("default", {"app": True, "push": False, "email": False}),
        })
    return result


@router.get("/notification-settings/{user_id}")
def get_notification_settings(user_id: int, db: Session = Depends(get_db)):
    """사용자의 알림 설정 조회"""
    rows = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == user_id
    ).all()
    return {
        r.event_type: {
            "app": r.channel_app,
            "push": r.channel_push,
            "email": r.channel_email,
        }
        for r in rows
    }


class SettingItem(BaseModel):
    event_type: str
    app: bool = True
    push: bool = False
    email: bool = False


class SaveSettingsBody(BaseModel):
    settings: List[SettingItem]


@router.post("/notification-settings/{user_id}")
def save_notification_settings(
    user_id: int,
    body: SaveSettingsBody,
    db: Session = Depends(get_db),
):
    """알림 설정 일괄 저장"""
    now = datetime.now(timezone.utc)

    for item in body.settings:
        existing = db.query(NotificationSetting).filter(
            NotificationSetting.user_id == user_id,
            NotificationSetting.event_type == item.event_type,
        ).first()

        if existing:
            existing.channel_app = item.app
            existing.channel_push = item.push
            existing.channel_email = item.email
            existing.updated_at = now
        else:
            db.add(NotificationSetting(
                user_id=user_id,
                event_type=item.event_type,
                channel_app=item.app,
                channel_push=item.push,
                channel_email=item.email,
                updated_at=now,
            ))

    db.commit()
    return {"ok": True, "count": len(body.settings)}


@router.post("/notification-settings/{user_id}/bulk")
def bulk_update_settings(
    user_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db),
):
    """전체 ON/OFF 등 일괄 업데이트
    body: {"channel": "app"|"push"|"email", "value": true|false, "role": "buyer"}
    """
    channel = body.get("channel", "app")
    value = body.get("value", True)
    role = body.get("role", "buyer")

    events = ALL_EVENTS_BY_ROLE.get(role, {})
    now = datetime.now(timezone.utc)

    col_map = {
        "app": "channel_app",
        "push": "channel_push",
        "email": "channel_email",
    }
    col = col_map.get(channel)
    if not col:
        raise HTTPException(400, "Invalid channel")

    for event_type in events:
        existing = db.query(NotificationSetting).filter(
            NotificationSetting.user_id == user_id,
            NotificationSetting.event_type == event_type,
        ).first()

        if existing:
            setattr(existing, col, value)
            existing.updated_at = now
        else:
            defaults = get_event_defaults(event_type, role)
            ns = NotificationSetting(
                user_id=user_id,
                event_type=event_type,
                channel_app=defaults.get("app", True),
                channel_push=defaults.get("push", False),
                channel_email=defaults.get("email", False),
                updated_at=now,
            )
            setattr(ns, col, value)
            db.add(ns)

    db.commit()
    return {"ok": True}
