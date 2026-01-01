import os
import requests
from pprint import pprint

# ---------------------------------------------------------
# 설정
# ---------------------------------------------------------
PORT = os.getenv("YP_PORT", "9000")
BASE_URL = f"http://127.0.0.1:{PORT}"


def print_section(title: str):
    print("\n" + "=" * 80)
    print(f"▶ {title}")
    print("=" * 80)


def main():
    offer_id = 1
    deal_id = 1
    buyer_id = 1
    seller_id = 1

    # ------------------------------------------------------------------
    # 0) 헬스 체크
    # ------------------------------------------------------------------
    print_section("0) 서버 헬스 체크")
    r = requests.get(f"{BASE_URL}/health")
    print("status:", r.status_code)
    if r.status_code != 200:
        print("❌ 서버 헬스 체크 실패, 테스트 중단")
        return

    # ------------------------------------------------------------------
    # 1) A2 정책 세팅: 발송 후 취소 불가
    # ------------------------------------------------------------------
    print_section("1) POST /offers/{offer_id}/policy  → A2(발송 후 취소 불가)로 설정")
    payload_policy = {
        "cancel_rule": "A2",
        "cancel_within_days": None,
        "extra_text": "발송 후에는 단순변심 취소 불가",
    }
    r = requests.post(f"{BASE_URL}/offers/{offer_id}/policy", json=payload_policy)
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)

    if r.status_code not in (200, 201):
        print("❌ 정책 설정 실패, 이후 시나리오 진행 불가")
        return

    # ------------------------------------------------------------------
    # 2) 예약 생성 (PENDING)
    # ------------------------------------------------------------------
    print_section("2) POST /reservations  예약 생성 (PENDING)")
    payload_resv = {
        "deal_id": deal_id,
        "offer_id": offer_id,
        "buyer_id": buyer_id,
        "qty": 1,
        "hold_minutes": 30,
    }
    r = requests.post(f"{BASE_URL}/reservations", json=payload_resv)
    print("status:", r.status_code)
    body = {}
    try:
        body = r.json()
        pprint(body)
    except Exception:
        print(r.text)

    if r.status_code != 201:
        print("❌ 예약 생성이 실패해서 이후 시나리오 진행 불가.")
        return

    reservation_id = body["id"]
    print(f"=> 생성된 reservation_id = {reservation_id}")

    # ------------------------------------------------------------------
    # 3) 예약 결제 (PENDING → PAID)
    # ------------------------------------------------------------------
    print_section("3) POST /reservations/pay  예약 결제 (PENDING → PAID)")
    payload_pay = {
        "reservation_id": reservation_id,
        "buyer_id": buyer_id,
    }
    r = requests.post(f"{BASE_URL}/reservations/pay", json=payload_pay)
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)

    if r.status_code != 200:
        print("❌ 결제가 정상적으로 되지 않아 이후 진행 불가")
        return

    # ------------------------------------------------------------------
    # 4) 발송 처리 (shipped_at 세팅)
    # ------------------------------------------------------------------
    print_section("4) POST /reservations/{id}/mark_shipped  발송 처리 (shipped_at 세팅)")
    payload_ship = {
        "seller_id": seller_id,
        "shipping_carrier": "CJ",
        "tracking_number": "TEST-1234",
    }
    r = requests.post(
        f"{BASE_URL}/reservations/{reservation_id}/mark_shipped",
        json=payload_ship,
    )
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)

    if r.status_code != 200:
        print("❌ 발송 처리 실패, 이후 시나리오 진행 불가")
        return

    # ------------------------------------------------------------------
    # 5) Buyer가 취소 시도 (buyer_cancel) → A2 정책에 의해 409 가 나와야 "정상"
    # ------------------------------------------------------------------
    print_section("5) POST /reservations/cancel  Buyer 취소 시도 (A2 → 발송 후 취소 불가)")

    payload_refund = {
        "reservation_id": reservation_id,
        "actor": "buyer_cancel",
    }
    r = requests.post(f"{BASE_URL}/reservations/cancel", json=payload_refund)
    print("status:", r.status_code)
    try:
        body = r.json()
        pprint(body)
    except Exception:
        print(r.text)
        body = {}

    if r.status_code == 409:
        print("✅ 기대대로 409 에러 발생 (A2 정책으로 발송 후 취소 불가 처리)")
        print("detail:", body.get("detail"))
    else:
        print("⚠ 예상과 다른 응답 코드입니다. 원래 의도는 발송 후 buyer_cancel 이 409 로 막히는 것.")
        print("status:", r.status_code)

    # ------------------------------------------------------------------
    # 6) 최종 예약 상태 확인
    # ------------------------------------------------------------------
    print_section("6) GET /reservations/{id}  최종 상태 확인")
    r = requests.get(f"{BASE_URL}/reservations/{reservation_id}")
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)

    print("\n" + "=" * 80)
    print("▶ ✅ BAD FLOW: A2 정책 (발송 후 취소 불가) 시나리오 완료")
    print("=" * 80)


if __name__ == "__main__":
    main()