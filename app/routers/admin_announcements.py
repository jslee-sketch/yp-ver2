# app/routers/admin_announcements.py
"""Announcements CRUD for admin + public read"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import get_db
from app import models

router = APIRouter(tags=["announcements"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Admin CRUD ───────────────────────────────────────────

@router.get("/admin/announcements")
def admin_list_announcements(
    category: Optional[str] = None,
    is_published: Optional[bool] = None,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(models.Announcement)
    if category:
        q = q.filter(models.Announcement.category == category)
    if is_published is not None:
        q = q.filter(models.Announcement.is_published == is_published)
    items = q.order_by(models.Announcement.id.desc()).limit(limit).all()
    result = []
    for a in items:
        result.append({
            "id": a.id,
            "title": a.title,
            "content": a.content,
            "category": a.category,
            "is_pinned": a.is_pinned,
            "is_published": a.is_published,
            "target_role": a.target_role,
            "author": a.author,
            "created_at": str(a.created_at) if a.created_at else None,
            "updated_at": str(a.updated_at) if a.updated_at else None,
        })
    total = db.query(sa_func.count(models.Announcement.id)).scalar() or 0
    return {"items": result, "total": total}


@router.post("/admin/announcements", status_code=201)
def admin_create_announcement(payload: dict, db: Session = Depends(get_db)):
    a = models.Announcement(
        title=payload.get("title", ""),
        content=payload.get("content", ""),
        category=payload.get("category", "general"),
        is_pinned=payload.get("is_pinned", False),
        is_published=payload.get("is_published", False),
        target_role=payload.get("target_role", "all"),
        author=payload.get("author", "admin"),
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "title": a.title}


@router.put("/admin/announcements/{ann_id}")
def admin_update_announcement(ann_id: int, payload: dict, db: Session = Depends(get_db)):
    a = db.query(models.Announcement).filter(models.Announcement.id == ann_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")
    for field in ("title", "content", "category", "is_pinned", "is_published", "target_role"):
        if field in payload:
            setattr(a, field, payload[field])
    a.updated_at = _utcnow()
    db.commit()
    return {"ok": True, "id": a.id}


@router.delete("/admin/announcements/{ann_id}")
def admin_delete_announcement(ann_id: int, db: Session = Depends(get_db)):
    a = db.query(models.Announcement).filter(models.Announcement.id == ann_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Announcement not found")
    a.is_published = False
    a.updated_at = _utcnow()
    db.commit()
    return {"ok": True, "id": a.id}


# ── Public read ──────────────────────────────────────────

@router.get("/announcements")
def public_list_announcements(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    items = (
        db.query(models.Announcement)
        .filter(models.Announcement.is_published == True)
        .order_by(models.Announcement.is_pinned.desc(), models.Announcement.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "title": a.title,
            "content": a.content,
            "category": a.category,
            "is_pinned": a.is_pinned,
            "target_role": a.target_role,
            "created_at": str(a.created_at) if a.created_at else None,
        }
        for a in items
    ]
