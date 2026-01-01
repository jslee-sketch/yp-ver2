# scripts/bad_flow_mismatched_buyer_pay.py

import requests
import sys
from pprint import pprint

BASE_URL = "http://localhost:9000"  # 필요시 수정

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
    # 0) 헬스 체크
    print_sep("0) 서버 헬스 체크")
    r = requests.get(f"{BASE_URL}/health")
    assert_status(r, 200)
    print("status:", r.status_code)

    # 1) [DEV] 리셋 (있으면, 없으면 스킵)
    print_sep("[DEV] offers.id=1 의 sold_qty / reserved_qty 리셋")
    r = requests.post(f"{BASE_URL}/dev/offers/1/reset_qty")
    if r.status_code == 404:
        print("  - DEV reset 엔드포인트 없음(404). 건너뜁니다.")
    elif r.status_code != 200:
        print(f"❌ 리셋 실패 status={r.status_code}")
        try:
            pprint(r.json())
        except Exception:
            print(r.text)
        sys.exit(1)
    else:
        print("  - done")

    # 2) 정책 A1 설정
    print_sep("1) POST /offers/{offer_id}/policy  → A1 설정")
    payload_policy = {
        "cancel_rule": "A1",
        "cancel_within_days": None,
        "extra_text": "발송 전까지는 단순변심 취소 가능",
    }
    r = requests.post(f"{BASE_URL}/offers/1/policy", json=payload_policy)
    assert_status(r, 200)
    policy = r.json()
    pprint(policy)

    # 3) buyer_id=1 로 예약 생성 (PENDING)
    print_sep("2) POST /reservations  예약 생성 (buyer_id=1)")
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

    if reservation.get("status") != "PENDING":
        print("❌ 예약 생성 후 status 가 PENDING 이 아닙니다.")
        sys.exit(1)

    # 4) buyer_id=2 가 남의 예약 결제 시도 (상태는 PENDING)
    print_sep("3) POST /reservations/pay  (buyer_id=2, 남의 예약 결제 시도 - 상태는 PENDING)")
    payload_pay_other = {
        "reservation_id": reservation_id,
        "buyer_id": 2,
    }
    r = requests.post(f"{BASE_URL}/reservations/pay", json=payload_pay_other)

    # 👉 여기서 '정상'으로 보고 싶은 status를 정해야 함:
    # - 403 Forbidden: "너 이 예약의 주인이 아님"
    # - 404 Not Found: "없는 예약인 척 해서 정보 숨김"
    # 일단 403 기준으로 두고, 네 서비스 정책에 따라 404 로 바꿔도 됨.
    # 예약 소유자가 아닌 경우, 비즈니스 룰 위반으로 409 사용
    expected_forbidden_status = 409



    if r.status_code != expected_forbidden_status:
        print(f"❌ buyer_id=2 로 pay 요청 시 status={r.status_code} (예상={expected_forbidden_status})")
        try:
            body = r.json()
            pprint(body)
        except Exception:
            print(r.text)
        sys.exit(1)

    print(f"status: {r.status_code} (예상대로 남의 예약 결제 차단)")

    try:
        body = r.json()
        pprint(body)
    except Exception:
        print(r.text)
        sys.exit(1)

    detail = body.get("detail", "")
    if not isinstance(detail, str) or "not owned" not in detail:
        print("❌ detail 메시지가 예상과 다릅니다. ('not owned' 포함 x)")
        sys.exit(1)





    # 5) buyer_id=1 로 정상 결제 (PENDING → PAID)
    print_sep("4) POST /reservations/pay  (buyer_id=1, 정상 결제)")
    payload_pay_legit = {
        "reservation_id": reservation_id,
        "buyer_id": 1,
    }
    r = requests.post(f"{BASE_URL}/reservations/pay", json=payload_pay_legit)
    assert_status(r, 200)
    reservation_paid = r.json()
    pprint(reservation_paid)

    if reservation_paid.get("status") != "PAID" or reservation_paid.get("phase") != "PAID":
        print("❌ buyer_id=1 결제 후 status/phase 가 PAID 가 아닙니다.")
        sys.exit(1)

    print_sep("✅ BAD FLOW MISMATCHED-BUYER-PAY(A안): 남의 예약 결제 시도 차단 + 소유자 결제 정상 완료")
    print()

if __name__ == "__main__":
    main()