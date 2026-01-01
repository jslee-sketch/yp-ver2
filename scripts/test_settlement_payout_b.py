# scripts/test_settlement_payout_b.py
# 실행: python scripts/test_settlement_payout_b.py
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ====== 환경 설정(필요하면 여기만 수정) ======
BASE_URL = "http://127.0.0.1:9000"
DB_PATH = r"app/ypver2.db"
# ==========================================


def http_post(path: str) -> tuple[int, dict]:
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


def http_get(path: str) -> tuple[int, str]:
    url = f"{BASE_URL}{path}"
    req = Request(url, method="GET")
    try:
        with urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"서버 접속 실패: {url} / {e}")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def insert_ready_settlement(conn: sqlite3.Connection, *, block_reason: str | None = None) -> int:
    """
    reservation_settlements 필수 NOT NULL 컬럼 채워서 READY 상태 1건 삽입.
    reservation_id는 UNIQUE 제약이 있을 수 있으므로 매번 고유값 사용.
    """
    cur = conn.cursor()

    # ✅ 유니크 reservation_id 생성: 현재 max(reservation_id)+1 (없으면 990000부터)
    row = cur.execute("SELECT COALESCE(MAX(reservation_id), 990000) + 1 FROM reservation_settlements").fetchone()
    new_reservation_id = int(row[0])

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
            new_reservation_id,
            new_reservation_id,
            new_reservation_id,
            new_reservation_id,
            new_reservation_id,
            1000, 0, 0, 1000,
            block_reason,
        ),
    )
    conn.commit()
    new_id = cur.execute("SELECT last_insert_rowid()").fetchone()[0]
    return int(new_id)


def set_scheduled(conn: sqlite3.Connection, settlement_id: int, when_sqlite_expr: str):
    """
    when_sqlite_expr 예:
      - "'2000-01-01 00:00:00'"
      - "datetime('now', '+1 day')"
      - "datetime('now', '-1 day')"
    """
    conn.execute(
        f"UPDATE reservation_settlements SET scheduled_payout_at = {when_sqlite_expr} WHERE id = ?",
        (settlement_id,),
    )
    conn.commit()


def fetch_row(conn: sqlite3.Connection, settlement_id: int) -> dict:
    row = conn.execute(
        """
        SELECT id, status, approved_at, paid_at, scheduled_payout_at, block_reason, updated_at
        FROM reservation_settlements
        WHERE id = ?
        """,
        (settlement_id,),
    ).fetchone()
    return dict(row) if row else {}


def assert_true(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def main():
    # 0) 서버 살아있는지 확인
    status, _ = http_get("/openapi.json")
    assert_true(status == 200, "서버가 떠있지 않거나 /openapi.json 접근 실패")

    conn = db()

    try:
        print("=== TEST A: scheduled_payout_at 과거면 bulk-mark-paid가 PAID 처리해야 함 ===")
        a_id = insert_ready_settlement(conn, block_reason=None)

        # approve
        code, body = http_post(f"/settlements/{a_id}/approve")
        assert_true(code == 200 and body.get("status") == "APPROVED", f"approve 실패: {code} {body}")

        # scheduled 과거로 당김
        set_scheduled(conn, a_id, "'2000-01-01 00:00:00'")

        # bulk-mark-paid
        code, body = http_post("/settlements/bulk-mark-paid")
        assert_true(code == 200, f"bulk-mark-paid 호출 실패: {code} {body}")

        a = fetch_row(conn, a_id)
        assert_true(a["status"] == "PAID", f"PAID 전환 실패: {a}")
        assert_true(a["paid_at"] is not None and str(a["paid_at"]).strip() != "", f"paid_at 미기록: {a}")
        print(f"PASS A ✅ id={a_id} -> PAID")

        print("\n=== TEST B: scheduled_payout_at 미래면 bulk-mark-paid가 건드리면 안 됨 ===")
        b_id = insert_ready_settlement(conn, block_reason="DISPUTE_PATH")

        # approve
        code, body = http_post(f"/settlements/{b_id}/approve")
        assert_true(code == 200 and body.get("status") == "APPROVED", f"approve 실패: {code} {body}")

        # scheduled 미래로 설정
        set_scheduled(conn, b_id, "datetime('now', '+1 day')")

        # bulk-mark-paid
        code, body = http_post("/settlements/bulk-mark-paid")
        assert_true(code == 200, f"bulk-mark-paid 호출 실패: {code} {body}")

        b = fetch_row(conn, b_id)
        assert_true(b["status"] == "APPROVED", f"미래인데 status 변함(버그): {b}")
        assert_true(b["paid_at"] is None or str(b["paid_at"]).strip() == "", f"미래인데 paid_at 찍힘(버그): {b}")
        print(f"PASS B ✅ id={b_id} -> APPROVED 유지")

        print("\nALL PASS ✅ (Approve + BulkPaid 가드레일까지 고정됨)")
        return 0

    finally:
        conn.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\nTEST FAILED ❌ {e}")
        sys.exit(1)