# app/batch/review_request.py
"""리뷰 요청 자동 알림 배치."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from app.database import SessionLocal
from app.models import Reservation, SellerReview, UserNotification

REVIEW_REQUEST_DAYS = 3


def send_review_requests() -> dict:
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=REVIEW_REQUEST_DAYS)
        targets = (
            db.query(Reservation)
            .filter(
                Reservation.arrival_confirmed_at.isnot(None),
                Reservation.arrival_confirmed_at < cutoff,
                Reservation.status == "PAID",
            )
            .all()
        )

        sent = 0
        for resv in targets:
            existing_review = db.query(SellerReview).filter(
                SellerReview.reservation_id == resv.id
            ).first() if hasattr(SellerReview, "reservation_id") else None

            if existing_review:
                continue

            already = db.query(UserNotification).filter(
                UserNotification.user_id == resv.buyer_id,
                UserNotification.type == "review_request",
                UserNotification.meta_json.contains(str(resv.id)),
            ).first()
            if already:
                continue

            try:
                from app.routers.notifications import create_notification
                create_notification(
                    db,
                    user_id=resv.buyer_id,
                    type="review_request",
                    title="상품은 만족스러우셨나요?",
                    message=f"예약 #{resv.id} 상품 리뷰를 남겨주세요!",
                    meta={"reservation_id": resv.id, "deal_id": resv.deal_id},
                )
                sent += 1
            except Exception as e:
                print(f"[REVIEW_REQUEST] Error resv#{resv.id}: {e}")

        db.commit()
        print(f"[REVIEW_REQUEST] {sent} sent")
        return {"sent": sent}
    finally:
        db.close()


if __name__ == "__main__":
    send_review_requests()
