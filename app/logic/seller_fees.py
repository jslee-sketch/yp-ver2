# app/logic/seller_fees.py
from __future__ import annotations
from typing import Dict, Any, Tuple, Optional

from app.config import project_rules as R
from sqlalchemy.orm import Session

try:
    from app import crud  # type: ignore
except Exception:
    crud = None  # type: ignore


def _safe_total_sales(db: Session, seller_id: int) -> int:
    # 다양한 CRUD 이름 시도
    for name in ("get_seller_total_sales", "count_seller_orders", "seller_total_orders"):
        fn = getattr(crud, name, None)
        if callable(fn):
            try:
                v = fn(db, seller_id=seller_id)
            except TypeError:
                v = fn(db, seller_id)
            try:
                return int(v or 0)
            except Exception:
                pass
    return 0


def _safe_rating_adjusted(db: Session, seller_id: int) -> Optional[float]:
    for name in ("get_seller_rating_adjusted", "seller_rating_adjusted", "get_seller_rating"):
        fn = getattr(crud, name, None)
        if callable(fn):
            try:
                v = fn(db, seller_id=seller_id)
            except TypeError:
                v = fn(db, seller_id)
            try:
                return float(v) if v is not None else None
            except Exception:
                pass
    return None


def seller_level_and_fee(db: Session, seller_id: int) -> Dict[str, Any]:
    """
    반환: {
      'level': 'Lv.x',
      'fee_percent': float,
      'total_sales': int,
      'rating_adjusted': Optional[float],
    }
    """
    # 중앙 규칙이 없으면 안전 기본값
    if not getattr(R, "RV", None):
        return {"level": "Lv.6", "fee_percent": 0.035, "total_sales": 0, "rating_adjusted": None}

    total = _safe_total_sales(db, seller_id)
    rating = _safe_rating_adjusted(db, seller_id)

    level, fee = R.RV.seller_level_for(total, rating)  # type: ignore[attr-defined]

    # 안전 클램프(중앙 규칙 상/하한 존재 시)
    floor = getattr(R.RV, "SELLER_FEE_FLOOR", 0.02)
    ceil  = getattr(R.RV, "SELLER_FEE_CEIL",  0.15)
    try:
        fee = max(float(floor), min(float(ceil), float(fee)))
    except Exception:
        fee = float(fee)

    return {"level": level, "fee_percent": float(fee), "total_sales": int(total), "rating_adjusted": rating}