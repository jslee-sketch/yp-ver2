from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import DonzzulVoucher, DonzzulStore, DonzzulDeal


def run_donzzul_expiry_batch(db: Session) -> dict:
    """
    돈쭐 상품권 만료 배치
    - ACTIVE + 유효기간 지난 상품권 → DONATED (가게에 자동 기부)
    - 낙전수익 ZERO: 역핑이 가져가지 않음
    """
    now = datetime.utcnow()

    expired = db.query(DonzzulVoucher).filter(
        DonzzulVoucher.status == "ACTIVE",
        DonzzulVoucher.expires_at < now,
    ).all()

    donated_count = 0
    donated_total = 0

    for v in expired:
        v.status = "DONATED"
        v.donated_at = now
        v.remaining_amount = 0
        donated_count += 1
        donated_total += v.amount

    if expired:
        db.commit()

    return {
        "donated_count": donated_count,
        "donated_total": donated_total,
        "run_at": str(now),
    }


def run_donzzul_expiry_warning_batch(db: Session) -> dict:
    """
    만료 임박 알림 배치
    - 14일 전, 7일 전, 1일 전 알림
    """
    try:
        from app.policy.runtime import load_defaults
        policy = load_defaults()
        warning_days = policy.get("donzzul", {}).get("voucher_expiry_warning_days", [14, 7, 1])
    except Exception:
        warning_days = [14, 7, 1]

    now = datetime.utcnow()
    warnings_sent = 0

    for days in warning_days:
        target_date = now + timedelta(days=days)
        start = target_date.replace(hour=0, minute=0, second=0)
        end = target_date.replace(hour=23, minute=59, second=59)

        vouchers = db.query(DonzzulVoucher).filter(
            DonzzulVoucher.status == "ACTIVE",
            DonzzulVoucher.expires_at >= start,
            DonzzulVoucher.expires_at <= end,
        ).all()

        for v in vouchers:
            v.last_warning_days = days
            warnings_sent += 1

    if warnings_sent:
        db.commit()

    return {
        "warnings_sent": warnings_sent,
        "run_at": str(now),
    }


def run_donzzul_deal_expiry_batch(db: Session) -> dict:
    """
    딜 마감 배치
    - expires_at 지난 OPEN 딜 → CLOSED
    """
    now = datetime.utcnow()

    expired_deals = db.query(DonzzulDeal).filter(
        DonzzulDeal.status == "OPEN",
        DonzzulDeal.expires_at < now,
    ).all()

    for deal in expired_deals:
        deal.status = "CLOSED"

    if expired_deals:
        db.commit()

    return {
        "closed_deals": len(expired_deals),
        "run_at": str(now),
    }
