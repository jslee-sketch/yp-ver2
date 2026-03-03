# app/batch/daily_report.py
"""핑퐁이 일일 리포트 생성 배치."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.database import SessionLocal
from app.models import Deal, Offer, Reservation, SellerReview, SpectatorPrediction


def generate_daily_report() -> dict:
    db = SessionLocal()
    try:
        yesterday = datetime.utcnow() - timedelta(days=1)
        day_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)

        def safe_count(q):
            try:
                return q.count()
            except Exception:
                return 0

        report = {
            "date": yesterday.strftime("%Y-%m-%d"),
            "new_deals": safe_count(db.query(Deal).filter(Deal.created_at.between(day_start, day_end))),
            "new_offers": safe_count(db.query(Offer).filter(Offer.created_at.between(day_start, day_end))),
            "new_reservations": safe_count(db.query(Reservation).filter(Reservation.created_at.between(day_start, day_end))),
            "payments": safe_count(db.query(Reservation).filter(Reservation.paid_at.between(day_start, day_end))),
            "cancellations": safe_count(
                db.query(Reservation).filter(
                    Reservation.status == "CANCELLED",
                    Reservation.cancelled_at.between(day_start, day_end),
                )
            ),
            "new_reviews": safe_count(db.query(SellerReview).filter(SellerReview.created_at.between(day_start, day_end))),
            "spectator_predictions": safe_count(
                db.query(SpectatorPrediction).filter(SpectatorPrediction.created_at.between(day_start, day_end))
            ),
        }

        print(f"[DAILY_REPORT] {report}")
        return report
    finally:
        db.close()


if __name__ == "__main__":
    generate_daily_report()
