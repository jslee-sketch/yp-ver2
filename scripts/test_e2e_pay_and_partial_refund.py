# scripts/test_e2e_pay_and_partial_refund.py

import os
import sys
import json
from datetime import datetime

import requests


BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:9000/v3_6")

DEAL_ID = int(os.getenv("DEAL_ID", "1"))
OFFER_ID = int(os.getenv("OFFER_ID", "1"))
BUYER_ID = int(os.getenv("BUYER_ID", "1"))
QTY = int(os.getenv("QTY", "3"))
QTY_REFUND_EACH = int(os.getenv("QTY_REFUND_EACH", "1"))  # 부분환불할 때마다 취소할 수량

print(f"✅ Using BASE_URL: {BASE_URL}")
print(f"✅ Using DEAL_ID: {DEAL_ID}, OFFER_ID: {OFFER_ID}, BUYER_ID: {BUYER_ID}")
print(f"✅ Using QTY: {QTY}, QTY_REFUND_EACH: {QTY_REFUND_EACH}")
print()


def pretty(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def step(title: str):
    print()
    print("=" * 10, title, "=" * 10)


def create_reservation():
    step("0) POST /reservations  (예약 생성)")
    url = f"{BASE_URL}/reservations"
    body = {
        "deal_id": DEAL_ID,
        "offer_id": OFFER_ID,
        "buyer_id": BUYER_ID,
        "qty": QTY,
        "hold_minutes": 30,
    }
    print("POST", url)
    print("body:", body)

    r = requests.post(url, json=body)
    print("status:", r.status_code)
    try:
        data = r.json()
    except Exception:
        print("raw text:", r.text)
        sys.exit(1)

    pretty(data)

    if r.status_code != 201:
        print("❌ 예약 생성 실패. 위 응답 확인 필요.")
        sys.exit(1)

    resv_id = data["id"]
    print(f"✅ Created reservation_id: {resv_id}")
    return resv_id


def pay_reservation(reservation_id: int):
    step("1) POST /pay  (예약 결제 v3.5 + PG 스텁)")
    url = f"{BASE_URL}/pay"
    body = {
        "reservation_id": reservation_id,
        "buyer_id": BUYER_ID,
    }
    print("POST", url)
    print("body:", body)

    r = requests.post(url, json=body)
    print("status:", r.status_code)
    try:
        data = r.json()
    except Exception:
        print("raw text:", r.text)
        sys.exit(1)

    pretty(data)

    if r.status_code != 200:
        print("❌ 결제 실패. 위 응답 확인 필요.")
        sys.exit(1)

    print(f"👉 after pay: status={data['status']}, paid_at={data.get('paid_at')}")
    return data


def get_reservation(reservation_id: int, title: str):
    step(title)
    url = f"{BASE_URL}/reservations/by-id/{reservation_id}"
    print("GET", url)
    r = requests.get(url)
    print("status:", r.status_code)
    data = r.json()
    pretty(data)
    return data


def get_refund_summary(reservation_id: int):
    step("refund/summary 조회")
    url = f"{BASE_URL}/refund/summary/{reservation_id}"
    print("GET", url)
    r = requests.get(url)
    print("status:", r.status_code)
    data = r.json()
    pretty(data)

    print(
        f"👉 status={data['status']}, "
        f"qty={data['qty']}, refunded_qty={data['refunded_qty']}, "
        f"refundable_qty={data['refundable_qty']}, "
        f"refundable_amount_max={data['refundable_amount_max']}"
    )
    return data


def partial_refund_once(reservation_id: int, qty_refund: int):
    step(f"부분환불 1회: qty_refund={qty_refund}")

    # 1) preview
    url_preview = f"{BASE_URL}/reservations/refund/preview"
    body = {
        "reservation_id": reservation_id,
        "quantity_refund": qty_refund,   # 🔴 우리 백엔드에서 쓰는 필드 이름 기준
        "actor": "buyer_cancel",
    }
    print("POST", url_preview)
    print("body:", body)
    r = requests.post(url_preview, json=body)
    print("status:", r.status_code)
    data_preview = r.json()
    pretty(data_preview)

    if r.status_code != 200:
        print("⚠️ preview 단계에서 실패. 더 이상 진행하지 않음.")
        return False

    ctx = data_preview.get("context", {})
    print(
        "👉 Preview: total_qty=%s, qty_refund=%s, amount_total=%s"
        % (
            ctx.get("quantity_total"),
            ctx.get("quantity_refund"),
            ctx.get("amount_total"),
        )
    )

    # 2) 실제 refund
    url_refund = f"{BASE_URL}/reservations/refund"
    print("POST", url_refund)
    r2 = requests.post(url_refund, json=body)
    print("status:", r2.status_code)
    data_refund = r2.json()
    pretty(data_refund)

    if r2.status_code != 200:
        print("⚠️ refund 단계에서 실패. 더 이상 진행하지 않음.")
        return False

    print(
        "👉 After partial refund: status=%s, refunded_qty=%s, refunded_amount_total=%s"
        % (
            data_refund["status"],
            data_refund.get("refunded_qty"),
            data_refund.get("refunded_amount_total"),
        )
    )
    return True


def main():
    start = datetime.now()
    print(f"🚀 E2E: create → pay(PG stub) → partial refund(s) 시작 ({start})")
    print()

    # 0) 예약 생성
    resv_id = create_reservation()

    # 1) 결제 (PG 스텁 포함)
    pay_reservation(resv_id)

    # 2) 결제 후 상태 확인
    get_reservation(resv_id, "2) GET /reservations/by-id (after pay)")
    get_refund_summary(resv_id)

    # 3) 부분환불을 여러 번 수행 (refundable_qty가 0 될 때까지)
    while True:
        summary = get_refund_summary(resv_id)
        refundable_qty = summary.get("refundable_qty", 0)
        if refundable_qty <= 0:
            print("✅ 더 이상 환불 가능한 수량이 없습니다. 루프 종료.")
            break

        qty_refund = min(QTY_REFUND_EACH, refundable_qty)
        ok = partial_refund_once(resv_id, qty_refund)
        if not ok:
            break

        # 환불 후 상태 확인
        get_reservation(resv_id, "GET /reservations/by-id (after partial refund)")
        # 루프 다시 돌면서 summary 확인

    final = get_reservation(resv_id, "최종 상태 확인")
    print()
    print("🎉 E2E 테스트 종료")
    print(
        f"   - reservation_id: {resv_id}\n"
        f"   - final status:   {final['status']}\n"
        f"   - refunded_qty:   {final.get('refunded_qty')}\n"
        f"   - refunded_total: {final.get('refunded_amount_total')}"
    )
    print(f"   (완료 시각: {datetime.now()})")


if __name__ == "__main__":
    main()