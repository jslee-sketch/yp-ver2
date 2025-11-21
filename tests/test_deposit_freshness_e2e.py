# tests/test_deposit_freshness_e2e.py
import importlib
from fastapi.testclient import TestClient

from app.main import app
from app.config import project_rules as R

client = TestClient(app)

# 테스트에 맞는 고정값 (DB에 존재하는 값으로 맞춰주세요)
DEAL_ID  = 1
OFFER_ID = 46
BUYER_ID = 10

def _post(url: str, json=None):
    return client.post(url, json=json)

def test_deposit_freshness_after_reservation():
    # 0) 디파짓 요구 강제: 환경/티어와 무관하게 재현되도록
    R.DEPOSIT_REQUIRE_ALWAYS = True

    # 1) 오퍼 재고 넉넉히 확보
    r = client.post(f"/offers/{OFFER_ID}/set_total_qs", params={"total": 999})
    assert r.status_code in (200, 201)

    old_id = None
    new_id = None
    try:
        # 2) (의도적으로) 예약 전에 OLD 디파짓 생성 → 결제요건으로 인정되면 안 됨
        r = _post(f"/deposits/hold/{DEAL_ID}/{BUYER_ID}", json={"amount": 3000})
        assert r.status_code in (200, 201), r.text
        old_id = r.json()["deposit_id"]

        # 3) 예약 생성 → 201
        r = _post(
            "/reservations",
            json={"deal_id": DEAL_ID, "offer_id": OFFER_ID, "buyer_id": BUYER_ID, "qty": 1, "hold_minutes": 5},
        )
        assert r.status_code == 201, r.text
        rid = r.json()["id"]

        # 4) 첫 결제 → ★ 409 deposit_required (OLD 는 무효여야 함)
        r = _post("/reservations/pay", json={"reservation_id": rid, "buyer_id": BUYER_ID})
        assert r.status_code == 409, r.text
        assert "deposit_required" in r.text

        # 5) (신선한) NEW 디파짓 생성 → 201/200 + HELD
        r = _post(f"/deposits/hold/{DEAL_ID}/{BUYER_ID}", json={"amount": 3000})
        assert r.status_code in (200, 201), r.text
        new_id = r.json()["deposit_id"]

        # 6) 두 번째 결제 → ★ 200 PAID (예약 이후 디파짓을 인정)
        r = _post("/reservations/pay", json={"reservation_id": rid, "buyer_id": BUYER_ID})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "PAID"
    finally:
        # (선택) 정리: NEW/OLD 디파짓 환불 시도 (멱등)
        for did in (new_id, old_id):
            if did:
                client.post(f"/deposits/refund/{did}")
        # 토글 복구
        R.DEPOSIT_REQUIRE_ALWAYS = False