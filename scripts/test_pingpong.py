# scripts/test_pingpong.py
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---- requests가 있으면 사용, 없으면 urllib로 fallback ----
try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore

import urllib.request
import urllib.error


DEFAULT_ENDPOINT = "http://127.0.0.1:9000/v3_6/pingpong/ask"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTDIR = Path(os.getenv("PINGPONG_OUTDIR", str(PROJECT_ROOT / "scripts" / "out")))

ENDPOINT = os.getenv("PINGPONG_ENDPOINT", DEFAULT_ENDPOINT)


def now_ms() -> int:
    return int(time.time() * 1000)


def ensure_outdir() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)


def dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def http_post_json(url: str, payload: Any, timeout: int = 30) -> Tuple[int, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}

    if requests is not None:
        r = requests.post(url, data=body, headers=headers, timeout=timeout)
        return r.status_code, r.text

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                text = raw.decode("utf-8")
            except Exception:
                text = raw.decode("latin-1", errors="replace")
            return resp.getcode(), text
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("latin-1", errors="replace")
        return e.code, text


def safe_json_loads(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return None


def base_body(question: str) -> Dict[str, Any]:
    return {
        "user_id": 1,
        "role": "buyer",
        "screen": "REFUND_FLOW",
        "context": {"deal_id": None, "reservation_id": None, "offer_id": None},
        "question": question,
        "locale": "ko",
        "mode": "read_only",
        "max_chat_messages": 10,
    }


def run_case(name: str, payload: Any, expect_status: int = 200) -> bool:
    t0 = now_ms()
    status, text = http_post_json(ENDPOINT, payload, timeout=30)
    dt = now_ms() - t0

    ok = (status == expect_status)
    tag = "OK" if ok else "FAIL"

    print(f"\n=== CASE: {name} ===")
    print(f"[{tag}] status={status} in {dt}ms (expect {expect_status})")

    data = safe_json_loads(text)
    out = {
        "case": name,
        "endpoint": ENDPOINT,
        "expect_status": expect_status,
        "status": status,
        "latency_ms": dt,
        "raw_text": text[:2000],  # 너무 길면 잘라 저장
        "json": data,
    }
    dump_json(OUTDIR / f"{name}.json", out)

    # 성공 케이스면 핵심 필드만 콘솔에 간단히 표시
    if status == 200 and isinstance(data, dict):
        ans = data.get("answer")
        used = data.get("debug", {}).get("used_policy_keys") if isinstance(data.get("debug"), dict) else None
        if not used:
            used = [p.get("policy_key") for p in (data.get("used_policies") or []) if isinstance(p, dict)]
        print("answer:", (ans or "")[:200])
        print("used:", used)

    return ok


def main() -> int:
    ensure_outdir()

    print(f"Endpoint: {ENDPOINT}")
    print(f"OutDir:   {OUTDIR}")

    # -------------------------
    # (A) 정상 케이스(기존 3개 + 엣지 2개)
    # -------------------------
    positive_cases: List[Tuple[str, Any]] = [
        ("refund_fee_buyer_before_shipping", base_body("정산 전/발송 전 바이어 귀책 환불이면 수수료는 누가 부담해?")),
        ("refund_points_partial", base_body("부분 환불하면 포인트는 어떻게 돼?")),
        ("refund_after_shipping_buyer_fault", base_body("발송 후 바이어 귀책이면 환불 가능해?")),
        # ✅ 엣지1: 셀러 귀책(발송 전) 수수료
        ("refund_fee_seller_before_shipping", base_body("정산 전/발송 전 셀러 귀책 환불이면 수수료는 누가 부담해?")),
        # ✅ 엣지2: 부분환불 + 배송비
        ("refund_shipping_fee_partial", base_body("부분환불이면 배송비는 환불돼?")),
    ]

    # -------------------------
    # (B) 실패 테스트(중요: 서버가 “예상대로” 거절하는지)
    # -------------------------
    negative_cases: List[Tuple[str, Any, int]] = [
        # question이 비어있으면 400
        ("fail_empty_question", base_body(""), 400),
        ("fail_whitespace_question", base_body("   "), 400),
        # question 필드 자체가 없으면 pydantic validation으로 422
        ("fail_missing_question_field", {k: v for k, v in base_body("x").items() if k != "question"}, 422),
        # context 타입이 틀리면 422
        ("fail_bad_context_type", {**base_body("환불 가능해?"), "context": "oops"}, 422),
    ]

    ok_count = 0
    total = 0

    print(f"\nCases (positive): {len(positive_cases)}")
    for name, payload in positive_cases:
        total += 1
        if run_case(name, payload, expect_status=200):
            ok_count += 1

    print(f"\nCases (negative): {len(negative_cases)}")
    for name, payload, expect_status in negative_cases:
        total += 1
        if run_case(name, payload, expect_status=expect_status):
            ok_count += 1

    print(f"\nDone. OK {ok_count}/{total}")
    # 하나라도 실패하면 exit 1
    return 0 if ok_count == total else 1


if __name__ == "__main__":
    raise SystemExit(main())