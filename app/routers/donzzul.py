from fastapi import APIRouter, Depends, HTTPException, Query  # Sprint5 채팅
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    DonzzulActuator, DonzzulStore, DonzzulDeal, DonzzulVoucher,
    DonzzulVoteWeek, DonzzulVote, DonzzulSettlement, DonzzulChatMessage
)
from datetime import datetime, timedelta
from hashlib import sha256
import json
import secrets

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
    """돈쭐 딜 상세 (사연/사진/달성률/응원 메시지)"""
    deal = db.query(DonzzulDeal).filter(DonzzulDeal.id == deal_id).first()
    if not deal:
        raise HTTPException(404, "딜을 찾을 수 없습니다")

    store = db.query(DonzzulStore).filter(DonzzulStore.id == deal.store_id).first()

    # 최근 응원 메시지 (상품권 cheer_message)
    cheer_vouchers = db.query(DonzzulVoucher).filter(
        DonzzulVoucher.deal_id == deal_id,
        DonzzulVoucher.cheer_message != None,
        DonzzulVoucher.cheer_message != "",
    ).order_by(DonzzulVoucher.created_at.desc()).limit(20).all()

    # 달성률
    target = deal.target_amount or 0
    current = deal.current_amount or 0
    progress = round((current / target * 100), 1) if target > 0 else 0

    return {
        "deal": {
            "id": deal.id,
            "title": deal.title,
            "status": deal.status,
            "target_amount": target,
            "current_amount": current,
            "progress": min(progress, 100),
            "voucher_count": deal.voucher_count or 0,
            "starts_at": str(deal.starts_at),
            "expires_at": str(deal.expires_at),
        },
        "store": {
            "id": store.id,
            "store_name": store.store_name,
            "store_address": store.store_address,
            "store_phone": store.store_phone,
            "store_category": store.store_category,
            "story_text": store.story_text,
            "youtube_url": store.youtube_url,
            "store_photos": json.loads(store.store_photos) if store.store_photos else [],
        } if store else None,
        "cheer_messages": [
            {"message": m.cheer_message, "amount": m.amount, "created_at": str(m.created_at)}
            for m in cheer_vouchers
        ],
    }


# ============================================================
# 상품권
# ============================================================

def _load_donzzul_policy() -> dict:
    try:
        from app.policy.runtime import load_defaults
        policy = load_defaults()
        return policy.get("donzzul", {})
    except Exception:
        return {}


@router.post("/vouchers/purchase")
def purchase_voucher(body: dict, db: Session = Depends(get_db)):
    """상품권 구매"""
    deal_id = body.get("deal_id")
    buyer_id = body.get("buyer_id")
    amount = body.get("amount")
    cheer_message = body.get("cheer_message", "")

    # 딜 존재 + OPEN 확인
    deal = db.query(DonzzulDeal).filter(DonzzulDeal.id == deal_id).first()
    if not deal or deal.status != "OPEN":
        raise HTTPException(400, "구매 가능한 딜이 아닙니다")

    # 딜 만료 확인
    if deal.expires_at and deal.expires_at < datetime.utcnow():
        raise HTTPException(400, "마감된 딜입니다")

    # 금액 검증
    policy = _load_donzzul_policy()
    allowed = policy.get("voucher_amounts", [10000, 20000, 50000])
    if amount not in allowed:
        raise HTTPException(400, f"허용 금액: {allowed}")

    # 상품권 코드 생성 (DONZZUL-XXXX-XXXX)
    prefix = policy.get("voucher_code_prefix", "DONZZUL")
    while True:
        code = f"{prefix}-{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
        if not db.query(DonzzulVoucher).filter(DonzzulVoucher.code == code).first():
            break

    # PIN 생성 (4자리 랜덤)
    pin_length = policy.get("voucher_pin_length", 4)
    pin_plain = ''.join([str(secrets.randbelow(10)) for _ in range(pin_length)])
    pin_hash = sha256(pin_plain.encode()).hexdigest()

    # 유효기간
    expiry_days = policy.get("voucher_expiry_days", 90)
    expires_at = datetime.utcnow() + timedelta(days=expiry_days)

    voucher = DonzzulVoucher(
        code=code,
        deal_id=deal.id,
        store_id=deal.store_id,
        buyer_id=buyer_id,
        amount=amount,
        remaining_amount=amount,
        pin_hash=pin_hash,
        cheer_message=cheer_message[:200] if cheer_message else None,
        status="ACTIVE",
        expires_at=expires_at,
    )
    db.add(voucher)

    # 딜 금액/건수 업데이트
    deal.current_amount = (deal.current_amount or 0) + amount
    deal.voucher_count = (deal.voucher_count or 0) + 1

    db.commit()
    db.refresh(voucher)

    store = db.query(DonzzulStore).filter(DonzzulStore.id == deal.store_id).first()
    return {
        "voucher_id": voucher.id,
        "code": voucher.code,
        "pin": pin_plain,  # 구매 시에만 1회 반환
        "amount": voucher.amount,
        "expires_at": str(voucher.expires_at),
        "store_name": store.store_name if store else "",
    }


@router.post("/vouchers/{code}/redeem")
def redeem_voucher(code: str, body: dict, db: Session = Depends(get_db)):
    """상품권 사용 확정 (사장님 비밀번호 입력)"""
    voucher = db.query(DonzzulVoucher).filter(DonzzulVoucher.code == code).first()
    if not voucher:
        raise HTTPException(404, "상품권을 찾을 수 없습니다")

    if voucher.status != "ACTIVE":
        raise HTTPException(400, f"사용할 수 없는 상품권입니다 (상태: {voucher.status})")

    # 유효기간 확인
    if voucher.expires_at < datetime.utcnow():
        raise HTTPException(400, "유효기간이 만료된 상품권입니다")

    # 잠금 확인
    if voucher.pin_locked_until and voucher.pin_locked_until > datetime.utcnow():
        remaining = (voucher.pin_locked_until - datetime.utcnow()).seconds // 60
        raise HTTPException(423, f"비밀번호 오류로 {remaining}분간 잠금 상태입니다")

    # 가게 비밀번호 검증
    store = db.query(DonzzulStore).filter(DonzzulStore.id == voucher.store_id).first()
    if not store or not store.store_pin_hash:
        raise HTTPException(500, "가게 비밀번호가 설정되지 않았습니다")

    input_pin = body.get("store_pin", "")
    input_pin_hash = sha256(input_pin.encode()).hexdigest()

    if input_pin_hash != store.store_pin_hash:
        # 오류 횟수 증가
        voucher.pin_attempts = (voucher.pin_attempts or 0) + 1

        policy = _load_donzzul_policy()
        max_attempts = policy.get("voucher_pin_max_attempts", 5)
        lock_minutes = policy.get("voucher_pin_lock_minutes", 30)

        if voucher.pin_attempts >= max_attempts:
            voucher.pin_locked_until = datetime.utcnow() + timedelta(minutes=lock_minutes)
            db.commit()
            raise HTTPException(423, f"비밀번호 {max_attempts}회 오류! {lock_minutes}분간 잠금됩니다")

        remaining = max_attempts - voucher.pin_attempts
        db.commit()
        raise HTTPException(401, f"비밀번호가 틀렸습니다 (남은 시도: {remaining}회)")

    # 성공! 사용 처리
    voucher.status = "USED"
    voucher.used_at = datetime.utcnow()
    voucher.remaining_amount = 0
    voucher.pin_attempts = 0
    voucher.pin_locked_until = None

    # 위치 정보 (있으면)
    voucher.used_location_lat = body.get("lat")
    voucher.used_location_lng = body.get("lng")

    db.commit()

    return {
        "status": "USED",
        "message": "사용 완료! 감사합니다 💚",
        "store_name": store.store_name,
        "amount": voucher.amount,
    }


@router.get("/vouchers/my")
def my_vouchers(buyer_id: int = Query(...), db: Session = Depends(get_db)):
    """내 상품권함"""
    vouchers = db.query(DonzzulVoucher).filter(
        DonzzulVoucher.buyer_id == buyer_id
    ).order_by(DonzzulVoucher.created_at.desc()).all()

    result = []
    for v in vouchers:
        store = db.query(DonzzulStore).filter(DonzzulStore.id == v.store_id).first()
        result.append({
            "id": v.id,
            "code": v.code,
            "amount": v.amount,
            "remaining_amount": v.remaining_amount,
            "status": v.status,
            "store_name": store.store_name if store else "알 수 없음",
            "store_address": store.store_address if store else "",
            "expires_at": str(v.expires_at),
            "used_at": str(v.used_at) if v.used_at else None,
            "cheer_message": v.cheer_message,
            "created_at": str(v.created_at),
            "days_left": max(0, (v.expires_at - datetime.utcnow()).days) if v.expires_at else 0,
        })

    return result


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
# 투표
# ============================================================

@router.get("/votes/current-week")
def current_vote(db: Session = Depends(get_db)):
    """이번 주 투표 (VOTING 상태 우선, 없으면 UPCOMING)"""
    week = db.query(DonzzulVoteWeek).filter(
        DonzzulVoteWeek.status.in_(["VOTING", "UPCOMING"])
    ).order_by(DonzzulVoteWeek.created_at.desc()).first()
    if not week:
        return None
    return _vote_week_response(week, db)


@router.get("/votes/weeks")
def list_vote_weeks(status: str = Query(None), db: Session = Depends(get_db)):
    """투표 주차 목록"""
    q = db.query(DonzzulVoteWeek)
    if status:
        q = q.filter(DonzzulVoteWeek.status == status)
    weeks = q.order_by(DonzzulVoteWeek.created_at.desc()).limit(20).all()
    return [_vote_week_response(w, db) for w in weeks]


@router.get("/votes/weeks/{week_id}")
def get_vote_week(week_id: int, db: Session = Depends(get_db)):
    """투표 주차 상세"""
    week = db.query(DonzzulVoteWeek).filter(DonzzulVoteWeek.id == week_id).first()
    if not week:
        raise HTTPException(404, "투표 주차를 찾을 수 없습니다")
    return _vote_week_response(week, db)


@router.post("/votes/weeks")
def create_vote_week(body: dict, db: Session = Depends(get_db)):
    """투표 주차 생성 (관리자)"""
    week_label = body.get("week_label", "")
    if not week_label:
        raise HTTPException(400, "week_label은 필수입니다")

    # 후보 가게 ID 목록
    candidate_ids = body.get("candidate_store_ids", [])
    if len(candidate_ids) < 2:
        raise HTTPException(400, "최소 2개 이상의 후보 가게가 필요합니다")

    # 후보 가게 존재 확인
    for sid in candidate_ids:
        store = db.query(DonzzulStore).filter(DonzzulStore.id == sid, DonzzulStore.status == "APPROVED").first()
        if not store:
            raise HTTPException(400, f"가게 ID {sid}는 승인된 가게가 아닙니다")

    # 투표 기간
    policy = _load_donzzul_policy()
    vote_duration = policy.get("vote_duration_days", 7)
    vote_start = datetime.utcnow()
    vote_end = vote_start + timedelta(days=vote_duration)

    week = DonzzulVoteWeek(
        week_label=week_label,
        vote_start=vote_start,
        vote_end=vote_end,
        candidates=json.dumps(candidate_ids),
        status="VOTING",
        total_votes=0,
    )
    db.add(week)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"DB commit error: {e}")
    db.refresh(week)
    try:
        return _vote_week_response(week, db)
    except Exception as e:
        raise HTTPException(500, f"Response error: {e}")


@router.post("/votes/cast")
def cast_vote(body: dict, db: Session = Depends(get_db)):
    """투표하기"""
    week_id = body.get("week_id")
    voter_id = body.get("voter_id")
    store_id = body.get("store_id")

    if not week_id or not store_id:
        raise HTTPException(400, "week_id와 store_id는 필수입니다")

    week = db.query(DonzzulVoteWeek).filter(DonzzulVoteWeek.id == week_id).first()
    if not week:
        raise HTTPException(404, "투표 주차를 찾을 수 없습니다")
    if week.status != "VOTING":
        raise HTTPException(400, "현재 투표 중이 아닙니다")

    # 후보 확인
    candidates = json.loads(week.candidates or "[]")
    if store_id not in candidates:
        raise HTTPException(400, "해당 가게는 이번 주 후보가 아닙니다")

    # 중복 투표 확인
    if voter_id:
        existing = db.query(DonzzulVote).filter(
            DonzzulVote.week_id == week_id,
            DonzzulVote.voter_id == voter_id,
        ).first()
        if existing:
            raise HTTPException(409, "이미 이번 주에 투표하셨습니다")

    # 가중치 계산 (히어로 레벨에 따라)
    weight = 1
    if voter_id:
        hero = db.query(DonzzulActuator).filter(DonzzulActuator.user_id == voter_id).first()
        if hero:
            policy = _load_donzzul_policy()
            vote_weights = policy.get("vote_weights", {})
            weight = vote_weights.get(hero.hero_level or "sprout", 1)

    vote = DonzzulVote(
        week_id=week_id,
        voter_id=voter_id,
        store_id=store_id,
        weight=weight,
    )
    db.add(vote)

    week.total_votes = (week.total_votes or 0) + weight
    db.commit()
    db.refresh(vote)

    return {
        "vote_id": vote.id,
        "week_id": week_id,
        "store_id": store_id,
        "weight": weight,
        "message": f"투표 완료! (가중치: {weight}표)",
    }


@router.post("/votes/weeks/{week_id}/close")
def close_vote_week(week_id: int, body: dict = {}, db: Session = Depends(get_db)):
    """투표 마감 + 결과 집계 + 자동 딜 생성 (관리자)"""
    week = db.query(DonzzulVoteWeek).filter(DonzzulVoteWeek.id == week_id).first()
    if not week:
        raise HTTPException(404, "투표 주차를 찾을 수 없습니다")
    if week.status not in ("VOTING", "UPCOMING"):
        raise HTTPException(400, "이미 마감된 투표입니다")

    # 투표 집계
    votes = db.query(DonzzulVote).filter(DonzzulVote.week_id == week_id).all()
    store_scores: dict = {}
    for v in votes:
        store_scores[v.store_id] = store_scores.get(v.store_id, 0) + (v.weight or 1)

    # 정렬
    ranked = sorted(store_scores.items(), key=lambda x: x[1], reverse=True)

    # 상위 3개 저장
    if len(ranked) >= 1:
        week.rank_1_store_id = ranked[0][0]
    if len(ranked) >= 2:
        week.rank_2_store_id = ranked[1][0]
    if len(ranked) >= 3:
        week.rank_3_store_id = ranked[2][0]

    week.status = "CLOSED"
    week.announced_at = datetime.utcnow()

    # 1위 가게에 자동 딜 생성
    created_deals = []
    policy = _load_donzzul_policy()
    top_n = body.get("auto_deal_count", policy.get("vote_auto_deal_top_n", 1))

    for i in range(min(top_n, len(ranked))):
        store_id = ranked[i][0]
        store = db.query(DonzzulStore).filter(DonzzulStore.id == store_id).first()
        if not store:
            continue

        # 이미 OPEN 딜이 있으면 스킵
        existing_deal = db.query(DonzzulDeal).filter(
            DonzzulDeal.store_id == store_id,
            DonzzulDeal.status == "OPEN",
        ).first()
        if existing_deal:
            created_deals.append({"store_id": store_id, "deal_id": existing_deal.id, "status": "already_open"})
            continue

        deal_duration = policy.get("deal_duration_days", 7)
        deal = DonzzulDeal(
            store_id=store_id,
            title=f"{store.store_name} 응원하기 (투표 선정)",
            starts_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=deal_duration),
            status="OPEN",
        )
        db.add(deal)
        db.flush()
        created_deals.append({"store_id": store_id, "deal_id": deal.id, "status": "created"})

    db.commit()

    return {
        "week_id": week_id,
        "status": "CLOSED",
        "total_votes": week.total_votes,
        "ranking": [{"store_id": sid, "score": score, "rank": i+1} for i, (sid, score) in enumerate(ranked)],
        "created_deals": created_deals,
    }


def _vote_week_response(week, db):
    """투표 주차 응답 구성"""
    candidates = json.loads(week.candidates or "[]")
    candidate_stores = []
    for sid in candidates:
        store = db.query(DonzzulStore).filter(DonzzulStore.id == sid).first()
        # 해당 가게 득표수
        votes = db.query(DonzzulVote).filter(
            DonzzulVote.week_id == week.id,
            DonzzulVote.store_id == sid,
        ).all()
        score = sum(v.weight or 1 for v in votes)

        candidate_stores.append({
            "store_id": sid,
            "store_name": store.store_name if store else "알 수 없음",
            "story_text": (store.story_text[:100] + "...") if store and store.story_text and len(store.story_text) > 100 else (store.story_text if store else ""),
            "score": score,
        })

    return {
        "id": week.id,
        "week_label": week.week_label,
        "vote_start": str(week.vote_start),
        "vote_end": str(week.vote_end),
        "status": week.status,
        "total_votes": week.total_votes,
        "candidates": candidate_stores,
        "rank_1_store_id": week.rank_1_store_id,
        "rank_2_store_id": week.rank_2_store_id,
        "rank_3_store_id": week.rank_3_store_id,
        "announced_at": str(week.announced_at) if week.announced_at else None,
    }


# ============================================================
# 배치
# ============================================================

@router.post("/batch/expiry")
def batch_expiry(db: Session = Depends(get_db)):
    """상품권 만료 처리 배치 (매일 자정)"""
    from app.services.donzzul_batch import run_donzzul_expiry_batch
    return run_donzzul_expiry_batch(db)


@router.post("/batch/expiry-warning")
def batch_expiry_warning(db: Session = Depends(get_db)):
    """만료 임박 알림 배치 (매일 오전 9시)"""
    from app.services.donzzul_batch import run_donzzul_expiry_warning_batch
    return run_donzzul_expiry_warning_batch(db)


@router.post("/batch/deal-expiry")
def batch_deal_expiry(db: Session = Depends(get_db)):
    """딜 마감 배치 (매일)"""
    from app.services.donzzul_batch import run_donzzul_deal_expiry_batch
    return run_donzzul_deal_expiry_batch(db)


# ============================================================
# 정산
# ============================================================

@router.post("/settlements/create")
def create_settlement_endpoint(body: dict, db: Session = Depends(get_db)):
    """가게 정산 생성 (관리자)"""
    from app.services.donzzul_settlement import create_donzzul_settlement
    store_id = body.get("store_id")
    return create_donzzul_settlement(store_id, db)


@router.put("/settlements/{settlement_id}/process")
def process_settlement_endpoint(settlement_id: int, body: dict, db: Session = Depends(get_db)):
    """정산 승인/지급/거절 (관리자)"""
    from app.services.donzzul_settlement import process_donzzul_settlement
    action = body.get("action")
    admin_id = body.get("admin_id")
    return process_donzzul_settlement(settlement_id, action, db, admin_id)


@router.get("/settlements")
def list_settlements(
    store_id: int = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db),
):
    """정산 목록"""
    query = db.query(DonzzulSettlement)
    if store_id:
        query = query.filter(DonzzulSettlement.store_id == store_id)
    if status:
        query = query.filter(DonzzulSettlement.status == status)
    return query.order_by(DonzzulSettlement.created_at.desc()).all()


@router.get("/settlements/{settlement_id}")
def get_settlement(settlement_id: int, db: Session = Depends(get_db)):
    """정산 상세 (포함된 상품권 목록)"""
    settlement = db.query(DonzzulSettlement).filter(DonzzulSettlement.id == settlement_id).first()
    if not settlement:
        raise HTTPException(404, "정산을 찾을 수 없습니다")

    vouchers = db.query(DonzzulVoucher).filter(
        DonzzulVoucher.settlement_id == settlement_id
    ).all()

    store = db.query(DonzzulStore).filter(DonzzulStore.id == settlement.store_id).first()

    return {
        "settlement": settlement,
        "store": store,
        "vouchers": [{
            "id": v.id,
            "code": v.code,
            "amount": v.amount,
            "status": v.status,
            "buyer_id": v.buyer_id,
            "used_at": str(v.used_at) if v.used_at else None,
            "donated_at": str(v.donated_at) if v.donated_at else None,
        } for v in vouchers],
    }


# ============================================================
# 채팅
# ============================================================

@router.get("/deals/{deal_id}/chat/messages")
def get_chat_messages(
    deal_id: int,
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """채팅 기록 (is_deleted=False만, 페이지네이션)"""
    q = db.query(DonzzulChatMessage).filter(
        DonzzulChatMessage.deal_id == deal_id,
        DonzzulChatMessage.is_deleted == False,
    ).order_by(DonzzulChatMessage.created_at.desc())

    total = q.count()
    messages = q.offset(offset).limit(limit).all()

    return {
        "messages": [
            {
                "id": m.id,
                "deal_id": m.deal_id,
                "sender_id": m.sender_id,
                "sender_nickname": m.sender_nickname or "익명",
                "message_type": m.message_type,
                "content": m.content,
                "created_at": str(m.created_at),
            }
            for m in messages
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/deals/{deal_id}/chat/messages")
def post_chat_message(deal_id: int, body: dict, db: Session = Depends(get_db)):
    """메시지 전송"""
    content = str(body.get("content", "")).strip()
    if not content:
        raise HTTPException(400, "메시지 내용을 입력해주세요")
    if len(content) > 500:
        raise HTTPException(400, "메시지는 500자 이내로 작성해주세요")

    # 딜 존재 확인
    deal = db.query(DonzzulDeal).filter(DonzzulDeal.id == deal_id).first()
    if not deal:
        raise HTTPException(404, "딜을 찾을 수 없습니다")

    msg = DonzzulChatMessage(
        deal_id=deal_id,
        sender_id=body.get("sender_id"),
        sender_nickname=str(body.get("sender_nickname", "익명"))[:50],
        message_type=body.get("message_type", "CHEER"),
        content=content[:500],
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return {
        "id": msg.id,
        "deal_id": msg.deal_id,
        "sender_id": msg.sender_id,
        "sender_nickname": msg.sender_nickname or "익명",
        "message_type": msg.message_type,
        "content": msg.content,
        "created_at": str(msg.created_at),
    }


@router.delete("/chat/messages/{message_id}")
def delete_chat_message(message_id: int, body: dict = {}, db: Session = Depends(get_db)):
    """메시지 삭제 (soft delete)"""
    msg = db.query(DonzzulChatMessage).filter(DonzzulChatMessage.id == message_id).first()
    if not msg:
        raise HTTPException(404, "메시지를 찾을 수 없습니다")

    # 본인 확인 (sender_id가 있는 경우)
    requester_id = body.get("sender_id")
    if msg.sender_id and requester_id and msg.sender_id != requester_id:
        raise HTTPException(403, "본인의 메시지만 삭제할 수 있습니다")

    msg.is_deleted = True
    db.commit()
    return {"ok": True, "message": "삭제되었습니다"}
