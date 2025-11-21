# app/routers/offers.py
from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from .. import crud
from ..database import get_db
from .. import schemas

from app.config import project_rules as R  # 정책/시간 계산 등
from ..logic.trust import buyer_trust_tier_and_deposit_percent

# (선택) 모델 직접 조회 가능하면 신선도/나이 필터에 사용
try:
    from ..models import BuyerDeposit  # 존재하지 않을 수도 있음
except Exception:
    BuyerDeposit = None  # type: ignore


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
    if "deposit_required" in str(exc).lower():
        return True
    return False


def _translate_error(exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if _is_conflict(exc):
        detail = (str(exc) or "deposit_required")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc) or "not found")

    logging.exception("offers router error", exc_info=exc)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": exc.__class__.__name__, "msg": str(exc)},
    )


# ─────────────────────────────────────────────────────
# 공용 CRUD import (실제 프로젝트의 crud 함수 사용)
# ─────────────────────────────────────────────────────
from ..crud import (
    get_offer_remaining_capacity,
    create_reservation,
    cancel_reservation,
    expire_reservations,
    pay_reservation,  # v3.5 규칙 가정
    confirm_offer_if_soldout,
    refund_paid_reservation,
    get_reservation as crud_get_reservation,
    update_offer_total_qty,
)


# ─────────────────────────────────────────────────────
# Freshness/유효기간 계산 보조
# ─────────────────────────────────────────────────────
def _status_norm(s: str | None) -> str:
    u = (s or "").upper()
    return "HELD" if u in {"HELD", "HOLD", "ACTIVE"} else u


def _as_utc(dt: Optional[datetime]):
    """naive -> UTC, aware -> UTC, None -> None (문자열이 와도 fromisoformat 시도)"""
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            if dt.endswith("Z"):
                dt = dt[:-1]
                x = datetime.fromisoformat(dt)
                return x.replace(tzinfo=timezone.utc)
            x = datetime.fromisoformat(dt)
            return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    if isinstance(dt, datetime):
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _ge_with_tolerance(lhs: Optional[datetime], rhs: Optional[datetime], tol_sec: int = 1) -> bool:
    """lhs >= rhs - tol_sec (둘 중 하나라도 None이면 True로 간주)"""
    if lhs is None or rhs is None:
        return True
    return lhs >= (rhs - timedelta(seconds=int(tol_sec)))


def _select_freshness_anchor_dt(db: Session, *, resv) -> Optional[datetime]:
    """
    DEPOSIT_FRESHNESS_ANCHOR에 따라 '이 이후 생성된 디파짓만 인정'의 기준시각을 반환.
    - reservation: 예약 created_at
    - offer      : 해당 오퍼 created_at (조회 실패 시 예약 created_at로 폴백)
    - deal       : 해당 딜 created_at   (조회 실패 시 예약 created_at로 폴백)
    """
    anchor = getattr(R, "DEPOSIT_FRESHNESS_ANCHOR", "reservation") or "reservation"
    anchor = str(anchor).lower()

    # 기본: 예약 생성시각
    resv_created = _as_utc(getattr(resv, "created_at", None))

    if anchor == "reservation":
        return resv_created

    if anchor == "offer":
        get_offer = getattr(crud, "get_offer", None) or getattr(crud, "get_offer_by_id", None)
        if callable(get_offer):
            try:
                off = get_offer(db, getattr(resv, "offer_id", None))
            except TypeError:
                try:
                    off = get_offer(db, offer_id=getattr(resv, "offer_id", None))
                except TypeError:
                    off = None
            if off is not None:
                return _as_utc(getattr(off, "created_at", None)) or resv_created
        return resv_created

    if anchor == "deal":
        get_deal = getattr(crud, "get_deal", None) or getattr(crud, "get_deal_by_id", None)
        if callable(get_deal):
            try:
                deal = get_deal(db, getattr(resv, "deal_id", None))
            except TypeError:
                try:
                    deal = get_deal(db, deal_id=getattr(resv, "deal_id", None))
                except TypeError:
                    deal = None
            if deal is not None:
                return _as_utc(getattr(deal, "created_at", None)) or resv_created
        return resv_created

    # 미지정/이상값 → 예약 기준
    return resv_created


def _get_fresh_active_deposit(
    db: Session,
    *,
    deal_id: int,
    buyer_id: int,
    anchor_dt: Optional[datetime],  # freshness 앵커(UTC)
):
    """
    1) 모델이 있으면: deal/buyer + HELD 계열만 최신순으로 가져오고 파이썬에서 신선도 판정
    2) 모델이 없으면: crud.get_active_deposit_for 한 건을 가져와서 파이썬에서 신선도 판정
    조건 불충족이면 None
    """
    dep = None

    # 1) 모델 직접 조회 (가능하면 이것이 가장 정확)
    if BuyerDeposit is not None:
        q = (
            db.query(BuyerDeposit)
              .filter(
                  BuyerDeposit.deal_id == deal_id,
                  BuyerDeposit.buyer_id == buyer_id,
                  func.upper(BuyerDeposit.status).in_(("HELD", "HOLD", "ACTIVE")),
              )
              .order_by(BuyerDeposit.id.desc())
        )
        cand = q.first()
        if cand:
            cad = _as_utc(getattr(cand, "created_at", None))
            # 1초 관용 허용: 저장/직후조회 간 미세 시차 보완
            if _ge_with_tolerance(cad, _as_utc(anchor_dt), tol_sec=1):
                return cand
            return None

    # 2) CRUD 한 건 가져와 파이썬에서 신선도 확인
    fn = getattr(crud, "get_active_deposit_for", None)
    if callable(fn):
        try:
            dep = fn(db, deal_id=deal_id, buyer_id=buyer_id)
        except TypeError:
            dep = fn(db, deal_id, buyer_id)  # 위치 인자 시그니처 대응
        if dep and _status_norm(getattr(dep, "status", None)) == "HELD":
            cad = _as_utc(getattr(dep, "created_at", None))
            if _ge_with_tolerance(cad, _as_utc(anchor_dt), tol_sec=1):
                return dep

    return None


def _is_deposit_within_age(dep, *, now_utc: datetime) -> bool:
    """
    DEPOSIT_MAX_AGE_MINUTES 정책을 적용하여, 디파짓의 '나이'가 허용 범위 이내인지 확인.
    정책이 None이면 True.
    """
    max_age = getattr(R, "DEPOSIT_MAX_AGE_MINUTES", None)
    if not max_age and max_age != 0:
        return True  # 비활성화
    try:
        max_age = int(max_age)
    except Exception:
        return True  # 잘못된 설정은 안전하게 무시

    created = _as_utc(getattr(dep, "created_at", None))
    if not created:
        return False
    age_min = (now_utc - created).total_seconds() / 60.0
    return age_min <= max_age


# ─────────────────────────────────────────────────────
# A) /reservations (v3.5)
# ─────────────────────────────────────────────────────
router_resv = APIRouter(prefix="/reservations", tags=["reservations v3.5"])


@router_resv.post(
    "",
    response_model=schemas.ReservationOut,
    status_code=status.HTTP_201_CREATED,
    summary="예약 생성(PENDING) — 재고 홀드 [DEBUG]",
)
def api_create_reservation(
    body: schemas.ReservationCreate = Body(...),
    db: Session = Depends(get_db),
):
    try:
        res = create_reservation(
            db,
            deal_id=body.deal_id,
            offer_id=body.offer_id,
            buyer_id=body.buyer_id,
            qty=body.qty,
            hold_minutes=body.hold_minutes,
        )
        # 테스트 고정시간이 있으면 응답용 타임스탬프 보정
        try:
            base = R.now_utc()
            if hasattr(res, "created_at"):
                setattr(res, "created_at", base)
            expires = R.apply_deadtime_pause(start_time=base, minutes=int(body.hold_minutes))
            setattr(res, "expires_at", expires)
        except Exception:
            pass

        return res
    except Exception as e:
        _translate_error(e)


@router_resv.post(
    "/pay",
    response_model=schemas.ReservationOut,
    summary="예약 결제 — reserved→sold, buyer 포인트 적립 (디파짓 가드 포함)",
)
def api_pay_reservation(
    body: schemas.ReservationPayIn = Body(...),
    db: Session = Depends(get_db),
):
    try:
        # 1) 결제 대상 조회
        resv = crud_get_reservation(db, body.reservation_id)

        # 2) 디파짓 요구 여부 결정 (토글 우선, 아니면 티어 기반)
        require = bool(getattr(R, "DEPOSIT_REQUIRE_ALWAYS", False))
        if not require:
            try:
                trust = buyer_trust_tier_and_deposit_percent(db, body.buyer_id) or {}
                require = float(trust.get("deposit_percent") or 0.0) > 0.0
            except Exception:
                # 조회 실패 시 보수적으로 패스(운영 정책에 따라 변경 가능)
                require = False

        # 3) 디파짓 필요 시: 앵커 결정 + 신선한 HELD 존재 + (옵션) 최소금액/나이 검증
        if require:
            anchor_dt = _select_freshness_anchor_dt(db, resv=resv)
            fresh = _get_fresh_active_deposit(
                db,
                deal_id=resv.deal_id,
                buyer_id=body.buyer_id,
                anchor_dt=anchor_dt,
            )
            if not fresh:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="deposit_required")

            # 최소 금액
            min_amount = getattr(R, "DEPOSIT_MIN_AMOUNT", 1)
            if min_amount and int(getattr(fresh, "amount", 0) or 0) < int(min_amount):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="deposit_required")

            # 유효기간(나이 제한) — 결제 시각 기준
            if getattr(R, "DEPOSIT_MAX_AGE_MINUTES", None) is not None:
                now = R.now_utc() if callable(getattr(R, "now_utc", None)) else datetime.now(timezone.utc)
                if not _is_deposit_within_age(fresh, now_utc=now):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="deposit_required")

        # 4) 결제 실행 (포인트 기본값 명시)
        paid = pay_reservation(
            db,
            reservation_id=body.reservation_id,
            buyer_id=body.buyer_id,
            buyer_point_per_qty=getattr(R, "BUYER_POINT_PER_QTY", 20),
        )

        # 🔁 자동 환불 훅: 정책이 켜져 있으면, '해당 예약 이후 생성된' 최신 HELD만 환불
        try:
            auto_on = bool(getattr(R, "DEPOSIT_AUTO_REFUND_ON_PAY", False))
            logging.info(
                "[AUTO_REFUND] enabled=%s reservation_id=%s deal=%s buyer=%s",
                auto_on, getattr(paid, "id", None), getattr(paid, "deal_id", None), getattr(paid, "buyer_id", None)
            )
            if auto_on:
                fresh = _get_fresh_active_deposit(
                    db,
                    deal_id=paid.deal_id,
                    buyer_id=paid.buyer_id,
                    anchor_dt=_as_utc(getattr(paid, "created_at", None)),
                )
                dep_id = getattr(fresh, "deposit_id", None) or getattr(fresh, "id", None)
                logging.info("[AUTO_REFUND] fresh_deposit=%s", dep_id)

                if fresh and dep_id:
                    # 후보 함수명/시그니처를 관대하게 시도
                    fn_names = ("refund_deposit", "refund_deposit_by_id", "refund_buyer_deposit")
                    called = False
                    for name in fn_names:
                        fn = getattr(crud, name, None)
                        if not callable(fn):
                            continue
                        try:
                            fn(db, deposit_id=dep_id)  # 키워드 우선
                            called = True
                            logging.info("[AUTO_REFUND] %s(deposit_id=%s) OK (kw)", name, dep_id)
                            break
                        except TypeError:
                            try:
                                fn(db, dep_id)  # 위치 인자 백업
                                called = True
                                logging.info("[AUTO_REFUND] %s(%s) OK (pos)", name, dep_id)
                                break
                            except TypeError:
                                try:
                                    fn(db, deposit_id=dep_id, actor="auto_on_pay")  # actor 지원 구현
                                    called = True
                                    logging.info("[AUTO_REFUND] %s(deposit_id=%s,actor=auto_on_pay) OK", name, dep_id)
                                    break
                                except TypeError:
                                    continue
                    if not called:
                        logging.warning("[AUTO_REFUND] refund function not found or wrong signature")
                else:
                    logging.info("[AUTO_REFUND] skip: no fresh HELD deposit for this reservation")
        except Exception as _e:
            # 자동 환불은 보조 기능이므로 실패해도 결제 성공 흐름은 유지
            logging.warning("[AUTO_REFUND] failed: %s", _e)

        return paid
    except Exception as e:
        _translate_error(e)


class ReservationRefundIn(BaseModel):
    reservation_id: int
    actor: str = "buyer_cancel"


@router_resv.post(
    "/refund",
    response_model=schemas.ReservationOut,
    summary="결제 후 환불 — PAID → CANCELLED, buyer 포인트 롤백",
)
def api_refund_paid_reservation(
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


@router_resv.post(
    "/expire",
    summary="만료 스윕 — 기한 지난 PENDING → EXPIRED",
)
def api_expire_reservations(
    db: Session = Depends(get_db),
):
    try:
        n = expire_reservations(db)
        return {"expired": n}
    except Exception as e:
        _translate_error(e)


# ─────────────────────────────────────────────────────
# B) /offers
# ─────────────────────────────────────────────────────
router_offers = APIRouter(prefix="/offers", tags=["offers"])


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
    summary="오퍼 확정(전량 판매 시) — 셀러 +30pt",
)
def api_confirm_offer(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        offer = confirm_offer_if_soldout(db, offer_id=offer_id, seller_point_on_confirm=30)
        return {
            "offer_id": offer_id,
            "confirmed": bool(getattr(offer, "is_confirmed", False)),
            "decision_state": getattr(offer, "decision_state", None),
        }
    except Exception as e:
        _translate_error(e)


class SetTotalBody(BaseModel):
    total: Optional[int] = None
    total_available_qty: Optional[int] = None


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


# ─────────────────────────────────────────────────────
# 집계 라우터(api): 원하면 main.py에서 이 'api' 하나만 include
# ─────────────────────────────────────────────────────
api = APIRouter()
api.include_router(router_resv)    # /reservations/*
api.include_router(router_offers)  # /offers/*


# ─────────────────────────────────────────────────────
# Export aliases (v3.5)
# ─────────────────────────────────────────────────────
from fastapi import APIRouter as _APIRouter  # type: ignore

router_reservations_v35: _APIRouter = router_resv
router_offers_v35: _APIRouter = router_offers
router: _APIRouter = router_resv  # 구 호환

__all__ = [
    "router_reservations_v35",
    "router_offers_v35",
    "router",
    "router_offers",
    "api",
]