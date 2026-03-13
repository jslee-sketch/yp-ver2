"""
후속 처리 엔진 — 12가지 시나리오 완전 자동화

E-1. execute_dispute_resolution  — 분쟁 합의 후 자동 실행
E-2. start_resolution_from_refund — 단순 환불에서 시작
E-3. route_resolution            — 상태에 따라 다음 단계 자동 결정
E-4. initiate_return / submit_return_tracking / confirm_return_and_inspect — 반품/수거/검수
E-5. process_refund / adjust_settlement — PG 환불 + 정산 조정
E-6. initiate_exchange / submit_exchange_tracking / confirm_exchange_received — 교환
E-7. process_compensation — 보상금 (포인트)
E-8. handle_rejected_dispute — 분쟁 거절 → LEGAL_HOLD
E-9. admin_manual_resolution — 관리자 수동 처리
E-10. close_resolution — 종결
E-11. process_clawback_batch — Clawback 배치
E-12. process_resolution_timeouts — 타임아웃 배치
"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    ClawbackRecord, Dispute, Offer, Reservation,
    ResolutionAction, RefundRequest, ReservationSettlement, Seller, User,
)
from app.services.refund_calculator import calculate_refund, determine_fault, _load_raw_policy
from app.services.working_days import add_working_days

logger = logging.getLogger(__name__)


def _safe_notify(user_id, event_type, variables, db):
    try:
        if user_id is None:
            return
        from app.services.notification_service import send_notification
        send_notification(db, user_id=user_id, event_type=event_type, variables=variables)
    except Exception as e:
        logger.warning(f"Notification failed: {event_type} → {e}")


def _get_seller_id(reservation, db):
    """Reservation에서 seller_id 추출 (Offer 경유)"""
    if reservation.offer:
        return reservation.offer.seller_id
    offer = db.query(Offer).filter(Offer.id == reservation.offer_id).first()
    return offer.seller_id if offer else None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-1. 분쟁 합의 후 자동 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def execute_dispute_resolution(dispute_id: int, db: Session) -> dict:
    """분쟁 ACCEPTED → 12가지 시나리오 자동 분기"""
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute or dispute.status not in ("ACCEPTED", "CLOSED"):
        return {"error": "합의된 분쟁이 아닙니다"}

    reservation = db.query(Reservation).filter(Reservation.id == dispute.reservation_id).first()
    if not reservation:
        return {"error": "예약을 찾을 수 없습니다"}

    resolution_amount = dispute.resolution_amount or 0
    if dispute.requested_resolution == "exchange":
        res_type = "EXCHANGE"
    elif resolution_amount >= reservation.amount_total * 0.9:
        res_type = "FULL_REFUND"
    elif resolution_amount > 0:
        res_type = "PARTIAL_REFUND"
    else:
        res_type = "NO_ACTION"

    # 귀책 결정
    cat = dispute.category or ""
    if cat in SELLER_FAULT_REASONS_KR or cat in ("defective", "wrong_item", "damaged", "not_delivered", "description_mismatch"):
        fault = "seller"
    elif cat in ("buyer_change_mind",):
        fault = "buyer"
    else:
        fault = determine_fault(cat)

    shipping_mode = getattr(reservation, 'shipping_mode', 'free') or 'free'
    delivery_status_val = getattr(reservation, 'delivery_status', 'delivered') or 'delivered'
    orig_amount = reservation.amount_total - reservation.amount_shipping
    ship_fee = reservation.amount_shipping

    calc = calculate_refund(
        original_amount=orig_amount,
        shipping_fee=ship_fee,
        shipping_mode=shipping_mode,
        reason=cat or "other",
        delivery_status=delivery_status_val,
        dispute_agreed_amount=resolution_amount,
        resolution_type=res_type,
        role="admin",
    )

    si = calc.get("settlement_impact", {})

    action = ResolutionAction(
        dispute_id=dispute.id,
        reservation_id=reservation.id,
        resolution_type=res_type,
        original_amount=orig_amount,
        original_shipping_fee=ship_fee,
        original_total=reservation.amount_total,
        shipping_mode=shipping_mode,
        delivery_status=delivery_status_val,
        fault=fault,
        refund_reason=cat or "dispute",
        return_required=calc["return_required"],
        buyer_refund_amount=calc["buyer_refund_amount"],
        total_deduction=calc["total_deduction"],
        return_shipping_cost=calc.get("total_deduction", 0) if fault == "buyer" else 0,
        shipping_payer=calc["shipping_payer"],
        seller_deduction_amount=si.get("loss", 0),
        seller_return_shipping_burden=si.get("return_shipping_burden", 0),
        platform_fee_refund=si.get("platform_fee_refund", 0),
        compensation_amount=resolution_amount if res_type == "COMPENSATION" else 0,
        status="PENDING",
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    return route_resolution(action.id, db)


SELLER_FAULT_REASONS_KR = {"품질불량", "미배송", "허위설명", "파손", "오배송"}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-2. 단순 환불에서 시작
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def start_resolution_from_refund(refund_request_id: int, db: Session) -> dict:
    req = db.query(RefundRequest).filter(RefundRequest.id == refund_request_id).first()
    if not req:
        return {"error": "환불 요청을 찾을 수 없습니다"}
    reservation = db.query(Reservation).filter(Reservation.id == req.reservation_id).first()
    if not reservation:
        return {"error": "예약을 찾을 수 없습니다"}

    fault = determine_fault(req.reason)
    shipping_mode = getattr(reservation, 'shipping_mode', 'free') or 'free'
    delivery_status_val = getattr(reservation, 'delivery_status', 'delivered') or 'delivered'
    orig_amount = reservation.amount_total - reservation.amount_shipping
    ship_fee = reservation.amount_shipping

    calc = calculate_refund(
        original_amount=orig_amount,
        shipping_fee=ship_fee,
        shipping_mode=shipping_mode,
        reason=req.reason,
        delivery_status=delivery_status_val,
        role="admin",
    )
    si = calc.get("settlement_impact", {})

    action = ResolutionAction(
        refund_request_id=req.id,
        reservation_id=reservation.id,
        resolution_type="FULL_REFUND",
        original_amount=orig_amount,
        original_shipping_fee=ship_fee,
        original_total=reservation.amount_total,
        shipping_mode=shipping_mode,
        delivery_status=delivery_status_val,
        fault=fault,
        refund_reason=req.reason,
        return_required=calc["return_required"],
        buyer_refund_amount=calc["buyer_refund_amount"],
        total_deduction=calc["total_deduction"],
        shipping_payer=calc["shipping_payer"],
        seller_deduction_amount=si.get("loss", 0),
        seller_return_shipping_burden=si.get("return_shipping_burden", 0),
        platform_fee_refund=si.get("platform_fee_refund", 0),
        status="PENDING",
    )
    db.add(action)
    req.resolution_action_id = action.id
    db.commit()
    db.refresh(action)

    return route_resolution(action.id, db)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-3. 라우터 — 상태에 따라 다음 단계 자동 결정
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def route_resolution(action_id: int, db: Session) -> dict:
    """모든 분기를 자동 라우팅"""
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()

    if action.resolution_type == "NO_ACTION":
        return close_resolution(action_id, "RELEASE", db)

    if action.resolution_type == "COMPENSATION":
        return process_compensation(action_id, db)

    if action.return_required:
        return initiate_return(action_id, db)

    # 반품 불필요 (배송전 취소, 미배송, 부분보상)
    return process_refund(action_id, db)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-4. 반품/수거/검수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def initiate_return(action_id: int, db: Session) -> dict:
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    reservation = db.query(Reservation).filter(Reservation.id == action.reservation_id).first()
    seller_id = _get_seller_id(reservation, db)

    # 판매자 반품 주소 가져오기
    return_addr = "판매자 주소 미등록"
    if seller_id:
        seller = db.query(Seller).filter(Seller.id == seller_id).first()
        if seller:
            return_addr = getattr(seller, 'return_address', None) or getattr(seller, 'address', '') or return_addr

    action.return_address = return_addr
    action.return_deadline = add_working_days(datetime.utcnow(), 7)
    action.status = "RETURN_REQUESTED"
    db.commit()

    _safe_notify(reservation.buyer_id, "RETURN_ADDRESS", {"address": return_addr}, db)
    _safe_notify(seller_id, "RETURN_INITIATED", {"order_number": getattr(reservation, 'order_number', '')}, db)
    return {"status": "RETURN_REQUESTED", "return_address": return_addr, "action_id": action.id}


def submit_return_tracking(action_id: int, tracking: str, carrier: str, db: Session):
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    if not action or action.status != "RETURN_REQUESTED":
        return {"error": "반품 대기 상태가 아닙니다"}
    action.return_tracking_number = tracking
    action.return_carrier = carrier
    action.return_shipped_at = datetime.utcnow()
    action.status = "RETURN_IN_TRANSIT"
    db.commit()

    reservation = db.query(Reservation).filter(Reservation.id == action.reservation_id).first()
    seller_id = _get_seller_id(reservation, db) if reservation else None
    _safe_notify(seller_id, "RETURN_SHIPPED", {"tracking": tracking}, db)
    return {"status": "RETURN_IN_TRANSIT"}


def confirm_return_and_inspect(action_id: int, result: str, deduction_rate: float, notes: str, db: Session):
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    if not action or action.status != "RETURN_IN_TRANSIT":
        return {"error": "반품 배송 중 상태가 아닙니다"}

    raw = _load_raw_policy()
    max_rate = raw.get("refund", {}).get("max_inspection_deduction_rate", 0.5)
    deduction_rate = min(deduction_rate, max_rate)

    action.return_received_at = datetime.utcnow()
    action.inspection_result = result
    action.inspection_notes = notes
    action.inspected_at = datetime.utcnow()
    action.status = "INSPECTED"

    # 감가 재계산 (검수 기반)
    if result == "PARTIAL" and deduction_rate > 0:
        usage = int(action.original_amount * deduction_rate)
        action.usage_deduction = usage
        action.usage_deduction_rate = deduction_rate
        action.buyer_refund_amount = max(0, action.buyer_refund_amount - usage)
        action.total_deduction += usage

    db.commit()

    if result in ("PASS", "PARTIAL"):
        if action.resolution_type == "EXCHANGE":
            return initiate_exchange(action_id, db)
        else:
            return process_refund(action_id, db)
    else:
        # FAIL → 관리자
        action.admin_override = True
        action.escalation_reason = f"반품 검수 FAIL: {notes}"
        action.status = "ADMIN_PENDING"
        db.commit()
        _safe_notify(None, "ADMIN_MANUAL_NEEDED", {"id": action.id, "reason": f"검수 FAIL: {notes}"}, db)
        return {"status": "ADMIN_PENDING", "action_id": action.id}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-5. PG 환불 + 정산 조정 (핵심!)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def process_refund(action_id: int, db: Session):
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    reservation = db.query(Reservation).filter(Reservation.id == action.reservation_id).first()

    if action.buyer_refund_amount <= 0:
        return close_resolution(action_id, "RELEASE", db)

    action.status = "REFUND_PROCESSING"
    action.pg_refund_requested = True
    db.commit()

    # PG 환불 (모의 — PG 연동 후 실제 API로 교체)
    try:
        pg_tx_id = getattr(reservation, 'pg_transaction_id', None) or f"MOCK_{reservation.id}"
        if action.buyer_refund_amount >= (action.original_total or action.original_amount or 0):
            pg_result = {"cancel_tx_id": f"FULL_{pg_tx_id}", "method": "CARD_CANCEL"}
        else:
            pg_result = {"cancel_tx_id": f"PARTIAL_{pg_tx_id}_{action.buyer_refund_amount}", "method": "CARD_CANCEL"}

        action.pg_refund_tx_id = pg_result["cancel_tx_id"]
        action.pg_refund_status = "SUCCESS"
        action.pg_refunded_at = datetime.utcnow()
        action.pg_refund_method = pg_result["method"]
    except Exception as e:
        action.pg_refund_status = "FAILED"
        action.pg_refund_error = str(e)
        action.pg_refund_retry_count += 1
        if action.pg_refund_retry_count >= 3:
            action.admin_override = True
            action.escalation_reason = f"PG 환불 3회 실패: {e}"
            action.status = "ADMIN_PENDING"
            db.commit()
            _safe_notify(None, "ADMIN_MANUAL_NEEDED", {"id": action.id, "reason": f"PG 실패: {e}"}, db)
            return {"status": "PG_REFUND_FAILED", "action_id": action.id}
        db.commit()
        return {"status": "PG_REFUND_FAILED", "retry": action.pg_refund_retry_count}

    action.status = "PG_REFUNDED"
    db.commit()

    # 예약 환불 추적 업데이트
    if reservation:
        reservation.refunded_qty = (reservation.refunded_qty or 0) + (reservation.qty or 0)
        reservation.refunded_amount_total = (reservation.refunded_amount_total or 0) + action.buyer_refund_amount
        reservation.refund_type = "refund"
        db.commit()

    # 정산 조정
    return adjust_settlement(action_id, db)


def adjust_settlement(action_id: int, db: Session):
    """정산 자동 재계산 — 모든 경우"""
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    reservation = db.query(Reservation).filter(Reservation.id == action.reservation_id).first()
    settlement = db.query(ReservationSettlement).filter(
        ReservationSettlement.reservation_id == reservation.id
    ).first()

    if not settlement:
        return close_resolution(action_id, None, db)

    raw = _load_raw_policy()
    fee_rate = raw.get("money", {}).get("platform_fee_rate", 0.035)

    action.settlement_id = settlement.id
    action.settlement_before_payout = settlement.seller_payout_amount

    # ── Case 1: 미지급 ──
    if settlement.status in ("DISPUTE_HOLD", "COOLING", "READY", "PENDING", "APPROVED", "HOLD"):
        if action.resolution_type == "FULL_REFUND" and action.buyer_refund_amount >= (action.original_total or 0) * 0.9:
            settlement.status = "CANCELLED"
            settlement.seller_payout_amount = 0
            settlement.platform_commission_amount = 0
            action.settlement_adjustment_type = "CANCEL"
        else:
            refunded = action.buyer_refund_amount
            remaining = (action.original_amount or 0) - refunded
            remaining = max(0, remaining)
            settlement.seller_payout_amount = int(remaining * (1 - fee_rate))
            settlement.platform_commission_amount = int(remaining * fee_rate)
            settlement.status = "ADJUSTED"
            action.settlement_adjustment_type = "DEDUCT"

        action.settlement_adjustment_amount = action.buyer_refund_amount
        action.platform_fee_refund = int(action.buyer_refund_amount * fee_rate)

    # ── Case 2: 이미 지급됨 → Clawback ──
    elif settlement.status == "PAID":
        seller_id = _get_seller_id(reservation, db) or settlement.seller_id
        clawback = ClawbackRecord(
            settlement_id=settlement.id,
            seller_id=seller_id,
            resolution_action_id=action.id,
            amount=action.buyer_refund_amount,
            remaining_amount=action.buyer_refund_amount,
            reason=f"환불 (사유: {action.refund_reason})",
        )
        db.add(clawback)
        settlement.status = "CLAWBACK_PENDING"
        action.settlement_adjustment_type = "CLAWBACK"
        action.settlement_adjustment_amount = action.buyer_refund_amount

    action.settlement_adjusted = True
    action.settlement_after_payout = settlement.seller_payout_amount

    # 세금계산서 조정 플래그
    if action.settlement_adjustment_type in ("CANCEL", "DEDUCT", "CLAWBACK"):
        action.tax_invoice_adjusted = True
        action.tax_invoice_adjustment_note = f"환불 {action.buyer_refund_amount:,}원에 따른 세금계산서 수정 필요"

    db.commit()

    # 알림
    _safe_notify(reservation.buyer_id, "PG_REFUNDED", {"amount": f"{action.buyer_refund_amount:,}"}, db)
    seller_id = _get_seller_id(reservation, db)
    _safe_notify(seller_id, "SETTLEMENT_ADJUSTED", {"amount": f"{action.settlement_adjustment_amount:,}"}, db)

    return close_resolution(action_id, action.settlement_adjustment_type, db)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-6. 교환
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def initiate_exchange(action_id: int, db: Session):
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    action.exchange_ship_deadline = add_working_days(datetime.utcnow(), 3)
    action.status = "EXCHANGE_SHIPPING"
    db.commit()

    reservation = db.query(Reservation).filter(Reservation.id == action.reservation_id).first()
    seller_id = _get_seller_id(reservation, db) if reservation else None
    _safe_notify(seller_id, "EXCHANGE_SHIP_REQUEST", {}, db)
    return {"status": "EXCHANGE_SHIPPING", "action_id": action.id}


def submit_exchange_tracking(action_id: int, tracking: str, carrier: str, db: Session):
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    if not action or action.status != "EXCHANGE_SHIPPING":
        return {"error": "교환 발송 대기 상태가 아닙니다"}
    action.exchange_tracking_number = tracking
    action.exchange_carrier = carrier
    action.exchange_shipped_at = datetime.utcnow()
    action.status = "EXCHANGE_IN_TRANSIT"
    db.commit()

    reservation = db.query(Reservation).filter(Reservation.id == action.reservation_id).first()
    _safe_notify(reservation.buyer_id if reservation else None, "EXCHANGE_SHIPPED", {"tracking": tracking}, db)
    return {"status": "EXCHANGE_IN_TRANSIT"}


def confirm_exchange_received(action_id: int, db: Session):
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    action.exchange_delivered_at = datetime.utcnow()

    # 정산 HOLD 해제 (교환 완료 → 금액 변경 없음)
    settlement = db.query(ReservationSettlement).filter(
        ReservationSettlement.reservation_id == action.reservation_id
    ).first()
    if settlement and settlement.status == "DISPUTE_HOLD":
        settlement.status = "READY"
        action.settlement_adjustment_type = "RELEASE"

    return close_resolution(action_id, "RELEASE", db)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-7. 보상금 (포인트)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def process_compensation(action_id: int, db: Session):
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    reservation = db.query(Reservation).filter(Reservation.id == action.reservation_id).first()

    # 포인트 적립 (User 모델에 points 필드가 있으면)
    if reservation:
        buyer = db.query(User).filter(User.id == reservation.buyer_id).first()
        if buyer and hasattr(buyer, 'points'):
            buyer.points = (buyer.points or 0) + action.compensation_amount

    # PG 환불도 필요한 경우 (현금 보상)
    if action.buyer_refund_amount > 0:
        return process_refund(action_id, db)

    action.status = "COMPENSATION_PROCESSING"
    db.commit()
    return close_resolution(action_id, "DEDUCT", db)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-8. 분쟁 거절 → LEGAL_HOLD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def handle_rejected_dispute(dispute_id: int, db: Session):
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        return {"error": "분쟁을 찾을 수 없습니다"}

    reservation = db.query(Reservation).filter(Reservation.id == dispute.reservation_id).first()

    settlement = db.query(ReservationSettlement).filter(
        ReservationSettlement.reservation_id == reservation.id
    ).first() if reservation else None

    if settlement:
        settlement.status = "LEGAL_HOLD"

    orig_amount = reservation.amount_total - reservation.amount_shipping if reservation else 0

    action = ResolutionAction(
        dispute_id=dispute.id,
        reservation_id=dispute.reservation_id,
        resolution_type="PENDING_LEGAL",
        original_amount=orig_amount,
        original_total=reservation.amount_total if reservation else 0,
        status="ADMIN_PENDING",
        admin_override=True,
        escalation_reason="2차 AI 중재 미합의. 법적 결과 대기.",
    )
    db.add(action)
    db.commit()
    _safe_notify(None, "ADMIN_MANUAL_NEEDED", {"id": action.id, "reason": "분쟁 미합의 LEGAL_HOLD"}, db)
    return {"status": "LEGAL_HOLD", "action_id": action.id}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-9. 관리자 수동 처리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def admin_manual_resolution(action_id: int, data: dict, db: Session):
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    if not action:
        return {"error": "존재하지 않는 건"}

    decision = data.get("decision")
    amount = data.get("amount", 0)

    action.admin_processed_by = data.get("admin_id")
    action.admin_notes = data.get("notes", "")

    if decision == "refund":
        action.resolution_type = "FULL_REFUND"
        action.buyer_refund_amount = action.original_total or 0
        return process_refund(action_id, db)
    elif decision == "partial_refund":
        action.resolution_type = "PARTIAL_REFUND"
        action.buyer_refund_amount = amount
        return process_refund(action_id, db)
    elif decision == "release":
        settlement = db.query(ReservationSettlement).filter(
            ReservationSettlement.reservation_id == action.reservation_id
        ).first()
        if settlement:
            settlement.status = "READY"
        return close_resolution(action_id, "RELEASE", db)
    elif decision == "compensation":
        action.resolution_type = "COMPENSATION"
        action.compensation_amount = amount
        return process_compensation(action_id, db)

    return {"status": action.status, "action_id": action.id}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-10. 종결
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def close_resolution(action_id: int, adjustment_type: str, db: Session):
    action = db.query(ResolutionAction).filter(ResolutionAction.id == action_id).first()
    action.status = "COMPLETED"
    action.completed_at = datetime.utcnow()
    if adjustment_type:
        action.settlement_adjustment_type = action.settlement_adjustment_type or adjustment_type
    db.commit()
    return {
        "status": "COMPLETED",
        "action_id": action.id,
        "refund": action.buyer_refund_amount,
        "type": action.resolution_type,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-11. Clawback 배치 (차기 정산 자동 차감)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def process_clawback_batch(db: Session) -> dict:
    """정산 배치 시 호출 — PENDING Clawback 자동 차감"""
    pending = db.query(ClawbackRecord).filter(ClawbackRecord.status == "PENDING").all()

    processed = 0
    insufficient = 0
    escalated = 0

    for cb in pending:
        next_settlement = db.query(ReservationSettlement).filter(
            ReservationSettlement.seller_id == cb.seller_id,
            ReservationSettlement.status == "READY",
        ).order_by(ReservationSettlement.created_at.asc()).first()

        if not next_settlement:
            cb.attempt_count += 1
            if cb.attempt_count >= cb.max_attempts:
                cb.status = "INSUFFICIENT_BALANCE"
                escalated += 1
                _safe_notify(None, "ADMIN_MANUAL_NEEDED", {
                    "id": cb.id, "reason": f"Clawback {cb.amount:,}원 3회 차감 실패. 판매자 ID: {cb.seller_id}"
                }, db)
            insufficient += 1
            continue

        if next_settlement.seller_payout_amount >= cb.remaining_amount:
            next_settlement.seller_payout_amount -= cb.remaining_amount
            cb.deducted_from_settlement_id = next_settlement.id
            cb.remaining_amount = 0
            cb.status = "DEDUCTED"
            cb.processed_at = datetime.utcnow()
            processed += 1
        else:
            deducted = next_settlement.seller_payout_amount
            next_settlement.seller_payout_amount = 0
            cb.remaining_amount -= deducted
            cb.attempt_count += 1
            if cb.attempt_count >= cb.max_attempts:
                cb.status = "INSUFFICIENT_BALANCE"
                escalated += 1
                _safe_notify(None, "ADMIN_MANUAL_NEEDED", {
                    "id": cb.id, "reason": f"Clawback 잔여 {cb.remaining_amount:,}원 미회수"
                }, db)
            insufficient += 1

    if pending:
        db.commit()

    return {"processed": processed, "insufficient": insufficient, "escalated": escalated}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# E-12. 타임아웃 배치
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def process_resolution_timeouts(db: Session) -> dict:
    """기한 초과 자동 처리 배치"""
    now = datetime.utcnow()
    results = {"return_expired": 0, "exchange_expired": 0, "warnings": 0}

    # 반품 미발송 7일 → 환불 취소
    expired_returns = db.query(ResolutionAction).filter(
        ResolutionAction.status == "RETURN_REQUESTED",
        ResolutionAction.return_deadline < now,
    ).all()
    for a in expired_returns:
        a.status = "CANCELLED"
        a.admin_notes = "반품 발송 기한 초과 — 환불 취소"
        a.completed_at = now
        settlement = db.query(ReservationSettlement).filter(
            ReservationSettlement.reservation_id == a.reservation_id
        ).first()
        if settlement and settlement.status == "DISPUTE_HOLD":
            settlement.status = "READY"
        results["return_expired"] += 1

    # 교환 미발송 3일 → 관리자 에스컬레이션
    expired_exchanges = db.query(ResolutionAction).filter(
        ResolutionAction.status == "EXCHANGE_SHIPPING",
        ResolutionAction.exchange_ship_deadline < now,
    ).all()
    for a in expired_exchanges:
        a.admin_override = True
        a.escalation_reason = "교환 상품 발송 기한 초과"
        a.status = "ADMIN_PENDING"
        results["exchange_expired"] += 1

    # 반품 발송 기한 임박 경고 (1영업일 전)
    near_deadline = db.query(ResolutionAction).filter(
        ResolutionAction.status == "RETURN_REQUESTED",
        ResolutionAction.return_expired_notified == False,
    ).all()
    for a in near_deadline:
        if a.return_deadline and (a.return_deadline - now).days <= 1:
            a.return_expired_notified = True
            reservation = db.query(Reservation).filter(Reservation.id == a.reservation_id).first()
            _safe_notify(reservation.buyer_id if reservation else None, "RETURN_DEADLINE_WARNING", {}, db)
            results["warnings"] += 1

    if any(v > 0 for v in results.values()):
        db.commit()

    return results
