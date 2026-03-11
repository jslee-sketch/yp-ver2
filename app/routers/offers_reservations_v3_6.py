# app/routers/offers_reservations_v3_6.py
from __future__ import annotations

import logging
import traceback
from fastapi import Body
from app import models
from app.routers.notifications import create_notification
from app.logic.reservation_phase import compute_reservation_phase

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy import func

from dataclasses import asdict, is_dataclass
from datetime import datetime, date
from enum import Enum
from decimal import Decimal

from ..database import get_db
from ..schemas import (
    OfferCreate, OfferOut,
    ReservationCreate, ReservationOut,
    ReservationPayIn, ReservationCancelIn,
    SellerOfferConfirmIn, SellerOfferCancelIn,
    ReservationRefundIn, RefundPreviewOut,
    ReservationRefundPreviewIn,
    ReservationShipIn,
    ReservationArrivalConfirmIn,
)
from ..crud import (
    create_offer, get_offers,
    create_reservation, cancel_reservation, pay_reservation, expire_reservations,
    seller_confirm_offer, seller_cancel_offer,
    refund_paid_reservation,
    NotFoundError, ConflictError,           # ← 여기서 이미 예외를 가져옴
    get_reservation as crud_get_reservation,
    _map_refund_actor,
    refund_paid_reservation,
    preview_refund_for_paid_reservation,
    mark_reservation_shipped,
    confirm_reservation_arrival,
    create_or_update_settlement_for_reservation,
    create_settlement_for_paid_reservation,
)
from ..models import Offer, Reservation

from ..core.time_policy import TIME_POLICY, _utcnow, _as_utc
from ..core.refund_policy import (
    RefundContext,
    REFUND_POLICY_ENGINE,
    SettlementState,
    CoolingState,
)
from ..core.shipping_policy import calc_shipping_fee
import app.crud as crud

def _xlate(e: Exception):
    """
    내부 예외를 HTTPException으로 변환.
    디버깅 편의를 위해 500 에러에 실제 에러 타입/메시지를 같이 내려줌.
    """
    # 1) crud 에서 온 도메인 예외들은 그대로 HTTP 코드 매핑
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, ConflictError):
        raise HTTPException(status_code=409, detail=str(e))

    # 2) 나머지는 예상 못 한 버그 → 로그 남기고 500
    logging.exception("Unhandled error in offers_reservations_v3_6", exc_info=e)
    traceback.print_exc()

    raise HTTPException(
        status_code=500,
        detail=f"Internal error: {e.__class__.__name__}: {str(e)}",
    )


router = APIRouter(prefix="/v3_6", tags=["v3.6 offers/reservations"])


# v3.6 전용 strict cancel 입력 모델
class ReservationCancelV36In(BaseModel):
    reservation_id: int
    buyer_id: int   # v3.6에서는 필수로 강제


# 파일 상단 아무 데나 헬퍼 추가
def _attach_phase(resv: models.Reservation | None):
    """
    Reservation SQLAlchemy 객체에 .phase 동적 속성을 채워
    ReservationOut / ReservationOutLite 에서 그대로 사용 가능하게 해주는 헬퍼.
    """
    if resv is None:
        return None
    try:
        resv.phase = compute_reservation_phase(resv)
    except Exception:
        # phase 계산 실패해도 메인 로직은 깨지지 않도록 방어
        resv.phase = None
    return resv


def _json_safe(v):
    """dataclass/Enum/datetime 등을 JSON 직렬화 가능한 형태로 변환"""
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, Enum):
        return v.value
    if is_dataclass(v):
        return {k: _json_safe(val) for k, val in asdict(v).items()}
    if isinstance(v, dict):
        return {k: _json_safe(val) for k, val in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_json_safe(x) for x in v]
    # 마지막 fallback
    return str(v)

# -----------------------------
# Offers
# -----------------------------
@router.post("/offers", response_model=OfferOut, status_code=201, summary="오퍼 생성")
def api_create_offer(payload: OfferCreate, db: Session = Depends(get_db)):
    try:
        return create_offer(db, payload)
    except Exception as e:
        _xlate(e)

@router.get("/offers", response_model=List[OfferOut], summary="오퍼 목록")
def api_list_offers(
    deal_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    try:
        rows = get_offers(db)
        if deal_id is not None:
            rows = [o for o in rows if o.deal_id == deal_id]
        return rows
    except Exception as e:
        _xlate(e)


@router.patch("/offers/{offer_id}", summary="오퍼 수정 (셀러)")
def api_patch_offer(
    offer_id: int = Path(..., ge=1),
    body: dict = Body(...),
    db: Session = Depends(get_db),
):
    """
    오퍼 수정 API.
    - 수정 가능 필드: price, total_available_qty, delivery_days,
      shipping_mode, shipping_fee_per_reservation, shipping_fee_per_qty, is_active
    - price 변경은 sold_qty == 0 일 때만 허용
    """
    offer = db.query(models.Offer).filter(models.Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="offer_not_found")

    ALLOWED = {
        "price", "total_available_qty", "delivery_days",
        "shipping_mode", "shipping_fee_per_reservation", "shipping_fee_per_qty", "is_active",
    }
    updates = {k: v for k, v in body.items() if k in ALLOWED}

    if "price" in updates and int(getattr(offer, "sold_qty", 0) or 0) > 0:
        raise HTTPException(status_code=409, detail="cannot change price after sales started")

    for k, v in updates.items():
        setattr(offer, k, v)

    db.commit()
    db.refresh(offer)
    return offer


@router.post("/offers/{offer_id}/confirm", response_model=OfferOut, summary="셀러 오퍼 확정")
def api_confirm_offer(
    offer_id: int = Path(..., ge=1),
    body: SellerOfferConfirmIn = SellerOfferConfirmIn(),
    db: Session = Depends(get_db),
):
    """
    오퍼 확정 엔드포인트 (idempotent)
    - 이미 is_confirmed=True 면 200으로 현재 상태 그대로 반환
    - 기본 정책:
        * 매진(= sold_qty == total_available_qty) AND PENDING 예약 0건 이어야 확정 가능
        * 위 조건 미충족 시 409 (cannot_confirm_not_soldout / cannot confirm while PENDING reservations exist)
        * force=True 면 조건 무시하고 확정
    - 확정 성공 시:
        * offer.is_confirmed=True, offer.is_active=False
        * 셀러/액츄에이터 알림 전송
    """
    try:
        # 1) 오퍼 로드
        offer = (
            db.query(models.Offer)
            .filter(models.Offer.id == offer_id)
            .with_for_update()
            .first()
        )
        if not offer:
            raise HTTPException(status_code=404, detail="offer_not_found")

        # 2) 이미 확정이면 그냥 현재 상태 반환 (idempotent)
        if getattr(offer, "is_confirmed", False):
            db.refresh(offer)
            return offer

        # 3) 현재 상태 점검
        total = int(offer.total_available_qty or 0)
        sold = int(offer.sold_qty or 0)

        # 이 오퍼 기준 PENDING 예약 수
        pending_cnt = (
            db.query(func.count(models.Reservation.id))
            .filter(
                models.Reservation.offer_id == offer.id,
                models.Reservation.status == "PENDING",
            )
            .scalar()
        ) or 0

        is_soldout = (total > 0 and sold >= total)

        # 4) 강제 확정이 아니면 정책 검증
        if not body.force:
            if pending_cnt > 0:
                # PENDING 예약 존재
                raise HTTPException(
                    status_code=409,
                    detail="cannot confirm while PENDING reservations exist",
                )
            if not is_soldout:
                # 매진 아님
                raise HTTPException(
                    status_code=409,
                    detail="cannot_confirm_not_soldout",
                )

        # 5) 확정 처리
        offer.is_confirmed = True
        offer.is_active = False

        # (선택) 정책 포인트 부여 로직: award_on_full
        # - 전량 판매 & pending 0건일 때 +30pt 같은 정책을 쓰려면 아래처럼 조건부로 처리
        # - 지금은 body.force로 넘어온 경우도 award_on_full을 부여할지 정책에 따라 분기 가능
        try:
            award_on_full = 30  # 기존 주석 유지: 정책 상수
            if award_on_full and (is_soldout and pending_cnt == 0):
                # 예: seller point 적립 (모델/스키마에 맞춰 구현)
                pass
        except Exception:
            # 포인트 적립 실패는 확정 자체를 실패로 만들지 않음
            logging.exception("failed to award seller points on offer confirm")

        # 6) 알림 전송 (셀러/액츄에이터)
        try:
            # GMV 계산
            gmv = int((offer.price or 0) * sold)

            # 셀러 알림
            if offer.seller_id:
                create_notification(
                    db,
                    user_id=offer.seller_id,
                    type="offer_confirmed",
                    title=f"오퍼 #{offer.id}가 확정되었습니다.",
                    message=f"딜 #{offer.deal_id} 오퍼가 전량 판매되어 확정되었습니다. (판매수량: {sold}, GMV: {gmv}원)",
                    meta={
                        "role": "seller",
                        "deal_id": offer.deal_id,
                        "offer_id": offer.id,
                        "sold_qty": sold,
                        "gmv": gmv,
                    },
                )

                # 액츄에이터 알림 (셀러에 연결되어 있을 때)
                seller = db.query(models.Seller).filter(models.Seller.id == offer.seller_id).first()
                actuator_id = getattr(seller, "actuator_id", None) if seller else None
                if actuator_id:
                    create_notification(
                        db,
                        user_id=actuator_id,
                        type="actuator_seller_offer_confirmed",
                        title="연결된 셀러의 오퍼가 확정되었습니다.",
                        message=(
                            f"당신이 모집한 셀러 #{offer.seller_id} 의 오퍼 #{offer.id}가 "
                            f"전량 판매되어 확정되었습니다. (GMV: {gmv}원)"
                        ),
                        meta={
                            "role": "actuator",
                            "seller_id": offer.seller_id,
                            "deal_id": offer.deal_id,
                            "offer_id": offer.id,
                            "sold_qty": sold,
                            "gmv": gmv,
                        },
                    )

                    # (선택) 추천자 알림 타입을 따로 쓰는 경우가 있으면 추가
                    # create_notification(... type="offer_confirmed_by_seller", ...)

        except Exception:
            logging.exception("failed to create notifications on offer confirm")

        # 7) 커밋 및 반환
        db.commit()
        db.refresh(offer)
        return offer

    except HTTPException:
        # 위에서 명시적으로 올린 것은 그대로 전달
        raise
    except Exception as e:
        # 기존 프로젝트의 예외 매핑 사용
        _xlate(e)



@router.post("/offers/{offer_id}/cancel", response_model=OfferOut, summary="셀러 오퍼 취소(부분 환불/포인트 롤백 포함)")
def api_cancel_offer(
    offer_id: int = Path(..., ge=1),
    body: SellerOfferCancelIn = SellerOfferCancelIn(),
    db: Session = Depends(get_db),
):
    try:
        return seller_cancel_offer(
            db,
            offer_id=offer_id,
            penalize=body.penalize,
            allow_paid=body.allow_paid,
            reverse_buyer_points=body.reverse_buyer_points,
            buyer_point_per_qty=body.buyer_point_per_qty,
        )
    except Exception as e:
        _xlate(e)

# -----------------------------
# Reservations
# -----------------------------
@router.post("/reservations", response_model=ReservationOut, status_code=201, summary="예약 생성(좌석 홀드)")
def api_create_reservation(payload: ReservationCreate, db: Session = Depends(get_db)):
    logging.warning("[TRACE] HIT v3_6 reservations create: offers_reservations_v3_6.py")
    try:
        resv = create_reservation(
            db,
            deal_id=payload.deal_id,
            offer_id=payload.offer_id,
            buyer_id=payload.buyer_id,
            qty=payload.qty,
            hold_minutes=payload.hold_minutes,
        )
        return _attach_phase(resv)
    except Exception as e:
        _xlate(e)


@router.get(
    "/reservations/by-id/{reservation_id}",
    response_model=ReservationOut,
    summary="예약 단건 조회(v3.6)",
)
def api_get_reservation_v36(
    reservation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        resv = crud_get_reservation(db, reservation_id)
        return _attach_phase(resv)
    except Exception as e:
        _xlate(e)



@router.post("/reservations/cancel", response_model=ReservationOut, summary="예약 취소(v3.6, strict 소유자 체크)")
def api_cancel_reservation(
    payload: ReservationCancelV36In,
    db: Session = Depends(get_db),
):
    """
    v3.6 예약 취소 규칙:
    - 예약의 buyer_id 와 payload.buyer_id 가 반드시 일치해야 함
    - 아니면 409 "not owned by buyer"
    - 상태 체크(PENDING 전용)는 crud.cancel_reservation 에서 처리
    """
    try:
        # 1) 예약 조회
        resv = crud_get_reservation(db, payload.reservation_id)

        # 2) 소유자 가드
        if resv.buyer_id != payload.buyer_id:
            raise ConflictError("not owned by buyer")

        # 3) 실제 취소 처리 (PENDING → CANCELLED, reserved 복구)
        return cancel_reservation(
            db,
            reservation_id=payload.reservation_id,
            buyer_id=payload.buyer_id,
        )
    except Exception as e:
        _xlate(e)


@router.post("/reservations/pay", response_model=ReservationOut, summary="예약 결제(확정)")
def api_pay_reservation(payload: ReservationPayIn, db: Session = Depends(get_db)):
    try:
        # ✅ 1) 결제 만료 선행 가드 (v3.6 타임라인 정책 반영)
        resv = db.get(Reservation, payload.reservation_id)
        if not resv:
            raise NotFoundError("Reservation not found")

        # (선택) 소유자 체크를 여기서도 한 번 선행해도 되지만,
        # 보통은 CRUD 레이어에서 최종 가드를 하게 남겨둬도 OK
        # if resv.buyer_id != payload.buyer_id:
        #     raise ConflictError("not owned by buyer")

        if resv.expires_at:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc)
            exp = resv.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)

            if exp < now:
                raise ConflictError("reservation payment window expired")

        # ✅ 2) 실제 결제 로직은 기존 CRUD pay_reservation(=v3.5 SSOT)에 위임
        #    - CRUD 시그니처는 (db, reservation_id, paid_amount) 임
        #    - buyer_id는 이 라우터에서 "검증용"으로만 사용하고 CRUD로 넘기지 않는다.

        # (선택) 소유권 체크를 여기서 확정
        if int(getattr(resv, "buyer_id", 0) or 0) != int(getattr(payload, "buyer_id", 0) or 0):
            raise ConflictError("not owned by buyer")

        paid_amount = int(getattr(payload, "paid_amount", 0) or 0)
        if paid_amount <= 0:
            # v3.6 payload에 paid_amount가 없거나 0이면 SSOT인 reservation.amount_total로 대체
            paid_amount = int(getattr(resv, "amount_total", 0) or 0)
        
        paid = pay_reservation(
            db,
            reservation_id=int(payload.reservation_id),
            paid_amount=paid_amount,
        )

        # ✅ 1) 결제 결과는 먼저 커밋해서 확정 (결제가 SSOT)
        db.commit()
        db.refresh(paid)

        # ✅ 2) 그 다음 settlement는 best-effort로 별도 트랜잭션에서 시도
        try:
            crud.create_settlement_for_paid_reservation(db, reservation_id=int(paid.id))
            db.commit()
        except Exception as e:
            logging.exception("[SETTLEMENT] snapshot create failed (best-effort)", exc_info=e)
            try:
                db.rollback()
            except Exception:
                pass

        return _attach_phase(paid)


        # ✅ 2-1) 결제 직후 정산 스냅샷 생성/갱신 (SSOT: Reservation.amount_total)
        # - v3.6 /reservations/pay 경로에서 settlement가 생성되지 않던 버그를 막는다.
        try:
            create_or_update_settlement_for_reservation(db, paid)
            db.commit()
            db.refresh(paid)
        except Exception as _e:
            # 정산 실패가 결제 자체를 망치면 안 되므로 best-effort
            logging.exception("[SETTLEMENT] create_or_update_settlement_for_reservation failed (v3_6 pay)")


        # ✅ 3) 🔔 결제 완료 알림 (buyer / seller / actuator)
        try:
            # 3-1) 바이어에게 알림
            if paid.buyer_id:
                create_notification(
                    db,
                    user_id=paid.buyer_id,
                    type="reservation_paid",
                    title=f"예약 #{paid.id} 결제가 완료되었습니다.",
                    message=(
                        f"딜 #{paid.deal_id} / 오퍼 #{paid.offer_id} "
                        f"예약 결제가 완료되었습니다."
                    ),
                    meta={
                        "role": "buyer",
                        "deal_id": paid.deal_id,
                        "offer_id": paid.offer_id,
                        "reservation_id": paid.id,
                    },
                )

            # 3-2) 셀러에게 알림 (해당 오퍼의 seller_id 기준)
            offer = db.get(models.Offer, paid.offer_id)
            seller_id = int(getattr(offer, "seller_id", 0) or 0) if offer else 0
            if seller_id:
                create_notification(
                    db,
                    user_id=seller_id,
                    type="reservation_paid_on_offer",
                    title=f"오퍼 #{paid.offer_id}에 결제 완료된 예약이 있습니다.",
                    message=(
                        f"딜 #{paid.deal_id} / 예약 #{paid.id} "
                        f"결제가 완료되었습니다."
                    ),
                    meta={
                        "role": "seller",
                        "deal_id": paid.deal_id,
                        "offer_id": paid.offer_id,
                        "reservation_id": paid.id,
                    },
                )

            # 3-3) 액추에이터에게 알림 (해당 오퍼에 actuator_id 가 있는 경우)
            actuator_id = int(getattr(offer, "actuator_id", 0) or 0) if offer else 0
            if actuator_id:
                create_notification(
                    db,
                    user_id=actuator_id,
                    type="actuator_commission_earned",
                    title=f"추천한 셀러의 오퍼 #{paid.offer_id}에서 결제가 발생했습니다.",
                    message=(
                        f"딜 #{paid.deal_id} / 예약 #{paid.id} 에서 결제가 완료되었습니다. "
                        f"해당 거래에 대한 커미션이 발생할 수 있습니다."
                    ),
                    meta={
                        "role": "actuator",
                        "deal_id": paid.deal_id,
                        "offer_id": paid.offer_id,
                        "reservation_id": paid.id,
                        "seller_id": seller_id,
                    },
                )

        except Exception as notify_err:
            # 알림 실패로 결제가 망가지면 안 되니까, 로그만 찍고 무시
            logging.exception(
                "failed to create reservation_paid notifications",
                exc_info=notify_err,
            )

        # ✅ 4) 최종 결제된 예약 객체 응답
        return _attach_phase(paid)
    except Exception as e:
        _xlate(e)


@router.post(
    "/reservations/{reservation_id}/ship",
    response_model=ReservationOut,
    summary="셀러: 예약 발송 완료 처리",
)
    
def api_mark_reservation_shipped(
    reservation_id: int = Path(..., ge=1),
    body: ReservationShipIn = Body(default_factory=ReservationShipIn),
    db: Session = Depends(get_db),
):
    """
    셀러가 '발송 완료' 버튼 누르는 API.

    규칙 (crud.mark_reservation_shipped 기준):
    - 예약 status 는 반드시 PAID 여야 함
    - (선택) seller_id 가 넘어오면 해당 셀러의 예약인지 검증
    - 최초 1회만 shipped_at 을 세팅 (이미 있으면 그대로 반환 가능)
    """
    try:
        resv = mark_reservation_shipped(
            db,
            reservation_id=reservation_id,
            seller_id=body.seller_id,
            shipping_carrier=getattr(body, "shipping_carrier", None),
            tracking_number=getattr(body, "tracking_number", None),
        )

        # ✅ 알림: SHIPPING_STARTED → 구매자
        try:
            from app.services.notification_service import send_notification
            buyer_id = getattr(resv, "buyer_id", None)
            if buyer_id:
                from app import models as _models
                _deal = db.query(_models.Deal).get(resv.deal_id) if getattr(resv, "deal_id", None) else None
                product_name = getattr(_deal, "product_name", "") or "" if _deal else ""
                courier = getattr(body, "shipping_carrier", "") or ""
                tracking = getattr(body, "tracking_number", "") or ""
                send_notification(
                    db, user_id=buyer_id, role="buyer",
                    event_type="SHIPPING_STARTED",
                    variables={"product_name": product_name, "courier": courier, "tracking_number": tracking},
                    reservation_id=reservation_id,
                )
        except Exception:
            pass

        # ✅ 응답 품질: phase 채우기 (DB 영향 없음)
        try:
            resv = _attach_phase(resv)
        except Exception:
            pass

        return resv
    except Exception as e:
        _xlate(e)



@router.post(
    "/reservations/{reservation_id}/arrival-confirm",
    response_model=ReservationOut,
    summary="바이어: 예약 도착 확인",
)
def api_confirm_reservation_arrival(
    reservation_id: int = Path(..., ge=1),
    body: ReservationArrivalConfirmIn = ...,
    db: Session = Depends(get_db),
):
    """
    바이어가 '도착 확인' 버튼 누르는 API.

    규칙 (crud.confirm_reservation_arrival 기준):
    - 예약 status 는 반드시 PAID 여야 함
    - buyer_id 가 본인 예약인지 검증
    - shipped_at 이 없으면 도착확인 불가
    - 최초 1회만 arrival_confirmed_at / delivered_at 을 now 로 세팅
    - 내부에서 actuator 커미션 ready_at 세팅 시도
    """
    try:
        resv = confirm_reservation_arrival(
        db,
        reservation_id=reservation_id,
        buyer_id=body.buyer_id,
        )

        # ✅ 알림: PURCHASE_CONFIRMED → 구매자
        try:
            from app.services.notification_service import send_notification
            b_id = getattr(resv, "buyer_id", None) or body.buyer_id
            if b_id:
                from app import models as _models
                _deal = db.query(_models.Deal).get(resv.deal_id) if getattr(resv, "deal_id", None) else None
                product_name = getattr(_deal, "product_name", "") or "" if _deal else ""
                send_notification(
                    db, user_id=b_id, role="buyer",
                    event_type="PURCHASE_CONFIRMED",
                    variables={"product_name": product_name},
                    reservation_id=reservation_id,
                )
        except Exception:
            pass

        try:
            resv = _attach_phase(resv)
        except Exception:
            pass

        return resv
    except Exception as e:
        _xlate(e)



@router.post("/maintenance/reservations/expire", summary="만료 스윕 실행", status_code=200)
def api_expire_reservations(db: Session = Depends(get_db)):
    try:
        count = expire_reservations(db)
        return {"expired": count}
    except Exception as e:
        _xlate(e)


# ✅ 여기 추가
@router.post(
    "/reservations/refund",
    response_model=ReservationOut,
    summary="예약 환불 실행 (전체/부분)",
)
def api_refund_reservation(
    payload: ReservationRefundIn,
    db: Session = Depends(get_db),
):
    try:
        # ---------------------------------------------------------
        # ✅ v3.6 refund payload에는 actor가 없다.
        #    requested_by(BUYER/SELLER/ADMIN) → actor 문자열로 매핑해서 crud에 전달
        # ---------------------------------------------------------
        requested_by = getattr(payload, "requested_by", "BUYER") or "BUYER"
        requested_by = str(requested_by).upper()

        if requested_by == "SELLER":
            actor = "seller_fault"
        elif requested_by == "ADMIN":
            actor = "admin_cancel"
        else:
            actor = "buyer_cancel"

        reason = getattr(payload, "reason", "") or ""
        quantity_refund = getattr(payload, "quantity_refund", None)
        shipping_refund_override = getattr(payload, "shipping_refund_override", None)
        shipping_refund_override_reason = getattr(payload, "shipping_refund_override_reason", None)
        refund_type = getattr(payload, "refund_type", "refund") or "refund"

        # ✅ 환불 실행
        result = refund_paid_reservation(
            db,
            reservation_id=payload.reservation_id,
            actor=actor,
            quantity_refund=quantity_refund,
            reason=reason,
            shipping_refund_override=shipping_refund_override,
            shipping_refund_override_reason=shipping_refund_override_reason,
            refund_type=refund_type,
        )

        # ✅ 알림: REFUND_REQUESTED → 판매자 + REFUND_COMPLETE → 구매자
        try:
            from app.services.notification_service import send_notification
            from app import models as _models
            # product_name, seller_id 조회
            _resv = db.query(_models.Reservation).get(payload.reservation_id) if payload.reservation_id else None
            _offer = db.query(_models.Offer).get(_resv.offer_id) if _resv and getattr(_resv, "offer_id", None) else None
            _deal = db.query(_models.Deal).get(_resv.deal_id) if _resv and getattr(_resv, "deal_id", None) else None
            _product_name = getattr(_deal, "product_name", "") or "" if _deal else ""
            _seller_id = getattr(_offer, "seller_id", None) if _offer else None
            _buyer_id = getattr(_resv, "buyer_id", None) if _resv else None

            if _seller_id:
                send_notification(
                    db, user_id=_seller_id, role="seller",
                    event_type="REFUND_REQUESTED",
                    variables={"product_name": _product_name, "refund_reason": reason or "미지정"},
                    reservation_id=payload.reservation_id,
                )
            if _buyer_id:
                _refund_amt = getattr(result, "refunded_amount_total", 0) or getattr(result, "refund_amount", 0) or 0
                send_notification(
                    db, user_id=_buyer_id, role="buyer",
                    event_type="REFUND_COMPLETE",
                    variables={"product_name": _product_name, "refund_amount": str(int(_refund_amt))},
                    reservation_id=payload.reservation_id,
                )
        except Exception:
            pass

        # ✅ 응답용: phase 붙이기 (DB 영향 X)
        try:
            result = _attach_phase(result)
        except Exception:
            pass

        return result

    except Exception as e:
        _xlate(e)


@router.post(
    "/reservations/refund/preview",
    response_model=Dict[str, Any],   # 그대로 dict 응답 유지
    summary="예약 환불 정책 미리보기",
)
def api_refund_preview_reservation(
    body: ReservationRefundPreviewIn,
    db: Session = Depends(get_db),
):
    """
    PAID 예약에 대해 '환불 버튼을 누르면 어떻게 처리될지' 미리 보기용 엔드포인트.

    - DB 상태(예약/포인트/정산)는 건드리지 않고
    - RefundPolicyEngine 이 내려주는 RefundContext + RefundDecision 을
      dataclass → dict 로 변환해서 그대로 반환한다.
    - quantity_refund 가 있으면 부분환불 기준으로 계산.
    """
    try:
        # crud 쪽에서 컨텍스트 계산 + 정책 엔진 호출
        ctx, decision = preview_refund_for_paid_reservation(
            db,
            reservation_id=body.reservation_id,
            actor=body.actor,
            quantity_refund=getattr(body, "quantity_refund", None),  # ★ 추가된 부분
        )

        return {
            "reservation_id": int(getattr(ctx, "reservation_id", body.reservation_id) or body.reservation_id),
            "context": _json_safe(ctx),
            "decision": _json_safe(decision),
        }

    except Exception as e:
        _xlate(e)