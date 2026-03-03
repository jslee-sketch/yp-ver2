# app/schemas_spectator.py
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

try:
    from pydantic import ConfigDict
    _V2 = True
except ImportError:
    _V2 = False

if _V2:
    class ORMModel(BaseModel):
        model_config = ConfigDict(from_attributes=True)
else:
    class ORMModel(BaseModel):  # type: ignore[misc]
        class Config:
            from_attributes = True


# ── 요청 스키마 ──────────────────────────────────────────

class SpectatorPredictIn(BaseModel):
    deal_id: int
    buyer_id: int
    predicted_price: int   # 1 ~ 99999999
    comment: Optional[str] = None


class SettleRequest(BaseModel):
    settled_price: Optional[int] = None  # None이면 Reservation 기반 auto-detect


# ── 기본 예측 출력 (마감 전/내 예측) ───────────────────────

class SpectatorPredictOut(ORMModel):
    id: int
    deal_id: int
    buyer_id: int
    predicted_price: int
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    # 판정 결과 (settle 후 채워짐)
    settled_price: Optional[int] = None
    error_pct: Optional[float] = None
    tier_name: Optional[str] = None
    points_earned: int = 0
    settled_at: Optional[datetime] = None


# ── 판정 결과 포함 출력 (마감 후) ────────────────────────

class SpectatorPredictionSettled(ORMModel):
    id: int
    deal_id: int
    buyer_id: int
    predicted_price: int
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    settled_price: Optional[int] = None
    error_pct: Optional[float] = None
    tier_name: Optional[str] = None
    tier_label: Optional[str] = None   # YAML scoring.tiers[].label — ORM에 없으므로 None 허용
    points_earned: int = 0
    settled_at: Optional[datetime] = None


# ── 딜 예측 집계 응답 ────────────────────────────────────

class DealPredictionsOut(BaseModel):
    deal_id: int
    deal_status: str
    predictions_count: int
    avg_predicted_price: Optional[float] = None
    median_predicted_price: Optional[float] = None
    predictions: List[SpectatorPredictOut]


# ── 뷰어 응답 ────────────────────────────────────────────

class DealViewerOut(BaseModel):
    deal_id: int
    viewer_count: int
    is_viewing: bool


# ── 예측자 수 응답 ────────────────────────────────────────

class PredictionCountOut(BaseModel):
    deal_id: int
    count: int


# ── 랭킹 항목 ────────────────────────────────────────────

class SpectatorRankingEntry(BaseModel):
    rank: int
    buyer_id: int
    nickname: str
    total_points: int
    predictions_count: int
    hits_count: int
    hit_rate: float
    exact_count: int
    avg_error_pct: Optional[float] = None
    tier: Optional[str] = None
    badge: Optional[str] = None
    bonus_points: int = 0


# ── 랭킹 전체 응답 ───────────────────────────────────────

class SpectatorRankingsOut(BaseModel):
    year_month: str
    rankings: List[SpectatorRankingEntry]


# ── settle 응답 ──────────────────────────────────────────

class SettleResponse(BaseModel):
    deal_id: int
    settled: bool
    settled_price: Optional[int] = None
    processed: int = 0
    reason: Optional[str] = None


# ── 하위 호환 alias ──────────────────────────────────────
PredictionCreate = SpectatorPredictIn
PredictionOut = SpectatorPredictOut
RankingEntry = SpectatorRankingEntry
RankingResponse = SpectatorRankingsOut
