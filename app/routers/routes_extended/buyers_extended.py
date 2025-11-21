# app/routers/routes_extended/buyers_extended.py
from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.security import get_current_user
from app import models

# 신뢰티어/포인트 등급 로직
try:
    from app.logic.trust import buyer_trust_tier_and_deposit_percent, buyer_points_grade
except Exception:
    def buyer_trust_tier_and_deposit_percent(db: Session, buyer_id: int) -> Dict[str, Any]:
        return {
            "buyer_id": buyer_id,
            "tier": "T4",
            "deposit_percent": 0.10,
            "participations": 0,
            "fulfillments": 0,
            "fulfillment_rate": 0.0,
            "restricted": False,
        }
    def buyer_points_grade(balance: int) -> str:
        if balance >= 500: return "PLATINUM"
        if balance >= 201: return "GOLD"
        if balance >= 51:  return "SILVER"
        return "BRONZE"

router = APIRouter(prefix="/buyers", tags=["buyers-extended"])

# ─────────────────────────────────────────────────────────
# 내부 유틸: 포인트 합계 (ORM 없어도 RAW SQL로 자동 탐색)
# ─────────────────────────────────────────────────────────
def _list_tables_sqlite(db: Session) -> List[str]:
    try:
        rows = db.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
        return [r[0] for r in rows]
    except SQLAlchemyError:
        return []

def _table_has_columns_sqlite(db: Session, table: str, *cols: str) -> bool:
    try:
        info = db.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
        colnames = {row[1] for row in info}  # cid, name, type, notnull, dflt, pk
        return all(c in colnames for c in cols)
    except SQLAlchemyError:
        return False

def _points_balance(db: Session, buyer_id: int) -> int:
    """
    다음 순서로 합계 탐색:
      1) 흔한 후보명 우선 스캔
      2) 전체 테이블 스캔(컬럼 시그니처 매칭: (user_id or buyer_id), amount [, user_type])
    합계가 처음으로 non-zero가 되는 테이블을 채택.
    """
    # 1) 흔한 후보명
    candidate_tables = [
        "points_ledger", "points_ledgers",
        "points_transaction", "points_transactions",
        "points_log", "points_logs",
        "points_entry", "points_entries",
        "points",
    ]
    # 2) 실제 DB의 테이블들
    all_tables = _list_tables_sqlite(db)
    scan_order = candidate_tables + [t for t in all_tables if t not in candidate_tables]

    # user_type 컬럼 유무 모두 처리
    def _sum_with_clause(table: str, where_has_type: bool) -> int:
        try:
            if where_has_type and _table_has_columns_sqlite(db, table, "user_type", "user_id", "amount"):
                row = db.execute(
                    text(f"""
                        SELECT COALESCE(SUM(amount), 0) AS total
                        FROM {table}
                        WHERE user_id = :uid AND (user_type = 'buyer' OR user_type = 'BUYER')
                    """),
                    {"uid": buyer_id},
                ).fetchone()
                return int(row[0] or 0) if row else 0

            # user_id + amount (user_type 없음)
            if _table_has_columns_sqlite(db, table, "user_id", "amount"):
                row = db.execute(
                    text(f"SELECT COALESCE(SUM(amount), 0) FROM {table} WHERE user_id = :uid"),
                    {"uid": buyer_id},
                ).fetchone()
                if row and (row[0] or 0) != 0:
                    return int(row[0] or 0)

            # buyer_id + amount (스키마 변형)
            if _table_has_columns_sqlite(db, table, "buyer_id", "amount"):
                row = db.execute(
                    text(f"SELECT COALESCE(SUM(amount), 0) FROM {table} WHERE buyer_id = :uid"),
                    {"uid": buyer_id},
                ).fetchone()
                return int(row[0] or 0) if row else 0
        except SQLAlchemyError:
            return 0
        return 0

    # 스캔: user_type 있는 케이스 → 없는 케이스 → buyer_id 케이스
    for t in scan_order:
        val = _sum_with_clause(t, where_has_type=True)
        if val != 0:
            return val
        val = _sum_with_clause(t, where_has_type=False)
        if val != 0:
            return val

    return 0

def _require_buyer(user: Any) -> None:
    # 권한 체크가 필요하면 여기에서 403을 던지도록 수정
    return

# ─────────────────────────────────────────────────────────
# 엔드포인트
# ─────────────────────────────────────────────────────────
@router.get("/summary", summary="내 요약(예약/포인트/티어)")
def get_buyer_summary(
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    _require_buyer(current_user)
    buyer_id = getattr(current_user, "id", None)
    if not buyer_id:
        raise HTTPException(status_code=401, detail="invalid user")

    reservations = (
        db.query(models.Reservation)
          .filter(models.Reservation.buyer_id == buyer_id)
          .order_by(desc(models.Reservation.id))
          .limit(20)
          .all()
    )

    balance = _points_balance(db, buyer_id)
    grade = buyer_points_grade(balance)
    trust = buyer_trust_tier_and_deposit_percent(db, buyer_id)

    def _s(r: models.Reservation) -> Dict[str, Any]:
        return {
            "id": r.id,
            "deal_id": r.deal_id,
            "offer_id": r.offer_id,
            "qty": r.qty,
            "status": getattr(r.status, "name", str(r.status)),
            "created_at": r.created_at,
            "paid_at": r.paid_at,
            "cancelled_at": r.cancelled_at,
            "expired_at": r.expired_at,
        }

    return {
        "buyer": {"id": buyer_id, "email": getattr(current_user, "email", None)},
        "points": {"balance": balance, "grade": grade},
        "trust": trust,
        "reservations": [_s(x) for x in reservations],
    }

@router.get("/{buyer_id}/trust_tier", summary="구매자 신뢰 티어 및 Deposit 비율(미이행 제한 포함)")
def api_buyer_trust_tier(
    buyer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    return buyer_trust_tier_and_deposit_percent(db, buyer_id)

@router.get("/{buyer_id}/points_grade", summary="구매자 포인트 등급(표시용)")
def api_buyer_points_grade(
    buyer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    bal = _points_balance(db, buyer_id)
    grade = buyer_points_grade(bal)
    return {"buyer_id": buyer_id, "balance": bal, "grade": grade}

@router.get("/{buyer_id}/points_balance", summary="구매자 포인트 잔액(숫자)")
def api_buyer_points_balance(
    buyer_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    return {"buyer_id": buyer_id, "balance": _points_balance(db, buyer_id)}