# app/routers/admin_simulate_status.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models

router = APIRouter(prefix="/admin/simulate", tags=["admin", "simulate"])

@router.get("/status", summary="시뮬레이션/DB 상태 요약")
def simulate_status(db: Session = Depends(get_db)):
    deals = db.query(models.Deal).all()
    offers = db.query(models.Offer).all()

    deal_summaries = []
    for d in deals:
        participants = db.query(models.DealParticipant).filter(models.DealParticipant.deal_id == d.id).count()
        off = db.query(models.Offer).filter(models.Offer.deal_id == d.id).count()
        deal_summaries.append({
            "deal_id": d.id,
            "product_name": d.product_name,
            "participants": participants,
            "offers": off,
            "status": getattr(d, "status", "open"),
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "deadline_at": d.deadline_at.isoformat() if getattr(d, "deadline_at", None) else None
        })

    return {
        "totals": {
            "deals": len(deals),
            "offers": len(offers),
        },
        "deal_summaries": deal_summaries
    }