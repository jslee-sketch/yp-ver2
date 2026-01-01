#!/usr/bin/env python
import os
import json
import requests
from datetime import datetime

# 기본 BASE_URL 은 v3_6
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:9000/v3_6")
# 테스트할 예약 ID (환경변수 RESERVATION_ID 로 덮어쓸 수 있음)
RESV_ID = int(os.getenv("RESERVATION_ID", "80"))

def pretty(obj):
    return json.dumps(obj, ensure_ascii=False, indent=2)


def step0_get_reservation():
    print("====== 0) GET /reservations/by-id/{id} ======")
    url = f"{BASE_URL}/reservations/by-id/{RESV_ID}"
    resp = requests.get(url)
    print("status:", resp.status_code)
    try:
        print(pretty(resp.json()))
    except Exception:
        print(resp.text)
    print()
    return resp


def step1_refund_preview(actor="buyer_cancel"):
    print("====== 1) POST /reservations/refund/preview ======")
    url = f"{BASE_URL}/reservations/refund/preview"
    payload = {
        "reservation_id": RESV_ID,
        "actor": actor,
    }
    resp = requests.post(url, json=payload)
    print("status:", resp.status_code)
    try:
        print(pretty(resp.json()))
    except Exception:
        print(resp.text)
    print()
    return resp


def step2_refund_execute(actor="buyer_cancel"):
    print("====== 2) POST /reservations/refund (실제 환불 실행) ======")
    url = f"{BASE_URL}/reservations/refund"
    payload = {
        "reservation_id": RESV_ID,
        "actor": actor,
    }
    resp = requests.post(url, json=payload)
    print("status:", resp.status_code)
    try:
        print(pretty(resp.json()))
    except Exception:
        print(resp.text)
    print()

    if resp.status_code == 200:
        print("✅ 환불이 성공적으로 처리되었습니다.")
    else:
        print("⚠️ 환불 처리에 실패하거나, 정책에 의해 거부되었습니다.")
    print()
    return resp


def step3_get_reservation_after():
    print("====== 3) GET /reservations/by-id/{id} (after refund) ======")
    url = f"{BASE_URL}/reservations/by-id/{RESV_ID}"
    resp = requests.get(url)
    print("status:", resp.status_code)
    try:
        print(pretty(resp.json()))
    except Exception:
        print(resp.text)
    print()
    return resp


def main():
    print(f"✅ Using BASE_URL: {BASE_URL}")
    print(f"✅ Using RESERVATION_ID: {RESV_ID}")
    print()

    # 0) 현재 예약 상태 조회
    r0 = step0_get_reservation()

    # 상태 안내 (단순 참고용)
    if r0.status_code == 200:
        data = r0.json()
        status = data.get("status")
        print(f"👉 현재 예약 status: {status}")
        if status != "PAID":
            print("   (참고) 이 스크립트는 PAID 상태에서 환불을 테스트하는 용도입니다.")
            print("   지금은 정책에 따라 409(충돌) 등이 나와도 자연스러운 상황일 수 있습니다.")
        print()

    # 1) 환불 미리보기
    step1_refund_preview(actor="buyer_cancel")

    # 2) 실제 환불 실행
    step2_refund_execute(actor="buyer_cancel")

    # 3) 환불 후 예약 상태 재조회
    step3_get_reservation_after()

    print("🎉 환불 플로우 테스트 스크립트 종료")
    print(f"   (완료 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")


if __name__ == "__main__":
    main()