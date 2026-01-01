# app/routers/deal_intents.py
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(
    prefix="/deal_intents",
    tags=["deal_intents (placeholder)"],
)


@router.get("/ping")
def ping():
    """
    임시/플레이스홀더 엔드포인트.

    - main.py 에서 router 마운트는 유지하면서
    - 예전 BuyerIntentParsed/DealMatchCandidate 의존성은 완전히 제거

    나중에
    - 'free text -> DealResolveIn' LLM 파이프라인을
      이 파일에서 다시 구현하고 싶으면
    여기에 POST 엔드포인트를 추가하면 된다.
    """
    return {"ok": True, "msg": "deal_intents router is alive"}