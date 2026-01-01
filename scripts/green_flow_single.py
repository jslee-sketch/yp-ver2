# scripts/green_flow_single.py

import requests
import json
from pprint import pprint

BASE_URL = "http://127.0.0.1:9000"

# 테스트에 사용할 ID들 (필요하면 여기만 수정해서 쓰면 됨)
BUYER_ID = 1
SELLER_ID = 1
DEAL_ID = 1
OFFER_ID = 1


def print_step(title):
    print("\n" + "=" * 80)
    print("▶", title)
    print("=" * 80)


def main():
    # 0) 서버 살아있는지 체크
    print_step("0) 서버 헬스 체크")
    r = requests.get(BASE_URL + "/")
    print("status:", r.status_code)

    # 1) 오퍼 취소정책 등록 (A3: 발송 후 3일 이내 취소 가능)
    print_step("1) POST /offers/{offer_id}/policy  취소정책 등록")
    policy_body = {
        "cancel_rule": "A3",
        "cancel_within_days": 3,
        "extra_text": "배송완료 후 3일 이내 단순변심 취소 가능, 왕복배송비는 구매자 부담.",
    }
    r = requests.post(
        f"{BASE_URL}/offers/{OFFER_ID}/policy",
        json=policy_body,
    )
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)

    # 2) 예약 생성
    print_step("2) POST /reservations  예약 생성 (PENDING)")
    reservation_body = {
        "deal_id": DEAL_ID,
        "offer_id": OFFER_ID,
        "buyer_id": BUYER_ID,
        "qty": 1,
        "hold_minutes": 60,  # 대충 60분
    }
    r = requests.post(
        f"{BASE_URL}/reservations",
        json=reservation_body,
    )
    print("status:", r.status_code)
    resv = r.json()
    pprint(resv)

    reservation_id = resv["id"]
    print(f"=> 생성된 reservation_id = {reservation_id}")

    # 3) 예약 결제
    print_step("3) POST /reservations/pay  예약 결제 (PENDING → PAID)")
    pay_body = {
        "reservation_id": reservation_id,
        "buyer_id": BUYER_ID,
    }
    r = requests.post(
        f"{BASE_URL}/reservations/pay",
        json=pay_body,
    )
    print("status:", r.status_code)
    paid_resv = r.json()
    pprint(paid_resv)

    # 4) Seller 발송 처리
    print_step("4) POST /reservations/{id}/mark_shipped  발송 처리 (shipped_at 세팅)")
    ship_body = {
        "seller_id": SELLER_ID,
        # 추후 tracking_number 등 확장 가능
    }
    r = requests.post(
        f"{BASE_URL}/reservations/{reservation_id}/mark_shipped",
        json=ship_body,
    )
    print("status:", r.status_code)
    shipped_resv = r.json()
    pprint(shipped_resv)

    # 5) Buyer 수령확인
    print_step("5) POST /reservations/{id}/arrival_confirm  수령확인 (DELIVERED + 정산 생성)")
    confirm_body = {
        "buyer_id": BUYER_ID,
    }
    r = requests.post(
        f"{BASE_URL}/reservations/{reservation_id}/arrival_confirm",
        json=confirm_body,
    )
    print("status:", r.status_code)
    confirmed_resv = r.json()
    pprint(confirmed_resv)

    # 6) 최종 Reservation 상태 확인
    print_step("6) GET /reservations/{id}  최종 상태 확인 (phase, shipped_at, delivered_at 등)")
    r = requests.get(f"{BASE_URL}/reservations/{reservation_id}")
    print("status:", r.status_code)
    final_resv = r.json()
    pprint(final_resv)

    # 7) reservation_settlements 테이블 확인 (옵션)
    print("================================================================================")
    print("▶ 7) reservation_settlements 에 row 생겼는지 확인 (reservation_id 기준)")
    print("================================================================================")

    r = requests.get(f"{BASE_URL}/admin/settlements/by_reservation/{reservation_id}")
    print("status:", r.status_code)
    print(r.json())

    
    
    print_step("✅ GREEN FLOW SINGLE 시나리오 완료")
    
    
if __name__ == "__main__":
    main()