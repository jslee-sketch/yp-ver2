# routers/simulate_v3_6.py
from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import DealRoundCreate, DealRoundOut, RoundProgressIn
from ..crud import (
    create_deal_round,
    progress_round,
    list_rounds,
    get_active_round,
    NotFoundError,
    ConflictError,
)

router = APIRouter(prefix="/admin/simulate/v3_6", tags=["admin/simulate v3.6"])

def _translate_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ConflictError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")

# -------------------------------------------------------------------
# 라운드 생성
# -------------------------------------------------------------------
@router.post(
    "/rounds/{deal_id}/create",
    response_model=DealRoundOut,
    status_code=status.HTTP_201_CREATED,
    summary="(v3.6) 라운드 생성(PLANNED)",
)
def api_create_round(
    deal_id: int = Path(..., ge=1),
    payload: DealRoundCreate = ...,
    db: Session = Depends(get_db),
):
    """
    동일 딜 내 `(deal_id, round_no)` 유니크 보장.
    생성 시 상태=PLANNED. OPEN은 progress API로 전이하세요.
    """
    try:
        return create_deal_round(db, deal_id=deal_id, round_no=payload.round_no, meta=payload.meta)
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 라운드 상태 전이 (OPEN/FINALIZE/CLOSE/CANCEL)
# -------------------------------------------------------------------
@router.post(
    "/rounds/{deal_id}/progress",
    response_model=DealRoundOut,
    summary="(v3.6) 라운드 상태 전이: OPEN → FINALIZING → CLOSED/CANCELLED",
)
def api_progress_round(
    deal_id: int = Path(..., ge=1),
    payload: RoundProgressIn = ...,
    db: Session = Depends(get_db),
):
    """
    action: OPEN | FINALIZE | CLOSE | CANCEL
    round_no 미지정 시 OPEN/FINALIZE/CLOSE는 활성 라운드 대상으로 처리(정책에 따라 최근 FINALIZING 사용 가능).
    """
    try:
        return progress_round(db, deal_id=deal_id, action=payload.action, round_no=payload.round_no)
    except Exception as e:
        _translate_error(e)

# 선택: REST 스타일 보조 엔드포인트
@router.post(
    "/rounds/{deal_id}/{action}",
    response_model=DealRoundOut,
    summary="(v3.6) 보조: path param action으로 전이",
)
def api_progress_round_alt(
    deal_id: int = Path(..., ge=1),
    action: str = Path(..., pattern="^(OPEN|FINALIZE|CLOSE|CANCEL)$"),
    round_no: Optional[int] = Query(default=None, ge=1, description="대상 라운드. 미지정 시 활성 라운드"),
    db: Session = Depends(get_db),
):
    try:
        return progress_round(db, deal_id=deal_id, action=action, round_no=round_no)
    except Exception as e:
        _translate_error(e)

# -------------------------------------------------------------------
# 라운드 조회
# -------------------------------------------------------------------
@router.get(
    "/rounds",
    response_model=List[DealRoundOut],
    summary="(v3.6) 특정 딜의 모든 라운드 조회",
)
def api_list_rounds(
    deal_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        return list_rounds(db, deal_id=deal_id)
    except Exception as e:
        _translate_error(e)

@router.get(
    "/rounds/active",
    response_model=DealRoundOut,
    summary="(v3.6) 활성(OPEN) 라운드 조회",
)
def api_get_active_round(
    deal_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
):
    try:
        r = get_active_round(db, deal_id=deal_id)
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active (OPEN) round")
        return r
    except Exception as e:
        _translate_error(e)