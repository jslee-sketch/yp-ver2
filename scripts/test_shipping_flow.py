# scripts/test_shipping_flow.py
import requests
import json

BASE_URL = "http://127.0.0.1:9000/v3_6"
RESERVATION_ID = 1      # 테스트할 예약 ID
SELLER_ID = 1           # 테스트 셀러
BUYER_ID = 1            # 테스트 바이어

def pretty(res):
    print("status:", res.status_code)
    try:
        print(json.dumps(res.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(res.text)
    print()

def main():
    print("✅ Using BASE_URL:", BASE_URL)
    print("✅ Using RESERVATION_ID:", RESERVATION_ID)
    print()

    # 0) 현재 예약 상태 확인
    print("====== 0) GET /reservations/by-id/{id} ======")
    r = requests.get(f"{BASE_URL}/reservations/by-id/{RESERVATION_ID}")
    pretty(r)

    # 1) 셀러 발송 완료 시도
    print("====== 1) POST /reservations/{id}/ship ======")
    r = requests.post(
        f"{BASE_URL}/reservations/{RESERVATION_ID}/ship",
        json={"seller_id": SELLER_ID},
    )
    pretty(r)

    # 2) 바이어 도착 확인 시도
    print("====== 2) POST /reservations/{id}/arrival-confirm ======")
    r = requests.post(
        f"{BASE_URL}/reservations/{RESERVATION_ID}/arrival-confirm",
        json={"buyer_id": BUYER_ID},
    )
    pretty(r)

if __name__ == "__main__":
    main()