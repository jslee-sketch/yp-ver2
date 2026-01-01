# app/logic/notifications_actuator.py

from sqlalchemy.orm import Session
from typing import Optional

from app import models
from app.logic.notifications import create_notification
from app.config import rules_v3_5 as RV


def _get_actuator_rate_for_level(level_str: str) -> float:
    """
    이미 offers.py 에 있는 함수와 동일하게 맞추면 됨.
    여기 중복이면, 공통 util로 빼서 import 해도 OK.
    """
    try:
        table = getattr(RV, "ACTUATOR_FEE_BY_LEVEL", None) or {}
        if table:
            return float(table.get(level_str, 0.0))
    except Exception:
        pass

    default_table = {
        "Lv.6": 0.5,
        "Lv.5": 0.2,
        "Lv.4": 0.1,
        "Lv.3": 0.0,
        "Lv.2": 0.0,
        "Lv.1": 0.0,
    }
    return float(default_table.get(level_str, 0.0))


# 1) 추천 셀러 등록 완료
def notify_actuator_seller_registered(
    db: Session,
    seller: models.Seller,
):
    """
    Seller가 판매자 등록(APPROVED) 완료되었을 때 호출.
    """
    actuator_id = getattr(seller, "actuator_id", None)
    if not actuator_id:
        return

    seller_name = getattr(seller, "display_name", None) or getattr(seller, "name", None) or f"Seller#{seller.id}"
    level_int = int(getattr(seller, "level", 6) or 6)
    level_str = f"Lv.{level_int}"

    title = "추천 셀러 등록 완료"
    message = f"당신이 추천한 셀러 '{seller_name}' 이(가) 판매자 등록을 완료했습니다. (현재 레벨: {level_str})"

    meta = {
        "seller_id": seller.id,
        "seller_name": seller_name,
        "seller_level": level_str,
    }

    create_notification(
        db,
        user_id=actuator_id,
        event_type="actuator_seller_registered",
        title=title,
        message=message,
        seller_id=seller.id,
        actuator_id=actuator_id,
        meta=meta,
    )


# 2) 셀러 레벨 변경 → 수수료율 변경
def notify_actuator_commission_rate_changed(
    db: Session,
    seller: models.Seller,
    old_level: int,
    new_level: int,
):
    actuator_id = getattr(seller, "actuator_id", None)
    if not actuator_id:
        return

    if old_level == new_level:
        return

    old_level_str = f"Lv.{int(old_level)}"
    new_level_str = f"Lv.{int(new_level)}"

    old_rate = _get_actuator_rate_for_level(old_level_str)
    new_rate = _get_actuator_rate_for_level(new_level_str)

    # 수수료율이 실제로 달라지지 않으면 알림 생략
    if abs(old_rate - new_rate) < 1e-9:
        return

    seller_name = getattr(seller, "display_name", None) or getattr(seller, "name", None) or f"Seller#{seller.id}"

    title = "추천 셀러 수수료율 변경"
    message = (
        f"추천 셀러 '{seller_name}' 의 레벨이 {old_level_str} → {new_level_str} 로 변경되었습니다. "
        f"당신의 커미션율은 {old_rate}% → {new_rate}% 로 바뀝니다."
    )

    meta = {
        "seller_id": seller.id,
        "seller_name": seller_name,
        "old_level": old_level_str,
        "new_level": new_level_str,
        "old_rate_percent": old_rate,
        "new_rate_percent": new_rate,
    }

    create_notification(
        db,
        user_id=actuator_id,
        event_type="actuator_commission_rate_changed",
        title=title,
        message=message,
        seller_id=seller.id,
        actuator_id=actuator_id,
        meta=meta,
    )


# 3) 커미션 지급 완료
def notify_actuator_commission_paid(
    db: Session,
    commission: models.ActuatorCommission,
    seller: Optional[models.Seller] = None,
):
    """
    ActuatorCommission row의 status를 PAID로 바꾼 직후 호출.
    (정산 배치/로직 내에서)
    """
    actuator_id = getattr(commission, "actuator_id", None)
    if not actuator_id:
        return

    if seller is None and getattr(commission, "seller_id", None):
        seller = db.get(models.Seller, commission.seller_id)

    seller_name = None
    if seller:
        seller_name = (
            getattr(seller, "display_name", None)
            or getattr(seller, "name", None)
            or f"Seller#{seller.id}"
        )

    title = "커미션 지급 완료"
    if seller_name:
        who = f"추천 셀러 '{seller_name}'"
    else:
        who = "추천 셀러"

    amount = int(getattr(commission, "amount", 0) or 0)
    message = f"{who} 의 거래에 대한 커미션 {amount}원이 지급 완료되었습니다."

    meta = {
        "seller_id": getattr(commission, "seller_id", None),
        "seller_name": seller_name,
        "reservation_id": getattr(commission, "reservation_id", None),
        "gmv": getattr(commission, "gmv", None),
        "rate_percent": getattr(commission, "rate_percent", None),
        "amount": amount,
    }

    create_notification(
        db,
        user_id=actuator_id,
        event_type="actuator_commission_paid",
        title=title,
        message=message,
        seller_id=getattr(commission, "seller_id", None),
        reservation_id=getattr(commission, "reservation_id", None),
        actuator_id=actuator_id,
        meta=meta,
    )