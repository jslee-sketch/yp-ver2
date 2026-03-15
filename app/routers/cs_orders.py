"""CS 주문 관리 라우터 — 취소 / 반품·교환 요청 / 내 주문·반품 조회"""
import json
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Reservation, CSReturnRequest, Buyer

# ── Policy ──
try:
    from app.policy.api import cooling_days as policy_cooling_days
except ImportError:
    def policy_cooling_days() -> int:
        return 7

router = APIRouter(tags=["cs-orders"])


# ───────────────────────── Schemas ─────────────────────────

class CancelItem(BaseModel):
    item_id: int
    quantity: int = Field(ge=1)


class CancelType(str, Enum):
    full = "full"
    partial = "partial"


class CancelRequest(BaseModel):
    cancel_type: CancelType
    items: List[CancelItem] = Field(default_factory=list)
    reason_code: str = Field(min_length=1, max_length=30)


class ReturnRequestType(str, Enum):
    return_full = "return_full"
    exchange_same = "exchange_same"
    exchange_different = "exchange_different"
    partial_refund_request = "partial_refund_request"
    partial_return = "partial_return"


class ReturnItem(BaseModel):
    item_id: int
    quantity: int = Field(ge=1)


class ReturnRequestBody(BaseModel):
    request_type: ReturnRequestType
    items: List[ReturnItem] = Field(default_factory=list)
    reason_code: str = Field(min_length=1, max_length=30)
    reason_detail: Optional[str] = None
    evidence_urls: List[str] = Field(default_factory=list)
    partial_refund_amount: Optional[int] = Field(default=None, ge=0)


# ───────────────────────── Helpers ─────────────────────────

def _get_reservation_by_order(order_number: str, db: Session) -> Reservation:
    """주문번호로 예약 조회, 없으면 404."""
    reservation = (
        db.query(Reservation)
        .filter(Reservation.order_number == order_number)
        .first()
    )
    if not reservation:
        raise HTTPException(404, f"주문번호 {order_number}에 해당하는 예약을 찾을 수 없습니다.")
    return reservation


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_reservation(r: Reservation) -> dict:
    return {
        "id": r.id,
        "order_number": r.order_number,
        "deal_id": r.deal_id,
        "offer_id": r.offer_id,
        "buyer_id": r.buyer_id,
        "qty": r.qty,
        "amount_goods": r.amount_goods,
        "amount_shipping": r.amount_shipping,
        "amount_total": r.amount_total,
        "refunded_qty": r.refunded_qty,
        "refunded_amount_total": r.refunded_amount_total,
        "status": r.status.value if hasattr(r.status, "value") else str(r.status),
        "delivery_status": r.delivery_status,
        "delivered_at": str(r.delivered_at) if r.delivered_at else None,
        "created_at": str(r.created_at) if r.created_at else None,
        "paid_at": str(r.paid_at) if r.paid_at else None,
        "cancelled_at": str(r.cancelled_at) if r.cancelled_at else None,
    }


def _serialize_cs_return(cr: CSReturnRequest) -> dict:
    def _parse_json_field(raw):
        if not raw:
            return []
        if isinstance(raw, list):
            return raw
        try:
            return json.loads(raw)
        except Exception:
            return []

    return {
        "id": cr.id,
        "order_number": cr.order_number,
        "reservation_id": cr.reservation_id,
        "buyer_id": cr.buyer_id,
        "seller_id": cr.seller_id,
        "request_type": cr.request_type,
        "items": _parse_json_field(cr.items),
        "reason_code": cr.reason_code,
        "reason_detail": cr.reason_detail,
        "evidence_urls": _parse_json_field(cr.evidence_urls),
        "requested_amount": cr.requested_amount,
        "status": cr.status,
        "seller_response": cr.seller_response,
        "seller_responded_at": str(cr.seller_responded_at) if cr.seller_responded_at else None,
        "created_at": str(cr.created_at) if cr.created_at else None,
        "updated_at": str(cr.updated_at) if cr.updated_at else None,
    }


# Statuses that allow instant cancel (결제 완료 직후, 아직 준비 전)
_INSTANT_CANCEL_DELIVERY = {None, "READY"}
# Statuses that require seller approval for cancel (상품 준비 중)
_SELLER_APPROVAL_DELIVERY = {"COLLECTING", "PREPARING"}
# 취소 불가 상태
_NO_CANCEL_DELIVERY = {"IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "FAILED"}


# ───────────────────────── 1) POST /{order_number}/cancel ─────────────────────────

@router.post("/v3/orders/{order_number}/cancel")
def cancel_order(
    order_number: str,
    body: CancelRequest,
    db: Session = Depends(get_db),
):
    """
    주문 취소 (전체 또는 부분).

    - PAID 상태 & delivery_status 가 None/READY → 즉시 취소
    - PAID 상태 & delivery_status 가 COLLECTING/PREPARING → 판매자 승인 필요 (CSReturnRequest 생성)
    - 그 외 → 취소 불가
    """
    reservation = _get_reservation_by_order(order_number, db)

    # 이미 취소된 주문
    status_val = reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status)
    if status_val == "CANCELLED":
        raise HTTPException(400, "이미 취소된 주문입니다.")

    # PAID 상태만 취소 가능
    if status_val not in ("PAID",):
        raise HTTPException(
            400,
            f"현재 주문 상태({status_val})에서는 취소할 수 없습니다. PAID 상태의 주문만 취소 가능합니다.",
        )

    delivery = reservation.delivery_status
    items_json = json.dumps([item.model_dump() for item in body.items], ensure_ascii=False)

    # Case 1: 즉시 취소 가능
    if delivery in _INSTANT_CANCEL_DELIVERY:
        request_type = f"cancel_{body.cancel_type.value}"

        if body.cancel_type == CancelType.full:
            reservation.status = "CANCELLED"
            reservation.cancelled_at = _now()
        else:
            # 부분 취소: refunded_qty / refunded_amount_total 업데이트는
            # 실제 환불 프로세스에서 처리 (여기서는 상태만 기록)
            pass

        cs_req = CSReturnRequest(
            order_number=order_number,
            reservation_id=reservation.id,
            buyer_id=reservation.buyer_id,
            seller_id=reservation.offer.seller_id if reservation.offer else 0,
            request_type=request_type,
            items=items_json,
            reason_code=body.reason_code,
            status="COMPLETED",
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(cs_req)
        db.commit()
        db.refresh(reservation)
        db.refresh(cs_req)

        return {
            "result": "cancelled",
            "cancel_type": body.cancel_type.value,
            "cs_return_request_id": cs_req.id,
            "reservation": _serialize_reservation(reservation),
        }

    # Case 2: 판매자 승인 필요
    if delivery in _SELLER_APPROVAL_DELIVERY:
        request_type = f"cancel_{body.cancel_type.value}"

        cs_req = CSReturnRequest(
            order_number=order_number,
            reservation_id=reservation.id,
            buyer_id=reservation.buyer_id,
            seller_id=reservation.offer.seller_id if reservation.offer else 0,
            request_type=request_type,
            items=items_json,
            reason_code=body.reason_code,
            status="REQUESTED",
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(cs_req)
        db.commit()
        db.refresh(cs_req)

        return {
            "result": "pending_seller_approval",
            "cancel_type": body.cancel_type.value,
            "cs_return_request_id": cs_req.id,
            "message": "상품 준비 중이므로 판매자 승인이 필요합니다.",
        }

    # Case 3: 취소 불가
    raise HTTPException(
        400,
        f"배송 상태({delivery})에서는 취소할 수 없습니다. 반품/교환을 이용해주세요.",
    )


# ───────────────────────── 2) POST /{order_number}/return-request ─────────────────────────

@router.post("/v3/orders/{order_number}/return-request")
def create_return_request(
    order_number: str,
    body: ReturnRequestBody,
    db: Session = Depends(get_db),
):
    """
    반품/교환/부분환불 요청.

    - 배송 완료(DELIVERED) 상태여야 함
    - cooling_days 이내여야 함
    - CSReturnRequest 레코드 생성
    """
    reservation = _get_reservation_by_order(order_number, db)

    status_val = reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status)
    if status_val == "CANCELLED":
        raise HTTPException(400, "취소된 주문은 반품/교환 요청을 할 수 없습니다.")

    # 배송 완료 확인
    delivery = reservation.delivery_status
    if delivery != "DELIVERED":
        raise HTTPException(
            400,
            f"배송 완료 상태에서만 반품/교환 요청이 가능합니다. 현재 배송 상태: {delivery}",
        )

    # 쿨링 기간 확인
    delivered_at = reservation.delivered_at or reservation.arrival_confirmed_at
    if delivered_at:
        cooling = policy_cooling_days()
        elapsed = (_now() - delivered_at).days if delivered_at.tzinfo else (_now().replace(tzinfo=None) - delivered_at).days
        if elapsed > cooling:
            raise HTTPException(
                400,
                f"반품/교환 가능 기간({cooling}일)이 경과했습니다. (경과: {elapsed}일)",
            )

    # 부분환불 시 금액 필수
    if body.request_type == ReturnRequestType.partial_refund_request:
        if body.partial_refund_amount is None or body.partial_refund_amount <= 0:
            raise HTTPException(400, "부분환불 요청 시 partial_refund_amount는 필수이며 0보다 커야 합니다.")
        if body.partial_refund_amount > reservation.amount_total:
            raise HTTPException(400, "요청 금액이 주문 총액을 초과할 수 없습니다.")

    # 중복 요청 확인 (같은 주문에 대해 진행 중인 요청이 있으면 거부)
    existing = (
        db.query(CSReturnRequest)
        .filter(
            CSReturnRequest.order_number == order_number,
            CSReturnRequest.status.in_(["REQUESTED", "SELLER_APPROVED", "RETURN_SHIPPING"]),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            409,
            f"이미 진행 중인 요청(ID={existing.id}, 상태={existing.status})이 있습니다.",
        )

    items_json = json.dumps([item.model_dump() for item in body.items], ensure_ascii=False)
    evidence_json = json.dumps(body.evidence_urls, ensure_ascii=False)

    cs_req = CSReturnRequest(
        order_number=order_number,
        reservation_id=reservation.id,
        buyer_id=reservation.buyer_id,
        seller_id=reservation.offer.seller_id if reservation.offer else 0,
        request_type=body.request_type.value,
        items=items_json,
        reason_code=body.reason_code,
        reason_detail=body.reason_detail,
        evidence_urls=evidence_json,
        requested_amount=body.partial_refund_amount,
        status="REQUESTED",
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(cs_req)
    db.commit()
    db.refresh(cs_req)

    return {
        "result": "created",
        "cs_return_request": _serialize_cs_return(cs_req),
    }


# ───────────────────────── 3) GET /my — 내 주문 목록 ─────────────────────────

@router.get("/v3/orders/my")
def list_my_orders(
    buyer_id: int = Query(..., description="바이어 ID"),
    status: Optional[str] = Query(None, description="필터: PENDING / PAID / CANCELLED / EXPIRED"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    바이어의 주문 목록 + 상태별 건수(status_counts) 반환.
    """
    # 바이어 존재 확인
    buyer = db.query(Buyer).filter(Buyer.id == buyer_id).first()
    if not buyer:
        raise HTTPException(404, f"바이어(ID={buyer_id})를 찾을 수 없습니다.")

    # 상태별 카운트
    all_reservations = (
        db.query(Reservation)
        .filter(Reservation.buyer_id == buyer_id)
        .all()
    )
    status_counts: dict = {}
    for r in all_reservations:
        sv = r.status.value if hasattr(r.status, "value") else str(r.status)
        status_counts[sv] = status_counts.get(sv, 0) + 1

    # 필터 쿼리
    q = db.query(Reservation).filter(Reservation.buyer_id == buyer_id)
    if status:
        q = q.filter(Reservation.status == status)
    orders = q.order_by(Reservation.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": len(all_reservations),
        "status_counts": status_counts,
        "orders": [_serialize_reservation(r) for r in orders],
    }


# ───────────────────────── 4) GET /v3/returns/my — 반품/교환 요청 이력 ─────────────────────────

@router.get("/v3/returns/my")
def list_my_returns(
    buyer_id: int = Query(..., description="바이어 ID"),
    status: Optional[str] = Query(None, description="필터: REQUESTED / SELLER_APPROVED / COMPLETED 등"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    바이어의 반품/교환/취소 요청 이력 반환.
    """
    buyer = db.query(Buyer).filter(Buyer.id == buyer_id).first()
    if not buyer:
        raise HTTPException(404, f"바이어(ID={buyer_id})를 찾을 수 없습니다.")

    q = db.query(CSReturnRequest).filter(CSReturnRequest.buyer_id == buyer_id)
    if status:
        q = q.filter(CSReturnRequest.status == status)

    total = q.count()
    records = q.order_by(CSReturnRequest.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "returns": [_serialize_cs_return(cr) for cr in records],
    }
