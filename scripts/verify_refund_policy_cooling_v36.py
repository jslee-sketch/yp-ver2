# scripts/verify_refund_policy_cooling_v36.py
from __future__ import annotations

import json
import sys
from datetime import timedelta

from app.database import SessionLocal
from app import models
from app.core.time_policy import _utcnow
from app.core.refund_policy import DEFAULT_COOLING_DAYS
from app.core.time_policy import _as_utc
from app import crud


ACTORS = ["buyer_cancel", "seller_cancel", "admin_force", "system_error", "dispute_resolve"]


def _dump(obj):
    print(json.dumps(obj, ensure_ascii=False))


def _set_stage(db, resv: models.Reservation, stage: str):
    """
    stage를 강제로 세팅해서 cooling_state가 기대대로 나오게 만든다.
    """
    now = _utcnow()

    if stage == "BEFORE_SHIPPING":
        resv.shipped_at = None
        resv.delivered_at = None
        resv.arrival_confirmed_at = None

    elif stage == "SHIPPED_NOT_DELIVERED":
        resv.shipped_at = now - timedelta(hours=1)
        resv.delivered_at = None
        resv.arrival_confirmed_at = None

    elif stage == "WITHIN_COOLING":
        # shipped는 과거, delivered는 최근(쿨링 내)
        resv.shipped_at = now - timedelta(days=1)
        resv.delivered_at = now - timedelta(hours=2)
        resv.arrival_confirmed_at = None

    elif stage == "AFTER_COOLING":
        # delivered를 충분히 과거로 밀어서 cooling out
        resv.shipped_at = now - timedelta(days=DEFAULT_COOLING_DAYS + 3)
        resv.delivered_at = now - timedelta(days=DEFAULT_COOLING_DAYS + 1)
        resv.arrival_confirmed_at = None

    else:
        raise ValueError(f"unknown stage={stage}")

    db.add(resv)
    db.commit()
    db.refresh(resv)


def _pick_policy_gate(meta: dict) -> dict:
    """
    meta 내 policy_gate만 뽑아 출력/검증에 사용
    """
    out = {}
    if not meta:
        return out
    # 네 구현은 meta에 shipping_refund_allowed_by_policy, auto, final 등이 들어있음
    for k in ("shipping_refund_allowed_by_policy", "shipping_refund_auto", "shipping_refund_final"):
        if k in meta:
            out[k] = meta.get(k)
    return out


# ✅ v3.6 배송비 환불 gate 정책표(SSOT) — B안 반영 완료
# - dispute_resolve는 stage 무관 True
EXPECTED_GATE = {
    "BEFORE_SHIPPING": {
        "buyer_cancel": True,
        "seller_cancel": True,
        "admin_force": True,
        "system_error": True,
        "dispute_resolve": True,
    },
    "SHIPPED_NOT_DELIVERED": {
        "buyer_cancel": False,
        "seller_cancel": True,
        "admin_force": True,
        "system_error": True,
        "dispute_resolve": True,  # ✅ B안 핵심 변경점
    },
    "WITHIN_COOLING": {
        "buyer_cancel": False,
        "seller_cancel": True,
        "admin_force": True,
        "system_error": True,
        "dispute_resolve": True,  # ✅ B안 핵심 변경점
    },
    "AFTER_COOLING": {
        "buyer_cancel": False,
        "seller_cancel": False,
        "admin_force": False,
        "system_error": False,
        "dispute_resolve": True,  # (기존에도 True였음)
    },
}


def main():
    if len(sys.argv) < 2:
        print("usage: python scripts/verify_refund_policy_cooling_v36.py <reservation_id>")
        return 2

    reservation_id = int(sys.argv[1])

    db = SessionLocal()
    try:
        resv = db.get(models.Reservation, reservation_id)
        if not resv:
            print(f"[ERR] reservation not found: {reservation_id}")
            return 2

        if resv.status != models.ReservationStatus.PAID:
            print(f"[ERR] target reservation must be PAID. current={resv.status}")
            return 2

        print("=" * 100)
        print(
            f"[INFO] target reservation_id={resv.id} status={resv.status} qty={resv.qty}\n"
            f"[INFO] DEFAULT_COOLING_DAYS={DEFAULT_COOLING_DAYS}\n"
            f"[INFO] amount_shipping(SSOT)={resv.amount_shipping} amount_total={resv.amount_total}"
        )
        print("=" * 100)
        print()

        stages = ["BEFORE_SHIPPING", "SHIPPED_NOT_DELIVERED", "WITHIN_COOLING", "AFTER_COOLING"]

        failed = False

        for stage in stages:
            _set_stage(db, resv, stage)

            print("#" * 100)
            print(f"# STAGE SET = {stage}")
            print(
                f"# shipped_at={resv.shipped_at} delivered_at={resv.delivered_at} arrival_confirmed_at={resv.arrival_confirmed_at}"
            )
            print("#" * 100)

            for actor in ACTORS:
                for quantity_refund in (1, None):
                    # ✅ return_meta=True로 meta 강제 (호환성은 아래에서 처리)
                    ret = crud.preview_refund_for_paid_reservation(
                        db,
                        reservation_id=resv.id,
                        actor=actor,
                        quantity_refund=quantity_refund,
                        return_meta=True,
                        log_preview=False,   # 검증 스크립트는 로그 과도 생성 방지
                    )

                    # preview가 (ctx, decision) 또는 (ctx, decision, meta) 형태일 수 있으니 방어
                    if isinstance(ret, tuple) and len(ret) == 3:
                        ctx, decision, meta = ret
                        meta_supported = True
                    else:
                        ctx, decision = ret
                        meta = {}
                        meta_supported = False

                    # meta에 정책게이트가 들어있어야 "박제 검증"이 의미가 있음
                    if not meta_supported:
                        print("[ERR] meta not supported. preview must support return_meta=True")
                        return 2

                    # cooling_state / fault_party / trigger
                    cooling_state = getattr(ctx, "cooling_state", None)
                    fault_party = getattr(ctx, "fault_party", None)
                    trigger = getattr(ctx, "trigger", None)

                    amount_goods_refund = int(getattr(ctx, "amount_goods", 0) or 0)
                    amount_shipping_refund = int(getattr(ctx, "amount_shipping", 0) or 0)
                    amount_total_refund = int(getattr(ctx, "amount_total", 0) or 0)

                    gate = _pick_policy_gate(meta)
                    allowed = bool(gate.get("shipping_refund_allowed_by_policy"))
                    auto = int(gate.get("shipping_refund_auto") or 0)
                    final = int(gate.get("shipping_refund_final") or 0)

                    out = {
                        "stage_set": stage,
                        "actor": actor,
                        "quantity_refund": quantity_refund,
                        "cooling_state": getattr(cooling_state, "value", str(cooling_state)),
                        "fault_party": getattr(fault_party, "value", str(fault_party)),
                        "trigger": getattr(trigger, "value", str(trigger)),
                        "amount_goods_refund": amount_goods_refund,
                        "amount_shipping_refund": amount_shipping_refund,
                        "amount_total_refund": amount_total_refund,
                        "decision_use_pg_refund": bool(getattr(decision, "use_pg_refund", False)),
                        "decision_note": getattr(decision, "note", ""),
                        "meta_supported": True,
                        "policy_gate": {
                            "shipping_refund_allowed_by_policy": allowed,
                            "shipping_refund_auto": auto,
                            "shipping_refund_final": final,
                        },
                    }

                    _dump(out)

                    # -------------------------------
                    # ✅ 1) gate expected assert
                    # -------------------------------
                    expected_allowed = EXPECTED_GATE[stage][actor]
                    if allowed != expected_allowed:
                        failed = True
                        print(
                            f"[FAIL] gate mismatch stage={stage} actor={actor} "
                            f"expected={expected_allowed} actual={allowed}"
                        )

                    # -------------------------------
                    # ✅ 2) gate 결과에 따른 final assert
                    # - override를 안 넣는 케이스이므로
                    #   allowed=True이면 final==auto
                    #   allowed=False이면 final==0
                    # -------------------------------
                    if allowed:
                        if final != auto:
                            failed = True
                            print(
                                f"[FAIL] final!=auto stage={stage} actor={actor} "
                                f"auto={auto} final={final}"
                            )
                    else:
                        if final != 0:
                            failed = True
                            print(
                                f"[FAIL] final not zero when disallowed stage={stage} actor={actor} "
                                f"auto={auto} final={final}"
                            )

            print()

        if failed:
            print("[ERR] verify_refund_policy_cooling_v36 FAILED")
            return 2

        print("[OK] verify_refund_policy_cooling_v36 finished.")
        return 0

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())