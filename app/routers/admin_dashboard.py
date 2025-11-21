# app/routers/admin_dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
from datetime import datetime

router = APIRouter(prefix="/admin/dashboard", tags=["admin", "dashboard"])

@router.get("/")
def get_admin_dashboard(db: Session = Depends(get_db)):
    total_buyers = db.query(models.Buyer).count()
    total_sellers = db.query(models.Seller).count()
    total_deals = db.query(models.Deal).count()
    total_offers = db.query(models.Offer).count()

    total_buyer_points = sum([b.points for b in db.query(models.Buyer).all()])
    total_seller_points = sum([s.points for s in db.query(models.Seller).all()])

    recent_deals = db.query(models.Deal).order_by(models.Deal.created_at.desc()).limit(5).all()
    recent_offers = db.query(models.Offer).order_by(models.Offer.created_at.desc()).limit(5).all()

    return {
        "meta": {"timestamp": datetime.utcnow().isoformat()},
        "summary": {
            "buyers": total_buyers,
            "sellers": total_sellers,
            "deals": total_deals,
            "offers": total_offers,
            "buyer_points_total": total_buyer_points,
            "seller_points_total": total_seller_points,
        },
        "recent": {
            "deals": [
                {"id": d.id, "product_name": d.product_name, "created_at": d.created_at}
                for d in recent_deals
            ],
            "offers": [
                {"id": o.id, "deal_id": o.deal_id, "price": o.price, "created_at": o.created_at}
                for o in recent_offers
            ],
        },
    }