# scripts/smoke_refund_preview_v36.py
from __future__ import annotations

import json
import os
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.crud import preview_refund_for_paid_reservation


ACTORS = [
    "buyer_cancel",
    "seller_cancel",
    "admin_force",
    "system_error",
    "dispute_resolve",
]


def run_one(db: Session, reservation_id: int, actor: str):
    # ✅ v3.6 smoke는 meta를 항상 켠다
    out = preview_refund_for_paid_reservation(
        db,
        reservation_id=reservation_id,
        actor=actor,
        quantity_refund=None,
        return_meta=True,     # ✅ 핵심
        log_preview=False,    # smoke는 로그 안 남겨도 됨(원하면 True)
    )

    # 호환: 혹시 코드가 아직 2개 반환이면 여기서 흡수
    if isinstance(out, tuple) and len(out) == 2:
        ctx, decision = out
        meta = {}
        meta_supported = False
    else:
        ctx, decision, meta = out
        meta_supported = True

    payload = {
        "meta_supported": meta_supported,
        "cooling_state": str(getattr(ctx, "cooling_state", None)),
        "fault_party": str(getattr(ctx, "fault_party", None)),
        "trigger": str(getattr(ctx, "trigger", None)),
        "amount_goods_refund": int(getattr(ctx, "amount_goods", 0) or 0),
        "amount_shipping_refund": int(getattr(ctx, "amount_shipping", 0) or 0),
        "amount_total_refund": int(getattr(ctx, "amount_total", 0) or 0),
        "decision_use_pg_refund": bool(getattr(decision, "use_pg_refund", False)),
        "decision_note": str(getattr(decision, "note", "")),
    }

    # meta가 있으면 중요한 것만 같이 보여줌
    if meta_supported:
        payload["meta"] = {
            "shipping_total_db": meta.get("shipping_total_db"),
            "shipping_total_calc": meta.get("shipping_total_calc"),
            "shipping_mismatch": meta.get("shipping_mismatch"),
            "shipping_refund_auto": meta.get("shipping_refund_auto"),
            "shipping_refund_final": meta.get("shipping_refund_final"),
            "shipping_refund_allowed_by_policy": meta.get("shipping_refund_allowed_by_policy"),
            "shipping_refund_override_applied": meta.get("shipping_refund_override_applied"),
        }

    print("=" * 80)
    print(f"reservation_id={reservation_id} actor={actor}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main():
    # ✅ 예약 ID는 환경변수로 바꿀 수 있게
    reservation_id = int(os.environ.get("RESERVATION_ID", "6"))

    db = SessionLocal()
    try:
        for actor in ACTORS:
            run_one(db, reservation_id, actor)
    finally:
        db.close()

    print("\n[OK] smoke test finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())