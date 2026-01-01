# scripts/test_reservation_full_flow.py
"""
예약 생성 + 결제 + 알림(buyer/seller)까지 한 번에 점검하는 스크립트.

사용법 (기본값: deal_id=1, offer_id=1, buyer_id=1, qty=1):

    (venv) python scripts/test_reservation_full_flow.py
    (venv) python scripts/test_reservation_full_flow.py  1  1  1  2
                                                   #  deal offer buyer qty
"""

import sys
import json
import requests

BASE_URL = "http://127.0.0.1:9000"


def pretty(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def print_section(title: str):
    print("\n" + "=" * 70)
    print("▶ " + title)
    print("=" * 70)


def main():
    # --- 인자 처리 ---
    deal_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    offer_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    buyer_id = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    qty = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    # ─────────────────────────────────────────────
    # 1) 예약 생성: POST /v3_6/reservations
    # ─────────────────────────────────────────────
    print_section(
        f"1) POST /v3_6/reservations  (deal_id={deal_id}, offer_id={offer_id}, buyer_id={buyer_id}, qty={qty})"
    )

    # ✅ ReservationCreate 스키마에 맞춰 deal_id 포함
    create_payload = {
        "deal_id": deal_id,
        "offer_id": offer_id,
        "buyer_id": buyer_id,
        "qty": qty,
    }

    url_create = f"{BASE_URL}/v3_6/reservations"
    resp_create = requests.post(url_create, json=create_payload)
    print("status:", resp_create.status_code)

    try:
        data_create = resp_create.json()
        pretty(data_create)
    except Exception:
        print(resp_create.text)
        print("❌ JSON 파싱 실패. 위 응답 텍스트를 확인해 주세요.")
        return

    if resp_create.status_code >= 300:
        print("❌ 예약 생성 실패. 위 응답 내용을 먼저 확인해 주세요.")
        return

    reservation_id = data_create.get("id") or data_create.get("reservation_id")
    if not reservation_id:
        print("❌ 응답에서 reservation id를 찾지 못했습니다. 'id' 필드명을 한 번 확인해 주세요.")
        return

    print(f"\n✅ 생성된 예약 ID: {reservation_id}")

    # ─────────────────────────────────────────────
    # 2) 예약 결제: POST /v3_6/reservations/pay
    # ─────────────────────────────────────────────
    print_section("2) POST /v3_6/reservations/pay  (방금 만든 예약 결제)")

    pay_payload = {
        "reservation_id": reservation_id,
        "buyer_id": buyer_id,
        # 프로젝트 정책값과 맞춰서 필요시 수정
        "buyer_point_per_qty": 20,
    }

    url_pay = f"{BASE_URL}/v3_6/reservations/pay"
    resp_pay = requests.post(url_pay, json=pay_payload)
    print("status:", resp_pay.status_code)

    try:
        data_pay = resp_pay.json()
        pretty(data_pay)
    except Exception:
        print(resp_pay.text)
        print("❌ JSON 파싱 실패. 위 응답 텍스트를 확인해 주세요.")
        return

    if resp_pay.status_code >= 300:
        print("❌ 결제 실패. 위 응답 내용을 먼저 확인해 주세요.")
        return

    deal_id_paid = data_pay.get("deal_id") or deal_id
    offer_id_paid = data_pay.get("offer_id") or offer_id
    print(
        f"\n✅ 결제 완료된 예약 ID: {data_pay.get('id')} "
        f"(deal_id={deal_id_paid}, offer_id={offer_id_paid})"
    )

# ─────────────────────────────────────────────
    # 3) 오퍼 조회해서 seller_id 가져오기 (있으면)
    # ─────────────────────────────────────────────
    print_section("3) GET /v3_6/offers/{offer_id}  (seller_id 확인)")

    url_offer_v36 = f"{BASE_URL}/v3_6/offers/{offer_id_paid}"
    resp_offer = requests.get(url_offer_v36)
    print("status:", resp_offer.status_code)

    seller_id = None
    if resp_offer.status_code < 300:
        try:
            data_offer = resp_offer.json()
            pretty(data_offer)
            seller_id = data_offer.get("seller_id")
            print(f"\n✅ seller_id: {seller_id}")
        except Exception:
            print(resp_offer.text)
            print("⚠️ v3_6 오퍼 JSON 파싱 실패. 그래도 다음 단계 진행.")
    else:
        print(resp_offer.text)
        print("⚠️ /v3_6/offers/{id} 라우트가 없거나 404 입니다.")

        # 🔁 플랜 B: 구버전 /offers/{id} 도 한 번 시도
        url_offer_legacy = f"{BASE_URL}/offers/{offer_id_paid}"
        resp_offer_legacy = requests.get(url_offer_legacy)
        print("\n다시 시도: GET /offers/{offer_id}")
        print("status:", resp_offer_legacy.status_code)
        if resp_offer_legacy.status_code < 300:
            try:
                data_offer2 = resp_offer_legacy.json()
                pretty(data_offer2)
                seller_id = data_offer2.get("seller_id")
                print(f"\n✅ seller_id (legacy): {seller_id}")
            except Exception:
                print(resp_offer_legacy.text)
                print("⚠️ 구버전 오퍼 JSON 파싱 실패.")
        else:
            print(resp_offer_legacy.text)
            print("⚠️ 구버전 /offers/{id} 도 404 입니다.")

    # 👉 DEV 환경용 강제 fallback (seller=1 가정)
    if not seller_id:
        print("\n⚠️ seller_id 를 API에서 못 찾았으므로, DEV 용으로 seller_id=1 로 가정합니다.")
        seller_id = 1

    # ─────────────────────────────────────────────
    # 4) Buyer 알림 조회
    # ─────────────────────────────────────────────
    print_section(f"4) GET /notifications?user_id={buyer_id}  (buyer 알림)")

    url_notif = f"{BASE_URL}/notifications"
    resp_notif_buyer = requests.get(
        url_notif,
        params={"user_id": buyer_id, "only_unread": False},
    )
    print("status:", resp_notif_buyer.status_code)
    ...
    # (이 부분은 기존 코드 그대로 두면 됩니다.)

    # ─────────────────────────────────────────────
    # 5) Seller 알림 조회 (fallback seller_id 사용)
    # ─────────────────────────────────────────────
    print_section(f"5) GET /notifications?user_id={seller_id}  (seller 알림)")

    resp_notif_seller = requests.get(
        url_notif,
        params={"user_id": seller_id, "only_unread": False},
    )
    print("status:", resp_notif_seller.status_code)

    try:
        notifs_seller = resp_notif_seller.json()
    except Exception:
        print(resp_notif_seller.text)
        print("⚠️ seller 알림 JSON 파싱 실패.")
        notifs_seller = []

    print("\n📨 Seller 알림 (최근 5개):")
    pretty(notifs_seller[:5])

    seller_paid = [
        n
        for n in notifs_seller
        if n.get("type") == "reservation_paid_on_offer"
    ]
    if seller_paid:
        print("\n✅ Seller 쪽 'reservation_paid_on_offer' 알림 감지:")
        pretty(seller_paid[:3])
    else:
        print("\n⚠️ Seller 쪽 'reservation_paid_on_offer' 알림을 찾지 못했습니다.")

    print("\n🎉 시나리오 완료!")


if __name__ == "__main__":
    main()