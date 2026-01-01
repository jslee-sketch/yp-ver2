# scripts/create_reservation_sqlite.py
# 목적: SQLite DB에 reservation을 1개 생성한다.
# - buyers/ offers 존재 보장(offers는 --offer-id로 지정)
# - reservations 스키마의 NOT NULL 컬럼을 PRAGMA로 읽어서 자동 채움
# - amount_shipping / amount_total을 offers.shipping_mode 기준으로 계산해 채움
#
# 사용 예)
#   python scripts/create_reservation_sqlite.py --db "C:\Users\user\Desktop\yp-ver2\app\ypver2.db" --offer-id 4 --buyer-id 2 --qty 3
#   python scripts/create_reservation_sqlite.py --offer-id 4 --qty 3   (buyer 자동 생성/확보)
#
# 주의:
# - 프로젝트마다 reservations의 컬럼이 다를 수 있어 "존재하는 컬럼만" 넣도록 방어함.
# - status enum이 문자열인지 정수인지 프로젝트마다 다를 수 있어 기본값은 'PENDING' 시도.

from __future__ import annotations

import argparse
import os
import re
import sqlite3
from datetime import datetime


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_sqlite_path(db: str | None) -> str:
    if db:
        return db
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("ERROR: --db 를 주거나 DATABASE_URL 환경변수를 설정해야 합니다.")
    m = re.match(r"^sqlite:\/\/\/(.*)$", url)
    if not m:
        raise SystemExit(f"ERROR: DATABASE_URL이 sqlite:///... 형태가 아닙니다: {url}")
    return m.group(1)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;", (table,)
    )
    return cur.fetchone() is not None


def pragma_table_info(conn: sqlite3.Connection, table: str):
    return conn.execute(f"PRAGMA table_info({table});").fetchall()


def pragma_foreign_keys(conn: sqlite3.Connection, table: str):
    return conn.execute(f"PRAGMA foreign_key_list({table});").fetchall()


def get_primary_key_name(conn: sqlite3.Connection, table: str) -> str:
    info = pragma_table_info(conn, table)
    for _cid, name, _type, _notnull, _dflt, pk in info:
        if pk == 1:
            return name
    return "id"


def find_any_row_id(conn: sqlite3.Connection, table: str) -> int | None:
    pk = get_primary_key_name(conn, table)
    cur = conn.execute(f"SELECT {pk} FROM {table} ORDER BY {pk} ASC LIMIT 1;")
    row = cur.fetchone()
    return int(row[0]) if row else None


def guess_value(col_type: str, col_name: str):
    t = (col_type or "").upper()
    if "DATE" in t or "TIME" in t or col_name.lower().endswith("_at"):
        return now_str()
    if "INT" in t:
        if col_name.lower().startswith("is_") or col_name.lower().endswith("_flag"):
            return 1
        return 0
    if "REAL" in t or "FLOA" in t or "DOUB" in t:
        return 0.0
    return f"DUMMY_{col_name}_{now_str()}"


def get_required_columns(conn: sqlite3.Connection, table: str):
    info = pragma_table_info(conn, table)
    required = []
    for _cid, name, col_type, notnull, dflt, pk in info:
        if pk == 1:
            continue
        if notnull == 1 and (dflt is None):
            required.append((name, col_type))
    return required


def ensure_row(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(conn, table):
        raise RuntimeError(f"table not found: {table}")

    existing = find_any_row_id(conn, table)
    if existing is not None:
        return existing

    required_cols = dict(get_required_columns(conn, table))  # name -> type
    fk_list = pragma_foreign_keys(conn, table)
    fk_from_to = {}
    for _id, _seq, ref_table, from_col, to_col, *_rest in fk_list:
        fk_from_to[from_col] = (ref_table, to_col)

    values = {}
    for col_name, col_type in required_cols.items():
        if col_name in fk_from_to:
            ref_table, _to_col = fk_from_to[col_name]
            ref_id = ensure_row(conn, ref_table)
            values[col_name] = ref_id
        else:
            values[col_name] = guess_value(col_type, col_name)

    cols = ", ".join(values.keys())
    qs = ", ".join(["?"] * len(values))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({qs});"
    cur = conn.execute(sql, tuple(values.values()))
    conn.commit()

    new_id = cur.lastrowid
    if new_id is None:
        new_id = find_any_row_id(conn, table)
        if new_id is None:
            raise RuntimeError(f"failed to create row in {table}")
    return int(new_id)


def read_offer(conn: sqlite3.Connection, offer_id: int):
    row = conn.execute(
        "SELECT id, price, shipping_mode, shipping_fee_per_reservation, shipping_fee_per_qty "
        "FROM offers WHERE id=?;",
        (offer_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"ERROR: offer not found: {offer_id}")
    return {
        "id": int(row[0]),
        "price": float(row[1]),
        "shipping_mode": row[2],
        "per_reservation": int(row[3]),
        "per_qty": int(row[4]),
    }


def compute_amounts(offer: dict, qty: int):
    item_total = int(round(offer["price"] * qty))
    if offer["shipping_mode"] == "PER_QTY":
        shipping = offer["per_qty"] * qty
    else:
        shipping = offer["per_reservation"]
    total = item_total + shipping
    return shipping, total


def create_reservation(
    conn: sqlite3.Connection,
    offer_id: int,
    buyer_id: int | None,
    qty: int,
    status: str,
):
    if not table_exists(conn, "reservations"):
        raise SystemExit("ERROR: reservations 테이블이 없습니다.")

    if buyer_id is None:
        if table_exists(conn, "buyers"):
            buyer_id = ensure_row(conn, "buyers")
        else:
            raise SystemExit("ERROR: buyers 테이블이 없어서 buyer_id를 만들 수 없습니다. --buyer-id로 직접 주세요.")

    offer = read_offer(conn, offer_id)
    shipping, total = compute_amounts(offer, qty)

    info = pragma_table_info(conn, "reservations")
    res_cols = {name for _cid, name, *_ in info}

    data = {}

    def put(k, v):
        if k in res_cols and v is not None:
            data[k] = v

    # 핵심 필드
    put("offer_id", offer_id)
    put("buyer_id", buyer_id)
    put("qty", qty)
    put("amount_shipping", shipping)
    put("amount_total", total)
    put("created_at", now_str())

    # status는 프로젝트마다 enum/문자열/정수일 수 있어:
    # - 문자열 컬럼이면 그대로 들어감
    # - INT면 실패할 수 있으니, 실패 시 자동 재시도(0) 로 fallback
    put("status", status)

    # NOT NULL 요구 컬럼들 자동 채움
    required = get_required_columns(conn, "reservations")
    fk_map = {f[3]: f[2] for f in pragma_foreign_keys(conn, "reservations")}  # from_col -> ref_table
    for col_name, col_type in required:
        if col_name in data:
            continue
        if col_name in fk_map and table_exists(conn, fk_map[col_name]):
            data[col_name] = ensure_row(conn, fk_map[col_name])
        else:
            # status/created_at 같은 건 우리가 이미 넣으려 했는데 컬럼명이 다를 수 있음
            data[col_name] = guess_value(col_type, col_name)

    cols = ", ".join(data.keys())
    qs = ", ".join(["?"] * len(data))
    sql = f"INSERT INTO reservations ({cols}) VALUES ({qs});"

    try:
        cur = conn.execute(sql, tuple(data.values()))
        conn.commit()
    except sqlite3.IntegrityError as e:
        # status 타입 불일치 같은 케이스 구제
        if "status" in data:
            # status를 숫자 0으로 바꿔 재시도
            data["status"] = 0
            cols = ", ".join(data.keys())
            qs = ", ".join(["?"] * len(data))
            sql = f"INSERT INTO reservations ({cols}) VALUES ({qs});"
            cur = conn.execute(sql, tuple(data.values()))
            conn.commit()
        else:
            raise

    reservation_id = int(cur.lastrowid)
    row = conn.execute(
        "SELECT id, offer_id, buyer_id, qty, amount_shipping, amount_total, status, created_at "
        "FROM reservations WHERE id=?;",
        (reservation_id,),
    ).fetchone()

    print("\n=== CREATED RESERVATION ===")
    print(f"reservation_id={reservation_id}")
    print("offer:", offer)
    print("computed:", {"qty": qty, "amount_shipping": shipping, "amount_total": total})
    print("row:", row)
    print("==========================\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--offer-id", type=int, required=True)
    ap.add_argument("--buyer-id", type=int, default=None)
    ap.add_argument("--qty", type=int, default=3)
    ap.add_argument("--status", default="PENDING")
    args = ap.parse_args()

    db_path = parse_sqlite_path(args.db)
    print(f"DB: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    create_reservation(
        conn=conn,
        offer_id=args.offer_id,
        buyer_id=args.buyer_id,
        qty=args.qty,
        status=args.status,
    )

    conn.close()


if __name__ == "__main__":
    main()