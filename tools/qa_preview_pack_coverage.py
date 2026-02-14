# tools/qa_preview_pack_coverage.py
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, List

import requests

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

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:9000")
    ap.add_argument("--user_id", type=int, default=1)
    ap.add_argument("--role", default="BUYER")
    ap.add_argument("--reservation_id", type=int, default=403)
    ap.add_argument("--offer_id", type=int, default=1)
    ap.add_argument("--deal_id", type=int, default=1)
    ap.add_argument("--buyer_id", type=int, default=1)
    args = ap.parse_args()

    base = args.base.rstrip("/")
    q = f"user_id={args.user_id}&role={args.role}"

    targets = [
        ("reservation", f"{base}/preview/reservation/{args.reservation_id}?{q}"),
        ("offer", f"{base}/preview/offer/{args.offer_id}?{q}"),
        ("deal", f"{base}/preview/deal/{args.deal_id}?{q}"),
        ("buyer", f"{base}/preview/buyer/{args.buyer_id}?{q}"),
        ("me", f"{base}/preview/me?{q}"),
    ]

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
