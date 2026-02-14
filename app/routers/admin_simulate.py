# app/routers/admin_simulate.py
# Author: Jeong Sang Lee
# Version: v3.4-fullflow-api
# ✅ FastAPI에서 DB 초기화 + 샘플 데이터 생성 + 시뮬레이션 실행용 API

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict, Any
import os
import traceback

from app.database import get_db, engine
from app import models, schemas, crud
from app.config.feature_flags import FEATURE_FLAGS

from simulation_fullflow_v3_7 import run   # ✅ 여기서 v3_4 → v3_5 로 변경

router = APIRouter(prefix="/admin/simulate", tags=["simulate"])


# -----------------------------------------------------
# 🧨 내부 함수: DB 전체 리셋
# -----------------------------------------------------
def _reset_db() -> None:
    print("🧨 RESET_DB → 모든 테이블 드롭 후 재생성")
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)


# -----------------------------------------------------
# 🚀 풀플로우 시뮬레이션
# -----------------------------------------------------
@router.post("/fullflow")
def simulate_fullflow(
    reset_db: bool = Query(False, description="DB 초기화 후 실행 여부"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    ✅ v3.4 풀플로우 시뮬레이션
    """
    try:
        if reset_db:
            _reset_db()

        # ---- 샘플 Buyers ----
        buyer_ids, buyer_emails = [], []
        for i in range(5):
            email = f"buyer{i}_auto@test.com"
            buyer = crud.create_buyer(db, schemas.BuyerCreate(
                email=email, name=f"Buyer {i}", password="pass1234"
            ))
            buyer_ids.append(buyer.id)
            buyer_emails.append(email)

        # ---- 샘플 Sellers ----
        seller_ids, seller_emails = [], []
        for i in range(4):
            email = f"seller{i}_auto@test.com"

            # ✅ SellerCreate 스키마 필수필드 채우기 (phone/address/zip_code/established_date)
            seller = crud.create_seller(db, schemas.SellerCreate(
                email=email,
                password="pass1234",
                business_name=f"Biz {i}",
                business_number=f"100-00-000{i}",
                phone=f"010-9000-000{i}",
                address=f"Seoul Test-ro {i}",
                zip_code="00000",
                established_date=datetime.utcnow(),
            ))
            seller_ids.append(seller.id)
            seller_emails.append(email)

        # ---- Deal A ----
        deal_a = crud.create_deal(db, schemas.DealCreate(
            product_name="Smartphone Bundle A",
            creator_id=buyer_ids[0],
            desired_qty=3,
            target_price=1000.0,        # ✅ 추가
        ))

        crud.add_participant(db, schemas.DealParticipantCreate(deal_id=deal_a.id, buyer_id=buyer_ids[1], qty=1))
        crud.add_participant(db, schemas.DealParticipantCreate(deal_id=deal_a.id, buyer_id=buyer_ids[2], qty=2))

        offer_a1 = crud.create_offer(db, schemas.OfferCreate(
            deal_id=deal_a.id,
            seller_id=seller_ids[1],
            price=1000.0,
            total_available_qty=10,
            free_text="A1",
            shipping_mode="PER_RESERVATION",
            shipping_fee_per_reservation=0,
            shipping_fee_per_qty=0,
        ))

        offer_a2 = crud.create_offer(db, schemas.OfferCreate(
            deal_id=deal_a.id,
            seller_id=seller_ids[2],
            price=1100.0,
            total_available_qty=5,
            free_text="A2",
            shipping_mode="PER_RESERVATION",
            shipping_fee_per_reservation=0,
            shipping_fee_per_qty=0,
        ))

        offer_a1.sold_qty = offer_a1.total_available_qty
        db.commit(); db.refresh(offer_a1)

        crud.reward_buyer_payment(db, buyer_id=buyer_ids[1])       # +20
        crud.penalize_buyer_cancel(db, buyer_id=buyer_ids[2])      # -20
        crud.confirm_offer_and_reward(db, offer_id=offer_a1.id)    # +30
        crud.penalize_seller_cancel_offer(db, seller_id=seller_ids[2])  # -30

        # ---- Deal B ----
        deal_b = crud.create_deal(db, schemas.DealCreate(
            product_name="Headphone B",
            creator_id=buyer_ids[3],
            desired_qty=2,
            target_price=1000.0,        # ✅ 예시(원하는 값으로)
        ))

        offer_b1 = crud.create_offer(db, schemas.OfferCreate(
            deal_id=deal_b.id,
            seller_id=seller_ids[1],
            price=200.0,
            total_available_qty=3,
            free_text="B1",

            # ✅ 중요: NONE 금지 → 유효 enum으로 명시
            shipping_mode="PER_RESERVATION",
            shipping_fee_per_reservation=0,
            shipping_fee_per_qty=0,
        ))

        offer_b2 = crud.create_offer(db, schemas.OfferCreate(
            deal_id=deal_b.id,
            seller_id=seller_ids[2],
            price=210.0,
            total_available_qty=2,
            free_text="B2",

            # ✅ 중요: NONE 금지 → 유효 enum으로 명시
            shipping_mode="PER_RESERVATION",
            shipping_fee_per_reservation=0,
            shipping_fee_per_qty=0,
        ))


        # ---- Deal C ----
        deal_c = crud.create_deal(db, schemas.DealCreate(
            product_name="Monitor C",
            creator_id=buyer_ids[4],
            desired_qty=1,
            target_price=1000.0,        # ✅ 예시(원하는 값으로)
        ))
        p1 = crud.add_participant(db, schemas.DealParticipantCreate(deal_id=deal_c.id, buyer_id=buyer_ids[2], qty=5))
        _ = crud.add_participant(db, schemas.DealParticipantCreate(deal_id=deal_c.id, buyer_id=buyer_ids[1], qty=10))
        crud.remove_participant(db, participant_id=p1.id)  # -20

        # ---- 포인트 요약 ----
        buyers_balance = {str(bid): crud.get_user_balance(db, "buyer", bid) for bid in buyer_ids}
        sellers_balance = {str(sid): crud.get_user_balance(db, "seller", sid) for sid in seller_ids}

        return {
            "meta": {
                "started_at": datetime.utcnow().isoformat(),
                "reset_db": reset_db,
                "version": "v3.4-fullflow-api",
                "db": str(db.bind.url) if db.bind else None,
                "feature_flags": FEATURE_FLAGS,
            },
            "buyers": buyer_emails,
            "sellers": seller_emails,
            "deals": [
                {"id": deal_a.id, "product_name": deal_a.product_name},
                {"id": deal_b.id, "product_name": deal_b.product_name},
                {"id": deal_c.id, "product_name": deal_c.product_name},
            ],
            "offers": {
                "deal_a": [offer_a1.id, offer_a2.id],
                "deal_b": [offer_b1.id, offer_b2.id],
            },
            "point_balances": {
                "buyers": buyers_balance,
                "sellers": sellers_balance,
            },
        }

    except Exception as e:
        tb = traceback.format_exc()
        print("❌ simulate_fullflow failed:", repr(e))
        print(tb)
        # ✅ 이제 curl에서 detail로 원인이 바로 보이게
        raise HTTPException(status_code=500, detail=f"{e.__class__.__name__}: {e}")


# -----------------------------------------------------
# 📊 최신 분석 그래프 조회
# -----------------------------------------------------
@router.get("/analysis/latest", response_class=FileResponse)
def get_latest_analysis_chart(chart_type: str = "buyer_points"):
    """
    최근 분석 그래프 반환 (buyer_points / seller_points / deal_participants_offers)
    """
    output_dir = "analysis_output"
    if not os.path.exists(output_dir):
        raise HTTPException(status_code=404, detail="No analysis results found")

    files = sorted([f for f in os.listdir(output_dir) if chart_type in f], reverse=True)
    if not files:
        raise HTTPException(status_code=404, detail=f"No chart for type '{chart_type}'")

    latest_file = os.path.join(output_dir, files[0])
    return FileResponse(latest_file, media_type="image/png")

# -----------------------------------------------------
# 📊 Summary
# -----------------------------------------------------
@router.get("/summary", tags=["admin", "simulate"])
def get_simulation_summary():
    import json, os
    filepath = "simulation_results_fullflow_v3_4.json"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Simulation result not found")

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

# -----------------------------------------------------
# 📊 Dashboard 요약용 API
# -----------------------------------------------------
@router.get("/stats", tags=["admin", "simulate"])
def get_stats():
    import json
    filepath = "simulation_results_fullflow_v3_4.json"
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    stats = {
        "total_buyers": len(data.get("buyers", [])),
        "total_sellers": len(data.get("sellers", [])),
        "total_deals": len(data.get("deals", [])),
        "total_offers": len(data.get("offers", {}).get("deal_a", [])) + len(data.get("offers", {}).get("deal_b", [])),
        "total_participants": len(data.get("participants", [])),
    }
    return stats

#---------------------------------
# v3.5 시뮬레이터 실행
#---------------------------------
@router.post("/")
def run_simulation(db: Session = Depends(get_db)):
    """
    🔁 DB 리셋 후 전체 시뮬레이션 실행
    """
    result = run()
    return {"message": "Simulation complete", "result": result}