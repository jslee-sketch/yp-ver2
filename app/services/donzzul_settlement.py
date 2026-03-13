from datetime import datetime
from sqlalchemy.orm import Session
from app.models import DonzzulVoucher, DonzzulStore, DonzzulSettlement


def create_donzzul_settlement(store_id: int, db: Session) -> dict:
    """
    돈쭐 가게 정산 생성
    - 사용 완료(USED) + 만료 기부(DONATED) 상품권 합산
    - 역핑 수수료 0원
    """
    store = db.query(DonzzulStore).filter(DonzzulStore.id == store_id).first()
    if not store:
        return {"error": "가게를 찾을 수 없습니다"}

    # 미정산 상품권 조회: USED 또는 DONATED 중 settlement_id가 없는 것
    unsettled = db.query(DonzzulVoucher).filter(
        DonzzulVoucher.store_id == store_id,
        DonzzulVoucher.status.in_(["USED", "DONATED"]),
        DonzzulVoucher.settlement_id == None,
    ).all()

    if not unsettled:
        return {"error": "정산할 상품권이 없습니다", "count": 0}

    # 합산
    used_amount = sum(v.amount for v in unsettled if v.status == "USED")
    donated_amount = sum(v.amount for v in unsettled if v.status == "DONATED")
    total_amount = used_amount + donated_amount

    # 역핑 수수료 0원!
    platform_fee = 0
    payout_amount = total_amount - platform_fee

    # 정산 생성
    settlement = DonzzulSettlement(
        store_id=store_id,
        total_amount=total_amount,
        used_amount=used_amount,
        donated_amount=donated_amount,
        platform_fee=platform_fee,
        payout_amount=payout_amount,
        voucher_count=len(unsettled),
        status="PENDING",
        bank_name=store.bank_name,
        account_number=store.account_number,
        account_holder=store.account_holder,
        period_from=min(v.created_at for v in unsettled),
        period_to=max(v.used_at or v.expires_at or v.created_at for v in unsettled),
    )
    db.add(settlement)
    db.flush()

    # 상품권에 settlement_id 연결
    for v in unsettled:
        v.settlement_id = settlement.id

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        return {"error": f"DB 오류: {e}"}
    db.refresh(settlement)

    return {
        "settlement_id": settlement.id,
        "store_name": store.store_name,
        "total_amount": total_amount,
        "used_amount": used_amount,
        "donated_amount": donated_amount,
        "payout_amount": payout_amount,
        "voucher_count": len(unsettled),
    }


def process_donzzul_settlement(settlement_id: int, action: str, db: Session, admin_id: int = None) -> dict:
    """정산 승인/지급/거절"""
    settlement = db.query(DonzzulSettlement).filter(DonzzulSettlement.id == settlement_id).first()
    if not settlement:
        return {"error": "정산을 찾을 수 없습니다"}

    if action == "approve":
        settlement.status = "APPROVED"
        settlement.approved_by = admin_id
        settlement.approved_at = datetime.utcnow()

    elif action == "pay":
        if settlement.status != "APPROVED":
            return {"error": "승인된 정산만 지급 가능합니다"}
        settlement.status = "PAID"
        settlement.paid_at = datetime.utcnow()

    elif action == "reject":
        settlement.status = "REJECTED"

    db.commit()
    return {"settlement_id": settlement.id, "status": settlement.status}
