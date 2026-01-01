import sys
import json
import requests

BASE_URL = "http://127.0.0.1:9000"

# 사용법:
#   python scripts/test_reservation_pay_and_notifications.py  <reservation_id> <buyer_id>
# 인자 안 주면 둘 다 1로 테스트
RESERVATION_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 1
BUYER_ID = int(sys.argv[2]) if len(sys.argv) > 2 else 1

# crud 기본값이랑 맞춰둠 (원하면 바꿔도 됨)
BUYER_POINT_PER_QTY = 20


def pretty_print(resp, title: str):
    print("\n" + "=" * 60)
    print(f"▶ {title}")
    print("=" * 60)
    print("status:", resp.status_code)
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(resp.text)


def main():
    # 1) 예약 결제 호출
    payload = {
        "reservation_id": RESERVATION_ID,
        "buyer_id": BUYER_ID,
        "buyer_point_per_qty": BUYER_POINT_PER_QTY,
    }

    url_pay = f"{BASE_URL}/v3_6/reservations/pay"
    resp_pay = requests.post(url_pay, json=payload)
    pretty_print(resp_pay, f"POST {url_pay}")

    if resp_pay.status_code != 200:
        print("❌ 결제 실패 – 위 응답을 먼저 확인해봐요.")
        return

    paid = resp_pay.json()
    deal_id = paid.get("deal_id")
    offer_id = paid.get("offer_id")
    buyer_id = paid.get("buyer_id")

    # 2) buyer 알림 목록 확인
    url_notif_buyer = f"{BASE_URL}/notifications"
    resp_notif_buyer = requests.get(url_notif_buyer, params={"user_id": buyer_id})
    pretty_print(resp_notif_buyer, f"GET {url_notif_buyer}?user_id={buyer_id}  (buyer 알림)")

    # 3) seller_id 가져오기 위한 오퍼 조회
    seller_id = None
    if offer_id:
        url_offer = f"{BASE_URL}/offers/{offer_id}"
        resp_offer = requests.get(url_offer)
        pretty_print(resp_offer, f"GET {url_offer} (offer 조회)")

        if resp_offer.status_code == 200:
            seller_id = resp_offer.json().get("seller_id")

    # 4) seller 알림 목록 확인
    if seller_id:
        url_notif_seller = f"{BASE_URL}/notifications"
        resp_notif_seller = requests.get(url_notif_seller, params={"user_id": seller_id})
        pretty_print(
            resp_notif_seller,
            f"GET {url_notif_seller}?user_id={seller_id}  (seller 알림)",
        )
    else:
        print("\n⚠️ seller_id를 찾지 못해서 seller 알림 테스트는 건너뛰었어요.")


if __name__ == "__main__":
    main()