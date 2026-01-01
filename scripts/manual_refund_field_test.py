# scripts/manual_refund_field_test.py

import sys
import pathlib

# 🔹 1) 프로젝트 루트(yp-ver2)를 sys.path에 추가
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import SessionLocal, DATABASE_URL
from app.models import Reservation


RESV_ID = 86  # 테스트할 예약 id


def main():
    print("DATABASE_URL =", DATABASE_URL)

    db = SessionLocal()
    try:
        # 1) 먼저 현재 값 읽기
        resv = db.get(Reservation, RESV_ID)
        if not resv:
            print(f"Reservation {RESV_ID} not found")
            return

        print(
            f"[BEFORE] id={resv.id}, "
            f"refunded_qty={getattr(resv, 'refunded_qty', None)}, "
            f"refunded_amount_total={getattr(resv, 'refunded_amount_total', None)}"
        )

        # 2) 값 변경해보기
        resv.refunded_qty = 5
        resv.refunded_amount_total = 555555

        db.add(resv)
        db.commit()
        db.refresh(resv)

        print(
            f"[AFTER ] id={resv.id}, "
            f"refunded_qty={getattr(resv, 'refunded_qty', None)}, "
            f"refunded_amount_total={getattr(resv, 'refunded_amount_total', None)}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()