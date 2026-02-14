# app/routers/deals.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
import logging
from app.database import get_db

from .. import crud, schemas, database, models
from app.routers.notifications import create_notification
from datetime import datetime, timezone
import logging
from app.models import Deal

from app.schemas_ai import DealResolveIn, DealResolveOut, BuyerIntentParsed, DealResolveResult, BuyerIntentParsed
from app.crud import create_deal_from_intent, find_matching_deals_for_intent

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
    """
    try:
        db_deal = crud.create_deal(db, deal_in)

        # ✅ S1: 딜 생성 직후 guardrail 평가/적용/로그 (SSOT: pricing_guardrail_hook)
        result = run_pricing_guardrail(
            deal_id=int(db_deal.id),
            category=getattr(db_deal, "category", None),
            target_price=getattr(db_deal, "target_price", None),
            anchor_price=getattr(db_deal, "anchor_price", None),  # 있을 수도/없을 수도
            evidence_score=getattr(db_deal, "evidence_score", 0) or 0,
            anchor_confidence=getattr(db_deal, "anchor_confidence", 1.0) or 1.0,
        )

        apply_guardrail_to_deal(db, db_deal, result)
        log_guardrail_evidence(db, deal_id=int(db_deal.id), result=result, anchor_version="S1_CREATE")

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
    db_participant = crud.add_participant(db=db, participant=participant)

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