# app/routers/deal_chat.py
from __future__ import annotations

from datetime import datetime
from io import StringIO
import csv
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, crud
from app.routers.notifications import create_notification

router = APIRouter(
    prefix="/deals",
    tags=["deal_chat"],
)

# ============================================================
# 공통 에러 변환 헬퍼
# ============================================================
def _xlate(e: Exception):
    # crud 모듈 내부의 예외 클래스를 HTTPException 으로 변환
    if isinstance(e, crud.NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, crud.ConflictError):
        raise HTTPException(status_code=409, detail=str(e))
    # 모르는 예외는 그대로 터뜨려서 500
    raise e


# ============================================================
# Pydantic 스키마
# ============================================================
class DealChatMessageCreate(BaseModel):
    buyer_id: int
    text: str


class DealChatMessageOut(BaseModel):
    id: int
    deal_id: int
    buyer_id: int
    sender_nickname: str
    text: str
    blocked: bool
    blocked_reason: Optional[str] = None
    created_at: datetime

    class Config:
        orm_mode = True  # Pydantic v1 스타일 (경고만 뜨고 동작은 함)


class DealChatMessageListOut(BaseModel):
    items: List[DealChatMessageOut]
    total: int


# 닉네임 만들기 (crud 쪽에 get_buyer_nickname 이 있으면 그거 우선 사용)
def _make_display_name(db: Session, buyer_id: int) -> str:
    if hasattr(crud, "get_buyer_nickname"):
        return crud.get_buyer_nickname(db, buyer_id)

    buyer = db.get(models.Buyer, buyer_id)
    if not buyer:
        return f"buyer-{buyer_id}"

    nick = getattr(buyer, "nickname", None)
    if nick:
        return nick

    return f"buyer-{buyer_id}"


# ============================================================
# 1) 메시지 생성
# ============================================================
@router.post(
    "/{deal_id}/chat/messages",
    response_model=DealChatMessageOut,
    summary="딜 채팅 메시지 작성",
)
def api_create_deal_chat_message(
    deal_id: int,
    body: DealChatMessageCreate,
    db: Session = Depends(get_db),
):
    """
    - 딜 참가자만 작성 가능 (DealParticipant 체크)
    - 욕설/전화번호/계좌번호 등은 `blocked=True` 로 저장하고 reason 기록
    - 메시지 생성 후, 같은 딜의 다른 참여자들에게 알림(Notification) 생성
    - ❗ 딜 상태가 open 이 아닐 경우: 채팅 작성 불가 (read-only)
    """
    try:
        # 0) 딜 상태 체크: open 일 때만 작성 허용
        deal = db.get(models.Deal, deal_id)
        if not deal:
            raise HTTPException(status_code=404, detail="Deal not found")

        status = (getattr(deal, "status", None) or "open").lower()
        if status != "open":
            # 딜 마감 이후에는 write 금지, read-only
            raise HTTPException(
                status_code=409,
                detail=f"deal chat is read-only (status={status})",
            )

        # 1) 메시지 생성
        msg = crud.create_deal_chat_message(
            db,
            deal_id=deal_id,
            buyer_id=body.buyer_id,
            text=body.text,
        )

        # 2) 표시용 닉네임
        sender_nickname = _make_display_name(db, body.buyer_id)

        # 2-1) 🔐 차단된 메시지는 알림을 보내지 않음
        if msg.blocked:
            return DealChatMessageOut(
                id=msg.id,
                deal_id=msg.deal_id,
                buyer_id=msg.buyer_id,
                sender_nickname=sender_nickname,
                text=msg.text,
                blocked=msg.blocked,
                blocked_reason=msg.blocked_reason,
                created_at=msg.created_at,
            )

        # 3) 🔔 알림 생성 트리거
        #    - 동일 딜의 다른 참여자(buyer)에게만 알림 생성
        try:
            participants = (
                db.query(models.DealParticipant)
                  .filter(models.DealParticipant.deal_id == deal_id)
                  .all()
            )

            # snippet 은 body.text 대신, 실제 저장된 msg.text 기준으로
            snippet = (msg.text or "").strip()
            if len(snippet) > 50:
                snippet = snippet[:50] + "..."

            for p in participants:
                target_buyer_id = int(getattr(p, "buyer_id", 0) or 0)
                if target_buyer_id <= 0:
                    continue
                if target_buyer_id == body.buyer_id:
                    continue  # 자기 자신은 알림 제외

                create_notification(
                    db,
                    user_id=target_buyer_id,
                    type="deal_chat_message",
                    title=f"딜 #{deal_id} 새 채팅 메시지",
                    message=f"{sender_nickname}: {snippet}",
                    meta={
                        "role": "buyer",
                        "deal_id": deal_id,
                        "sender_buyer_id": body.buyer_id,
                        "chat_message_id": msg.id,
                    },
                )
        except Exception as notify_err:
            # 알림 실패로 채팅이 막히면 안 되므로, 로그만 찍고 무시
            import logging
            logging.exception(
                "failed to create deal_chat notification",
                exc_info=notify_err,
            )

        # 4) 응답
        return DealChatMessageOut(
            id=msg.id,
            deal_id=msg.deal_id,
            buyer_id=msg.buyer_id,
            sender_nickname=sender_nickname,
            text=msg.text,
            blocked=msg.blocked,
            blocked_reason=msg.blocked_reason,
            created_at=msg.created_at,
        )
    except Exception as e:
        _xlate(e)

# ============================================================
# 2) 메시지 목록 조회
# ============================================================
@router.get(
    "/{deal_id}/chat/messages",
    response_model=DealChatMessageListOut,
    summary="딜 채팅 메시지 목록 조회",
)
def api_list_deal_chat_messages(
    deal_id: int,
    buyer_id: int = Query(..., description="요청하는 buyer_id (참여자인지 확인용)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, description="검색어 (텍스트 LIKE 검색)"),
    db: Session = Depends(get_db),
):
    """
    - 딜 참가자(buyer)만 읽기 가능
    - 최신 순 정렬(id desc)
    - q 가 있으면 내용 LIKE 검색
    """
    try:
        items, total = crud.list_deal_chat_messages(
            db,
            deal_id=deal_id,
            buyer_id=buyer_id,
            limit=limit,
            offset=offset,
            q=q,
        )

        out_items: List[DealChatMessageOut] = []
        for m in items:
            sender_nickname = _make_display_name(db, m.buyer_id)
            out_items.append(
                DealChatMessageOut(
                    id=m.id,
                    deal_id=m.deal_id,
                    buyer_id=m.buyer_id,
                    sender_nickname=sender_nickname,
                    text=m.text,
                    blocked=m.blocked,
                    blocked_reason=m.blocked_reason,
                    created_at=m.created_at,
                )
            )

        return DealChatMessageListOut(items=out_items, total=total)
    except Exception as e:
        _xlate(e)


# ============================================================
# 3) 메시지 CSV 다운로드 (운영/분쟁 대응용)
# ============================================================
@router.get(
    "/{deal_id}/chat/messages/export",
    summary="딜 채팅 메시지 CSV 다운로드",
    response_class=Response,
    responses={
        200: {
            "description": "CSV file",
            "content": {
                "text/csv": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        },
        422: {"description": "Validation Error"},
    },
)
def api_export_deal_chat_messages(
    deal_id: int,
    buyer_id: int = Query(..., description="요청하는 buyer_id (참여자인지 확인용)"),
    q: Optional[str] = Query(None, description="검색어 (텍스트 LIKE 검색)"),
    db: Session = Depends(get_db),
):
    """
    - 딜 참가자 여부 체크: list_deal_chat_messages 재사용
    - 전체 메시지를 한 번에 CSV로 만들어서 응답
    - UTF-8 + BOM 으로 저장해서 엑셀에서 한글 안 깨지게 처리
    """
    try:
        # 참여자 체크 + 메시지 가져오기
        items, _ = crud.list_deal_chat_messages(
            db,
            deal_id=deal_id,
            buyer_id=buyer_id,
            limit=10_000,
            offset=0,
            q=q,
        )

        buf = StringIO()
        writer = csv.writer(buf)

        # 헤더
        writer.writerow(
            [
                "id",
                "deal_id",
                "buyer_id",
                "sender_nickname",
                "text",
                "blocked",
                "blocked_reason",
                "created_at",
            ]
        )

        # 데이터 행
        for m in items:
            nickname = _make_display_name(db, m.buyer_id)

            raw_text = m.text or ""
            safe_text = raw_text
            # 전부 숫자로만 구성된 경우 → 엑셀에서 지수표기로 바뀌지 않게 ' 프리픽스
            if raw_text.isdigit():
                safe_text = "'" + raw_text

            writer.writerow(
                [
                    m.id,
                    m.deal_id,
                    m.buyer_id,
                    nickname,
                    safe_text,
                    bool(m.blocked),
                    m.blocked_reason or "",
                    m.created_at.isoformat() if m.created_at else "",
                ]
            )

        csv_text = buf.getvalue()
        buf.close()

        # 엑셀 한글 깨짐 방지를 위한 BOM 추가
        csv_bytes = ("\ufeff" + csv_text).encode("utf-8-sig")

        filename = f"deal_{deal_id}_chat_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.csv"

        return Response(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except Exception as e:
        _xlate(e)