# app/services/fcm_push.py
"""
Firebase Cloud Messaging (FCM) 푸시 알림 서비스.
환경변수: FIREBASE_CREDENTIALS (JSON 문자열) 또는 FIREBASE_CREDENTIALS_PATH (파일 경로)
미설정 시 발송 스킵.
"""
import os
import json
import logging

logger = logging.getLogger(__name__)

_app = None
_init_attempted = False


def _init_firebase():
    global _app, _init_attempted
    if _init_attempted:
        return
    _init_attempted = True

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        logger.warning("[FCM] firebase-admin 패키지 미설치 -> 푸시 비활성")
        return

    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    cred_path = os.environ.get("FIREBASE_CREDENTIALS_PATH")

    try:
        if cred_json:
            cred = credentials.Certificate(json.loads(cred_json))
        elif cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
        else:
            logger.info("[FCM] Firebase 미설정 -> 푸시 비활성")
            return

        _app = firebase_admin.initialize_app(cred)
        logger.info("[FCM] Firebase 초기화 완료")
    except Exception as e:
        logger.error("[FCM] Firebase 초기화 실패: %s", e)


def send_push(token: str, title: str, body: str, data: dict | None = None) -> bool:
    """단일 기기 푸시 발송."""
    _init_firebase()
    if not _app:
        logger.debug("[FCM] 비활성 상태 -> 스킵: %s", title)
        return False
    if not token:
        return False

    try:
        from firebase_admin import messaging
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=token,
        )
        result = messaging.send(message)
        logger.info("[FCM] 발송 성공: %s", result)
        return True
    except Exception as e:
        logger.warning("[FCM] 발송 실패: %s", e)
        return False


def send_push_multiple(tokens: list[str], title: str, body: str, data: dict | None = None) -> int:
    """여러 기기 동시 푸시."""
    _init_firebase()
    if not _app or not tokens:
        return 0

    try:
        from firebase_admin import messaging
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            tokens=tokens,
        )
        response = messaging.send_each_for_multicast(message)
        logger.info("[FCM] 다중 발송: 성공 %d, 실패 %d", response.success_count, response.failure_count)
        return response.success_count
    except Exception as e:
        logger.warning("[FCM] 다중 발송 실패: %s", e)
        return 0


# ── 알림 유형별 헬퍼 ─────────────────────────────────────────

def notify_new_offer(token: str, deal_title: str, seller_name: str):
    send_push(token, "새 오퍼가 도착했어요!", f"{seller_name}님이 '{deal_title}'에 오퍼를 제출했습니다.",
              {"type": "NEW_OFFER", "deal_title": deal_title})

def notify_offer_selected(token: str, deal_title: str):
    send_push(token, "오퍼가 선택되었어요!", f"'{deal_title}' 딜에서 고객님의 오퍼가 선택되었습니다.",
              {"type": "OFFER_SELECTED", "deal_title": deal_title})

def notify_shipping_complete(token: str, product_name: str):
    send_push(token, "배달 완료!", f"'{product_name}' 배송이 완료되었습니다. 수취 확인해주세요!",
              {"type": "DELIVERY_COMPLETE", "product": product_name})

def notify_settlement_ready(token: str, amount: int):
    send_push(token, "정산 준비 완료", f"{amount:,}원 정산이 준비되었습니다. 컨펌해주세요!",
              {"type": "SETTLEMENT_READY", "amount": str(amount)})

def notify_tax_invoice(token: str, amount: int):
    send_push(token, "세금계산서 발행", f"{amount:,}원 세금계산서가 발행되었습니다. 확인해주세요.",
              {"type": "TAX_INVOICE", "amount": str(amount)})

def notify_refund(token: str, amount: int):
    send_push(token, "환불 처리 완료", f"{amount:,}원이 환불 처리되었습니다.",
              {"type": "REFUND", "amount": str(amount)})

def notify_dispute(token: str, dispute_id: int):
    send_push(token, "분쟁 접수", f"분쟁 #{dispute_id}이 접수되었습니다.",
              {"type": "DISPUTE", "dispute_id": str(dispute_id)})

def notify_deal_match(token: str, deal_title: str, match_count: int):
    send_push(token, f"유사 딜방 {match_count}개 발견!", f"'{deal_title}' 비슷한 딜방이 있어요. 참여해보세요!",
              {"type": "DEAL_MATCH", "deal_title": deal_title})

def notify_spectator_result(token: str, is_correct: bool, points: int):
    if is_correct:
        send_push(token, "예측 적중!", f"축하합니다! {points}포인트 적립되었어요.",
                  {"type": "PREDICT_HIT", "points": str(points)})

def notify_nudge(token: str, product_name: str):
    send_push(token, f"'{product_name}' 딜방 만들어볼까요?", "관심 있는 제품이 있는 것 같아요!",
              {"type": "NUDGE", "product": product_name})

def notify_chat_message(token: str, sender_name: str, deal_title: str, snippet: str):
    send_push(token, f"{sender_name} ({deal_title})", snippet[:100],
              {"type": "CHAT_MESSAGE", "deal_title": deal_title})
