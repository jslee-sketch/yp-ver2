# app/services/anomaly_detector.py
"""이상 거래 감지 서비스."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session


@dataclass
class AnomalyAlert:
    type: str
    severity: str   # low/medium/high/critical
    entity_type: str
    entity_id: int
    description: str
    evidence: dict = field(default_factory=dict)
    detected_at: datetime = field(default_factory=datetime.utcnow)


def detect_anomalies(db: Session, lookback_hours: int = 24) -> List[AnomalyAlert]:
    """최근 N시간 데이터를 분석하여 이상 패턴 반환."""
    from app.models import Reservation, Buyer
    alerts: List[AnomalyAlert] = []
    since = datetime.utcnow() - timedelta(hours=lookback_hours)

    # 1. 높은 환불률 buyer 탐지
    try:
        from sqlalchemy import func
        paid_counts = (
            db.query(Reservation.buyer_id, func.count().label("cnt"))
            .filter(Reservation.paid_at.isnot(None), Reservation.paid_at >= since)
            .group_by(Reservation.buyer_id)
            .all()
        )
        cancelled_counts = (
            db.query(Reservation.buyer_id, func.count().label("cnt"))
            .filter(Reservation.cancelled_at.isnot(None), Reservation.cancelled_at >= since)
            .group_by(Reservation.buyer_id)
            .all()
        )
        paid_map = {r.buyer_id: r.cnt for r in paid_counts}
        cancelled_map = {r.buyer_id: r.cnt for r in cancelled_counts}

        for buyer_id, cancelled in cancelled_map.items():
            paid = paid_map.get(buyer_id, 0)
            total = paid + cancelled
            if total >= 3 and cancelled / total >= 0.5:
                alerts.append(AnomalyAlert(
                    type="high_refund_rate",
                    severity="medium",
                    entity_type="buyer",
                    entity_id=buyer_id,
                    description=f"환불률 {cancelled / total * 100:.0f}% ({cancelled}/{total})",
                    evidence={"paid": paid, "cancelled": cancelled, "rate": round(cancelled / total, 2)},
                ))
    except Exception as e:
        print(f"[ANOMALY] refund rate check error: {e}")

    # 2. 대량 예약 탐지 (단시간 5건 이상)
    try:
        from sqlalchemy import func
        bulk = (
            db.query(Reservation.buyer_id, func.count().label("cnt"))
            .filter(Reservation.created_at >= since)
            .group_by(Reservation.buyer_id)
            .having(func.count() >= 5)
            .all()
        )
        for row in bulk:
            alerts.append(AnomalyAlert(
                type="bulk_reservation",
                severity="low",
                entity_type="buyer",
                entity_id=row.buyer_id,
                description=f"{lookback_hours}시간 내 {row.cnt}건 예약",
                evidence={"count": row.cnt, "lookback_hours": lookback_hours},
            ))
    except Exception as e:
        print(f"[ANOMALY] bulk reservation check error: {e}")

    return alerts
