# scripts/test_notifications_and_actuator_flow.py
import requests
import json
from pprint import pprint

BASE_URL = "http://127.0.0.1:9000"

# 💡 필요한 ID들 (현재 DB 상황에 맞게 조정 가능)
DEAL_ID = 1
OFFER_ID = 1
BUYER_ID = 1
SELLER_USER_ID = 1      # seller_id와 동일하게 쓰는 구조
ACTUATOR_USER_ID = 1    # seller에 연결된 actuator_id (seller.actuator_id == 1 이라고 가정)


def print_title(title: str):
    print("\n" + "=" * 70)
    print(f"▶ {title}")
    print("=" * 70)


def jprint(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main():
    resv_id = None
    paid = None

    # -------------------------------------------------------------
    # 1) 예약 생성: POST /v3_6/reservations
    # -------------------------------------------------------------
    print_title(
        f"1) POST /v3_6/reservations  (deal_id={DEAL_ID}, offer_id={OFFER_ID}, "
        f"buyer_id={BUYER_ID}, qty=1)"
    )
    payload_resv = {
        "deal_id": DEAL_ID,
        "offer_id": OFFER_ID,
        "buyer_id": BUYER_ID,
        "qty": 1,
    }
    r = requests.post(f"{BASE_URL}/v3_6/reservations", json=payload_resv)
    print("status:", r.status_code)

    # 응답 출력
    try:
        data = r.json()
        jprint(data)
    except Exception:
        print(r.text)
        data = None

    # ✅ 케이스 A: 새 예약 성공
    if r.status_code == 201 and data:
        resv_id = data["id"]
        print(f"\n✅ 생성된 예약 ID: {resv_id}")
    # ✅ 케이스 B: 이미 매진 → 새 예약 불가 (remain=0)
    elif r.status_code == 409 and data and data.get("detail") == "not enough capacity (remain=0)":
        print("\n⚠️ 이미 이 오퍼는 남은 수량이 0입니다. (매진 상태)")
        print("   → 새 예약/결제 단계는 건너뛰고, 기존 상태 기준으로")
        print("     오퍼 확정 및 알림 플로우만 확인합니다.")
    else:
        print("❌ 예약 생성 실패. 위 응답 내용을 먼저 확인해 주세요.")
        return

    # -------------------------------------------------------------
    # 2) (선택) 예약 결제: POST /v3_6/reservations/pay
    #    - 새 예약을 만든 경우에만 수행
    # -------------------------------------------------------------
    if resv_id is not None:
        print_title(
            f"2) POST /v3_6/reservations/pay  (reservation_id={resv_id}, buyer_id={BUYER_ID})"
        )
        payload_pay = {
            "reservation_id": resv_id,
            "buyer_id": BUYER_ID,
            "buyer_point_per_qty": 20,
        }
        r = requests.post(f"{BASE_URL}/v3_6/reservations/pay", json=payload_pay)
        print("status:", r.status_code)
        try:
            paid = r.json()
            jprint(paid)
        except Exception:
            print(r.text)
            return

        if r.status_code != 200:
            print("❌ 결제 실패. 위 응답 내용을 먼저 확인해 주세요.")
            return

        print(
            f"\n✅ 결제 완료된 예약 ID: {paid['id']} "
            f"(deal_id={paid['deal_id']}, offer_id={paid['offer_id']})"
        )

    # -------------------------------------------------------------
    # 2-1) 현재 오퍼 상태 확인
    # -------------------------------------------------------------
    print_title(f"2-1) GET /offers/{OFFER_ID}  (오퍼 판매 현황)")
    r = requests.get(f"{BASE_URL}/offers/{OFFER_ID}")
    print("status:", r.status_code)
    try:
        offer_data = r.json()
        jprint(offer_data)
    except Exception:
        print(r.text)
        return

    # -------------------------------------------------------------
    # 3) Buyer 알림 확인 (예약이 새로 생겼든 아니든, 최근 상태를 봄)
    # -------------------------------------------------------------
    print_title(f"3) GET /notifications?user_id={BUYER_ID}  (buyer 알림)")
    r = requests.get(f"{BASE_URL}/notifications", params={"user_id": BUYER_ID})
    print("status:", r.status_code)
    try:
        notifs_buyer = r.json()
    except Exception:
        print(r.text)
        return

    print("\n📨 Buyer 알림 (최근 5개):")
    jprint(notifs_buyer[:5])

    buyer_paid = [
        n
        for n in notifs_buyer
        if n.get("type") == "reservation_paid" and n.get("meta_json")
    ]
    print("\n✅ Buyer 'reservation_paid' 알림:")
    jprint(buyer_paid)

    # -------------------------------------------------------------
    # 4) Seller 알림 확인 (reservation_paid_on_offer)
    # -------------------------------------------------------------
    print_title(f"4) GET /notifications?user_id={SELLER_USER_ID}  (seller 알림)")
    r = requests.get(f"{BASE_URL}/notifications", params={"user_id": SELLER_USER_ID})
    print("status:", r.status_code)
    try:
        notifs_seller = r.json()
    except Exception:
        print(r.text)
        return

    print("\n📨 Seller 알림 (최근 5개):")
    jprint(notifs_seller[:5])

    seller_paid_on_offer = [
        n for n in notifs_seller if n.get("type") == "reservation_paid_on_offer"
    ]
    print("\n✅ Seller 'reservation_paid_on_offer' 알림:")
    jprint(seller_paid_on_offer)

    # -------------------------------------------------------------
    # 5) 오퍼 확정: POST /offers/{offer_id}/confirm
    #    - 전량 판매 상태면 200 OK
    # -------------------------------------------------------------
    print_title(f"5) POST /offers/{OFFER_ID}/confirm  (오퍼 확정 시도)")
    r = requests.post(f"{BASE_URL}/offers/{OFFER_ID}/confirm")
    print("status:", r.status_code)
    try:
        confirm_res = r.json()
        jprint(confirm_res)
    except Exception:
        print(r.text)
        confirm_res = None

    if r.status_code == 200:
        print("\n✅ 오퍼 확정 성공")
    else:
        print("\n⚠️ 오퍼 확정 실패 또는 조건 미충족(전량 판매 아님 등).")
        print("   - detail을 확인해 주세요.")
        # 그래도 아래에서 알림 상태는 참고할 수 있으니 바로 return 하진 않음

    # -------------------------------------------------------------
    # 6) Seller 알림 재확인: offer_confirmed
    # -------------------------------------------------------------
    print_title(
        f"6) GET /notifications?user_id={SELLER_USER_ID}  (seller 알림 재확인)"
    )
    r = requests.get(f"{BASE_URL}/notifications", params={"user_id": SELLER_USER_ID})
    print("status:", r.status_code)
    try:
        notifs_seller2 = r.json()
    except Exception:
        print(r.text)
        return

    print("\n📨 Seller 알림 (최근 10개):")
    jprint(notifs_seller2[:10])

    seller_offer_confirmed = [
        n for n in notifs_seller2 if n.get("type") == "offer_confirmed"
    ]
    print("\n✅ Seller 'offer_confirmed' 알림:")
    jprint(seller_offer_confirmed)

    # -------------------------------------------------------------
    # 7) Actuator 알림: actuator_seller_offer_confirmed
    # -------------------------------------------------------------
    print_title(
        f"7) GET /notifications?user_id={ACTUATOR_USER_ID}  (actuator 알림)"
    )
    r = requests.get(f"{BASE_URL}/notifications", params={"user_id": ACTUATOR_USER_ID})
    print("status:", r.status_code)
    try:
        notifs_act = r.json()
    except Exception:
        print(r.text)
        return

    print("\n📨 Actuator 알림 (최근 10개):")
    jprint(notifs_act[:10])

    act_offer_confirmed = [
        n for n in notifs_act
        if n.get("type") == "actuator_seller_offer_confirmed"
    ]
    print("\n✅ Actuator 'actuator_seller_offer_confirmed' 알림:")
    jprint(act_offer_confirmed)

    print("\n🎉 시나리오 완료!")


if __name__ == "__main__":
    main()