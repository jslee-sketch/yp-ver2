# app/routers/deals.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import crud, schemas, database, models

router = APIRouter(prefix="/deals", tags=["deals"])
get_db = database.get_db


# ---------------------------
# 🟢 Deal 생성
# ---------------------------
@router.post("/", response_model=schemas.DealOut)
def create_deal(deal_in: schemas.DealCreate, db: Session = Depends(get_db)):
    deal = models.Deal(
        product_name=deal_in.product_name,
        creator_id=deal_in.creator_id,
        desired_qty=deal_in.desired_qty,
        target_price=deal_in.target_price,
        max_budget=deal_in.max_budget,
        free_text=deal_in.free_text,
    )
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal


# ---------------------------
# 📋 Deal 목록 조회
# ---------------------------
@router.get("/", response_model=List[schemas.DealOut])
def read_deals(skip: int = 0, limit: int = 10, db: Session = Depends(get_db)):
    return crud.get_deals(db, skip=skip, limit=limit)


# ---------------------------
# 🔍 특정 Deal 상세조회
# ---------------------------
@router.get("/{deal_id}", response_model=schemas.DealDetail)
def read_deal(deal_id: int, db: Session = Depends(get_db)):
    db_deal = crud.get_deal(db, deal_id=deal_id)
    if not db_deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    return db_deal


# ---------------------------
# ➕ Deal 참여자 추가
# ---------------------------
@router.post("/{deal_id}/participants", response_model=schemas.DealParticipantOut)
def add_participant(
    deal_id: int,
    participant: schemas.DealParticipantCreate,
    db: Session = Depends(get_db),
):
    # deal_id 강제 설정 (schemas.DealParticipantCreate에 포함되었더라도 덮어쓰기)
    participant.deal_id = deal_id
    db_participant = crud.add_participant(db=db, participant=participant)
    return db_participant


# ---------------------------
# 📋 Deal 참여자 목록 조회
# ---------------------------
@router.get("/{deal_id}/participants", response_model=List[schemas.DealParticipantOut])
def read_deal_participants(deal_id: int, db: Session = Depends(get_db)):
    participants = crud.get_deal_participants(db=db, deal_id=deal_id)
    return participants


# ---------------------------
# ❌ Deal 참여자 삭제 (참여 취소)
# ---------------------------
@router.delete("/participants/{participant_id}")
def remove_participant(participant_id: int, db: Session = Depends(get_db)):
    result = crud.remove_participant(db=db, participant_id=participant_id)
    if not result:
        raise HTTPException(status_code=404, detail="Participant not found or already removed")
    return result