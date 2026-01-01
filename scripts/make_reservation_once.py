# scripts/make_reservation_once.py
# -*- coding: utf-8 -*-

import argparse
from typing import Optional

from app.database import SessionLocal
from app import crud, models


def main() -> int:
    ap = argparse.ArgumentParser(description="Create ONE reservation (PENDING) and print the created row.")
    ap.add_argument("--deal_id", type=int, required=True)
    ap.add_argument("--offer_id", type=int, required=True)
    ap.add_argument("--buyer_id", type=int, required=True)
    ap.add_argument("--qty", type=int, required=True)
    ap.add_argument("--hold_minutes", type=int, default=None, help="Optional. Overrides policy default hold window.")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        # 0) 기본 검증(있는지 체크는 crud.create_reservation에서도 하지만, 메시지 선명하게)
        deal = db.get(models.Deal, args.deal_id)
        if deal is None:
            raise RuntimeError(f"Deal not found: deal_id={args.deal_id}")

        offer = db.get(models.Offer, args.offer_id)
        if offer is None:
            raise RuntimeError(f"Offer not found: offer_id={args.offer_id}")

        buyer = db.get(models.Buyer, args.buyer_id)
        if buyer is None:
            raise RuntimeError(f"Buyer not found: buyer_id={args.buyer_id}")

        # 1) 예약 생성 (PENDING)
        resv = crud.create_reservation(
            db,
            deal_id=int(args.deal_id),
            offer_id=int(args.offer_id),
            buyer_id=int(args.buyer_id),
            qty=int(args.qty),
            hold_minutes=args.hold_minutes,
        )

        db.commit()
        db.refresh(resv)

        # 2) 출력
        print("=== CREATED RESERVATION (PENDING) ===")
        print(f"id={resv.id}")
        print(f"status={getattr(resv, 'status', None)}")
        print(f"deal_id={resv.deal_id} offer_id={resv.offer_id} buyer_id={resv.buyer_id} qty={resv.qty}")
        print(f"amount_goods={getattr(resv, 'amount_goods', None)} amount_shipping={getattr(resv, 'amount_shipping', None)} amount_total={getattr(resv, 'amount_total', None)}")
        print(f"created_at={getattr(resv, 'created_at', None)}")
        print(f"expires_at={getattr(resv, 'expires_at', None)}")
        print("=====================================")

        return 0

    except Exception as e:
        db.rollback()
        print(f"[ERR] {type(e).__name__}: {e}")
        return 2

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())