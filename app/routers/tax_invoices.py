# app/routers/tax_invoices.py
"""세금계산서 관리 API — 생성/확인/발행/목록/ECOUNT 내보내기."""
from __future__ import annotations

from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from io import BytesIO

from app.database import get_db
from app import models
from app.models import TaxInvoice, TaxInvoiceStatus
from app.services.tax_invoice import (
    create_tax_invoice,
    confirm_invoice,
    issue_invoices,
    cancel_invoice,
    export_ecount_xlsx,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v3_6/tax-invoices", tags=["tax-invoices"])


# ── Schemas ──────────────────────────────────────────────
class TaxInvoiceOut(BaseModel):
    id: int
    invoice_number: str
    status: str
    supplier_business_name: str
    supplier_business_number: str
    supplier_representative: str
    supplier_address: str
    supplier_email: Optional[str] = None
    recipient_type: str
    recipient_id: int
    recipient_business_name: Optional[str] = None
    recipient_business_number: Optional[str] = None
    recipient_representative: Optional[str] = None
    recipient_address: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_business_type: Optional[str] = None
    recipient_business_item: Optional[str] = None
    settlement_id: int
    total_amount: int
    supply_amount: int
    tax_amount: int
    issued_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class GenerateRequest(BaseModel):
    settlement_id: int


class BatchIssueRequest(BaseModel):
    invoice_ids: List[int]


class ExportRequest(BaseModel):
    invoice_ids: List[int]


def _to_out(inv: TaxInvoice) -> dict:
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
        "supplier_business_name": inv.supplier_business_name,
        "supplier_business_number": inv.supplier_business_number,
        "supplier_representative": inv.supplier_representative,
        "supplier_address": inv.supplier_address,
        "supplier_email": inv.supplier_email,
        "recipient_type": inv.recipient_type,
        "recipient_id": inv.recipient_id,
        "recipient_business_name": inv.recipient_business_name,
        "recipient_business_number": inv.recipient_business_number,
        "recipient_representative": inv.recipient_representative,
        "recipient_address": inv.recipient_address,
        "recipient_email": inv.recipient_email,
        "recipient_business_type": inv.recipient_business_type,
        "recipient_business_item": inv.recipient_business_item,
        "settlement_id": inv.settlement_id,
        "total_amount": inv.total_amount,
        "supply_amount": inv.supply_amount,
        "tax_amount": inv.tax_amount,
        "issued_at": inv.issued_at,
        "confirmed_at": inv.confirmed_at,
        "cancelled_at": inv.cancelled_at,
        "created_at": inv.created_at,
        "notes": inv.notes,
    }


# ── 1) 수동 생성 (admin) ────────────────────────────────
@router.post("/generate", summary="[ADMIN] 세금계산서 수동 생성")
def generate_tax_invoice(body: GenerateRequest, db: Session = Depends(get_db)):
    settlement = db.query(models.ReservationSettlement).get(body.settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    inv = create_tax_invoice(db, settlement)
    if inv is None:
        raise HTTPException(status_code=400, detail="수수료가 0이거나 이미 생성된 세금계산서가 있습니다.")
    db.commit()
    return {"ok": True, "invoice": _to_out(inv)}


# ── 2) 판매자 확인 ──────────────────────────────────────
@router.post("/{invoice_id}/confirm", summary="판매자 세금계산서 확인")
def confirm_tax_invoice(
    invoice_id: int = Path(..., ge=1),
    seller_id: int = Query(..., description="판매자 ID"),
    db: Session = Depends(get_db),
):
    try:
        inv = confirm_invoice(db, invoice_id, seller_id)
        db.commit()
        return {"ok": True, "invoice": _to_out(inv)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ── 3) 단건 발행 (admin) ────────────────────────────────
@router.post("/{invoice_id}/issue", summary="[ADMIN] 세금계산서 단건 발행")
def issue_single(invoice_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    issued = issue_invoices(db, [invoice_id])
    if not issued:
        raise HTTPException(status_code=400, detail="발행 가능한 세금계산서가 없습니다.")
    db.commit()
    return {"ok": True, "invoice": _to_out(issued[0])}


# ── 4) 일괄 발행 (admin) ────────────────────────────────
@router.post("/batch-issue", summary="[ADMIN] 세금계산서 일괄 발행")
def batch_issue(body: BatchIssueRequest, db: Session = Depends(get_db)):
    issued = issue_invoices(db, body.invoice_ids)
    db.commit()
    return {"ok": True, "count": len(issued), "invoices": [_to_out(i) for i in issued]}


# ── 5) 관리자 목록 ──────────────────────────────────────
@router.get("", summary="[ADMIN] 세금계산서 목록")
def list_invoices(
    status: Optional[str] = Query(None),
    seller_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(TaxInvoice)
    if status:
        q = q.filter(TaxInvoice.status == status)
    if seller_id:
        q = q.filter(TaxInvoice.recipient_type == "seller", TaxInvoice.recipient_id == seller_id)
    if date_from:
        q = q.filter(TaxInvoice.created_at >= date_from)
    if date_to:
        q = q.filter(TaxInvoice.created_at <= date_to)

    total = q.count()
    rows = q.order_by(TaxInvoice.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_to_out(r) for r in rows]}


# ── 6) 판매자 본인 목록 ─────────────────────────────────
@router.get("/seller/me", summary="판매자 본인 세금계산서 목록")
def my_invoices(
    seller_id: int = Query(..., description="판매자 ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = (
        db.query(TaxInvoice)
        .filter(TaxInvoice.recipient_type == "seller", TaxInvoice.recipient_id == seller_id)
    )
    total = q.count()
    rows = q.order_by(TaxInvoice.created_at.desc()).offset(skip).limit(limit).all()
    return {"total": total, "items": [_to_out(r) for r in rows]}


# ── 7) ECOUNT XLSX 내보내기 ──────────────────────────────
@router.get("/export-ecount", summary="[ADMIN] ECOUNT 엑셀 내보내기")
def export_ecount(
    invoice_ids: str = Query(..., description="콤마 구분 invoice ID 목록"),
    db: Session = Depends(get_db),
):
    ids = [int(x.strip()) for x in invoice_ids.split(",") if x.strip().isdigit()]
    if not ids:
        raise HTTPException(status_code=400, detail="invoice_ids가 비어있습니다.")

    try:
        xlsx_bytes = export_ecount_xlsx(db, ids)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=tax_invoices_ecount.xlsx"},
    )


# ── 8) 취소 (admin) ─────────────────────────────────────
@router.post("/{invoice_id}/cancel", summary="[ADMIN] 세금계산서 취소")
def cancel_tax_invoice(invoice_id: int = Path(..., ge=1), db: Session = Depends(get_db)):
    try:
        inv = cancel_invoice(db, invoice_id)
        db.commit()
        return {"ok": True, "invoice": _to_out(inv)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
