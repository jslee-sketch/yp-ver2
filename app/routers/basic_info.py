# app/routers/basic_info.py
from __future__ import annotations
from typing import Optional, List, Any, Mapping
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Path
from pydantic import BaseModel
from sqlalchemy import MetaData, Table, select, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.reviews import compute_seller_level_info, SellerLevelOut


# 가능한 경우 ORM 모델 사용
try:
    from app.models import Buyer as BuyerModel, Seller as SellerModel  # type: ignore
except Exception:
    BuyerModel = None  # type: ignore
    SellerModel = None  # type: ignore

# 🔸 prefix 를 /basic 으로 고정 → /buyers/*, /sellers/* 와 절대 안 겹치게
router = APIRouter(tags=["Basic Info"])

# ---------------- Pydantic ----------------
class BuyerBasicOut(BaseModel):
    buyer_id: int
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class SellerBasicOut(BaseModel):
    seller_id: int
    name: Optional[str] = None
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: Optional[datetime] = None
    approval_status: Optional[str] = None
        # 🔹 새로 추가되는 필드들
    level: Optional[str] = None          # 예: "Lv.6"
    fee_percent: Optional[float] = None  # 예: 3.5
    rating_adjusted: Optional[float] = None
    rating_count: Optional[int] = None
    total_orders: Optional[int] = None
    

    class Config:
        from_attributes = True


# ---------------- helpers ----------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _buyer_from_mapping(m: Mapping[str, Any]) -> BuyerBasicOut:
    return BuyerBasicOut(
        buyer_id=int(m.get("id") or m.get("buyer_id")),
        name=(
            m.get("name")
            or m.get("full_name")
            or m.get("display_name")
            or m.get("username")
        ),
        email=m.get("email") or m.get("email_address"),
        phone=m.get("phone") or m.get("phone_number") or m.get("mobile") or m.get("tel"),
        address=m.get("address") or m.get("addr") or m.get("shipping_address"),
        created_at=m.get("created_at") or m.get("joined_at") or m.get("createdAt"),
    )

def _seller_from_mapping(m: Mapping[str, Any]) -> SellerBasicOut:
    sid = int(m.get("id") or m.get("seller_id"))
    nm = m.get("name") or m.get("company_name")
    return SellerBasicOut(
        seller_id=sid,
        name=nm,
        company_name=m.get("company_name"),
        email=m.get("email"),
        phone=m.get("phone"),
        address=m.get("address"),
        created_at=m.get("created_at"),
    )

def _reflect_table(db: Session, names: List[str]) -> Optional[Table]:
    md = MetaData()
    bind = db.get_bind()
    for n in names:
        try:
            return Table(n, md, autoload_with=bind)
        except Exception:
            continue
    return None


# ---------------- fetchers (ORM → reflect → raw SQL) ----------------
def _fetch_buyer_row(db: Session, buyer_id: int) -> Optional[Mapping[str, Any]]:
    # 1) ORM
    if BuyerModel is not None:
        try:
            pk = getattr(BuyerModel, "id", None) or getattr(BuyerModel, "buyer_id", None)
            if pk is not None:
                row = db.query(BuyerModel).filter(pk == buyer_id).first()
                if row is not None:
                    return {
                        "id": getattr(row, "id", getattr(row, "buyer_id", None)),
                        "name": getattr(row, "name", None),
                        "email": getattr(row, "email", None),
                        "phone": getattr(row, "phone", None),
                        "address": getattr(row, "address", None),
                        "created_at": getattr(row, "created_at", None),
                    }
        except Exception:
            pass

    # 2) 리플렉션
    t = _reflect_table(db, ["buyers", "buyer"])
    if t is not None:
        try:
            col = t.c.get("id") or t.c.get("buyer_id")
            if col is not None:
                r = db.execute(select(t).where(col == buyer_id)).mappings().first()
                if r:
                    return r
        except Exception:
            pass

    # 3) 원시 SQL 폴백
    for tbl in ("buyers", "buyer"):
        for pk in ("id", "buyer_id"):
            try:
                sql = text(f"SELECT * FROM {tbl} WHERE {pk} = :bid LIMIT 1")
                r = db.execute(sql, {"bid": buyer_id}).mappings().first()
                if r:
                    return r
            except Exception:
                continue
    return None

def _fetch_buyer_list(db: Session, skip: int, limit: int) -> List[Mapping[str, Any]]:
    out: List[Mapping[str, Any]] = []

    if BuyerModel is not None:
        try:
            id_col = getattr(BuyerModel, "id", None) or getattr(BuyerModel, "buyer_id", None)
            q = db.query(BuyerModel)
            if id_col is not None:
                q = q.order_by(id_col.desc())
            rows = q.offset(skip).limit(limit).all()
            for r in rows:
                out.append({
                    "id": getattr(r, "id", getattr(r, "buyer_id", None)),
                    "name": getattr(r, "name", None),
                    "email": getattr(r, "email", None),
                    "phone": getattr(r, "phone", None),
                    "address": getattr(r, "address", None),
                    "created_at": getattr(r, "created_at", None),
                })
            if out:
                return out
        except Exception:
            out = []

    t = _reflect_table(db, ["buyers", "buyer"])
    if t is not None:
        try:
            id_col = t.c.get("id") or t.c.get("buyer_id")
            stmt = select(t)
            if id_col is not None:
                stmt = stmt.order_by(id_col.desc())
            rows = db.execute(stmt.offset(skip).limit(limit)).mappings().all()
            return list(rows)
        except Exception:
            pass

    # 원시 SQL 리스트 폴백
    for tbl in ("buyers", "buyer"):
        try:
            sql = text(f"SELECT * FROM {tbl} ORDER BY id DESC LIMIT :limit OFFSET :skip")
            rows = db.execute(sql, {"limit": limit, "skip": skip}).mappings().all()
            if rows:
                return list(rows)
        except Exception:
            continue
    return []

def _fetch_seller_row(db: Session, seller_id: int) -> Optional[Mapping[str, Any]]:
    if SellerModel is not None:
        try:
            pk = getattr(SellerModel, "id", None) or getattr(SellerModel, "seller_id", None)
            if pk is not None:
                row = db.query(SellerModel).filter(pk == seller_id).first()
                if row is not None:
                    return {
                        "id": getattr(row, "id", getattr(row, "seller_id", None)),
                        "name": getattr(row, "name", None),
                        "company_name": getattr(row, "company_name", None),
                        "email": getattr(row, "email", None),
                        "phone": getattr(row, "phone", None),
                        "address": getattr(row, "address", None),
                        "created_at": getattr(row, "created_at", None),
                    }
        except Exception:
            pass

    t = _reflect_table(db, ["sellers", "seller"])
    if t is not None:
        try:
            col = t.c.get("id") or t.c.get("seller_id")
            if col is not None:
                r = db.execute(select(t).where(col == seller_id)).mappings().first()
                if r:
                    return r
        except Exception:
            pass

    for tbl in ("sellers", "seller"):
        for pk in ("id", "seller_id"):
            try:
                sql = text(f"SELECT * FROM {tbl} WHERE {pk} = :sid LIMIT 1")
                r = db.execute(sql, {"sid": seller_id}).mappings().first()
                if r:
                    return r
            except Exception:
                continue
    return None

def _fetch_seller_list(db: Session, skip: int, limit: int) -> List[Mapping[str, Any]]:
    out: List[Mapping[str, Any]] = []

    if SellerModel is not None:
        try:
            id_col = getattr(SellerModel, "id", None) or getattr(SellerModel, "seller_id", None)
            q = db.query(SellerModel)
            if id_col is not None:
                q = q.order_by(id_col.desc())
            rows = q.offset(skip).limit(limit).all()
            for r in rows:
                out.append({
                    "id": getattr(r, "id", getattr(r, "seller_id", None)),
                    "name": getattr(r, "name", None),
                    "company_name": getattr(r, "company_name", None),
                    "email": getattr(r, "email", None),
                    "phone": getattr(r, "phone", None),
                    "address": getattr(r, "address", None),
                    "created_at": getattr(r, "created_at", None),
                })
            if out:
                return out
        except Exception:
            out = []

    t = _reflect_table(db, ["sellers", "seller"])
    if t is not None:
        try:
            id_col = t.c.get("id") or t.c.get("seller_id")
            stmt = select(t)
            if id_col is not None:
                stmt = stmt.order_by(id_col.desc())
            rows = db.execute(stmt.offset(skip).limit(limit)).mappings().all()
            return list(rows)
        except Exception:
            pass

    for tbl in ("sellers", "seller"):
        try:
            sql = text(f"SELECT * FROM {tbl} ORDER BY id DESC LIMIT :limit OFFSET :skip")
            rows = db.execute(sql, {"limit": limit, "skip": skip}).mappings().all()
            if rows:
                return list(rows)
        except Exception:
            continue
    return []


# ---------------- routes (이제 /basic/* 만 사용) ----------------

@router.get("/basic/buyers/{buyer_id}", response_model=BuyerBasicOut)
def get_buyer(
    buyer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    m = _fetch_buyer_row(db, buyer_id)
    if m:
        return _buyer_from_mapping(m)
    return BuyerBasicOut(
        buyer_id=buyer_id,
        name=f"Buyer #{buyer_id}",
        created_at=_now_utc(),
    )


@router.get("/basic/buyers/", response_model=List[BuyerBasicOut])
def list_buyers(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = _fetch_buyer_list(db, skip, limit)
    return [_buyer_from_mapping(r) for r in rows]


@router.get("/basic/sellers/{seller_id}", response_model=SellerBasicOut)
def get_seller(
    seller_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    m = _fetch_seller_row(db, seller_id)
    if m:
        # 기본 프로필 정보
        base = _seller_from_mapping(m)  # SellerBasicOut 인스턴스

        try:
            lvl = compute_seller_level_info(db, seller_id)
            # Pydantic v1/v2 모두 dict() 는 동작
            data = base.dict()
            data.update(
                level=lvl.level,
                fee_percent=lvl.fee_percent,
                rating_adjusted=lvl.rating_adjusted,
                rating_count=lvl.rating_count,
                total_orders=lvl.total_orders,
            )
            return SellerBasicOut(**data)
        except Exception:
            # 리뷰/레벨 계산에 문제가 나도 기본 정보는 그대로 반환
            return base

    # seller row 자체가 없을 때 기본값
    return SellerBasicOut(
        seller_id=seller_id,
        name=f"Seller #{seller_id}",
        created_at=_now_utc(),
    )

@router.get("/basic/sellers/", response_model=List[SellerBasicOut])
def list_sellers(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    rows = _fetch_seller_list(db, skip, limit)
    return [_seller_from_mapping(r) for r in rows]