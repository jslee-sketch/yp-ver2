# app/services/ecount_service.py
"""ECOUNT ERP 연동 서비스 (현재: 엑셀, 추후: API)"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)


class EcountService:
    def __init__(self):
        self.api_key = os.environ.get("ECOUNT_API_KEY")
        self.use_api = bool(self.api_key)

    def register_partner(self, name: str, biz_number: str, partner_type: str) -> Optional[str]:
        if self.use_api:
            pass  # TODO: ECOUNT API
        return None

    def register_item(self, item_name: str, item_type: str) -> Optional[str]:
        if self.use_api:
            pass  # TODO: ECOUNT API
        return None

    def create_sales_order(self, partner_code: str, item_code: str, data: dict) -> Optional[str]:
        if self.use_api:
            pass  # TODO: ECOUNT API
        return None

    def create_purchase_order(self, partner_code: str, item_code: str, data: dict) -> Optional[str]:
        if self.use_api:
            pass  # TODO: ECOUNT API
        return None


def export_sales_excel(db: Session, invoice_ids: list[int] | None = None,
                       status: str | None = None,
                       date_from: str | None = None,
                       date_to: str | None = None) -> bytes:
    """매출용 엑셀 (판매자 정산 — 플랫폼 수수료)"""
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl 패키지가 필요합니다.")

    q = db.query(models.TaxInvoice)
    if invoice_ids:
        q = q.filter(models.TaxInvoice.id.in_(invoice_ids))
    if status:
        q = q.filter(models.TaxInvoice.status == status)
    if date_from:
        q = q.filter(models.TaxInvoice.created_at >= date_from)
    if date_to:
        q = q.filter(models.TaxInvoice.created_at <= date_to + " 23:59:59")

    invoices = q.order_by(models.TaxInvoice.created_at.desc()).all()

    # settlement → deal 매핑
    sett_ids = list({inv.settlement_id for inv in invoices if inv.settlement_id})
    sett_map = {}
    deal_map = {}
    if sett_ids:
        setts = db.query(models.ReservationSettlement).filter(
            models.ReservationSettlement.id.in_(sett_ids)
        ).all()
        sett_map = {s.id: s for s in setts}
        deal_ids = list({s.deal_id for s in setts if s.deal_id})
        if deal_ids:
            deals = db.query(models.Deal).filter(models.Deal.id.in_(deal_ids)).all()
            deal_map = {d.id: d for d in deals}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "매출 (플랫폼 수수료)"

    headers = [
        "거래처코드", "거래처명", "사업자번호",
        "품목코드", "품목명", "전표일자",
        "수량", "단가", "공급가액", "세액", "합계", "비고",
    ]
    ws.append(headers)

    for inv in invoices:
        sett = sett_map.get(inv.settlement_id)
        deal = deal_map.get(sett.deal_id) if sett else None
        deal_id = sett.deal_id if sett else ""

        ws.append([
            "",  # 거래처코드
            inv.recipient_business_name or "",
            inv.recipient_business_number or "",
            "",  # 품목코드
            "플랫폼 수수료",
            inv.created_at.strftime("%Y-%m-%d") if inv.created_at else "",
            1,
            inv.supply_amount or 0,
            inv.supply_amount or 0,
            inv.tax_amount or 0,
            inv.total_amount or 0,
            f"정산 S-{inv.settlement_id}, 딜 D-{deal_id}",
        ])

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 30)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_purchase_excel(db: Session,
                          date_from: str | None = None,
                          date_to: str | None = None) -> bytes:
    """매입용 엑셀 (액츄에이터 커미션 지급)"""
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl 패키지가 필요합니다.")

    q = db.query(models.ActuatorCommission)
    if date_from:
        q = q.filter(models.ActuatorCommission.created_at >= date_from)
    if date_to:
        q = q.filter(models.ActuatorCommission.created_at <= date_to + " 23:59:59")

    commissions = q.order_by(models.ActuatorCommission.created_at.desc()).all()

    # actuator 정보
    act_ids = list({c.actuator_id for c in commissions if c.actuator_id})
    act_map = {}
    if act_ids:
        acts = db.query(models.Actuator).filter(models.Actuator.id.in_(act_ids)).all()
        act_map = {a.id: a for a in acts}

    # seller 정보
    seller_ids = list({c.seller_id for c in commissions if c.seller_id})
    seller_map = {}
    if seller_ids:
        sellers = db.query(models.Seller).filter(models.Seller.id.in_(seller_ids)).all()
        seller_map = {s.id: s for s in sellers}

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "매입 (액츄에이터 커미션)"

    headers = [
        "거래처코드", "거래처명", "사업자번호",
        "품목코드", "품목명", "전표일자",
        "수량", "단가", "공급가액", "세액", "합계",
        "원천징수(3.3%)", "비고",
    ]
    ws.append(headers)

    for c in commissions:
        act = act_map.get(c.actuator_id)
        seller = seller_map.get(c.seller_id)
        is_biz = getattr(act, "is_business", False) if act else False
        amount = getattr(c, "amount", 0) or 0

        if is_biz:
            supply = round(amount / 1.1)
            tax = amount - supply
            withholding = 0
        else:
            supply = amount
            tax = 0
            withholding = round(amount * 0.033)

        ws.append([
            "",  # 거래처코드
            getattr(act, "business_name", "") or getattr(act, "nickname", "") or f"ACT-{c.actuator_id}",
            getattr(act, "business_number", "") or "",
            "",  # 품목코드
            "액츄에이터 커미션",
            c.created_at.strftime("%Y-%m-%d") if c.created_at else "",
            1,
            supply,
            supply,
            tax,
            amount,
            withholding if not is_biz else "",
            f"정산 S-{getattr(c, 'settlement_id', '')}, 모집판매자: {getattr(seller, 'business_name', '')}",
        ])

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 30)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
