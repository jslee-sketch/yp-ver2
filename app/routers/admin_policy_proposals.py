# app/routers/admin_policy_proposals.py
"""
정책 제안서 CRUD + 적용/롤백.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import PolicyProposal

router = APIRouter(prefix="/admin/policy/proposals", tags=["admin-policy-proposals"])


class ProposalCreate(BaseModel):
    title: str
    description: str
    proposal_type: str
    target_param: Optional[str] = None
    current_value: Optional[str] = None
    proposed_value: Optional[str] = None
    evidence_summary: Optional[str] = None


class ProposalOut(BaseModel):
    id: int
    title: str
    description: str
    proposal_type: str
    target_param: Optional[str] = None
    current_value: Optional[str] = None
    proposed_value: Optional[str] = None
    status: str
    proposed_at: Optional[datetime] = None
    proposed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    review_note: Optional[str] = None
    applied_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReviewRequest(BaseModel):
    reviewed_by: str
    review_note: Optional[str] = None


class RollbackRequest(BaseModel):
    rollback_reason: str


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("", response_model=List[ProposalOut])
def list_proposals(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(PolicyProposal)
    if status:
        q = q.filter(PolicyProposal.status == status)
    return q.order_by(PolicyProposal.proposed_at.desc()).limit(100).all()


@router.get("/{proposal_id}", response_model=ProposalOut)
def get_proposal(proposal_id: int, db: Session = Depends(get_db)):
    p = db.query(PolicyProposal).filter(PolicyProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(404, "제안서를 찾을 수 없습니다")
    return p


@router.post("", response_model=ProposalOut, status_code=201)
def create_proposal(body: ProposalCreate, db: Session = Depends(get_db)):
    p = PolicyProposal(
        title=body.title,
        description=body.description,
        proposal_type=body.proposal_type,
        target_param=body.target_param,
        current_value=body.current_value,
        proposed_value=body.proposed_value,
        evidence_summary=body.evidence_summary,
        status="PROPOSED",
        proposed_at=_utcnow(),
        proposed_by="manual",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.post("/{proposal_id}/approve", response_model=ProposalOut)
def approve_proposal(proposal_id: int, body: ReviewRequest, db: Session = Depends(get_db)):
    p = db.query(PolicyProposal).filter(PolicyProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(404, "제안서를 찾을 수 없습니다")
    p.status = "APPROVED"
    p.reviewed_at = _utcnow()
    p.reviewed_by = body.reviewed_by
    p.review_note = body.review_note
    db.commit()
    db.refresh(p)
    return p


@router.post("/{proposal_id}/reject", response_model=ProposalOut)
def reject_proposal(proposal_id: int, body: ReviewRequest, db: Session = Depends(get_db)):
    p = db.query(PolicyProposal).filter(PolicyProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(404, "제안서를 찾을 수 없습니다")
    p.status = "REJECTED"
    p.reviewed_at = _utcnow()
    p.reviewed_by = body.reviewed_by
    p.review_note = body.review_note
    db.commit()
    db.refresh(p)
    return p


@router.post("/{proposal_id}/apply", response_model=ProposalOut)
def apply_proposal(proposal_id: int, db: Session = Depends(get_db)):
    p = db.query(PolicyProposal).filter(PolicyProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(404, "제안서를 찾을 수 없습니다")
    if p.status != "APPROVED":
        raise HTTPException(400, "APPROVED 상태만 적용 가능합니다")

    # YAML 백업 (가능한 경우)
    try:
        from app.services.yaml_version import backup_yaml, read_yaml_content
        target = (p.target_param or "").split(".")[0]
        if target:
            backup_path = backup_yaml(f"{target}.yaml")
            p.yaml_snapshot_before = read_yaml_content(f"{target}.yaml")
    except Exception:
        pass

    p.status = "APPLIED"
    p.applied_at = _utcnow()
    db.commit()
    db.refresh(p)
    return p


@router.post("/{proposal_id}/rollback", response_model=ProposalOut)
def rollback_proposal(proposal_id: int, body: RollbackRequest, db: Session = Depends(get_db)):
    p = db.query(PolicyProposal).filter(PolicyProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(404, "제안서를 찾을 수 없습니다")
    if p.status != "APPLIED":
        raise HTTPException(400, "APPLIED 상태만 롤백 가능합니다")
    p.status = "ROLLED_BACK"
    p.rolled_back_at = _utcnow()
    p.rollback_reason = body.rollback_reason
    db.commit()
    db.refresh(p)
    return p
