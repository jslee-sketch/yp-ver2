# app/routers/deal_chat_ws.py
"""
딜방 실시간 WebSocket 채팅.
/ws/chat/{deal_id} — 인증 후 양방향 메시지 교환.
메시지 유형: CHAT, TYPING, STOP_TYPING, READ, ONLINE_LIST, SYSTEM
"""
from __future__ import annotations

import html as _html
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException
from jose import JWTError, jwt

from app.database import SessionLocal
from app import models

logger = logging.getLogger(__name__)

router = APIRouter(tags=["deal_chat_ws"])


# ── JWT 검증 (WebSocket용) ─────────────────────────────────
def _verify_ws_token(token: str) -> dict:
    """JWT 토큰 디코딩. 실패 시 예외."""
    from app.security import SECRET_KEY, ALGORITHM
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise ValueError("Invalid token")


# ── 연결 관리자 ──────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        # deal_id -> list of {"ws": WebSocket, "user_id": int, "role": str, "nickname": str}
        self.rooms: dict[int, list[dict]] = {}

    async def connect(self, ws: WebSocket, deal_id: int, user_id: int, role: str, nickname: str):
        await ws.accept()
        if deal_id not in self.rooms:
            self.rooms[deal_id] = []
        self.rooms[deal_id].append({
            "ws": ws, "user_id": user_id, "role": role, "nickname": nickname,
        })
        # 입장 알림
        await self.broadcast(deal_id, {
            "type": "SYSTEM",
            "message": f"{nickname}님이 입장했습니다.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "online_count": len(self.rooms[deal_id]),
        })

    def disconnect(self, ws: WebSocket, deal_id: int) -> str | None:
        nickname = None
        if deal_id in self.rooms:
            for c in self.rooms[deal_id]:
                if c["ws"] is ws:
                    nickname = c["nickname"]
                    break
            self.rooms[deal_id] = [c for c in self.rooms[deal_id] if c["ws"] is not ws]
            if not self.rooms[deal_id]:
                del self.rooms[deal_id]
        return nickname

    async def broadcast(self, deal_id: int, message: dict, exclude_user: int | None = None):
        if deal_id not in self.rooms:
            return
        dead = []
        for conn in self.rooms[deal_id]:
            if exclude_user is not None and conn["user_id"] == exclude_user:
                continue
            try:
                await conn["ws"].send_json(message)
            except Exception:
                dead.append(conn["ws"])
        # 죽은 연결 정리
        if dead:
            self.rooms[deal_id] = [c for c in self.rooms[deal_id] if c["ws"] not in dead]

    def get_online_users(self, deal_id: int) -> list[dict]:
        if deal_id not in self.rooms:
            return []
        seen = set()
        result = []
        for c in self.rooms[deal_id]:
            if c["user_id"] not in seen:
                seen.add(c["user_id"])
                result.append({"user_id": c["user_id"], "nickname": c["nickname"], "role": c["role"]})
        return result


manager = ConnectionManager()


# ── WebSocket 엔드포인트 ─────────────────────────────────────
@router.websocket("/ws/chat/{deal_id}")
async def websocket_chat(ws: WebSocket, deal_id: int):
    """딜방 실시간 채팅 WebSocket."""

    # 1) 첫 메시지로 인증
    try:
        await ws.accept()
        auth_raw = await ws.receive_text()
        auth_msg = json.loads(auth_raw)
        token = auth_msg.get("token", "")
        if not token:
            await ws.send_json({"type": "ERROR", "message": "토큰이 필요합니다"})
            await ws.close(code=4001, reason="토큰 필요")
            return

        payload = _verify_ws_token(token)
        user_id = int(payload.get("sub", 0))
        role = payload.get("role", "buyer")
        if user_id <= 0:
            await ws.send_json({"type": "ERROR", "message": "유효하지 않은 토큰"})
            await ws.close(code=4001, reason="유효하지 않은 토큰")
            return

    except (json.JSONDecodeError, ValueError, Exception) as e:
        try:
            await ws.send_json({"type": "ERROR", "message": "인증 실패"})
            await ws.close(code=4001, reason="인증 실패")
        except Exception:
            pass
        return

    # 닉네임 조회
    nickname = f"User{user_id}"
    try:
        db = SessionLocal()
        if role == "seller":
            row = db.query(models.Seller).get(user_id)
            nickname = getattr(row, "nickname", None) or getattr(row, "business_name", "") or nickname
        elif role == "actuator":
            row = db.query(models.Actuator).get(user_id)
            nickname = getattr(row, "nickname", None) or getattr(row, "name", "") or nickname
        else:
            row = db.query(models.Buyer).get(user_id)
            nickname = getattr(row, "nickname", None) or getattr(row, "name", "") or nickname
        db.close()
    except Exception:
        pass

    # 2) 연결 등록 (accept은 이미 완료됨 → broadcast만)
    if deal_id not in manager.rooms:
        manager.rooms[deal_id] = []
    manager.rooms[deal_id].append({
        "ws": ws, "user_id": user_id, "role": role, "nickname": nickname,
    })
    await manager.broadcast(deal_id, {
        "type": "SYSTEM",
        "message": f"{nickname}님이 입장했습니다.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "online_count": len(manager.rooms.get(deal_id, [])),
    })

    # 인증 성공 응답
    await ws.send_json({
        "type": "AUTH_OK",
        "user_id": user_id,
        "nickname": nickname,
        "role": role,
        "online_count": len(manager.rooms.get(deal_id, [])),
    })

    # 3) 메시지 루프
    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "CHAT")

            if msg_type == "CHAT":
                content = _html.escape((data.get("message") or "").strip())
                if not content:
                    continue

                # DB 저장
                chat_id = None
                try:
                    db = SessionLocal()
                    chat = models.DealChatMessage(
                        deal_id=deal_id,
                        buyer_id=user_id,
                        text=content,
                    )
                    db.add(chat)
                    db.commit()
                    db.refresh(chat)
                    chat_id = chat.id
                    db.close()
                except Exception as e:
                    logger.warning("채팅 DB 저장 실패: %s", e)

                await manager.broadcast(deal_id, {
                    "type": "CHAT",
                    "user_id": user_id,
                    "nickname": nickname,
                    "role": role,
                    "message": content,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "chat_id": chat_id,
                })

            elif msg_type == "TYPING":
                await manager.broadcast(deal_id, {
                    "type": "TYPING",
                    "user_id": user_id,
                    "nickname": nickname,
                }, exclude_user=user_id)

            elif msg_type == "STOP_TYPING":
                await manager.broadcast(deal_id, {
                    "type": "STOP_TYPING",
                    "user_id": user_id,
                }, exclude_user=user_id)

            elif msg_type == "READ":
                chat_id = data.get("chat_id")
                await manager.broadcast(deal_id, {
                    "type": "READ",
                    "user_id": user_id,
                    "chat_id": chat_id,
                }, exclude_user=user_id)

            elif msg_type == "ONLINE_LIST":
                users = manager.get_online_users(deal_id)
                await ws.send_json({
                    "type": "ONLINE_LIST",
                    "users": users,
                    "count": len(users),
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket 오류 (deal=%d, user=%d): %s", deal_id, user_id, e)
    finally:
        nickname_left = manager.disconnect(ws, deal_id)
        if nickname_left:
            await manager.broadcast(deal_id, {
                "type": "SYSTEM",
                "message": f"{nickname_left}님이 퇴장했습니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "online_count": len(manager.rooms.get(deal_id, [])),
            })
