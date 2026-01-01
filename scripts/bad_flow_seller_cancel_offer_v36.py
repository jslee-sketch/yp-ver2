# scripts/bad_flow_seller_cancel_offer_v36.py

import requests
from pprint import pprint
import sys

BASE_URL = "http://localhost:9000"  # v3.6 서버 포트 기준


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
    offer_id = 1
    deal_id = 1
    buyer_id = 1

    # 0) 헬스 체크
    print_sep("0) 서버 헬스 체크")
    r = requests.get(f"{BASE_URL}/health")
    assert_status(r, 200)
    print("status:", r.status_code)

    # 1) [DEV] offers.id=1 sold/reserved 리셋 (있으면 사용, 없으면 스킵)
    print_sep("[DEV] offers.id=1 의 sold_qty / reserved_qty 리셋")
    r = requests.post(f"{BASE_URL}/dev/offers/{offer_id}/reset_qty")
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

    # 2) 정책 A1 설정 (기존 /offers 엔드포인트 사용)
    print_sep("1) POST /offers/{offer_id}/policy  → A1 설정")
    payload_policy = {
        "cancel_rule": "A1",
        "cancel_within_days": None,
        "extra_text": "발송 전까지는 단순변심 취소 가능",
    }
    r = requests.post(f"{BASE_URL}/offers/{offer_id}/policy", json=payload_policy)
    assert_status(r, 200)
    policy = r.json()
    pprint(policy)

    # 3) v3.6 예약 1 생성 (PENDING 유지할 예약)
    print_sep("2) POST /v3_6/reservations  예약1 생성 (PENDING 유지)")
    payload_resv_1 = {
        "offer_id": offer_id,
        "buyer_id": buyer_id,
        "qty": 1,
        "deal_id": deal_id,
        "hold_minutes": 10,
    }
    r = requests.post(f"{BASE_URL}/v3_6/reservations", json=payload_resv_1)
    assert_status(r, 201)
    resv1 = r.json()
    pprint(resv1)
    resv_id_1 = resv1["id"]
    print(f"=> 생성된 reservation_id_1 = {resv_id_1}")

    # 4) v3.6 예약 2 생성 + 결제 (PAID 만들기)
    print_sep("3) POST /v3_6/reservations  예약2 생성 (이후 PAID로 변경)")
    payload_resv_2 = {
        "offer_id": offer_id,
        "buyer_id": buyer_id,
        "qty": 1,
        "deal_id": deal_id,
        "hold_minutes": 10,
    }
    r = requests.post(f"{BASE_URL}/v3_6/reservations", json=payload_resv_2)
    assert_status(r, 201)
    resv2 = r.json()
    pprint(resv2)
    resv_id_2 = resv2["id"]
    print(f"=> 생성된 reservation_id_2 = {resv_id_2}")

    print_sep("4) POST /v3_6/reservations/pay  예약2 결제 (PENDING → PAID)")
    payload_pay_2 = {
        "reservation_id": resv_id_2,
        "buyer_id": buyer_id,
    }
    r = requests.post(f"{BASE_URL}/v3_6/reservations/pay", json=payload_pay_2)
    assert_status(r, 200)
    resv2_paid = r.json()
    pprint(resv2_paid)
    assert resv2_paid["status"] == "PAID", "예약2가 PAID 상태가 아님"

    # 5) allow_paid=False 상태에서 오퍼 취소 시도 → PAID 존재하므로 409 기대
    print_sep("5) POST /v3_6/offers/{offer_id}/cancel  (allow_paid=False, PAID 예약 존재)")
    payload_cancel_block = {
        "penalize": True,
        "allow_paid": False,
        "reverse_buyer_points": True,
        "buyer_point_per_qty": 20,
    }
    r = requests.post(
        f"{BASE_URL}/v3_6/offers/{offer_id}/cancel",
        json=payload_cancel_block,
    )
    print("status:", r.status_code)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    pprint(body)

    if r.status_code != 409:
        print("⚠️ 예상은 status=409 (PAID 예약 있어 취소 불가) 였습니다.")
    else:
        print("✅ 예상대로 PAID 예약 존재 시 allow_paid=False 에서 409 반환")

    # 6) allow_paid=True 로 다시 오퍼 취소 시도 → PENDING/PAID 모두 정리 기대
    print_sep("6) POST /v3_6/offers/{offer_id}/cancel  (allow_paid=True, 강제 취소)")
    payload_cancel_force = {
        "penalize": True,               # 셀러 귀책으로 보고 환불 정책 적용
        "allow_paid": True,             # PAID 있어도 강제 처리
        "reverse_buyer_points": True,
        "buyer_point_per_qty": 20,
    }
    r = requests.post(
        f"{BASE_URL}/v3_6/offers/{offer_id}/cancel",
        json=payload_cancel_force,
    )
    assert_status(r, 200)
    offer_after = r.json()
    pprint(offer_after)

    # 7) 예약1/예약2 상태 확인 (v3.5 reservations 조회 API 재사용)
    print_sep("7) GET /v3_6/reservations/by-id/{id}  예약1/2 상태 확인")
    r1 = requests.get(f"{BASE_URL}/v3_6/reservations/by-id/{resv_id_1}")
    assert_status(r1, 200)
    resv1_after = r1.json()
    pprint(resv1_after)

    r2 = requests.get(f"{BASE_URL}/v3_6/reservations/by-id/{resv_id_2}")
    assert_status(r2, 200)
    resv2_after = r2.json()
    pprint(resv2_after)

    print(f"예약1 status: {resv1_after['status']}")
    print(f"예약2 status: {resv2_after['status']}")

    print_sep("✅ BAD FLOW SELLER-CANCEL-OFFER(v3.6): PAID 예약 존재 시 동작 확인 완료")
    print()


if __name__ == "__main__":
    main()