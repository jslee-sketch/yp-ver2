# app/routers/customer_inquiries.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Path, Body, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import CustomerInquiry
from app.database import get_db

router = APIRouter(prefix="/customer-inquiries", tags=["Customer Inquiries"])


# ── Schemas ──────────────────────────────────────────────
class InquiryCreate(BaseModel):
    seller_id: int
    buyer_id: int
    reservation_id: Optional[int] = None
    category: str = "general"
    title: str = Field(..., max_length=200)
    content: str


class InquiryReply(BaseModel):
    comment: str


class InquiryOut(BaseModel):
    id: int
    seller_id: int
    buyer_id: int
    reservation_id: Optional[int] = None
    category: str
    title: str
    content: str
    status: str
    seller_reply: Optional[str] = None
    replied_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────
@router.post("/", response_model=InquiryOut, status_code=201)
def create_inquiry(body: InquiryCreate, db: Session = Depends(get_db)):
    inq = CustomerInquiry(
        seller_id=body.seller_id,
        buyer_id=body.buyer_id,
        reservation_id=body.reservation_id,
        category=body.category,
        title=body.title,
        content=body.content,
    )
    db.add(inq)
    db.commit()
    db.refresh(inq)
    return inq


@router.get("/seller/{seller_id}", response_model=List[InquiryOut])
def list_seller_inquiries(
    seller_id: int = Path(..., ge=1),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(CustomerInquiry).filter(CustomerInquiry.seller_id == seller_id)
    if status:
        q = q.filter(CustomerInquiry.status == status)
    return q.order_by(CustomerInquiry.id.desc()).all()


@router.post("/{inquiry_id}/reply", response_model=InquiryOut)
def reply_inquiry(
    inquiry_id: int = Path(..., ge=1),
    body: InquiryReply = Body(...),
    db: Session = Depends(get_db),
):
    inq = db.query(CustomerInquiry).filter(CustomerInquiry.id == inquiry_id).first()
    if not inq:
        raise HTTPException(404, "inquiry not found")
    inq.seller_reply = body.comment
    inq.replied_at = datetime.now(timezone.utc)
    inq.status = "answered"
    db.commit()
    db.refresh(inq)
    return inq


@router.patch("/{inquiry_id}/close", response_model=InquiryOut)
def close_inquiry(
    inquiry_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
):
    inq = db.query(CustomerInquiry).filter(CustomerInquiry.id == inquiry_id).first()
    if not inq:
        raise HTTPException(404, "inquiry not found")
    inq.status = "closed"
    db.commit()
    db.refresh(inq)
    return inq
