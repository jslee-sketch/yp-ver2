"""단순 환불 요청 서비스 — 구매자 요청 → 판매자 승인/거절 → 자동 승인"""
import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import RefundRequest, Reservation, ReservationSettlement
from app.services.working_days import add_working_days

logger = logging.getLogger(__name__)


def safe_notify(user_id, event_type, variables, db):
    """알림 발송 (실패해도 비즈 로직 중단 안 함)"""
    try:
        if user_id is None:
            return
        from app.services.notification_service import send_notification
        send_notification(db, user_id=user_id, event_type=event_type, variables=variables)
    except Exception as e:
        logger.warning(f"Notification failed: {event_type} → {e}")


def create_refund_request(data: dict, db: Session) -> dict:
    """구매자 환불 요청 → 판매자 2영업일 승인 대기"""
    reservation = db.query(Reservation).filter(Reservation.id == data["reservation_id"]).first()
    if not reservation:
        return {"error": "예약을 찾을 수 없습니다"}

    existing = db.query(RefundRequest).filter(
        RefundRequest.reservation_id == reservation.id,
        RefundRequest.status.in_(["REQUESTED", "SELLER_APPROVED", "AUTO_APPROVED"]),
    ).first()
    if existing:
        return {"error": "이미 처리 중인 환불 요청이 있습니다"}

    now = datetime.utcnow()
    req = RefundRequest(
        reservation_id=reservation.id,
        buyer_id=data["buyer_id"],
        reason=data.get("reason", "buyer_change_mind"),
        reason_detail=data.get("reason_detail", ""),
        evidence_urls=json.dumps(data.get("evidence", [])),
        seller_response_deadline=add_working_days(now, 2),
    )
    db.add(req)

    # 정산 보류
    settlement = db.query(ReservationSettlement).filter(
        ReservationSettlement.reservation_id == reservation.id
    ).first()
    if settlement and settlement.status in ("COOLING", "READY", "PENDING"):
        settlement.status = "DISPUTE_HOLD"

    db.commit()
    db.refresh(req)

    # 알림
    seller_id = None
    if reservation.offer:
        seller_id = reservation.offer.seller_id
    order_num = getattr(reservation, 'order_number', '') or str(reservation.id)
    safe_notify(seller_id, "REFUND_REQUESTED_SELLER", {"order_number": order_num}, db)
    safe_notify(data["buyer_id"], "REFUND_REQUESTED_BUYER", {"order_number": order_num}, db)

    return {
        "refund_request_id": req.id,
        "status": req.status,
        "deadline": str(req.seller_response_deadline),
    }


def seller_respond_refund(request_id: int, response: str, reject_reason: str, db: Session) -> dict:
    req = db.query(RefundRequest).filter(
        RefundRequest.id == request_id,
        RefundRequest.status == "REQUESTED",
    ).first()
    if not req:
        return {"error": "처리할 수 없는 상태"}

    req.seller_response = response
    req.seller_response_at = datetime.utcnow()

    if response == "approve":
        req.status = "SELLER_APPROVED"
        db.commit()
        from app.services.resolution_executor import start_resolution_from_refund
        return start_resolution_from_refund(req.id, db)
    else:
        req.status = "SELLER_REJECTED"
        req.seller_reject_reason = reject_reason
        db.commit()
        safe_notify(req.buyer_id, "REFUND_REJECTED", {"reason": reject_reason}, db)
        return {"status": "SELLER_REJECTED", "can_dispute": True}


def auto_approve_expired_refunds(db: Session) -> dict:
    now = datetime.utcnow()
    expired = db.query(RefundRequest).filter(
        RefundRequest.status == "REQUESTED",
        RefundRequest.seller_response_deadline < now,
    ).all()

    count = 0
    for req in expired:
        req.status = "AUTO_APPROVED"
        req.seller_response = "auto_approve"
        req.seller_response_at = now
        count += 1
        safe_notify(req.buyer_id, "REFUND_AUTO_APPROVED", {}, db)
        from app.services.resolution_executor import start_resolution_from_refund
        start_resolution_from_refund(req.id, db)

    if count:
        db.commit()
    return {"auto_approved": count}
