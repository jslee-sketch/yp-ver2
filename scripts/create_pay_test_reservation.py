# scripts/create_pay_test_reservation.py

import os
import json
import requests

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:9000/v3_6")

DEAL_ID = int(os.getenv("DEAL_ID", "1"))
OFFER_ID = int(os.getenv("OFFER_ID", "1"))
BUYER_ID = int(os.getenv("BUYER_ID", "1"))
QTY = int(os.getenv("QTY", "3"))
HOLD_MINUTES = int(os.getenv("HOLD_MINUTES", "30"))


def main() -> None:
    print(f"✅ Using BASE_URL: {BASE_URL}")
    print(f"✅ Using DEAL_ID: {DEAL_ID}, OFFER_ID: {OFFER_ID}, BUYER_ID: {BUYER_ID}, QTY: {QTY}")

    url = f"{BASE_URL}/reservations"
    payload = {
        "deal_id": DEAL_ID,
        "offer_id": OFFER_ID,
        "buyer_id": BUYER_ID,
        "qty": QTY,
        "hold_minutes": HOLD_MINUTES,
    }

    resp = requests.post(url, json=payload)
    print("CREATE RESV status:", resp.status_code)

    try:
        data = resp.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        print(resp.text)
        return

    if resp.status_code // 100 != 2:
        print("❌ 예약 생성 실패")
        return

    resv_id = data.get("id")
    print(f"✅ Created reservation_id for pay test: {resv_id}")


if __name__ == "__main__":
    main()