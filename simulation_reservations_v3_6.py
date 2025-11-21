# simulation_reservations_v3_6.py
# v3.6 — 예약/결제/만료/취소/오퍼확정(정상+비정상) 통합 시뮬레이터 (FULL)
# - 라운드: OPEN → (예약/결제/취소/만료/확정 시나리오) → FINALIZING → CLOSED
# - 정상 시나리오: 합법적 예약/결제, 전량판매 확인 후 확정(+30pt), 포인트 적립
# - 비정상 시나리오: 과예약(overbook), 잘못된 소유자 결제, 만료 후 결제 시도, PAID 취소 시도, 미완판 확정 시도 등
#
# 실행 예)
#   python simulation_reservations_v3_6.py --deal-id 1 --rounds 2 --seed 42 ^
#     --offers-per-round-min 2 --offers-per-round-max 3 --offer-capacity-min 5 --offer-capacity-max 12 ^
#     --pay-rate 0.75 --cancel-rate 0.1 --expire-rate 0.05 --overbook-rate 0.05 --wrong-owner-pay-rate 0.02 ^
#     --seller-early-confirm-rate 0.1 --output .\analysis\resv_sim_v3_6.json --root-output .\resv_sim_v3_6.json
#
# 출력: 상세 JSON 리포트 (정상/에러 카운트, 라운드별 상태, 포인트 요약, 수량 기반 불변성 검사)

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

# 내부 모듈
from app.database import SessionLocal
from app.models import (
    Deal, DealParticipant, Offer, Buyer, Seller,
    Reservation, ReservationStatus,
)
from app.crud import (
    # 라운드 제어
    open_round, finalize_round, close_round, get_active_round,
    get_round_by_no, get_or_create_next_round,
    # 예약/결제/만료/확정
    get_offer_remaining_capacity, create_reservation, cancel_reservation,
    expire_reservations, pay_reservation, confirm_offer_if_soldout,
    # 에러 타입
    NotFoundError, ConflictError,
)

# ------------------------------
# Config
# ------------------------------
@dataclass
class SimConfig:
    deal_id: int
    rounds: int = 1
    seed: int = 42
    # 오퍼/바이어
    offers_per_round_min: int = 2
    offers_per_round_max: int = 3
    offer_capacity_min: int = 5
    offer_capacity_max: int = 12
    # 행동 비율(0.0~1.0)
    pay_rate: float = 0.6
    cancel_rate: float = 0.15
    expire_rate: float = 0.15
    overbook_rate: float = 0.10
    wrong_owner_pay_rate: float = 0.10
    seller_early_confirm_rate: float = 0.10
    # 포인트 정책
    buyer_point_per_qty: int = 1
    seller_point_on_confirm: int = 30
    # 리포트/검증
    assert_invariants: bool = True  # 수량 불변성 검사
    # 파일 출력
    output: str = "./analysis/resv_sim_v3_6.json"

# ------------------------------
# Utils
# ------------------------------
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None

def _rnd_price(r: random.Random, lo: float = 10.0, hi: float = 100.0) -> float:
    return round(r.uniform(lo, hi), 2)

def _ensure_seed_entities(db: Session, num_buyers: int = 10, num_sellers: int = 5) -> Tuple[List[int], List[int]]:
    """없으면 샘플 엔터티 생성, 있으면 기존 일부 활용."""
    buyer_ids = [b.id for b in db.query(Buyer).order_by(Buyer.id.asc()).limit(num_buyers).all()]
    seller_ids = [s.id for s in db.query(Seller).order_by(Seller.id.asc()).limit(num_sellers).all()]

    created = False
    while len(buyer_ids) < num_buyers:
        n = len(buyer_ids) + 1
        b = Buyer(email=f"buyer{n}@ex.com", password_hash="x", name=f"Buyer{n}",
                  created_at=_utcnow(), points=0, status="active")
        db.add(b); db.flush()
        buyer_ids.append(b.id); created = True

    while len(seller_ids) < num_sellers:
        n = len(seller_ids) + 1
        s = Seller(email=f"seller{n}@ex.com", password_hash="x", business_name=f"SellerBiz{n}",
                   business_number=f"SBN{n:05d}", created_at=_utcnow(), points=0)
        db.add(s); db.flush()
        seller_ids.append(s.id); created = True

    if created: db.commit()
    return buyer_ids, seller_ids

def _get_existing_participants(db: Session, deal_id: int) -> Dict[int, int]:
    rows = db.query(DealParticipant).filter(DealParticipant.deal_id == deal_id).all()
    return {r.buyer_id: r.qty for r in rows}

def _touch_participants(db: Session, r: random.Random, deal_id: int, buyer_pool: List[int]) -> None:
    """라운드 진입 시 참여자 약간 증감(선택)."""
    before = _get_existing_participants(db, deal_id)
    # 일부 바이어 수량 상향/하향
    keys = list(before.keys()); r.shuffle(keys)
    for b in keys[: max(1, len(keys)//2)]:
        change = r.randint(-2, 3)
        new_qty = max(0, before[b] + change)
        dp = db.query(DealParticipant).filter_by(deal_id=deal_id, buyer_id=b).one_or_none()
        if dp:
            dp.qty = new_qty; db.add(dp)
        else:
            dp = DealParticipant(deal_id=deal_id, buyer_id=b, qty=new_qty, created_at=_utcnow()); db.add(dp)

    # 신규 참여 몇 명
    add_count = min(r.randint(0, 2), len(buyer_pool))
    if add_count > 0:
        for b in r.sample(buyer_pool, k=add_count):
            if b in before: continue
            dp = DealParticipant(deal_id=deal_id, buyer_id=b, qty=r.randint(1, 3), created_at=_utcnow())
            db.add(dp)
    db.commit()

def _create_offers(db: Session, r: random.Random, deal_id: int, seller_pool: List[int],
                   count: int, cap_min: int, cap_max: int) -> List[int]:
    offer_ids: List[int] = []
    sellers = r.sample(seller_pool, k=min(count, len(seller_pool)))
    for sid in sellers:
        cap = r.randint(cap_min, cap_max)
        offer = Offer(
            deal_id=deal_id, seller_id=sid, price=_rnd_price(r),
            total_available_qty=cap, delivery_days=r.randint(1, 7),
            comment="resv_sim_v3_6", is_active=True, is_confirmed=False,
            created_at=_utcnow(),
        )
        # 초기 sold/reserved 0 보장
        offer.sold_qty = int(offer.sold_qty or 0)
        offer.reserved_qty = int(offer.reserved_qty or 0)
        db.add(offer); db.flush()
        offer_ids.append(offer.id)
    db.commit()
    return offer_ids

def _choose_buyer_for_reservation(r: random.Random, participants_map: Dict[int, int]) -> Optional[int]:
    if not participants_map: return None
    # 수량 큰 사람에 약간 가중
    weighted = []
    for b, qty in participants_map.items():
        weighted.extend([b] * max(1, qty))
    return r.choice(weighted) if weighted else None

# ------------------------------
# Single Round Simulation
# ------------------------------
def simulate_one_round(db: Session, cfg: SimConfig, r: random.Random,
                       buyer_pool: List[int], seller_pool: List[int], rn_counter: int) -> dict:
    # 선행: 열려있으면 닫고 새 라운드
    active = get_active_round(db, cfg.deal_id)
    if active:
        close_round(db, cfg.deal_id, active.round_no); db.commit()

    opened = open_round(db, cfg.deal_id, round_no=None)
    eff_round_no = opened.round_no
    opened_at = opened.started_at

    # 참여자 변동(선택)
    _touch_participants(db, r, cfg.deal_id, buyer_pool)
    participants = _get_existing_participants(db, cfg.deal_id)

    # 오퍼 생성
    offer_count = r.randint(cfg.offers_per_round_min, cfg.offers_per_round_max)
    offer_ids = _create_offers(db, r, cfg.deal_id, seller_pool, offer_count,
                               cfg.offer_capacity_min, cfg.offer_capacity_max)

    # -------------------------
    # 예약 생성(정상 + 과예약 시도)
    # -------------------------
    created_resv_ids: List[int] = []
    created_qty_by_id: Dict[int, int] = {}  # reservation_id -> qty
    errors: Dict[str, int] = {
        "overbook": 0, "wrong_owner_pay": 0, "pay_after_expire": 0,
        "cancel_after_paid": 0, "confirm_not_soldout": 0,
    }

    for oid in offer_ids:
        tries = r.randint(2, 5)
        for _ in range(tries):
            buyer_id = _choose_buyer_for_reservation(r, participants)
            if not buyer_id:
                continue
            remain = get_offer_remaining_capacity(db, oid)
            if remain <= 0:
                break

            # 과예약 시도 확률
            if r.random() < cfg.overbook_rate:
                req = remain + r.randint(1, max(1, remain))  # 남은 수량 초과 요청
            else:
                req = r.randint(1, min(3, remain))

            try:
                resv = create_reservation(
                    db, deal_id=cfg.deal_id, offer_id=oid, buyer_id=buyer_id,
                    qty=req, hold_minutes=5
                )
                created_resv_ids.append(resv.id)
                created_qty_by_id[resv.id] = resv.qty
            except ConflictError:
                errors["overbook"] += 1
            except Exception:
                errors["overbook"] += 1

    # 현재 PENDING 목록
    pending: List[Reservation] = db.query(Reservation)\
        .filter(Reservation.status == ReservationStatus.PENDING)\
        .order_by(Reservation.id.asc())\
        .all()

    # 만료 타겟 선정(일부를 과거로 보내고 스윕)
    to_expire = [resv for resv in pending if r.random() < cfg.expire_rate]
    now = _utcnow()
    for resv in to_expire:
        resv.expires_at = now - timedelta(minutes=1)
        db.add(resv)
    db.commit()
    _ = expire_reservations(db)  # 상태변경

    # 결제/취소/방치/오류유발 결제
    paid_ids: List[int] = []
    cancelled_ids: List[int] = []
    paid_qty = 0
    cancelled_qty = 0
    for resv in db.query(Reservation).filter(Reservation.status == ReservationStatus.PENDING).all():
        roll = r.random()
        if roll < cfg.cancel_rate:
            # 정상 취소
            try:
                cancel_reservation(db, reservation_id=resv.id, buyer_id=resv.buyer_id)
                cancelled_ids.append(resv.id)
                cancelled_qty += created_qty_by_id.get(resv.id, resv.qty)
            except Exception:
                pass
        elif roll < cfg.cancel_rate + cfg.pay_rate:
            # 정상 결제
            try:
                paid = pay_reservation(db, reservation_id=resv.id, buyer_id=resv.buyer_id,
                                       buyer_point_per_qty=cfg.buyer_point_per_qty)
                paid_ids.append(paid.id)
                paid_qty += created_qty_by_id.get(paid.id, paid.qty)
            except ConflictError as e:
                # (예: 순간적으로 만료경합 등)
                if "expired" in str(e).lower():
                    errors["pay_after_expire"] += 1
            except Exception:
                pass
        else:
            # 오류 유발: 잘못된 소유자로 결제 시도
            if r.random() < cfg.wrong_owner_pay_rate:
                wrong_buyer = resv.buyer_id + 999  # 틀린 소유자
                try:
                    _ = pay_reservation(db, reservation_id=resv.id, buyer_id=wrong_buyer,
                                        buyer_point_per_qty=cfg.buyer_point_per_qty)
                except ConflictError:
                    errors["wrong_owner_pay"] += 1
                except Exception:
                    errors["wrong_owner_pay"] += 1
            # 아무것도 안 함 → PENDING 유지

    # 이미 PAID 된 건을 취소 시도(오류 기대)
    paid_rows = db.query(Reservation).filter(Reservation.status == ReservationStatus.PAID).all()
    for pr in paid_rows:
        try:
            cancel_reservation(db, reservation_id=pr.id, buyer_id=pr.buyer_id)
        except ConflictError:
            errors["cancel_after_paid"] += 1

    # 미완판 확정 시도(비정상)
    for oid in offer_ids:
        if random.random() < cfg.seller_early_confirm_rate:
            try:
                confirm_offer_if_soldout(db, offer_id=oid, seller_point_on_confirm=cfg.seller_point_on_confirm)
            except ConflictError:
                errors["confirm_not_soldout"] += 1

    # 정상 확정: 전량 판매된 오퍼만
    confirmed_offers: List[int] = []
    for oid in offer_ids:
        off = db.get(Offer, oid)
        total = int(off.total_available_qty or 0)
        sold = int(off.sold_qty or 0)
        if sold >= total and total > 0:
            try:
                confirm_offer_if_soldout(db, offer_id=oid, seller_point_on_confirm=cfg.seller_point_on_confirm)
                confirmed_offers.append(oid)
            except Exception:
                pass

    # 라운드 종료 전, 만료/보류 수량 집계
    if created_resv_ids:
        expired_rows = db.query(Reservation).filter(
            Reservation.id.in_(created_resv_ids),
            Reservation.status == ReservationStatus.EXPIRED
        ).all()
        expired_count = len(expired_rows)
        expired_qty = sum(r_.qty for r_ in expired_rows)

        pending_rows = db.query(Reservation).filter(
            Reservation.id.in_(created_resv_ids),
            Reservation.status == ReservationStatus.PENDING
        ).all()
        pending_end = len(pending_rows)
        pending_end_qty = sum(r_.qty for r_ in pending_rows)
    else:
        expired_count = 0
        expired_qty = 0
        pending_end = 0
        pending_end_qty = 0

    # 라운드 마감
    finalize_round(db, deal_id=cfg.deal_id, round_no=eff_round_no)
    close_round(db, deal_id=cfg.deal_id, round_no=eff_round_no)
    closed = get_round_by_no(db, cfg.deal_id, eff_round_no); closed_at = closed.ended_at
    db.commit()

    # 리포트 구성
    offer_snap = []
    for oid in offer_ids:
        off = db.get(Offer, oid)
        offer_snap.append({
            "offer_id": oid,
            "seller_id": off.seller_id,
            "price": float(off.price),
            "total": int(off.total_available_qty or 0),
            "sold": int(off.sold_qty or 0),
            "reserved": int(off.reserved_qty or 0),
            "confirmed": bool(off.is_confirmed),
        })

    created_qty = sum(created_qty_by_id.values())
    counters = {
        # 건수
        "reservations_created": len(created_resv_ids),
        "reservations_paid": len(paid_ids),
        "reservations_cancelled": len(cancelled_ids),
        "reservations_expired": expired_count,
        "reservations_pending_end": pending_end,
        "offers_confirmed": len(confirmed_offers),
        # 수량
        "qty": {
            "created": created_qty,
            "paid": paid_qty,
            "cancelled": cancelled_qty,
            "expired": expired_qty,
            "pending_end": pending_end_qty,
        },
    }

    # 불변성 검사 (생략 가능)
    if cfg.assert_invariants:
        left = counters["qty"]["created"]
        right = counters["qty"]["paid"] + counters["qty"]["cancelled"] + counters["qty"]["expired"] + counters["qty"]["pending_end"]
        if left != right:
            print(f"[WARN][round {eff_round_no}] qty mismatch: created={left} vs paid+cancelled+expired+pending_end={right}")

        # 오퍼 레벨: 모델 카운터 vs 실제 예약 집계 비교
        for oid in offer_ids:
            off = db.get(Offer, oid)
            pending_qty_db = sum(q.qty for q in db.query(Reservation).filter(
                Reservation.offer_id == oid,
                Reservation.status == ReservationStatus.PENDING
            ).all())
            paid_qty_db = sum(q.qty for q in db.query(Reservation).filter(
                Reservation.offer_id == oid,
                Reservation.status == ReservationStatus.PAID
            ).all())

            if pending_qty_db != int(off.reserved_qty or 0):
                print(f"[WARN][round {eff_round_no}] offer {oid} reserved_qty mismatch: model={off.reserved_qty}, db_pending_sum={pending_qty_db}")
            if paid_qty_db != int(off.sold_qty or 0):
                print(f"[WARN][round {eff_round_no}] offer {oid} sold_qty mismatch: model={off.sold_qty}, db_paid_sum={paid_qty_db}")
            if (int(off.sold_qty or 0) + int(off.reserved_qty or 0)) > int(off.total_available_qty or 0):
                print(f"[WARN][round {eff_round_no}] offer {oid} capacity overflow: sold+reserved > total")

    return {
        "round_no": eff_round_no,
        "timestamps": {"opened_at": _iso(opened_at), "closed_at": _iso(closed_at)},
        "offers": offer_snap,
        "counters": counters,
        "errors": errors,
    }

# ------------------------------
# Runner
# ------------------------------
def run(cfg: SimConfig) -> dict:
    r = random.Random(cfg.seed)
    report: Dict[str, object] = {
        "deal_id": cfg.deal_id,
        "seed": cfg.seed,
        "rounds": [],
        "summary": {},
        "generated_at": _iso(_utcnow()),
    }
    with SessionLocal() as db:
        # 선행 검증
        deal = db.get(Deal, cfg.deal_id)
        if not deal:
            raise NotFoundError(f"Deal not found: {cfg.deal_id}")

        buyers, sellers = _ensure_seed_entities(db, num_buyers=12, num_sellers=6)

        for i in range(1, cfg.rounds + 1):
            info = simulate_one_round(db, cfg, r, buyers, sellers, i)
            report["rounds"].append(info)

        # 요약
        total_errs: Dict[str, int] = {}
        totals = {
            "offers_confirmed": 0,
            # 건수
            "resv_created": 0, "paid": 0, "cancelled": 0, "expired": 0, "pending_end": 0,
            # 수량
            "qty": {"created": 0, "paid": 0, "cancelled": 0, "expired": 0, "pending_end": 0},
        }
        for rd in report["rounds"]:
            c = rd["counters"]; q = c["qty"]
            totals["offers_confirmed"] += c["offers_confirmed"]
            totals["resv_created"]     += c["reservations_created"]
            totals["paid"]             += c["reservations_paid"]
            totals["cancelled"]        += c["reservations_cancelled"]
            totals["expired"]          += c["reservations_expired"]
            totals["pending_end"]      += c["reservations_pending_end"]
            # qty
            totals["qty"]["created"]   += q["created"]
            totals["qty"]["paid"]      += q["paid"]
            totals["qty"]["cancelled"] += q["cancelled"]
            totals["qty"]["expired"]   += q["expired"]
            totals["qty"]["pending_end"] += q["pending_end"]

            for k, v in rd["errors"].items():
                total_errs[k] = total_errs.get(k, 0) + v

        report["summary"] = {
            "totals": totals,
            "errors": total_errs,
        }
    return report

def main():
    import argparse
    p = argparse.ArgumentParser(description="v3.6 reservations simulator (normal + abnormal)")
    p.add_argument("--deal-id", type=int, required=True)
    p.add_argument("--rounds", type=int, default=1)
    p.add_argument("--seed", type=int, default=42)

    p.add_argument("--offers-per-round-min", type=int, default=2)
    p.add_argument("--offers-per-round-max", type=int, default=3)
    p.add_argument("--offer-capacity-min", type=int, default=5)
    p.add_argument("--offer-capacity-max", type=int, default=12)

    p.add_argument("--pay-rate", type=float, default=0.6)
    p.add_argument("--cancel-rate", type=float, default=0.15)
    p.add_argument("--expire-rate", type=float, default=0.15)
    p.add_argument("--overbook-rate", type=float, default=0.10)
    p.add_argument("--wrong-owner-pay-rate", type=float, default=0.10)
    p.add_argument("--seller-early-confirm-rate", type=float, default=0.10)

    p.add_argument("--buyer-point-per-qty", type=int, default=1)
    p.add_argument("--seller-point-on-confirm", type=int, default=30)

    p.add_argument("--output", type=str, default="./analysis/resv_sim_v3_6.json")
    p.add_argument("--root-output", type=str, default=None,
                   help="선택: 결과 JSON을 추가로 저장할 경로 (예: ./resv_sim_v3_6.json)")

    # 불변성 검사 on/off
    p.add_argument("--no-assert-invariants", action="store_true",
                   help="지정 시 라운드 종료 후 불변성(수량 정합) 검사를 생략")

    args = p.parse_args()

    cfg = SimConfig(
        deal_id=args.deal_id, rounds=args.rounds, seed=args.seed,
        offers_per_round_min=args.offers_per_round_min,
        offers_per_round_max=args.offers_per_round_max,
        offer_capacity_min=args.offer_capacity_min,
        offer_capacity_max=args.offer_capacity_max,
        pay_rate=args.pay_rate, cancel_rate=args.cancel_rate, expire_rate=args.expire_rate,
        overbook_rate=args.overbook_rate, wrong_owner_pay_rate=args.wrong_owner_pay_rate,
        seller_early_confirm_rate=args.seller_early_confirm_rate,
        buyer_point_per_qty=args.buyer_point_per_qty,
        seller_point_on_confirm=args.seller_point_on_confirm,
        assert_invariants=not args.no_assert_invariants,
        output=args.output,
    )

    result = run(cfg)

    # 기본 출력
    out = Path(cfg.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"✅ simulation completed. saved -> {out.resolve()}")

    # 루트(또는 임의 경로) 추가 저장
    if args.root_output:
        root_out = Path(args.root_output)
        root_out.parent.mkdir(parents=True, exist_ok=True)
        with root_out.open("w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"📄 also saved -> {root_out.resolve()}")

if __name__ == "__main__":
    main()