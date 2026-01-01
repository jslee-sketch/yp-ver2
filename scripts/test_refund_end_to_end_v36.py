# scripts/test_refund_end_to_end_v36.py

import requests
from pprint import pprint

BASE_URL = "http://localhost:9000"


def print_sep(title: str):
    print("\n" + "=" * 80)
    print(f"▶ {title}")
    print("=" * 80)


def main():
    # 0) 헬스 체크
    print_sep("0) 서버 헬스 체크")
    r = requests.get(f"{BASE_URL}/health")
    print("status:", r.status_code)
    r.raise_for_status()

    # 1) v3.6 예약 생성 (PENDING)
    print_sep("1) POST /v3_6/reservations  예약 생성 (PENDING)")
    payload_resv = {
        "deal_id": 1,
        "offer_id": 1,
        "buyer_id": 1,
        "qty": 1,
        "hold_minutes": 120,
    }
    r = requests.post(f"{BASE_URL}/v3_6/reservations", json=payload_resv)
    print("status:", r.status_code)
    r.raise_for_status()
    resv = r.json()
    pprint(resv)
    rid = resv["id"]
    print(f"👉 새 예약 id: {rid}")

    # 2) v3.6 결제 (PENDING → PAID)
    print_sep("2) POST /v3_6/reservations/pay  결제")
    payload_pay = {
        "reservation_id": rid,
        "buyer_id": 1,
        "buyer_point_per_qty": 20,  # v3.6 pay_reservation 시그니처 맞춤
    }
    r = requests.post(f"{BASE_URL}/v3_6/reservations/pay", json=payload_pay)
    print("status:", r.status_code)
    r.raise_for_status()
    paid = r.json()
    pprint(paid)

    # 3) v3.6 환불 (PAID → CANCELLED, actor=buyer_cancel)
    print_sep("3) POST /v3_6/reservations/refund  환불 요청 (buyer_cancel)")
    payload_refund = {
        "reservation_id": rid,
        "actor": "buyer_cancel",
    }
    r = requests.post(f"{BASE_URL}/v3_6/reservations/refund", json=payload_refund)
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)

    # 4) 같은 예약에 대해 다시 환불 시도 (이중 환불 방지 확인)
    print_sep("4) POST /v3_6/reservations/refund  두 번째 환불 시도 (409 기대)")
    r = requests.post(f"{BASE_URL}/v3_6/reservations/refund", json=payload_refund)
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)


if __name__ == "__main__":
    main()