# app/services/notification_templates.py
"""알림 이벤트 정의 + 메시지 템플릿 (57개 이벤트 + 7개 관리자)"""
from __future__ import annotations
import re

# ══════════════════════════════════════════════════════
# 이벤트별 기본 채널 설정 + 메시지 템플릿
# ══════════════════════════════════════════════════════

BUYER_EVENTS = {
    "DEAL_NEW_PARTICIPANT":     {"title": "새 참여자 합류! 👋",           "message": "'{product_name}' 딜에 새 참여자가 합류했어요. 현재 {participant_count}명 참여 중!", "link": "/deal/{deal_id}", "default": {"app": True, "push": True, "email": False}, "group": "딜"},
    "DEAL_INFO_CHANGED":        {"title": "딜 정보가 변경되었어요 📝",     "message": "'{product_name}' 딜의 정보가 변경되었어요. 확인해보세요!", "link": "/deal/{deal_id}", "default": {"app": True, "push": True, "email": False}, "group": "딜"},
    "DEAL_NEW_CHAT":            {"title": "새 채팅 💬",                   "message": "'{product_name}' 딜방에 새 메시지가 도착했어요.", "link": "/deal/{deal_id}", "default": {"app": True, "push": False, "email": False}, "group": "딜"},
    "DEAL_CLOSED":              {"title": "딜이 마감되었어요 🔒",          "message": "'{product_name}' 딜이 마감되었습니다. 결과를 확인해보세요!", "link": "/deal/{deal_id}", "default": {"app": True, "push": True, "email": False}, "group": "딜"},
    "DEAL_OFFER_STARTED":       {"title": "오퍼 접수 시작! 🎉",           "message": "'{product_name}' 딜에 오퍼 접수가 시작되었어요!", "link": "/deal/{deal_id}", "default": {"app": True, "push": True, "email": False}, "group": "딜"},

    "OFFER_ARRIVED":            {"title": "새 오퍼 도착! 📩",             "message": "'{product_name}' 딜에 {seller_name}님이 {offer_price}원에 오퍼를 제출했어요!", "link": "/deal/{deal_id}", "default": {"app": True, "push": True, "email": False}, "group": "오퍼"},
    "OFFER_DEADLINE_SOON":      {"title": "오퍼 마감 임박 ⏰",            "message": "'{product_name}' 딜 오퍼 마감까지 {remaining_time} 남았어요!", "link": "/deal/{deal_id}", "default": {"app": True, "push": True, "email": False}, "group": "오퍼"},

    "PAYMENT_COMPLETE":         {"title": "결제 완료! ✅",                "message": "'{product_name}' {amount}원 결제가 완료되었습니다. 주문번호: {order_number}", "link": "/my-orders", "default": {"app": True, "push": False, "email": True}, "group": "예약/결제"},
    "RESERVATION_CONFIRMED":    {"title": "예약이 확정되었어요! 🎊",       "message": "{seller_name}님이 '{product_name}' 예약을 확정했습니다.", "link": "/my-orders", "default": {"app": True, "push": True, "email": False}, "group": "예약/결제"},

    "SHIPPING_STARTED":         {"title": "배송이 시작되었어요! 🚚",       "message": "'{product_name}' 상품이 발송되었습니다. 택배사: {courier}, 운송장: {tracking_number}", "link": "/my-orders", "default": {"app": True, "push": True, "email": False}, "group": "배송"},
    "DELIVERY_COMPLETE":        {"title": "배달 완료! 📦",                "message": "'{product_name}' 배달이 완료되었습니다. 수취 확인을 해주세요!", "link": "/my-orders", "default": {"app": True, "push": True, "email": False}, "group": "배송"},
    "AUTO_CONFIRM_SOON":        {"title": "내일 자동 구매확정 ⏳",         "message": "'{product_name}' 주문이 내일 자동 구매확정됩니다.", "link": "/my-orders", "default": {"app": True, "push": True, "email": False}, "group": "배송"},
    "PURCHASE_CONFIRMED":       {"title": "구매확정 완료 ✅",              "message": "'{product_name}' 구매가 확정되었습니다. 리뷰를 남겨주세요!", "link": "/my-orders", "default": {"app": True, "push": False, "email": False}, "group": "배송"},

    "REFUND_COMPLETE":          {"title": "환불 처리 완료 💸",             "message": "'{product_name}' {refund_amount}원 환불이 처리되었습니다.", "link": "/my-orders", "default": {"app": True, "push": True, "email": True}, "group": "환불/분쟁"},
    "RETURN_EXCHANGE_UPDATE":   {"title": "반품/교환 진행 상황 📋",        "message": "'{product_name}' 반품/교환 상태가 변경되었습니다.", "link": "/my-orders", "default": {"app": True, "push": True, "email": False}, "group": "환불/분쟁"},
    "DISPUTE_FILED":            {"title": "분쟁이 접수되었어요 ⚖️",        "message": "'{product_name}' 분쟁이 접수되었습니다. 관리자가 검토합니다.", "link": "/my-orders", "default": {"app": True, "push": True, "email": True}, "group": "환불/분쟁"},
    "DISPUTE_SELLER_RESPONSE":  {"title": "판매자 이의제기 도착 📨",       "message": "'{product_name}' 분쟁에 대해 판매자가 이의를 제기했습니다.", "link": "/my-orders", "default": {"app": True, "push": True, "email": True}, "group": "환불/분쟁"},
    "DISPUTE_RESULT":           {"title": "분쟁 결과 통보 📋",             "message": "'{product_name}' 분쟁 결과: {result}.", "link": "/my-orders", "default": {"app": True, "push": True, "email": True}, "group": "환불/분쟁"},

    "POINTS_EARNED":            {"title": "포인트 적립! 🎯",              "message": "{earned_points}포인트가 적립되었어요! 현재 잔액: {total_points}pt", "link": "/points", "default": {"app": True, "push": False, "email": False}, "group": "포인트/등급"},
    "GRADE_CHANGED":            {"title": "등급이 변경되었어요! 🏅",       "message": "{old_grade} → {new_grade}(으)로 등급이 변경되었어요!", "link": "/my", "default": {"app": True, "push": True, "email": False}, "group": "포인트/등급"},
    "SPECTATOR_PREDICT_RESULT": {"title": "예측 결과 발표! 🎯",            "message": "'{product_name}' 딜 예측 결과: {result}! {points_change}", "link": "/spectating", "default": {"app": True, "push": False, "email": False}, "group": "포인트/등급"},

    "NUDGE_INTEREST_DEAL":      {"title": "관심 상품 딜방 오픈! 💡",       "message": "관심 등록하신 '{matched_interest}' 관련 '{product_name}' 딜이 생성되었어요!", "link": "/deal/{deal_id}", "default": {"app": True, "push": True, "email": False}, "group": "매칭"},
    "REFERRAL_SIGNUP":          {"title": "추천 친구 가입! 🎉",            "message": "{referred_name}님이 내 추천으로 가입했어요! {reward_points}포인트 적립!", "link": "/my", "default": {"app": True, "push": True, "email": False}, "group": "매칭"},

    "B_ANNOUNCEMENT":           {"title": "📢 공지사항",                   "message": "{announcement_preview}", "link": "/support", "default": {"app": True, "push": False, "email": False}, "group": "시스템"},
}

SELLER_EVENTS = {
    "DEAL_MATCH_INTEREST":      {"title": "관심 상품 딜 등록! 🔔",        "message": "'{matched_interest}' 관련 '{product_name}' 딜이 생성되었어요! 목표가: {target_price}원. 오퍼를 제출해보세요!", "link": "/deal/{deal_id}", "default": {"app": True, "push": True, "email": False}, "group": "딜/오퍼 매칭"},
    "OFFER_SELECTED":           {"title": "오퍼가 선택되었어요! 🎊",       "message": "'{product_name}' 딜에서 {offer_price}원 오퍼가 낙찰되었습니다!", "link": "/seller/offers", "default": {"app": True, "push": True, "email": False}, "group": "딜/오퍼 매칭"},
    "OFFER_NOT_SELECTED":       {"title": "오퍼 미선택 😢",               "message": "'{product_name}' 딜에서 다른 오퍼가 선택되었어요.", "link": "/seller/offers", "default": {"app": True, "push": False, "email": False}, "group": "딜/오퍼 매칭"},

    "ORDER_RECEIVED":           {"title": "새 주문 접수! 📦",              "message": "'{product_name}' {quantity}개 주문이 접수되었습니다. 금액: {amount}원. 발송해주세요!", "link": "/seller/delivery", "default": {"app": True, "push": True, "email": True}, "group": "주문/배송"},
    "SHIPPING_REMINDER":        {"title": "발송 요청 🚚",                  "message": "'{product_name}' 주문 발송을 아직 처리하지 않으셨어요.", "link": "/seller/delivery", "default": {"app": True, "push": True, "email": False}, "group": "주문/배송"},

    "S_SETTLEMENT_READY":       {"title": "정산 준비 완료! 💰",            "message": "정산 S-{settlement_id} ({amount}원)이 준비되었습니다.", "link": "/seller/settlements", "default": {"app": True, "push": True, "email": True}, "group": "정산"},
    "SETTLEMENT_APPROVED":      {"title": "정산 승인됨 ✅",                "message": "정산 S-{settlement_id} ({amount}원)이 승인되었습니다.", "link": "/seller/settlements", "default": {"app": True, "push": True, "email": False}, "group": "정산"},
    "S_SETTLEMENT_PAID":        {"title": "정산 입금 완료! 💰",            "message": "정산 S-{settlement_id} ({payout_amount}원)이 계좌에 입금되었습니다!", "link": "/seller/settlements", "default": {"app": True, "push": True, "email": True}, "group": "정산"},
    "S_TAX_INVOICE_CONFIRM":    {"title": "세금계산서 확인 요청 🧾",       "message": "세금계산서 TI-{invoice_id} 확인이 필요합니다.", "link": "/seller/tax-invoices", "default": {"app": True, "push": True, "email": True}, "group": "정산"},
    "S_TAX_INVOICE_ISSUED":     {"title": "세금계산서 발행 완료 🧾",       "message": "세금계산서 TI-{invoice_id}가 발행되었습니다.", "link": "/seller/tax-invoices", "default": {"app": True, "push": False, "email": True}, "group": "정산"},

    "REFUND_REQUESTED":         {"title": "환불 요청 접수 💸",             "message": "'{product_name}' 주문에 환불 요청이 접수되었습니다. 사유: {refund_reason}", "link": "/seller/refunds", "default": {"app": True, "push": True, "email": True}, "group": "환불/분쟁"},
    "RETURN_EXCHANGE_REQUESTED":{"title": "반품/교환 요청 📦↩️",           "message": "'{product_name}' 반품/교환 요청이 접수되었습니다.", "link": "/seller/refunds", "default": {"app": True, "push": True, "email": True}, "group": "환불/분쟁"},
    "S_REFUND_RETURN_UPDATE":   {"title": "환불/반품 상태 변경 📋",        "message": "'{product_name}' 환불/반품 상태가 변경되었습니다.", "link": "/seller/refunds", "default": {"app": True, "push": True, "email": False}, "group": "환불/분쟁"},
    "S_DISPUTE_RECEIVED":       {"title": "분쟁 접수 ⚠️",                 "message": "'{product_name}' 주문에 구매자가 분쟁을 접수했습니다.", "link": "/seller/refunds", "default": {"app": True, "push": True, "email": True}, "group": "환불/분쟁"},
    "S_DISPUTE_RESULT":         {"title": "분쟁 결과 ⚖️",                 "message": "'{product_name}' 분쟁 결과: {result}.", "link": "/seller/refunds", "default": {"app": True, "push": True, "email": True}, "group": "환불/분쟁"},

    "NEW_REVIEW":               {"title": "새 리뷰가 작성되었어요 ⭐",     "message": "{buyer_name}님이 '{product_name}'에 리뷰를 남겼어요.", "link": "/seller/reviews", "default": {"app": True, "push": True, "email": False}, "group": "리뷰"},
    "LEVEL_CHANGED":            {"title": "판매자 레벨 변경! 📊",          "message": "Lv.{old_level} → Lv.{new_level} 변경! 수수료율: {old_fee}% → {new_fee}%", "link": "/seller", "default": {"app": True, "push": True, "email": False}, "group": "레벨"},

    "BUYER_MESSAGE":            {"title": "구매자 메시지 📧",              "message": "{buyer_name}님이 메시지를 보냈어요.", "link": "/seller/inquiries", "default": {"app": True, "push": True, "email": False}, "group": "소통"},
    "S_DEAL_CHAT_MESSAGE":      {"title": "딜방 채팅 💬",                  "message": "'{product_name}' 딜방에 새 메시지가 도착했어요.", "link": "/deal/{deal_id}", "default": {"app": True, "push": False, "email": False}, "group": "소통"},

    "S_ANNOUNCEMENT":           {"title": "📢 공지사항",                   "message": "{announcement_preview}", "link": "/seller/announcements", "default": {"app": True, "push": False, "email": False}, "group": "시스템"},
    "SELLER_APPROVED":          {"title": "판매자 승인 완료! 🎉",          "message": "축하합니다! 판매자로 승인되었어요. 오퍼를 제출할 수 있습니다!", "link": "/seller", "default": {"app": True, "push": True, "email": True}, "group": "시스템"},
    "S_ACCOUNT_WARNING":        {"title": "계정 경고 ⚠️",                 "message": "계정에 경고가 발생했습니다. 사유: {warning_reason}", "link": "/settings", "default": {"app": True, "push": True, "email": True}, "group": "시스템"},
}

ACTUATOR_EVENTS = {
    "COMMISSION_EARNED":        {"title": "커미션 발생! 💰",              "message": "{recruited_seller}님의 '{product_name}' 거래 성사! 커미션 {commission_amount}원 발생.", "link": "/actuator/commissions", "default": {"app": True, "push": True, "email": False}, "group": "커미션/정산"},
    "A_SETTLEMENT_READY":       {"title": "커미션 정산 준비 완료 💰",     "message": "정산 S-{settlement_id} ({amount}원) 컨펌이 필요합니다.", "link": "/actuator/commissions", "default": {"app": True, "push": True, "email": True}, "group": "커미션/정산"},
    "A_SETTLEMENT_PAID":        {"title": "커미션 입금 완료! 💰",         "message": "커미션 {payout_amount}원이 입금되었습니다!", "link": "/actuator/commissions", "default": {"app": True, "push": True, "email": True}, "group": "커미션/정산"},
    "A_TAX_INVOICE_CONFIRM":    {"title": "세금계산서 확인 🧾",           "message": "세금계산서 TI-{invoice_id} 확인이 필요합니다.", "link": "/actuator/commissions", "default": {"app": True, "push": True, "email": True}, "group": "커미션/정산"},
    "WITHHOLDING_RECEIPT":      {"title": "원천징수영수증 발급 📄",       "message": "{period} 원천징수영수증이 발급되었습니다.", "link": "/actuator/commissions", "default": {"app": True, "push": False, "email": True}, "group": "커미션/정산"},

    "RECRUITED_SELLER_APPROVED":{"title": "모집 판매자 승인! 👤✅",       "message": "{seller_name}님이 판매자로 승인되었어요!", "link": "/actuator/sellers", "default": {"app": True, "push": True, "email": False}, "group": "모집 판매자"},
    "RECRUITED_SELLER_OFFER":   {"title": "모집 판매자 오퍼 제출 📋",     "message": "{seller_name}님이 '{product_name}' 딜에 오퍼를 제출했어요!", "link": "/actuator/sellers", "default": {"app": True, "push": True, "email": False}, "group": "모집 판매자"},
    "RECRUITED_SELLER_DEAL":    {"title": "모집 판매자 거래 확정! 🎊",    "message": "{seller_name}님의 '{product_name}' 오퍼가 낙찰되었어요!", "link": "/actuator/sellers", "default": {"app": True, "push": True, "email": False}, "group": "모집 판매자"},
    "RECRUITED_SELLER_FIRST":   {"title": "모집 판매자 첫 거래! 🎉🎉",   "message": "{seller_name}님의 첫 거래가 성사되었어요!", "link": "/actuator/sellers", "default": {"app": True, "push": True, "email": True}, "group": "모집 판매자"},

    "INTEREST_DEAL_CREATED":    {"title": "관심 상품 딜 등록! 📌",        "message": "'{matched_interest}' 관련 '{product_name}' 딜이 생성되었어요!", "link": "/deal/{deal_id}", "default": {"app": True, "push": True, "email": False}, "group": "매칭"},

    "A_ANNOUNCEMENT":           {"title": "📢 공지사항",                  "message": "{announcement_preview}", "link": "/support", "default": {"app": True, "push": False, "email": False}, "group": "시스템"},
    "CONTRACT_RENEWAL":         {"title": "위탁계약 갱신 안내 📋",        "message": "위탁계약이 {renewal_date}에 자동 갱신됩니다.", "link": "/actuator/contract", "default": {"app": True, "push": True, "email": True}, "group": "시스템"},
    "A_ACCOUNT_WARNING":        {"title": "계정 경고 ⚠️",                "message": "계정에 경고가 발생했습니다. 사유: {warning_reason}", "link": "/settings", "default": {"app": True, "push": True, "email": True}, "group": "시스템"},
}

ADMIN_EVENTS = {
    "NEW_SELLER_PENDING":       {"title": "판매자 승인 대기 👤",          "message": "{seller_name}님이 판매자 가입을 신청했습니다.", "link": "/admin/sellers"},
    "NEW_DISPUTE":              {"title": "새 분쟁 접수 ⚠️",             "message": "'{product_name}' 주문 분쟁이 접수되었습니다.", "link": "/admin/reports"},
    "NEW_REPORT":               {"title": "새 신고 접수 🚨",             "message": "신고 RPT-{report_id}: {report_reason}", "link": "/admin/reports"},
    "SETTLEMENT_BATCH_READY":   {"title": "정산 일괄 승인 대기 💰",      "message": "{count}건의 정산이 승인 대기 중입니다. 총 {total_amount}원", "link": "/admin/settlements"},
    "TAX_INVOICE_BATCH_READY":  {"title": "세금계산서 일괄 발행 🧾",     "message": "{count}건의 세금계산서 발행 대기 중입니다.", "link": "/admin/tax-invoices"},
    "ANOMALY_DETECTED":         {"title": "이상 감지! 🔴",               "message": "{anomaly_desc}", "link": "/admin/anomalies"},
    "SYSTEM_ERROR":             {"title": "시스템 오류 🔧",              "message": "{error_summary}", "link": "/admin"},
}

# ── 역할별 이벤트 맵 ──
ALL_EVENTS_BY_ROLE = {
    "buyer": BUYER_EVENTS,
    "seller": SELLER_EVENTS,
    "actuator": ACTUATOR_EVENTS,
    "admin": ADMIN_EVENTS,
}

# ── 모든 이벤트 합쳐진 맵 ──
ALL_EVENTS = {**BUYER_EVENTS, **SELLER_EVENTS, **ACTUATOR_EVENTS, **ADMIN_EVENTS}


def get_event_defaults(event_type: str, role: str = "buyer") -> dict:
    """이벤트의 기본 채널 설정 반환"""
    events = ALL_EVENTS_BY_ROLE.get(role, BUYER_EVENTS)
    evt = events.get(event_type, ALL_EVENTS.get(event_type, {}))
    return evt.get("default", {"app": True, "push": False, "email": False})


def render_notification(event_type: str, variables: dict) -> dict:
    """템플릿에 변수 치환하여 최종 알림 문구 생성"""
    template = ALL_EVENTS.get(event_type, {})

    title = template.get("title", event_type)
    message = template.get("message", "")
    link = template.get("link", "")

    for key, value in variables.items():
        title = title.replace(f"{{{key}}}", str(value))
        message = message.replace(f"{{{key}}}", str(value))
        link = link.replace(f"{{{key}}}", str(value))

    # 남은 치환 변수 제거
    title = re.sub(r'\{[^}]+\}', '', title).strip()
    message = re.sub(r'\{[^}]+\}', '', message).strip()

    return {"title": title, "message": message, "link": link}


# 프리셋 관심 카테고리
PRESET_CATEGORIES = [
    "스마트폰", "노트북", "태블릿", "TV/모니터", "가전",
    "게임/콘솔", "음향/이어폰", "카메라", "생활용품", "식품",
    "패션", "뷰티", "유아/키즈", "스포츠/아웃도어", "자동차용품",
]
