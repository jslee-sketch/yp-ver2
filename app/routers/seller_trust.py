"""판매자 신뢰 엔진 v2 — 외부평점 + AI 스코어링 + 해지 + KPI + 인사이트 + 환불 시뮬레이터"""
import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import (
    SellerExternalRating, SellerVerificationScore, ActuatorSellerDisconnection,
    Reservation, Offer, Deal, Seller,
)
from app.services.external_rating_service import (
    register_external_rating, verify_external_rating,
    run_external_rating_batch, get_seller_ratings,
)
from app.services.seller_score_service import calculate_seller_score

router = APIRouter(prefix="/v3_6", tags=["seller-trust"])


# ═══════════ 외부 평점 ═══════════

@router.post("/seller/external-ratings")
def api_register_rating(body: dict, db: Session = Depends(get_db)):
    result = register_external_rating(body, db)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/seller/external-ratings/{id}/verify")
def api_verify_rating(id: int, db: Session = Depends(get_db)):
    result = verify_external_rating(id, db)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/seller/{seller_id}/external-ratings")
def api_get_ratings(seller_id: int, db: Session = Depends(get_db)):
    return get_seller_ratings(seller_id, db)


@router.post("/seller/external-ratings/batch")
def api_batch_ratings(db: Session = Depends(get_db)):
    return run_external_rating_batch(db)


# ═══════════ AI 스코어링 ═══════════

@router.post("/seller/{seller_id}/score")
def api_calculate_score(seller_id: int, db: Session = Depends(get_db)):
    result = calculate_seller_score(seller_id, db)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/seller/{seller_id}/score")
def api_get_score(seller_id: int, db: Session = Depends(get_db)):
    score = db.query(SellerVerificationScore).filter(
        SellerVerificationScore.seller_id == seller_id
    ).first()
    if not score:
        return {"total_score": 0, "auto_decision": None}
    return {
        "total_score": score.total_score,
        "auto_decision": score.auto_decision,
        "scores": {
            "age": score.score_age,
            "rating": score.score_rating,
            "reviews": score.score_reviews,
            "sentiment": score.score_sentiment,
            "trade_cert": score.score_trade_cert,
            "account": score.score_account,
            "biz": score.score_biz,
        },
        "seller_message": score.seller_message,
        "admin_message": score.admin_message,
        "reasons": json.loads(score.reasons or "[]"),
    }


@router.put("/admin/seller/{seller_id}/decision")
def api_admin_decision(seller_id: int, body: dict, db: Session = Depends(get_db)):
    score = db.query(SellerVerificationScore).filter(
        SellerVerificationScore.seller_id == seller_id
    ).first()
    if not score:
        raise HTTPException(404, "스코어 레코드 없음")
    decision = body.get("decision")
    notes = body.get("notes", "")

    if decision == "approve":
        score.auto_decision = "ADMIN_APPROVED"
        score.admin_notes = notes
    else:
        score.auto_decision = "ADMIN_REJECTED"
        score.admin_notes = notes

    db.commit()
    return {"seller_id": seller_id, "decision": score.auto_decision}


# ═══════════ 액츄에이터-판매자 해지 ═══════════

@router.post("/actuator-seller/disconnect")
def api_request_disconnect(body: dict, db: Session = Depends(get_db)):
    if not body.get("agreement_accepted"):
        raise HTTPException(400, "해지 약관에 동의해야 합니다")

    now = datetime.utcnow()
    grace_days = 7
    cooldown_days = 30

    # 쿨다운 체크
    recent = db.query(ActuatorSellerDisconnection).filter(
        ActuatorSellerDisconnection.actuator_id == body["actuator_id"],
        ActuatorSellerDisconnection.seller_id == body["seller_id"],
        ActuatorSellerDisconnection.status == "CONFIRMED",
        ActuatorSellerDisconnection.cooldown_ends > now,
    ).first()
    if recent:
        raise HTTPException(400, f"쿨다운 기간입니다. {recent.cooldown_ends}까지 재연결 불가")

    d = ActuatorSellerDisconnection(
        actuator_id=body["actuator_id"],
        seller_id=body["seller_id"],
        requested_by=body.get("requested_by", "actuator"),
        reason=body.get("reason", "personal_reason"),
        reason_detail=body.get("reason_detail", ""),
        status="GRACE_PERIOD",
        grace_period_ends=now + timedelta(days=grace_days),
        cooldown_ends=now + timedelta(days=grace_days + cooldown_days),
        agreement_accepted=True,
        agreement_accepted_at=now,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return {
        "id": d.id,
        "status": d.status,
        "grace_period_ends": str(d.grace_period_ends),
        "cooldown_ends": str(d.cooldown_ends),
    }


@router.put("/actuator-seller/disconnect/{id}/cancel")
def api_cancel_disconnect(id: int, db: Session = Depends(get_db)):
    d = db.query(ActuatorSellerDisconnection).filter(
        ActuatorSellerDisconnection.id == id
    ).first()
    if not d or d.status != "GRACE_PERIOD":
        raise HTTPException(400, "철회 가능한 상태가 아닙니다")
    if datetime.utcnow() > d.grace_period_ends:
        raise HTTPException(400, "유예 기간이 만료되었습니다")

    d.status = "CANCELLED"
    d.cancelled_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": "해지가 철회되었습니다"}


@router.post("/actuator-seller/disconnect/batch/confirm")
def api_batch_confirm(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    pending = db.query(ActuatorSellerDisconnection).filter(
        ActuatorSellerDisconnection.status == "GRACE_PERIOD",
        ActuatorSellerDisconnection.grace_period_ends < now,
    ).all()

    confirmed = 0
    for d in pending:
        d.status = "CONFIRMED"
        d.confirmed_at = now
        confirmed += 1

    if confirmed:
        db.commit()
    return {"confirmed": confirmed}


@router.get("/actuator-seller/disconnections")
def api_list_disconnections(
    actuator_id: int = Query(None),
    seller_id: int = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(ActuatorSellerDisconnection)
    if actuator_id:
        query = query.filter(ActuatorSellerDisconnection.actuator_id == actuator_id)
    if seller_id:
        query = query.filter(ActuatorSellerDisconnection.seller_id == seller_id)
    results = query.order_by(ActuatorSellerDisconnection.created_at.desc()).all()
    return [
        {
            "id": d.id, "status": d.status,
            "actuator_id": d.actuator_id, "seller_id": d.seller_id,
            "requested_by": d.requested_by, "reason": d.reason,
            "grace_period_ends": str(d.grace_period_ends) if d.grace_period_ends else None,
            "cooldown_ends": str(d.cooldown_ends) if d.cooldown_ends else None,
            "created_at": str(d.created_at) if d.created_at else None,
        }
        for d in results
    ]


# ═══════════ KPI 고도화 ═══════════

@router.get("/admin/kpi/advanced")
def api_kpi_advanced(period: str = Query("30d"), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    days_map = {"7d": 7, "30d": 30, "90d": 90, "all": 9999}
    since = now - timedelta(days=days_map.get(period, 30))

    gmv = db.query(func.sum(Reservation.total_amount)).filter(
        Reservation.created_at >= since,
        Reservation.status.in_(["CONFIRMED", "COMPLETED"]),
    ).scalar() or 0

    order_count = db.query(Reservation).filter(
        Reservation.created_at >= since,
        Reservation.status.in_(["CONFIRMED", "COMPLETED"]),
    ).count()
    aov = round(gmv / order_count) if order_count > 0 else 0

    total_offers = db.query(Offer).filter(Offer.created_at >= since).count()
    accepted_offers = db.query(Offer).filter(
        Offer.created_at >= since, Offer.status == "ACCEPTED",
    ).count()
    conversion_rate = round(accepted_offers / total_offers * 100, 1) if total_offers > 0 else 0

    mau = db.query(func.count(func.distinct(Reservation.buyer_id))).filter(
        Reservation.created_at >= now - timedelta(days=30),
    ).scalar() or 0

    last_month_buyers = db.query(func.distinct(Reservation.buyer_id)).filter(
        Reservation.created_at >= now - timedelta(days=60),
        Reservation.created_at < now - timedelta(days=30),
    ).all()
    last_month_ids = [b[0] for b in last_month_buyers]

    retained = 0
    if last_month_ids:
        retained = db.query(func.count(func.distinct(Reservation.buyer_id))).filter(
            Reservation.created_at >= now - timedelta(days=30),
            Reservation.buyer_id.in_(last_month_ids),
        ).scalar() or 0
    retention_rate = round(retained / len(last_month_ids) * 100, 1) if last_month_ids else 0

    return {
        "period": period,
        "gmv": gmv,
        "aov": aov,
        "order_count": order_count,
        "total_offers": total_offers,
        "accepted_offers": accepted_offers,
        "conversion_rate": conversion_rate,
        "mau": mau,
        "retention_rate": retention_rate,
        "retained_users": retained,
        "last_month_users": len(last_month_ids),
    }


# ═══════════ 금맥 인사이트 ═══════════

@router.get("/admin/insights/trends")
def api_insights_trends(db: Session = Depends(get_db)):
    now = datetime.utcnow()

    categories = db.query(
        Deal.category, func.count(Deal.id).label("deal_count"),
    ).group_by(Deal.category).order_by(func.count(Deal.id).desc()).limit(10).all()

    brands = db.query(
        Deal.brand, func.count(Deal.id).label("deal_count"),
        func.avg(Deal.target_price).label("avg_target"),
    ).filter(Deal.brand != None, Deal.brand != "").group_by(
        Deal.brand
    ).order_by(func.count(Deal.id).desc()).limit(10).all()

    price_ranges = []
    for low, high, label in [
        (0, 100000, "10만 미만"),
        (100000, 300000, "10-30만"),
        (300000, 500000, "30-50만"),
        (500000, 1000000, "50-100만"),
        (1000000, 99999999, "100만+"),
    ]:
        count = db.query(Deal).filter(
            Deal.target_price >= low, Deal.target_price < high,
        ).count()
        price_ranges.append({"label": label, "count": count})

    recent_deals = db.query(Deal.title).filter(
        Deal.created_at >= now - timedelta(days=7)
    ).all()

    from collections import Counter
    words = Counter()
    for (title,) in recent_deals:
        if title:
            for word in title.split():
                if len(word) >= 2:
                    words[word] += 1
    hot_keywords = [{"word": w, "count": c} for w, c in words.most_common(15)]

    return {
        "categories": [{"category": c[0] or "미분류", "count": c[1]} for c in categories],
        "brands": [{"brand": b[0], "count": b[1], "avg_target": round(b[2] or 0)} for b in brands],
        "price_ranges": price_ranges,
        "hot_keywords": hot_keywords,
    }


# ═══════════ 환불 시뮬레이터 (구매자/판매자 확장) ═══════════

@router.get("/refund-simulator/calculate")
def api_refund_simulate(
    amount: int = Query(...),
    reason: str = Query("buyer_change_mind"),
    delivery_status: str = Query("before"),
    shipping_mode: str = Query("free"),
    shipping_cost: int = Query(3000),
    days_since_delivery: int = Query(0),
    role: str = Query("buyer"),
    db: Session = Depends(get_db),
):
    cooling = 7
    can_refund = days_since_delivery <= cooling

    refund_amount = amount
    deductions = []

    if reason == "buyer_change_mind":
        if delivery_status in ("in_transit", "delivered"):
            if shipping_mode == "free":
                refund_amount -= shipping_cost
                deductions.append(f"왕복 배송비 차감: -{shipping_cost:,}원")
            elif shipping_mode == "buyer_paid":
                refund_amount -= shipping_cost
                deductions.append(f"반품 배송비 차감: -{shipping_cost:,}원")

    usage_deduction = 0
    if days_since_delivery > 3 and reason == "buyer_change_mind":
        usage_rate = min(days_since_delivery * 2, 20)
        usage_deduction = int(amount * usage_rate / 100)
        refund_amount -= usage_deduction
        deductions.append(f"사용 차감 ({usage_rate}%): -{usage_deduction:,}원")

    refund_amount = max(0, refund_amount)

    result = {
        "can_refund": can_refund,
        "original_amount": amount,
        "refund_amount": refund_amount,
        "deductions": deductions,
        "reason": reason,
        "delivery_status": delivery_status,
        "days_since_delivery": days_since_delivery,
        "cooling_period": cooling,
    }

    if role in ("seller", "admin"):
        platform_fee_rate = 0.05
        original_settlement = int(amount * (1 - platform_fee_rate))
        after_refund_settlement = int((amount - refund_amount) * (1 - platform_fee_rate))

        result["settlement_impact"] = {
            "before_refund": original_settlement,
            "after_refund": after_refund_settlement,
            "settlement_loss": original_settlement - after_refund_settlement,
            "platform_fee_rate": platform_fee_rate,
        }

    return result
