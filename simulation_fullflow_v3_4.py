"""
YeokPing v3.4 Fullflow Simulator (Auth 제거 버전)
- DB 초기화(옵션) → Buyer/Seller 생성 → Deal/Participant/Offer 생성
- 다양한 케이스: 결제/취소/오퍼확정/철회/무참여딜/과참여요청/중복취소 등
- 최종 포인트/엔티티 스냅샷을 JSON 저장

실행:
(venv) $ python simulation_fullflow_v3_4.py
"""

import json, random, string
from datetime import datetime
from pathlib import Path

# --- App imports (현재 프로젝트 구조 기준) ---
from app.database import Base, engine, SessionLocal
from app import models, schemas, crud

# -----------------------------
# 설정
# -----------------------------
RESET_DB = True
SEED = 42
OUTFILE = "simulation_results_fullflow_v3_4.json"

random.seed(SEED)

# -----------------------------
# 유틸
# -----------------------------
def randsfx(n=4):
    return "".join(random.choices(string.ascii_lowercase, k=n))

def reset_db():
    print("🧨 RESET_DB=True → 모든 테이블 드롭 후 재생성합니다.")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def now_iso():
    return datetime.utcnow().isoformat()

# -----------------------------
# 시나리오 빌더
# -----------------------------
def build_buyers(db, n=5):
    buyers = []
    for i in range(n):
        email = f"buyer{i}_{randsfx()}@test.com"
        b = schemas.BuyerCreate(
            email=email,
            password="pw1234",
            name=f"Buyer {i}",
            phone=None, address=None, zip_code=None, gender=None, birth_date=None
        )
        buyers.append(crud.create_buyer(db, b))
    print(f"👥 Buyers created: {[b.email for b in buyers]}")
    return buyers

def build_sellers(db, n=4):
    sellers = []
    for i in range(n):
        email = f"seller{i}_{randsfx()}@test.com"
        s = schemas.SellerCreate(
            email=email,
            password="pw1234",
            business_name=f"Seller Biz {i}",
            business_number=f"BN-{i}-{randsfx(6)}",
            phone=None, company_phone=None, address=None, zip_code=None, established_date=None
        )
        sellers.append(crud.create_seller(db, s))
    print(f"🏢 Sellers created: {[s.email for s in sellers]}")
    return sellers

def build_deal(db, creator_buyer, name="Sample Product", desired_qty=3, with_options=True):
    d = schemas.DealCreate(
        product_name=name,
        creator_id=creator_buyer.id,
        desired_qty=desired_qty,
        free_text="Auto-generated deal",
        **({
            "option1_title": "Color", "option1_value": "Black",
            "option2_title": "Storage", "option2_value": "128GB",
            "option3_title": None, "option3_value": None,
            "option4_title": None, "option4_value": None,
            "option5_title": None, "option5_value": None,
        } if with_options else {})
    )
    deal = crud.create_deal(db, d)
    print(f"📦 Deal created: {deal.product_name} (id={deal.id}, desired={deal.desired_qty})")
    return deal

def add_participants(db, deal, buyers, qty_plan):
    """
    qty_plan: [(buyer, qty), ...]
    """
    created = []
    for buyer, qty in qty_plan:
        p = schemas.DealParticipantCreate(deal_id=deal.id, buyer_id=buyer.id, qty=qty)
        created.append(crud.add_participant(db, p))
    print(f"➕ Participants added to deal#{deal.id}: {[(c.buyer_id, c.qty) for c in created]}")
    return created

def remove_participant_safe(db, participant_id):
    res = crud.remove_participant(db, participant_id)
    if res is None:
        print(f"⚠️ remove_participant: participant_id={participant_id} not found (already removed?)")
    else:
        print(f"➖ Participant removed: {participant_id} → {res}")
    return res

def post_offers(db, deal, sellers, price_plan):
    """
    price_plan: [(seller, price, qty, free_text), ...]
    """
    offers = []
    for seller, price, qty, text in price_plan:
        oc = schemas.OfferCreate(
            deal_id=deal.id,
            seller_id=seller.id,
            price=price,
            total_available_qty=qty,
            free_text=text
        )
        offers.append(crud.create_offer(db, oc))
    print(f"💰 Offers created for deal#{deal.id}: {[o.id for o in offers]}")
    return offers

def confirm_offer_reward(db, offer):
    # 실제 confirm 비즈니스 로직은 간소화 (포인트 보상만 수행)
    crud.reward_seller_success(db, seller_id=offer.seller_id)
    print(f"✅ Offer confirmed → seller#{offer.seller_id} +30 points (offer#{offer.id})")

def cancel_offer_penalize(db, offer):
    crud.penalize_seller_cancel_offer(db, seller_id=offer.seller_id)
    # 실제 오퍼 삭제를 API처럼 수행
    db_offer = db.query(models.Offer).filter(models.Offer.id == offer.id).first()
    if db_offer:
        db.delete(db_offer)
        db.commit()
    print(f"❌ Offer cancelled → seller#{offer.seller_id} -30 points (offer#{offer.id})")

def buyer_checkout(db, buyer, deal):
    # 결제 성공 보상
    crud.reward_buyer_payment(db, buyer_id=buyer.id)
    print(f"💳 Buyer checkout → buyer#{buyer.id} +20 points (deal#{deal.id})")

def buyer_cancel(db, buyer, deal):
    crud.penalize_buyer_cancel(db, buyer_id=buyer.id)
    print(f"↩️ Buyer cancel → buyer#{buyer.id} -20 points (deal#{deal.id})")

def balance_snapshot(db, buyers, sellers):
    b = {str(x.id): crud.get_user_balance(db, "buyer", x.id) for x in buyers}
    s = {str(x.id): crud.get_user_balance(db, "seller", x.id) for x in sellers}
    return {"buyers": b, "sellers": s}

# -----------------------------
# 시뮬레이션 시나리오
# -----------------------------
def run():
    if RESET_DB:
        reset_db()
    else:
        print("⏭ DB Reset 생략")

    db = SessionLocal()
    try:
        # 1) 엔티티 생성
        buyers = build_buyers(db, n=5)
        sellers = build_sellers(db, n=4)

        # 2) Deal A: 정상 다자 참여 → 판매자 2명 오퍼 → 한 명 확정/한 명 철회 → 결제/취소 혼재
        deal_a = build_deal(db, creator_buyer=buyers[0], name="Smartphone Bundle A", desired_qty=3)

        # 참여: 방장(desired_qty=3 자동 참여됨) + 추가 참여자
        part_a = add_participants(
            db, deal_a,
            buyers=[buyers[1], buyers[2]],
            qty_plan=[(buyers[1], 1), (buyers[2], 2)]
        )

        # 판매자 오퍼 (가격/수량 다양)
        offers_a = post_offers(
            db, deal_a, sellers,
            price_plan=[
                (sellers[0], 950.0, 4, "Fast delivery, official warranty"),
                (sellers[1], 980.0, 5, "Extra accessories included"),
            ]
        )

        # 결제: 일부 성공 / 일부 취소
        buyer_checkout(db, buyers[1], deal_a)     # +20
        buyer_cancel(db, buyers[2], deal_a)       # -20

        # 오퍼 처리: 하나 확정(+30), 다른 하나 철회(-30)
        confirm_offer_reward(db, offers_a[0])     # seller0 +30
        cancel_offer_penalize(db, offers_a[1])    # seller1 -30

        # 3) Deal B: 무참여 → 판매자 오퍼만 존재 → 결국 판매 성사 없음
        deal_b = build_deal(db, creator_buyer=buyers[3], name="Headphone B", desired_qty=2)
        # 참여자 추가 안 함 (방장 자동참여만 존재)
        offers_b = post_offers(
            db, deal_b, sellers,
            price_plan=[
                (sellers[2], 120.0, 2, "Brand new"),
                (sellers[3], 115.0, 1, "Limited stock"),
            ]
        )
        # 별도 결제/취소/확정 없음 → 포인트 변화 없음

        # 4) Deal C: 과참여 요청(의미상) → 실제로는 시스템에서 qty는 제약 없이 저장됨(현 모델)
        deal_c = build_deal(db, creator_buyer=buyers[4], name="Monitor C", desired_qty=1)
        part_c = add_participants(db, deal_c, buyers=[buyers[2], buyers[1]], qty_plan=[(buyers[2], 5), (buyers[1], 10)])
        # 일부 참여자 취소(중복 취소 시도 포함)
        remove_participant_safe(db, part_c[0].id)  # 정상 제거
        remove_participant_safe(db, part_c[0].id)  # 재시도 → 안전 처리 로그

        # 5) 최종 스냅샷
        balances = balance_snapshot(db, buyers, sellers)

# -----------------------------
# 6️⃣ 시뮬레이션 결과 저장
# -----------------------------

        result = {
            "meta": {
                "started_at": now_iso(),
                "reset_db": RESET_DB,
                "version": "v3.4-fullflow",
                "db": str(engine.url),
            },
            "buyers": [b.email for b in buyers],
            "sellers": [s.email for s in sellers],
            "deals": [
                {"id": deal_a.id, "product_name": deal_a.product_name},
                {"id": deal_b.id, "product_name": deal_b.product_name},
                {"id": deal_c.id, "product_name": deal_c.product_name},
            ],
            "offers": {
                "deal_a": [o.id for o in offers_a],
                "deal_b": [o.id for o in offers_b],
            },
            "participants": [
                {
                    "deal_id": p.deal_id,
                    "buyer_id": p.buyer_id,
                    "qty": p.qty
                }
                
            
        for p in db.query(models.DealParticipant).all()
    ],


            
            "point_balances": balances,
        
        "deal_summary": [
    {
        "deal_id": d.id,
        "product_name": d.product_name,
        "participants": len(db.query(models.DealParticipant).filter(models.DealParticipant.deal_id == d.id).all()),
        "offers": len(db.query(models.Offer).filter(models.Offer.deal_id == d.id).all())
    }
    for d in db.query(models.Deal).all()
],
        
        
        
        }
        
        



        Path(OUTFILE).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"✅ 시뮬레이션 완료 → {OUTFILE} 저장됨")

    finally:
        db.close()

if __name__ == "__main__":
    print(f"✅ Using database: {engine.url}")
    run()