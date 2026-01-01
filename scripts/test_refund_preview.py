# scripts/test_refund_preview.py
import requests
import json

BASE = "http://localhost:9000"

# 환불 정책을 보고 싶은 예약 id (지금은 61 같은 거)
RESERVATION_ID = 61

def main():
    for actor in ["buyer_cancel", "seller_cancel", "admin_force"]:
        print("\n===============================")
        print(f"▶ actor = {actor}")
        print("===============================")

        params = {"actor": actor}
        url = f"{BASE}/reservations/refund/preview/{RESERVATION_ID}"
        r = requests.get(url, params=params)

        print("status:", r.status_code)
        try:
            data = r.json()
            print(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception:
            print(r.text)

if __name__ == "__main__":
    main()