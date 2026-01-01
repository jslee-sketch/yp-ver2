# scripts/create_offer_sqlite.py
# 목적: SQLite DB에서 buyers/sellers/deals를 필요한 만큼 자동 생성하고 offers를 생성한다.
# 특징: PRAGMA table_info / foreign_key_list 로 NOT NULL & FK 요구사항을 자동으로 맞춤.
#
# 사용 예)
#   python scripts/create_offer_sqlite.py --db "C:\Users\user\Desktop\yp-ver2\app\ypver2.db" --price 100000 --total-available 1000 --shipping-mode PER_RESERVATION --per-reservation 10001
#   python scripts/create_offer_sqlite.py --shipping-mode PER_QTY --per-qty 5000
#
# DB 경로를 안 주면 DATABASE_URL에서 sqlite 파일 경로를 파싱한다.

from __future__ import annotations

import argparse
import os
import re
import sqlite3
from datetime import datetime


def now_str() -> str:
    # sqlite datetime('now','localtime') 대신 파이썬에서 찍기 (ISO-ish)
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_sqlite_path(db: str | None) -> str:
    if db:
        return db

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise SystemExit("ERROR: --db 를 주거나 DATABASE_URL 환경변수를 설정해야 합니다.")

    # 예: sqlite:///C:\path\to\db.sqlite  또는 sqlite:////absolute/unix/path
    m = re.match(r"^sqlite:\/\/\/(.*)$", url)
    if not m:
        raise SystemExit(f"ERROR: DATABASE_URL이 sqlite:///... 형태가 아닙니다: {url}")

    path = m.group(1)
    # Windows 백슬래시 포함 경로 그대로 사용
    return path


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1;", (table,)
    )
    return cur.fetchone() is not None


def pragma_table_info(conn: sqlite3.Connection, table: str):
    # (cid, name, type, notnull, dflt_value, pk)
    return conn.execute(f"PRAGMA table_info({table});").fetchall()


def pragma_foreign_keys(conn: sqlite3.Connection, table: str):
    # (id, seq, table, from, to, on_update, on_delete, match)
    return conn.execute(f"PRAGMA foreign_key_list({table});").fetchall()


def guess_value(col_type: str, col_name: str):
    t = (col_type or "").upper()

    # created_at, updated_at, deadline_at 등
    if "DATE" in t or "TIME" in t or col_name.lower().endswith("_at"):
        return now_str()

    if "INT" in t:
        # boolean도 INT로 올 수 있음
        if col_name.lower().startswith("is_") or col_name.lower().endswith("_flag"):
            return 1
        return 1
    if "CHAR" in t or "TEXT" in t or "CLOB" in t or "VARCHAR" in t:
        return f"DUMMY_{col_name}_{now_str()}"
    if "REAL" in t or "FLOA" in t or "DOUB" in t:
        return 0.0

    # 타입 미상: 문자열로
    return f"DUMMY_{col_name}_{now_str()}"


def get_required_columns(conn: sqlite3.Connection, table: str):
    """
    NOT NULL & default 없음 & pk 아님 => 반드시 값을 넣어야 하는 컬럼 후보
    """
    info = pragma_table_info(conn, table)
    required = []
    for _cid, name, col_type, notnull, dflt, pk in info:
        if pk == 1:
            continue
        if notnull == 1 and (dflt is None):
            required.append((name, col_type))
    return required


def get_primary_key_name(conn: sqlite3.Connection, table: str) -> str:
    info = pragma_table_info(conn, table)
    # pk=1 인 컬럼 찾아서 리턴, 없으면 id 가정
    for _cid, name, _type, _notnull, _dflt, pk in info:
        if pk == 1:
            return name
    return "id"


def find_any_row_id(conn: sqlite3.Connection, table: str) -> int | None:
    pk = get_primary_key_name(conn, table)
    cur = conn.execute(f"SELECT {pk} FROM {table} ORDER BY {pk} ASC LIMIT 1;")
    row = cur.fetchone()
    return int(row[0]) if row else None


def ensure_row(conn: sqlite3.Connection, table: str) -> int:
    """
    table에 최소 1 row 보장. 이미 있으면 첫 row id 반환.
    없으면 스키마 보고 더미로 insert 시도.
    """
    if not table_exists(conn, table):
        raise RuntimeError(f"table not found: {table}")

    existing = find_any_row_id(conn, table)
    if existing is not None:
        return existing

    # FK 요구사항 먼저 채우기: required FK 컬럼이 있으면 참조 테이블 row를 만들어 id를 넣는다.
    required_cols = dict(get_required_columns(conn, table))  # name -> type
    fk_list = pragma_foreign_keys(conn, table)
    fk_from_to = {}  # from_col -> (ref_table, ref_to_col)
    for _id, _seq, ref_table, from_col, to_col, *_rest in fk_list:
        fk_from_to[from_col] = (ref_table, to_col)

    values = {}
    for col_name, col_type in required_cols.items():
        if col_name in fk_from_to:
            ref_table, _to_col = fk_from_to[col_name]
            # 참조 테이블도 최소 1 row 확보
            ref_id = ensure_row(conn, ref_table)
            values[col_name] = ref_id
        else:
            values[col_name] = guess_value(col_type, col_name)

    cols = ", ".join(values.keys())
    qs = ", ".join(["?"] * len(values))
    sql = f"INSERT INTO {table} ({cols}) VALUES ({qs});"
    cur = conn.execute(sql, tuple(values.values()))
    conn.commit()

    pk_name = get_primary_key_name(conn, table)
    # lastrowid가 pk와 다를 수도 있어 select로 확인
    new_id = cur.lastrowid
    if new_id is None:
        new_id = find_any_row_id(conn, table)
        if new_id is None:
            raise RuntimeError(f"failed to create row in {table}")
    return int(new_id)


def create_offer(
    conn: sqlite3.Connection,
    deal_id: int | None,
    seller_id: int | None,
    price: float,
    total_available_qty: int,
    delivery_days: int | None,
    comment: str | None,
    shipping_mode: str,
    shipping_fee_per_reservation: int,
    shipping_fee_per_qty: int,
    is_active: int,
    is_confirmed: int | None,
    deadline_at: str | None,
):
    if not table_exists(conn, "offers"):
        raise SystemExit("ERROR: offers 테이블이 없습니다.")

    # deal/seller 확보
    if deal_id is None:
        if table_exists(conn, "deals"):
            deal_id = ensure_row(conn, "deals")
        else:
            raise SystemExit("ERROR: deals 테이블이 없어서 offer 생성에 필요한 deal_id를 만들 수 없습니다. --deal-id로 직접 주세요.")

    if seller_id is None:
        if table_exists(conn, "sellers"):
            seller_id = ensure_row(conn, "sellers")
        else:
            raise SystemExit("ERROR: sellers 테이블이 없어서 offer 생성에 필요한 seller_id를 만들 수 없습니다. --seller-id로 직접 주세요.")

    # offers 스키마 보고 존재하는 컬럼만 채우기 (프로젝트마다 컬럼명이 다를 가능성 방어)
    info = pragma_table_info(conn, "offers")
    offer_cols = {name for _cid, name, *_ in info}

    data = {}

    def put(k, v):
        if k in offer_cols and v is not None:
            data[k] = v

    put("deal_id", deal_id)
    put("seller_id", seller_id)
    put("price", float(price))
    put("total_available_qty", int(total_available_qty))
    put("delivery_days", int(delivery_days) if delivery_days is not None else None)
    put("comment", comment or f"[AUTO OFFER {now_str()}]")
    put("sold_qty", 0)
    put("reserved_qty", 0)
    put("shipping_mode", shipping_mode)
    put("shipping_fee_per_reservation", int(shipping_fee_per_reservation))
    put("shipping_fee_per_qty", int(shipping_fee_per_qty))
    put("is_active", int(is_active))
    put("created_at", now_str())
    put("deadline_at", deadline_at)
    put("is_confirmed", int(is_confirmed) if is_confirmed is not None else None)

    # NOT NULL & default 없음 컬럼이 있는데 우리가 안 넣었으면, 자동으로 더미 채우기
    required = get_required_columns(conn, "offers")
    for col_name, col_type in required:
        if col_name not in data:
            # FK면 참조 row 만들어 넣기
            fk_map = {f[3]: f[2] for f in pragma_foreign_keys(conn, "offers")}  # from_col -> ref_table
            if col_name in fk_map and table_exists(conn, fk_map[col_name]):
                data[col_name] = ensure_row(conn, fk_map[col_name])
            else:
                data[col_name] = guess_value(col_type, col_name)

    cols = ", ".join(data.keys())
    qs = ", ".join(["?"] * len(data))
    sql = f"INSERT INTO offers ({cols}) VALUES ({qs});"

    cur = conn.execute(sql, tuple(data.values()))
    conn.commit()

    offer_id = int(cur.lastrowid)
    row = conn.execute(
        "SELECT id, deal_id, seller_id, price, total_available_qty, shipping_mode, shipping_fee_per_reservation, shipping_fee_per_qty, comment, created_at "
        "FROM offers WHERE id=?;",
        (offer_id,),
    ).fetchone()

    print("\n=== CREATED OFFER ===")
    print(f"offer_id={offer_id}")
    print(row)
    print("====================\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None, help="sqlite db file path. If omitted, uses DATABASE_URL=sqlite:///...")
    ap.add_argument("--deal-id", type=int, default=None)
    ap.add_argument("--seller-id", type=int, default=None)

    ap.add_argument("--price", type=float, default=100000.0)
    ap.add_argument("--total-available", type=int, default=1000)
    ap.add_argument("--delivery-days", type=int, default=3)
    ap.add_argument("--comment", default=None)

    ap.add_argument("--shipping-mode", choices=["PER_RESERVATION", "PER_QTY"], default="PER_RESERVATION")
    ap.add_argument("--per-reservation", type=int, default=10001)
    ap.add_argument("--per-qty", type=int, default=0)

    ap.add_argument("--is-active", type=int, default=1)
    ap.add_argument("--is-confirmed", type=int, default=None)
    ap.add_argument("--deadline-at", default=None, help="e.g. '2025-12-31 23:59:59'")

    args = ap.parse_args()

    db_path = parse_sqlite_path(args.db)
    print(f"DB: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    # shipping_mode에 맞춰 fee 정리
    if args.shipping_mode == "PER_RESERVATION":
        per_res = args.per_reservation
        per_qty = 0
    else:
        per_res = 0
        per_qty = args.per_qty if args.per_qty is not None else 5000

    create_offer(
        conn=conn,
        deal_id=args.deal_id,
        seller_id=args.seller_id,
        price=args.price,
        total_available_qty=args.total_available,
        delivery_days=args.delivery_days,
        comment=args.comment,
        shipping_mode=args.shipping_mode,
        shipping_fee_per_reservation=per_res,
        shipping_fee_per_qty=per_qty,
        is_active=args.is_active,
        is_confirmed=args.is_confirmed,
        deadline_at=args.deadline_at,
    )

    conn.close()


if __name__ == "__main__":
    main()