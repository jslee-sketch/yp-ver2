# app/routers/seller_offers.py
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query, Body
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from ..database import get_db
from ..models import Offer, Reservation, ReservationStatus
from ..crud import (
    NotFoundError,
    ConflictError,
    seller_confirm_offer,
    seller_withdraw_offer_v35,     # v3.5 고정 포인트 반영 철회
    update_offer_total_qty,        # ✅ 총량 변경
    get_offer_remaining_capacity,  # ✅ 잔여 계산
    audit_offer_inventory,
    reconcile_offer_inventory,
    get_offer_snapshot,            # ✅ 스냅샷 (reservations 라우터 의존 없는 별칭)
)
from ..config import project_rules as R

router = APIRouter(prefix="/offers", tags=["seller offers v3.5"])


# 공통 에러 변환
def _translate_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")


# 간단한 별칭
def _tx(e: Exception):
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")


# ------------------------------------------------------------
# (편의) 오퍼 기본 정보(판매자/딜 id) — 포인트 조회 등에 사용
# ------------------------------------------------------------
@router.get(
    "/{offer_id}/who",
    summary="오퍼 기본 정보(판매자/딜 id)",
    operation_id="SellerOffers__Who",
)
def api_offer_who(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        offer = db.get(Offer, offer_id)
        if not offer:
            raise NotFoundError("Offer not found")
        return {"offer_id": offer.id, "seller_id": offer.seller_id, "deal_id": offer.deal_id}
    except Exception as e:
        _translate_error(e)


# -------------------------------------------------------------------
# 판매자 의사결정창 상태 조회
# -------------------------------------------------------------------
@router.get(
    "/{offer_id}/decision-window",
    summary="판매자 의사결정창 상태 조회 (can_withdraw / can_confirm / deadline 등)",
    operation_id="SellerOffers__DecisionWindow",
)
def api_offer_decision_window(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        offer = db.get(Offer, offer_id)
        if not offer:
            raise NotFoundError("Offer not found")

        sold = int(offer.sold_qty or 0)
        total = int(offer.total_available_qty or 0)

        pending_cnt = (
            db.query(func.count(Reservation.id))
              .filter(
                  Reservation.offer_id == offer_id,
                  Reservation.status == ReservationStatus.PENDING,
              )
              .scalar()
        ) or 0

        # 상태 플래그
        is_active = bool(getattr(offer, "is_active", True))
        is_confirmed = bool(getattr(offer, "is_confirmed", False))
        decision_state = getattr(offer, "decision_state", None)

        # ▶ 확정 해제 후에도 decision_state="CONFIRMED"가 남아 있을 수 있는 스테일 보정
        if (not is_confirmed) and decision_state == "CONFIRMED":
            decision_state = None

        terminal_states = {"WITHDRAWN", "AUTO_WITHDRAWN", "CONFIRMED", "AUTO_CONFIRMED"}
        live = is_active and (decision_state not in terminal_states)

        can_confirm = live and (total > 0) and (sold == total) and (pending_cnt == 0)
        # 확정 상태에선 어떤 경우든 철회 불가
        can_withdraw = live and (not is_confirmed) and (not can_confirm)

        # 마감 시각 계산 (DeadTime-aware 우선)
        minutes = 30
        try:
            minutes = int(getattr(R, "TIMELINE", {}).get("SELLER_DECISION_WINDOW", 0.5) * 60)
        except Exception:
            pass

        if getattr(offer, "decision_deadline_at", None):
            deadline = offer.decision_deadline_at
        else:
            if hasattr(R, "apply_deadtime_pause"):
                deadline = R.apply_deadtime_pause(datetime.now(timezone.utc), minutes=minutes)
            else:
                deadline = datetime.now(timezone.utc) + timedelta(minutes=minutes)

        return {
            "offer_id": offer_id,
            "sold": sold,
            "total": total,
            "pending": int(pending_cnt),
            "can_withdraw": bool(can_withdraw),
            "can_confirm": bool(can_confirm),
            "is_confirmed": is_confirmed,
            "decision_deadline_at": deadline,
            "decision_state": decision_state,
            "is_active": is_active,
        }
    except Exception as e:
        _translate_error(e)


# -------------------------------------------------------------------
# 판매자 철회 (부분/무판매 시 허용) — 바이어 포인트 −20 고정 회수(v3.5)
# -------------------------------------------------------------------
@router.post(
    "/{offer_id}/seller/withdraw",
    summary="판매자 철회 (부분/무판매 시 허용) — 바이어 포인트 −20 고정 회수",
    operation_id="SellerOffers__Withdraw",
)
def api_seller_withdraw(
    offer_id: int = Path(..., ge=1),
    reason: Optional[str] = Query(default=None, description="철회 사유"),
    db: Session = Depends(get_db),
):
    try:
        offer = seller_withdraw_offer_v35(
            db,
            offer_id=offer_id,
            reason=reason,
            penalize_seller=True,
        )
        return {"offer_id": offer_id, "withdrawn": True, "decision_state": offer.decision_state}
    except Exception as e:
        _translate_error(e)


# -------------------------------------------------------------------
# 판매자 확정 — 전량+PENDING=0일 때만 +30pt
#  - force=True 이면 전량 미달이어도 확정(포인트 없음)
# -------------------------------------------------------------------
@router.post(
    "/{offer_id}/seller/confirm",
    summary="판매자 확정 — 전량 판매 시 +30pt, force=True 시 강제 확정(무포인트)",
    operation_id="SellerOffers__Confirm",
)
def api_seller_confirm(
    offer_id: int = Path(..., ge=1),
    force: bool = Query(False, description="True면 전량 미달이어도 확정(포인트 없음)"),
    award_on_full: int = Query(30, ge=0, description="전량판매 확정 시 가산 포인트"),
    db: Session = Depends(get_db),
):
    try:
        offer = seller_confirm_offer(db, offer_id=offer_id, force=force, award_on_full=award_on_full)
        # 확정되면 표시 플래그도 반영
        offer.decision_state = "CONFIRMED" if offer.is_confirmed else getattr(offer, "decision_state", None)
        db.add(offer)
        db.commit()
        db.refresh(offer)
        return {
            "offer_id": offer_id,
            "confirmed": offer.is_confirmed,
            "decision_state": offer.decision_state,
            "force": force,
        }
    except Exception as e:
        _translate_error(e)


# -------------------------------------------------------------------
# 오퍼 총량 변경 — 증량 시 자동 unconfirm, remaining 함께 반환
# -------------------------------------------------------------------
@router.post(
    "/{offer_id}/set_total",
    summary="오퍼 총량 변경(증량 시 자동 unconfirm) — remaining도 함께 반환",
    operation_id="SellerOffers__SetTotal",  # 고유 operationId로 충돌 제거
)
def seller_offers_set_total(
    offer_id: int = Path(..., ge=1),
    body: dict = Body(..., example={"total_available_qty": 20}),
    db: Session = Depends(get_db),
):
    try:
        if "total_available_qty" not in body:
            raise ConflictError("missing field: total_available_qty")
        new_total = int(body["total_available_qty"])

        offer = update_offer_total_qty(db, offer_id=offer_id, total_available_qty=new_total)
        remain = get_offer_remaining_capacity(db, offer_id)

        return {
            "deal_id": offer.deal_id,
            "id": offer.id,
            "total_available_qty": offer.total_available_qty,
            "sold_qty": offer.sold_qty,
            "reserved_qty": offer.reserved_qty,
            "is_confirmed": offer.is_confirmed,
            "is_active": offer.is_active,
            "remaining": remain,
            "created_at": offer.created_at,
            "deadline_at": offer.deadline_at,
            "comment": offer.comment,
        }
    except Exception as e:
        _translate_error(e)


# === JSON 없이도 되는 QS 버전: 총량 변경 ===
@router.post(
    "/{offer_id}/set_total_qs",
    summary="오퍼 총량 변경(QS) — JSON 바디 없이 ?total= 로 변경",
    operation_id="SellerOffers__SetTotalQS",
)
def api_set_total_qs(
    offer_id: int = Path(..., ge=1),
    total: int = Query(..., ge=0, description="새 total_available_qty"),
    db: Session = Depends(get_db),
):
    try:
        offer = update_offer_total_qty(db, offer_id=offer_id, total_available_qty=total)
        remaining = get_offer_remaining_capacity(db, offer_id)
        return {
            "offer_id": offer.id,
            "deal_id": offer.deal_id,
            "total_available_qty": offer.total_available_qty,
            "sold_qty": offer.sold_qty,
            "reserved_qty": offer.reserved_qty,
            "is_confirmed": offer.is_confirmed,
            "is_active": offer.is_active,
            "remaining": remaining,
            "created_at": offer.created_at,
            "deadline_at": offer.deadline_at,
            "comment": offer.comment,
        }
    except Exception as e:
        _tx(e)


# ------------------------------------------------------------
# 스냅샷 / 점검 / 동기화
# ------------------------------------------------------------
@router.get(
    "/{offer_id}/stats",
    summary="오퍼 수량 스냅샷(총/예약/판매/남은수량 + 상태별 합계)",
    operation_id="SellerOffers__Stats",
)
def api_offer_stats_alias(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        return get_offer_snapshot(db, offer_id)
    except Exception as e:
        _tx(e)


@router.get(
    "/{offer_id}/audit",
    summary="오퍼 인벤토리 점검 — reserved/sold vs sum(PENDING/PAID)",
    operation_id="SellerOffers__Audit",
)
def api_offer_audit(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        return audit_offer_inventory(db, offer_id)
    except Exception as e:
        _translate_error(e)


@router.post(
    "/{offer_id}/reconcile",
    summary="오퍼 인벤토리 동기화 — reserved/sold를 예약합계로 정렬",
    operation_id="SellerOffers__Reconcile",
)
def api_offer_reconcile(
    offer_id: int = Path(..., ge=1),
    apply: bool = Query(False, description="true면 실제 반영(dry-run 아님)"),
    db: Session = Depends(get_db),
):
    try:
        return reconcile_offer_inventory(db, offer_id, apply=apply)
    except Exception as e:
        _translate_error(e)


# ------------------------------------------------------------
# (관리용) WITHDRAWN 오퍼 재활성화
# ------------------------------------------------------------
@router.post(
    "/{offer_id}/reactivate",
    summary="(관리용) WITHDRAWN 오퍼 재활성화",
    operation_id="SellerOffers__Reactivate",
)
def api_offer_reactivate(
    offer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        offer = db.get(Offer, offer_id)
        if not offer:
            raise NotFoundError("Offer not found")

        # 철회 상태가 아니면 재활성화 대상 아님
        decision_state = getattr(offer, "decision_state", None)
        if decision_state not in {"WITHDRAWN", "AUTO_WITHDRAWN"}:
            raise ConflictError("offer is not withdrawn")

        # 안전장치: 판매/예약 수량이 남아있으면 재활성화 불가
        if int(offer.sold_qty or 0) > 0 or int(offer.reserved_qty or 0) > 0:
            raise ConflictError("cannot reactivate: sold/reserved must be zero")

        offer.is_active = True
        offer.is_confirmed = False
        offer.decision_state = None
        offer.decision_made_at = None
        offer.decision_reason = None

        db.add(offer)
        db.commit()
        db.refresh(offer)

        return {
            "offer_id": offer.id,
            "reactivated": True,
            "is_active": offer.is_active,
            "decision_state": offer.decision_state,
        }
    except Exception as e:
        _translate_error(e)