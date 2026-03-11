# app/routers/deals.py
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from app.database import get_db

from .. import crud, schemas, database, models
from app.routers.notifications import create_notification
from datetime import datetime, timezone
import logging
from app.models import Deal

from app.schemas_ai import DealResolveIn, DealResolveOut, BuyerIntentParsed, DealResolveResult, BuyerIntentParsed
from app.crud import create_deal_from_intent, find_matching_deals_for_intent
import re as _re

from app.policy.target_vs_anchor_guardrail import run_target_vs_anchor_guardrail 

from app.policy.pricing_guardrail_hook import (
    run_pricing_guardrail,
    apply_guardrail_to_deal,
    log_guardrail_evidence,
)


router = APIRouter(prefix="/deals", tags=["deals"])
get_db = database.get_db


# ---------------------------
# 🟢 Deal 생성 (S1)
# ---------------------------
@router.post("/", response_model=schemas.DealOut)
def create_deal(deal_in: schemas.DealCreate, db: Session = Depends(get_db)):
    """
    Deal 생성 + 방장 자동 참여까지 한 번에 처리.
    옵션 / target_price / max_budget 모두 crud.create_deal에서 저장.
    anchor_price가 없으면 AI Helper(LLM+네이버)를 자동 호출해 채움.
    """
    try:
        db_deal = crud.create_deal(db, deal_in)

        # ── AI Helper 자동 호출 (anchor_price 미입력 시) ──────────────
        if not deal_in.anchor_price:
            try:
                from app.routers.deal_ai_helper import _run_ai_deal_helper
                ai = _run_ai_deal_helper(
                    raw_title=db_deal.product_name,
                    raw_free_text=db_deal.free_text or "",
                )
                # 브랜드 / canonical_name
                db_deal.brand = ai.brand
                db_deal.ai_product_key = ai.canonical_name

                # anchor_price ← 네이버 최저가
                if ai.price.naver_lowest_price:
                    db_deal.anchor_price = float(ai.price.naver_lowest_price)

                # 조건 (입력값 우선 — None인 필드만 채움)
                if ai.conditions:
                    if ai.conditions.shipping_fee_krw is not None and db_deal.shipping_fee_krw is None:
                        db_deal.shipping_fee_krw = ai.conditions.shipping_fee_krw
                    if ai.conditions.refund_days is not None and db_deal.refund_days is None:
                        db_deal.refund_days = ai.conditions.refund_days
                    if ai.conditions.warranty_months is not None and db_deal.warranty_months is None:
                        db_deal.warranty_months = ai.conditions.warranty_months
                    if ai.conditions.delivery_days is not None and db_deal.delivery_days is None:
                        db_deal.delivery_days = ai.conditions.delivery_days
                    if ai.conditions.extra_conditions and not db_deal.extra_conditions:
                        db_deal.extra_conditions = ai.conditions.extra_conditions

                # 옵션 (비어있는 슬롯에만 채움)
                for i, opt in enumerate(ai.suggested_options[:5]):
                    t_col, v_col = f"option{i+1}_title", f"option{i+1}_value"
                    if getattr(db_deal, t_col) is None:
                        setattr(db_deal, t_col, opt.title)
                        val = opt.selected_value or (opt.values[0] if opt.values else None)
                        setattr(db_deal, v_col, val)

                db.commit()
                db.refresh(db_deal)

            except Exception as ai_err:
                logging.warning("[create_deal] AI helper auto-call skipped: %r", ai_err)

        # ✅ S1: 딜 생성 직후 guardrail 평가/적용/로그 (SSOT: pricing_guardrail_hook)
        result = run_pricing_guardrail(
            deal_id=int(db_deal.id),
            category=getattr(db_deal, "category", None),
            target_price=getattr(db_deal, "target_price", None),
            anchor_price=getattr(db_deal, "anchor_price", None),  # AI Helper가 채워줄 수 있음
            evidence_score=getattr(db_deal, "evidence_score", 0) or 0,
            anchor_confidence=getattr(db_deal, "anchor_confidence", 1.0) or 1.0,
        )

        apply_guardrail_to_deal(db, db_deal, result)
        log_guardrail_evidence(db, deal_id=int(db_deal.id), result=result, anchor_version="S1_CREATE")

        # ✅ 관심 상품 매칭 알림 발송
        try:
            from app.services.interest_matcher import match_interests_for_deal
            match_interests_for_deal(db_deal, db)
        except Exception as match_err:
            logging.warning("[create_deal] interest_match skipped: %r", match_err)

        return db_deal

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create deal: {e}")


# ---------------------------
# 🟡 Deal target 변경 (S2)
# ---------------------------
@router.patch("/{deal_id}/target")
def update_deal_target(deal_id: int, body: dict, db: Session = Depends(get_db)):
    deal = db.get(models.Deal, deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    deal.target_price = body.get("target_price")
    db.commit()
    db.refresh(deal)

    try:
        # ✅ S2: 타겟 변경 직후 guardrail 재평가/적용/로그
        result = run_pricing_guardrail(
            deal_id=int(deal.id),
            category=getattr(deal, "category", None),
            target_price=getattr(deal, "target_price", None),
            anchor_price=getattr(deal, "anchor_price", None),
            evidence_score=getattr(deal, "evidence_score", 0) or 0,
            anchor_confidence=getattr(deal, "anchor_confidence", 1.0) or 1.0,
        )

        apply_guardrail_to_deal(db, deal, result)
        log_guardrail_evidence(db, deal_id=int(deal.id), result=result, anchor_version="S2_TARGET_UPDATE")

    except Exception as e:
        logging.exception("[update_deal_target] post-update guardrail failed: %r", e)

    return deal

# ---------------------------
# 📋 Deal 목록 조회 (검색/필터/페이지네이션)
# ---------------------------
from pydantic import BaseModel as _BaseModel
from typing import Optional as _Opt, Any as _Any


class DealListOut(_BaseModel):
    items: list
    total: int
    page: int
    size: int
    pages: int


@router.get("/", response_model=None)  # 직접 dict 반환 (ORM 직렬화 이슈 방지)
def read_deals(
    status: _Opt[str] = Query(None, description="open|closed|completed|expired (복수: comma-separated)"),
    keyword: _Opt[str] = Query(None, description="제품명 검색"),
    min_price: _Opt[int] = Query(None, ge=0),
    max_price: _Opt[int] = Query(None, ge=0),
    buyer_id: _Opt[int] = Query(None, description="내 딜만 보기"),
    sort: str = Query("created_at:desc"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(models.Deal)

    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if statuses:
            q = q.filter(models.Deal.status.in_(statuses))

    if keyword:
        q = q.filter(models.Deal.product_name.ilike(f"%{keyword}%"))

    if min_price is not None:
        q = q.filter(models.Deal.target_price >= min_price)
    if max_price is not None:
        q = q.filter(models.Deal.target_price <= max_price)

    if buyer_id is not None:
        q = q.filter(models.Deal.creator_id == buyer_id)

    total = q.count()

    # 정렬
    sort_field, sort_dir = (sort.split(":") + ["desc"])[:2]
    col = getattr(models.Deal, sort_field, models.Deal.created_at)
    if sort_dir == "asc":
        q = q.order_by(col.asc())
    else:
        q = q.order_by(col.desc())

    # 페이지네이션
    offset = (page - 1) * size
    items = q.offset(offset).limit(size).all()
    pages = (total + size - 1) // size if total > 0 else 1

    # ORM 객체를 Pydantic으로 직렬화
    serialized = [schemas.DealOut.model_validate(item) for item in items]
    return {"items": [i.model_dump() for i in serialized], "total": total, "page": page, "size": size, "pages": pages}


# ---------------------------
# 🔍 딜 검색 (키워드 + 카테고리 필터)
# ---------------------------
@router.get("/search")
def search_deals(
    q: str = Query("", description="검색어 (제품명)"),
    category: Optional[str] = Query(None, description="카테고리 필터"),
    min_price: Optional[int] = Query(None, ge=0),
    max_price: Optional[int] = Query(None, ge=0),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """딜 검색 엔드포인트 (GET /deals/ 의 keyword 검색 래퍼)."""
    query = db.query(models.Deal)
    if q:
        query = query.filter(models.Deal.product_name.ilike(f"%{q}%"))
    if category:
        query = query.filter(models.Deal.category == category)
    if min_price is not None:
        query = query.filter(models.Deal.target_price >= min_price)
    if max_price is not None:
        query = query.filter(models.Deal.target_price <= max_price)

    total = query.count()
    items = query.order_by(models.Deal.created_at.desc()).offset((page - 1) * size).limit(size).all()
    serialized = [schemas.DealOut.model_validate(item) for item in items]
    return {"items": [i.model_dump() for i in serialized], "total": total, "page": page, "size": size}


# ---------------------------
# 🔍 유사 딜 찾기 (딜 생성 시 중복 방지)
# ---------------------------
def _normalize_for_matching(text: str) -> str:
    """매칭용 정규화: 공백/대소문자/특수문자 통일."""
    text = text.lower().strip()
    text = _re.sub(r'[_\-/·]', ' ', text)       # 특수문자 → 공백
    text = _re.sub(r'\s+', ' ', text)            # 다중 공백 → 단일
    # 한글+영문/숫자 사이 공백 추가: "갤럭시S25" → "갤럭시 s25"
    text = _re.sub(r'([가-힣])([a-zA-Z0-9])', r'\1 \2', text)
    text = _re.sub(r'([a-zA-Z0-9])([가-힣])', r'\1 \2', text)
    # 영문+숫자 사이: "S25울트라" → "s 25울트라"
    text = _re.sub(r'([a-zA-Z])(\d)', r'\1 \2', text)
    text = _re.sub(r'(\d)([a-zA-Z])', r'\1 \2', text)
    return text.strip()


@router.get("/find-similar")
def find_similar_deals(
    product_name: str = Query(..., min_length=2),
    brand: str = Query(""),
    db: Session = Depends(get_db),
):
    """동일/유사 제품의 진행 중인 딜 찾기."""
    from sqlalchemy import or_, func

    q = db.query(models.Deal).filter(models.Deal.status == "open")

    normalized = _normalize_for_matching(product_name)
    keywords = [kw for kw in normalized.split() if len(kw) >= 2]
    if not keywords:
        return {"similar_deals": [], "count": 0}

    # 키워드 OR 매칭 (원본 + 정규화 둘 다)
    conditions = []
    for kw in keywords:
        conditions.append(models.Deal.product_name.ilike(f"%{kw}%"))
        conditions.append(models.Deal.product_detail.ilike(f"%{kw}%"))
    # 원본 키워드도 추가 (공백 있는 원본)
    for kw in product_name.strip().split():
        if len(kw) >= 2:
            conditions.append(models.Deal.product_name.ilike(f"%{kw}%"))
    q = q.filter(or_(*conditions))

    if brand:
        q = q.filter(
            or_(
                models.Deal.brand.ilike(f"%{brand}%"),
                models.Deal.product_name.ilike(f"%{brand}%"),
            )
        )

    results = q.order_by(models.Deal.created_at.desc()).limit(20).all()

    similar = []
    for deal in results:
        deal_normalized = _normalize_for_matching(
            f"{deal.product_name or ''} {deal.product_detail or ''}"
        )
        match_count = sum(1 for kw in keywords if kw in deal_normalized)
        score = round(match_count / len(keywords) * 100) if keywords else 0
        if score < 40:
            continue
        offer_count = len(deal.offers) if hasattr(deal, "offers") and deal.offers else 0
        similar.append({
            "id": deal.id,
            "product_name": deal.product_name,
            "product_detail": deal.product_detail,
            "brand": deal.brand,
            "target_price": deal.target_price,
            "market_price": deal.market_price,
            "status": deal.status,
            "offer_count": offer_count,
            "match_score": score,
            "created_at": str(deal.created_at) if deal.created_at else None,
        })

    similar.sort(key=lambda x: x["match_score"], reverse=True)
    return {"similar_deals": similar[:5], "count": len(similar)}


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
# ➕ Deal 참여자 추가 + 알림 트리거
# ---------------------------
@router.post("/{deal_id}/participants", response_model=schemas.DealParticipantOut)
def add_participant(
    deal_id: int,
    participant: schemas.DealParticipantCreate,
    db: Session = Depends(get_db),
):
    # deal_id 강제 설정 (schemas.DealParticipantCreate에 포함되었더라도 덮어쓰기)
    participant.deal_id = deal_id
    try:
        db_participant = crud.add_participant(db=db, participant=participant)
    except crud.ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # 🔔 알림: 같은 딜에 참여한 다른 바이어들 + 방장에게 알림 보내기
    try:
        deal = crud.get_deal(db, deal_id=deal_id)
        if not deal:
            return db_participant  # 딜이 없으면 알림만 스킵

        product_name = getattr(deal, "product_name", "") or "딜"
        host_buyer_id = int(getattr(deal, "creator_id", 0) or 0)

        # 이 딜의 모든 참여자 조회 (나 포함)
        all_participants = (
            db.query(models.DealParticipant)
              .filter(models.DealParticipant.deal_id == deal_id)
              .all()
        )

        # 1) 다른 바이어들에게 "새 참여자" 알림
        for p in all_participants:
            target_buyer_id = int(getattr(p, "buyer_id", 0) or 0)
            if target_buyer_id <= 0:
                continue
            if target_buyer_id == participant.buyer_id:
                continue  # 자기 자신에게는 안 보냄

            create_notification(
                db,
                user_id=target_buyer_id,
                type="deal_participated",
                title=f"딜 #{deal_id}에 새 바이어가 참여했습니다.",
                message=f'"{product_name}" 딜에 다른 바이어가 참여했습니다.',
                meta={
                    "role": "buyer",
                    "deal_id": deal_id,
                    "new_buyer_id": participant.buyer_id,
                },
            )

        # 2) 방장(딜 생성한 buyer)에게 별도 알림
        if host_buyer_id and host_buyer_id != participant.buyer_id:
            create_notification(
                db,
                user_id=host_buyer_id,
                type="deal_participated_on_host",
                title=f"내가 만든 딜 #{deal_id}에 참여자가 늘었습니다.",
                message=f'"{product_name}" 딜에 바이어가 새로 참여했습니다.',
                meta={
                    "role": "buyer_host",
                    "deal_id": deal_id,
                    "new_buyer_id": participant.buyer_id,
                },
            )

    except Exception as notify_err:
        # 알림 실패로 참여 자체가 막히면 안 되니까 그냥 로그만 찍고 무시
        logging.exception(
            "failed to create deal_participated notification",
            exc_info=notify_err,
        )

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


# ---------------------------
# 🧪 [DEV] 마감 지난 딜 자동 종료 + 알림
# ---------------------------
@router.post(
    "/dev/close_expired",
    summary="[DEV] 마감 지난 딜 자동 종료 + 알림",
)
def dev_close_expired_deals(
    db: Session = Depends(get_db),
):
    """
    - status='open' 이고 deadline_at < now 인 딜을 찾아 자동으로 'closed' 처리
    - 딜 생성자 + 참여자들에게 알림 전송
    - 지금은 Swagger /dev 용으로 수동 호출
    """
    now = datetime.now(timezone.utc)

    q = (
        db.query(models.Deal)
        .filter(models.Deal.status == "open")
        .filter(models.Deal.deadline_at.isnot(None))
        .filter(models.Deal.deadline_at < now)
    )

    deals = q.all()
    closed_ids = []

    for deal in deals:
        deal.status = "closed"
        closed_ids.append(deal.id)

        # 참여자 목록
        participants = (
            db.query(models.DealParticipant)
            .filter(models.DealParticipant.deal_id == deal.id)
            .all()
        )
        buyer_ids = {p.buyer_id for p in participants if p.buyer_id}

        # 1) 딜 생성자 알림
        try:
            if deal.creator_id:
                create_notification(
                    db,
                    user_id=deal.creator_id,
                    type="deal_closed",
                    title=f"딜 #{deal.id} 이 마감되었습니다",
                    message=f"상품 '{deal.product_name}' 딜이 마감되었습니다.",
                    meta={
                        "role": "buyer",
                        "deal_id": deal.id,
                        "status": "closed",
                    },
                )
        except Exception:
            logging.exception("[NOTI] deal_closed to creator failed")

        # 2) 참여자 알림
        for buyer_id in buyer_ids:
            try:
                create_notification(
                    db,
                    user_id=buyer_id,
                    type="deal_closed",
                    title=f"참여 중인 딜 #{deal.id} 이 마감되었습니다",
                    message=f"상품 '{deal.product_name}' 딜이 마감되었습니다.",
                    meta={
                        "role": "buyer",
                        "deal_id": deal.id,
                        "status": "closed",
                    },
                )
            except Exception:
                logging.exception("[NOTI] deal_closed to participant failed")

    db.commit()
    return {"closed_deal_ids": closed_ids, "count": len(closed_ids)}


# ---------------------------------------------------
# 🔮 LLM intent 기반 deal 생성/조인 결정
# ---------------------------------------------------

AI_RESOLVE_ENDPOINT = "/deals/ai/resolve_from_intent"


@router.post("/ai/resolve_from_intent", response_model=DealResolveResult)
def deals_resolve_from_intent(
    body: DealResolveIn = Body(...),
    db: Session = Depends(get_db),
):
    """
    LLM 이 만든 구조화 intent(DealResolveIn)를 받아서

    1) product_name + 옵션들로 fingerprint 생성
    2) fingerprint / 유사도 기반으로 '열려있는(open) deal' 중
       가장 잘 맞는 방을 찾고,
        - 있으면: 그 deal_id 를 돌려준다 (created = False)
        - 없으면: 새 deal 을 생성하고 그 id 를 돌려준다 (created = True)
    3) 모든 호출은 deal_ai_logs (또는 log_ai_event) 테이블에 1줄씩 쌓인다.
    """

    # ── text 파싱: 자연어 입력 시 product_name/desired_qty 추출 ──
    if not body.product_name and body.text:
        _txt = body.text
        # 가격: "27만원" → 270000, "135만원" → 1350000
        _price_m = _re.search(r'(\d+)\s*만\s*원', _txt)
        if _price_m and not body.target_price:
            body.target_price = float(int(_price_m.group(1)) * 10000)
        # 수량: "100개", "50개"
        _qty_m = _re.search(r'(\d+)\s*개', _txt)
        if _qty_m and not body.desired_qty:
            body.desired_qty = int(_qty_m.group(1))
        # 상품명: 가격/수량/동사 패턴 앞의 텍스트
        _name = _re.split(r'\d+\s*만\s*원|\d+\s*개|사고\s*싶|원해|희망|묶음', _txt)[0].strip()
        if _name:
            body.product_name = _name

    if not body.product_name:
        body.product_name = body.text or "unknown"
    if not body.desired_qty:
        body.desired_qty = 1

    # 요청 바디(로그용)
    req_dict = body.model_dump(mode="json")

    # 1) fingerprint / fuzzy 기반 기존 deal 후보 조회
    candidates: list[models.Deal] = crud.find_matching_deals_for_intent(db, body)  # type: ignore[type-arg]

    if candidates:
        deal = candidates[0]
        result = DealResolveResult(
            deal_id=deal.id,
            created=False,
            product_name=deal.product_name,
            status=deal.status,
        )
    else:
        # 2) 없으면 새 deal 생성
        new_deal = crud.create_deal_from_intent(db, intent=body)
        result = DealResolveResult(
            deal_id=new_deal.id,
            created=True,
            product_name=new_deal.product_name,
            status=new_deal.status,
        )

    # 3) 로그 남기기 (로그 실패로 본 로직이 깨지지 않도록 try/except)
    try:
        crud.log_ai_event(
            db,
            endpoint=AI_RESOLVE_ENDPOINT,
            buyer_id=body.buyer_id,
            request=req_dict,
            response=result.model_dump(mode="json"),
            deal_id=result.deal_id,
        )
    except Exception as e:
        # 최소한 콘솔에는 찍어두기
        print("[deals_resolve_from_intent] log_ai_event ERROR:", repr(e))

    return result