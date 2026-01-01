# app/routers/notifications.py
from __future__ import annotations

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Path,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from pydantic import BaseModel

router = APIRouter(prefix="/notifications", tags=["notifications"])

# ─────────────────────────────
# 🔔 응답용 스키마 (로컬에서 사용)
# ─────────────────────────────
class NotificationOut(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    message: str
    link_url: Optional[str] = None
    event_time: Optional[datetime] = None
    created_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    is_read: bool
    # DB 에서는 TEXT 이므로 우선 문자열로
    meta_json: Optional[str] = None

    class Config:
        orm_mode = True  # SQLAlchemy 모델 → 자동 변환 허용


# -------------------------------------------------------
# 내부 헬퍼: meta_json <-> dict
# -------------------------------------------------------
def _meta_from_json(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def _meta_to_json(meta: Optional[Dict[str, Any]]) -> Optional[str]:
    if not meta:
        return None
    try:
        return json.dumps(meta, ensure_ascii=False)
    except Exception:
        return None


# -------------------------------------------------------
# 🔔 공용 헬퍼: 알림 생성 (다른 라우터에서 import 해서 사용)
# -------------------------------------------------------
def create_notification(
    db: Session,
    *,
    user_id: int,
    type: str,
    title: str,
    message: str,
    link_url: Optional[str] = None,
    event_time: Optional[datetime] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> models.UserNotification:
    """
    다른 라우터(offers, reservations, reviews 등)에서 호출하는 공용 헬퍼.
    """
    if user_id <= 0:
        raise ValueError("user_id must be > 0")

    now = datetime.now(timezone.utc)
    if event_time is None:
        event_time = now

    meta_json = _meta_to_json(meta)

    notif = models.UserNotification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        link_url=link_url,
        event_time=event_time,
        meta_json=meta_json,
        # created_at, is_read, read_at 은 default / server_default 사용
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


# -------------------------------------------------------
# 1️⃣ 유저 타입 + ID 로 알림 조회
#     GET /notifications/buyer/1
#     GET /notifications/seller/1
#     GET /notifications/actuator/1
# -------------------------------------------------------
@router.get(
    "/{user_type}/{user_id}",
    response_model=List[NotificationOut],
    summary="유저 알림 목록 조회",
)
def api_list_notifications_for_user(
    user_type: str = Path(..., description="buyer / seller / actuator"),
    user_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    테스트용 단순 버전:
    - user_type 은 지금은 필터에 쓰지 않고, user_id 기준으로만 조회.
    - 나중에 meta_json 등에 role 넣어서 필터링을 추가할 수 있음.
    """
    try:
        q = (
            db.query(models.UserNotification)
              .filter(models.UserNotification.user_id == user_id)
              .order_by(models.UserNotification.created_at.desc())
              .limit(50)
        )
        return q.all()
    except Exception as e:
        # 디버그 편하게 에러 문구 그대로 노출
        raise HTTPException(status_code=500, detail=f"list_error: {e}")


# -------------------------------------------------------
# 2️⃣ 쿼리 파라미터로 내 알림 목록 조회
#     GET /notifications?user_id=1&only_unread=true
# -------------------------------------------------------
@router.get(
    "",
    response_model=List[NotificationOut],
    summary="내 알림 목록 조회 (user_id 쿼리)",
)
def list_notifications(
    user_id: int = Query(..., ge=1, description="알림을 조회할 사용자 ID"),
    only_unread: bool = Query(
        False,
        description="true 이면 읽지 않은 알림만 조회",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=200,
        description="가져올 최대 개수 (최대 200)",
    ),
    db: Session = Depends(get_db),
):
    q = db.query(models.UserNotification).filter(
        models.UserNotification.user_id == user_id
    )
    if only_unread:
        q = q.filter(models.UserNotification.is_read == False)  # noqa: E712

    rows = (
        q.order_by(models.UserNotification.created_at.desc())
         .limit(limit)
         .all()
    )
    return rows


# -------------------------------------------------------
# 3️⃣ 단일 알림 읽음 처리
#     POST /notifications/{notification_id}/read?user_id=1
# -------------------------------------------------------
@router.post(
    "/{notification_id}/read",
    response_model=NotificationOut,
    summary="알림 하나 읽음 처리",
)
def api_mark_notification_read(
    notification_id: int = Path(..., ge=1),
    user_id: int = Query(..., ge=1, description="이 알림의 주인 user_id"),
    db: Session = Depends(get_db),
):
    notif = db.query(models.UserNotification).get(notification_id)
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    if int(getattr(notif, "user_id", 0) or 0) != int(user_id):
        raise HTTPException(
            status_code=409,
            detail="not owner of this notification",
        )

    if not getattr(notif, "is_read", False):
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        db.add(notif)
        db.commit()
        db.refresh(notif)

    return notif


# -------------------------------------------------------
# 4️⃣ 내 알림 전체 읽음 처리
#     POST /notifications/read_all
#     body: { "user_id": 1 }
# -------------------------------------------------------
class ReadAllIn(BaseModel):
    user_id: int


@router.post(
    "/read_all",
    summary="내 알림 전체 읽음 처리",
)
def mark_all_notifications_read(
    body: ReadAllIn,
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    q = db.query(models.UserNotification).filter(
        models.UserNotification.user_id == body.user_id,
        models.UserNotification.is_read == False,  # noqa: E712
    )

    try:
        updated = q.update(
            {
                models.UserNotification.is_read: True,
                models.UserNotification.read_at: now,
            },
            synchronize_session=False,
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logging.exception("mark_all_notifications_read failed", exc_info=e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"failed to update notifications: {e}",
        )

    return {"updated": int(updated)}


# -------------------------------------------------------
# 5️⃣ [DEV] 간단 Seed (현재 스키마에 맞게)
#     POST /notifications/dev/seed
# -------------------------------------------------------
@router.post(
    "/dev/seed",
    summary="[DEV] 테스트용 알림 3개 생성",
)
def api_seed_notifications(
    db: Session = Depends(get_db),
):
    """
    개발용:
    - user_id=1 에 테스트 알림 3개 생성
    """
    now = datetime.now(timezone.utc)

    samples = [
        dict(
            user_id=1,
            type="deal_deadline_soon",
            title="참여 딜 마감 1시간 전",
            message="참여한 딜 #1 이 1시간 후 마감됩니다.",
            meta={"role": "buyer", "deal_id": 1},
        ),
        dict(
            user_id=1,
            type="offer_reservation_created",
            title="내 오퍼에 예약이 들어왔어요",
            message="오퍼 #1 에 새 예약이 1건 발생했습니다.",
            meta={"role": "seller", "offer_id": 1, "reservation_id": 1},
        ),
        dict(
            user_id=1,
            type="seller_onboarded",
            title="추천한 셀러가 가입을 완료했어요",
            message="추천한 셀러 #1 이 승인되었습니다.",
            meta={"role": "actuator", "seller_id": 1},
        ),
    ]

    created_ids: List[int] = []

    for s in samples:
        notif = create_notification(
            db,
            user_id=s["user_id"],
            type=s["type"],
            title=s["title"],
            message=s["message"],
            event_time=now,
            meta=s["meta"],
        )
        created_ids.append(notif.id)

    return {"created": created_ids}