from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    DonzzulActuator, DonzzulStore, DonzzulDeal, DonzzulVoucher,
    DonzzulVoteWeek, DonzzulVote, DonzzulSettlement, DonzzulChatMessage
)
from datetime import datetime, timedelta
import json

router = APIRouter(prefix="/donzzul", tags=["donzzul"])

# ============================================================
# 가게
# ============================================================

@router.post("/stores")
def create_store(body: dict, db: Session = Depends(get_db)):
    """가게 추천 등록 (돈쭐 히어로)"""
    # 유효성 검증
    required = ["store_name", "store_address", "store_phone",
                "owner_name", "owner_phone",
                "bank_name", "account_number", "account_holder",
                "story_text"]
    for field in required:
        if not str(body.get(field, "")).strip():
            raise HTTPException(400, f"{field}은(는) 필수입니다")

    # 사연 최소 길이
    story = body.get("story_text", "")
    min_length = 50
    try:
        from app.policy.runtime import load_defaults
        policy = load_defaults()
        min_length = policy.get("donzzul", {}).get("deal_min_story_length", 50)
    except Exception:
        pass
    if len(story.strip()) < min_length:
        raise HTTPException(400, f"사연은 최소 {min_length}자 이상 작성해주세요")

    # 중복 체크 (주소 + 전화번호)
    existing = db.query(DonzzulStore).filter(
        DonzzulStore.store_address == body["store_address"],
        DonzzulStore.store_phone == body["store_phone"],
        DonzzulStore.status.notin_(["REJECTED", "CLOSED"]),
    ).first()
    if existing:
        raise HTTPException(409, "이미 등록된 가게입니다")

    # 히어로 확인
    hero = db.query(DonzzulActuator).filter(
        DonzzulActuator.user_id == body.get("registered_by_user_id")
    ).first()

    photos = body.get("store_photos", [])

    store = DonzzulStore(
        store_name=body["store_name"].strip(),
        store_address=body["store_address"].strip(),
        store_phone=body["store_phone"].strip(),
        store_lat=body.get("store_lat"),
        store_lng=body.get("store_lng"),
        store_photos=json.dumps(photos) if isinstance(photos, list) else photos,
        store_category=body.get("store_category", ""),
        owner_name=body["owner_name"].strip(),
        owner_phone=body["owner_phone"].strip(),
        owner_consent=body.get("owner_consent", False),
        bank_name=body["bank_name"].strip(),
        account_number=body["account_number"].strip(),
        account_holder=body["account_holder"].strip(),
        business_number=str(body.get("business_number", "")).strip() or None,
        story_text=story.strip(),
        youtube_url=str(body.get("youtube_url", "")).strip() or None,
        registered_by=hero.id if hero else None,
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


@router.put("/stores/{store_id}/verify")
def verify_store(store_id: int, body: dict, db: Session = Depends(get_db)):
    """가게 검증 — 승인/거절 (관리자)"""
    store = db.query(DonzzulStore).filter(DonzzulStore.id == store_id).first()
    if not store:
        raise HTTPException(404, "가게를 찾을 수 없습니다")

    action = body.get("action")  # "approve" or "reject"

    if action == "approve":
        store.status = "APPROVED"
        store.verified_at = datetime.utcnow()
        store.verified_by = body.get("admin_id")
        store.verification_notes = body.get("notes", "")
        store.owner_consent = True
        store.owner_consent_at = datetime.utcnow()
        store.owner_consent_method = body.get("consent_method", "phone")
        store.account_verified = body.get("account_verified", False)

        # 히어로 포인트 적립
        hero = db.query(DonzzulActuator).filter(
            DonzzulActuator.id == store.registered_by
        ).first()
        if hero:
            points = 500
            levels = {}
            try:
                from app.policy.runtime import load_defaults
                policy = load_defaults()
                donzzul = policy.get("donzzul", {})
                points = donzzul.get("hero_points_per_store", 500)
                levels = donzzul.get("hero_levels", {})
            except Exception:
                pass

            hero.total_stores = (hero.total_stores or 0) + 1
            hero.total_points = (hero.total_points or 0) + points

            # 레벨 체크
            for level_key in ["legend", "super", "good", "sprout"]:
                level_info = levels.get(level_key, {})
                if hero.total_stores >= level_info.get("min_stores", 999):
                    hero.hero_level = level_key
                    break

        # 돈쭐 딜 자동 생성 (Phase 1: 투표 없이 바로 오픈)
        deal_duration = 7
        try:
            from app.policy.runtime import load_defaults
            policy = load_defaults()
            deal_duration = policy.get("donzzul", {}).get("deal_duration_days", 7)
        except Exception:
            pass

        deal = DonzzulDeal(
            store_id=store.id,
            title=f"{store.store_name} 응원하기",
            starts_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=deal_duration),
            status="OPEN",
            created_by=store.registered_by,
        )
        db.add(deal)

    elif action == "reject":
        store.status = "REJECTED"
        store.verification_notes = body.get("notes", "거절 사유 미입력")
    else:
        raise HTTPException(400, "action은 'approve' 또는 'reject'이어야 합니다")

    db.commit()
    db.refresh(store)
    return store


@router.put("/stores/{store_id}/set-pin")
def set_store_pin(store_id: int, body: dict, db: Session = Depends(get_db)):
    """사장님 비밀번호 설정 (관리자 — 전화 후)"""
    store = db.query(DonzzulStore).filter(DonzzulStore.id == store_id).first()
    if not store:
        raise HTTPException(404, "가게를 찾을 수 없습니다")

    pin = str(body.get("pin", ""))
    if len(pin) != 4 or not pin.isdigit():
        raise HTTPException(400, "비밀번호는 4자리 숫자여야 합니다")

    from hashlib import sha256
    store.store_pin_hash = sha256(pin.encode()).hexdigest()
    store.store_pin_set_at = datetime.utcnow()

    db.commit()
    return {"ok": True, "message": "비밀번호 설정 완료"}


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
