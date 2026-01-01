# scripts/time_flow_reservation_expire.py

import requests
from pprint import pprint
from datetime import datetime, timezone

BASE_URL = "http://localhost:9000"

# ✅ v3.6 라우터를 쓰려면 True, 구(/reservations) 라우터를 쓰려면 False
USE_V36 = True

RES_CREATE_PATH = "/v3_6/reservations" if USE_V36 else "/reservations"
RES_PAY_PATH    = "/v3_6/reservations/pay" if USE_V36 else "/reservations/pay"


def print_sep(title: str):
    print("\n" + "=" * 80)
    print(f"▶ {title}")
    print("=" * 80)


def iso_to_dt(s: str) -> datetime | None:
    """ISO 문자열을 UTC datetime으로 변환 (없으면 None)"""
    if not s:
        return None
    # 2025-12-07T02:26:08.286713 형태를 UTC naive로 파싱
    try:
        # fromisoformat은 tz가 없으면 naive dt 반환. 비교 편의를 위해 UTC로 간주.
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def main():
    # 0) 헬스 체크
    print_sep("0) 서버 헬스 체크")
    r = requests.get(f"{BASE_URL}/health")
    print("status:", r.status_code)
    r.raise_for_status()

    # 1) 예약 생성 (hold_minutes=1)
    print_sep(f"1) POST {RES_CREATE_PATH}  예약 생성 (hold_minutes=1)")
    payload_resv = {
        "offer_id": 1,
        "buyer_id": 1,
        "qty": 1,
        "deal_id": 1,
        "hold_minutes": 1,
    }
    r = requests.post(f"{BASE_URL}{RES_CREATE_PATH}", json=payload_resv)
    print("status:", r.status_code)
    r.raise_for_status()
    resv = r.json()
    pprint(resv)
    reservation_id = resv["id"]
    print(f"=> 생성된 reservation_id = {reservation_id}")

    created_at = iso_to_dt(resv.get("created_at"))
    expires_at = iso_to_dt(resv.get("expires_at"))
    if created_at and expires_at:
        delta_sec = (expires_at - created_at).total_seconds()
        print(f"created_at: {created_at.isoformat()}  |  expires_at: {expires_at.isoformat()}  |  Δ={int(delta_sec)}s")
    else:
        print("created_at / expires_at 파싱 실패. 원문:", resv.get("created_at"), resv.get("expires_at"))

    # 2) 바로 결제 시도 (성공 기대)
    print_sep(f"2) POST {RES_PAY_PATH}  (바로 결제 시도 - 성공 기대)")
    payload_pay = {
        "reservation_id": reservation_id,
        "buyer_id": 1,
    }
    r = requests.post(f"{BASE_URL}{RES_PAY_PATH}", json=payload_pay)
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)

    # 3) 새 예약 생성 (hold_minutes=1)
    print_sep(f"3) POST {RES_CREATE_PATH}  두 번째 예약 생성 (hold_minutes=1)")
    r = requests.post(f"{BASE_URL}{RES_CREATE_PATH}", json=payload_resv)
    r.raise_for_status()
    resv2 = r.json()
    pprint(resv2)
    reservation_id2 = resv2["id"]
    print(f"=> 생성된 reservation_id2 = {reservation_id2}")

    created_at2 = iso_to_dt(resv2.get("created_at"))
    expires_at2 = iso_to_dt(resv2.get("expires_at"))
    if created_at2 and expires_at2:
        delta_sec2 = (expires_at2 - created_at2).total_seconds()
        print(f"created_at2: {created_at2.isoformat()}  |  expires_at2: {expires_at2.isoformat()}  |  Δ={int(delta_sec2)}s")
    else:
        print("created_at2 / expires_at2 파싱 실패. 원문:", resv2.get("created_at"), resv2.get("expires_at"))

    # 4) 만료 후 결제 시도
    input("\n💡 DB에서 expires_at을 과거로 바꾸거나, 70초 정도 기다린 뒤 Enter를 눌러주세요... ")

    print_sep(f"4) POST {RES_PAY_PATH}  (만료 후 결제 시도 - 409 기대)")
    payload_pay2 = {
        "reservation_id": reservation_id2,
        "buyer_id": 1,
    }
    r = requests.post(f"{BASE_URL}{RES_PAY_PATH}", json=payload_pay2)
    print("status:", r.status_code)
    try:
        pprint(r.json())
    except Exception:
        print(r.text)


if __name__ == "__main__":
    main()