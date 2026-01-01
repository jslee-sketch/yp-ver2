# scripts/test_actuator_dashboard.py

import os
import json
import requests
from datetime import datetime


BASE_URL = os.environ.get("YP_BASE_URL", "http://127.0.0.1:9000")
ACTUATOR_ID = int(os.environ.get("YP_TEST_ACTUATOR_ID", "1"))


def print_title(title: str):
    print("\n" + "=" * 70)
    print(f"▶ {title}")
    print("=" * 70)


def jprint(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def print_resp(r: requests.Response):
    print("status:", r.status_code)
    try:
        data = r.json()
        jprint(data)
        return data
    except Exception:
        print(r.text)
        return None


def main():
    print("✅ Using BASE_URL:", BASE_URL)
    print("✅ Using ACTUATOR_ID:", ACTUATOR_ID)

    # ---------------------------------------------------------
    # 0) 액츄에이터 기본 정보 확인
    # ---------------------------------------------------------
    print_title(f"0) GET /actuators/{ACTUATOR_ID}  (액츄에이터 기본 정보)")
    r = requests.get(f"{BASE_URL}/actuators/{ACTUATOR_ID}", timeout=5)
    actuator = print_resp(r)
    if r.status_code != 200:
        print("❌ 액츄에이터 정보를 가져오지 못했습니다. ACTUATOR_ID 를 확인해 주세요.")
        return

    # ---------------------------------------------------------
    # 1) 커미션 요약 (정산 전) 확인
    # ---------------------------------------------------------
    print_title(
        f"1) GET /actuators/{ACTUATOR_ID}/commissions/summary  (커미션 요약 - BEFORE payout)"
    )
    r = requests.get(
        f"{BASE_URL}/actuators/{ACTUATOR_ID}/commissions/summary",
        timeout=5,
    )
    summary_before = print_resp(r)

    # ---------------------------------------------------------
    # 2) 커미션 상세 리스트 (최근 N개) 확인
    #    - 구현에 따라 limit/status 파라미터는 없을 수도 있습니다.
    # ---------------------------------------------------------
    print_title(
        f"2) GET /actuators/{ACTUATOR_ID}/commissions  (커미션 로그 목록)"
    )
    try:
        r = requests.get(
            f"{BASE_URL}/actuators/{ACTUATOR_ID}/commissions",
            # 필요하면 쿼리 파라미터 추가:
            # params={"limit": 20, "status": "PENDING"},
            timeout=5,
        )
    except TypeError:
        # 만약 서버에서 limit/status 파라미터를 안 받도록 구현된 경우 대비
        r = requests.get(
            f"{BASE_URL}/actuators/{ACTUATOR_ID}/commissions",
            timeout=5,
        )
    commissions_before = print_resp(r)

    # ---------------------------------------------------------
    # 3) ready_at 지난 커미션 일괄 지급 (배치용 엔드포인트)
    # ---------------------------------------------------------
    print_title(
        "3) POST /actuators/commissions/payout-due  "
        "(ready_at 지난 커미션 일괄 지급)"
    )
    # limit 은 상황에 맞게 조절. 기본 100
    r = requests.post(
        f"{BASE_URL}/actuators/commissions/payout-due",
        params={"limit": 100},
        timeout=10,
    )
    payout_result = print_resp(r)

    if r.status_code == 200:
        paid_count = payout_result.get("paid_count", 0) if payout_result else 0
        paid_ids = payout_result.get("paid_ids", []) if payout_result else []
        print(f"\n✅ 일괄 지급 처리된 커미션 건수: {paid_count}")
        print(f"   지급된 commission_id 목록: {paid_ids}")
    else:
        print("⚠️ payout-due 호출이 실패했습니다. 위 응답을 참고해 주세요.")

    # ---------------------------------------------------------
    # 4) 커미션 요약 (정산 후) 재확인
    # ---------------------------------------------------------
    print_title(
        f"4) GET /actuators/{ACTUATOR_ID}/commissions/summary  (커미션 요약 - AFTER payout)"
    )
    r = requests.get(
        f"{BASE_URL}/actuators/{ACTUATOR_ID}/commissions/summary",
        timeout=5,
    )
    summary_after = print_resp(r)

    # ---------------------------------------------------------
    # 5) (선택) 커미션 리스트 재확인
    # ---------------------------------------------------------
    print_title(
        f"5) GET /actuators/{ACTUATOR_ID}/commissions  (커미션 로그 목록 재확인)"
    )
    r = requests.get(
        f"{BASE_URL}/actuators/{ACTUATOR_ID}/commissions",
        timeout=5,
    )
    commissions_after = print_resp(r)

    # ---------------------------------------------------------
    # 6) 이 액츄에이터가 모집한 셀러 + 오퍼 현황
    # ---------------------------------------------------------
    print_title(
        f"6) GET /actuators/{ACTUATOR_ID}/sellers  (연결된 셀러 목록 + 오퍼 현황)"
    )
    r = requests.get(
        f"{BASE_URL}/actuators/{ACTUATOR_ID}/sellers",
        timeout=5,
    )
    sellers = print_resp(r)

    print("\n🎉 액츄에이터 대시보드용 API 시나리오 완료!")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"   (완료 시각: {now})")


if __name__ == "__main__":
    main()