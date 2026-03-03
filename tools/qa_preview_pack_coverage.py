from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

import requests
import sqlite3
from pathlib import Path


def get(url: str) -> Dict[str, Any]:
    r = requests.get(url, timeout=5)
    try:
        return r.json()
    except Exception:
        return {"ok": False, "reason_code": "UPSTREAM_FAIL", "error": r.text[:200]}


def has_times(obj: Dict[str, Any]) -> bool:
    t = obj.get("times")
    if not isinstance(t, dict):
        return False
    if "as_of" not in t or "entity" not in t or "events" not in t:
        return False
    return True


def _find_sqlite_db_path() -> Path | None:
    candidates = [
        Path("app/ypver2.db"),
        Path("ypver2.db"),
        Path("app.db"),
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def _get_latest_id_sqlite(db_path: Path, table_candidates: List[str]) -> int | None:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        for t in table_candidates:
            try:
                cur.execute(f"SELECT id FROM {t} ORDER BY id DESC LIMIT 1;")
                row = cur.fetchone()
                if row and row[0] is not None:
                    return int(row[0])
            except Exception:
                continue
        return None
    finally:
        conn.close()


def _resolve_reservation_id(args_reservation_id: int) -> int | None:
    # 1) CLI로 명시하면 그걸 사용
    if args_reservation_id and int(args_reservation_id) > 0:
        return int(args_reservation_id)

    # 2) 아니면 DB에서 최신값 자동탐색
    db_path = _find_sqlite_db_path()
    if not db_path:
        return None

    return _get_latest_id_sqlite(db_path, ["reservations", "reservation", "Reservation"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:9000")
    ap.add_argument("--user_id", type=int, default=1)
    ap.add_argument("--role", default="BUYER")

    # ✅ 기본값을 403 같은 “가짜 고정값”으로 두면 항상 깨짐
    # 0이면 자동탐색, >0이면 그 값을 그대로 사용
    ap.add_argument("--reservation_id", type=int, default=0)

    # (참고) 너 fullflow 기준 offer_id가 보통 2였지? 필요하면 2로 바꿔도 됨
    ap.add_argument("--offer_id", type=int, default=2)
    ap.add_argument("--deal_id", type=int, default=1)
    ap.add_argument("--buyer_id", type=int, default=1)
    args = ap.parse_args()

    base = args.base.rstrip("/")
    q = f"user_id={args.user_id}&role={args.role}"

    reservation_id = _resolve_reservation_id(args.reservation_id)

    targets = [
        ("offer", f"{base}/preview/offer/{args.offer_id}?{q}"),
        ("deal", f"{base}/preview/deal/{args.deal_id}?{q}"),
        ("buyer", f"{base}/preview/buyer/{args.buyer_id}?{q}"),
        ("me", f"{base}/preview/me?{q}"),
    ]

    # ✅ reservation은 있을 때만 검사 (없으면 SKIP)
    if reservation_id is not None:
        targets.insert(0, ("reservation", f"{base}/preview/reservation/{reservation_id}?{q}"))
    else:
        print("reservation: SKIP (no reservation found; pass-through)")

    ok_count = 0
    for name, url in targets:
        data = get(url)
        ok = bool(data.get("ok") is True and has_times(data))
        print(f"{name}: ok={ok} reason={data.get('reason_code')} latency_ms={data.get('latency_ms')}")
        if not ok:
            print(json.dumps(data, ensure_ascii=False, indent=2)[:800])
        ok_count += 1 if ok else 0

    if ok_count != len(targets):
        sys.exit(1)


if __name__ == "__main__":
    main()