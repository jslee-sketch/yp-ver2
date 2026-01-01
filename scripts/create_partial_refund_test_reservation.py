# scripts/create_partial_refund_test_reservation.py
import requests
import json

BASE_URL = "http://127.0.0.1:9000/v3_6"

BUYER_ID = 1
DEAL_ID = 1
OFFER_ID = 1

def main():
    # 1) 예약 생성 (qty=3)
    payload_resv = {
        "deal_id": 1,
        "offer_id": 1,
        "buyer_id": 1,
        "qty": 3,
        "hold_minutes": 30,
    }
    r = requests.post(f"{BASE_URL}/reservations", json=payload_resv)
    print("CREATE RESV status:", r.status_code)
    print(r.text)
    r.raise_for_status()
    resv = r.json()
    resv_id = resv["id"]
    print(f"✅ Created reservation_id for partial refund test: {resv_id}")

    # 2) 결제 (PAID로 만들기)
    payload_pay = {
        "reservation_id": resv_id,
        "buyer_id": BUYER_ID,
        "buyer_point_per_qty": 1,
    }
    r2 = requests.post(f"{BASE_URL}/reservations/pay", json=payload_pay)
    print("PAY RESV status:", r2.status_code)
    print(r2.text)
    r2.raise_for_status()
    paid_resv = r2.json()
    print("✅ Reservation is PAID now.")
    print(json.dumps(paid_resv, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()