# scripts/test_settlement_payout_b_with_batch_logs_actor.py
# 실행: python scripts/test_settlement_payout_b_with_batch_logs_actor.py

from __future__ import annotations

import json
import sqlite3
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


BASE_URL = "http://127.0.0.1:9000"
DB_PATH = r"app/ypver2.db"
ACTOR_ID = 777


def http_get(path: str) -> tuple[int, str]:
    url = f"{BASE_URL}{path}"
    req = Request(url, method="GET")
    with urlopen(req) as resp:
        return resp.status, resp.read().decode("utf-8")


def http_post_json(path: str, headers: dict | None = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    req = Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    if headers:
        for k, v in headers.items():
            req.add_header(k, str(v))

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
    cur = conn.cursor()
    new_resv_id = int(cur.execute("SELECT COALESCE(MAX(reservation_id), 990000) + 1 FROM reservation_settlements").fetchone()[0])
    cur.execute(
        """
        INSERT INTO reservation_settlements (
          reservation_id, deal_id, offer_id, seller_id, buyer_id,
          buyer_paid_amount, pg_fee_amount, platform_commission_amount, seller_payout_amount,
          status, currency, block_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'READY', 'KRW', ?)
        """,
        (new_resv_id, new_resv_id, new_resv_id, new_resv_id, new_resv_id, 1000, 0, 0, 1000, block_reason),
    )
    conn.commit()
    return int(cur.execute("SELECT last_insert_rowid()").fetchone()[0])


def set_scheduled_literal(conn: sqlite3.Connection, settlement_id: int, dt_text: str):
    conn.execute("UPDATE reservation_settlements SET scheduled_payout_at = ? WHERE id = ?", (dt_text, settlement_id))
    conn.commit()


def set_scheduled_expr(conn: sqlite3.Connection, settlement_id: int, sqlite_expr: str):
    conn.execute(f"UPDATE reservation_settlements SET scheduled_payout_at = {sqlite_expr} WHERE id = ?", (settlement_id,))
    conn.commit()


def fetch_settlement(conn: sqlite3.Connection, settlement_id: int) -> dict:
    row = conn.execute(
        "SELECT id, status, approved_at, paid_at, scheduled_payout_at FROM reservation_settlements WHERE id = ?",
        (settlement_id,),
    ).fetchone()
    return dict(row) if row else {}


def fetch_event_by_idem(conn: sqlite3.Connection, idem: str) -> dict | None:
    row = conn.execute(
        "SELECT id, event_type, actor_type, actor_id, reason, idempotency_key, meta FROM event_logs WHERE idempotency_key = ? ORDER BY id DESC LIMIT 1",
        (idem,),
    ).fetchone()
    return dict(row) if row else None


def parse_meta(meta_val) -> dict:
    if meta_val is None:
        return {}
    try:
        return json.loads(meta_val)
    except Exception:
        return {}


def main():
    status, _ = http_get("/openapi.json")
    assert_true(status == 200, "서버가 떠있지 않거나 /openapi.json 접근 실패")

    headers = {"X-Actor-Id": str(ACTOR_ID)}

    conn = db()
    try:
        print("=== TEST A: 과거 스케줄이면 PAID + batch start/end + actor_id 로그 ===")
        a_id = insert_ready_settlement(conn, block_reason=None)

        code, body = http_post_json(f"/settlements/{a_id}/approve", headers=headers)
        assert_true(code == 200 and body.get("status") == "APPROVED", f"approve 실패: {code} {body}")

        # approve 로그 actor_id 확인
        approve_evt = fetch_event_by_idem(conn, f"settlement:{a_id}:approve")
        assert_true(approve_evt is not None, "SETTLE_APPROVE 로그 없음")
        assert_true(int(approve_evt["actor_id"]) == ACTOR_ID, f"approve actor_id 불일치: {approve_evt}")

        set_scheduled_literal(conn, a_id, "1000-01-01 00:00:00")

        code, body = http_post_json("/settlements/bulk-mark-paid?limit=200", headers=headers)
        assert_true(code == 200 and body.get("ok") is True, f"bulk 실패: {code} {body}")
        batch_id = body.get("batch_id")
        assert_true(batch_id, "batch_id 없음")

        # batch start/end actor_id 확인
        start = fetch_event_by_idem(conn, f"paid_batch:{batch_id}:start")
        end = fetch_event_by_idem(conn, f"paid_batch:{batch_id}:end")
        assert_true(start is not None and end is not None, "batch start/end 로그 없음")
        assert_true(int(start["actor_id"]) == ACTOR_ID, f"batch start actor_id 불일치: {start}")
        assert_true(int(end["actor_id"]) == ACTOR_ID, f"batch end actor_id 불일치: {end}")

        # settlement paid 로그 actor_id 확인
        paid_evt = fetch_event_by_idem(conn, f"settlement:{a_id}:paid")
        assert_true(paid_evt is not None, "SETTLE_PAID 로그 없음")
        assert_true(int(paid_evt["actor_id"]) == ACTOR_ID, f"paid actor_id 불일치: {paid_evt}")

        a = fetch_settlement(conn, a_id)
        assert_true(a.get("status") == "PAID", f"PAID 전환 실패: {a}")

        print(f"PASS A ✅ id={a_id}, batch_id={batch_id}")

        print("\n=== TEST B: 미래 스케줄이면 APPROVED 유지 + batch start/end 로그 + paid 로그 없음 ===")
        b_id = insert_ready_settlement(conn, block_reason="DISPUTE_PATH")

        code, body = http_post_json(f"/settlements/{b_id}/approve", headers=headers)
        assert_true(code == 200 and body.get("status") == "APPROVED", f"approve 실패: {code} {body}")

        set_scheduled_expr(conn, b_id, "datetime('now', '+1 day')")

        code, body = http_post_json("/settlements/bulk-mark-paid?limit=200", headers=headers)
        assert_true(code == 200 and body.get("ok") is True, f"bulk 실패: {code} {body}")
        batch_id2 = body.get("batch_id")
        assert_true(batch_id2, "batch_id 없음")

        start2 = fetch_event_by_idem(conn, f"paid_batch:{batch_id2}:start")
        end2 = fetch_event_by_idem(conn, f"paid_batch:{batch_id2}:end")
        assert_true(start2 is not None and end2 is not None, "batch start/end 로그 없음(미래)")
        assert_true(int(start2["actor_id"]) == ACTOR_ID, f"batch start actor_id 불일치(미래): {start2}")
        assert_true(int(end2["actor_id"]) == ACTOR_ID, f"batch end actor_id 불일치(미래): {end2}")

        b = fetch_settlement(conn, b_id)
        assert_true(b.get("status") == "APPROVED", f"미래인데 status 변함(버그): {b}")
        assert_true(b.get("paid_at") in (None, ""), f"미래인데 paid_at 찍힘(버그): {b}")

        paid_evt_b = fetch_event_by_idem(conn, f"settlement:{b_id}:paid")
        assert_true(paid_evt_b is None, f"미래인데 paid 로그 생김(버그): {paid_evt_b}")

        print(f"PASS B ✅ id={b_id}, batch_id={batch_id2}")

        print("\nALL PASS ✅ (actor_id까지 포함해서 고정됨)")
        return 0

    finally:
        conn.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\nTEST FAILED ❌ {e}")
        sys.exit(1)