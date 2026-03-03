# app/batch/auto_arrival_confirm.py
"""도착확인 자동처리 배치. python -m app.batch.auto_arrival_confirm"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from app.database import SessionLocal
from app.models import Reservation

AUTO_CONFIRM_DAYS = 7


def auto_confirm_arrivals() -> dict:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=AUTO_CONFIRM_DAYS)
        targets = (
            db.query(Reservation)
            .filter(
                Reservation.delivered_at.isnot(None),
                Reservation.arrival_confirmed_at.is_(None),
                Reservation.delivered_at < cutoff,
                Reservation.status == "PAID",
            )
            .all()
        )

        confirmed = 0
        for resv in targets:
            try:
                resv.arrival_confirmed_at = datetime.now(timezone.utc)
                setattr(resv, "delivery_confirmed_source", "auto_confirm")
                try:
                    from app.routers.notifications import create_notification
                    create_notification(
                        db,
                        user_id=resv.buyer_id,
                        type="auto_arrival_confirmed",
                        title=f"예약 #{resv.id} 자동 도착확인 처리",
                        message=f"배송완료 후 {AUTO_CONFIRM_DAYS}일 경과하여 자동 도착확인 처리되었습니다.",
                        meta={"reservation_id": resv.id},
                    )
                except Exception:
                    pass
                confirmed += 1
            except Exception as e:
                print(f"[AUTO_ARRIVAL] Error resv#{resv.id}: {e}")

        db.commit()
        print(f"[AUTO_ARRIVAL] {confirmed}/{len(targets)} confirmed")
        return {"confirmed": confirmed, "total": len(targets)}
    finally:
        db.close()


if __name__ == "__main__":
    auto_confirm_arrivals()
