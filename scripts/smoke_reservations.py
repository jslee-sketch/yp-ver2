# scripts/smoke_reservations.py
import os
import json
import requests
from typing import Optional

# ===============================
# 공통: API 베이스 URL 자동 탐지
# ===============================
CANDIDATES: list[str] = []
env_base = os.getenv("API_BASE_URL")
if env_base:
    CANDIDATES.append(env_base.rstrip("/"))
CANDIDATES += [
    "http://127.0.0.1:9000",
    "http://localhost:9000",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

def pick_base() -> Optional[str]:
    for base in CANDIDATES:
        try:
            r = requests.get(f"{base}/openapi.json", timeout=1.5)
            if r.status_code == 200:
                return base
        except Exception:
            pass
    return None

BASE = pick_base()
if not BASE:
    raise SystemExit(
        "❌ API 서버에 연결할 수 없습니다. 서버가 떠 있고 포트를 확인하세요. "
        "필요하면 환경변수 API_BASE_URL 로 지정하세요."
    )

print(f"✅ Using API base: {BASE}")

# 테스트용 기본 파라미터 (환경변수로 덮어쓰기 가능)
DEAL_ID = int(os.getenv("DEAL_ID", "1"))
OFFER_ID = int(os.getenv("OFFER_ID", "46"))
BUYER_ID = int(os.getenv("BUYER_ID", "10"))

# ===============================
# 요청 유틸
# ===============================
def _pretty(resp: requests.Response) -> str:
    try:
        return json.dumps(resp.json(), ensure_ascii=False, indent=2)
    except Exception:
        return resp.text

def get(path: str) -> requests.Response:
    url = f"{BASE}{path}"
    r = requests.get(url, timeout=5)
    print(f"\nGET {url} -> {r.status_code}\n{_pretty(r)}")
    r.raise_for_status()
    return r

def post(path: str, payload: dict) -> requests.Response:
    url = f"{BASE}{path}"
    r = requests.post(url, json=payload, timeout=5)
    print(f"\nPOST {url}\n{json.dumps(payload, ensure_ascii=False)}\n-> {r.status_code}\n{_pretty(r)}")
    r.raise_for_status()
    return r

# ===============================
# 메인 시나리오
# ===============================
def main() -> None:
    print("== A) 잔여/통계 사전 확인 ==")
    get(f"/reservations/offers/{OFFER_ID}/remaining")
    get(f"/reservations/offers/{OFFER_ID}/stats")

    print("\n== B) 예약 생성 ==")
    res = post("/reservations", {
        "deal_id": DEAL_ID,
        "offer_id": OFFER_ID,
        "buyer_id": BUYER_ID,
        "qty": 1,
        "hold_minutes": 5
    }).json()
    resv_id = res["id"]

    print("\n== C) 결제 ==")
    post("/reservations/pay", {
        "reservation_id": resv_id,
        "buyer_id": BUYER_ID,
        "buyer_point_per_qty": 1   # v3.6: qty당 +1
    })

    print("\n== D) 잔여/통계 확인 (결제 후) ==")
    get(f"/reservations/offers/{OFFER_ID}/remaining")
    get(f"/reservations/offers/{OFFER_ID}/stats")

    print("\n== E) 검색 API ==")
    get("/reservations/search?limit=20")
    get(f"/reservations/search?buyer_id={BUYER_ID}&status=PAID&limit=20")
    get(f"/reservations/search?reservation_id={resv_id}&limit=5")

    print("\n== F) (선택) 환불 흐름 테스트 ==")
    try:
        post("/reservations/refund", {"reservation_id": resv_id, "actor": "buyer_cancel"})
    except requests.HTTPError as e:
        # 이미 취소/만료 상태 등 정책상 409가 날 수 있음
        print(f"↪️ 환불 단계에서 정책/상태로 인한 오류가 발생할 수 있습니다: {e}")

    print("\n== G) 만료 스윕 ==")
    post("/reservations/expire", {})

    print("\n== H) (선택) 전량 판매 시 오퍼 확정 ==")
    try:
        post(f"/reservations/offers/{OFFER_ID}/confirm", {})
    except requests.HTTPError as e:
        print("↪️ 전량 판매가 아니면 409가 정상입니다:", e)

    # ======================================
    # I) 커서 페이징(search_page) 동작 점검
    # ======================================
    print("\n== I) 커서 페이징 테스트 ==")
    try:
        r1 = get("/reservations/search_page?limit=5")
        payload1 = r1.json()
        items1 = payload1.get("items") or []
        count1 = payload1.get("count", len(items1))
        cursor1 = payload1.get("next_cursor")
        print(f"page1 count={count1}, next_cursor={cursor1}")

        if cursor1:
            r2 = get(f"/reservations/search_page?limit=5&cursor={cursor1}")
            payload2 = r2.json()
            items2 = payload2.get("items") or []
            count2 = payload2.get("count", len(items2))
            cursor2 = payload2.get("next_cursor")
            print(f"page2 count={count2}, next_cursor={cursor2}")
    except requests.HTTPError as e:
        # 서버에 해당 엔드포인트가 아직 없거나 스키마가 다른 경우
        print("search_page 페이징 엔드포인트 확인 필요:", e)

if __name__ == "__main__":
    main()