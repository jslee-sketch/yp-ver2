# app/routers/deposits.py
from __future__ import annotations

from typing import Optional, Literal
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Path, Body, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import crud
from ..logic.trust import buyer_trust_tier_and_deposit_percent
from app.config import project_rules as R


# ---- 프로젝트 예외(없으면 폴백 정의) -----------------------------------------
try:
    from ..crud import NotFoundError, ConflictError
except Exception:
    class NotFoundError(Exception): ...
    class ConflictError(Exception): ...

class DepositConflict(ConflictError):
    """Deposit idempotency / state conflict."""

# ---- (선택) ORM 모델 폴백 ----------------------------------------------------
try:
    from ..models import BuyerDeposit  # 프로젝트에 존재하지 않을 수도 있음
except Exception:
    BuyerDeposit = None  # type: ignore

# ---- 라우터 ------------------------------------------------------------------
router = APIRouter(prefix="/deposits", tags=["deposits v3.5"])

# ---- 공용 스키마 -------------------------------------------------------------
class DepositHoldIn(BaseModel):
    amount: int = Field(..., ge=1, description="디파짓 홀드 금액(원)")

class DepositOut(BaseModel):
    deposit_id: int
    deal_id: int
    buyer_id: int
    amount: int
    status: Literal["HELD", "REFUNDED"]
    created_at: Optional[datetime] = None
    refunded_at: Optional[datetime] = None

# ---- 유틸 --------------------------------------------------------------------
def _status_norm(s: str | None) -> str:
    u = (s or "").upper()
    if u in {"HOLD", "ACTIVE"}:
        return "HELD"
    return u

def _translate_error(e: Exception) -> None:
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, (ConflictError, DepositConflict)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")

def _get_active_deposit_for(db: Session, *, deal_id: int, buyer_id: int):
    """
    ACTIVE/HELD 디파짓 조회.
    crud.get_active_deposit_for를 우선 사용, 없으면 모델 직접 조회.
    """
    fn = getattr(crud, "get_active_deposit_for", None)
    if callable(fn):
        try:
            return fn(db, deal_id=deal_id, buyer_id=buyer_id)
        except TypeError:
            return fn(db, deal_id, buyer_id)  # type: ignore[misc]

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
        return q.first()
    return None

# ---- 외부에서 사용하는 결제 전 디파짓 가드 -----------------------------------
def ensure_deposit_before_pay(
    db: Session,
    *,
    deal_id: int,
    buyer_id: int,
    min_amount: int | None = None,
    max_age_minutes: int | None = None,
) -> dict:
    """
    결제 직전 가드:
      - R.DEPOSIT_REQUIRE_ALWAYS 가 True면 무조건 디파짓 요구
      - 아니면, buyer_trust_tier_and_deposit_percent(db, buyer_id)['deposit_percent'] > 0 이면 디파짓 요구
      - 디파짓이 '요구'되면 ACTIVE/HOLD/HELD 상태의 보증금이 실제로 있어야 통과
      - min_amount / max_age_minutes 조건도 함께 적용
    반환 예:
      - {"required": False, "ok": True}                       # 불요
      - {"required": True, "ok": True, "deposit_id": ..., ...} # 요구 + 충족(통과)
    요구인데 불충족이면 ConflictError("deposit_required") 발생 → 409로 번역됨
    """
    # 1) 요구 여부 판단: 토글 우선, 없으면 티어 퍼센트
    force = bool(getattr(R, "DEPOSIT_REQUIRE_ALWAYS", False))
    pct = 0.0
    if not force:
        try:
            trust = buyer_trust_tier_and_deposit_percent(db, buyer_id) or {}
            pct = float(trust.get("deposit_percent") or 0.0)
        except Exception:
            pct = 0.0
    require = force or (pct > 0.0)

    if not require:
        return {"required": False, "ok": True}

    # 2) 실제 활성 디파짓 확인
    dep = _get_active_deposit_for(db, deal_id=deal_id, buyer_id=buyer_id)
    if not dep:
        raise ConflictError("deposit_required")

    status_norm = _status_norm(getattr(dep, "status", None))
    if status_norm != "HELD":
        raise ConflictError("deposit_required")

    # 3) 금액/유효기간 옵션 검사
    if min_amount is not None:
        if int(getattr(dep, "amount", 0) or 0) < int(min_amount):
            raise ConflictError("deposit_required")

    if max_age_minutes and getattr(dep, "created_at", None):
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=int(max_age_minutes))
        if getattr(dep, "created_at") < cutoff:
            raise ConflictError("deposit_required")

    return {
        "required": True,
        "ok": True,
        "deposit_id": getattr(dep, "id", None),
        "amount": getattr(dep, "amount", None),
        "status": "HELD",
    }

# ---- 1) 디파짓 홀드 생성 ------------------------------------------------------
@router.post(
    "/hold/{deal_id}/{buyer_id}",
    summary="구매자 디파짓 홀드 생성",
    status_code=status.HTTP_201_CREATED,
    response_model=DepositOut,
)
def hold_deposit(
    deal_id: int = Path(..., ge=1),
    buyer_id: int = Path(..., ge=1),
    payload: DepositHoldIn = Body(...),
    db: Session = Depends(get_db),
):
    try:
        dep = crud.create_buyer_deposit(
            db, deal_id=deal_id, buyer_id=buyer_id, amount=int(payload.amount)
        )
        if dep is None:
            raise ConflictError("Deposit tracking disabled")

        # ORM 객체든 dict든 안전하게 매핑
        return DepositOut(
            deposit_id=getattr(dep, "id", None),
            deal_id=getattr(dep, "deal_id", deal_id),
            buyer_id=getattr(dep, "buyer_id", buyer_id),
            amount=getattr(dep, "amount", payload.amount),
            status=_status_norm(getattr(dep, "status", "HELD")) or "HELD",
            created_at=getattr(dep, "created_at", None),
            refunded_at=getattr(dep, "refunded_at", None),
        )
    except Exception as e:
        _translate_error(e)

# ---- 2) 디파짓 환불(멱등) -----------------------------------------------------
@router.post(
    "/refund/{deposit_id}",
    summary="구매자 디파짓 환불",
    response_model=DepositOut,
)
def refund_deposit(
    deposit_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        dep0 = crud.get_buyer_deposit(db, deposit_id)
        if not dep0:
            raise NotFoundError("Deposit not found")

        if _status_norm(getattr(dep0, "status", None)) == "REFUNDED":
            # 이미 환불됨 → 멱등 409
            raise DepositConflict("Deposit already refunded")

        dep = crud.refund_buyer_deposit(db, deposit_id)
        if not dep:
            raise NotFoundError("Deposit not found (after)")

        if _status_norm(getattr(dep, "status", None)) != "REFUNDED":
            raise ConflictError(f"Refund not applied (status={getattr(dep, 'status', None)})")

        return DepositOut(
            deposit_id=getattr(dep, "id", deposit_id),
            deal_id=getattr(dep, "deal_id", None),
            buyer_id=getattr(dep, "buyer_id", None),
            amount=getattr(dep, "amount", None),
            status="REFUNDED",
            refunded_at=getattr(dep, "refunded_at", None),
            created_at=getattr(dep, "created_at", None),
        )
    except DepositConflict as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        _translate_error(e)

# ---- 3) 디파짓 정책 프리뷰 ----------------------------------------------------
@router.get(
    "/policy/preview",
    summary="Deposit 비율(티어 연동) 프리뷰",
)
def api_deposit_policy_preview(
    buyer_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        return buyer_trust_tier_and_deposit_percent(db, buyer_id)
    except Exception as e:
        _translate_error(e)

# ---- 4) 단건 조회(디버깅용) ---------------------------------------------------
@router.get("/by-id/{deposit_id}", summary="디파짓 단건 조회(디버깅용)")
def get_deposit_by_id(
    deposit_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    dep = crud.get_buyer_deposit(db, deposit_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deposit not found")
    return {
        "deposit_id": getattr(dep, "id", deposit_id),
        "deal_id": getattr(dep, "deal_id", None),
        "buyer_id": getattr(dep, "buyer_id", None),
        "amount": getattr(dep, "amount", None),
        "status": _status_norm(getattr(dep, "status", None)) or None,
        "created_at": getattr(dep, "created_at", None),
        "refunded_at": getattr(dep, "refunded_at", None),
    }
    
# ---- (디버그) 현재 활성 디파짓 조회 ------------------------------------------
@router.get(
    "/active/{deal_id}/{buyer_id}",
    summary="(디버그) 해당 딜/구매자의 활성(HELD/HOLD/ACTIVE) 디파짓 조회",
)
def get_active_deposit(
    deal_id: int = Path(..., ge=1),
    buyer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    dep = _get_active_deposit_for(db, deal_id=deal_id, buyer_id=buyer_id)
    if not dep:
        return {"active": False}
    return {
        "active": True,
        "deposit_id": getattr(dep, "id", None),
        "deal_id": getattr(dep, "deal_id", deal_id),
        "buyer_id": getattr(dep, "buyer_id", buyer_id),
        "amount": getattr(dep, "amount", None),
        "status": _status_norm(getattr(dep, "status", None)) or None,
        "created_at": getattr(dep, "created_at", None),
        "refunded_at": getattr(dep, "refunded_at", None),
    }