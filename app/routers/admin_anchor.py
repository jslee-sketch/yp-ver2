# app/routers/admin_anchor.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.database import get_db
from app import models

from app.policy.pricing_guardrail_hook import (
    run_pricing_guardrail,
    apply_guardrail_to_deal,
    log_guardrail_evidence,
)

router = APIRouter(prefix="/admin/anchor", tags=["admin-anchor"])

@router.post("/deal/{deal_id}")
def admin_set_deal_anchor(
    deal_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db),
):
    """
    DEV/ADMIN: deal에 anchor_price를 주입하고(S3),
    즉시 guardrail 평가→deal 반영→evidence 로그까지 수행.
    """
    deal = db.get(models.Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    anchor_price = body.get("anchor_price")
    anchor_confidence = body.get("anchor_confidence", 1.0)
    evidence_score = body.get("evidence_score", 0)


    # 1) Deal에 컬럼이 있으면 저장 (없으면 스킵)
    # --- persist anchor onto Deal if fields exist ---
    if anchor_price is not None and hasattr(deal, "anchor_price"):
        setattr(deal, "anchor_price", float(anchor_price))
    if anchor_confidence is not None and hasattr(deal, "anchor_confidence"):
        setattr(deal, "anchor_confidence", float(anchor_confidence or 1.0))
    if evidence_score is not None and hasattr(deal, "evidence_score"):
        setattr(deal, "evidence_score", int(evidence_score or 0))

    db.add(deal)
    db.commit()
    db.refresh(deal)

    # 2) ✅ S3: anchor 도착 직후 guardrail 평가/적용/로그
    result = run_pricing_guardrail(
        deal_id=int(deal.id),
        category=getattr(deal, "category", None),
        target_price=getattr(deal, "target_price", None),
        anchor_price=getattr(deal, "anchor_price", None),  # ✅ 저장값 기준으로 평가
        evidence_score=getattr(deal, "evidence_score", 0) or 0,
        anchor_confidence=getattr(deal, "anchor_confidence", 1.0) or 1.0,
    )
    apply_guardrail_to_deal(db, deal, result)
    log_guardrail_evidence(db, deal_id=int(deal.id), result=result, anchor_version="S3_ANCHOR_ARRIVED")

    return {
        "ok": True,
        "deal_id": int(deal.id),
        "target_price": getattr(deal, "target_price", None),
        "anchor_price": getattr(deal, "anchor_price", None),
        "guardrail": {
            "level": getattr(result, "level", None),
            "reason_codes": getattr(result, "reason_codes", []),
            "ui": getattr(result, "ui", None),
            "ops": getattr(result, "ops", None),
        },
    }