# scripts/test_settlement_payout_b_with_batch_logs.py
# 실행: python scripts/test_settlement_payout_b_with_batch_logs.py

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ====== 환경 설정(여기만 필요하면 수정) ======
BASE_URL = "http://127.0.0.1:9000"
DB_PATH = r"app/ypver2.db"
# ============================================


def http_get(path: str) -> tuple[int, str]:
    url = f"{BASE_URL}{path}"
    req = Request(url, method="GET")
    try:
        with urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"서버 접속 실패: {url} / {e}")


def http_post_json(path: str) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    req = Request(url, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urlopen(req, data=b"{}") as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"raw": body}
    except URLError as e:
        raise RuntimeError(f"서버 접속 실패: {url} / {e}")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def assert_true(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def insert_ready_settlement(conn: sqlite3.Connection, *, block_reason: str | None = None) -> int:
    """
    reservation_settlements 에 READY 1건 삽입.
    reservation_id UNIQUE 제약이 있을 수 있으니 매번 고유값 사용.
    """
    cur = conn.cursor()

    new_resv_id = int(
        cur.execute(
            "SELECT COALESCE(MAX(reservation_id), 990000) + 1 FROM reservation_settlements"
        ).fetchone()[0]
    )

    cur.execute(
        """
        INSERT INTO reservation_settlements (
          reservation_id, deal_id, offer_id, seller_id, buyer_id,
          buyer_paid_amount, pg_fee_amount, platform_commission_amount, seller_payout_amount,
          status, currency,
          block_reason,
          scheduled_payout_at,
          approved_at,
          paid_at,
          ready_at,
          updated_at
        ) VALUES (
          ?, ?, ?, ?, ?,
          ?, ?, ?, ?,
          'READY', 'KRW',
          ?,
          NULL,
          NULL,
          NULL,
          NULL,
          NULL
        )
        """,
        (
            new_resv_id, new_resv_id, new_resv_id, new_resv_id, new_resv_id,
            1000, 0, 0, 1000,
            block_reason,
        ),
    )
    conn.commit()
    new_id = int(cur.execute("SELECT last_insert_rowid()").fetchone()[0])
    return new_id


def set_scheduled_literal(conn: sqlite3.Connection, settlement_id: int, dt_text: str):
    conn.execute(
        "UPDATE reservation_settlements SET scheduled_payout_at = ? WHERE id = ?",
        (dt_text, settlement_id),
    )
    conn.commit()


def set_scheduled_expr(conn: sqlite3.Connection, settlement_id: int, sqlite_expr: str):
    """
    sqlite_expr 예: "datetime('now', '+1 day')"
    """
    conn.execute(
        f"UPDATE reservation_settlements SET scheduled_payout_at = {sqlite_expr} WHERE id = ?",
        (settlement_id,),
    )
    conn.commit()


def fetch_settlement(conn: sqlite3.Connection, settlement_id: int) -> dict:
    row = conn.execute(
        """
        SELECT id, status, approved_at, paid_at, scheduled_payout_at, block_reason, updated_at
        FROM reservation_settlements
        WHERE id = ?
        """,
        (settlement_id,),
    ).fetchone()
    return dict(row) if row else {}


def fetch_event_by_idem(conn: sqlite3.Connection, idem: str) -> dict | None:
    row = conn.execute(
        """
        SELECT id, event_type, reason, idempotency_key, meta, created_at
        FROM event_logs
        WHERE idempotency_key = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (idem,),
    ).fetchone()
    return dict(row) if row else None


def parse_meta(meta_val) -> dict:
    if meta_val is None:
        return {}
    if isinstance(meta_val, str):
        try:
            return json.loads(meta_val)
        except Exception:
            return {}
    # sqlite에서 JSON 타입이더라도 문자열로 오는 경우가 대부분이라, 이 케이스는 안전용
    try:
        return json.loads(str(meta_val))
    except Exception:
        return {}


def main():
    # 0) 서버 확인
    status, _ = http_get("/openapi.json")
    assert_true(status == 200, "서버가 떠있지 않거나 /openapi.json 접근 실패")

    conn = db()
    try:
        # -----------------------------
        # TEST A: 과거 스케줄이면 PAID + 로그(SETTLE_BATCH start/end + SETTLE_PAID batch_id) 검증
        # -----------------------------
        print("=== TEST A: scheduled_payout_at 과거면 bulk-mark-paid가 PAID 처리 + 배치로그 남겨야 함 ===")
        a_id = insert_ready_settlement(conn, block_reason=None)

        # approve
        code, body = http_post_json(f"/settlements/{a_id}/approve")
        assert_true(code == 200 and body.get("status") == "APPROVED", f"approve 실패: {code} {body}")

        # 우리 건이 배치에서 우선 선택되도록 "매우 과거"로 설정
        set_scheduled_literal(conn, a_id, "1000-01-01 00:00:00")

        # bulk 실행 (batch_id 얻기)
        code, body = http_post_json("/settlements/bulk-mark-paid?limit=200")
        assert_true(code == 200 and body.get("ok") is True, f"bulk 실패: {code} {body}")
        batch_id = body.get("batch_id")
        assert_true(isinstance(batch_id, str) and len(batch_id) > 0, f"batch_id 없음: {body}")

        # batch start/end 로그 확인
        start = fetch_event_by_idem(conn, f"paid_batch:{batch_id}:start")
        end = fetch_event_by_idem(conn, f"paid_batch:{batch_id}:end")
        assert_true(start is not None, "SETTLE_BATCH start 로그 없음")
        assert_true(end is not None, "SETTLE_BATCH end 로그 없음")

        end_meta = parse_meta(end["meta"])
        assert_true("updated" in end_meta, f"end.meta에 updated 없음: {end}")
        # updated는 0 이상이면 OK(실 DB에 다른 후보가 있을 수도 있음). 대신 우리 settlement가 PAID인지로 결정
        a = fetch_settlement(conn, a_id)
        assert_true(a.get("status") == "PAID", f"PAID 전환 실패: {a}")
        assert_true(a.get("paid_at") is not None and str(a.get("paid_at")).strip() != "", f"paid_at 미기록: {a}")

        # settlement paid 로그(건별) + batch_id 포함 확인
        paid_evt = fetch_event_by_idem(conn, f"settlement:{a_id}:paid")
        assert_true(paid_evt is not None, "SETTLE_PAID (settlement:ID:paid) 로그 없음")
        paid_meta = parse_meta(paid_evt["meta"])
        assert_true(paid_meta.get("batch_id") == batch_id, f"SETTLE_PAID meta.batch_id 불일치: {paid_evt}")
        assert_true(paid_evt["event_type"] == "SETTLE_PAID", f"event_type 이상: {paid_evt}")

        print(f"PASS A ✅ id={a_id} -> PAID, batch_id={batch_id}")

        # -----------------------------
        # TEST B: 미래 스케줄이면 APPROVED 유지 + 배치 start/end는 남음 + settlement paid 로그 없음
        # -----------------------------
        print("\n=== TEST B: scheduled_payout_at 미래면 bulk-mark-paid가 건드리면 안 됨 (+ 배치로그는 남아야 함) ===")
        b_id = insert_ready_settlement(conn, block_reason="DISPUTE_PATH")

        # approve
        code, body = http_post_json(f"/settlements/{b_id}/approve")
        assert_true(code == 200 and body.get("status") == "APPROVED", f"approve 실패: {code} {body}")

        # 미래 스케줄
        set_scheduled_expr(conn, b_id, "datetime('now', '+1 day')")

        # bulk 실행 (batch_id 얻기)
        code, body = http_post_json("/settlements/bulk-mark-paid?limit=200")
        assert_true(code == 200 and body.get("ok") is True, f"bulk 실패: {code} {body}")
        batch_id2 = body.get("batch_id")
        assert_true(isinstance(batch_id2, str) and len(batch_id2) > 0, f"batch_id 없음: {body}")

        # batch start/end 로그 확인 (0건이어도 남아야 정상)
        start2 = fetch_event_by_idem(conn, f"paid_batch:{batch_id2}:start")
        end2 = fetch_event_by_idem(conn, f"paid_batch:{batch_id2}:end")
        assert_true(start2 is not None, "SETTLE_BATCH start 로그 없음(미래 케이스)")
        assert_true(end2 is not None, "SETTLE_BATCH end 로그 없음(미래 케이스)")

        b = fetch_settlement(conn, b_id)
        assert_true(b.get("status") == "APPROVED", f"미래인데 status 변함(버그): {b}")
        assert_true(b.get("paid_at") is None or str(b.get("paid_at")).strip() == "", f"미래인데 paid_at 찍힘(버그): {b}")

        # settlement paid 로그가 없어야 함 (없으면 None이 정상)
        paid_evt_b = fetch_event_by_idem(conn, f"settlement:{b_id}:paid")
        assert_true(paid_evt_b is None, f"미래인데 SETTLE_PAID 로그 생김(버그): {paid_evt_b}")

        print(f"PASS B ✅ id={b_id} -> APPROVED 유지, batch_id={batch_id2}")

        print("\nALL PASS ✅ (Approve + BulkPaid + Batch start/end logs까지 고정됨)")
        return 0

    finally:
        conn.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\nTEST FAILED ❌ {e}")
        sys.exit(1)