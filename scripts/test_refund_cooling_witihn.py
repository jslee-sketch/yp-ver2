# scripts/test_refund_cooling_within.py
import requests, json

BASE_URL = "http://localhost:9000"

def main():
    rid = 61  # 👉 방금 새로 만든 PAID 예약 id로 교체

    payload = {
        "reservation_id": rid,
        "actor": "buyer_cancel",  # 바이어 귀책 시나리오
    }
    r = requests.post(f"{BASE_URL}/reservations/cancel", json=payload)
    print("status:", r.status_code)
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    except:
        print(r.text)

if __name__ == "__main__":
    main()