# app/services/interest_matcher.py
"""딜 생성 시 관심 등록 사용자에게 매칭 알림 발송"""
from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from app import models

logger = logging.getLogger(__name__)


def match_interests_for_deal(deal, db: Session) -> int:
    """새 딜 생성 시 → 관심 등록 사용자에게 알림 발송.
    Returns: 매칭된 알림 수
    """
    from app.services.notification_service import send_notification

    product = (getattr(deal, "product_name", None) or "").lower()
    category = (getattr(deal, "category", None) or "").lower()
    brand = (getattr(deal, "brand", None) or "").lower()

    if not product:
        return 0

    search_terms = [t for t in [product, category, brand] if t]
    interests = db.query(models.UserInterest).all()
    sent_count = 0

    # 딜 생성자 제외
    deal_creator_id = getattr(deal, "buyer_id", None) or getattr(deal, "created_by", None)

    for interest in interests:
        val = (interest.value or "").lower()
        if not val:
            continue

        # 매칭: 관심어가 상품명/카테고리/브랜드에 포함되거나 역방향
        matched = any(
            val in term or term in val
            for term in search_terms
        )
        if not matched:
            continue

        # 딜 생성자 본인 제외
        if interest.user_id == deal_creator_id:
            continue

        role = interest.role or "buyer"
        event_map = {
            "seller": "DEAL_MATCH_INTEREST",
            "actuator": "INTEREST_DEAL_CREATED",
            "buyer": "NUDGE_INTEREST_DEAL",
        }
        event_type = event_map.get(role, "NUDGE_INTEREST_DEAL")

        try:
            send_notification(
                db,
                user_id=interest.user_id,
                role=role,
                event_type=event_type,
                variables={
                    "matched_interest": interest.value,
                    "product_name": deal.product_name or "",
                    "deal_id": str(deal.id),
                    "target_price": f"{deal.target_price:,.0f}" if deal.target_price else "",
                },
                deal_id=deal.id,
            )
            sent_count += 1
        except Exception as e:
            logger.warning("[INTEREST_MATCH] Failed to send for user=%d: %s", interest.user_id, e)

    logger.info("[INTEREST_MATCH] deal=%d matched=%d", deal.id, sent_count)
    return sent_count


def match_interests_for_offer(offer, deal, db: Session) -> int:
    """오퍼 제출 시 → 딜 참여자에게 알림"""
    from app.services.notification_service import send_notification

    # 딜 참여자에게 새 오퍼 알림
    participants = db.query(models.DealParticipant).filter(
        models.DealParticipant.deal_id == deal.id
    ).all() if hasattr(models, 'DealParticipant') else []

    sent_count = 0
    seller_name = ""
    if hasattr(offer, "seller_id") and offer.seller_id:
        seller = db.query(models.Seller).filter(models.Seller.id == offer.seller_id).first()
        seller_name = getattr(seller, "company_name", "") or getattr(seller, "name", "") or ""

    for p in participants:
        buyer_id = getattr(p, "buyer_id", None) or getattr(p, "user_id", None)
        if not buyer_id:
            continue
        try:
            send_notification(
                db,
                user_id=buyer_id,
                role="buyer",
                event_type="OFFER_ARRIVED",
                variables={
                    "product_name": deal.product_name or "",
                    "seller_name": seller_name,
                    "offer_price": f"{offer.unit_price:,.0f}" if hasattr(offer, "unit_price") and offer.unit_price else "",
                    "deal_id": str(deal.id),
                },
                deal_id=deal.id,
                offer_id=offer.id,
            )
            sent_count += 1
        except Exception as e:
            logger.warning("[OFFER_NOTIFY] Failed user=%s: %s", buyer_id, e)

    return sent_count
