# tests/test_reservations_apply_deadtime_e2e.py
import os
import importlib
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

# 🔧 고정 환경 가정 (이미 로컬 데이터에 존재하는 값)
DEAL_ID = int(os.getenv("E2E_DEAL_ID", 1))
OFFER_ID = int(os.getenv("E2E_OFFER_ID", 46))
BUYER_ID = int(os.getenv("E2E_BUYER_ID", 10))

def _set_now_utc(base_utc: datetime):
    """
    서버가 참조하는 now_utc 를 고정값으로 패치.
    time_policy 와 project_rules 양쪽에 동일하게 주입.
    """
    import app.config.time_policy as tp
    import app.config.project_rules as pr
    def _fixed_now():
        return base_utc
    tp.now_utc = _fixed_now  # type: ignore[attr-defined]
    pr.now_utc = _fixed_now  # type: ignore[attr-defined]

def _mk_client():
    # app.main 은 모듈 임포트 시 라우터만 세팅하고,
    # 실제 시간은 요청 시점에 now_utc()를 부르므로 재로드 불필요
    from app.main import app
    return TestClient(app)

def _ensure_offer_capacity(client: TestClient, offer_id: int, total: int = 999):
    r = client.post(f"/offers/{offer_id}/set_total_qs", params={"total": total})
    # 없거나 접근 불가한 오퍼면 E2E 의미가 없으므로 skip
    if r.status_code == 404:
        pytest.skip(f"Offer {offer_id} not found. Skip E2E.")
    assert r.status_code in (200, 409), f"unexpected status on set_total_qs: {r.status_code} {r.text}"

def _create_reservation(client: TestClient, *, deal_id: int, offer_id: int, buyer_id: int, qty: int, hold_minutes: int):
    payload = {
        "deal_id": deal_id,
        "offer_id": offer_id,
        "buyer_id": buyer_id,
        "qty": qty,
        "hold_minutes": hold_minutes,
    }
    r = client.post("/reservations", json=payload)
    return r

def _parse_dt(s: str) -> datetime:
    # API가 naive 또는 aware 둘 다 나올 수 있어 유연 파싱
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        # 서버가 naive(UTC기준 문자열)로 내려줄 수도 있으니 UTC로 간주
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

@pytest.mark.order(1)
def test_reservation_expiry_in_working_hours():
    """
    근무시간 내(월 09:00 KST == 00:00 UTC)에 5분 홀드로 예약 생성 시,
    expires_at == created_at + 5분 여야 한다.
    """
    base_utc = datetime(2025, 1, 6, 0, 0, tzinfo=timezone.utc)  # Mon 00:00 UTC == KST 09:00
    _set_now_utc(base_utc)
    client = _mk_client()
    _ensure_offer_capacity(client, OFFER_ID)

    r = _create_reservation(client,
                            deal_id=DEAL_ID, offer_id=OFFER_ID, buyer_id=BUYER_ID,
                            qty=1, hold_minutes=5)
    assert r.status_code == 201, f"unexpected: {r.status_code} {r.text}"
    data = r.json()
    created_at = _parse_dt(data["created_at"])
    expires_at = _parse_dt(data["expires_at"])

    assert int((expires_at - created_at).total_seconds()) == 5 * 60

@pytest.mark.order(2)
def test_reservation_expiry_skips_weekend_deadtime():
    """
    일요일 심야(KST) → 다음 근무 재개(월 09:00 KST)로 밀린 뒤 5분.
    KST 2025-01-05 23:50 == UTC 2025-01-05 14:50 에 생성하면
    expires_at 는 UTC 2025-01-06 00:05 가 되어야 한다.
    """
    base_utc = datetime(2025, 1, 5, 14, 50, tzinfo=timezone.utc)  # Sun 23:50 KST
    _set_now_utc(base_utc)
    client = _mk_client()
    _ensure_offer_capacity(client, OFFER_ID)

    r = _create_reservation(client,
                            deal_id=DEAL_ID, offer_id=OFFER_ID, buyer_id=BUYER_ID,
                            qty=1, hold_minutes=5)
    assert r.status_code == 201, f"unexpected: {r.status_code} {r.text}"
    data = r.json()
    expires_at = _parse_dt(data["expires_at"])

    expected = datetime(2025, 1, 6, 0, 5, tzinfo=timezone.utc)  # Mon 00:05 UTC
    assert expires_at == expected, f"expires_at={expires_at.isoformat()} expected={expected.isoformat()}"