# app/pingpong/evidence/build_evidence_pack_v0.py
from __future__ import annotations

from typing import Any, Dict
from sqlalchemy.orm import Session

from app.pingpong.evidence.build_offer_confirm_v1 import build_offer_confirm_v1
from app.pingpong.evidence.build_refund_dispute_v1 import build_refund_dispute_v1
from app.pingpong.evidence.build_reservation_paid_v1 import build_reservation_paid_v1

from app.pingpong.evidence.build_reservation_cancel_v1 import build_reservation_cancel_v1


def build_evidence_pack_v0(
    db: Session,
    *,
    kind: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    단일 엔트리 포인트 (PingPong이 여기만 보면 됨)
    kind 예:
      - "offer_confirm_v1"
      - "refund_dispute_v1"
      - "reservation_paid_v1"
    """
    if kind == "buyer_register_v1":
        from app.pingpong.evidence.build_buyer_register_v1 import build_buyer_register_v1
        return build_buyer_register_v1(db, **payload)

    if kind == "buyer_referral_reward_v1":
        from app.pingpong.evidence.build_buyer_referral_reward_v1 import build_buyer_referral_reward_v1
        return build_buyer_referral_reward_v1(db, **payload)
    
    if kind == "seller_register_v1":
        from app.pingpong.evidence.build_seller_register_v1 import build_seller_register_v1
        return build_seller_register_v1(db, **payload)

    if kind == "login_v1":
        from app.pingpong.evidence.build_login_v1 import build_login_v1
        return build_login_v1(db, **payload)
    
    if kind == "actuator_create_v1":
        from app.pingpong.evidence.build_actuator_create_v1 import build_actuator_create_v1
        return build_actuator_create_v1(db, **payload)
    
    if kind == "deal_create_v1":
        from app.pingpong.evidence.build_deal_create_v1 import build_deal_create_v1
        return build_deal_create_v1(db, **payload)
    
    if kind == "offer_create_v1":
        from app.pingpong.evidence.build_offer_create_v1 import build_offer_create_v1
        return build_offer_create_v1(db, **payload)

    if kind == "reservation_create_v1":
        from app.pingpong.evidence.build_reservation_create_v1 import build_reservation_create_v1
        return build_reservation_create_v1(db, **payload)

    if kind == "reservation_expire_v1":
        from app.pingpong.evidence.build_reservation_expire_v1 import build_reservation_expire_v1
        return build_reservation_expire_v1(db, **payload)

    if kind == "recommender_reward_v1":
        from app.pingpong.evidence.build_recommender_reward_v1 import build_recommender_reward_v1
        return build_recommender_reward_v1(db, **payload)

    if kind == "reservation_paid_v1":
        return build_reservation_paid_v1(db, **payload)
    
    if kind == "reservation_cancel_v1":
        return build_reservation_cancel_v1(db, **payload)

    if kind == "offer_confirm_v1":
        return build_offer_confirm_v1(db, **payload)

    if kind == "refund_dispute_v1":
        return build_refund_dispute_v1(db, **payload)

    raise ValueError(f"unknown evidence kind: {kind}")