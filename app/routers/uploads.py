# app/routers/uploads.py
"""
POST /uploads/image           — 이미지 업로드
GET  /uploads/{type}/{id}     — 이미지 목록
DELETE /uploads/{file_id}     — 삭제
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import UploadedFile

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOAD_ROOT = Path("uploads")
MAX_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class FileOut(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    filename: str
    filepath: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.post("/image", response_model=FileOut, status_code=201)
async def upload_image(
    entity_type: str = Form(...),
    entity_id: int = Form(...),
    uploaded_by_id: Optional[int] = Form(None),
    uploaded_by_type: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"허용 확장자: {ALLOWED_EXT}")

    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(400, f"최대 파일 크기: 5MB")

    ts = int(time.time())
    safe_name = f"{entity_type}_{entity_id}_{ts}{ext}"
    dir_path = UPLOAD_ROOT / entity_type
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / safe_name

    with open(file_path, "wb") as f:
        f.write(content)

    rel_path = f"/uploads/{entity_type}/{safe_name}"
    record = UploadedFile(
        entity_type=entity_type,
        entity_id=entity_id,
        filename=safe_name,
        filepath=rel_path,
        file_size=len(content),
        mime_type=file.content_type,
        uploaded_by_id=uploaded_by_id,
        uploaded_by_type=uploaded_by_type,
        created_at=_utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{entity_type}/{entity_id}", response_model=List[FileOut])
def list_files(entity_type: str, entity_id: int, db: Session = Depends(get_db)):
    return (
        db.query(UploadedFile)
        .filter(UploadedFile.entity_type == entity_type, UploadedFile.entity_id == entity_id)
        .order_by(UploadedFile.created_at.desc())
        .all()
    )


@router.delete("/{file_id}")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    rec = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not rec:
        raise HTTPException(404, "파일을 찾을 수 없습니다")
    # 실제 파일 삭제
    fp = Path(rec.filepath.lstrip("/"))
    if fp.exists():
        fp.unlink()
    db.delete(rec)
    db.commit()
    return {"deleted": file_id}
