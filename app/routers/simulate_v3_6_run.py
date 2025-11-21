# routers/simulate_v3_6_run.py
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# 시뮬레이터가 루트에 있을 때
from simulation_fullflow_v3_6 import run_simulation, SimConfig
# 만약 app/ 폴더에 있다면:
# from app.simulation_fullflow_v3_6 import run_simulation, SimConfig

router = APIRouter(prefix="/admin/simulate/v3_6", tags=["admin/simulate v3.6"])

class SimRunRequest(BaseModel):
    deal_id: int = Field(..., ge=1)
    rounds: int = Field(3, ge=1, le=100)
    seed: int = 42
    price_min: float = 10.0
    price_max: float = 100.0
    buyer_point_per_qty: int = 1
    seller_point_on_confirm: int = 30
    offer_capacity_min: int = 5
    offer_capacity_max: int = 20
    output: Optional[str] = Field(None, description="파일로도 저장하고 싶으면 경로 지정")

@router.post(
    "/run",
    summary="(v3.6) 시간축 풀플로우 시뮬레이터 실행",
    status_code=status.HTTP_200_OK,
)
def run_v36_simulation(body: SimRunRequest):
    try:
        cfg = SimConfig(
            deal_id=body.deal_id,
            rounds=body.rounds,
            seed=body.seed,
            price_min=body.price_min,
            price_max=body.price_max,
            buyer_point_per_qty_on_close=body.buyer_point_per_qty,
            seller_point_on_confirm=body.seller_point_on_confirm,
            offer_capacity_min=body.offer_capacity_min,
            offer_capacity_max=body.offer_capacity_max,
            output=body.output or "./analysis/simulation_results_v3_6.json",
        )
        return run_simulation(cfg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"simulation failed: {e}")