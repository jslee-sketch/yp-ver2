# simulation_fullflow_v3_6.py
from __future__ import annotations
r"""
v3.6 — DealRound 단위 자동 시뮬레이션 (예약/결제 기반)

- 자동 배분 제거
- 바이어가 오퍼를 선택해 예약(PENDING) → 결제(PAID) or 만료(EXPIRED)
- 오퍼 전량 판매되면 셀러 오퍼 확정(+30pt)
- 바이어 포인트: 결제 성공 qty당 +1
- 결과 JSON 저장

예)
python .\\simulation_fullflow_v3_6.py --deal-id 1 --rounds 1 --seed 123 ^
  --offer-capacity-min 5 --offer-capacity-max 15 ^
  --output .\\analysis\\captest_v36.json
"""

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Deal, DealParticipant, Offer, Buyer, Seller, Reservation,
)
from app.crud import (
    open_round, finalize_round, close_round, get_round_by_no, get_active_round, NotFoundError,
    create_reservation, pay_reservation, cancel_reservation, expire_reservations,
    confirm_offer_if_soldout, get_offer_remaining_capacity,
)

# ------------------------------
# 설정/규칙
# ------------------------------
@dataclass
class SimConfig:
    deal_id: int
    rounds: int = 3
    seed: int = 42
    min_new_buyers: int = 1
    max_new_buyers: int = 3
    min_offer_count: int = 2
    max_offer_count: int = 4
    buyer_point_per_qty_on_close: int = 1     # 결제 성공 시 qty당 적립
    seller_point_on_confirm: int = 30         # 오퍼 전량 판매 후 확정 시
    price_min: float = 10.0
    price_max: float = 100.0
    offer_capacity_min: int = 5               # 오퍼 용량 하한
    offer_capacity_max: int = 20              # 오퍼 용량 상한
    output: str = "./analysis/simulation_results_v3_6.json"

# ------------------------------
# 유틸
# ------------------------------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _iso_utc(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()

def _rnd_price(r: random.Random, lo: float, hi: float) -> float:
    return round(r.uniform(lo, hi), 2)

def _ensure_seed_entities(db: Session, num_buyers: int = 8, num_sellers: int = 5) -> Tuple[List[int], List[int]]:
    buyer_ids = [b.id for b in db.query(Buyer).order_by(Buyer.id.asc()).limit(num_buyers).all()]
    seller_ids = [s.id for s in db.query(Seller).order_by(Seller.id.asc()).limit(num_sellers).all()]
    created = False
    while len(buyer_ids) < num_buyers:
        n = len(buyer_ids) + 1
        b = Buyer(email=f"buyer{n}@ex.com", password_hash="x", name=f"Buyer{n}", points=0)
        db.add(b); db.flush(); buyer_ids.append(b.id); created = True
    while len(seller_ids) < num_sellers:
        n = len(seller_ids) + 1
        s = Seller(email=f"seller{n}@ex.com", password_hash="x",
                   business_name=f"SellerBiz{n}", business_number=f"SBN{n:05d}", points=0)
        db.add(s); db.flush(); seller_ids.append(s.id); created = True
    if created:
        db.commit()
    return buyer_ids, seller_ids

def _get_existing_participants(db: Session, deal_id: int) -> Dict[int, int]:
    rows = db.query(DealParticipant).filter(DealParticipant.deal_id == deal_id).all()
    return {r.buyer_id: r.qty for r in rows}

def _set_participant_qty(db: Session, deal_id: int, buyer_id: int, qty: int) -> None:
    dp = db.query(DealParticipant).filter(
        DealParticipant.deal_id == deal_id, DealParticipant.buyer_id == buyer_id
    ).one_or_none()
    if qty <= 0:
        if dp:
            db.delete(dp)
        return
    if dp:
        dp.qty = qty
        db.add(dp)
    else:
        db.add(DealParticipant(deal_id=deal_id, buyer_id=buyer_id, qty=qty))

def _create_offers_for_round(
    db: Session, r: random.Random, deal_id: int, seller_pool: List[int], count: int, round_no: int, cfg: SimConfig
) -> List[int]:
    offer_ids: List[int] = []
    chosen_sellers = r.sample(seller_pool, k=min(count, len(seller_pool)))
    for sid in chosen_sellers:
        price = _rnd_price(r, cfg.price_min, cfg.price_max)
        capacity = r.randint(cfg.offer_capacity_min, cfg.offer_capacity_max)
        offer = Offer(
            deal_id=deal_id, seller_id=sid, price=price,
            total_available_qty=capacity, delivery_days=r.randint(1, 7),
            comment=f"round_no={round_no}", is_active=True, is_confirmed=False
        )
        db.add(offer); db.flush(); offer_ids.append(offer.id)
    return offer_ids

# ------------------------------
# 예약/결제 시뮬 헬퍼
# ------------------------------
def _simulate_reservations_and_payments(
    db: Session, r: random.Random, *, deal_id: int, buyer_ids: List[int], offer_ids: List[int], cfg: SimConfig
) -> Dict[str, Any]:
    """
    - 각 바이어가 임의의 오퍼 1개를 골라 일부 수량 예약(PENDING)
    - 절반은 결제(PAID), 나머지는 만료 스윕으로 EXPIRED
    - 전량 판매된 오퍼는 확정(+30pt)
    - 결과에 allocations(결제된 수량 기준), clearing_price(가중평균) 포함
    """
    created: List[int] = []
    paid: List[int] = []
    expired: List[int] = []
    allocations: List[Dict[str, Any]] = []

    # 1) 예약 생성
    for buyer_id in buyer_ids:
        if not offer_ids:
            break
        offer_id = r.choice(offer_ids)
        remain = get_offer_remaining_capacity(db, offer_id)
        if remain <= 0:
            continue
        want = r.randint(1, min(5, remain))
        try:
            resv = create_reservation(
                db, deal_id=deal_id, offer_id=offer_id,
                buyer_id=buyer_id, qty=want, hold_minutes=5
            )
            created.append(resv.id)
        except Exception:
            pass

    # 2) 결제/만료 분기
    r.shuffle(created)
    to_pay = created[: max(1, len(created)//2)]
    to_expire = set(created) - set(to_pay)

    for rid in to_pay:
        try:
            buyer_id = db.get(Reservation, rid).buyer_id
            resv = pay_reservation(
                db, reservation_id=rid, buyer_id=buyer_id,
                buyer_point_per_qty=cfg.buyer_point_per_qty_on_close
            )
            paid.append(rid)
            off = db.get(Offer, resv.offer_id)
            allocations.append({
                "offer_id": off.id, "seller_id": off.seller_id,
                "price": float(off.price), "allocated_qty": resv.qty
            })
        except Exception:
            pass

    # 만료 스윕
    expire_reservations(db)
    expired = list(to_expire)

    # 3) 전량 판매된 오퍼 확정(+30pt)
    confirmed_offers: List[int] = []
    for oid in offer_ids:
        try:
            before = db.get(Offer, oid).is_confirmed
            confirm_offer_if_soldout(db, offer_id=oid, seller_point_on_confirm=cfg.seller_point_on_confirm)
            after = db.get(Offer, oid).is_confirmed
            if not before and after:
                confirmed_offers.append(oid)
        except Exception:
            pass

    # 4) 가중평균가 (결제된 할당 기준)
    if allocations:
        wsum = sum(a["price"] * a["allocated_qty"] for a in allocations)
        qty = sum(a["allocated_qty"] for a in allocations)
        clearing = round(wsum / qty, 2) if qty else None
    else:
        clearing = None

    # 5) 보조 정보(디버그용): 오퍼 상세
    offers_detail = [
        {
            "offer_id": o.id, "seller_id": o.seller_id, "price": float(o.price),
            "capacity": int(o.total_available_qty or 0),
            "sold_qty": int(o.sold_qty or 0), "reserved_qty": int(o.reserved_qty or 0),
            "is_confirmed": bool(o.is_confirmed)
        }
        for o in db.query(Offer).filter(Offer.id.in_(offer_ids)).all()
    ]

    # 6) seller_points 페이로드(확정된 오퍼만 보고서용 표시)
    seller_points = []
    for oid in confirmed_offers:
        off = db.get(Offer, oid)
        seller_points.append({"seller_id": off.seller_id, "amount": cfg.seller_point_on_confirm, "offer_id": oid})

    # 7) buyer_points(보고서용): 이 라운드에서 결제된 예약만 합산
    buyer_points = []
    for rid in paid:
        resv = db.get(Reservation, rid)
        buyer_points.append({"buyer_id": resv.buyer_id, "amount": cfg.buyer_point_per_qty_on_close * resv.qty})

    return {
        "reservations_created": created,
        "reservations_paid": paid,
        "reservations_expired": expired,
        "allocations": allocations,
        "seller_points": seller_points,
        "buyer_points": buyer_points,
        "clearing_price": clearing,
        "offers_detail": offers_detail,
    }

# ------------------------------
# 라운드 시뮬레이션
# ------------------------------
def simulate_round(
    db: Session, deal_id: int, round_no: int, r: random.Random,
    buyer_pool: List[int], seller_pool: List[int], cfg: SimConfig
) -> Dict[str, Any]:
    # 기존 OPEN 라운드 정리
    active = get_active_round(db, deal_id)
    if active:
        close_round(db, deal_id, active.round_no)
        db.commit()

    # 새 라운드 OPEN
    opened = open_round(db, deal_id=deal_id, round_no=None)
    eff_round_no = opened.round_no
    opened_at = opened.started_at

    # 참여자 변화(간단 샘플)
    before = _get_existing_participants(db, deal_id)
    new_count = r.randint(cfg.min_new_buyers, cfg.max_new_buyers)
    new_buyers = r.sample(buyer_pool, k=min(new_count, len(buyer_pool)))
    for b in new_buyers:
        base_qty = r.randint(1, 3)
        prev = before.get(b, 0)
        _set_participant_qty(db, deal_id, b, prev + base_qty)
    # 기존 일부 수정
    existing_ids = list(before.keys())
    r.shuffle(existing_ids)
    for b in existing_ids[: max(1, len(existing_ids)//2)]:
        change = r.randint(-2, 2)
        _set_participant_qty(db, deal_id, b, max(0, before[b] + change))
    db.commit()
    mid = _get_existing_participants(db, deal_id)

    # 오퍼 생성
    offer_count = r.randint(cfg.min_offer_count, cfg.max_offer_count)
    offer_ids = _create_offers_for_round(db, r, deal_id, seller_pool, offer_count, eff_round_no, cfg)
    db.commit()

    # 예약/결제/만료/확정
    buyers_in_round = list(mid.keys())
    outcome = _simulate_reservations_and_payments(
        db, r, deal_id=deal_id, buyer_ids=buyers_in_round, offer_ids=offer_ids, cfg=cfg
    )

    # FINALIZE → CLOSE
    finalize_round(db, deal_id=deal_id, round_no=eff_round_no)
    close_round(db, deal_id=deal_id, round_no=eff_round_no)
    closed_row = get_round_by_no(db, deal_id, eff_round_no)
    closed_at = closed_row.ended_at
    db.commit()

    after = _get_existing_participants(db, deal_id)

    return {
        "round_no": eff_round_no,
        "participants_before": before,
        "participants_after": after,
        "offers": offer_ids,
        "outcome": {
            "allocations": outcome["allocations"],
            "buyer_points": outcome["buyer_points"],
            "seller_points": outcome["seller_points"],
            "clearing_price": outcome["clearing_price"],
            "reservations": {
                "created": outcome["reservations_created"],
                "paid": outcome["reservations_paid"],
                "expired": outcome["reservations_expired"],
            },
            "offers_detail": outcome["offers_detail"],
        },
        "timestamps": {
            "opened_at": _iso_utc(opened_at),
            "closed_at": _iso_utc(closed_at),
        },
    }

# ------------------------------
# 전체 시뮬레이션
# ------------------------------
def run_simulation(cfg: SimConfig) -> Dict[str, Any]:
    r = random.Random(cfg.seed)
    results: Dict[str, Any] = {
        "deal_id": cfg.deal_id, "seed": cfg.seed, "rounds": [],
        "summary": {}, "generated_at": _iso_utc(_utcnow())
    }

    with SessionLocal() as db:
        deal = db.get(Deal, cfg.deal_id)
        if not deal:
            raise NotFoundError(f"Deal not found: {cfg.deal_id}")

        buyer_pool, seller_pool = _ensure_seed_entities(db, num_buyers=8, num_sellers=5)

        for rn in range(1, cfg.rounds + 1):
            info = simulate_round(db, cfg.deal_id, rn, r, buyer_pool, seller_pool, cfg)
            results["rounds"].append(info)

        # 요약
        final_participants = _get_existing_participants(db, cfg.deal_id)
        last = results["rounds"][-1]["outcome"] if results["rounds"] else {}
        results["summary"] = {
            "final_participants": final_participants,
            "last_clearing_price": last.get("clearing_price"),
        }
    return results

# ------------------------------
# 외부에서 바로 부를 수 있도록 run 제공
# ------------------------------
def run(cfg: SimConfig) -> Dict[str, Any]:
    return run_simulation(cfg)

# ------------------------------
# CLI
# ------------------------------
def main() -> None:
    p = argparse.ArgumentParser(description="v3.6 DealRound fullflow simulator (reservation-based)")
    p.add_argument("--deal-id", type=int, required=True)
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--output", type=str, default="./analysis/simulation_results_v3_6.json")
    p.add_argument("--price-min", type=float, default=10.0)
    p.add_argument("--price-max", type=float, default=100.0)
    p.add_argument("--buyer-point-per-qty", type=int, default=1)
    p.add_argument("--seller-point-on-confirm", type=int, default=30)
    p.add_argument("--offer-capacity-min", type=int, default=5)
    p.add_argument("--offer-capacity-max", type=int, default=20)
    args = p.parse_args()

    cfg = SimConfig(
        deal_id=args.deal_id, rounds=args.rounds, seed=args.seed,
        price_min=args.price_min, price_max=args.price_max,
        buyer_point_per_qty_on_close=args.buyer_point_per_qty,
        seller_point_on_confirm=args.seller_point_on_confirm,
        offer_capacity_min=args.offer_capacity_min, offer_capacity_max=args.offer_capacity_max,
        output=args.output,
    )
    results = run_simulation(cfg)

    out = Path(cfg.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅ simulation finished. saved -> {out.resolve()}")

if __name__ == "__main__":  # pragma: no cover
    main()