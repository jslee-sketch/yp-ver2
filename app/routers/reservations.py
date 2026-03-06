# app/routers/reservations.py
from __future__ import annotations

from typing import Optional, List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from datetime import datetime, timezone
from app import models

from ..database import get_db
from .. import schemas
from ..models import ReservationStatus as ReservationStatusEnum
from ..crud import (
    NotFoundError,
    ConflictError,
    get_offer_remaining_capacity,
    create_reservation,
    cancel_reservation,
    expire_reservations,
    pay_reservation_v35,
    refund_paid_reservation,
    get_reservation as crud_get_reservation,   # ✅ 결제 전 deal_id 얻기용
    search_reservations as crud_search_reservations,
    preview_refund_policy_for_reservation,
    get_refund_summary_for_reservation,
)
from app.schemas import ReservationRefundSummary


router = APIRouter(prefix="/v3_6", tags=["reservations"])


def _translate_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")

# -------------------------------------------------------------------
# 예약 생성 (좌석 홀드)
# -------------------------------------------------------------------
@router.post(
    "",
    response_model=schemas.ReservationOut,
    status_code=status.HTTP_201_CREATED,
    summary="예약 생성(PENDING) — 재고 홀드",
    operation_id="Reservations__Create",
)
def reservations_create(
    body: schemas.ReservationCreate = Body(...),
    db: Session = Depends(get_db),
):
    try:
        return create_reservation(
            db,
            deal_id=body.deal_id,
            offer_id=body.offer_id,
            buyer_id=body.buyer_id,
            qty=body.qty,
            hold_minutes=body.hold_minutes,  # ✅ 추가
        )


    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 예약 결제 — v3.5 고정 포인트(+20/건) + ✅ 디파짓 가드
# -------------------------------------------------------------------
@router.post(
    "/pay",
    response_model=schemas.ReservationOut,
    summary="예약 결제 — reserved→sold, buyer 포인트(+20 고정, 디파짓 가드 포함)",
    operation_id="Reservations__PayV35",
)
def reservations_pay_v35(
    body: schemas.ReservationPayIn = Body(...),
    db: Session = Depends(get_db),
):
    try:
        # 1) 결제 대상 예약 조회(가드에 필요한 deal_id 확보)
        resv = crud_get_reservation(db, body.reservation_id)

        # 2) 결제 수행 (CRUD는 v3.5 규칙으로 +20 고정 적립)
        return pay_reservation_v35(
            db,
            reservation_id=body.reservation_id,
            buyer_id=body.buyer_id,
        )
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 예약 취소 — 홀드 해제 (PENDING → CANCELLED)
# -------------------------------------------------------------------
# app/routers/reservations.py 중 일부

@router.post(
    "/cancel",
    response_model=schemas.ReservationOut,
    summary="예약 취소 — reserved 복구 (PENDING 전용)",
    operation_id="Reservations__CancelPending",
)
def reservations_cancel(
    body: schemas.ReservationCancelIn = Body(...),
    db: Session = Depends(get_db),
):
    try:
        # 1) 먼저 예약을 조회해서 소유자 확인
        resv = crud_get_reservation(db, body.reservation_id)

        # 2) buyer_id가 넘어온 경우, 소유자 가드
        if body.buyer_id is not None and resv.buyer_id != body.buyer_id:
            # pay 쪽이랑 맞춰서 409 + "not owned by buyer"
            raise ConflictError("not owned by buyer")

        # 3) 소유자가 맞으면 실제 취소 처리 (PENDING → CANCELLED)
        return cancel_reservation(
            db,
            reservation_id=body.reservation_id,
            buyer_id=body.buyer_id,
        )
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 결제 후 환불(=취소) 처리 (PAID → CANCELLED, 바이어 포인트 -20 회수)
# -------------------------------------------------------------------
class ReservationRefundIn(BaseModel):
    reservation_id: int
    actor: str = "buyer_cancel"

@router.post(
    "/refund",
    response_model=schemas.ReservationOut,
    summary="결제 후 환불 — PAID → CANCELLED, buyer 포인트 -20 롤백",
    operation_id="Reservations__RefundPaid",
)
def reservations_refund_paid(
    body: ReservationRefundIn = Body(...),
    db: Session = Depends(get_db),
):
    try:
        return refund_paid_reservation(
            db,
            reservation_id=body.reservation_id,
            actor=body.actor,
        )
    except Exception as e:
        _translate_error(e)



class RefundPreviewOut(BaseModel):
    reservation_id: int
    actor: str
    context: Dict[str, Any]
    decision: Dict[str, Any]


@router.get(
    "/refund/preview/{reservation_id}",
    response_model=RefundPreviewOut,
    summary="환불 정책 프리뷰 — 상태 변경 없이 정책/돈 흐름만 보기",
    operation_id="Reservations__RefundPreview",
)
def reservations_refund_preview(
    reservation_id: int = Path(..., ge=1),
    actor: str = Query("buyer_cancel", description="buyer_cancel / seller_cancel / admin_force ..."),
    db: Session = Depends(get_db),
):
    """
    - 예약/오퍼 상태는 **절대 변경하지 않고**
    - RefundContext + RefundDecision 을 계산해서 그대로 반환

    나중에:
    - Admin 툴에서 '이 건 환불하면 누가 무엇을 부담하는지' 미리보기
    - 멀티 시뮬레이션 스크립트에서 정책 검증 등에 활용 가능
    """
    try:
        data = preview_refund_policy_for_reservation(
            db,
            reservation_id=reservation_id,
            actor=actor,
        )
        return data
    except Exception as e:
        _translate_error(e)


@router.get(
    "/refund/summary/{reservation_id}",
    response_model=ReservationRefundSummary,
    summary="예약의 환불 가능 수량/금액 요약 조회",
    operation_id="Reservations_RefundSummary",
)
def api_get_refund_summary(
    reservation_id: int,
    db: Session = Depends(get_db),
):
    """
    예약의 부분환불 가능 상태 요약 조회 API.

    - status != PAID 이거나 환불 가능 수량이 0 이면:
      refundable_qty = 0, refundable_amount_max = 0 로 응답
    - PAID 이고 남은 수량이 있으면:
      남은 수량 전체를 부분환불한다고 가정했을 때의
      최대 환불 가능 금액을 계산해서 반환
    """
    return get_refund_summary_for_reservation(db, reservation_id=reservation_id)



# -------------------------------------------------------------------
# 만료 스윕 — EXPIRED로 전환 & reserved 복구
# -------------------------------------------------------------------
@router.post(
    "/expire",
    summary="만료 스윕 — 기한 지난 PENDING → EXPIRED",
    operation_id="Reservations__ExpireSweep",
)
def reservations_expire(
    db: Session = Depends(get_db),
):
    try:
        n = expire_reservations(db)
        return {"expired": n}
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 예약 단건 조회 (by id)
# -------------------------------------------------------------------
@router.get(
    "/by-id/{reservation_id}",
    response_model=schemas.ReservationOut,
    summary="예약 단건 조회(by id)",
    operation_id="Reservations__GetById",
)
def reservations_get_by_id(
    reservation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        return crud_get_reservation(db, reservation_id)
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 예약 검색 (buyer_id / deal_id / offer_id / status/ after_id)
# -------------------------------------------------------------------
@router.get(
    "/search",
    response_model=List[schemas.ReservationOut],
    summary="예약 검색(필터: reservation_id / deal_id / offer_id / buyer_id / status, 커서 after_id)",
    operation_id="Reservations__Search",
)
def reservations_search(
    reservation_id: Optional[int] = Query(None, ge=1),
    deal_id: Optional[int] = Query(None, ge=1),
    offer_id: Optional[int] = Query(None, ge=1),
    buyer_id: Optional[int] = Query(None, ge=1),
    status: Optional[str] = Query(None, description="PENDING | PAID | CANCELLED | EXPIRED"),
    is_disputed: Optional[bool] = Query(None, description="분쟁 중인 예약만 필터"),
    after_id: Optional[int] = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        enum_status = None
        if status is not None:
            s = status.strip().upper()
            try:
                if s in ReservationStatusEnum.__members__:
                    enum_status = ReservationStatusEnum[s]
                else:
                    enum_status = ReservationStatusEnum(s)
            except Exception:
                valid = ", ".join(ReservationStatusEnum.__members__.keys())
                raise HTTPException(status_code=400, detail=f"invalid status: {status}. use one of [{valid}]")

        rows = crud_search_reservations(
            db,
            reservation_id=reservation_id,
            deal_id=deal_id,
            offer_id=offer_id,
            buyer_id=buyer_id,
            status=enum_status,
            is_disputed=is_disputed,
            after_id=after_id,
            limit=limit,
        )
        return rows
    except HTTPException:
        raise
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 예약 검색(커서 페이징) — 응답에 next_cursor 포함
# -------------------------------------------------------------------
def _to_dict(r: Any) -> dict:
    return {
        "id": r.id,
        "deal_id": r.deal_id,
        "offer_id": r.offer_id,
        "buyer_id": r.buyer_id,
        "qty": r.qty,
        "status": r.status.name if hasattr(r.status, "name") else str(r.status),
        "created_at": r.created_at,
        "expires_at": r.expires_at,
        "paid_at": r.paid_at,
        "cancelled_at": r.cancelled_at,
        "expired_at": r.expired_at,
    }

@router.get(
    "/search_page",
    summary="예약 검색(커서 페이징)",
    operation_id="Reservations__SearchCursor",
)
def reservations_search_page(
    reservation_id: Optional[int] = Query(None),
    deal_id:       Optional[int] = Query(None),
    offer_id:      Optional[int] = Query(None),
    buyer_id:      Optional[int] = Query(None),
    status:        Optional[str] = Query(None, description="PENDING | PAID | CANCELLED | EXPIRED"),
    cursor:        Optional[int] = Query(None, description="이 ID보다 작은 항목부터 조회"),
    limit:         int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    try:
        enum_status = None
        if status is not None:
            s = status.strip().upper()
            try:
                if s in ReservationStatusEnum.__members__:
                    enum_status = ReservationStatusEnum[s]
                else:
                    enum_status = ReservationStatusEnum(s)
            except Exception:
                valid = ", ".join(ReservationStatusEnum.__members__.keys())
                raise HTTPException(status_code=400, detail=f"invalid status: {status}. use one of [{valid}]")

        items = crud_search_reservations(
            db,
            reservation_id=reservation_id,
            deal_id=deal_id,
            offer_id=offer_id,
            buyer_id=buyer_id,
            status=enum_status,
            after_id=cursor,
            limit=limit,
        )
        payload = [_to_dict(x) for x in items]
        next_cursor = items[-1].id if len(items) == limit else None
        return {"count": len(payload), "items": payload, "next_cursor": next_cursor}
    except HTTPException:
        raise
    except Exception as e:
        _translate_error(e)


        
class DisputeOpenIn(BaseModel):
    admin_id: Optional[int] = None
    reason: Optional[str] = None
    buyer_id: Optional[int] = None

@router.post(
    "/{reservation_id}/dispute/open",
    summary="분쟁 오픈 (구매자 or 관리자)",
)
def open_dispute(
    reservation_id: int,
    body: DisputeOpenIn = Body(...),
    db: Session = Depends(get_db),
):
    resv = db.get(models.Reservation, reservation_id)
    if not resv:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if getattr(resv, "is_disputed", False):
        return {"reservation_id": reservation_id, "is_disputed": True, "message": "이미 분쟁 중입니다"}

    now = datetime.now(timezone.utc)
    resv.is_disputed = True
    resv.dispute_opened_at = now
    if body.reason:
        resv.dispute_reason = body.reason
    if body.admin_id:
        resv.dispute_admin_id = body.admin_id

    # 정산 자동 보류: is_disputed=True인 예약의 정산은 admin_settlements에서 필터링됨
    # EventLog 기록
    try:
        log = models.EventLog(
            event_type="dispute_opened",
            actor_type="admin" if body.admin_id else "buyer",
            actor_id=body.admin_id or body.buyer_id or 0,
            entity_type="reservation",
            entity_id=reservation_id,
            description=body.reason or "분쟁 접수",
        )
        db.add(log)
    except Exception:
        pass

    # 알림 발송 (판매자)
    try:
        offer = resv.offer
        if offer and getattr(offer, "seller_id", None):
            from app.routers.notifications import create_notification
            create_notification(
                db, user_id=offer.seller_id,
                type="dispute_opened",
                title="분쟁이 접수되었습니다",
                message=f"예약 R-{reservation_id}에 대한 분쟁이 접수되었습니다. 사유: {body.reason or '미기재'}",
                link_url=f"/seller/settlements",
            )
    except Exception:
        pass

    # 알림 발송 (구매자)
    try:
        if resv.buyer_id:
            from app.routers.notifications import create_notification
            create_notification(
                db, user_id=resv.buyer_id,
                type="dispute_opened",
                title="분쟁이 접수되었습니다",
                message=f"예약 R-{reservation_id}에 대한 분쟁이 접수되었습니다.",
                link_url=f"/my-orders",
            )
    except Exception:
        pass

    db.add(resv)
    db.commit()
    db.refresh(resv)

    return {
        "reservation_id": reservation_id,
        "is_disputed": True,
        "dispute_opened_at": resv.dispute_opened_at,
        "dispute_reason": resv.dispute_reason,
    }


class DisputeCloseIn(BaseModel):
    admin_id: Optional[int] = None
    resolution: Optional[str] = None
    refund_action: Optional[str] = None  # "full_refund" | "partial_refund" | "no_refund" | None

@router.post(
    "/{reservation_id}/dispute/close",
    summary="(관리자) 분쟁 종료",
)
def close_dispute(
    reservation_id: int,
    body: DisputeCloseIn = Body(...),
    db: Session = Depends(get_db),
):
    resv = db.get(models.Reservation, reservation_id)
    if not resv:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if not getattr(resv, "is_disputed", False):
        return {"reservation_id": reservation_id, "is_disputed": False, "message": "분쟁 상태가 아닙니다"}

    now = datetime.now(timezone.utc)
    resv.is_disputed = False
    resv.dispute_closed_at = now
    if body.resolution:
        resv.dispute_resolution = body.resolution
    if body.admin_id:
        resv.dispute_admin_id = body.admin_id

    # EventLog 기록
    try:
        log = models.EventLog(
            event_type="dispute_closed",
            actor_type="admin",
            actor_id=body.admin_id or 0,
            entity_type="reservation",
            entity_id=reservation_id,
            description=body.resolution or "분쟁 종료",
        )
        db.add(log)
    except Exception:
        pass

    # 알림 발송 (판매자 + 구매자)
    try:
        from app.routers.notifications import create_notification
        offer = resv.offer
        if offer and getattr(offer, "seller_id", None):
            create_notification(
                db, user_id=offer.seller_id,
                type="dispute_closed",
                title="분쟁이 종료되었습니다",
                message=f"예약 R-{reservation_id} 분쟁이 종료되었습니다. 결과: {body.resolution or '처리 완료'}",
                link_url=f"/seller/settlements",
            )
        if resv.buyer_id:
            create_notification(
                db, user_id=resv.buyer_id,
                type="dispute_closed",
                title="분쟁이 종료되었습니다",
                message=f"예약 R-{reservation_id} 분쟁이 종료되었습니다. 결과: {body.resolution or '처리 완료'}",
                link_url=f"/my-orders",
            )
    except Exception:
        pass

    db.add(resv)
    db.commit()
    db.refresh(resv)

    return {
        "reservation_id": reservation_id,
        "is_disputed": False,
        "dispute_closed_at": resv.dispute_closed_at,
        "dispute_resolution": resv.dispute_resolution,
    }