import os
import sqlite3
from datetime import datetime, timedelta
import requests
from pprint import pprint

PORT = os.getenv("YP_PORT", "9000")
BASE_URL = f"http://127.0.0.1:{PORT}"
DB_PATH = "./app/ypver2.db"


def print_section(title: str):
    print("\n" + "=" * 80)
    print(f"▶ {title}")
    print("=" * 80)


def main():
    offer_id = 1
    deal_id = 1
    buyer_id = 1
    seller_id = 1

    # 0) 헬스 체크
    print_section("0) 서버 헬스 체크")
    r = requests.get(f"{BASE_URL}/health")
    print("status:", r.status_code)
    if r.status_code != 200:
        print("❌ 서버 헬스 체크 실패, 테스트 중단")
        return

    # 1) A3 정책 세팅
    print_section("1) POST /offers/{offer_id}/policy  → A3(발송 후 3일 이내 취소 가능) 설정")
    payload_policy = {
        "cancel_rule": "A3",
        "cancel_within_days": 3,
        "extra_text": "배송완료 후 3일 이내 단순변심 취소 가능, 왕복배송비는 구매자 부담.",
    }
    r = requests.post(f"{BASE_URL}/offers/{offer_id}/policy", json=payload_policy)
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)
    if r.status_code not in (200, 201):
        print("❌ 정책 설정 실패, 이후 진행 불가")
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

    # 3) 결제
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

    # 4) 발송
    print_section("4) POST /reservations/{id}/mark_shipped  발송 처리")
    payload_ship = {
        "seller_id": seller_id,
        "shipping_carrier": "CJ",
        "tracking_number": "TEST-A3-EXPIRED",
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
        print("❌ 발송 실패")
        return

    # 5) 수령확인
    print_section("5) POST /reservations/{id}/arrival_confirm  수령확인")
    payload_arrival = {
        "buyer_id": buyer_id,
    }
    r = requests.post(
        f"{BASE_URL}/reservations/{reservation_id}/arrival_confirm",
        json=payload_arrival,
    )
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)
    if r.status_code != 200:
        print("❌ 수령확인 실패")
        return

    # 6) DB 직접 수정: delivered_at / arrival_confirmed_at 을 5일 전으로
    print_section("6) [TEST] DB 직접 수정 → delivered_at/arrival_confirmed_at 을 5일 전으로 조정")
    target_dt = datetime.utcnow() - timedelta(days=5)
    target_str = target_dt.strftime("%Y-%m-%dT%H:%M:%S")

    print("DB_PATH =", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE reservations
        SET delivered_at = ?, arrival_confirmed_at = ?
        WHERE id = ?
        """,
        (target_str, target_str, reservation_id),
    )
    conn.commit()
    conn.close()
    print(f"  - reservation_id={reservation_id} → delivered_at={target_str}")

    # 7) A3 기간 초과 상태에서 취소 시도
    print_section("7) POST /reservations/cancel  → A3 기한 초과 취소 시도")

    payload_cancel = {
        "reservation_id": reservation_id,
        "actor": "buyer_cancel",
    }
    r = requests.post(f"{BASE_URL}/reservations/cancel", json=payload_cancel)
    print("status:", r.status_code)
    try:
        body = r.json()
        pprint(body)
    except Exception:
        print(r.text)
        body = {}

    if r.status_code == 409 and body.get("detail") in (
        "cancel_period_expired",
        "cancel_not_allowed_after_shipped",
    ):
        print("✅ 기대대로 409 에러 (A3 기간 초과로 취소 불가)")
    else:
        print("⚠ 예상과 다른 응답 코드 (원래 의도: 409 cancel_period_expired)")
        print("status:", r.status_code)

    # 8) 최종 상태 확인
    print_section("8) GET /reservations/{id}  최종 상태 확인")
    r = requests.get(f"{BASE_URL}/reservations/{reservation_id}")
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)

    print("\n" + "=" * 80)
    print("▶ ✅ BAD FLOW A3-EXPIRED: 발송+3일 초과 취소 불가 시나리오 완료")
    print("=" * 80)


if __name__ == "__main__":
    main()