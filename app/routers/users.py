"""공통 유저 유틸 엔드포인트 (닉네임 체크 등)."""
import re
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud

router = APIRouter(prefix="/users", tags=["users"])

_NICK_RE = re.compile(r'^[가-힣a-zA-Z0-9_]{2,15}$')


@router.get("/check-nickname")
def check_nickname(
    nickname: str = Query(..., min_length=2, max_length=15, description="확인할 닉네임"),
    db: Session = Depends(get_db),
):
    """
    닉네임 가용 여부 확인.
    - 형식 검사 (2~15자, 한글/영문/숫자/_ 만)
    - buyers + sellers 전체 중복 체크
    """
    if not _NICK_RE.fullmatch(nickname):
        return {"available": False, "reason": "invalid_format"}
    available = crud.is_nickname_available(db, nickname)
    return {"available": available}
