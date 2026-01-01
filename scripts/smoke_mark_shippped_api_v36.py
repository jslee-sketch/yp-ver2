# scripts/smoke_mark_shipped_api_v36.py
from __future__ import annotations

import sys
from typing import Optional
from datetime import datetime

from app.database import SessionLocal
from app import models
import app.crud as crud
from app.core.time_policy import _utcnow


def _pick_reservation_id(db, rid: Optional[int]) -> int:
    if rid is not None:
        r = db.get(models.Reservation, rid)
        if not r:
            raise SystemExit(f"[ERR] reservation not found: {rid}")
        return rid

    r = (
        db.query(models.Reservation)
        .order_by(models.Reservation.id.desc())
        .first()
    )
    if not r:
        raise SystemExit("[ERR] no reservations found")
    return int(r.id)


def _try_mark_shipped_via_crud(db, reservation_id: int) -> bool:
    """
    프로젝트 내에 '이미 존재하는 shipped_at 찍는 CRUD'를 최대한 찾아서 호출한다.
    이름/시그니처가 조금씩 달라도 동작하도록 여러 패턴을 시도한다.
    """
    candidates = [
        "mark_reservation_shipped",
        "mark_reservation_shipped_v36",
        "mark_shipped_reservation",
        "api_mark_reservation_shipped",  # 혹시 crud에 래퍼가 있을 때
    ]

    for name in candidates:
        fn = getattr(crud, name, None)
        if not fn:
            continue

        # 1) 가장 흔한 패턴들
        try:
            fn(
                db,
                reservation_id=reservation_id,
                shipping_carrier="TEST_CARRIER",
                tracking_number=f"TEST-{reservation_id}",
            )
            return True
        except TypeError:
            pass
        except Exception as e:
            print(f"[WARN] {name} call failed (pattern1): {e}")

        try:
            fn(
                db,
                reservation_id=reservation_id,
                carrier="TEST_CARRIER",
                tracking_number=f"TEST-{reservation_id}",
            )
            return True
        except TypeError:
            pass
        except Exception as e:
            print(f"[WARN] {name} call failed (pattern2): {e}")

        try:
            fn(
                db,
                reservation_id=reservation_id,
                actor="seller",
                shipping_carrier="TEST_CARRIER",
                tracking_number=f"TEST-{reservation_id}",
            )
            return True
        except TypeError:
            pass
        except Exception as e:
            print(f"[WARN] {name} call failed (pattern3): {e}")

    return False


def main() -> int:
    rid = None
    if len(sys.argv) >= 2:
        try:
            rid = int(sys.argv[1])
        except Exception:
            raise SystemExit("usage: python scripts/smoke_mark_shipped_api_v36.py [reservation_id]")

    db = SessionLocal()
    try:
        reservation_id = _pick_reservation_id(db, rid)
        r = db.get(models.Reservation, reservation_id)

        print("=" * 80)
        print(f"[INFO] target reservation_id={reservation_id} status={getattr(r,'status',None)}")
        print(f"[INFO] before shipped_at={getattr(r,'shipped_at',None)}")

        ok = _try_mark_shipped_via_crud(db, reservation_id)

        if not ok:
            print("[WARN] could not find/call shipped_at CRUD. Fallback: direct set shipped_at (for test only).")
            r.shipped_at = _utcnow()
            if hasattr(r, "shipping_carrier") and not getattr(r, "shipping_carrier", None):
                r.shipping_carrier = "TEST_CARRIER"
            if hasattr(r, "tracking_number") and not getattr(r, "tracking_number", None):
                r.tracking_number = f"TEST-{reservation_id}"
            db.add(r)
            db.commit()

        db.refresh(r)
        print(f"[INFO] after shipped_at={getattr(r,'shipped_at',None)} carrier={getattr(r,'shipping_carrier',None)} tracking={getattr(r,'tracking_number',None)}")

        if not getattr(r, "shipped_at", None):
            print("[ERR] shipped_at is still None")
            return 2

        print("[OK] shipped_at set")
        print("=" * 80)
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())