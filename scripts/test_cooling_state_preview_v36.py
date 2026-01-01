# scripts/test_cooling_state_preview_v36.py
import requests
import json

BASE_URL = "http://localhost:9000"

# 👉 여기 숫자를, 테스트할 "PAID 상태 예약 id" 로 바꿔줘
RESERVATION_ID = 72


def call_preview(actor: str = "buyer_cancel"):
    payload = {
        "reservation_id": RESERVATION_ID,
        "actor": actor,
    }
    r = requests.post(
        f"{BASE_URL}/v3_6/reservations/refund/preview",
        json=payload,
    )
    print(f"status: {r.status_code}")
    try:
        data = r.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        # cooling_state만 콕 집어서 한 줄 요약
        ctx = data.get("context", {})
        print("👉 cooling_state:", ctx.get("cooling_state"))
        return data
    except Exception:
        print(r.text)
        return None


def main():
    print("=" * 40)
    print("▶ 1) 현재 arrival_confirmed_at 상태에서 preview")
    print("=" * 40)
    call_preview()

    input(
        "\n💡 2단계) DB에서 reservations.id={rid} 의 arrival_confirmed_at 을\n"
        "   now - 1일 정도(쿨링 기간 안)으로 바꾼 뒤 Enter 를 눌러줘...".format(
            rid=RESERVATION_ID
        )
    )

    print("\n" + "=" * 40)
    print("▶ 2) arrival_confirmed_at = now-1일 정도 (WITHIN_COOLING 기대)")
    print("=" * 40)
    call_preview()

    input(
        "\n💡 3단계) DB에서 reservations.id={rid} 의 arrival_confirmed_at 을\n"
        "   now - 30일 정도(쿨링 기간 지난 상태)로 바꾼 뒤 Enter 를 눌러줘...".format(
            rid=RESERVATION_ID
        )
    )

    print("\n" + "=" * 40)
    print("▶ 3) arrival_confirmed_at = now-30일 정도 (AFTER_COOLING 기대)")
    print("=" * 40)
    call_preview()


if __name__ == "__main__":
    main()