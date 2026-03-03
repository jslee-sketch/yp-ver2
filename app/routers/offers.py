# app/routers/offers.py
from __future__ import annotations
from app import crud as crud_v36

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session, relationship
from sqlalchemy import func
import logging
from app.database import get_db
from app.schemas import OfferOut

import json
from app.core.time_policy import TIME_POLICY, _as_utc

from .. import crud
from app.database import get_db
from app.config import rules_v3_5 as RV
from app import crud, schemas, models

from app.config import project_rules as R  # 정책/시간 계산 등

from app.crud import seller_approval_status, mark_reservation_shipped
from app.core.time_policy import _utcnow
from ..crud import get_reservation as crud_get_reservation, NotFoundError as CrudNotFoundError
from ..crud import (
    get_reservation as crud_get_reservation,
    NotFoundError as CrudNotFoundError,
)
from app.routers.notifications import create_notification #알람 헬퍼
import logging


# ✅ 셀러 평점 집계 모델 (없으면 그냥 None)
try:
    from ..models import SellerRatingAggregate  # seller_rating_aggregates 테이블
except Exception:
    SellerRatingAggregate = None  # type: ignore


from app.policy.api import payment_timeout_minutes
from app.policy import api as policy_api
from app.routers import deals, admin_anchor

# ─────────────────────────────────────────────────────
# 에러 유틸
# ─────────────────────────────────────────────────────
class NotFoundError(Exception):
    ...


class ConflictError(Exception):
    ...


def _is_conflict(exc: Exception) -> bool:
    if isinstance(exc, HTTPException) and exc.status_code == status.HTTP_409_CONFLICT:
        return True
    name = exc.__class__.__name__
    if name in {"ConflictError", "DepositConflict"}:
        return True

    return False


def _translate_error(exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if _is_conflict(exc):
        detail = (str(exc))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc) or "not found")

    logging.exception("offers router error", exc_info=exc)
    import traceback
    print("TRACEBACK:\n" + "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))    
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": exc.__class__.__name__, "msg": str(exc)},
    )


# ─────────────────────────────────────────────────────
# 공용 CRUD import
# ─────────────────────────────────────────────────────
from ..crud import (
    get_offer_remaining_capacity,
    create_reservation,
    cancel_reservation,
    expire_reservations,
    pay_reservation,
    confirm_offer_if_soldout,
    refund_paid_reservation,
    preview_refund_for_paid_reservation,
    get_reservation as crud_get_reservation,
    update_offer_total_qty,
)


def _percent_to_ratio(p) -> float:
    """
    10  → 0.10
    0.1 → 0.10   (이미 비율로 들어온 경우)
    None / 이상값 → 0.0
    """
    try:
        v = float(p)
    except Exception:
        return 0.0
    if v <= 0:
        return 0.0
    # 1보다 크면 "10 == 10%" 로 보고 /100
    return v / 100.0 if v > 1.0 else v


# -------------------------------------------------------
# Reservation 에 저장할 OfferPolicy 스냅샷 헬퍼
# -------------------------------------------------------

def _make_policy_snapshot(policy: Optional[models.OfferPolicy]) -> Optional[str]:
    """
    OfferPolicy ORM 객체를 JSON 문자열로 직렬화해서
    Reservation.policy_snapshot_json 에 저장할 용도.
    """
    if policy is None:
        return None

    try:
        data: Dict[str, Any] = {
            "id": policy.id,
            "offer_id": policy.offer_id,
            "cancel_rule": policy.cancel_rule,
            "cancel_within_days": policy.cancel_within_days,
            "extra_text": policy.extra_text,
            "created_at": (
                policy.created_at.isoformat()
                if getattr(policy, "created_at", None)
                else None
            ),
        }
        return json.dumps(data, ensure_ascii=False)
    except Exception:
        # 스냅샷 실패해도 예약 자체는 막지 않기 위해
        return None


# ---------------------------------------------------------
# 🔎 Reservation ↔ Policy helper
# ---------------------------------------------------------
def _get_effective_policy_for_reservation(
    db: Session,
    resv: models.Reservation,
) -> Optional[schemas.ReservationPolicySnapshot]:
    """
    1순위: reservation.policy_snapshot_json (결제 시점 스냅샷)
    2순위: 현재 OfferPolicy (구 데이터 호환용)
    둘 다 없으면 None 반환
    """
    # 1) 스냅샷 우선
    snapshot = getattr(resv, "policy_snapshot_json", None)
    if snapshot:
        try:
            data = json.loads(snapshot)
            return schemas.ReservationPolicySnapshot.model_validate(data)
        except Exception:
            pass

    # 2) fallback: 현재 OfferPolicy
    try:
        policy = crud.get_offer_policy(db, resv.offer_id)
    except Exception:
        policy = None

    if not policy:
        return None

    return schemas.ReservationPolicySnapshot(
        cancel_rule=policy.cancel_rule,
        cancel_within_days=policy.cancel_within_days,
        extra_text=policy.extra_text,
        id=policy.id,
        offer_id=policy.offer_id,
        created_at=policy.created_at,
    )


# ---------------------------------------------------------
# 🔧 naive/aware datetime 보정 헬퍼
# ---------------------------------------------------------
def _as_aware(dt):
    """
    DB 에서 가져온 datetime 이 tz 정보가 없으면(naive)
    UTC 기준 aware 로 강제 변환.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------
# 🔎 취소 가능 여부 정책 검사 헬퍼
# ---------------------------------------------------------
def _ensure_cancel_allowed_by_policy(
    resv: models.Reservation,
    db: Session,
    actor: str,
):
    """
    예약의 상태 + 취소/환불 정책 기준으로
    '취소 가능한지' 검사한다.
    - actor == "buyer_cancel" 일 때만 A1~A4 정책을 강하게 적용
    - admin_cancel, seller_fault 등은 정책 무시하고 취소 허용
    """
    # 0) 상태 체크
    status_val = getattr(resv, "status", None)
    name = getattr(status_val, "name", None) or str(status_val)

    # PENDING 은 언제든 취소 가능
    if name == "PENDING":
        return

    # PAID 가 아닌 경우에는 여기서 취소 허용하지 않음
    if name != "PAID":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"cannot cancel: status={name}",
        )

    # 1) actor 가 buyer_cancel 이 아니면 정책 체크 스킵
    if actor != "buyer_cancel":
        return

    # 2) 이 예약에 적용되는 정책(스냅샷 or 현재 policy) 가져오기
    policy = _get_effective_policy_for_reservation(db, resv)
    if not policy:
        # 정책 정보가 없으면 보수적으로도 막지 않고 통과시킴
        return

    now = datetime.now(timezone.utc)

    # 🔹 DB 값 → 모두 aware 로 보정
    shipped_at = _as_aware(getattr(resv, "shipped_at", None))
    delivered_at = _as_aware(
        getattr(resv, "delivered_at", None)
        or getattr(resv, "arrival_confirmed_at", None)
    )

    # ⚠ 기본 룰: 발송 전이면 어떤 정책이든 취소 가능
    if shipped_at is None:
        return

    rule = policy.cancel_rule

    # A2: 발송 후 취소 불가
    if rule == "A2":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="cancel_not_allowed_after_shipped",
        )

    # A3: 배송완료/수령확인 기준 X일 이내만 취소 가능
    if rule == "A3":
        days = policy.cancel_within_days or 0
        if days <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cancel_not_allowed_after_shipped",
            )

        base = delivered_at or shipped_at
        base = _as_aware(base)   # 혹시 모를 naive 보정 (안전용)

        # base 가 None 일 일은 거의 없지만, 방어적으로 허용 처리
        if base is None:
            return

        limit = base + timedelta(days=days)
        # 👉 여기서 now(aware) vs limit(aware) 비교 → 더 이상 TypeError 안 남
        if now > limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cancel_period_expired",
            )
        return

    # A1, A4: 여기서는 별도 제한 없음 (추가 제약은 extra_text 로 안내)
    return



# ─────────────────────────────────────────────────────
# A) /reservations (v3.5)
# ─────────────────────────────────────────────────────
router_resv = APIRouter(prefix="/reservations", tags=["reservations v3.5"])

@router_resv.post(
    "",
    response_model=schemas.ReservationOut,
    status_code=status.HTTP_201_CREATED,
    summary="예약 생성(PENDING) — 디포짓 없이 재고 홀드",
)
def api_create_reservation(
    body: schemas.ReservationCreate = Body(...),
    db: Session = Depends(get_db),
):
    logging.warning("[TRACE] HIT v3_5 reservations create: offers.py")

    """
    v3.5 예약 생성 (디포짓 제거 버전)

    ✅ 변경 포인트(B안):
    - v3.5에서 직접 reserved_qty/Reservation row 생성/amount_total 계산을 하지 않는다.
    - v3.6 SSOT(crud.create_reservation)에 위임하여
      amount_goods/amount_shipping/amount_total + policy_snapshot_json + reserved_qty까지
      DB에 일관되게 저장되게 한다.
    """

    try:
        # (선택) trace용
        if body.deal_id == 999999:
            raise HTTPException(status_code=418, detail="TRACE: api_create_reservation reached")

        # 0) 기본 검증 ---------------------------------------------------
        deal = db.query(models.Deal).get(body.deal_id)
        if not deal:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

        offer = db.query(models.Offer).get(body.offer_id)
        if not offer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")

        if int(getattr(offer, "deal_id", 0)) != int(body.deal_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="offer does not belong to given deal",
            )

        buyer = db.query(models.Buyer).get(body.buyer_id)
        if not buyer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Buyer not found")

        # 1) hold_minutes 계산 ------------------------------------------
        #    (v3.6 SSOT로 넘겨서 expires_at 계산에 사용)
        try:
            from app.policy.api import payment_timeout_minutes
            default_hold = int(payment_timeout_minutes())
        except Exception:
            default_hold = 60

        hold_minutes = int(body.hold_minutes) if body.hold_minutes is not None else int(default_hold)
        if hold_minutes < 1:
            hold_minutes = 1
        if hold_minutes > 24 * 60:
            hold_minutes = 24 * 60

        # --------------------------------------------------------------
        # ✅ 핵심: v3.6 SSOT 예약 생성 로직에 위임
        #   - capacity check
        #   - reserved_qty 홀드
        #   - policy_id + policy_snapshot_json 저장
        #   - amount_goods/amount_shipping/amount_total 스냅샷 저장
        # --------------------------------------------------------------

        res = crud_v36.create_reservation(
            db,
            deal_id=int(body.deal_id),
            offer_id=int(body.offer_id),
            buyer_id=int(body.buyer_id),
            qty=int(body.qty),
            hold_minutes=int(hold_minutes),
        )

        # 3) Seller 알림 (v3.6이 알림을 안 만든다면 여기서 유지) -----------
        try:
            seller = db.query(models.Seller).get(offer.seller_id) if offer else None
            if seller:
                create_notification(
                    db,
                    user_id=seller.id,
                    type="offer_reservation_created",
                    title="내 오퍼에 예약이 들어왔어요",
                    message="등록하신 오퍼에 새로운 예약이 생성되었습니다.",
                    link_url=None,
                    meta={
                        "role": "seller",
                        "offer_id": offer.id,
                        "reservation_id": res.id,
                    },
                )
        except Exception as _e:
            logging.warning("[NOTIFICATION] offer_reservation_created failed: %s", _e)

        # 4) policy/phase 붙이기 ----------------------------------------
        # - policy는 "응답용 attach"로만 처리 (ORM setattr 최소화)
        try:
            _attach_policy_to_reservation_obj(res, db)
        except Exception as _e:
            logging.warning("[RESERVATION] attach_policy (create) failed: %s", _e)

        try:
            _attach_phase_to_reservation_obj(res)
        except Exception as _e:
            logging.warning("[RESERVATION] attach_phase (create) failed: %s", _e)

        return res

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {e.__class__.__name__}: {e}",
        )

# ---------------------------------------------------------
# 📋 Seller용 예약 리스트
# ---------------------------------------------------------
@router_resv.get(
    "/seller/{seller_id}",
    response_model=List[schemas.ReservationOut],
    summary="[Seller] 내 오퍼에 걸린 예약 목록 조회",
)
def api_list_reservations_for_seller(
    seller_id: int = Path(..., ge=1),
    only_active: bool = Query(
        True,
        description="true 이면 취소/만료 아닌 것만 (PENDING/PAID/SHIPPED/DELIVERED)",
    ),
    db: Session = Depends(get_db),
):
    """
    - Offer.seller_id 기준으로 예약 목록 조회
    - 배송/도착 phase, 취소정책 스냅샷(policy)도 함께 내려줌
    """
    # Reservation ↔ Offer 조인
    q = (
        db.query(models.Reservation)
        .join(models.Offer, models.Reservation.offer_id == models.Offer.id)
        .filter(models.Offer.seller_id == seller_id)
    )

    if only_active:
        # status 가 CANCELLED / EXPIRED 아닌 것만
        q = q.filter(
            models.Reservation.status.notin_(["CANCELLED", "EXPIRED"])
        )

    rows = (
        q.order_by(models.Reservation.created_at.desc())
         .limit(200)
         .all()
    )

    # 각 row 에 policy / phase 붙이기
    for r in rows:
        try:
            _attach_policy_to_reservation_obj(r, db)
        except Exception as _e:
            logging.warning("[RESERVATION] attach_policy (seller_list) failed: %s", _e)
        try:
            _attach_phase_to_reservation_obj(r)
        except Exception as _e:
            logging.warning("[RESERVATION] attach_phase (seller_list) failed: %s", _e)

    return rows


# ---------------------------------------------------------
# 📋 Buyer용 예약/주문 리스트
# ---------------------------------------------------------
@router_resv.get(
    "/buyer/{buyer_id}",
    response_model=List[schemas.ReservationOut],
    summary="[Buyer] 내가 만든 예약/주문 목록 조회",
)
def api_list_reservations_for_buyer(
    buyer_id: int = Path(..., ge=1),
    only_active: bool = Query(
        False,
        description="true 이면 취소/만료 아닌 것만 보기",
    ),
    db: Session = Depends(get_db),
):
    """
    - buyer_id 기준으로 예약/주문 목록 조회
    - 마이페이지 '나의 주문' 리스트에 그대로 사용 가능
    """
    q = db.query(models.Reservation).filter(
        models.Reservation.buyer_id == buyer_id
    )

    if only_active:
        q = q.filter(
            models.Reservation.status.notin_(["CANCELLED", "EXPIRED"])
        )

    rows = (
        q.order_by(models.Reservation.created_at.desc())
         .limit(200)
         .all()
    )

    for r in rows:
        try:
            _attach_policy_to_reservation_obj(r, db)
        except Exception as _e:
            logging.warning("[RESERVATION] attach_policy (buyer_list) failed: %s", _e)
        try:
            _attach_phase_to_reservation_obj(r)
        except Exception as _e:
            logging.warning("[RESERVATION] attach_phase (buyer_list) failed: %s", _e)

    return rows


#--------------------------------
# Pay Reservation API  (디포짓 완전 제거 버전)
#---------------------------------

@router_resv.post(
    "/pay",
    response_model=schemas.ReservationOut,
    summary="예약 결제 — PENDING→PAID, 재고/포인트/정책 스냅샷 처리 (디포짓 없음)",
)
def api_pay_reservation(
    body: schemas.ReservationPayIn = Body(...),
    db: Session = Depends(get_db),
):
    """
    v3.5 예약 결제 (디포짓 제거 버전)

    흐름:
    - (1) 예약 로드
    - (2) pay_reservation() 호출 → 재고(sold_qty) 반영 + buyer 포인트 적립
    - (3) Actuator 커미션 적립 시도
    - (4) 해당 시점의 오퍼 취소/환불 정책을 스냅샷으로 저장
    - (5) 응답용 policy / phase 필드 붙이기
    """

    try:
        # 1) 결제 대상 예약 조회
        resv = crud_get_reservation(db, body.reservation_id)

        # 2) 결제 실행
        # - CRUD 시그니처: pay_reservation(db, reservation_id: int, paid_amount: int)
        # - buyer_id는 "검증"에만 쓰고, CRUD로 넘기지 않는다.
        if getattr(body, "buyer_id", None) is not None:
            if int(getattr(resv, "buyer_id", 0) or 0) != int(body.buyer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="reservation does not belong to buyer",
                )

        # paid_amount는 body가 주면 그걸 쓰고, 없으면 예약 스냅샷(SSOT)에서 가져온다.
        paid_amount = getattr(body, "paid_amount", None)
        if paid_amount is None:
            paid_amount = int(getattr(resv, "amount_total", 0) or 0)

        paid_amount = int(paid_amount or 0)
        if paid_amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="paid_amount must be positive",
            )

        paid = crud.pay_reservation(
            db,
            reservation_id=int(body.reservation_id),
            paid_amount=paid_amount,
        )

        # 3) 🔹 결제 시 정산 스냅샷 생성 (PG/역핑/셀러 정산 계산) — v3.5 안정화 버전
        #    ✅ 원칙:
        #    - settlement 실패가 결제(pay) 자체를 롤백시키면 안 된다.
        #    - 따라서 pay 결과를 먼저 확정(commit)하고, 그 다음 settlement를 만들고 별도로 commit한다.
        try:
            # (A) pay 결과를 먼저 확정 (pay_reservation가 내부에서 commit을 안 했을 수도 있으므로 여기서 보장)
            try:
                db.add(paid)
                db.commit()
            except Exception:
                # 이미 commit 되었거나, add/commit이 필요 없는 상황일 수 있으니 best-effort
                try:
                    db.rollback()
                except Exception:
                    pass

            try:
                db.refresh(paid)
            except Exception:
                pass

            # (B) settlement 생성 + commit 보장
            try:
                crud.create_settlement_for_paid_reservation(
                    db,
                    reservation_id=int(paid.id),
                )
                db.commit()
            except Exception as e:
                logging.exception("[SETTLEMENT] snapshot create failed (best-effort)", exc_info=e)
                try:
                    db.rollback()
                except Exception:
                    pass

        except Exception as e:
            # 절대 결제 흐름을 망치지 않기
            logging.exception("[SETTLEMENT] unexpected error (best-effort)", exc_info=e)


        # 4) Actuator 커미션 적립 시도 (기존 로직 그대로 유지)
        try:
            _maybe_create_actuator_commission_for_reservation(db, paid)
        except Exception as e:
            logging.warning("[ACTUATOR COMMISSION] failed: %s", e)

        # ---------------------------------------------------------
        # 5) ✅ 결제 시점의 오퍼 정책 스냅샷 저장 + 응답에 policy 포함
        #    - ORM(paid)에 Pydantic(policy)를 setattr 하면 SQLAlchemy가 relationship로 오해 → _sa_instance_state 에러
        #    - 따라서 DB에는 snapshot_json만 저장하고,
        #      응답용 ReservationOut(Pydantic)에만 policy를 붙인다.
        # ---------------------------------------------------------
        policy_for_response = None

        try:
            # 이미 policy_id가 있으면(재호출 등) 덮어쓰지 않음
            if getattr(paid, "policy_id", None) is None:
                policy = crud.get_offer_policy(db, paid.offer_id)

                if policy:
                    policy_schema = schemas.OfferPolicyOut.model_validate(policy, from_attributes=True)

                    # 스냅샷 필드 세팅 (DB 저장)
                    paid.policy_id = policy.id
                    paid.policy_snapshot_json = json.dumps(
                        policy_schema.model_dump(mode="json"),
                        ensure_ascii=False,
                        default=str,
                    )
                    # 이 컬럼이 실제로 존재하면 유지, 없으면 조용히 패스
                    try:
                        paid.policy_agreed_at = datetime.now(timezone.utc)
                    except Exception:
                        pass

                    db.add(paid)
                    db.commit()
                    db.refresh(paid)

                    # ✅ 응답용으로만 보관
                    policy_for_response = policy_schema

            else:
                # 이미 스냅샷이 있을 땐 snapshot_json → policy 로만 복원해서 응답에 붙임
                snapshot = getattr(paid, "policy_snapshot_json", None)
                if snapshot:
                    data = json.loads(snapshot)
                    policy_schema = schemas.OfferPolicyOut.model_validate(data)
                    policy_for_response = policy_schema

        except Exception as _e:
            logging.exception("[RESERVATION] policy snapshot on pay failed", exc_info=_e)
            logging.warning("[RESERVATION] policy snapshot on pay failed: %s", _e)

        # 6) phase 계산해서 응답에 붙이기 (PENDING/PAID/SHIPPED/DELIVERED/CANCELLED 등)
        try:
            _attach_phase_to_reservation_obj(paid)
        except Exception as _e:
            logging.warning("[RESERVATION] attach_phase (pay) failed: %s", _e)

        # ✅ ORM(paid) 그대로 return 하지 말고, 응답 모델로 변환 후 policy 붙여 반환
        out = schemas.ReservationOut.model_validate(paid, from_attributes=True)
        if policy_for_response is not None:
            out.policy = policy_for_response

        return out

    except Exception as e:
        _translate_error(e)



# ---------------------------------------------------------
# 📦 Reservation 배송/도착 관련 API
# ---------------------------------------------------------
class ReservationShipIn(BaseModel):
    seller_id: int = Field(..., ge=1, description="발송 처리하는 셀러 ID")
    shipping_carrier: Optional[str] = Field(
        None, max_length=50, description="택배사 (예: CJ대한통운)"
    )
    tracking_number: Optional[str] = Field(
        None, max_length=100, description="운송장 번호"
    )

@router_resv.post(
    "/{reservation_id}/mark_shipped",
    response_model=schemas.ReservationOut,
    summary="[Seller] 배송완료(발송완료) 표시",
)
def api_mark_reservation_shipped(
    reservation_id: int = Path(..., ge=1),
    body: ReservationShipIn = Body(default_factory=ReservationShipIn),
    db: Session = Depends(get_db),
):
    # ✅ Optional 방어
    if body.seller_id is None:
        raise HTTPException(status_code=422, detail="seller_id is required")

    try:
        resv = mark_reservation_shipped(
            db,
            reservation_id=reservation_id,
            seller_id=body.seller_id,
            shipping_carrier=getattr(body, "shipping_carrier", None),
            tracking_number=getattr(body, "tracking_number", None),
        )
    except HTTPException:
        raise
    except Exception as e:
        # ConflictError/NotFoundError 같은 커스텀 에러를 여기서 HTTP로 변환
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        if "cannot" in msg.lower() or "conflict" in msg.lower() or "not owned" in msg.lower():
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=500, detail=msg)


    # 🆕 phase 계산 (DB 영향 없음)
    try:
        _attach_phase_to_reservation_obj(resv)
    except Exception as _e:
        logging.warning("[RESERVATION] attach_phase (shipped) failed: %s", _e)

    return resv




class ReservationArrivalConfirmIn(BaseModel):
    buyer_id: int = Field(..., ge=1, description="도착확인 하는 바이어 ID")


#----------------------------------------
# 수령확인 API
#------------------------------------------
@router_resv.post(
    "/{reservation_id}/arrival_confirm",
    response_model=schemas.ReservationOut,
    summary="[Buyer] 도착완료(수령확인)",
)
def api_arrival_confirm_reservation(
    reservation_id: int = Path(..., ge=1),
    body: ReservationArrivalConfirmIn = Body(...),
    db: Session = Depends(get_db),
):
    # 1) 예약 조회
    resv = (
        db.query(models.Reservation)
        .filter(models.Reservation.id == reservation_id)
        .first()
    )
    if not resv:
        raise HTTPException(status_code=404, detail="Reservation not found")

    # 2) 본인 소유 확인
    if int(getattr(resv, "buyer_id", 0)) != int(body.buyer_id):
        raise HTTPException(status_code=409, detail="not owned by buyer")

    # 3) 상태 확인 (PAID 상태에서만 도착확인 가능)
    status_val = getattr(resv, "status", None)
    name = getattr(status_val, "name", None) or str(status_val)
    if name != "PAID":
        raise HTTPException(
            status_code=409,
            detail=f"cannot confirm arrival: status={name}",
        )

    # 4) 발송 여부 확인
    if getattr(resv, "shipped_at", None) is None:
        raise HTTPException(
            status_code=409,
            detail="cannot confirm arrival before shipped",
        )

    # 5) 최초 한 번만 도착 처리 (멱등)
    if getattr(resv, "arrival_confirmed_at", None) is None:
        now = datetime.now(timezone.utc)
        resv.arrival_confirmed_at = now

        # delivered_at 이 별도로 있다면 같이 채워줌
        if getattr(resv, "delivered_at", None) is None:
            resv.delivered_at = now

        db.add(resv)
        db.commit()
        db.refresh(resv)

    # 6) 도착이 확정된 이후에는 정산 레코드 생성(또는 이미 있으면 재사용)
    try:
        row = _ensure_settlement_for_reservation(db, resv)
        logging.info("[SETTLEMENT] ensured: resv_id=%s settlement_id=%s", resv.id, getattr(row, "id", None))
    except Exception as _e:
        # ✅ 이제는 절대 삼키지 말고, 콘솔에 traceback 찍고 500으로 터뜨려서 원인 확인
        logging.exception("[SETTLEMENT] ensure failed: resv_id=%s", resv.id)
        raise HTTPException(status_code=500, detail=f"settlement ensure failed: {_e}")
    
    # 7) phase / policy 헬퍼 붙이기
    try:
        _attach_phase_to_reservation_obj(resv)
    except Exception as _e:
        logging.warning("[RESERVATION] attach_phase (arrival_confirm) failed: %s", _e)

    try:
        _attach_policy_to_reservation_obj(resv, db)
    except Exception as _e:
        logging.warning("[RESERVATION] attach_policy (arrival_confirm) failed: %s", _e)

    return resv


# =========================================================
# 💰 Actuator 커미션 적립 헬퍼
# =========================================================
def _get_actuator_rate_for_level(level_str: str) -> float:
    """
    Seller 레벨 문자열(Lv.1~Lv.6)에 대응하는 Actuator 수수료율(%).
    rules_v3_5.ACTUATOR_FEE_BY_LEVEL 를 우선 사용하고,
    없으면 안전한 기본값으로 fallback.
    """
    try:
        table = getattr(RV, "ACTUATOR_FEE_BY_LEVEL", None) or {}
        if table:
            return float(table.get(level_str, 0.0))
    except Exception:
        pass

    default_table = {
        "Lv.6": 0.5,
        "Lv.5": 0.2,
        "Lv.4": 0.1,
        "Lv.3": 0.0,
        "Lv.2": 0.0,
        "Lv.1": 0.0,
    }
    return float(default_table.get(level_str, 0.0))



def _compute_actuator_commission_ready_at_for_reservation(
    resv: models.Reservation,
    offer: Optional[models.Offer],
) -> Optional[datetime]:
    """
    액츄에이터 커미션 지급가능일 계산:

    - 기준일 = arrival_confirmed_at or delivered_at or paid_at
    - cooling_days:
        * 우선 Offer.cooling_days 에서 가져오고
        * 없으면 TIME_POLICY.cooling_days 사용
    - ready_at = 기준일 + cooling_days + TIME_POLICY.actuator_payout_after_cooling_days
    """
    if not resv:
        return None

    # 1) 기준일
    base: Optional[datetime] = None
    if getattr(resv, "arrival_confirmed_at", None):
        base = _as_utc(resv.arrival_confirmed_at)
    elif getattr(resv, "delivered_at", None):
        base = _as_utc(resv.delivered_at)
    elif getattr(resv, "paid_at", None):
        base = _as_utc(resv.paid_at)

    if base is None:
        return None

    # 2) 쿨링 일수
    cooling_days: Optional[int] = None
    if offer is not None:
        cooling_days = getattr(offer, "cooling_days", None)

    if not cooling_days:
        cooling_days = TIME_POLICY.cooling_days

    total_days = cooling_days + TIME_POLICY.actuator_payout_after_cooling_days
    return base + timedelta(days=total_days)



def _maybe_create_actuator_commission_for_reservation(
    db: Session,
    resv: models.Reservation,
):
    """
    - Reservation 이 PAID 상태이고
    - 해당 Offer 의 Seller 가 actuator_id 를 가지고 있다면
      → ACTUATOR_FEE_BY_LEVEL 에 따라 ActuatorCommission row 생성.
    - 결제 시점에는 status='PENDING', ready_at=None 으로만 생성하고
      실제 ready_at(정산 예정일)은 나중에 별도 로직에서 세팅.
    """
    status_val = getattr(resv, "status", None)
    status_name = getattr(status_val, "name", None) or str(status_val)
    if status_name != "PAID":
        return

    offer = db.query(models.Offer).get(resv.offer_id)
    if not offer:
        return

    seller = db.query(models.Seller).get(offer.seller_id)
    if not seller:
        return

    if not seller.actuator_id:
        return

    price = float(getattr(offer, "price", 0.0) or 0.0)
    qty = int(getattr(resv, "qty", 0) or 0)
    gmv = int(price * qty)
    if gmv <= 0:
        return

    level_int = int(getattr(seller, "level", 6) or 6)
    level_str = f"Lv.{level_int}"
    rate = _get_actuator_rate_for_level(level_str)
    if rate <= 0.0:
        return

    amount = int(gmv * (rate / 100.0))
    if amount <= 0:
        return

    log = models.ActuatorCommission(
        actuator_id=seller.actuator_id,
        seller_id=seller.id,
        reservation_id=resv.id,
        gmv=gmv,
        rate_percent=rate,
        amount=amount,
        status="PENDING",   # 👈 결제 순간부터 PENDING row 존재
        ready_at=None,      # 👈 아직 정산일 미정 (쿨링+30일 계산 전)
    )
    db.add(log)
    # commit 은 상위 pay 함수에서 한 번에 처리
    


# ---------------------------------------------------------
# Reservation 정책 스냅샷 관련 헬퍼
# ---------------------------------------------------------
def _build_policy_snapshot_dict(policy: models.OfferPolicy) -> dict:
    """OfferPolicy ORM 객체를 Reservation용 스냅샷 dict로 변환."""
    if not policy:
        return {}
    return {
        "cancel_rule": policy.cancel_rule,
        "cancel_within_days": policy.cancel_within_days,
        "extra_text": policy.extra_text,
        "id": policy.id,
        "offer_id": policy.offer_id,
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
    }


def _attach_policy_to_reservation_obj(resv: models.Reservation, db: Session):
    """
    Reservation ORM 객체에 .policy 필드를 채워준다.
    - policy_snapshot_json 있으면 그걸 기준으로
    - 없으면 OfferPolicy를 조회해서 사용
    """
    snap = None

    # 1) 스냅샷 JSON 우선
    raw = getattr(resv, "policy_snapshot_json", None)
    if raw:
        try:
            data = json.loads(raw)
            snap = schemas.ReservationPolicySnapshot(**data)
        except Exception:
            snap = None

    # 2) 스냅샷이 없으면, 현재 OfferPolicy 조회해서 사용 (주로 PENDING 상태일 때)
    if snap is None:
        policy = crud.get_offer_policy(db, resv.offer_id)
        if policy:
            data = _build_policy_snapshot_dict(policy)
            try:
                snap = schemas.ReservationPolicySnapshot(**data)
            except Exception:
                snap = None

    if snap is not None:
        setattr(resv, "policy", snap)


# ---------------------------------------------------------
# 예약 상태 Phase 계산 헬퍼
#  - DB status + 배송 타임스탬프를 조합해서
#    PENDING / PAID / SHIPPED / DELIVERED / CANCELLED / EXPIRED 리턴
# ---------------------------------------------------------
def _calc_reservation_phase(resv: models.Reservation) -> str:
    status_val = getattr(resv, "status", None)
    name = (getattr(status_val, "name", None) or str(status_val) or "").upper()

    shipped_at = getattr(resv, "shipped_at", None)
    delivered_at = (
        getattr(resv, "delivered_at", None)
        or getattr(resv, "arrival_confirmed_at", None)
    )

    if name == "CANCELLED":
        return "CANCELLED"
    if name == "EXPIRED":
        return "EXPIRED"
    if name == "PENDING":
        return "PENDING"

    if name == "PAID":
        # 도착 확인이 있으면 DELIVERED 단계
        if delivered_at is not None:
            return "DELIVERED"
        # 발송은 했지만 도착확인은 안 된 상태
        if shipped_at is not None:
            return "SHIPPED"
        # 결제는 했지만 발송 전
        return "PAID"

    # 혹시 다른 status 값이 추가되면 그대로 노출
    return name or "UNKNOWN"


def _attach_phase_to_reservation_obj(resv: models.Reservation):
    """
    Reservation ORM 객체에 .phase 속성을 계산해서 붙여준다.
    (response_model=ReservationOut 에서 그대로 사용)
    """
    try:
        phase = _calc_reservation_phase(resv)
        setattr(resv, "phase", phase)
    except Exception as _e:
        logging.warning("[RESERVATION] calc phase failed: %s", _e)



# ---------------------------------------------------------
# 💰 Reservation → ReservationSettlement 생성 헬퍼
# ---------------------------------------------------------

def _resolve_cooling_days_for_reservation(db: Session, resv: models.Reservation) -> int:
    """
    cooling_days SSOT:
      1) reservation.policy_id -> OfferPolicy.cancel_within_days
      2) offer_id -> OfferPolicy.cancel_within_days
      3) policy.api.cooling_days() fallback
      4) 마지막 안전 fallback 7
    """
    # 1) reservation.policy_id
    try:
        pid = getattr(resv, "policy_id", None)
        if pid:
            row = (
                db.query(models.OfferPolicy)
                .filter(models.OfferPolicy.id == int(pid))
                .first()
            )
            if row is not None:
                v = getattr(row, "cancel_within_days", None)
                if v is not None:
                    cd = int(v)
                    return max(1, min(cd, 365))
    except Exception:
        pass

    # 2) offer_id
    try:
        oid = getattr(resv, "offer_id", None)
        if oid:
            row = (
                db.query(models.OfferPolicy)
                .filter(models.OfferPolicy.offer_id == int(oid))
                .first()
            )
            if row is not None:
                v = getattr(row, "cancel_within_days", None)
                if v is not None:
                    cd = int(v)
                    return max(1, min(cd, 365))
    except Exception:
        pass

    # 3) policy.api fallback
    try:
        from app.policy import api as policy_api
        cd = int(policy_api.cooling_days())
        return max(1, min(cd, 365))
    except Exception:
        return 7


def _resolve_settlement_payout_delay_days_default() -> int:
    """
    '쿨링 종료 후 지급 예정일' 기본값.
    - 너 설계: '쿨링 끝나고 30일 이내 지급' => 기본 30일로 두고,
      운영자가 scheduled_payout_at을 당겨서 지급 가능하게 설계.
    """
    try:
        from app.policy import api as policy_api
        v = int(getattr(policy_api, "settlement_payout_delay_days_after_cooling")())
        return max(0, min(v, 365))
    except Exception:
        return 30


def _resolve_dispute_payout_delay_days_default() -> int:
    """
    분쟁 종료 후 지급(별도 패스) 기본값.
    - 기본 30일(요구사항), 추후 운영자 정책으로 중앙화.
    """
    try:
        from app.policy import api as policy_api
        v = int(getattr(policy_api, "dispute_settlement_payout_delay_days")())
        return max(0, min(v, 365))
    except Exception:
        return 30



def _to_percent(v: Any, default: float = 0.0) -> float:
    """
    입력이 3.5 / "3.5" / 0.035 / "0.035" / "3.5%" 등으로 와도
    '퍼센트 값(예: 3.5)'로 정규화해서 반환.
    """
    if v is None:
        return default
    try:
        if isinstance(v, str):
            s = v.strip().replace("%", "")
            f = float(s)
        else:
            f = float(v)
    except Exception:
        return default

    if f <= 0:
        return default

    # 0.035처럼 "비율"로 들어오면 퍼센트로 환산
    if f < 1.0:
        return f * 100.0

    # 3.5처럼 퍼센트로 들어오면 그대로
    return f


def _seller_level_str_from_obj(seller: Any) -> str:
    """
    Seller.level이 1~6 int로 저장되어 있다고 가정하고 Lv.N 문자열 생성.
    기본은 Lv.6(신규)
    """
    try:
        lvl = int(getattr(seller, "level", 6) or 6)
    except Exception:
        lvl = 6
    if lvl < 1:
        lvl = 1
    if lvl > 6:
        lvl = 6
    return f"Lv.{lvl}"


def _platform_fee_percent_for_seller(db: Session, seller_id: int) -> float:
    """
    플랫폼 수수료(퍼센트)를 Seller Level 기반으로 결정.

    우선순위:
      1) rules_v3_5.SELLER_FEE_BY_LEVEL (있으면)
      2) 없으면 문서(v3.5)의 기본 테이블 fallback

    반환: percent (예: 3.5)
    """
    seller = db.get(models.Seller, seller_id) if seller_id else None
    level_str = _seller_level_str_from_obj(seller) if seller else "Lv.6"

    # 1) SSOT 테이블 우선
    table = None
    try:
        table = getattr(RV, "SELLER_FEE_BY_LEVEL", None)
    except Exception:
        table = None

    if isinstance(table, dict) and table:
        # 값이 3.5 또는 0.035 등 무엇이든 들어와도 퍼센트로 통일
        return float(_to_percent(table.get(level_str, table.get(level_str.replace("Lv.", "L"), None)), default=3.5))

    # 2) fallback: 문서 기준
    fallback = {
        "Lv.6": 3.5,
        "Lv.5": 3.0,
        "Lv.4": 2.8,
        "Lv.3": 2.7,
        "Lv.2": 2.5,
        "Lv.1": 2.0,
    }
    return float(fallback.get(level_str, 3.5))



def _ensure_settlement_for_reservation(db: Session, resv: models.Reservation):
    """
    A안(업서트 버전):
    - arrival_confirm에서 Settlement row는 생성/갱신(멱등)
    - READY 전환은 배치(refresh-ready)에서만 수행(원칙)
      * 단, 분쟁/해제 같은 "블록 상태"는 즉시 반영 필요 -> 여기서 갱신
    - 분쟁이면 해당 건 HOLD + DISPUTE
    - 분쟁 종료 후에는 별도 패스(HOLD 유지 + dispute path 스케줄링)로 다룸
    """

    # 0) 기존 정산 row 조회
    existing = (
        db.query(models.ReservationSettlement)
        .filter(models.ReservationSettlement.reservation_id == resv.id)
        .first()
    )

    # 1) Offer 조회(정산 생성에 필요)
    offer = db.get(models.Offer, resv.offer_id)
    if not offer:
        return None

    # 2) ✅ SSOT 금액 = Reservation.amount_total
    buyer_paid_amount = int(getattr(resv, "amount_total", 0) or 0)
    if buyer_paid_amount <= 0:
        # 금액 0 이하면 정산 레코드 불필요
        return None

    # 3) PG fee는 지금은 0 (추후 ReservationPayment 합계 등으로 확장)
    pg_fee_amount = 0

    # 4) 플랫폼 수수료: Seller Level 연동 (✅ SSOT ratio)
    seller = db.get(models.Seller, offer.seller_id) if offer else None
    level_int = int(getattr(seller, "level", 6) or 6) if seller else 6

    commission = _platform_fee_percent_for_seller(db, offer.seller_id)  # 이름은 일단 유지
    # ✅ 자동 정규화: 3.5면 percent, 0.035면 rate로 간주
    commission_rate = (commission / 100.0) if commission > 1.0 else commission

    platform_commission_amount = int(round(buyer_paid_amount * commission_rate))
    platform_commission_amount = max(0, platform_commission_amount)

    logging.warning("[FEE] commission_raw=%s commission_rate=%s", commission, commission_rate)

    seller_payout_amount = buyer_paid_amount - pg_fee_amount - platform_commission_amount
    seller_payout_amount = max(0, seller_payout_amount)

    now = datetime.now(timezone.utc)

    # 5) ✅ 쿨링 기준일 = arrival_confirmed_at 우선, 없으면 delivered_at fallback
    base = getattr(resv, "arrival_confirmed_at", None) or getattr(resv, "delivered_at", None)

    cooling_days = _resolve_cooling_days_for_reservation(db, resv)
    ready_at = None
    if base is not None:
        ready_at = base + timedelta(days=int(cooling_days))

    # 6) ✅ 기본 scheduled_payout_at = ready_at + (기본 30일)
    payout_delay_days = _resolve_settlement_payout_delay_days_default()
    scheduled_payout_at = None
    if ready_at is not None:
        scheduled_payout_at = ready_at + timedelta(days=int(payout_delay_days))

    # 7) ✅ 분쟁/블록 상태
    is_disputed = bool(getattr(resv, "is_disputed", False))
    dispute_opened_at = getattr(resv, "dispute_opened_at", None)
    dispute_closed_at = getattr(resv, "dispute_closed_at", None)

    # 기본값: HOLD
    status = "HOLD"
    if is_disputed:
        block_reason = "DISPUTE"
    else:
        block_reason = "WITHIN_COOLING"

    # ---------------------------------------------------------
    # ✅ 업서트(갱신/생성)
    # ---------------------------------------------------------
    if existing:
        # (A) 금액/매핑 갱신 (안전하게 최신으로 동기화)
        existing.deal_id = resv.deal_id
        existing.offer_id = resv.offer_id
        existing.seller_id = offer.seller_id
        existing.buyer_id = resv.buyer_id

        existing.buyer_paid_amount = buyer_paid_amount
        existing.pg_fee_amount = pg_fee_amount
        existing.platform_commission_amount = platform_commission_amount
        existing.seller_payout_amount = seller_payout_amount

        # (B) 타임라인 갱신
        existing.ready_at = ready_at
        existing.scheduled_payout_at = scheduled_payout_at

        # (C) 분쟁 메타 갱신
        existing.dispute_opened_at = dispute_opened_at
        existing.dispute_closed_at = dispute_closed_at

        # (D) 상태/블록 갱신 규칙
        if is_disputed:
            # 분쟁이면 무조건 HOLD + DISPUTE
            existing.status = "HOLD"
            existing.block_reason = "DISPUTE"
        else:
            # 분쟁이 아니면: 쿨링 중이면 HOLD/WITHIN_COOLING 유지
            # READY 전환은 원칙적으로 refresh-ready 배치가 하게 둔다.
            existing.status = "HOLD"
            existing.block_reason = "WITHIN_COOLING"

        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    # (분쟁 종료 후 별도 패스는 refresh_due에서 처리)
    row = models.ReservationSettlement(
        reservation_id=resv.id,
        deal_id=resv.deal_id,
        offer_id=resv.offer_id,
        seller_id=offer.seller_id,
        buyer_id=resv.buyer_id,

        buyer_paid_amount=buyer_paid_amount,
        pg_fee_amount=pg_fee_amount,
        platform_commission_amount=platform_commission_amount,
        seller_payout_amount=seller_payout_amount,

        status=status,
        currency="KRW",

        ready_at=ready_at,
        scheduled_payout_at=scheduled_payout_at,
        block_reason=block_reason,

        dispute_opened_at=dispute_opened_at,
        dispute_closed_at=dispute_closed_at,
    )

    db.add(row)
    db.commit()
    db.refresh(row)
    return row


#---------------------------
# API GET reservation 
#--------------------------

@router_resv.get(
    "/{reservation_id}",
    response_model=schemas.ReservationOut,
    summary="[DEV] Get reservation by id",
)
def api_get_reservation(
    reservation_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        resv = crud_get_reservation(db, reservation_id)

        # 정책 스냅샷 / 혹은 현재 정책을 .policy 에 주입
        try:
            _attach_policy_to_reservation_obj(resv, db)
        except Exception as _e:
            logging.warning("[RESERVATION] attach policy (get) failed: %s", _e)

        # 🆕 상태 phase 계산
        try:
            _attach_phase_to_reservation_obj(resv)
        except Exception as _e:
            logging.warning("[RESERVATION] attach_phase (get) failed: %s", _e)

        return resv

    except CrudNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e) or "Reservation not found",
        )


# ─────────────────────────────────────────────
# 🔴 예약 취소 API (PENDING / PAID 모두 지원)
# ─────────────────────────────────────────────

class ReservationCancelIn(BaseModel):
    reservation_id: int
    actor: str = "buyer_cancel"  # buyer_cancel / admin_cancel / seller_fault ...


@router_resv.post(
    "/cancel",
    response_model=schemas.ReservationOut,
    summary="예약 취소 (PENDING/PAID 공통) — 정책 검사 + 재고/포인트 처리",
)
def api_cancel_reservation(
    body: ReservationCancelIn = Body(...),
    db: Session = Depends(get_db),
):
    try:
        # 1) 예약 로드
        resv = crud_get_reservation(db, body.reservation_id)

        # 상태 문자열 얻기 (Enum, str 모두 대응)
        status_val = getattr(resv, "status", None)
        name = getattr(status_val, "name", None) or str(status_val)

        # ─────────────────────────────
        # 2-A) PENDING 취소 (결제 전)
        # ─────────────────────────────
        if name == "PENDING":
            # 재고 롤백: reserved_qty 감소, sold_qty 는 그대로
            offer = db.query(models.Offer).get(resv.offer_id)
            if offer:
                cur_reserved = int(getattr(offer, "reserved_qty", 0) or 0)
                offer.reserved_qty = max(0, cur_reserved - int(resv.qty or 0))
                db.add(offer)

            # 예약 상태 변경
            resv.status = models.ReservationStatus.CANCELLED
            resv.cancelled_at = datetime.now(timezone.utc)

            db.add(resv)
            db.commit()
            db.refresh(resv)

            # 응답 편의 필드들 붙이기
            try:
                _attach_policy_to_reservation_obj(resv, db)
            except Exception as _e:
                logging.warning("[RESERVATION] attach policy (cancel PENDING) failed: %s", _e)

            try:
                _attach_phase_to_reservation_obj(resv)
            except Exception as _e:
                logging.warning("[RESERVATION] attach_phase (cancel PENDING) failed: %s", _e)

            return resv

        # ─────────────────────────────
        # 2-B) PAID 취소 (결제 후 환불)
        # ─────────────────────────────
        if name == "PAID":
            # 도착확인 완료 예약은 취소 불가
            if getattr(resv, "arrival_confirmed_at", None) is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="cannot cancel reservation after arrival confirmed",
                )
            # actor 가 buyer_cancel 이면 A1/A2/A3/A4 정책을 적용해 검사
            _ensure_cancel_allowed_by_policy(resv, db, body.actor)

            # 실제 환불: sold_qty 감소 + buyer 포인트 롤백
            result = refund_paid_reservation(
                db,
                reservation_id=body.reservation_id,
                actor=body.actor,
            )

            # 응답 확장
            try:
                _attach_policy_to_reservation_obj(result, db)
            except Exception as _e:
                logging.warning("[RESERVATION] attach policy (refund) failed: %s", _e)

            try:
                _attach_phase_to_reservation_obj(result)
            except Exception as _e:
                logging.warning("[RESERVATION] attach_phase (refund) failed: %s", _e)

            try:
                crud.cancel_settlement_for_reservation(db, result.id)
            except Exception as _e:
                logging.warning("[SETTLEMENT] cancel settlement failed: %s", _e)


            return result

        # ─────────────────────────────
        # 2-C) 그 외 상태는 취소 불가
        # ─────────────────────────────
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"cannot cancel reservation in status={name}",
        )

    except CrudNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e) or "Reservation not found",
        )
    except HTTPException:
        # 위에서 이미 HTTPException 을 던졌으면 그대로 전달
        raise
    except Exception as e:
        _translate_error(e)


        
#------------------------------------------
# 정책 무시 강제 환불용 API
#-------------------------------------------
        
class ReservationAdminCancelIn(BaseModel):
    reservation_id: int
    actor: str = Field(
        "admin_cancel",
        description="admin_cancel 또는 seller_fault",
    )


@router_resv.post(
    "/force_refund",
    response_model=schemas.ReservationOut,
    summary="[Admin/Seller] 정책 무시 강제 환불 (PAID → CANCELLED)",
)
def api_force_refund(
    body: ReservationAdminCancelIn = Body(...),
    db: Session = Depends(get_db),
):
    """
    - buyer_cancel 과 다르게 정책 체크를 아예 하지 않고 바로 환불.
    - admin_cancel, seller_fault 등의 케이스에서 사용.
    """
    try:
        # 1) 예약 로드
        resv = crud_get_reservation(db, body.reservation_id)

        # 2) 강제 환불 실행 (정책 무시)
        result = refund_paid_reservation(
            db,
            reservation_id=body.reservation_id,
            actor=body.actor,
        )

        # 3) 응답에 정책(policy) 스냅샷 붙이기
        try:
            _attach_policy_to_reservation_obj(result, db)
        except Exception as _e:
            logging.warning("[RESERVATION] attach policy (force_refund) failed: %s", _e)

        # 4) phase 필드 계산해서 붙이기
        try:
            _attach_phase_to_reservation_obj(result)
        except Exception as _e:
            logging.warning("[RESERVATION] attach_phase (force_refund) failed: %s", _e)

        try:
            crud.cancel_settlement_for_reservation(db, result.id)
        except Exception as _e:
            logging.warning("[SETTLEMENT] cancel settlement failed: %s", _e)


        return result

    except CrudNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        _translate_error(e)



# --------------------------------------------------
# Seller 승인 안 되어있을 시 offer 금지
# --------------------------------------------------
def create_offer(db: Session, offer_in: schemas.OfferCreate):
    seller = db.query(models.Seller).get(offer_in.seller_id)
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    status = seller_approval_status(seller)
    if status != "APPROVED":
        raise HTTPException(
            status_code=403,
            detail=f"Seller is not approved (status={status}). Offers are allowed only for APPROVED sellers.",
        )

    db_offer = models.Offer(
        deal_id=offer_in.deal_id,
        seller_id=offer_in.seller_id,
        price=offer_in.price,
        total_available_qty=offer_in.total_available_qty,
        delivery_days=offer_in.delivery_days,
        comment=offer_in.comment,
    )
    db.add(db_offer)
    db.commit()
    db.refresh(db_offer)
    return db_offer


# ─────────────────────────────────────────────────────
# Offer 노출/그룹핑 응답 (PREMIUM / MATCHING / BELOW)
# UI에서 바로 쓰기 좋은 최소 필드 + offer 원본 포함
# ─────────────────────────────────────────────────────
class OfferRankedOut(BaseModel):
    group: str
    remaining_qty: int  # ✅ 이게 핵심 (정렬/표시 기본값)
    seller_level: Optional[int] = None
    yp_rating: Optional[float] = None
    yp_rating_count: Optional[int] = None
    external_rating: Optional[float] = None
    deal_status: Optional[str] = None
    offer: schemas.OfferOut

    # UI용 추가 필드들(선택)
    deal_price: Optional[float] = None
    offer_price: Optional[float] = None
    offer_index_pct: Optional[int] = None
    offer_total_qty: Optional[int] = None
    shipping_mode: Optional[str] = None

    # ✅ “표 컬럼명 맞춤”용 별칭(remaining_qty 그대로 복제)
    offer_remaining_qty: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)




def _offer_group_for_price(deal_price: Optional[float], offer_price: float) -> str:
    """
    Deal 가격 대비 Offer 가격으로 그룹 분류
    - PREMIUM : offer < deal
    - MATCHING: offer == deal
    - BELOW   : offer > deal
    """
    if deal_price is None:
        return "BELOW"
    try:
        dp = float(deal_price)
        op = float(offer_price)
    except Exception:
        return "BELOW"

    if op < dp:
        return "PREMIUM"
    if op == dp:
        return "MATCHING"
    return "BELOW"


#---------------------------------------------------------
# 상세 응답 스키마
#---------------------------------------------------------
class OfferDetailOut(BaseModel):
    """
    단일 Offer 클릭 시 내려줄 상세 정보 스키마.
    """

    offer: schemas.OfferOut
    deal: Optional[schemas.DealOut] = None

    # 수량 관련
    remaining_qty: int
    total_available_qty: int
    sold_qty: int
    reserved_qty: int

    # 셀러 레벨/평점
    seller_level: Optional[str] = Field(
        None, description="Seller.level 을 'Lv.6' 형태로 표현"
    )
    seller_rating_adjusted: Optional[float] = Field(
        None, description="역핑 조정 평점 (없으면 None)"
    )
    seller_rating_count: Optional[int] = Field(
        None, description="리뷰 개수 (없으면 None)"
    )
    external_rating: Optional[float] = Field(
        None, description="외부 평점(예: Naver/쿠팡); 아직 연동 전이면 None"
    )

    # 셀러 프로필
    region: Optional[str] = Field(
        None, description="셀러 지역/거점 (예: 서울, 경기…)"
    )
    seller_age_years: Optional[float] = Field(
        None, description="셀러 설립 연차(년 단위, 소수 가능)"
    )

    # Deal 옵션 + free_text
    options: Optional[dict] = Field(
        None,
        description=(
            "Deal 의 option1~5_title/value + free_text 를 모두 모은 dict. "
            "예: {'색상': '블루', '용량': '256GB', 'free_text': '직구/관부가세 포함'}"
        ),
    )

    # 👇 새로 추가
    policy: Optional[schemas.OfferPolicyOut] = Field(
        None,
        description="이 오퍼에 설정된 취소/환불/반품 정책 (없으면 null)",
    )


# ----------------------------------------
# Offer 취소정책 검증 헬퍼
# ----------------------------------------

_CANCEL_RULE_CHOICES = {"A1", "A2", "A3", "A4"}


def _validate_offer_policy_or_raise(data: schemas.OfferPolicyCreate) -> None:
    """
    A1/A2/A3/A4 규칙과 cancel_within_days 일관성 검증.

    - cancel_rule은 반드시 A1~A4 중 하나
    - A3일 때만 cancel_within_days 필요 (1~30)
    - A1/A2/A4일 때는 cancel_within_days는 None이어야 함
    """
    if data.cancel_rule not in _CANCEL_RULE_CHOICES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid cancel_rule: {data.cancel_rule}",
        )

    if data.cancel_rule == "A3":
        if data.cancel_within_days is None:
            raise HTTPException(
                status_code=400,
                detail="cancel_within_days is required when cancel_rule = 'A3'",
            )
        if not (1 <= data.cancel_within_days <= 30):
            raise HTTPException(
                status_code=400,
                detail="cancel_within_days must be between 1 and 30",
            )
    else:
        # A1/A2/A4 → cancel_within_days 를 쓰지 않음
        if data.cancel_within_days is not None:
            raise HTTPException(
                status_code=400,
                detail="cancel_within_days must be null unless cancel_rule = 'A3'",
            )

    # extra_text 길이는 Pydantic에서 max_length로 이미 체크하지만
    # 혹시나 해서 한 번 더 방어적 체크
    if data.extra_text is not None and len(data.extra_text) > 1000:
        raise HTTPException(
            status_code=400,
            detail="extra_text must be <= 1000 characters",
        )


# ─────────────────────────────────────────────────────
# B) /offers
# ─────────────────────────────────────────────────────
router_offers = APIRouter(prefix="/offers", tags=["offers"])


@router_offers.post(
    "",
    response_model=schemas.OfferOut,
    status_code=status.HTTP_201_CREATED,
    summary="오퍼 생성 (APPROVED 셀러만 가능)",
)
def api_create_offer(
    body: schemas.OfferCreate = Body(...),
    db: Session = Depends(get_db),
):
    try:
        offer = create_offer(db, body)
        return offer
    except Exception as e:
        _translate_error(e)



@router_offers.get(
    "/{offer_id}/remaining",
    summary="오퍼 잔여 판매 가능 수량 조회",
)
def api_offer_remaining_capacity(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        remain = get_offer_remaining_capacity(db, offer_id)
        return {"offer_id": offer_id, "remaining": remain}
    except Exception as e:
        _translate_error(e)



@router_offers.post(
    "/{offer_id}/confirm",
    response_model=schemas.OfferOut,
    summary="오퍼 확정(전량 판매 시에만) — 결제 없거나 미완판이면 409",
)
def api_confirm_offer(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    - 오퍼가 전량 판매(sold == total_available_qty) 된 경우에만 확정
    - 결제 0건이거나, 미완판이면 409 에러
    - 확정 성공 시:
        * 셀러에게 'offer_confirmed' 알림
        * 해당 셀러를 데려온 Actuator 에게 'actuator_seller_offer_confirmed' 알림
    """
    try:
        # 1) 오퍼 로드
        offer = db.get(models.Offer, offer_id)
        if not offer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Offer not found",
            )

        total_avail = int(getattr(offer, "total_available_qty", 0) or 0)
        sold = int(getattr(offer, "sold_qty", 0) or 0)

        # 2) 결제 0건이면 확정 불가
        if sold <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cannot_confirm_without_payment",
            )

        # 3) 전량 판매 상태가 아니면 확정 불가
        if total_avail <= 0 or sold != total_avail:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="cannot_confirm_not_soldout",
            )

        # 4) 실제 확정 처리 (포인트 적립 포함)
        confirmed_offer = crud.seller_confirm_offer(
            db,
            offer_id=offer_id,
            force=False,             # 전량판매 / pending 없음 조건만 허용
            award_on_full=30,        # full sell 시 셀러 포인트 30점
        )

        # 5) 🔔 알림 (셀러 & 액츄에이터)
        try:
            price = float(getattr(confirmed_offer, "price", 0.0) or 0.0)
            sold_qty = int(getattr(confirmed_offer, "sold_qty", 0) or 0)
            gmv = int(price * sold_qty)

            # 5-1) 셀러 알림
            if confirmed_offer.seller_id:
                create_notification(
                    db,
                    user_id=confirmed_offer.seller_id,
                    type="offer_confirmed",
                    title=f"오퍼 #{confirmed_offer.id}가 확정되었습니다.",
                    message=(
                        f"딜 #{confirmed_offer.deal_id} 오퍼가 전량 판매되어 확정되었습니다. "
                        f"(판매수량: {sold_qty}, GMV: {gmv}원)"
                    ),
                    meta={
                        "role": "seller",
                        "deal_id": confirmed_offer.deal_id,
                        "offer_id": confirmed_offer.id,
                        "sold_qty": sold_qty,
                        "gmv": gmv,
                    },
                )

            # 5-2) 액츄에이터 알림 (해당 셀러에 actuator_id 가 있는 경우)
            seller = (
                db.get(models.Seller, confirmed_offer.seller_id)
                if confirmed_offer.seller_id
                else None
            )
            actuator_id = int(getattr(seller, "actuator_id", 0) or 0) if seller else 0

            if actuator_id:
                create_notification(
                    db,
                    user_id=actuator_id,
                    type="actuator_seller_offer_confirmed",
                    title="연결된 셀러의 오퍼가 확정되었습니다.",
                    message=(
                        f"당신이 모집한 셀러 #{seller.id} 의 오퍼 #{confirmed_offer.id}가 "
                        f"전량 판매되어 확정되었습니다. (GMV: {gmv}원)"
                    ),
                    meta={
                        "role": "actuator",
                        "seller_id": seller.id if seller else None,
                        "deal_id": confirmed_offer.deal_id,
                        "offer_id": confirmed_offer.id,
                        "sold_qty": sold_qty,
                        "gmv": gmv,
                    },
                )

        except Exception as notify_err:
            # 알림 실패로 확정 로직이 깨지면 안 되므로, 로그만 남김
            import logging
            logging.exception(
                "offer_confirm notifications failed",
                exc_info=notify_err,
            )

        return confirmed_offer

    except HTTPException:
        # 위에서 이미 만든 HTTPException 은 그대로 전달
        raise
    except Exception as e:
        # crud.NotFoundError / ConflictError 등은 공용 변환기로 처리
        _translate_error(e)
        
        
        

class SetTotalBody(BaseModel):
    total_available_qty: Optional[int] = Field(
        None,
        ge=0,
        description="새 total_available_qty 값. total 과 둘 중 하나만 넣으면 됨.",
    )
    total: Optional[int] = Field(
        None,
        ge=0,
        description="total_available_qty 와 같은 의미. 둘 중 하나만 사용.",
    )

#---------------------------------------------------
@router_offers.post(
    "/{offer_id}/set_total",
    summary="오퍼 총량 설정(JSON)",
)
def api_offer_set_total_json(
    offer_id: int = Path(..., ge=1),
    body: SetTotalBody = Body(...),
    db: Session = Depends(get_db),
):
    try:
        new_total = body.total_available_qty if body.total_available_qty is not None else body.total
        if new_total is None:
            raise HTTPException(status_code=400, detail="must include 'total' or 'total_available_qty'")

        offer = update_offer_total_qty(
            db,
            offer_id,
            total_available_qty=int(new_total),
            allow_unconfirm_on_increase=True,
        )
        total_avail = int(getattr(offer, "total_available_qty", 0) or 0)
        sold = int(getattr(offer, "sold_qty", 0) or 0)
        reserved = int(getattr(offer, "reserved_qty", 0) or 0)
        remaining = total_avail - sold - reserved
        return {
            "offer_id": offer_id,
            "deal_id": getattr(offer, "deal_id", None),
            "total_available_qty": total_avail,
            "sold_qty": sold,
            "reserved_qty": reserved,
            "is_confirmed": getattr(offer, "is_confirmed", False),
            "remaining": remaining,
        }
    except Exception as e:
        _translate_error(e)


#------------------------------------------------
@router_offers.post(
    "/{offer_id}/set_total_qs",
    summary="오퍼 총량 설정(QS)",
)
def api_offer_set_total_qs(
    offer_id: int = Path(..., ge=1),
    total: int = Query(..., ge=0, description="= total_available_qty"),
    db: Session = Depends(get_db),
):
    try:
        offer = update_offer_total_qty(
            db,
            offer_id,
            total_available_qty=int(total),
            allow_unconfirm_on_increase=True,
        )
        total_avail = int(getattr(offer, "total_available_qty", 0) or 0)
        sold = int(getattr(offer, "sold_qty", 0) or 0)
        reserved = int(getattr(offer, "reserved_qty", 0) or 0)
        remaining = total_avail - sold - reserved
        return {
            "offer_id": offer_id,
            "deal_id": getattr(offer, "deal_id", None),
            "total_available_qty": total_avail,
            "sold_qty": sold,
            "reserved_qty": reserved,
            "is_confirmed": getattr(offer, "is_confirmed", False),
            "remaining": remaining,
        }
    except Exception as e:
        _translate_error(e)


#--------------------------------------------------
# 🔍 오퍼 단건 조회
#--------------------------------------------------
@router_offers.get("/{offer_id}", response_model=schemas.OfferOut)
def get_offer(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    offer = db.get(models.Offer, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


#----------------------------------------------------
# 📋 오퍼 목록 조회 (필터: deal_id)
#----------------------------------------------------
@router_offers.get("/", response_model=List[schemas.OfferOut])
def list_offers(
    deal_id: Optional[int] = Query(
        None, description="특정 딜에 속한 오퍼만 보고 싶으면 deal_id 입력"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(models.Offer)
    if deal_id is not None:
        q = q.filter(models.Offer.deal_id == deal_id)

    offers = (
        q.order_by(models.Offer.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return offers






#-----------------------------------------
# Offer list중 상위 20개 오퍼 랭킹 및 목록규칙
#-----------------------------------------
@router_offers.get(
    "/deal/{deal_id}/ranked",
    response_model=List[OfferRankedOut],
    summary="Deal별 상위 20개 오퍼 (PREMIUM/MATCHING/BELOW 그룹 + 평점/Deal!! 상태 포함)",
)
def api_list_ranked_offers_for_deal(
    deal_id: int = Path(..., ge=1),
    sort_by: str = Query(
        "default",
        description=(
            "정렬 기준:\n"
            "- default: 그룹(PREMIUM→MATCHING→BELOW) + 가격 오름차순 + 남은수량 내림차순\n"
            "- price:   그룹 + 가격 오름차순\n"
            "- external_rating: 그룹 + 외부평점 내림차순 + 가격\n"
            "- yp_rating:       그룹 + 역핑평점 내림차순 + 가격\n"
            "- remaining_qty:   그룹 + 남은수량 내림차순 + 가격"
        ),
    ),
    db: Session = Depends(get_db),
):
    # 0) Deal 존재/가격 확인
    deal = db.get(models.Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    deal_price = getattr(deal, "target_price", None)

    # 1) 해당 Deal 의 모든 오퍼 조회 (필요시 is_active=True 조건 추가 가능)
    q = db.query(models.Offer).filter(models.Offer.deal_id == deal_id)
    # q = q.filter(models.Offer.is_active == True)  # noqa: E712

    # 2) 가격 오름차순, id 오름차순 정렬 후 상위 20개만
    offers: List[models.Offer] = (
        q.order_by(models.Offer.price.asc(), models.Offer.id.asc())
         .limit(20)
         .all()
    )
    if not offers:
        return []

    # 3) Seller 정보 미리 로딩
    seller_ids = {
        int(o.seller_id)
        for o in offers
        if getattr(o, "seller_id", None) is not None
    }

    seller_map: dict[int, models.Seller] = {}
    if seller_ids:
        sellers = (
            db.query(models.Seller)
              .filter(models.Seller.id.in_(seller_ids))
              .all()
        )
        seller_map = {int(s.id): s for s in sellers}

    # 4) 셀러 평점 집계(있으면 사용)
    rating_map: dict[int, dict] = {}
    if SellerRatingAggregate is not None and seller_ids:
        rows = (
            db.query(SellerRatingAggregate)
              .filter(SellerRatingAggregate.seller_id.in_(seller_ids))
              .all()
        )
        for r in rows:
            sid = int(getattr(r, "seller_id", 0) or 0)
            if not sid:
                continue

            info: dict = {}

            # 역핑 조정 평점
            adj = (
                getattr(r, "adjusted_rating", None)
                or getattr(r, "rating_adjusted", None)
            )
            try:
                if adj is not None:
                    info["yp_rating"] = float(adj)
            except Exception:
                pass

            # 외부 플랫폼 평점
            ext = (
                getattr(r, "external_rating", None)
                or getattr(r, "external_score", None)
            )
            try:
                if ext is not None:
                    info["external_rating"] = float(ext)
            except Exception:
                pass

            # 리뷰 개수
            cnt = (
                getattr(r, "rating_count", None)
                or getattr(r, "count", None)
                or getattr(r, "review_count", None)
                or getattr(r, "num_reviews", None)
            )
            try:
                if cnt is not None:
                    info["yp_rating_count"] = int(cnt)
            except Exception:
                pass

            if info:
                rating_map[sid] = info

    # deal 기준가(딜 목표가) — index 계산 기준축
    deal_price_raw = getattr(deal, "target_price", None)
    deal_price_f = float(deal_price_raw) if deal_price_raw is not None else None

    # 5) Offer → ranked DTO 변환
    result: List[OfferRankedOut] = []

    for o in offers:
        offer_price_f = float(getattr(o, "price", 0.0) or 0.0)

        total = int(getattr(o, "total_available_qty", 0) or 0)
        sold = int(getattr(o, "sold_qty", 0) or 0)
        reserved = int(getattr(o, "reserved_qty", 0) or 0)
        remaining = max(0, total - sold - reserved)

        seller_id = int(getattr(o, "seller_id", 0) or 0)
        seller = seller_map.get(seller_id)
        seller_level = int(getattr(seller, "level", 0) or 0) if seller else None

        rating_info = rating_map.get(seller_id, {}) or {}
        external_rating = rating_info.get("external_rating")
        yp_rating = rating_info.get("yp_rating")
        yp_rating_count = rating_info.get("yp_rating_count")

        # 그룹은 deal_price vs offer_price로 결정
        group = _offer_group_for_price(deal_price_f, offer_price_f)
        deal_status = "Deal!!" if remaining <= 0 else "Open"

        offer_index_pct = None
        if deal_price_f and deal_price_f > 0:
            offer_index_pct = int(round((offer_price_f / deal_price_f) * 100))

        # 배송 요약(offer에 이미 있는 필드 그대로 노출)
        shipping_mode = getattr(o, "shipping_mode", None)

        result.append(
            OfferRankedOut(
                group=group,
                remaining_qty=remaining,          # ✅ 이 줄이 빠져서 터진 거야 (필수)
                deal_status=deal_status,
                offer_total_qty=total,
                offer_remaining_qty=remaining,
                offer_price=offer_price_f,
                deal_price=deal_price_f,
                offer_index_pct=offer_index_pct,
                seller_level=seller_level,
                yp_rating=yp_rating,
                yp_rating_count=yp_rating_count,
                external_rating=external_rating,
                shipping_mode=shipping_mode,
                offer=o,  # schemas.OfferOut (from_attributes로 변환)
            )
        )

    # 6) 정렬 규칙
    group_order = {"PREMIUM": 0, "MATCHING": 1, "BELOW": 2}

    def _price(o: OfferRankedOut) -> float:
        return float(getattr(o.offer, "price", 0.0) or 0.0)

    if sort_by == "price":
        result.sort(
            key=lambda x: (
                group_order.get(x.group, 3),
                _price(x),
            )
        )
    elif sort_by == "external_rating":
        result.sort(
            key=lambda x: (
                group_order.get(x.group, 3),
                -(
                    x.external_rating
                    if x.external_rating is not None
                    else -1e9
                ),
                _price(x),
            )
        )
    elif sort_by == "yp_rating":
        result.sort(
            key=lambda x: (
                group_order.get(x.group, 3),
                -(
                    x.yp_rating
                    if x.yp_rating is not None
                    else -1e9
                ),
                _price(x),
            )
        )
    elif sort_by == "remaining_qty":
        result.sort(
            key=lambda x: (
                group_order.get(x.group, 3),
                -x.remaining_qty,
                _price(x),
            )
        )
    else:
        # default: 그룹 → 가격 오름차순 → 남은수량 내림차순
        result.sort(
            key=lambda x: (
                group_order.get(x.group, 3),
                _price(x),
                -x.remaining_qty,
            )
        )

    return result

#----------------------------------------------------
# Offer 상세조회 API
#----------------------------------------------------
@router_offers.get(
    "/detail/{offer_id}",
    response_model=OfferDetailOut,
    summary="오퍼 상세 (Deal + Seller 메타 + 역핑 평점)",
)
def api_get_offer_detail(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    # 1) 오퍼 로딩
    offer = db.get(models.Offer, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")

    # 2) 딜 로딩
    deal = db.get(models.Deal, offer.deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    # 3) 수량 계산
    total = int(getattr(offer, "total_available_qty", 0) or 0)
    sold = int(getattr(offer, "sold_qty", 0) or 0)
    reserved = int(getattr(offer, "reserved_qty", 0) or 0)
    remaining = max(0, total - sold - reserved)

    # 4) 셀러 / 메타
    seller = None
    seller_level_str: Optional[str] = None
    region: Optional[str] = None
    seller_age_years: Optional[float] = None

    if getattr(offer, "seller_id", None):
        seller = db.get(models.Seller, offer.seller_id)

    if seller:
        # 레벨: 숫자면 "Lv.N"
        try:
            lvl = getattr(seller, "level", None)
            if lvl is not None:
                seller_level_str = f"Lv.{int(lvl)}"
        except Exception:
            seller_level_str = str(getattr(seller, "level", None))

        region = getattr(seller, "region", None)

        created_at = getattr(seller, "created_at", None)
        if created_at is not None:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            seller_age_years = max(0.0, (now - created_at).days / 365.0)

    # 5) Deal 가격 대비 group
    deal_price = getattr(deal, "target_price", None)
    offer_price = float(getattr(offer, "price", 0.0) or 0.0)
    group = _offer_group_for_price(deal_price, offer_price)

    # 6) 평점 (SellerRatingAggregate 사용)
    yp_rating: Optional[float] = None
    yp_rating_count: Optional[int] = None
    external_rating: Optional[float] = None
    
    if seller and SellerRatingAggregate is not None:
        agg = (
            db.query(SellerRatingAggregate)
              .filter(SellerRatingAggregate.seller_id == seller.id)
              .first()
        )
        if agg:
            adj = (
                getattr(agg, "adjusted_rating", None)
                or getattr(agg, "rating_adjusted", None)
            )
            if adj is not None:
                try:
                    yp_rating = float(adj)
                except Exception:
                    pass

            cnt = (
                getattr(agg, "rating_count", None)
                or getattr(agg, "count", None)
                or getattr(agg, "review_count", None)
                or getattr(agg, "num_reviews", None)
            )
            if cnt is not None:
                try:
                    yp_rating_count = int(cnt)
                except Exception:
                    pass

            ext = (
                getattr(agg, "external_rating", None)
                or getattr(agg, "external_score", None)
            )
            if ext is not None:
                try:
                    external_rating = float(ext)
                except Exception:
                    pass

    # 7) Deal 옵션 + free_text 묶기
    options: dict | None = None
    try:
        opt_dict: dict = {}
        for i in range(1, 6):
            t = getattr(deal, f"option{i}_title", None)
            v = getattr(deal, f"option{i}_value", None)
            if t and v is not None:
                opt_dict[str(t)] = v

        free_text = getattr(deal, "free_text", None)
        if free_text:
            opt_dict["free_text"] = free_text

        if opt_dict:
            options = opt_dict
    except Exception:
        options = None

    # 7-x) 🔎 오퍼 취소/환불 정책 조회 → Pydantic 으로 변환
    policy_obj = crud.get_offer_policy(db, offer.id)
    policy: Optional[schemas.OfferPolicyOut] = None
    if policy_obj is not None:
        policy = schemas.OfferPolicyOut(
            id=policy_obj.id,
            offer_id=policy_obj.offer_id,
            cancel_rule=policy_obj.cancel_rule,
            cancel_within_days=policy_obj.cancel_within_days,
            extra_text=policy_obj.extra_text,
            created_at=policy_obj.created_at,
        )
    # 8) 응답 조립
    return OfferDetailOut(
        group=group,
        yp_rating=yp_rating,
        yp_rating_count=yp_rating_count,
        external_rating=external_rating,
        offer=offer,
        deal=deal,
        remaining_qty=remaining,
        total_available_qty=total,
        sold_qty=sold,
        reserved_qty=reserved,
        seller_level=seller_level_str,
        region=region,
        seller_age_years=seller_age_years,
        options=options,
        policy=policy,
    )


# ----------------------------------------
# Offer 취소정책 검증 헬퍼
# ----------------------------------------

_CANCEL_RULE_CHOICES = {"A1", "A2", "A3", "A4"}


def _validate_offer_policy_or_raise(data: schemas.OfferPolicyCreate) -> None:
    """
    A1/A2/A3/A4 규칙과 cancel_within_days 일관성 검증.

    - cancel_rule은 반드시 A1~A4 중 하나
    - A3일 때만 cancel_within_days 필요 (1~30)
    - A1/A2/A4일 때는 cancel_within_days는 None이어야 함
    """
    if data.cancel_rule not in _CANCEL_RULE_CHOICES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid cancel_rule: {data.cancel_rule}",
        )

    if data.cancel_rule == "A3":
        if data.cancel_within_days is None:
            raise HTTPException(
                status_code=400,
                detail="cancel_within_days is required when cancel_rule = 'A3'",
            )
        if not (1 <= data.cancel_within_days <= 30):
            raise HTTPException(
                status_code=400,
                detail="cancel_within_days must be between 1 and 30",
            )
    else:
        # A1/A2/A4 → cancel_within_days 를 쓰지 않음
        if data.cancel_within_days is not None:
            raise HTTPException(
                status_code=400,
                detail="cancel_within_days must be null unless cancel_rule = 'A3'",
            )

    # extra_text 길이는 Pydantic에서 max_length로 이미 체크하지만
    # 혹시나 해서 한 번 더 방어적 체크
    if data.extra_text is not None and len(data.extra_text) > 1000:
        raise HTTPException(
            status_code=400,
            detail="extra_text must be <= 1000 characters",
        )

# ----------------------------------------------------
# Offer 취소정책 조회 API
# ----------------------------------------------------
@router_offers.get(
    "/{offer_id}/policy",
    response_model=schemas.OfferPolicyOut,
    summary="오퍼 취소/환불/반품 정책 조회",
)
def api_get_offer_policy(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    - 해당 오퍼에 연결된 취소/환불/반품 정책 1건 조회
    - 없으면 404
    """
    policy = crud.get_offer_policy(db, offer_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="OfferPolicy not found")

    return policy


@router_offers.post(
    "/{offer_id}/policy",
    response_model=schemas.OfferPolicyOut,
    summary="오퍼 취소/환불/반품 정책 생성/수정",
)
def api_upsert_offer_policy(
    offer_id: int = Path(..., ge=1),
    payload: schemas.OfferPolicyCreate = Body(...),
    db: Session = Depends(get_db),
):
    """
    - Seller가 오퍼 생성/수정 시 정책을 함께 저장
    - 이미 있으면 update, 없으면 insert
    """
    policy = crud.upsert_offer_policy(
        db,
        offer_id=offer_id,
        data=payload,
    )
    return policy


# ──────────────────────────────────────────────────────────
# [DEV] 만료 오퍼 자동 비활성화
# ──────────────────────────────────────────────────────────
@router_offers.post(
    "/dev/expire",
    summary="[DEV] 만료 오퍼 자동 비활성화",
    tags=["offers"],
)
def dev_expire_offers(db: Session = Depends(get_db)):
    """
    is_active=True이고 deadline_at < now 인 오퍼를 is_active=False로 전환.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    try:
        expired_offers = (
            db.query(models.Offer)
            .filter(
                models.Offer.is_active == True,
                models.Offer.deadline_at.isnot(None),
                models.Offer.deadline_at < now,
            )
            .all()
        )
    except Exception:
        return {"expired_count": 0, "expired_ids": []}

    expired_ids = []
    for offer in expired_offers:
        offer.is_active = False
        db.add(offer)
        expired_ids.append(offer.id)

    db.commit()
    return {"expired_count": len(expired_ids), "expired_ids": expired_ids}


# ─────────────────────────────────────────────────────
# 집계 라우터(api)
# ─────────────────────────────────────────────────────
api = APIRouter()
api.include_router(router_resv)   # /reservations/*
api.include_router(router_offers)  # /offers/*
api.include_router(admin_anchor.router)   # /admin/anchor/*


# ─────────────────────────────────────────────────────
# Export aliases (v3.5)
# ─────────────────────────────────────────────────────
from fastapi import APIRouter as _APIRouter  # type: ignore

router_reservations_v35: _APIRouter = router_resv
router_offers_v35: _APIRouter = router_offers
router: _APIRouter = api  # 구 호환: /reservations + /offers 모두 포함



__all__ = [
    "router_reservations_v35",
    "router_offers_v35",
    "router",
    "router_offers",
    "api",
]