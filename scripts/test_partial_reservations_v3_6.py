# scripts/test_partial_refund_flow.py
"""
부분 환불(Partial Refund) 플로우 테스트 스크립트.

⚠️ 사전 조건
- 아래 RESERVATION_ID 에 해당하는 예약은
  - status == PAID
  - qty >= 2  (부분환불 테스트용이므로 2개 이상 권장)
- 서버는 v3_6 엔드포인트(/v3_6/...)가 떠 있어야 함.

환경변수로도 설정 가능:
- YP_BASE_URL (기본: http://127.0.0.1:9000/v3_6)
- YP_PARTIAL_REFUND_RESERVATION_ID (기본: 1)
- YP_PARTIAL_REFUND_QTY (기본: 1)
"""

import os
import json
from datetime import datetime

import requests


BASE_URL = os.getenv("YP_BASE_URL", "http://127.0.0.1:9000/v3_6")
RESERVATION_ID = int(os.getenv("YP_PARTIAL_REFUND_RESERVATION_ID", "1"))
QTY_REFUND = int(os.getenv("YP_PARTIAL_REFUND_QTY", "1"))  # 부분환불 수량


def pretty(obj):
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        return str(obj)


def main():
    print(f"✅ Using BASE_URL: {BASE_URL}")
    print(f"✅ Using RESERVATION_ID: {RESERVATION_ID}")
    print(f"✅ Using QTY_REFUND: {QTY_REFUND}")
    print()

    # =====================================================
    # 0) 현재 예약 상태 조회
    # =====================================================
    print("====== 0) GET /reservations/by-id/{id} ======")
    url_get = f"{BASE_URL}/reservations/by-id/{RESERVATION_ID}"
    r0 = requests.get(url_get)
    print("status:", r0.status_code)
    try:
        j0 = r0.json()
        print(pretty(j0))
    except Exception:
        print(r0.text)
        return

    status = j0.get("status")
    qty = j0.get("qty")
    print()
    print(f"👉 현재 예약 status: {status}")
    print(f"👉 현재 예약 수량 qty: {qty}")
    print("   (참고) 부분환불 테스트를 위해서는 status=PAID, qty>=2 인 예약을 권장합니다.")
    print()

    # qty 체크 (부분환불 수량보다 적으면 중단)
    if isinstance(qty, int) and qty < QTY_REFUND:
        print("⚠️ 경고: 예약의 총 수량(qty)이 부분환불 수량(QTY_REFUND)보다 적습니다.")
        print(f"   - qty           : {qty}")
        print(f"   - QTY_REFUND    : {QTY_REFUND}")
        print("   이 예약으로는 부분환불 테스트를 진행할 수 없습니다. 다른 예약 ID를 사용하거나,")
        print("   부분환불 수량(QTY_REFUND)을 줄인 뒤 다시 실행해주세요.")
        return

    # status 가 PAID 가 아니면 경고만 띄우고, 그래도 진행해봄 (409 나오는 게 정상일 수 있음)
    if status != "PAID":
        print("⚠️ 경고: 이 스크립트는 PAID 상태에서 부분환불을 테스트하는 용도입니다.")
        print("   현재 상태에서는 /refund/preview 또는 /refund 에서 409(충돌)가 나와도 자연스러운 상황일 수 있습니다.")
        print()

    # =====================================================
    # 1) POST /reservations/refund/preview  (부분환불 미리보기)
    # =====================================================
    print("====== 1) POST /reservations/refund/preview (partial) ======")
    url_preview = f"{BASE_URL}/reservations/refund/preview"
    payload_preview = {
        "reservation_id": RESERVATION_ID,
        "actor": "buyer_cancel",   # 기본: 바이어가 취소
        "quantity_refund": QTY_REFUND,  # ★ 부분환불 수량
    }
    r1 = requests.post(url_preview, json=payload_preview)
    print("status:", r1.status_code)
    try:
        j1 = r1.json()
        print(pretty(j1))
    except Exception:
        print(r1.text)
        j1 = None

    if r1.status_code != 200:
        print()
        print("⚠️ 부분환불 미리보기 실패 또는 정책상 허용되지 않음.")
        print("   위의 detail 메시지를 참고하세요.")
        print()
    else:
        # context/decision 에서 몇 가지 핵심 값만 다시 요약
        ctx = j1.get("context") if isinstance(j1, dict) else None
        dec = j1.get("decision") if isinstance(j1, dict) else None
        if ctx:
            print()
            print("👉 Preview Context 요약:")
            print(f"   - quantity_total: {ctx.get('quantity_total')}")
            print(f"   - quantity_refund: {ctx.get('quantity_refund')}")
            print(f"   - amount_goods: {ctx.get('amount_goods')}")
            print(f"   - amount_shipping: {ctx.get('amount_shipping')}")
            print(f"   - amount_total: {ctx.get('amount_total')}")
        if dec:
            print()
            print("👉 Preview Decision 요약:")
            print(f"   - use_pg_refund: {dec.get('use_pg_refund')}")
            print(f"   - pg_fee_burden: {dec.get('pg_fee_burden')}")
            print(f"   - platform_fee_burden: {dec.get('platform_fee_burden')}")
            print(f"   - revoke_buyer_points: {dec.get('revoke_buyer_points')}")
            print(f"   - revoke_seller_points: {dec.get('revoke_seller_points')}")
            print(f"   - need_settlement_recovery: {dec.get('need_settlement_recovery')}")
            print(f"   - note: {dec.get('note')}")
        print()

    # =====================================================
    # 2) POST /reservations/refund  (부분환불 실제 실행)
    # =====================================================
    print("====== 2) POST /reservations/refund (partial) ======")
    url_refund = f"{BASE_URL}/reservations/refund"
    payload_refund = {
        "reservation_id": RESERVATION_ID,
        "actor": "buyer_cancel",
        "quantity_refund": QTY_REFUND,  # ★ 동일한 수량으로 환불 실행
    }
    r2 = requests.post(url_refund, json=payload_refund)
    print("status:", r2.status_code)
    try:
        j2 = r2.json()
        print(pretty(j2))
    except Exception:
        print(r2.text)
        j2 = None

    if r2.status_code != 200:
        print()
        print("⚠️ 부분환불 처리에 실패하거나, 정책에 의해 거부되었습니다.")
        print("   위의 detail 메시지를 참고하세요.")
        print()
    else:
        print()
        print("✅ 부분환불이 성공적으로 처리되었습니다. (응답 본문은 위 JSON 참조)")
        print()

    # =====================================================
    # 3) 다시 예약 상태 조회 (부분환불 후)
    # =====================================================
    print("====== 3) GET /reservations/by-id/{id} (after partial refund) ======")
    r3 = requests.get(url_get)
    print("status:", r3.status_code)
    try:
        j3 = r3.json()
        print(pretty(j3))
    except Exception:
        print(r3.text)
        j3 = None

    if isinstance(j3, dict):
        print()
        print("👉 After partial refund:")
        print(f"   - status: {j3.get('status')}")
        print(f"   - qty: {j3.get('qty')}")
        # 부분환불 누적 필드가 있다면 같이 보여줌 (없으면 None)
        print(f"   - refunded_qty: {j3.get('refunded_qty')}")
        print(f"   - refunded_amount_total: {j3.get('refunded_amount_total')}")
        print()

    print("🎉 부분환불 플로우 테스트 스크립트 종료")
    print(f"   (완료 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")


if __name__ == "__main__":
    main()