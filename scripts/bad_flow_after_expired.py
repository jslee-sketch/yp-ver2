# scripts/bad_flow_after_expired.py

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

    # 1) [DEV] 리셋 (있으면 쓰고, 없으면 스킵)
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

    # 4) DEV: 만료 처리 (expires_at 지난 상태로 간주)
    print_sep("3) [DEV] 예약을 EXPIRED 상태로 변경")
    # ✅ 서버에 이 라우트 하나만 추가해두면 됨 (404면 추후 구현)
    r = requests.post(f"{BASE_URL}/dev/reservations/{reservation_id}/expire")

    if r.status_code == 404:
        print("❌ EXPIRED 상태로 변경하는 DEV/API 엔드포인트가 없습니다. 여기서 중단합니다.")
        try:
            pprint(r.json())
        except Exception:
            print(r.text)
        sys.exit(1)

    if r.status_code not in (200, 204):
        print(f"❌ EXPIRED 전이 실패 status={r.status_code}")
        try:
            pprint(r.json())
        except Exception:
            print(r.text)
        sys.exit(1)

    print("  - EXPIRED 처리 완료 (엔드포인트 동작 확인 필요)")

    # 5) EXPIRED 이후 결제 시도
    print_sep("4) POST /reservations/pay  (EXPIRED 이후 결제 시도)")
    payload_pay = {
        "reservation_id": reservation_id,
        "buyer_id": 1,
    }
    r = requests.post(f"{BASE_URL}/reservations/pay", json=payload_pay)

    expected_error_status = 409  # 혹은 422 등, 실제 구현에 맞게 나중에 고정
    if r.status_code != expected_error_status:
        print(f"❌ EXPIRED 후 pay 응답 status={r.status_code} (예상={expected_error_status})")
        try:
            pprint(r.json())
        except Exception:
            print(r.text)
        sys.exit(1)

    print(f"status: {r.status_code}")
    body = r.json()
    pprint(body)
    detail = body.get("detail", "")

    if not isinstance(detail, str) or "expired" not in detail.lower():
        print("⚠️ detail 메시지에 'expired' 가 포함되어 있지 않습니다. (문구는 나중에 맞춰도 됨)")

    # 6) EXPIRED 이후 취소 시도
    print_sep("5) POST /reservations/cancel  (EXPIRED 이후 취소 시도)")
    payload_cancel = {
        "reservation_id": reservation_id,
        "buyer_id": 1,
        "reason": "테스트: 만료 후 취소",
    }
    r = requests.post(f"{BASE_URL}/reservations/cancel", json=payload_cancel)

    # 여기서는 둘 중 하나 정책 선택:
    # - 완전 차단 (409)  또는
    # - "만료이지만 취소는 허용" 정책 (200)
    # 일단 "완전 차단" 기준으로 작성해둘게.
    expected_cancel_status = 409
    if r.status_code != expected_cancel_status:
        print(f"⚠️ EXPIRED 후 cancel 응답 status={r.status_code} (예상={expected_cancel_status} 기준)")
        try:
            pprint(r.json())
        except Exception:
            print(r.text)
        # 취소 정책은 서비스 정책에 따라 달라질 수 있으니, 여기선 강종까진 안 해도 됨.
    else:
        print(f"status: {r.status_code}")
        body = r.json()
        pprint(body)

    print_sep("✅ BAD FLOW AFTER-EXPIRED: 만료 이후 결제/취소 시나리오 점검 완료(정책 값에 따라 튜닝 필요)")
    print()

if __name__ == "__main__":
    main()