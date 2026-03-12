from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    DonzzulActuator, DonzzulStore, DonzzulDeal, DonzzulVoucher,
    DonzzulVoteWeek, DonzzulVote, DonzzulSettlement, DonzzulChatMessage
)
from datetime import datetime

router = APIRouter(prefix="/donzzul", tags=["donzzul"])

# ============================================================
# 가게
# ============================================================

@router.post("/stores")
def create_store(body: dict, db: Session = Depends(get_db)):
    """가게 추천 등록 (돈쭐 히어로)"""
    store = DonzzulStore(
        store_name=body.get("store_name"),
        store_address=body.get("store_address"),
        store_phone=body.get("store_phone"),
        store_lat=body.get("store_lat"),
        store_lng=body.get("store_lng"),
        store_category=body.get("store_category"),
        owner_name=body.get("owner_name"),
        owner_phone=body.get("owner_phone"),
        bank_name=body.get("bank_name"),
        account_number=body.get("account_number"),
        account_holder=body.get("account_holder"),
        story_text=body.get("story_text", ""),
        youtube_url=body.get("youtube_url"),
        registered_by=body.get("registered_by"),
        status="REVIEWING",
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


@router.get("/stores")
def list_stores(status: str = Query(None), db: Session = Depends(get_db)):
    """가게 목록"""
    q = db.query(DonzzulStore)
    if status:
        q = q.filter(DonzzulStore.status == status)
    return q.order_by(DonzzulStore.created_at.desc()).all()


@router.get("/stores/{store_id}")
def get_store(store_id: int, db: Session = Depends(get_db)):
    """가게 상세"""
    store = db.query(DonzzulStore).filter(DonzzulStore.id == store_id).first()
    if not store:
        raise HTTPException(404, "가게를 찾을 수 없습니다")
    return store


# ============================================================
# 딜
# ============================================================

@router.get("/deals")
def list_deals(status: str = Query(None), db: Session = Depends(get_db)):
    """돈쭐 딜 목록"""
    q = db.query(DonzzulDeal)
    if status:
        q = q.filter(DonzzulDeal.status == status)
    return q.order_by(DonzzulDeal.created_at.desc()).all()


@router.get("/deals/{deal_id}")
def get_deal(deal_id: int, db: Session = Depends(get_db)):
    """돈쭐 딜 상세"""
    deal = db.query(DonzzulDeal).filter(DonzzulDeal.id == deal_id).first()
    if not deal:
        raise HTTPException(404, "딜을 찾을 수 없습니다")

    store = db.query(DonzzulStore).filter(DonzzulStore.id == deal.store_id).first()
    messages = db.query(DonzzulChatMessage).filter(
        DonzzulChatMessage.deal_id == deal_id
    ).order_by(DonzzulChatMessage.created_at.desc()).limit(50).all()

    return {
        "deal": deal,
        "store": store,
        "recent_messages": messages,
    }


# ============================================================
# 상품권
# ============================================================

@router.get("/vouchers/my")
def my_vouchers(buyer_id: int = Query(...), db: Session = Depends(get_db)):
    """내 상품권함"""
    return db.query(DonzzulVoucher).filter(
        DonzzulVoucher.buyer_id == buyer_id
    ).order_by(DonzzulVoucher.created_at.desc()).all()


# ============================================================
# 히어로
# ============================================================

@router.post("/actuators/register")
def register_hero(body: dict, db: Session = Depends(get_db)):
    """돈쭐 히어로 등록"""
    existing = db.query(DonzzulActuator).filter(
        DonzzulActuator.user_id == body.get("user_id")
    ).first()
    if existing:
        return existing

    hero = DonzzulActuator(
        user_id=body.get("user_id"),
        actuator_id=body.get("actuator_id"),
    )
    db.add(hero)
    db.commit()
    db.refresh(hero)
    return hero


@router.get("/actuators/me")
def my_hero_info(user_id: int = Query(...), db: Session = Depends(get_db)):
    """내 히어로 정보"""
    hero = db.query(DonzzulActuator).filter(
        DonzzulActuator.user_id == user_id
    ).first()
    if not hero:
        raise HTTPException(404, "돈쭐 히어로로 등록되지 않았습니다")
    return hero


@router.get("/actuators/ranking")
def hero_ranking(db: Session = Depends(get_db)):
    """히어로 랭킹"""
    return db.query(DonzzulActuator).filter(
        DonzzulActuator.status == "ACTIVE"
    ).order_by(DonzzulActuator.total_stores.desc()).limit(20).all()


# ============================================================
# 투표 (Phase 2용 — 현재 비활성)
# ============================================================

@router.get("/votes/current-week")
def current_vote(db: Session = Depends(get_db)):
    """이번 주 투표"""
    week = db.query(DonzzulVoteWeek).filter(
        DonzzulVoteWeek.status.in_(["VOTING", "UPCOMING"])
    ).order_by(DonzzulVoteWeek.created_at.desc()).first()
    return week


# ============================================================
# 정산
# ============================================================

@router.get("/settlements")
def list_settlements(db: Session = Depends(get_db)):
    """정산 목록 (관리자)"""
    return db.query(DonzzulSettlement).order_by(
        DonzzulSettlement.created_at.desc()
    ).all()


# ============================================================
# 채팅
# ============================================================

@router.get("/deals/{deal_id}/chat/messages")
def get_chat_messages(deal_id: int, limit: int = Query(50), db: Session = Depends(get_db)):
    """채팅 기록"""
    return db.query(DonzzulChatMessage).filter(
        DonzzulChatMessage.deal_id == deal_id
    ).order_by(DonzzulChatMessage.created_at.desc()).limit(limit).all()


@router.post("/deals/{deal_id}/chat/messages")
def post_chat_message(deal_id: int, body: dict, db: Session = Depends(get_db)):
    """메시지 전송"""
    msg = DonzzulChatMessage(
        deal_id=deal_id,
        sender_id=body.get("sender_id"),
        message_type=body.get("message_type", "CHEER"),
        content=body.get("content", ""),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
