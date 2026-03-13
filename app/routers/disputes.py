"""분쟁 프로세스 v3 — 2라운드 AI 중재 라우터"""
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Dispute, User, Reservation
from app.services.dispute_service import (
    file_dispute, submit_round1_response, submit_decision,
    submit_round2_rebuttal, run_dispute_timeout_batch,
)
from app.services.working_days import working_days_left

router = APIRouter(prefix="/v3_6", tags=["disputes"])


@router.post("/disputes")
def api_file_dispute(body: dict, db: Session = Depends(get_db)):
    result = file_dispute(body, db)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.put("/disputes/{id}/round1-response")
def api_round1_response(id: int, body: dict, db: Session = Depends(get_db)):
    result = submit_round1_response(id, body, db)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.put("/disputes/{id}/decision")
def api_decision(id: int, body: dict, db: Session = Depends(get_db)):
    result = submit_decision(id, body["user_id"], body["decision"], db)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.put("/disputes/{id}/round2-rebuttal")
def api_round2_rebuttal(id: int, body: dict, db: Session = Depends(get_db)):
    result = submit_round2_rebuttal(id, body["user_id"], body, db)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.get("/disputes/{id}")
def api_get_dispute(id: int, db: Session = Depends(get_db)):
    d = db.query(Dispute).filter(Dispute.id == id).first()
    if not d:
        raise HTTPException(404)

    reservation = db.query(Reservation).filter(Reservation.id == d.reservation_id).first()

    deadline_map = {
        "ROUND1_RESPONSE": d.r1_respondent_deadline,
        "ROUND1_REVIEW": d.r1_initiator_deadline,
        "ROUND2_RESPONSE": d.r2_rebuttal_deadline,
        "ROUND2_REVIEW": d.r2_initiator_deadline,
    }
    current_deadline = deadline_map.get(d.status)

    def parse_explanation(raw):
        try:
            return json.loads(raw) if raw else {}
        except Exception:
            return {"raw": raw}

    result = {
        "id": d.id,
        "status": d.status,
        "current_round": d.current_round,
        "category": d.category,
        "title": d.title,
        "initiator": {"id": d.initiator_id, "role": d.initiator_role},
        "respondent": {"id": d.respondent_id},
        "reservation_id": d.reservation_id,
        "reservation_amount": getattr(reservation, "total_amount", 0) if reservation else 0,
        "description": d.description,
        "evidence": json.loads(d.evidence_urls or "[]"),
        "requested_resolution": d.requested_resolution,
        "requested_amount": d.requested_amount,
        "round1": {
            "response": d.r1_respondent_reply,
            "response_evidence": json.loads(d.r1_respondent_evidence_urls or "[]"),
            "proposal_type": d.r1_respondent_proposal_type,
            "proposal_amount": d.r1_respondent_proposal_amount,
            "deadline": str(d.r1_respondent_deadline) if d.r1_respondent_deadline else None,
            "ai_opinion": d.r1_ai_opinion,
            "ai_recommendation": d.r1_ai_recommendation,
            "ai_amount": d.r1_ai_recommendation_amount,
            "ai_explanation": parse_explanation(d.r1_ai_explanation),
            "initiator_decision": d.r1_initiator_decision,
            "respondent_decision": d.r1_respondent_decision,
        },
        "round2": {
            "rebuttal_by": d.r2_rebuttal_by,
            "initiator_rebuttal": d.r2_initiator_rebuttal,
            "respondent_rebuttal": d.r2_respondent_rebuttal,
            "deadline": str(d.r2_rebuttal_deadline) if d.r2_rebuttal_deadline else None,
            "ai_opinion": d.r2_ai_opinion,
            "ai_recommendation": d.r2_ai_recommendation,
            "ai_amount": d.r2_ai_recommendation_amount,
            "ai_explanation": parse_explanation(d.r2_ai_explanation),
            "initiator_decision": d.r2_initiator_decision,
            "respondent_decision": d.r2_respondent_decision,
        } if d.current_round >= 2 else None,
        "resolution": d.resolution,
        "resolution_amount": d.resolution_amount,
        "closed_at": str(d.closed_at) if d.closed_at else None,
        "closed_reason": d.closed_reason,
        "legal_guidance_sent": d.legal_guidance_sent,
        "current_deadline": str(current_deadline) if current_deadline else None,
        "days_remaining": working_days_left(current_deadline) if current_deadline else None,
        "created_at": str(d.created_at) if d.created_at else None,
    }
    return result


@router.get("/disputes")
def api_list_disputes(
    status: str = Query(None),
    user_id: int = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Dispute)
    if status:
        query = query.filter(Dispute.status == status)
    if user_id:
        query = query.filter(
            (Dispute.initiator_id == user_id) | (Dispute.respondent_id == user_id)
        )
    disputes = query.order_by(Dispute.created_at.desc()).all()
    return [
        {
            "id": d.id,
            "status": d.status,
            "category": d.category,
            "title": d.title,
            "current_round": d.current_round,
            "initiator_id": d.initiator_id,
            "respondent_id": d.respondent_id,
            "created_at": str(d.created_at) if d.created_at else None,
        }
        for d in disputes
    ]


@router.post("/disputes/batch/timeout")
def api_timeout_batch(db: Session = Depends(get_db)):
    return run_dispute_timeout_batch(db)
