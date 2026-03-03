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
import inspect


router = APIRouter(
    prefix="/admin/refund",
    tags=["admin_refund"],
)

def _xlate(e: Exception):
    """간단 에러 변환 (원인 파악을 위해 500에서도 메시지 노출 + 서버 로그)"""
    import logging

    if isinstance(e, NotFoundError):
        raise HTTPException(status_code=404, detail=str(e) or "not found")

    # ✅ 원인 파악용: 서버 로그에 traceback 남기기
    logging.exception("[admin_refund_preview] error", exc_info=e)

    # ✅ 원인 파악용: 클라이언트에도 타입/메시지 내려주기
    raise HTTPException(
        status_code=500,
        detail={"error": e.__class__.__name__, "msg": str(e)},
    )


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
        fn = preview_refund_for_reservation
        sig = inspect.signature(fn)

        kwargs = {
            "reservation_id": reservation_id,
            "fault_party": fault_party,
            "trigger": trigger,
        }

        # ✅ CRUD 함수가 실제로 받는 인자만 필터링해서 넘긴다 (fault_party 없으면 자동 제외)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}

        return fn(db, **filtered)

    except Exception as e:
        _xlate(e)