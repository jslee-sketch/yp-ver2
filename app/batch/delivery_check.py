# app/batch/delivery_check.py
"""배송완료 자동감지 배치. python -m app.batch.delivery_check"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import Reservation
from app.services.delivery_tracker import track_delivery, DeliveryStatus


async def check_deliveries() -> dict:
    db = SessionLocal()
    try:
        pending = (
            db.query(Reservation)
            .filter(
                Reservation.shipped_at.isnot(None),
                Reservation.delivered_at.is_(None),
                Reservation.status == "PAID",
                Reservation.shipping_carrier.isnot(None),
                Reservation.tracking_number.isnot(None),
            )
            .all()
        )

        results = {"checked": 0, "delivered": 0, "errors": 0}

        for resv in pending:
            results["checked"] += 1
            try:
                result = await track_delivery(
                    carrier_name=resv.shipping_carrier,
                    tracking_number=resv.tracking_number,
                )
                if result.status == DeliveryStatus.DELIVERED:
                    resv.delivered_at = datetime.now(timezone.utc)
                    setattr(resv, "delivery_auto_confirmed", True)
                    setattr(resv, "delivery_confirmed_source", "batch_auto")
                    results["delivered"] += 1
            except Exception as e:
                results["errors"] += 1
                print(f"[DELIVERY_CHECK] Error resv#{resv.id}: {e}")

        db.commit()
        print(f"[DELIVERY_CHECK] {results}")
        return results
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(check_deliveries())
