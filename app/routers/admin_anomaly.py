# app/routers/admin_anomaly.py
"""
GET /admin/anomaly/detect  — 이상 감지
"""
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.services.anomaly_detector import detect_anomalies, AnomalyAlert

router = APIRouter(prefix="/admin/anomaly", tags=["admin-anomaly"])


class AnomalyOut(BaseModel):
    type: str
    severity: str
    entity_type: str
    entity_id: int
    description: str
    evidence: dict
    detected_at: datetime


@router.get("/detect", response_model=List[AnomalyOut])
def detect(
    lookback_hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
):
    alerts = detect_anomalies(db, lookback_hours=lookback_hours)
    return [
        AnomalyOut(
            type=a.type,
            severity=a.severity,
            entity_type=a.entity_type,
            entity_id=a.entity_id,
            description=a.description,
            evidence=a.evidence,
            detected_at=a.detected_at,
        )
        for a in alerts
    ]
