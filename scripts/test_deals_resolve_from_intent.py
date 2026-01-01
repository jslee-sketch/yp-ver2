# scripts/test_deals_resolve_from_intent.py
from __future__ import annotations

import json
from typing import Any, Dict

import requests

BASE_URL = "http://127.0.0.1:9000"


def call_deal_resolve(payload: Dict[str, Any]):
    """POST /deals/ai/resolve_from_intent 한 번 호출하고 예쁘게 출력."""
    url = f"{BASE_URL}/deals/ai/resolve_from_intent"
    print(f"\n=== POST {url}")
    print("Request payload:")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    resp = requests.post(url, json=payload, timeout=10)
    print(f"\nHTTP {resp.status_code}")
    try:
        data = resp.json()
        print("Response JSON:")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        print("Raw response text:")
        print(resp.text)
        raise

    return resp, data


def main():
    # 공통 베이스 페이로드 (화이트)
    base_payload = {
        "product_name": "애플 에어팟 프로 2세대",
        "desired_qty": 3,
        "target_price": 250000,
        "max_budget": 270000,
        "options": [
            {"title": "색상", "value": "화이트"},
        ],
        "free_text": "화이트 색상 3개",
        "buyer_id": 1,
    }

    # -----------------------------
    # TEST 1: 화이트 Intent 한 번 호출
    #  - 이미 방이 있으면 created=False
    #  - 없으면 created=True
    #  어쨌든 deal_id 하나를 기준으로 잡는다
    # -----------------------------
    print("\n[TEST 1] 화이트 색상 Intent 1회 호출")
    resp1, data1 = call_deal_resolve(base_payload)
    assert resp1.status_code == 200, "TEST 1: HTTP 200 아님"

    first_created = data1["created"]
    white_deal_id = data1["deal_id"]

    print(f"\n[INFO] TEST 1 결과: created={first_created}, deal_id={white_deal_id}")

    # -----------------------------
    # TEST 2: 같은 Intent 다시 보내기
    #  - 반드시 기존 딜 재사용(created=False) + 같은 deal_id 여야 함
    # -----------------------------
    print("\n[TEST 2] 같은 화이트 Intent 다시 → 기존 딜 재사용 기대")
    resp2, data2 = call_deal_resolve(base_payload)
    assert resp2.status_code == 200, "TEST 2: HTTP 200 아님"
    assert data2["created"] is False, "TEST 2: created=False 여야 함 (두 번째 호출)"
    assert (
        data2["deal_id"] == white_deal_id
    ), "TEST 2: deal_id 가 첫 호출과 같아야 함 (기존 방 재사용)"

    # -----------------------------
    # TEST 3: 색상만 블랙으로 바꾸기
    #  - fingerprint 가 바뀌므로 화이트 방과는 다른 deal_id 여야 함
    #  - created=True 이면 '처음 만든 블랙 방', created=False 이면 '기존 블랙 방'
    # -----------------------------
    print("\n[TEST 3] 색상만 블랙으로 변경 → 화이트 방과 다른 딜로 매칭 기대")
    payload_black = {
        **base_payload,
        "options": [{"title": "색상", "value": "블랙"}],
        "free_text": "블랙 색상 3개",
    }

    resp3, data3 = call_deal_resolve(payload_black)
    assert resp3.status_code == 200, "TEST 3: HTTP 200 아님"
    assert (
        data3["deal_id"] != white_deal_id
    ), "TEST 3: 블랙 deal_id 는 화이트 deal_id 와 달라야 함"

    print(
        "\n✅ 모든 테스트 통과!\n"
        f"  - TEST1 created={first_created}, deal_id={white_deal_id}\n"
        f"  - TEST2 created={data2['created']}, deal_id={data2['deal_id']} (화이트 재사용)\n"
        f"  - TEST3 created={data3['created']}, deal_id={data3['deal_id']} (블랙 별도 방)"
    )


if __name__ == "__main__":
    main()