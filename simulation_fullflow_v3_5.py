"""
Shim to root-level 'simulation_fullflow_v3_7.py'.
앱 레이어는 이 모듈을 임포트하면 되고, 실제 구현은 루트의 v3.7 파일이 수행합니다.
"""
import importlib

_impl = importlib.import_module("simulation_fullflow_v3_7")

SimConfig = getattr(_impl, "SimConfig")
run = getattr(_impl, "run")

__all__ = ["SimConfig", "run"]

if __name__ == "__main__":
    if hasattr(_impl, "main"):
        _impl.main()

# simulation_fullflow_v3_5.py
import os, json, random, string, argparse
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.database import SessionLocal, DATABASE_URL
from app import models, crud
from types import SimpleNamespace

# ---------- 공통 유틸 ----------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def iso(dt: datetime) -> str:
    # 항상 ISO8601(z 포함)로 기록
    return dt.astimezone(timezone.utc).isoformat()

def rstr(n=4):
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(n))

# ---------- 논리 시계(시간 역행 방지) ----------
class LogicalClock:
    """단계가 진행될 때마다 +Δ를 누적해 '시간 역행'을 방지합니다."""
    def __init__(self, start=None):
        self.t = start or now_utc()

    def tick(self, seconds: int = 1) -> datetime:
        self.t = self.t + timedelta(seconds=seconds)
        return self.t

    def mark(self) -> datetime:
        # 진행 없이 현재 논리시간을 그대로 마킹
        return self.t

# ---------- 데이터 생성 헬퍼 ----------
def create_buyers(db: Session, n=5):
    buyers = []
    for i in range(n):
        buyer = crud.create_buyer(db, buyer=SimpleNamespace(  # schemas 없이 구조만 맞춰 주입
            email=f"buyer{i}_{rstr()}@test.com",
            password="pass1234!",
            name=f"Buyer {i}",
            phone=None, address=None, zip_code=None, gender=None, birth_date=None
        ))
        buyers.append(buyer)
    return buyers

def create_sellers(db: Session, n=4):
    sellers = []
    for i in range(n):
        seller = crud.create_seller(db, seller=SimpleNamespace(
            email=f"seller{i}_{rstr()}@test.com",
            password="pass1234!",
            business_name=f"Seller {i}",
            business_number=f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10000,99999)}",
            phone=None, company_phone=None, address=None, zip_code=None, established_date=None
        ))
        sellers.append(seller)
    return sellers

def create_deal(db: Session, product_name: str, creator_id: int, desired_qty: int):
    return crud.create_deal(db, deal=SimpleNamespace(
        product_name=product_name,
        creator_id=creator_id,
        desired_qty=desired_qty,
        option1_title=None, option1_value=None,
        option2_title=None, option2_value=None,
        option3_title=None, option3_value=None,
        option4_title=None, option4_value=None,
        option5_title=None, option5_value=None,
        free_text=None
    ))

def add_participant(db: Session, deal_id: int, buyer_id: int, qty: int):
    return crud.add_participant(db, participant=SimpleNamespace(
        deal_id=deal_id, buyer_id=buyer_id, qty=qty
    ))

def post_offer(db: Session, deal_id: int, seller_id: int, price: float, qty: int, free_text=None):
    return crud.create_offer(db, offer=SimpleNamespace(
        deal_id=deal_id,
        seller_id=seller_id,
        price=price,
        total_available_qty=qty,
        free_text=free_text
    ))

# ---------- 시뮬레이션 본체 ----------
def run(reset_db=False):
    print(f"✅ Using database: {DATABASE_URL}")
    # DB 리셋은 기존 v3_4 스크립트에서 처리한 대로 실행했다고 가정 (여기선 생략)

    db = SessionLocal()

    # 결과 컨테이너
    timeline = []         # 시간순 이벤트 로그
    deal_progress = []    # deal 단위 현황 요약
    result = {
        "meta": {
            "started_at": iso(now_utc()),
            "reset_db": bool(reset_db),
            "version": "v3.5-fullflow-time",
            "db": DATABASE_URL,
        }
    }

    clock = LogicalClock(start=now_utc())

    # 1) 사용자/판매자
    buyers = create_buyers(db, n=5)
    sellers = create_sellers(db, n=4)
    timeline.append({"time": iso(clock.mark()), "event": f"Users created: {len(buyers)} buyers / {len(sellers)} sellers"})

    # 2) Deal A 생성 + 참여 + 오퍼
    deal_a = create_deal(db, "Smartphone Bundle A", buyers[0].id, 3)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Deal created: {deal_a.product_name} (id={deal_a.id}, desired={deal_a.desired_qty})"})

    # 방장 자동참여는 crud.create_deal에서 이미 추가됨. 추가 참가자:
    add_participant(db, deal_a.id, buyers[1].id, 1)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Buyer#{buyers[1].id} joined deal#{deal_a.id} (qty=1)"})

    add_participant(db, deal_a.id, buyers[2].id, 2)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Buyer#{buyers[2].id} joined deal#{deal_a.id} (qty=2)"})

    # 오퍼 2개
    offer1 = post_offer(db, deal_a.id, sellers[0].id, price=99000, qty=10, free_text="Fast shipping")
    timeline.append({"time": iso(clock.tick(1)), "event": f"Offer posted: offer#{offer1.id} by seller#{sellers[0].id} for deal#{deal_a.id}"})

    offer2 = post_offer(db, deal_a.id, sellers[1].id, price=102000, qty=5, free_text="Bundle option")
    timeline.append({"time": iso(clock.tick(1)), "event": f"Offer posted: offer#{offer2.id} by seller#{sellers[1].id} for deal#{deal_a.id}"})

    # 결제/취소/확정/철회 시나리오
    crud.reward_buyer_payment(db, buyer_id=buyers[1].id)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Buyer#{buyers[1].id} checkout → +20 points"})

    crud.penalize_buyer_cancel(db, buyer_id=buyers[2].id)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Buyer#{buyers[2].id} cancel → -20 points"})

    crud.confirm_offer_and_reward(db, offer_id=offer1.id)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Offer confirmed: offer#{offer1.id} → seller#{sellers[0].id} +30 points"})

    crud.penalize_seller_cancel_offer(db, seller_id=sellers[1].id)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Offer cancelled by seller#{sellers[1].id} → -30 points"})

    # 3) Deal B 생성 + 오퍼
    deal_b = create_deal(db, "Headphone B", buyers[3].id, 2)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Deal created: {deal_b.product_name} (id={deal_b.id}, desired={deal_b.desired_qty})"})
    offer_b1 = post_offer(db, deal_b.id, sellers[1].id, price=49000, qty=20)
    offer_b2 = post_offer(db, deal_b.id, sellers[2].id, price=45000, qty=30)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Offers posted for deal#{deal_b.id}: #{offer_b1.id}, #{offer_b2.id}"})

    # 4) Deal C 생성 + 참여 대량 + 일부 취소
    deal_c = create_deal(db, "Monitor C", buyers[4].id, 1)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Deal created: {deal_c.product_name} (id={deal_c.id}, desired={deal_c.desired_qty})"})
    p1 = add_participant(db, deal_c.id, buyers[2].id, 5)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Buyer#{buyers[2].id} joined deal#{deal_c.id} (qty=5)"})
    p2 = add_participant(db, deal_c.id, buyers[1].id, 10)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Buyer#{buyers[1].id} joined deal#{deal_c.id} (qty=10)"})

    # 하나 제거
    removed = crud.remove_participant(db, participant_id=p2.id)
    timeline.append({"time": iso(clock.tick(1)), "event": f"Participant removed: id={p2.id}, buyer_id={removed.get('buyer_id', '?')} (deal#{deal_c.id})"})

    # ---------- 집계 ----------
    # 전체 나열(이전 버전과 호환)
    deals = db.query(models.Deal).all()
    offers = db.query(models.Offer).all()

    result["buyers"] = [b.email for b in buyers]
    result["sellers"] = [s.email for s in sellers]
    result["deals"] = [{"id": d.id, "product_name": d.product_name} for d in deals]
    result["offers"] = {
        "deal_a": [offer1.id, offer2.id],
        "deal_b": [offer_b1.id, offer_b2.id],
    }

    # participants dump
    participants_dump = []
    for d in deals:
        for p in db.query(models.DealParticipant).filter(models.DealParticipant.deal_id == d.id).all():
            participants_dump.append({"deal_id": p.deal_id, "buyer_id": p.buyer_id, "qty": p.qty})
    result["participants"] = participants_dump

    # 포인트 잔액
    buyers_balance = {}
    sellers_balance = {}
    for b in buyers:
        buyers_balance[str(b.id)] = crud.get_user_balance(db, "buyer", b.id)
    for s in sellers:
        sellers_balance[str(s.id)] = crud.get_user_balance(db, "seller", s.id)
    result["point_balances"] = {"buyers": buyers_balance, "sellers": sellers_balance}

    # 단계별 현황(deal_progress)
    for d in deals:
        num_participants = db.query(models.DealParticipant).filter(models.DealParticipant.deal_id == d.id).count()
        num_offers = db.query(models.Offer).filter(models.Offer.deal_id == d.id).count()
        result_status = getattr(d, "status", "open")
        deal_progress.append({
            "deal_id": d.id,
            "product_name": d.product_name,
            "participants": num_participants,
            "offers": num_offers,
            "status": result_status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "deadline_at": d.deadline_at.isoformat() if getattr(d, "deadline_at", None) else None
        })

    result["deal_progress"] = deal_progress
    result["timeline"] = timeline

    # ---------- 저장 ----------
    out_name = "simulation_results_fullflow_v3_5.json"
    with open(out_name, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 시뮬레이션 완료 → {out_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-db", action="store_true", help="(선택) 외부 스크립트로 DB 초기화 수행했다고 표시만 함")
    args = parser.parse_args()
    run(reset_db=args.reset_db)

def run_simulation():
    print("✅ simulation_fullflow_v3_5 loaded successfully")