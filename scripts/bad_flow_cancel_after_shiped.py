# scripts/bad_flow_cancel_after_shipped.py

import requests
import sys
from pprint import pprint

BASE_URL = "http://localhost:9000"  # 필요 시 수정

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

    # 1) [DEV] offers.id=1 리셋 (있으면 쓰고, 없으면 스킵)
    print_sep("[DEV] offers.id=1 의 sold_qty / reserved_qty 리셋")
    r = requests.post(f"{BASE_URL}/dev/offers/1/reset_qty")
    if r.status_code == 404:
        print("  - DEV reset 엔드포인트 없음(404). 건너뜁니다.")
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

    # 4) 결제 (PENDING → PAID)
    print_sep("3) POST /reservations/pay  결제 (PENDING → PAID)")
    payload_pay = {
        "reservation_id": reservation_id,
        "buyer_id": 1,
    }
    r = requests.post(f"{BASE_URL}/reservations/pay", json=payload_pay)
    assert_status(r, 200)
    reservation_paid = r.json()
    pprint(reservation_paid)

    if reservation_paid.get("status") != "PAID" or reservation_paid.get("phase") != "PAID":
        print("❌ 결제 후 status/phase 가 PAID 가 아닙니다.")
        sys.exit(1)

    # 5) SHIPPED 상태로 변경
    print_sep("4) 예약을 SHIPPED 상태로 변경")

    # ✅ 여기 한 줄을 실제 서버 구현에 맞춰 수정하면 됨
    # 예시 A: DEV용 강제 전이
    r = requests.post(f"{BASE_URL}/dev/reservations/{reservation_id}/mark_shipped")

    # 예시 B: 실제 API가 있다면 이런 식일 수도 있음 (있으면 위/아래 중 선택해서 사용)
    # r = requests.post(f"{BASE_URL}/reservations/ship", json={"reservation_id": reservation_id})

    if r.status_code == 404:
        print("❌ SHIPPED 상태로 변경하는 DEV/API 엔드포인트가 없습니다. 여기서 중단합니다.")
        try:
            pprint(r.json())
        except Exception:
            print(r.text)
        sys.exit(1)

    if r.status_code not in (200, 204):
        print(f"❌ SHIPPED 전이 실패. status={r.status_code}")
        try:
            pprint(r.json())
        except Exception:
            print(r.text)
        sys.exit(1)

    print("  - SHIPPED 처리 완료 (엔드포인트 동작 확인 필요)")

    # 6) 발송 후 취소 시도
    print_sep("5) POST /reservations/cancel  (이미 SHIPPED 상태)")
    payload_cancel = {
        "reservation_id": reservation_id,
        "buyer_id": 1,
        "reason": "단순변심",
    }
    r = requests.post(f"{BASE_URL}/reservations/cancel", json=payload_cancel)

    expected_error_status = 409
    if r.status_code != expected_error_status:
        print(f"❌ 발송 후 취소 요청 응답 status={r.status_code} (예상={expected_error_status})")
        try:
            pprint(r.json())
        except Exception:
            print(r.text)
        sys.exit(1)

    print(f"status: {r.status_code}")
    body = r.json()
    pprint(body)
    detail = body.get("detail", "")

    # detail 메시지까지 어느 정도 검증 (필요시 수정)
    if not isinstance(detail, str) or "cannot cancel" not in detail:
        print("❌ detail 메시지가 예상과 다릅니다. ('cannot cancel' 포함 x)")
        sys.exit(1)

    print("detail:", detail)
    print_sep("✅ BAD FLOW CANCEL-AFTER-SHIPPED(A1): 발송 후 취소 불가 시나리오 완료")
    print()

if __name__ == "__main__":
    main()