"""공통 유저 유틸 엔드포인트 (닉네임 체크, 전화번호 체크 등)."""
import re
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud, models

router = APIRouter(prefix="/users", tags=["users"])

_NICK_RE = re.compile(r'^[가-힣a-zA-Z0-9_]{2,20}$')

BANNED_NICKNAMES = {
    "관리자", "admin", "운영자", "역핑", "yeokping",
    "test", "테스트", "system", "시스템",
}


@router.get("/check-nickname")
def check_nickname(
    nickname: str = Query(..., min_length=2, max_length=20, description="확인할 닉네임"),
    db: Session = Depends(get_db),
):
    """
    닉네임 가용 여부 확인.
    - 금지어 체크
    - 형식 검사 (2~20자, 한글/영문/숫자/_ 만)
    - buyers + sellers 전체 중복 체크
    """
    if nickname.lower() in BANNED_NICKNAMES:
        return {"available": False, "reason": "banned"}
    if not _NICK_RE.fullmatch(nickname):
        return {"available": False, "reason": "invalid_format"}
    available = crud.is_nickname_available(db, nickname)
    return {"available": available}


@router.get("/check-phone", summary="전화번호 중복 확인")
def check_phone(
    phone: str = Query(..., description="확인할 전화번호"),
    db: Session = Depends(get_db),
):
    """Buyer + Seller 테이블에서 전화번호 중복 여부를 확인합니다."""
    phone_clean = re.sub(r'\D', '', phone)
    buyer = db.query(models.Buyer).filter(models.Buyer.phone == phone_clean).first()
    if buyer:
        return {"available": False}
    seller = db.query(models.Seller).filter(models.Seller.phone == phone_clean).first()
    if seller:
        return {"available": False}
    return {"available": True}
