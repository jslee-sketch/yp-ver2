# app/routers/spectator.py
"""
관전자(Spectator) 엔드포인트.

POST /spectator/view/{deal_id}           딜방 열람 로그 (DealViewer)
GET  /spectator/viewers/{deal_id}        뷰어 수 조회
POST /spectator/predict                  예측 제출
GET  /spectator/predictions/{deal_id}    예측 조회 → DealPredictionsOut
GET  /spectator/predictions/{deal_id}/count  예측자 수
GET  /spectator/my_predictions           내 예측 이력
POST /spectator/settle/{deal_id}         적중 판정 트리거 (내부/admin)
GET  /spectator/rankings                 월간 랭킹
"""
from __future__ import annotations

import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app import database
from app.models import (
    Deal, Buyer, DealParticipant,
    SpectatorPrediction, DealViewer,
    PredictionVote,
)
from app.schemas_spectator import (
    SpectatorPredictIn,
    SpectatorPredictOut,
    DealPredictionsOut,
    DealViewerOut,
    PredictionCountOut,
    SpectatorRankingEntry,
    SpectatorRankingsOut,
    SettleRequest,
    SettleResponse,
    # 하위 호환 alias
    PredictionCreate,
    PredictionOut,
    RankingEntry,
    RankingResponse,
)

router = APIRouter(prefix="/spectator", tags=["spectator"])
get_db = database.get_db

_YAML_PATH = Path(__file__).parent.parent / "policy" / "params" / "spectator.yaml"


def _load_params() -> dict:
    with open(_YAML_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["spectator"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── 검증 헬퍼 ────────────────────────────────────────────

def _validate_prediction(
    db: Session,
    deal_id: int,
    buyer_id: int,
    predicted_price: int,
    params: dict,
) -> Deal:
    # 1. deal 조회 + status 확인
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="딜을 찾을 수 없습니다.")
    if deal.status != "open":
        raise HTTPException(status_code=400, detail="열린 딜에만 예측할 수 있습니다.")

    # 2. buyer 조회
    buyer = db.query(Buyer).filter(Buyer.id == buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="구매자를 찾을 수 없습니다.")

    # 3. 딜 참여자 확인 (참여자는 예측 불가)
    participant = (
        db.query(DealParticipant)
        .filter(
            DealParticipant.deal_id == deal_id,
            DealParticipant.buyer_id == buyer_id,
        )
        .first()
    )
    if participant:
        raise HTTPException(status_code=400, detail="딜 참여자는 가격 예측을 할 수 없습니다.")

    # 4. 중복 예측 확인 (딜당 1회 제한)
    existing = (
        db.query(SpectatorPrediction)
        .filter(
            SpectatorPrediction.deal_id == deal_id,
            SpectatorPrediction.buyer_id == buyer_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="이미 예측을 제출했습니다. (딜당 1회 제한)")

    # 5. 가격 범위 확인
    pred_cfg = params["prediction"]
    min_price = pred_cfg["min_price"]
    max_price = pred_cfg["max_price"]
    if predicted_price < min_price or predicted_price > max_price:
        raise HTTPException(
            status_code=400,
            detail=f"예측 가격은 {min_price:,}원 ~ {max_price:,}원 범위여야 합니다.",
        )

    return deal


# ── 뷰어 엔드포인트 ───────────────────────────────────────

@router.post("/view/{deal_id}", response_model=DealViewerOut, status_code=200)
def record_view(
    deal_id: int,
    buyer_id: int = Query(..., description="열람한 buyer_id"),
    db: Session = Depends(get_db),
):
    """딜방 열람 로그 (DealViewer). 중복 열람은 무시하고 viewer_count만 반환."""
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="딜을 찾을 수 없습니다.")

    # UNIQUE 충돌 무시 — 이미 열람한 경우 재삽입 안 함
    existing = (
        db.query(DealViewer)
        .filter(DealViewer.deal_id == deal_id, DealViewer.buyer_id == buyer_id)
        .first()
    )
    if not existing:
        viewer = DealViewer(
            deal_id=deal_id,
            buyer_id=buyer_id,
            viewed_at=_utcnow(),
        )
        db.add(viewer)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

    viewer_count = (
        db.query(DealViewer).filter(DealViewer.deal_id == deal_id).count()
    )
    return DealViewerOut(deal_id=deal_id, viewer_count=viewer_count, is_viewing=True)


@router.get("/viewers/{deal_id}", response_model=DealViewerOut)
def get_viewers(
    deal_id: int,
    db: Session = Depends(get_db),
):
    """딜 뷰어 수 조회."""
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="딜을 찾을 수 없습니다.")

    viewer_count = (
        db.query(DealViewer).filter(DealViewer.deal_id == deal_id).count()
    )
    return DealViewerOut(deal_id=deal_id, viewer_count=viewer_count, is_viewing=False)


# ── 예측 엔드포인트 ───────────────────────────────────────

@router.post("/predict", response_model=SpectatorPredictOut, status_code=201)
def submit_prediction(
    body: SpectatorPredictIn,
    db: Session = Depends(get_db),
):
    """
    관전자 가격 예측 제출.
    - 딜 status == open 확인
    - 딜 미참여 확인
    - 딜당 1회 제한
    - 가격 범위 확인
    """
    params = _load_params()

    # 코멘트 길이 검증
    if body.comment:
        max_len = params["prediction"]["comment_max_length"]
        if len(body.comment) > max_len:
            raise HTTPException(
                status_code=400,
                detail=f"코멘트는 최대 {max_len}자까지 입력할 수 있습니다.",
            )

    _validate_prediction(db, body.deal_id, body.buyer_id, body.predicted_price, params)

    prediction = SpectatorPrediction(
        deal_id=body.deal_id,
        buyer_id=body.buyer_id,
        predicted_price=body.predicted_price,
        comment=body.comment,
        created_at=_utcnow(),
        points_earned=0,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


@router.get("/predictions/{deal_id}", response_model=DealPredictionsOut)
def get_predictions(
    deal_id: int,
    buyer_id: Optional[int] = Query(None, description="본인 확인용 buyer_id"),
    db: Session = Depends(get_db),
):
    """
    딜 예측 조회 — DealPredictionsOut 반환.
    - 딜 마감 전: buyer_id가 있으면 본인 예측만 반환, avg/median 공개 안 함
    - 딜 마감 후: 전체 예측 공개 (판정 결과 포함) + 집계 포함
    """
    deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="딜을 찾을 수 없습니다.")

    params = _load_params()
    reveal_after_close = params["prediction"].get("reveal_after_close", True)
    is_closed = deal.status != "open"

    # 전체 예측 수는 항상 실제 DB 카운트 사용 (마감 전 "N명이 예측 중" 표시용)
    total_count = (
        db.query(SpectatorPrediction)
        .filter(SpectatorPrediction.deal_id == deal_id)
        .count()
    )

    if is_closed and reveal_after_close:
        # 마감 후 전체 공개
        preds = (
            db.query(SpectatorPrediction)
            .filter(SpectatorPrediction.deal_id == deal_id)
            .order_by(SpectatorPrediction.created_at)
            .all()
        )
        prices = [p.predicted_price for p in preds]
        avg = round(sum(prices) / len(prices), 2) if prices else None
        if prices:
            sorted_prices = sorted(prices)
            n = len(sorted_prices)
            median = float(sorted_prices[n // 2]) if n % 2 == 1 else (sorted_prices[n // 2 - 1] + sorted_prices[n // 2]) / 2
        else:
            median = None
    else:
        # 마감 전 — 내용은 본인 예측만 (없으면 빈 리스트), avg/median 비공개
        if buyer_id is None:
            preds = []
        else:
            preds = (
                db.query(SpectatorPrediction)
                .filter(
                    SpectatorPrediction.deal_id == deal_id,
                    SpectatorPrediction.buyer_id == buyer_id,
                )
                .all()
            )
        avg = None
        median = None

    return DealPredictionsOut(
        deal_id=deal_id,
        deal_status=deal.status,
        predictions_count=total_count,
        avg_predicted_price=avg,
        median_predicted_price=median,
        predictions=preds,
    )


@router.get("/predictions/{deal_id}/count", response_model=PredictionCountOut)
def get_prediction_count(
    deal_id: int,
    db: Session = Depends(get_db),
):
    """예측자 수만 반환 (마감 전 집계 노출용)."""
    count = (
        db.query(SpectatorPrediction)
        .filter(SpectatorPrediction.deal_id == deal_id)
        .count()
    )
    return PredictionCountOut(deal_id=deal_id, count=count)


@router.get("/my_predictions", response_model=List[SpectatorPredictOut])
def get_my_predictions(
    buyer_id: int = Query(..., description="조회할 buyer_id"),
    db: Session = Depends(get_db),
):
    """내 전체 예측 이력 조회."""
    buyer = db.query(Buyer).filter(Buyer.id == buyer_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="구매자를 찾을 수 없습니다.")

    predictions = (
        db.query(SpectatorPrediction)
        .filter(SpectatorPrediction.buyer_id == buyer_id)
        .order_by(SpectatorPrediction.created_at.desc())
        .all()
    )
    return predictions


# ── settle + 랭킹 ─────────────────────────────────────────

@router.post("/settle/{deal_id}", response_model=SettleResponse)
def settle_deal(
    deal_id: int,
    body: SettleRequest,
    db: Session = Depends(get_db),
):
    """
    적중 판정 트리거 (내부/admin용).
    settled_price=None → Reservation.status=PAID 기반 auto-detect.
    성사된 Reservation이 없으면 settled=False, 200 반환 (에러 아님).
    """
    settled_price = body.settled_price

    if settled_price is None:
        from app.policy.spectator_settlement import get_settled_price
        settled_price = get_settled_price(db, deal_id)

    if settled_price is None:
        return SettleResponse(
            deal_id=deal_id,
            settled=False,
            reason="no_paid_reservations",
        )

    if settled_price <= 0:
        raise HTTPException(status_code=400, detail="settled_price는 1 이상이어야 합니다.")

    from app.policy.spectator_settlement import settle_deal_predictions
    processed = settle_deal_predictions(db, deal_id, settled_price)
    db.commit()

    # 판정 결과 알림 발송
    try:
        from app.routers.notifications import create_notification
        from app.models import SpectatorPrediction
        settled_preds = (
            db.query(SpectatorPrediction)
            .filter(
                SpectatorPrediction.deal_id == deal_id,
                SpectatorPrediction.settled_at.isnot(None),
            )
            .all()
        )
        for pred in settled_preds:
            tier = getattr(pred, "tier_name", "miss") or "miss"
            pts = getattr(pred, "points_earned", 0) or 0
            ep = getattr(pred, "error_pct", 0.0) or 0.0
            create_notification(
                db,
                user_id=pred.buyer_id,
                type="spectator_result",
                title=f"딜 #{deal_id} 예측 결과: {tier}",
                message=(
                    f"예측가 {pred.predicted_price:,}원 / 성사가 {settled_price:,}원 "
                    f"(오차 {ep:.1f}%) → {pts}pt 획득"
                ),
                meta={
                    "deal_id": deal_id,
                    "prediction_id": pred.id,
                    "tier": tier,
                    "points": pts,
                },
            )
    except Exception as _notify_err:
        print(f"[SPECTATOR] settle notify error: {_notify_err}")

    return SettleResponse(
        deal_id=deal_id,
        settled=True,
        settled_price=settled_price,
        processed=processed,
    )


@router.get("/rankings", response_model=SpectatorRankingsOut)
def get_rankings(
    year_month: str = Query(..., description="조회할 연월 (예: 2026-02)"),
    db: Session = Depends(get_db),
):
    """월간 랭킹 조회."""
    from app.policy.spectator_ranking import compute_rankings

    rankings_data = compute_rankings(db, year_month)
    rankings = [SpectatorRankingEntry(**entry) for entry in rankings_data]
    return SpectatorRankingsOut(year_month=year_month, rankings=rankings)


# ── 좋아요/글쎄요 투표 ──────────────────────────────────
@router.post("/prediction-vote/{prediction_id}")
def vote_prediction(
    prediction_id: int,
    user_id: int = Query(...),
    vote_type: str = Query(..., pattern="^(like|meh)$"),
    db: Session = Depends(get_db),
):
    pred = db.query(SpectatorPrediction).filter(SpectatorPrediction.id == prediction_id).first()
    if not pred:
        raise HTTPException(status_code=404, detail="예측을 찾을 수 없습니다.")
    if pred.buyer_id == user_id:
        raise HTTPException(status_code=400, detail="본인 예측에는 투표할 수 없습니다.")

    existing = db.query(PredictionVote).filter(
        PredictionVote.prediction_id == prediction_id,
        PredictionVote.user_id == user_id,
    ).first()

    if existing:
        if existing.vote_type == vote_type:
            raise HTTPException(status_code=400, detail="이미 투표했습니다.")
        existing.vote_type = vote_type
    else:
        db.add(PredictionVote(prediction_id=prediction_id, user_id=user_id, vote_type=vote_type))

    db.commit()

    likes = db.query(PredictionVote).filter(PredictionVote.prediction_id == prediction_id, PredictionVote.vote_type == "like").count()
    mehs = db.query(PredictionVote).filter(PredictionVote.prediction_id == prediction_id, PredictionVote.vote_type == "meh").count()

    return {"prediction_id": prediction_id, "likes": likes, "mehs": mehs, "my_vote": vote_type}
