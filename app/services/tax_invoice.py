# app/services/tax_invoice.py
"""
세금계산서 생성/발행/확인/취소 로직.
정산 APPROVED 시 자동 생성 → 판매자 확인 → 관리자 발행 파이프라인.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

import yaml
from sqlalchemy.orm import Session

from app import models
from app.models import TaxInvoice, TaxInvoiceStatus

logger = logging.getLogger(__name__)

# ── 공급자(텔러스테크) 정보 로드 ──────────────────────────
_DEFAULTS_PATH = Path(__file__).resolve().parent.parent / "policy" / "params" / "defaults.yaml"
_tax_cfg: dict[str, Any] | None = None


def _get_tax_config() -> dict[str, Any]:
    global _tax_cfg
    if _tax_cfg is None:
        with open(_DEFAULTS_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _tax_cfg = data.get("tax_invoice", {})
    return _tax_cfg


def _supplier_info() -> dict[str, str]:
    cfg = _get_tax_config()
    sup = cfg.get("supplier", {})
    return {
        "supplier_business_name": sup.get("business_name", ""),
        "supplier_business_number": sup.get("business_number", ""),
        "supplier_representative": sup.get("representative", ""),
        "supplier_address": sup.get("address", ""),
        "supplier_email": sup.get("email", ""),
    }


# ── 채번 ─────────────────────────────────────────────────
def generate_invoice_number(db: Session) -> str:
    """YP-YYYYMMDD-NNNNNN 형식 채번."""
    cfg = _get_tax_config()
    prefix = cfg.get("number_prefix", "YP")
    today = datetime.now(timezone.utc).strftime("%Y%m%d")

    # 오늘 날짜 기준 최대 시퀀스 조회
    like_pat = f"{prefix}-{today}-%"
    last = (
        db.query(TaxInvoice.invoice_number)
        .filter(TaxInvoice.invoice_number.like(like_pat))
        .order_by(TaxInvoice.invoice_number.desc())
        .first()
    )
    if last and last[0]:
        seq = int(last[0].split("-")[-1]) + 1
    else:
        seq = 1

    return f"{prefix}-{today}-{seq:06d}"


# ── 세금계산서 생성 ──────────────────────────────────────
def create_tax_invoice(
    db: Session,
    settlement: models.ReservationSettlement,
    recipient: models.Seller | models.Actuator | None = None,
    recipient_type: str = "seller",
) -> TaxInvoice | None:
    """
    정산 APPROVED 시 호출.
    수수료(platform_commission_amount)에 대한 세금계산서 생성.
    """
    fee = getattr(settlement, "platform_commission_amount", 0) or 0
    if fee <= 0:
        logger.info("Settlement %s: 수수료 0 → 세금계산서 생략", settlement.id)
        return None

    # 중복 생성 방지
    existing = (
        db.query(TaxInvoice)
        .filter(TaxInvoice.settlement_id == settlement.id)
        .first()
    )
    if existing:
        logger.info("Settlement %s: 세금계산서 이미 존재 (id=%s)", settlement.id, existing.id)
        return existing

    # 공급받는 자 정보
    if recipient is None:
        sid = getattr(settlement, "seller_id", None)
        if sid:
            recipient = db.query(models.Seller).get(sid)
            recipient_type = "seller"

    cfg = _get_tax_config()
    vat_rate = cfg.get("vat_rate", 0.1)

    total_amount = fee  # VAT 포함 총액
    supply_amount = round(total_amount / (1 + vat_rate))
    tax_amount = total_amount - supply_amount

    sup = _supplier_info()
    inv = TaxInvoice(
        invoice_number=generate_invoice_number(db),
        status=TaxInvoiceStatus.PENDING,
        **sup,
        recipient_type=recipient_type,
        recipient_id=getattr(recipient, "id", 0) if recipient else 0,
        recipient_business_name=getattr(recipient, "business_name", None),
        recipient_business_number=getattr(recipient, "business_number", None),
        recipient_representative=getattr(recipient, "representative_name", None),
        recipient_address=getattr(recipient, "address", None) or getattr(recipient, "business_address", None),
        recipient_email=getattr(recipient, "tax_invoice_email", None) or getattr(recipient, "email", None),
        recipient_business_type=getattr(recipient, "business_type", None),
        recipient_business_item=getattr(recipient, "business_item", None),
        settlement_id=settlement.id,
        total_amount=total_amount,
        supply_amount=supply_amount,
        tax_amount=tax_amount,
    )
    db.add(inv)
    db.flush()
    logger.info("세금계산서 생성: %s (settlement=%s, amount=%s)", inv.invoice_number, settlement.id, total_amount)
    return inv


# ── 판매자 확인 ──────────────────────────────────────────
def confirm_invoice(db: Session, invoice_id: int, recipient_id: int) -> TaxInvoice:
    inv = db.query(TaxInvoice).get(invoice_id)
    if not inv:
        raise ValueError("세금계산서를 찾을 수 없습니다.")
    if inv.recipient_id != recipient_id:
        raise PermissionError("본인의 세금계산서만 확인할 수 있습니다.")
    if inv.status != TaxInvoiceStatus.PENDING:
        raise ValueError(f"PENDING 상태만 확인 가능합니다. (현재: {inv.status})")

    inv.status = TaxInvoiceStatus.CONFIRMED
    inv.confirmed_at = datetime.now(timezone.utc)
    db.add(inv)
    db.flush()
    return inv


# ── 관리자 발행 (단건/일괄) ──────────────────────────────
def issue_invoices(db: Session, invoice_ids: list[int]) -> list[TaxInvoice]:
    now = datetime.now(timezone.utc)
    issued = []
    for iid in invoice_ids:
        inv = db.query(TaxInvoice).get(iid)
        if not inv:
            continue
        if inv.status not in (TaxInvoiceStatus.PENDING, TaxInvoiceStatus.CONFIRMED):
            continue
        inv.status = TaxInvoiceStatus.ISSUED
        inv.issued_at = now
        db.add(inv)
        issued.append(inv)
    db.flush()
    return issued


# ── 취소 ─────────────────────────────────────────────────
def cancel_invoice(db: Session, invoice_id: int) -> TaxInvoice:
    inv = db.query(TaxInvoice).get(invoice_id)
    if not inv:
        raise ValueError("세금계산서를 찾을 수 없습니다.")
    if inv.status == TaxInvoiceStatus.CANCELLED:
        return inv
    inv.status = TaxInvoiceStatus.CANCELLED
    inv.cancelled_at = datetime.now(timezone.utc)
    db.add(inv)
    db.flush()
    return inv


# ── ECOUNT XLSX 내보내기 ─────────────────────────────────
def export_ecount_xlsx(db: Session, invoice_ids: list[int]) -> bytes:
    """ECOUNT 호환 엑셀 파일 생성."""
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl 패키지가 필요합니다.")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "세금계산서"

    headers = [
        "세금계산서번호", "작성일", "상태",
        "공급자(상호)", "공급자(사업자번호)", "공급자(대표자)",
        "공급받는자(상호)", "공급받는자(사업자번호)", "공급받는자(대표자)",
        "공급가액", "세액", "합계", "비고",
    ]
    ws.append(headers)

    invoices = (
        db.query(TaxInvoice)
        .filter(TaxInvoice.id.in_(invoice_ids))
        .order_by(TaxInvoice.created_at)
        .all()
    )

    for inv in invoices:
        ws.append([
            inv.invoice_number,
            inv.created_at.strftime("%Y-%m-%d") if inv.created_at else "",
            inv.status.value if inv.status else "",
            inv.supplier_business_name,
            inv.supplier_business_number,
            inv.supplier_representative,
            inv.recipient_business_name or "",
            inv.recipient_business_number or "",
            inv.recipient_representative or "",
            inv.supply_amount,
            inv.tax_amount,
            inv.total_amount,
            inv.notes or "",
        ])

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
