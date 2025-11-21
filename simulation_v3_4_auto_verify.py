# simulation_v3_4_auto_verify.py

import json
from datetime import datetime
from app import models, schemas, crud, database
from sqlalchemy import text

RESET_DB = True
DB_URL = "sqlite:///./app/ypver2.db"

db = next(database.get_db())
engine = database.engine

if RESET_DB:
    print("🧨 RESET_DB=True → 모든 테이블 드롭 후 재생성합니다.")
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)

print(f"✅ DB 준비 완료: {DB_URL}")

# ----------------------------
# Helper 함수
# ----------------------------
def randsuffix():
    import random, string
    return ''.join(random.choices(string.ascii_lowercase, k=4))

# ----------------------------
# 1️⃣ Buyer 생성
# ----------------------------
buyers = []
for i in range(2):
    buyer = crud.create_buyer(
        db,
        schemas.BuyerCreate(
            email=f"buyer{i}_{randsuffix()}@test.com",
            password="1234",
            name=f"Buyer{i}",
        ),
    )
    buyers.append(buyer)
print(f"👥 Buyers created: {[b.email for b in buyers]}")

# ----------------------------
# 2️⃣ Seller 생성 (+자동 승인)
# ----------------------------
sellers = []
for i in range(2):
    seller = crud.create_seller(
        db,
        schemas.SellerCreate(
            email=f"seller{i}_{randsuffix()}@test.com",
            password="1234",
            business_name=f"TestBiz{i}",
            business_number=f"99999999{i}",
        ),
    )
    # ✅ 자동 승인 로직
    seller.is_verified = True
    seller.verified_at = datetime.utcnow()
    db.commit()
    db.refresh(seller)
    sellers.append(seller)

print(f"🏢 Sellers created & auto-verified: {[s.email for s in sellers]}")

# ----------------------------
# 3️⃣ Deal 생성
# ----------------------------
deal = crud.create_deal(
    db,
    schemas.DealCreate(
        product_name="Smartphone Bundle",
        creator_id=buyers[0].id,
        desired_qty=3,
    ),
)
print(f"📦 Deal created: {deal.product_name} (id={deal.id})")

# ----------------------------
# 4️⃣ Seller가 Offer 생성
# ----------------------------
offers = []
for i, seller in enumerate(sellers):
    offer = crud.create_offer(
        db,
        schemas.OfferCreate(
            deal_id=deal.id,
            seller_id=seller.id,
            price=950.0 + (i * 10),
            total_available_qty=5,
            free_text="Special offer with auto-verified seller"
        ),
    )
    offers.append(offer)
print(f"💰 Offers created: {[o.id for o in offers]}")

# ----------------------------
# 5️⃣ 포인트 확인
# ----------------------------
balances = {
    "buyers": {b.id: crud.get_user_balance(db, "buyer", b.id) for b in buyers},
    "sellers": {s.id: crud.get_user_balance(db, "seller", s.id) for s in sellers},
}

# ----------------------------
# 6️⃣ 결과 저장
# ----------------------------
result = {
    "meta": {
        "started_at": datetime.utcnow().isoformat(),
        "reset_db": RESET_DB,
        "version": "v3.4-auto-verify",
        "db": DB_URL,
    },
    "buyers": [b.email for b in buyers],
    "sellers": [s.email for s in sellers],
    "deal": {"id": deal.id, "product_name": deal.product_name},
    "offers": [o.id for o in offers],
    "point_balances": balances,
}

with open("simulation_results_auto_verify.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=4, ensure_ascii=False)

print("✅ 시뮬레이션 완료 → simulation_results_auto_verify.json 저장됨")