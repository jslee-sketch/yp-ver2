# app/routers/offers_reservations_v3_6.py
from __future__ import annotations

import logging
import traceback
from app import models
from app.routers.notifications import create_notification
from app.logic.reservation_phase import compute_reservation_phase

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy import func
from dataclasses import asdict

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

#-------------------------




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

        # ✅ 2) 실제 결제 로직은 기존 pay_reservation 에게 위임
        paid = pay_reservation(
            db,
            reservation_id=payload.reservation_id,
            buyer_id=payload.buyer_id,
            buyer_point_per_qty=payload.buyer_point_per_qty,
        )

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
    body: ReservationShipIn = ReservationShipIn(),
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
        )
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
    """
    실제 환불 실행 엔드포인트.
    - PAID 상태가 아니면 409
    - refund_policy_engine 을 통해 결정 후
      - offers.sold_qty 롤백
      - reservation.status/phase 갱신
      - 포인트 회수 기록 추가
    - payload.quantity_refund:
      - None 또는 생략 → 전체환불
      - 1..qty → 부분환불
    """
    try:
        return refund_paid_reservation(
            db,
            reservation_id=payload.reservation_id,
            actor=payload.actor,
            quantity_refund=getattr(payload, "quantity_refund", None),  # ★ 부분환불 수량전달
        )
    except Exception as e:
        _xlate(e)


# app/routers/offers_reservations_v3_6.py 상단 import들 아래 쯤에 추가

from ..core.refund_policy import RefundContext, RefundDecision  # 이미 import 되어 있으면 생략

def _build_refund_context_out(ctx: RefundContext, ModelCls):
    """
    RefundContext(dataclass) -> RefundPreviewContextOut(Pydantic)
    - dataclass에 필드가 더 많아도, Pydantic 모델이 가지고 있는 필드만 골라서 매핑
    - Enum 타입은 .value 나 .name 으로 문자열로 바꿔줌
    """
    data = {}
    # Pydantic v2: model_fields 사용
    for field_name in ModelCls.model_fields.keys():
        if not hasattr(ctx, field_name):
            continue
        val = getattr(ctx, field_name)
        # enum이면 value/text로 변환
        if hasattr(val, "value"):
            val = val.value
        data[field_name] = val
    return ModelCls(**data)


def _build_refund_decision_out(decision: RefundDecision, ModelCls):
    """
    RefundDecision(dataclass) -> RefundPreviewDecisionOut(Pydantic)
    - 마찬가지로 모델이 가진 필드만 골라서 매핑
    """
    data = {}
    for field_name in ModelCls.model_fields.keys():
        if not hasattr(decision, field_name):
            continue
        val = getattr(decision, field_name)
        if hasattr(val, "value"):
            val = val.value
        data[field_name] = val
    return ModelCls(**data)



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

        # dataclass → dict
        ctx_dict = asdict(ctx)
        decision_dict = asdict(decision)

        return {
            "reservation_id": ctx.reservation_id,
            "context": ctx_dict,
            "decision": decision_dict,
        }
    except Exception as e:
        _xlate(e)