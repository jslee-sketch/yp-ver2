# app/routers/admin_refund_preview.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..crud import (
    preview_refund_for_reservation,
    NotFoundError,
)
from ..core.refund_policy import FaultParty, RefundTrigger

router = APIRouter(
    prefix="/admin/refund",
    tags=["admin_refund"],
)


def _xlate(e: Exception):
    """간단 에러 변환 (필요하면 더 추가 가능)"""
    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    raise HTTPException(status_code=500, detail="Internal error")


@router.get("/preview", summary="환불 정책 미리 보기")
def api_preview_refund(
    reservation_id: int = Query(..., ge=1, description="예약 ID"),
    fault_party: FaultParty = Query(
        FaultParty.BUYER,
        description="귀책 주체 (BUYER / SELLER / SYSTEM / DISPUTE)",
    ),
    trigger: RefundTrigger = Query(
        RefundTrigger.BUYER_CANCEL,
        description="환불 트리거 (기본: BUYER_CANCEL)",
    ),
    db: Session = Depends(get_db),
):
    """
    예시:

    GET /admin/refund/preview?reservation_id=57&fault_party=BUYER
    GET /admin/refund/preview?reservation_id=57&fault_party=SELLER&trigger=SELLER_CANCEL
    """
    try:
        return preview_refund_for_reservation(
            db,
            reservation_id=reservation_id,
            fault_party=fault_party,
            trigger=trigger,
        )
    except Exception as e:
        _xlate(e)