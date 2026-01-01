"""
v3.5 전체 플로우 스모크 테스트 스크립트

- Buyer 생성
- Seller 생성 (승인은 TODO: 프로젝트 라우터에 맞게 수정)
- Deal 생성
- Offer 생성
- (선택) Deposit 생성
- Reservation 생성
- Reservation 결제
- Seller 발송 처리
- Buyer 도착 확인
- Review 생성
- Review summary / Seller level 조회

실행:
    pip install requests
    python smoke_test_v35.py
"""

import os
import time
import json
from typing import Any, Dict, Optional
from datetime import datetime

import requests


BASE_URL = os.getenv("SMOKE_BASE_URL", "http://localhost:9000")


def _print_step(title: str):
    print("\n" + "=" * 80)
    print(f"[STEP] {title}")
    print("=" * 80)

def print_json(obj) -> None:
    """
    dict / list 같은 응답을 예쁘게 출력하기 위한 헬퍼.
    """
    try:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    except TypeError:
        # 직렬화 안 되는 타입이면 그냥 그대로 출력
        print(obj)

def _now_str() -> str:
    """이메일/아이디용 타임스탬프 문자열 (예: 20251129_234808)"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _unique_email(prefix: str) -> str:
    """
    prefix 기반으로 매번 다른 이메일 주소 생성 (예: buyer_smoke_20251129_130501@example.com)
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}@example.com"


def _req(method: str, path: str, **kwargs) -> Dict[str, Any]:
    url = BASE_URL.rstrip("/") + path
    resp = requests.request(method, url, **kwargs)
    print(f"{method} {path} -> {resp.status_code}")
    try:
        data = resp.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        print(resp.text)

    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code} on {method} {path}")
    return data


def create_buyer() -> int:
    _print_step("Create Buyer")

    email = _unique_email("buyer_smoke")

    body = {
        "email": email,
        "password": "SmokeTest123!",
        "name": "SmokeBuyer",
        "phone": "010-0000-0000",
        "address": "Seoul",
        "zip_code": "00000",
        "gender": "M",
        "birth_date": "1990-01-01T00:00:00",
    }
    data = _req("POST", "/buyers", json=body)
    print_json(data)
    return data["id"]


def create_seller():
    _print_step("Create Seller")

    # 🔹 매번 다른 접미어 (타임스탬프)
    suffix = _now_str()

    # 🔹 이메일/사업자번호/상호명에 모두 suffix 붙여서 절대 중복 안 나게
    email = f"seller_smoke_{suffix}@example.com"
    business_number = f"BN-{suffix}"
    business_name = f"SmokeSeller Inc. {suffix}"

    body = {
        "email": email,
        "password": "smoke_pw_1234",          # ✅ 아까 Buyer처럼 password 필드 포함
        "business_name": business_name,
        "business_number": business_number,
        "phone": "010-1111-2222",
        "company_phone": "02-1111-2222",
        "address": "Seoul",
        "zip_code": "00000",
        "established_date": "2020-01-01T00:00:00",
    }

    data = _req("POST", "/sellers", json=body)
    print_json(data)        # 응답 한 번 찍어보고
    return data["id"]


def approve_seller(seller_id: int):
    """
    Seller 승인 API가 따로 있다면 여기에 맞게 호출.
    없으면 이 함수는 그냥 pass 시키고, DB에서 수동으로 verified_at 넣어줘야 함.
    """
    _print_step("Approve Seller (set APPROVED)")
    path = f"/sellers/{seller_id}/approve"
    data = _req("POST", path)
    print(data)


def create_deal(creator_id: int) -> int:
    _print_step("Create Deal")
    body = {
        "product_name": "Smoke Test Product",
        "creator_id": creator_id,
        "desired_qty": 5,
        "target_price": 10000,
        "max_budget": 12000,
        "option1_title": "색상",
        "option1_value": "블랙",
        "free_text": "스모크 테스트용 딜입니다.",
    }
    # ❗ 실제 deals 라우터 경로에 맞게 수정 (예: /deals)
    data = _req("POST", "/deals", json=body)
    return int(data.get("id") or data.get("deal_id"))


def create_offer(seller_id: int, deal_id: int) -> int:
    _print_step("Create Offer")
    body = {
        "deal_id": deal_id,
        "seller_id": seller_id,
        "price": 9500,
        "total_available_qty": 10,
        "delivery_days": 3,
        "comment": "스모크 테스트 오퍼",
    }
    # ✅ 우리가 수정한 offers 라우터: POST /offers
    data = _req("POST", "/offers", json=body)
    return int(data.get("id") or data.get("offer_id"))


def create_deposit_if_needed(
    buyer_id: int,
    deal_id: int,
    qty: int,
) -> Optional[int]:
    """
    - 딜 / 바이어 / 수량 기준으로 필요한 디파짓을 선납
    - /deposits/policy/preview 는 buyer_id, deal_id 를 쿼리로 받음
    - /deposits/ 에서 amount_mismatch(409)가 나면 expected_amount 로 한 번 더 재시도
    """
    _print_step("Create Deposit")

    # 1) 디파짓 정책 프리뷰 (✅ buyer_id, deal_id 를 query 로 같이 보냄)
    pol = _req(
        "GET",
        "/deposits/policy/preview",
        params={"buyer_id": buyer_id, "deal_id": deal_id},
    )
    print_json(pol)

    deposit_percent = float(pol.get("deposit_percent", 0.0) or 0.0)

    # 2) 딜 정보 조회 (target_price 등)
    deal = _req("GET", f"/deals/{deal_id}")
    print_json(deal)

    target_price = float(deal.get("target_price") or 0.0)
    total_price = target_price * qty

    # 3) 1차 시도용 대략적인 금액 계산
    #    (어차피 서버가 amount_mismatch 면 expected_amount를 알려줌)
    guessed_amount = int(total_price * deposit_percent)
    if guessed_amount <= 0:
        guessed_amount = 1

    body = {
        "deal_id": deal_id,
        "buyer_id": buyer_id,
        "qty": qty,
        "amount": guessed_amount,
    }

    url = f"{BASE_URL}/deposits/"
    print("POST /deposits/ -> 1st try")
    resp = requests.post(url, json=body, timeout=10)
    print(f"POST /deposits/ -> {resp.status_code}")

    try:
        data = resp.json()
    except Exception:
        data = {}

    print_json(data)

    # 4) amount_mismatch(409) 이면 expected_amount 로 한 번 더 재시도
    if resp.status_code == 409:
        detail = data.get("detail") or {}
        if isinstance(detail, dict) and detail.get("error") == "amount_mismatch":
            expected = detail.get("expected_amount")
            if expected is not None:
                print(f"→ retry with expected_amount={expected}")
                body["amount"] = expected

                resp = requests.post(url, json=body, timeout=10)
                print(f"POST /deposits/ (retry) -> {resp.status_code}")
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                print_json(data)

    # 5) 그래도 실패면 에러로 처리
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code} on POST /deposits/")

    deposit_id = data.get("deposit_id")
    return int(deposit_id) if deposit_id is not None else None


def create_reservation(deal_id: int, offer_id: int, buyer_id: int, qty: int) -> int:
    _print_step("Create Reservation")
    body = {
        "deal_id": deal_id,
        "offer_id": offer_id,
        "buyer_id": buyer_id,
        "qty": qty,
        "hold_minutes": 10,
    }
    # ✅ /reservations (v3.5)
    data = _req("POST", "/reservations", json=body)
    return int(data.get("id") or data.get("reservation_id"))


def pay_reservation(reservation_id: int, buyer_id: int) -> None:
    _print_step("Pay Reservation")
    body = {
        "reservation_id": reservation_id,
        "buyer_id": buyer_id,
    }
    # ✅ /reservations/pay
    _req("POST", "/reservations/pay", json=body)


def mark_shipped(reservation_id: int, seller_id: int) -> None:
    """
    6-1) 셀러가 발송 완료 표시
    """
    _print_step("Mark Shipped")
    body = {"seller_id": seller_id}
    resp = _req("POST", f"/reservations/{reservation_id}/mark_shipped", json=body)
    print_json(resp)


def confirm_arrival(reservation_id: int, buyer_id: int) -> None:
    """
    6-2) 바이어가 도착 확인
    """
    _print_step("Arrival Confirm")
    body = {"buyer_id": buyer_id}
    resp = _req("POST", f"/reservations/{reservation_id}/arrival_confirm", json=body)
    print_json(resp)


def create_review(reservation_id: int, seller_id: int, buyer_id: int) -> int:
    """
    7) 리뷰 생성
    - 방금 만든 예약(reservation_id)에 대해
    - buyer_id / seller_id를 맞춰서 리뷰 한 건 생성
    """
    _print_step("Create Review")
    body = {
        "reservation_id": reservation_id,
        "seller_id": seller_id,
        "buyer_id": buyer_id,
        "price_fairness": 5,
        "quality": 5,
        "shipping": 4,
        "communication": 5,
        "accuracy": 4,
        "media_count": 1,
        "comment": "스모크 테스트 리뷰입니다.",
    }
    data = _req("POST", "/reviews", json=body)
    print_json(data)
    return int(data.get("id", 0))


def get_review_summary(seller_id: int) -> dict:
    """
    8) 셀러 리뷰 요약 조회
    """
    _print_step("Get Seller Review Summary")
    data = _req("GET", f"/reviews/seller/{seller_id}/summary")
    print_json(data)
    return data


def get_seller_level(seller_id: int) -> dict:
    """
    (옵션) 셀러 레벨 조회
    - /reviews/seller/{seller_id}/level 엔드포인트가 있을 때만 유효
    - 없으면 404 나올 수 있음 (그냥 참고용)
    """
    _print_step("Get Seller Level")
    data = _req("GET", f"/reviews/seller/{seller_id}/level")
    print_json(data)
    return data


def main():
    print(f"=== SMOKE TEST START: BASE_URL={BASE_URL} ===")

    # 이 테스트에서 사용할 수량
    qty = 2

    # 1) Buyer 생성
    buyer_id = create_buyer()

    # 2) Seller 생성 + 승인
    seller_id = create_seller()
    approve_seller(seller_id)

    # 3) Deal 생성 (Buyer가 만든 딜)
    deal_id = create_deal(creator_id=buyer_id)

    # 4) Deposit 선납 (딜 기준)
    try:
        create_deposit_if_needed(
            buyer_id=buyer_id,
            deal_id=deal_id,
            qty=qty,
        )
    except Exception as e:
        print(f"[WARN] 디파짓 생성 단계에서 오류 발생: {e}")
        print("→ 그래도 계속 진행해서 reservation 단계에서 deposit_required 가 나오는지 확인합니다.")

    # 5) Seller Offer 등록 (딜 마감 후 제안)
    offer_id = create_offer(
        seller_id=seller_id,
        deal_id=deal_id,
    )

    # 6) Buyer Reservation 생성 (오퍼에 대해 예약)
    reservation_id = create_reservation(
        deal_id=deal_id,
        offer_id=offer_id,
        buyer_id=buyer_id,
        qty=qty,
    )

    # 7) Reservation 결제 (완료)
    pay_reservation(
        reservation_id=reservation_id,
        buyer_id=buyer_id,
    )

    # 8) 발송 확인
    mark_shipped(reservation_id=reservation_id, seller_id=seller_id)
    
    # 9) 인수 확인
    confirm_arrival(reservation_id=reservation_id, buyer_id=buyer_id)
    
    # 10) Review 생성
    review_id = create_review(reservation_id=reservation_id, seller_id=seller_id, buyer_id=buyer_id)
    
    print(f"created review_id={review_id}")
    get_review_summary(seller_id=seller_id)
    # 필요하면: get_seller_level(seller_id=seller_id)

    get_seller_level(seller_id=seller_id)

    print()
    print("=== SMOKE TEST DONE ✅ ===")

if __name__ == "__main__": main()