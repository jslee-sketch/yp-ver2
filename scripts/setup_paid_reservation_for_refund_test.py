# scripts/setup_paid_reservation_for_refund_test.py
import requests, json

BASE_URL = "http://localhost:9000"

def main():
    # 1) 예약 생성 (PENDING)
    payload_resv = {
        "offer_id": 1,
        "buyer_id": 1,
        "qty": 1,
        "deal_id": 1,
        "hold_minutes": 120,  # 넉넉하게 2시간
    }
    r = requests.post(f"{BASE_URL}/v3_6/reservations", json=payload_resv)
    print("create status:", r.status_code)
    r.raise_for_status()
    resv = r.json()
    print(json.dumps(resv, ensure_ascii=False, indent=2))
    rid = resv["id"]
    print("👉 새 예약 id:", rid)

    # 2) 바로 결제 (PAID로 전환)
    payload_pay = {
        "reservation_id": rid,
        "buyer_id": 1,
        "buyer_point_per_qty": 20,  # v3.6 pay에 맞춰서
    }
    r = requests.post(f"{BASE_URL}/v3_6/reservations/pay", json=payload_pay)
    print("pay status:", r.status_code)
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()