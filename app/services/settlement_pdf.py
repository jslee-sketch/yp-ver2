# app/services/settlement_pdf.py
"""
정산내역서 PDF 생성 (reportlab 기반).
한글 지원: NanumGothic 폰트 (없으면 Helvetica fallback).
"""
from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 한글 폰트 경로 탐색 ─────────────────────────────────
_FONT_SEARCH = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgun.ttf",           # Windows 맑은 고딕
    "C:/Windows/Fonts/NanumGothic.ttf",
]
_KR_FONT: str | None = None
for _fp in _FONT_SEARCH:
    if Path(_fp).exists():
        _KR_FONT = _fp
        break


def _register_kr_font():
    """한글 폰트 등록. 없으면 Helvetica 사용."""
    if not _KR_FONT:
        return "Helvetica", "Helvetica-Bold"
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont("KR", _KR_FONT))
        pdfmetrics.registerFont(TTFont("KR-Bold", _KR_FONT))  # bold 없으면 동일 폰트
        return "KR", "KR-Bold"
    except Exception as e:
        logger.warning("한글 폰트 등록 실패: %s → Helvetica 사용", e)
        return "Helvetica", "Helvetica-Bold"


def generate_settlement_pdf(data: dict) -> bytes:
    """
    정산내역서 PDF 생성.

    data keys:
        id, approved_date, seller_name, biz_number, representative_name,
        total_sales, fee_rate, platform_fee, shipping_fee, net_amount,
        items (optional list of {name, qty, unit_price, amount})
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    font, font_bold = _register_kr_font()

    # ── 헤더 ──
    c.setFont(font_bold, 18)
    c.drawCentredString(w / 2, h - 2 * cm, "정 산 내 역 서")

    c.setFont(font, 9)
    c.drawRightString(w - 2 * cm, h - 2 * cm, f"정산번호: S-{data.get('id', '')}")
    c.drawRightString(w - 2 * cm, h - 2.5 * cm, f"정산일: {data.get('approved_date', '')}")

    y = h - 3.8 * cm

    # ── 공급자 (역핑/텔러스테크) ──
    c.setFont(font_bold, 11)
    c.drawString(2 * cm, y, "[ 공급자 ]")
    y -= 0.6 * cm
    c.setFont(font, 10)
    for line in [
        "(주)텔러스테크  |  사업자등록번호: 113-86-39805",
        "대표: 이정상  |  서울시 금천구 두산로 70 에이동 811호",
        "이메일: sales@tellustech.co.kr",
    ]:
        c.drawString(2 * cm, y, line)
        y -= 0.5 * cm

    y -= 0.4 * cm

    # ── 공급받는자 (판매자) ──
    c.setFont(font_bold, 11)
    c.drawString(2 * cm, y, "[ 공급받는자 ]")
    y -= 0.6 * cm
    c.setFont(font, 10)
    c.drawString(2 * cm, y, f"{data.get('seller_name', '-')}  |  사업자등록번호: {data.get('biz_number', '-')}")
    y -= 0.5 * cm
    rep = data.get('representative_name', '')
    if rep:
        c.drawString(2 * cm, y, f"대표: {rep}")
        y -= 0.5 * cm

    y -= 0.8 * cm

    # ── 정산 내역 ──
    c.setFont(font_bold, 11)
    c.drawString(2 * cm, y, "[ 정산 내역 ]")
    y -= 0.7 * cm

    # 테이블 헤더
    col_x = [2 * cm, 10 * cm, w - 2 * cm]
    c.setFont(font_bold, 10)
    c.drawString(col_x[0], y, "항목")
    c.drawRightString(col_x[2], y, "금액")
    y -= 0.15 * cm
    c.line(2 * cm, y, w - 2 * cm, y)
    y -= 0.5 * cm

    c.setFont(font, 10)

    def _row(label: str, amount: int | str, bold: bool = False):
        nonlocal y
        if bold:
            c.setFont(font_bold, 11)
        c.drawString(col_x[0], y, label)
        c.drawRightString(col_x[2], y, f"{int(amount):,}원" if isinstance(amount, (int, float)) else str(amount))
        if bold:
            c.setFont(font, 10)
        y -= 0.55 * cm

    _row("상품 판매액", data.get("total_sales", 0))
    _row(f"플랫폼 수수료 ({data.get('fee_rate', 0)}%)", f"-{int(data.get('platform_fee', 0)):,}원")
    shipping = data.get("shipping_fee", 0)
    if shipping:
        _row("배송비 공제", f"-{int(shipping):,}원")

    # 원천징수 (개인 액추에이터인 경우)
    withholding = data.get("withholding_amount", 0)
    if withholding:
        _row(f"원천징수 ({data.get('withholding_rate', '3.3')}%)", f"-{int(withholding):,}원")

    y -= 0.15 * cm
    c.line(2 * cm, y, w - 2 * cm, y)
    y -= 0.6 * cm

    _row("최종 지급액", data.get("net_amount", 0), bold=True)

    # ── 하단 안내 ──
    y -= 1 * cm
    c.setFont(font, 8)
    c.drawString(2 * cm, y, "* 본 정산내역서는 역핑 플랫폼에서 자동 생성되었습니다.")
    y -= 0.4 * cm
    c.drawString(2 * cm, y, "* 문의: sales@tellustech.co.kr")

    c.save()
    buf.seek(0)
    return buf.getvalue()


def generate_withholding_pdf(data: dict) -> bytes:
    """
    원천징수영수증 PDF 생성 (개인 액추에이터용).

    data keys:
        actuator_id, actuator_name, resident_id_last,
        period_start, period_end,
        gross_amount, income_tax, local_tax, withholding_total, net_amount
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    font, font_bold = _register_kr_font()

    # ── 헤더 ──
    c.setFont(font_bold, 18)
    c.drawCentredString(w / 2, h - 2 * cm, "원 천 징 수 영 수 증")

    c.setFont(font, 9)
    c.drawRightString(w - 2 * cm, h - 2.5 * cm, f"발급일: {data.get('issue_date', '')}")

    y = h - 3.8 * cm

    # ── 원천징수 의무자 (텔러스테크) ──
    c.setFont(font_bold, 11)
    c.drawString(2 * cm, y, "[ 원천징수 의무자 ]")
    y -= 0.6 * cm
    c.setFont(font, 10)
    for line in [
        "(주)텔러스테크  |  사업자등록번호: 113-86-39805",
        "대표: 이정상  |  서울시 금천구 두산로 70 에이동 811호",
    ]:
        c.drawString(2 * cm, y, line)
        y -= 0.5 * cm

    y -= 0.4 * cm

    # ── 소득자 (액추에이터) ──
    c.setFont(font_bold, 11)
    c.drawString(2 * cm, y, "[ 소득자 ]")
    y -= 0.6 * cm
    c.setFont(font, 10)
    c.drawString(2 * cm, y, f"성명: {data.get('actuator_name', '-')}")
    y -= 0.5 * cm
    rid = data.get("resident_id_last", "")
    if rid:
        c.drawString(2 * cm, y, f"주민등록번호 뒷자리: {rid}")
        y -= 0.5 * cm
    c.drawString(2 * cm, y, f"정산 기간: {data.get('period_start', '')} ~ {data.get('period_end', '')}")
    y -= 0.5 * cm

    y -= 0.8 * cm

    # ── 원천징수 내역 ──
    c.setFont(font_bold, 11)
    c.drawString(2 * cm, y, "[ 원천징수 내역 ]")
    y -= 0.7 * cm

    c.setFont(font_bold, 10)
    c.drawString(2 * cm, y, "항목")
    c.drawRightString(w - 2 * cm, y, "금액")
    y -= 0.15 * cm
    c.line(2 * cm, y, w - 2 * cm, y)
    y -= 0.5 * cm

    c.setFont(font, 10)

    def _row(label: str, amount, bold: bool = False):
        nonlocal y
        if bold:
            c.setFont(font_bold, 11)
        c.drawString(2 * cm, y, label)
        c.drawRightString(w - 2 * cm, y, f"{int(amount):,}원")
        if bold:
            c.setFont(font, 10)
        y -= 0.55 * cm

    _row("총 커미션(소득금액)", data.get("gross_amount", 0))
    _row("소득세 (3.0%)", data.get("income_tax", 0))
    _row("지방소득세 (0.3%)", data.get("local_tax", 0))

    y -= 0.15 * cm
    c.line(2 * cm, y, w - 2 * cm, y)
    y -= 0.6 * cm

    _row("원천징수 합계 (3.3%)", data.get("withholding_total", 0), bold=True)
    _row("실수령액", data.get("net_amount", 0), bold=True)

    # ── 하단 안내 ──
    y -= 1 * cm
    c.setFont(font, 8)
    c.drawString(2 * cm, y, "* 본 영수증은 역핑 플랫폼에서 자동 생성되었으며, 세무 신고용 참고 자료입니다.")
    y -= 0.4 * cm
    c.drawString(2 * cm, y, "* 정확한 세무 처리는 세무사에게 문의하시기 바랍니다.")

    c.save()
    buf.seek(0)
    return buf.getvalue()
