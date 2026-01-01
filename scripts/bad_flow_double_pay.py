# scripts/bad_flow_double_pay.py

import requests
import sys
from pprint import pprint

BASE_URL = "http://localhost:9000"  # 필요하면 수정

def print_sep(title: str):
    print("\n" + "=" * 80)
    print(f"▶ {title}")
    print("=" * 80)

def assert_status(resp, expected_status: int):
    if resp.status_code != expected_status:
        print(f"❌ 예상 status={expected_status}, 실제 status={resp.status_code}")
        try:
            print("response json:")
            pprint(resp.json())
        except Exception:
            print(resp.text)
        sys.exit(1)

def main():
    # 0) 서버 헬스 체크
    print_sep("0) 서버 헬스 체크")
    r = requests.get(f"{BASE_URL}/health")
    assert_status(r, 200)
    print("status:", r.status_code)

    # 1) [DEV] offers.id=1 의 sold_qty / reserved_qty 리셋 (있으면 쓰고, 없으면 스킵)
    print_sep("[DEV] offers.id=1 의 sold_qty / reserved_qty 리셋")
    r = requests.post(f"{BASE_URL}/dev/offers/1/reset_qty")
    if r.status_code == 404:
        print("  - DEV reset 엔드포인트가 없음(404). 이 단계는 건너뜁니다.")
    elif r.status_code != 200:
        print(f"❌ 리셋 요청 실패. status={r.status_code}")
        try:
            pprint(r.json())
        except Exception:
            print(r.text)
        sys.exit(1)
    else:
        print("  - done")

    # 2) 정책 A1 설정
    print_sep("1) POST /offers/{offer_id}/policy  → A1(발송 전까지 취소 가능) 설정")
    payload_policy = {
        "cancel_rule": "A1",
        "cancel_within_days": None,
        "extra_text": "발송 전까지는 단순변심 취소 가능",
    }
    r = requests.post(f"{BASE_URL}/offers/1/policy", json=payload_policy)
    assert_status(r, 200)
    policy = r.json()
    pprint(policy)

    # 3) 예약 생성 (PENDING)
    print_sep("2) POST /reservations  예약 생성 (PENDING)")
    payload_resv = {
        "offer_id": 1,
        "buyer_id": 1,
        "qty": 1,
        "deal_id": 1,
    }
    r = requests.post(f"{BASE_URL}/reservations", json=payload_resv)
    assert_status(r, 201)
    reservation = r.json()
    pprint(reservation)

    reservation_id = reservation["id"]
    print(f"=> 생성된 reservation_id = {reservation_id}")

    if reservation.get("status") != "PENDING" or reservation.get("phase") != "PENDING":
        print("❌ 예약 생성 후 status/phase 가 PENDING 이 아닙니다.")
        sys.exit(1)

    # 4) 첫 번째 결제 (PENDING → PAID)
    print_sep("3) POST /reservations/pay  첫 번째 결제 (PENDING → PAID)")
    payload_pay = {
        "reservation_id": reservation_id,
        "buyer_id": 1,
    }
    r = requests.post(f"{BASE_URL}/reservations/pay", json=payload_pay)
    assert_status(r, 200)
    reservation_after_first_pay = r.json()
    pprint(reservation_after_first_pay)

    if reservation_after_first_pay.get("status") != "PAID" or reservation_after_first_pay.get("phase") != "PAID":
        print("❌ 첫 번째 결제 후 status/phase 가 PAID 가 아닙니다.")
        sys.exit(1)

    # 5) 두 번째 결제 시도 (이미 PAID 상태)
    print_sep("4) POST /reservations/pay  두 번째 결제 시도 (이미 PAID 상태)")
    r = requests.post(f"{BASE_URL}/reservations/pay", json=payload_pay)

    expected_error_status = 409
    if r.status_code != expected_error_status:
        print(f"❌ 두 번째 /reservations/pay 응답 status={r.status_code} (예상={expected_error_status})")
        try:
            pprint(r.json())
        except Exception:
            print(r.text)
        sys.exit(1)

    print(f"status: {r.status_code}")

    try:
        body = r.json()
    except Exception:
        print("❌ 두 번째 결제 응답이 JSON 이 아닙니다.")
        print(r.text)
        sys.exit(1)

    pprint(body)
    detail = body.get("detail", "")

    if not isinstance(detail, str) or "cannot pay" not in detail:
        print("❌ 두 번째 결제 detail 메시지가 예상과 다릅니다. ('cannot pay' 포함 x)")
        sys.exit(1)

    print("=> 두 번째 결제 요청에 대해 에러 응답을 반환함")
    print("detail:", detail)

    print_sep("✅ BAD FLOW DOUBLE-PAY: 이중 결제 방지 시나리오 완료")
    print()

if __name__ == "__main__":
    main()