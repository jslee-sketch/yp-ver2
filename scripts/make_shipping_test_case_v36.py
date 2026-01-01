# scripts/make_shipping_test_case_v36.py
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app import crud, schemas, models


def _utcnow():
    return datetime.now(timezone.utc)


def _find_or_create_buyer(db: Session) -> models.Buyer:
    # ✅ EmailStr 통과용: example.com 사용
    email = "shipping_test_buyer@example.com"

    buyer = db.query(models.Buyer).filter(models.Buyer.email == email).first()
    if buyer:
        return buyer

    buyer_in = schemas.BuyerCreate(
        email=email,
        name="shipping test buyer",
        phone="010-0000-0000",
        address="test address",
        preferred_category="test",
        recommender_buyer_id=None,
    )
    return crud.create_buyer(db, buyer_in)


def _find_or_create_seller(db: Session) -> models.Seller:
    email = "shipping_test_seller@example.com"

    seller = db.query(models.Seller).filter(models.Seller.email == email).first()
    if seller:
        return seller

    seller_in = schemas.SellerCreate(
        email=email,
        business_name="shipping test seller",
        contact_name="seller owner",
        phone="010-1111-1111",
        business_address="seller address",
        business_number="000-00-00000",
        # ✅ SellerCreate는 established_date가 필수(현재 스키마 기준)
        established_date=_utcnow(),
        bank_name="testbank",
        bank_account="000-0000-0000",
        bank_holder="seller owner",
    )
    return crud.create_seller(db, seller_in)


def _create_deal(db: Session, creator_id: int) -> models.Deal:
    # DealCreate 스키마가 title/description이 아니라 product_name/creator_id 기반임(현재 schemas 기준)
    deal_in = schemas.DealCreate(
        product_name="shipping test product",
        desired_qty=10,
        creator_id=creator_id,
        free_text="auto-generated for refund shipping test",
    )
    return crud.create_deal(db, deal_in)


def _create_offer_per_qty(db: Session, deal_id: int, seller_id: int) -> models.Offer:
    # ✅ 네가 이미 OfferCreate에 shipping_* 추가해둔 상태를 가정.
    # 만약 아직이면(레거시) validation에서 터질 수 있으니 try/except로 안전하게.
    payload = dict(
        deal_id=deal_id,
        seller_id=seller_id,
        price=100000,
        total_available_qty=100,
        delivery_days=3,
        comment="shipping per-qty test offer",
        # v3.6 shipping fields
        shipping_mode="PER_QTY",
        shipping_fee_per_reservation=0,
        shipping_fee_per_qty=5000,
    )

    try:
        offer_in = schemas.OfferCreate(**payload)
    except Exception:
        # 레거시 OfferCreate(배송필드 없는 경우) fallback
        payload.pop("shipping_mode", None)
        payload.pop("shipping_fee_per_reservation", None)
        payload.pop("shipping_fee_per_qty", None)
        offer_in = schemas.OfferCreate(**payload)  # type: ignore

    offer = crud.create_offer(db, offer_in)

    # 레거시 fallback일 때, 모델에 필드가 있다면 직접 채워주기(테스트용)
    if hasattr(offer, "shipping_mode"):
        try:
            offer.shipping_mode = "PER_QTY"
            offer.shipping_fee_per_reservation = 0
            offer.shipping_fee_per_qty = 5000
            db.add(offer)
            db.commit()
            db.refresh(offer)
        except Exception:
            pass

    return offer


def _create_and_pay_reservation(db: Session, *, deal_id: int, offer_id: int, buyer_id: int, qty: int) -> models.Reservation:
    resv = crud.create_reservation(
        db,
        deal_id=deal_id,
        offer_id=offer_id,
        buyer_id=buyer_id,
        qty=qty,
        hold_minutes=30,
    )

    # 프로젝트에 pay_reservation_v35가 이미 있고 /v3_6/pay가 이걸 쓰는 상태라면 이게 제일 안전
    resv = crud.pay_reservation_v35(db, reservation_id=resv.id, buyer_id=buyer_id)
    return resv


def _print_preview(db: Session, reservation_id: int, actor: str, quantity_refund: int | None):
    # 네 스냅샷 기준: preview_refund_for_paid_reservation(return_meta=...) 지원
    try:
        ctx, decision, meta = crud.preview_refund_for_paid_reservation(
            db,
            reservation_id=reservation_id,
            actor=actor,
            quantity_refund=quantity_refund,
            return_meta=True,
            log_preview=False,   # 테스트 스팸 줄이기(원하면 True)
        )
        out = {
            "meta_supported": True,
            "cooling_state": str(ctx.cooling_state),
            "fault_party": str(ctx.fault_party),
            "trigger": str(ctx.trigger),
            "amount_goods_refund": int(ctx.amount_goods),
            "amount_shipping_refund": int(ctx.amount_shipping),
            "amount_total_refund": int(ctx.amount_total),
            "decision_use_pg_refund": bool(decision.use_pg_refund),
            "decision_note": decision.note,
            "meta": {
                "shipping_total_db": meta.get("shipping_total_db"),
                "shipping_total_calc": meta.get("shipping_total_calc"),
                "shipping_mismatch": meta.get("shipping_mismatch"),
                "shipping_refund_auto": meta.get("shipping_refund_auto"),
                "shipping_refund_final": meta.get("shipping_refund_final"),
                "shipping_refund_allowed_by_policy": meta.get("shipping_refund_allowed_by_policy"),
                "shipping_refund_override_applied": meta.get("shipping_refund_override_applied"),
            },
        }
    except Exception:
        # 구버전(2-tuple) 호환
        ctx, decision = crud.preview_refund_for_paid_reservation(
            db,
            reservation_id=reservation_id,
            actor=actor,
            quantity_refund=quantity_refund,
        )
        out = {
            "meta_supported": False,
            "cooling_state": str(ctx.cooling_state),
            "fault_party": str(ctx.fault_party),
            "trigger": str(ctx.trigger),
            "amount_goods_refund": int(ctx.amount_goods),
            "amount_shipping_refund": int(ctx.amount_shipping),
            "amount_total_refund": int(ctx.amount_total),
            "decision_use_pg_refund": bool(decision.use_pg_refund),
            "decision_note": decision.note,
        }

    print("=" * 80)
    print(f"reservation_id={reservation_id} actor={actor} quantity_refund={quantity_refund}")
    print(json.dumps(out, ensure_ascii=False, indent=2))


def main() -> int:
    db = SessionLocal()
    try:
        buyer = _find_or_create_buyer(db)
        seller = _find_or_create_seller(db)
        deal = _create_deal(db, creator_id=buyer.id)
        offer = _create_offer_per_qty(db, deal.id, seller.id)

        # qty=3으로 만들어서 부분환불(1/2/3) 배송비 배정 확인하기 좋게
        resv = _create_and_pay_reservation(db, deal_id=deal.id, offer_id=offer.id, buyer_id=buyer.id, qty=3)

        # BEFORE_SHIPPING 상태에서 actor별 preview
        for actor in ["buyer_cancel", "seller_cancel", "admin_force", "system_error", "dispute_resolve"]:
            _print_preview(db, resv.id, actor=actor, quantity_refund=1)
            _print_preview(db, resv.id, actor=actor, quantity_refund=2)
            _print_preview(db, resv.id, actor=actor, quantity_refund=None)  # remaining 전체

        print("\n[OK] make_shipping_test_case_v36 finished.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())