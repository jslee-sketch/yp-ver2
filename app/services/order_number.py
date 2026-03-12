"""주문번호 생성 서비스 — YP-YYYYMMDD-NNNN 형식"""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.models import Reservation


def generate_order_number(db: Session) -> str:
    """오늘 날짜 기준 순번으로 주문번호 생성."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"YP-{today}-"

    # 오늘 발급된 가장 큰 순번 조회
    last = (
        db.query(func.max(Reservation.order_number))
        .filter(Reservation.order_number.like(f"{prefix}%"))
        .scalar()
    )

    if last:
        seq = int(last.split("-")[-1]) + 1
    else:
        seq = 1

    return f"{prefix}{seq:04d}"


def backfill_order_numbers(db: Session) -> int:
    """order_number가 없는 기존 예약에 주문번호 부여 (created_at 순)."""
    rows = (
        db.query(Reservation)
        .filter(Reservation.order_number.is_(None))
        .order_by(Reservation.created_at.asc())
        .all()
    )
    if not rows:
        return 0

    # 날짜별 그룹핑하여 순번 부여
    date_seqs: dict[str, int] = {}
    for r in rows:
        dt = r.created_at
        if dt is None:
            dt = datetime.now(timezone.utc)
        day = dt.strftime("%Y%m%d")

        # 해당 날짜에 이미 발급된 최대 순번 조회 (캐시)
        if day not in date_seqs:
            prefix = f"YP-{day}-"
            last = (
                db.query(func.max(Reservation.order_number))
                .filter(Reservation.order_number.like(f"{prefix}%"))
                .scalar()
            )
            date_seqs[day] = int(last.split("-")[-1]) if last else 0

        date_seqs[day] += 1
        r.order_number = f"YP-{day}-{date_seqs[day]:04d}"

    db.commit()
    return len(rows)
