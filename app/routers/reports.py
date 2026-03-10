# app/routers/reports.py
"""
POST /reports              — 신고 접수
GET  /reports/my           — 내 신고 목록
GET  /admin/reports        — 전체 신고 (관리자)
POST /admin/reports/{id}/resolve — 신고 처리
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import Report

router = APIRouter(tags=["reports"])

_VALID_REPORTER_TYPES = {"buyer", "seller", "actuator"}
_VALID_TARGET_TYPES = {"deal", "offer", "seller", "buyer", "reservation"}
_VALID_CATEGORIES = {"fraud", "abuse", "defective", "not_delivered", "other"}


class ReportCreate(BaseModel):
    reporter_id: int
    reporter_type: str
    target_type: str
    target_id: int
    category: str
    description: Optional[str] = None


class ReportOut(BaseModel):
    id: int
    reporter_id: int
    reporter_type: str
    target_type: str
    target_id: int
    category: str
    description: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResolveRequest(BaseModel):
    resolution: str
    action_taken: Optional[str] = None


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("/reports", response_model=ReportOut, status_code=201)
def create_report(body: ReportCreate, db: Session = Depends(get_db)):
    if body.reporter_type not in _VALID_REPORTER_TYPES:
        raise HTTPException(400, f"reporter_type must be one of {_VALID_REPORTER_TYPES}")
    if body.target_type not in _VALID_TARGET_TYPES:
        raise HTTPException(400, f"target_type must be one of {_VALID_TARGET_TYPES}")
    if body.category not in _VALID_CATEGORIES:
        raise HTTPException(400, f"category must be one of {_VALID_CATEGORIES}")
    if body.description and len(body.description) > 1000:
        raise HTTPException(400, "description은 최대 1000자")

    report = Report(
        reporter_id=body.reporter_id,
        reporter_type=body.reporter_type,
        target_type=body.target_type,
        target_id=body.target_id,
        category=body.category,
        description=body.description,
        status="OPEN",
        created_at=_utcnow(),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("/reports/my", response_model=List[ReportOut])
def my_reports(
    reporter_id: int = Query(...),
    reporter_type: str = Query(...),
    db: Session = Depends(get_db),
):
    return (
        db.query(Report)
        .filter(Report.reporter_id == reporter_id, Report.reporter_type == reporter_type)
        .order_by(Report.created_at.desc())
        .all()
    )


@router.get("/admin/reports", response_model=List[ReportOut])
def admin_reports(
    status: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Report)
    if status:
        q = q.filter(Report.status == status)
    if date_from:
        try:
            q = q.filter(Report.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(Report.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass
    return q.order_by(Report.created_at.desc()).limit(200).all()


@router.post("/admin/reports/{report_id}/resolve")
def resolve_report(
    report_id: int,
    body: ResolveRequest,
    db: Session = Depends(get_db),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "신고를 찾을 수 없습니다")
    report.status = "RESOLVED"
    report.resolution = body.resolution
    report.action_taken = body.action_taken
    report.resolved_at = _utcnow()
    db.commit()
    return {"id": report_id, "status": "RESOLVED"}
