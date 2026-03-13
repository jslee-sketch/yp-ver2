# app/routers/public_demand.py
# 공개 수요 대시보드 — 인증 불필요
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.database import get_db
from app.models import Deal, Offer

router = APIRouter(tags=["public"])


@router.get("/public/demand")
def get_public_demand(db: Session = Depends(get_db)):
    """공개 수요 대시보드 — 인증 불필요"""
    now = datetime.utcnow()

    # 1. 실시간 수요 TOP 20 (OPEN 딜 기준)
    deals = (
        db.query(Deal)
        .filter(Deal.status.in_(["open", "OPEN", "active", "ACTIVE"]))
        .order_by(desc(Deal.created_at))
        .limit(50)
        .all()
    )

    top_demands = []
    for d in deals:
        offer_count = db.query(Offer).filter(Offer.deal_id == d.id).count()
        top_demands.append({
            "id": d.id,
            "title": d.product_name,
            "brand": d.brand or "",
            "category": d.category or "기타",
            "target_price": d.target_price or 0,
            "demand_count": max(offer_count * 3, 1),
            "created_at": str(d.created_at),
            "days_ago": (now - d.created_at).days if d.created_at else 0,
        })

    top_demands.sort(key=lambda x: x["demand_count"], reverse=True)

    # 2. 카테고리별 수요 집계
    category_stats = (
        db.query(
            Deal.category,
            func.count(Deal.id).label("count"),
            func.avg(Deal.target_price).label("avg_price"),
        )
        .filter(Deal.status.in_(["open", "OPEN", "active", "ACTIVE"]))
        .group_by(Deal.category)
        .order_by(desc("count"))
        .all()
    )

    categories = [
        {"category": c[0] or "기타", "count": c[1], "avg_price": round(c[2] or 0)}
        for c in category_stats
    ]

    # 3. 전체 통계
    total_deals = (
        db.query(Deal)
        .filter(Deal.status.in_(["open", "OPEN", "active", "ACTIVE"]))
        .count()
    )
    total_users = (
        db.query(func.count(func.distinct(Deal.creator_id)))
        .filter(Deal.created_at >= now - timedelta(days=30))
        .scalar()
    ) or 0
    total_completed = (
        db.query(Deal)
        .filter(Deal.status.in_(["completed", "COMPLETED"]))
        .count()
    )

    # 4. 최근 성사 사례
    recent_success = (
        db.query(Deal)
        .filter(Deal.status.in_(["completed", "COMPLETED"]))
        .order_by(desc(Deal.created_at))
        .limit(5)
        .all()
    )

    successes = []
    for d in recent_success:
        savings_pct = None
        tp = d.target_price or 0
        mp = d.market_price or (tp * 1.2 if tp else 0)
        if mp and tp and mp > 0:
            savings_pct = round((1 - tp / mp) * 100)
        successes.append({
            "title": d.product_name,
            "category": d.category or "기타",
            "savings_pct": savings_pct,
            "days_ago": (now - d.created_at).days if d.created_at else 0,
        })

    return {
        "top_demands": top_demands[:20],
        "categories": categories,
        "stats": {
            "total_active_deals": total_deals,
            "total_buyers_30d": total_users,
            "total_completed": total_completed,
        },
        "recent_successes": successes,
        "updated_at": str(now),
    }
