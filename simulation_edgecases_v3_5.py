# simulation_edgecases_v3_5.py
# YeokPing v3.5 Edge-Case Simulation (AUTO VERIFY + DEADTIME DEADLINES)
# Author: You
# Usage:
#   python simulation_edgecases_v3_5.py
#   python simulation_edgecases_v3_5.py --reset-db

import os
import sys
import json
import random
from dataclasses import dataclass, asdict
from datetime import datetime
from argparse import ArgumentParser
from sqlalchemy import func


# --- App imports (현재 코드베이스 기준) ---
from app.database import SessionLocal, engine, Base
from app import models, crud
from app.config.feature_flags import FEATURE_FLAGS
from app.config import time_policy

print("✅ Using database:", os.getenv("DATABASE_URL", "sqlite:///./app/ypver2.db"))

# --------------------------------------------------
# CLI
# --------------------------------------------------
parser = ArgumentParser()
parser.add_argument("--reset-db", action="store_true", help="Drop & recreate all tables")
args = parser.parse_args()

# --------------------------------------------------
# DB 초기화 (선택)
# --------------------------------------------------
if args.reset_db:
    print("🧨 RESET_DB=True → 모든 테이블 드롭 후 재생성합니다.")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
else:
    # 안전하게 테이블 생성 보장
    Base.metadata.create_all(bind=engine)

db = SessionLocal()

# --------------------------------------------------
# 유틸
# --------------------------------------------------
def utcnow_iso():
    return datetime.utcnow().isoformat()

def choose(dist):  # dist = [(value, weight), ...]
    total = sum(w for _, w in dist)
    r = random.uniform(0, total)
    upto = 0
    for val, w in dist:
        if upto + w >= r:
            return val
        upto += w
    return dist[-1][0]

@dataclass
class CaseResult:
    name: str
    ok: bool
    detail: str
    extra: dict | None = None

# Fail/Pass 수집
case_results: list[CaseResult] = []
def pass_case(name, detail="", extra=None):
    case_results.append(CaseResult(name=name, ok=True, detail=detail, extra=extra))

def fail_case(name, detail, extra=None):
    case_results.append(CaseResult(name=name, ok=False, detail=detail, extra=extra))

# --------------------------------------------------
# 시드 데이터 생성
# --------------------------------------------------
def seed_buyers(n=10):
    buyers = []
    from passlib.hash import bcrypt
    for i in range(n):
        b = models.Buyer(
            email=f"buyer{i}_{random.randint(1000,9999)}@test.com",
            password_hash=bcrypt.hash(("pw"+str(i))[:72]),
            name=f"Buyer {i}",
        )
        db.add(b)
        db.commit()
        db.refresh(b)
        buyers.append(b)
    return buyers

def seed_sellers(n=6):
    sellers = []
    from passlib.hash import bcrypt
    for i in range(n):
        s = models.Seller(
            email=f"seller{i}_{random.randint(1000,9999)}@test.com",
            password_hash=bcrypt.hash(("pw"+str(i))[:72]),
            business_name=f"Seller Biz {i}",
            business_number=f"SN-{i}-{random.randint(10000,99999)}",
        )
        # AUTO_VERIFY_SELLER 플래그 반영
        if FEATURE_FLAGS.get("AUTO_VERIFY_SELLER"):
            s.verified_at = datetime.utcnow()
        db.add(s)
        db.commit()
        db.refresh(s)
        sellers.append(s)
    return sellers

def seed_deals(buyers, m=5):
    deals = []
    for i in range(m):
        creator = random.choice(buyers)
        d_in = crud.schemas.DealCreate(
            product_name=f"Product {i}",
            creator_id=creator.id,
            desired_qty=random.choice([1,2,3,5,10]),
            free_text="edge-case test deal",
        )
        d = crud.create_deal(db, d_in)
        deals.append(d)
    return deals

def add_participants(deal, buyers, k=3):
    # 방장 자동참여는 이미 create_deal에서 처리됨
    others = [b for b in buyers if b.id != deal.creator_id]
    picked = random.sample(others, min(k, len(others)))
    for b in picked:
        p = crud.schemas.DealParticipantCreate(
            deal_id=deal.id, buyer_id=b.id, qty=random.choice([1,1,2,3,5])
        )
        crud.add_participant(db, p)

def post_offer(deal, seller, price, total_qty, free_text=None):
    o_in = crud.schemas.OfferCreate(
        deal_id=deal.id,
        seller_id=seller.id,
        price=price,
        total_available_qty=total_qty,
        free_text=free_text or "edge-case offer",
    )
    return crud.create_offer(db, o_in)

# --------------------------------------------------
# 검증 헬퍼
# --------------------------------------------------
def total_participant_qty(deal_id: int) -> int:
    total = db.query(models.DealParticipant)\
              .filter(models.DealParticipant.deal_id==deal_id)\
              .with_entities(func.coalesce(func.sum(models.DealParticipant.qty), 0))\
              .scalar()
    return int(total or 0)

def offers_by_deal(deal_id: int):
    return db.query(models.Offer).filter(models.Offer.deal_id==deal_id).all()

# --------------------------------------------------
# Edge-Case 시나리오
# --------------------------------------------------
def scenario_many_sellers_compete(deal, sellers):
    """
    여러 판매자가 다양한 가격/수량으로 제안 → 정합성 체크
    """
    needed = deal.desired_qty + total_participant_qty(deal.id)
    # 세일즈 4명 뽑아서 다양한 가격/수량
    ss = random.sample(sellers, min(4, len(sellers)))
    created_ids = []
    try:
        for s in ss:
            price = choose([(9900,1),(10000,2),(10500,2),(11000,1)])
            qty = choose([(1,2),(needed//2 or 1,1),(needed,1),(needed+5,1)])
            o = post_offer(deal, s, price, qty, free_text=f"s{ s.id } propose")
            if o:
                created_ids.append(o.id)
        pass_case("many_sellers_compete", f"created offers: {created_ids}", {"needed_total": needed})
    except Exception as e:
        fail_case("many_sellers_compete", f"Exception {e!r}")

def scenario_partial_vs_full_match(deal, sellers):
    """
    동일 가격대에서 부분충족/완전충족 제안이 혼재 → 플래그/데이터 정합성만 검사
    """
    needed = deal.desired_qty + total_participant_qty(deal.id)
    s1, s2 = random.sample(sellers, 2)
    try:
        o1 = post_offer(deal, s1, price=10000, total_qty=max(1, needed-1), free_text="partial")
        o2 = post_offer(deal, s2, price=10000, total_qty=needed, free_text="full")
        ok = (o1 is not None) and (o2 is not None)
        if ok:
            pass_case("partial_vs_full_match", "partial + full offers placed",
                      {"needed": needed, "partial": o1.total_available_qty, "full": o2.total_available_qty})
        else:
            fail_case("partial_vs_full_match", "offer creation failed")
    except Exception as e:
        fail_case("partial_vs_full_match", f"Exception {e!r}")

def scenario_over_supply(deal, sellers):
    """
    필요한 수량보다 훨씬 많은 오퍼 수량 제시 → 생성은 허용(비즈 규칙은 이후 단계에서)
    """
    needed = deal.desired_qty + total_participant_qty(deal.id)
    s = random.choice(sellers)
    try:
        o = post_offer(deal, s, price=12000, total_qty=needed*3, free_text="over-supply")
        if o:
            pass_case("over_supply", "created oversupply offer",
                      {"needed": needed, "offered": o.total_available_qty})
        else:
            fail_case("over_supply", "offer creation failed")
    except Exception as e:
        fail_case("over_supply", f"Exception {e!r}")

def scenario_cancellation_paths(deal, sellers):
    """
    오퍼 생성 → 일부 취소 → 포인트/데이터 이상 여부 확인
    (현재 포인트는 오퍼 확정/취소에서만 반영—오퍼 삭제 시 seller 차감 로직은 별도 라우터 사용)
    여기선 DB 레벨에서 단순 삭제 경로 체크
    """
    s = random.choice(sellers)
    try:
        o = post_offer(deal, s, price=13000, total_qty=3, free_text="will-cancel")
        if not o:
            fail_case("offer_cancel_path", "offer not created")
            return
        # 삭제
        to_del = db.query(models.Offer).get(o.id)
        db.delete(to_del); db.commit()
        # 존재 확인
        exists = db.query(models.Offer).filter_by(id=o.id).first()
        if exists:
            fail_case("offer_cancel_path", "offer still exists after delete", {"offer_id": o.id})
        else:
            pass_case("offer_cancel_path", "offer deleted ok", {"offer_id": o.id})
    except Exception as e:
        fail_case("offer_cancel_path", f"Exception {e!r}")

def scenario_deadline_autoset(deal, sellers):
    """
    FEATURE_FLAGS.AUTO_SET_DEADLINES 가 True인 경우, deal/offer deadline_at 채워지는지 확인
    """
    try:
        # deal.deadline_at 존재 여부
        deal_ref = db.query(models.Deal).get(deal.id)
        deal_deadline_ok = (deal_ref.deadline_at is not None) if FEATURE_FLAGS.get("AUTO_SET_DEADLINES") else True

        s = random.choice(sellers)
        o = post_offer(deal_ref, s, price=12500, total_qty=2, free_text="deadline-check")
        off_ref = db.query(models.Offer).get(o.id) if o else None
        offer_deadline_ok = (off_ref and off_ref.deadline_at is not None) if FEATURE_FLAGS.get("AUTO_SET_DEADLINES") else True

        if deal_deadline_ok and offer_deadline_ok:
            pass_case("deadline_autoset", "deadline fields ok",
                      {"deal_deadline": str(deal_ref.deadline_at), "offer_deadline": str(off_ref.deadline_at) if off_ref else None})
        else:
            fail_case("deadline_autoset", "deadline missing",
                      {"deal_deadline": str(deal_ref.deadline_at), "offer_deadline": str(off_ref.deadline_at) if off_ref else None})
    except Exception as e:
        fail_case("deadline_autoset", f"Exception {e!r}")

def scenario_points_flow(buyers, sellers, deals):
    """
    포인트 흐름: 결제 → +20, 취소 → -20, 오퍼 확정 → 판매자 +30
    crud/routers에서 이미 검증했지만 다시 한 번 체인 테스트
    """
    try:
        # 1) 랜덤 참가자 결제 처리(+20)
        any_part = db.query(models.DealParticipant).first()
        if any_part:
            crud.reward_buyer_payment(db, buyer_id=any_part.buyer_id)

        # 2) 임의 참가자 취소(-20)
        any_part2 = db.query(models.DealParticipant).filter(models.DealParticipant.id != (any_part.id if any_part else -1)).first()
        if any_part2:
            crud.penalize_buyer_cancel(db, buyer_id=any_part2.buyer_id)

        # 3) 임의 오퍼 생성 후 확정(+30)
        d = random.choice(deals)
        s = random.choice(sellers)
        o = post_offer(d, s, price=14000, total_qty=1, free_text="will-confirm")
        if o:
            crud.confirm_offer_and_reward(db, o.id)

        pass_case("points_flow", "buyer +/-, seller +30 check executed")
    except Exception as e:
        fail_case("points_flow", f"Exception {e!r}")

def scenario_deposit_tracking(deal, buyers):
    """
    입금(Deposit) 기록 기능 플래그에 따라 동작 여부 확인
    """
    try:
        b = random.choice(buyers)
        dep = crud.create_buyer_deposit(db, deal_id=deal.id, buyer_id=b.id, amount=10000)
        if FEATURE_FLAGS.get("ENABLE_DEPOSIT_TRACKING"):
            if not dep:
                fail_case("deposit_tracking", "expected held deposit, got None")
                return
            # 환불
            dep2 = crud.refund_buyer_deposit(db, dep.id)
            ok = (dep2 and dep2.status == "refunded")
            if ok:
                pass_case("deposit_tracking", "held -> refunded ok", {"deposit_id": dep.id})
            else:
                fail_case("deposit_tracking", "refund failed", {"deposit_id": dep.id})
        else:
            if dep is None:
                pass_case("deposit_tracking", "disabled correctly returns None")
            else:
                fail_case("deposit_tracking", "should be disabled but created?", {"deposit_id": dep.id})
    except Exception as e:
        fail_case("deposit_tracking", f"Exception {e!r}")

# --------------------------------------------------
# 실행
# --------------------------------------------------
def run():
    random.seed(42)

    buyers = seed_buyers(12)
    sellers = seed_sellers(7)
    deals = seed_deals(buyers, 6)

    # 각 딜에 몇 명씩 더 붙이기
    for d in deals:
        add_participants(d, buyers, k=random.choice([2,3,5]))

    # 대표 딜 하나 골라 집중 Edge Case
    focus = random.choice(deals)

    scenario_many_sellers_compete(focus, sellers)
    scenario_partial_vs_full_match(focus, sellers)
    scenario_over_supply(focus, sellers)
    scenario_cancellation_paths(focus, sellers)
    scenario_deadline_autoset(focus, sellers)
    scenario_points_flow(buyers, sellers, deals)
    scenario_deposit_tracking(focus, buyers)

    # 요약/밸런스
    buyer_ids = [b.id for b in buyers]
    seller_ids = [s.id for s in sellers]

    buyer_bal = {str(bid): crud.get_user_balance(db, "buyer", bid) for bid in buyer_ids}
    seller_bal = {str(sid): crud.get_user_balance(db, "seller", sid) for sid in seller_ids}

    # 결과 JSON
    out = {
        "meta": {
            "version": "v3.5-edgecases",
            "started_at": utcnow_iso(),
            "reset_db": bool(args.reset_db),
            "db": os.getenv("DATABASE_URL", "sqlite:///./app/ypver2.db"),
            "flags": FEATURE_FLAGS,
        },
        "counts": {
            "buyers": len(buyers),
            "sellers": len(sellers),
            "deals": len(deals),
            "participants_total": db.query(models.DealParticipant).count(),
            "offers_total": db.query(models.Offer).count(),
        },
        "focus_deal": {
            "id": focus.id,
            "product_name": focus.product_name,
            "needed_qty": int(focus.desired_qty + total_participant_qty(focus.id)),
        },
        "cases": [asdict(c) for c in case_results],
        "point_balances": {
            "buyers": buyer_bal,
            "sellers": seller_bal,
        },
        "deal_summaries": [
            {
                "deal_id": d.id,
                "product_name": d.product_name,
                "participants": db.query(models.DealParticipant).filter_by(deal_id=d.id).count(),
                "offers": db.query(models.Offer).filter_by(deal_id=d.id).count(),
                "deadline_at": str(d.deadline_at) if d.deadline_at else None,
                "status": d.status,
            }
            for d in deals
        ],
    }

    fname = "simulation_results_edgecases_v3_5.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # 콘솔 요약
    ok_cnt = sum(1 for c in case_results if c.ok)
    ng_cnt = sum(1 for c in case_results if not c.ok)
    print(f"\n✅ Edgecases finished → {fname}")
    print(f"   PASS: {ok_cnt} / FAIL: {ng_cnt}")
    if ng_cnt:
        for c in case_results:
            if not c.ok:
                print(f"   ❌ {c.name}: {c.detail} (extra={c.extra})")

if __name__ == "__main__":
    run()