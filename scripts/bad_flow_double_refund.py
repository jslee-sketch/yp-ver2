import os
import sqlite3
import requests
from pprint import pprint

PORT = os.getenv("YP_PORT", "9000")
BASE_URL = f"http://127.0.0.1:{PORT}"
DB_PATH = "./app/ypver2.db"


def print_section(title: str):
    print("\n" + "=" * 80)
    print(f"▶ {title}")
    print("=" * 80)


def reset_offer_counters(offer_id: int):
    """
    테스트를 반복 돌릴 수 있게, 특정 offer의 sold_qty / reserved_qty 를 0으로 리셋.
    (DEV / 테스트 용도 전용)
    """
    print_section(f"[DEV] offers.id={offer_id} 의 sold_qty / reserved_qty 리셋")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE offers
        SET sold_qty = 0,
            reserved_qty = 0
        WHERE id = ?
        """,
        (offer_id,),
    )
    conn.commit()
    conn.close()
    print("  - done")


def main():
    offer_id = 1
    deal_id = 1
    buyer_id = 1

    # 0) 헬스 체크
    print_section("0) 서버 헬스 체크")
    r = requests.get(f"{BASE_URL}/health")
    print("status:", r.status_code)
    if r.status_code != 200:
        print("❌ 서버 헬스 체크 실패")
        return

    # 0-1) (DEV) 재고 카운터 초기화
    reset_offer_counters(offer_id)

    # 1) A1 정책 (발송 전까지 취소 가능)
    print_section("1) POST /offers/{offer_id}/policy  → A1(발송 전까지 취소 가능) 설정")
    payload_policy = {
        "cancel_rule": "A1",
        "cancel_within_days": None,
        "extra_text": "발송 전까지는 단순변심 취소 가능",
    }
    r = requests.post(f"{BASE_URL}/offers/{offer_id}/policy", json=payload_policy)
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)
    if r.status_code not in (200, 201):
        print("❌ 정책 설정 실패")
        return

    # 2) 예약 생성
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
        print("❌ 예약 생성 실패")
        return

    reservation_id = body["id"]
    print(f"=> 생성된 reservation_id = {reservation_id}")

    # 3) 결제 (PENDING → PAID)
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
        print("❌ 결제 실패")
        return

    # 4) 첫 번째 환불 (buyer_cancel) → 200 이어야 정상
    print_section("4) POST /reservations/cancel  첫 번째 환불 (buyer_cancel)")
    payload_cancel = {
        "reservation_id": reservation_id,
        "actor": "buyer_cancel",
    }
    r = requests.post(f"{BASE_URL}/reservations/cancel", json=payload_cancel)
    print("status:", r.status_code)
    try:
        first_body = r.json()
        pprint(first_body)
    except Exception:
        print(r.text)
        first_body = {}

    if r.status_code != 200:
        print("❌ 첫 번째 환불이 정상 처리되지 않음 (원래는 200이어야 함)")
        return

    # 5) 두 번째 환불 시도 → 이미 CANCELLED 상태이므로 409 가 나와야 정상
    print_section("5) POST /reservations/cancel  두 번째 환불 시도 (이미 CANCELLED 상태)")
    r = requests.post(f"{BASE_URL}/reservations/cancel", json=payload_cancel)
    print("status:", r.status_code)
    try:
        second_body = r.json()
        pprint(second_body)
    except Exception:
        print(r.text)
        second_body = {}

    if r.status_code == 409:
        print("✅ 기대대로 409 에러 (이미 CANCELLED 상태에서 이중 환불 방지)")
        print("detail:", second_body.get("detail"))
    else:
        print("⚠ 예상과 다른 응답 코드 (원래 의도: 409 conflict)")
        print("status:", r.status_code)

    print("\n" + "=" * 80)
    print("▶ ✅ BAD FLOW DOUBLE-REFUND: 이중 환불 방지 시나리오 완료")
    print("=" * 80)


if __name__ == "__main__":
    main()