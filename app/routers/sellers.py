# app/routers/sellers.py
# 🔧 무인증(DEV) 버전 - 인증 제거 완료
# Writer: Jeong Sang Lee
# Date: 2025-11-07

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Path, Body, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .. import crud, schemas, database
from app import models, crud, schemas
from app.database import get_db

import logging
from app.routers.notifications import create_notification
from datetime import datetime, timezone

# 온보딩 승인 레코드에서 회사명/생성시각을 끌어오도록 시도
try:
    from app.routers.sellers_onboarding import SellerOnboarding  # type: ignore
except Exception:
    SellerOnboarding = None  # type: ignore


router = APIRouter(
    prefix="/sellers",
    tags=["sellers (NO-AUTH DEV)"],
)

@router.post(
    "/{seller_id}/approve",
    response_model=schemas.SellerOut,   # 프로젝트에서 쓰는 Seller 응답 스키마
    summary="운영자용: 셀러 승인",
)
def api_approve_seller(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    """
    운영자가 셀러를 APPROVED 상태로 바꾸는 API.
    - crud.approve_seller 를 그대로 호출한다.
    """
    try:
        seller = crud.approve_seller(db, seller_id)
        return seller
    except HTTPException:
        # crud.approve_seller 안에서 이미 HTTPException 을 던졌다면 그대로 전달
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------------------------------
# 1️⃣ 로그인된 판매자 정보 (무인증 대체 버전)
# -----------------------------------------------------
@router.get("/me")
def read_me():
    """
    ✅ 무인증 개발 모드:
    인증 절차 없이 항상 더미 판매자(dev_seller@yeokping.com)로 응답
    """
    return {"ok": True, "user": {"email": "dev_seller@yeokping.com (no-auth)"}}


# -----------------------------------------------------
# 2️⃣ 신규 Seller 생성
# -----------------------------------------------------
# app/routers/sellers.py

@router.post("/", response_model=schemas.SellerOut)
def create_seller(
    seller: schemas.SellerCreate,
    db: Session = Depends(database.get_db),
):
    """
    신규 Seller 생성 + (있다면) 연결된 Actuator에게 알림 발송
    """
    try:
        db_seller = crud.create_seller(db, seller)

        # 🔔 액츄에이터에게 "추천 셀러 온보딩 완료" 알림
        actuator_id = int(getattr(db_seller, "actuator_id", 0) or 0)
        if actuator_id > 0:
            try:
                create_notification(
                    db,
                    user_id=actuator_id,
                    type="seller_onboarded",
                    title="추천하신 셀러가 가입을 완료했어요",
                    message=f"추천한 셀러 #{db_seller.id} 가 판매자 등록을 완료했습니다.",
                    meta={
                        "role": "actuator",
                        "seller_id": db_seller.id,
                    },
                )
            except Exception as notify_err:
                logging.exception(
                    "failed to create seller_onboarded notification",
                    exc_info=notify_err,
                )

        return db_seller

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already exists")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

# -----------------------------------------------------
# 3️⃣ Seller 목록 조회
# -----------------------------------------------------
@router.get("/", response_model=list[schemas.SellerOut])
def list_sellers(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(database.get_db),
):
    return crud.get_sellers(db, skip=skip, limit=limit)


class SellerBasicOut(BaseModel):
    seller_id: int
    name: Optional[str] = None          # 포털 normalizeBasicInfo는 name/company_name 둘 다 인식
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None
    approval_status: Optional[str] = None  # APPROVED / PENDING / etc

# -----------------------------------------------------
# 4️⃣ Seller 단건 조회 (기본 프로필 + 승인 상태)
# -----------------------------------------------------
@router.get("/{seller_id}", response_model=SellerBasicOut)
def get_seller_basic(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(database.get_db),
):
    company = None
    created = None
    approval_status: Optional[str] = None

    # 1) 온보딩 레코드에서 회사명/생성시각 우선 가져오기
    if SellerOnboarding is not None:
        try:
            q = (
                db.query(SellerOnboarding)
                  .filter(SellerOnboarding.seller_id == seller_id)
                  .order_by(SellerOnboarding.id.desc())
            )
            row = q.first()
            if row:
                company = getattr(row, "company_name", None)
                created = getattr(row, "created_at", None)
        except Exception:
            pass

    # 2) Seller 테이블에서 이메일/전화/주소/승인상태 보완
    try:
        seller_row = db.query(models.Seller).get(seller_id)
    except Exception:
        seller_row = None

    email = None
    phone = None
    address = None

    if seller_row is not None:
        email = getattr(seller_row, "email", None)
        phone = getattr(seller_row, "phone", None) or getattr(seller_row, "company_phone", None)
        address = getattr(seller_row, "address", None)

        if created is None:
            created = getattr(seller_row, "created_at", None)
        if not company:
            company = getattr(seller_row, "business_name", None) or company

        # ✅ 승인 상태 (crud 헬퍼 재사용)
        try:
            approval_status = crud.seller_approval_status(seller_row)
        except Exception:
            approval_status = None

    # 3) 기본값(온보딩/셀러 둘 다 없을 때)
    if not company:
        company = f"Seller #{seller_id}"
    if created is None:
        created = datetime.now(timezone.utc)

    return SellerBasicOut(
        seller_id=seller_id,
        name=company,
        company_name=company,
        email=email,
        phone=phone,
        address=address,
        created_at=created,
        approval_status=approval_status,
    )

# -----------------------------------------------------
# 5️⃣ Seller 수동 승인
# -----------------------------------------------------
@router.patch("/{seller_id}/approve", response_model=schemas.SellerOut)
def approve_seller_api(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(database.get_db),
):
    """
    ✅ Seller 수동 승인 API
    - 생성 이후에 운영자가 Seller를 '승인' 처리할 때 사용
    - crud.approve_seller 를 thin-wrapper 로 감쌈
    - 반환 스키마는 기존 SellerOut 을 그대로 사용
    """
    try:
        seller = crud.approve_seller(db, seller_id)
    except HTTPException:
        # crud에서 던진 404/400 그대로 전달
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve seller: {e}")

    return seller