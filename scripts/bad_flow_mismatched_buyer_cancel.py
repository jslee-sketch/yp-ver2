# scripts/bad_flow_mismatched_buyer_cancel.py

import requests
import sys
from pprint import pprint

BASE_URL = "http://localhost:9000"  # 필요 시 수정

# v3.6 strict cancel 엔드포인트
CANCEL_URL_V36 = f"{BASE_URL}/v3_6/reservations/cancel"

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

    # 4) buyer_id=2 가 남의 예약 취소 시도 (v3.6 strict cancel)
    print_sep("3) POST /v3_6/reservations/cancel  (buyer_id=2, 남의 예약 취소 시도 - 상태는 PENDING)")
    payload_cancel_other = {
        "reservation_id": reservation_id,
        "buyer_id": 2,
    }
    r = requests.post(CANCEL_URL_V36, json=payload_cancel_other)

    expected_status = 409  # not owned by buyer
    if r.status_code != expected_status:
        print(f"❌ buyer_id=2 로 cancel 요청 시 status={r.status_code} (예상={expected_status})")
        try:
            body = r.json()
            pprint(body)
        except Exception:
            print(r.text)
        sys.exit(1)

    print(f"status: {r.status_code} (예상대로 남의 예약 취소 차단)")
    body = r.json()
    pprint(body)

    detail = body.get("detail", "")
    if not isinstance(detail, str) or "not owned" not in detail:
        print("❌ detail 메시지가 예상과 다릅니다. ('not owned' 포함 x)")
        sys.exit(1)

    # 5) buyer_id=1 로 정상 취소 (v3.6 strict cancel)
    print_sep("4) POST /v3_6/reservations/cancel  (buyer_id=1, 정상 취소)")
    payload_cancel_legit = {
        "reservation_id": reservation_id,
        "buyer_id": 1,
    }
    r = requests.post(CANCEL_URL_V36, json=payload_cancel_legit)
    assert_status(r, 200)
    reservation_cancelled = r.json()
    pprint(reservation_cancelled)

    if reservation_cancelled.get("status") != "CANCELLED":
        print("❌ buyer_id=1 취소 후 status 가 CANCELLED 가 아닙니다.")
        sys.exit(1)

    print_sep("✅ BAD FLOW MISMATCHED-BUYER-CANCEL(v3.6): 남의 예약 취소 차단 + 소유자 취소 정상 완료")
    print()

if __name__ == "__main__":
    main()