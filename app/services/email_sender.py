# app/services/email_sender.py
"""
이메일 발송 서비스 (SMTP).
환경변수: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
미설정 시 발송 스킵 (로그만 기록).
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

logger = logging.getLogger(__name__)


def _smtp_config() -> dict | None:
    user = os.environ.get("SMTP_USER")
    passwd = os.environ.get("SMTP_PASS")
    if not user or not passwd:
        return None
    return {
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": user,
        "pass": passwd,
    }


def send_email(
    to: str,
    subject: str,
    body_html: str,
    attachment: bytes | None = None,
    attachment_filename: str | None = None,
    from_addr: str | None = None,
) -> bool:
    """
    이메일 발송. SMTP 미설정 시 False 반환 (로그만).
    """
    cfg = _smtp_config()
    if not cfg:
        logger.info("[EMAIL] SMTP 미설정, 스킵: to=%s subject=%s", to, subject)
        return False

    sender = from_addr or cfg["user"]

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject

    msg.attach(MIMEText(body_html, "html", "utf-8"))

    if attachment and attachment_filename:
        part = MIMEApplication(attachment, Name=attachment_filename)
        part["Content-Disposition"] = f'attachment; filename="{attachment_filename}"'
        msg.attach(part)

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.starttls()
            server.login(cfg["user"], cfg["pass"])
            server.send_message(msg)
        logger.info("[EMAIL] 발송 성공: to=%s subject=%s", to, subject)
        return True
    except Exception as e:
        logger.error("[EMAIL] 발송 실패: to=%s error=%s", to, e)
        return False


# ── 정산 알림 이메일 템플릿 ────────────────────────────────────

def send_settlement_notification(to: str, settlement_id: int, seller_name: str, net_amount: int, pdf_bytes: bytes | None = None) -> bool:
    """정산 승인 알림 이메일 (PDF 첨부 가능)."""
    subject = f"[역핑] 정산내역서 확인 요청 (S-{settlement_id})"
    body = f"""
    <div style="font-family: 'Malgun Gothic', sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563eb;">정산내역서 확인 요청</h2>
        <p>안녕하세요 <strong>{seller_name}</strong>님,</p>
        <p>정산번호 <strong>S-{settlement_id}</strong>의 정산이 승인되었습니다.</p>
        <p>최종 지급액: <strong>{net_amount:,}원</strong></p>
        <p>첨부된 정산내역서를 확인해 주세요.</p>
        <hr style="margin: 20px 0;">
        <p style="color: #6b7280; font-size: 12px;">
            본 메일은 역핑 플랫폼에서 자동 발송되었습니다.<br>
            문의: sales@tellustech.co.kr
        </p>
    </div>
    """
    return send_email(
        to=to,
        subject=subject,
        body_html=body,
        attachment=pdf_bytes,
        attachment_filename=f"settlement_{settlement_id}.pdf" if pdf_bytes else None,
    )


def send_tax_invoice_notification(to: str, invoice_number: str, total_amount: int, status: str = "발행") -> bool:
    """세금계산서 발행/확인 요청 이메일."""
    subject = f"[역핑] 세금계산서 {status} 안내 ({invoice_number})"
    body = f"""
    <div style="font-family: 'Malgun Gothic', sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563eb;">세금계산서 {status} 안내</h2>
        <p>세금계산서 번호: <strong>{invoice_number}</strong></p>
        <p>합계 금액: <strong>{total_amount:,}원</strong></p>
        <p>역핑 플랫폼에서 세금계산서를 확인해 주세요.</p>
        <hr style="margin: 20px 0;">
        <p style="color: #6b7280; font-size: 12px;">
            본 메일은 역핑 플랫폼에서 자동 발송되었습니다.<br>
            문의: sales@tellustech.co.kr
        </p>
    </div>
    """
    return send_email(to=to, subject=subject, body_html=body)


def send_refund_notification(to: str, buyer_name: str, reservation_id: int, refund_amount: int) -> bool:
    """환불 완료 알림 이메일."""
    subject = f"[역핑] 환불 처리 완료 (예약번호: {reservation_id})"
    body = f"""
    <div style="font-family: 'Malgun Gothic', sans-serif; max-width: 600px; margin: 0 auto;">
        <h2 style="color: #2563eb;">환불 처리 완료</h2>
        <p>안녕하세요 <strong>{buyer_name}</strong>님,</p>
        <p>예약번호 <strong>{reservation_id}</strong>의 환불이 처리되었습니다.</p>
        <p>환불 금액: <strong>{refund_amount:,}원</strong></p>
        <hr style="margin: 20px 0;">
        <p style="color: #6b7280; font-size: 12px;">
            본 메일은 역핑 플랫폼에서 자동 발송되었습니다.<br>
            문의: sales@tellustech.co.kr
        </p>
    </div>
    """
    return send_email(to=to, subject=subject, body_html=body)
