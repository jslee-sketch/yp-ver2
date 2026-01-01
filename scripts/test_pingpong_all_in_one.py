# scripts/test_pingpong_all_in_one.py
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---- requests가 있으면 사용, 없으면 urllib로 fallback ----
try:
    import requests  # type: ignore
except Exception:
    requests = None  # type: ignore

import urllib.request
import urllib.error


# =========================
# Config
# =========================
DEFAULT_ENDPOINT = "http://127.0.0.1:9000/v3_6/pingpong/ask"
ENDPOINT = os.getenv("PINGPONG_ENDPOINT", DEFAULT_ENDPOINT)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTDIR = Path(os.getenv("PINGPONG_OUTDIR", str(PROJECT_ROOT / "scripts" / "out")))

# (선택) sqlite DB 경로 넣으면 “자동 DB 검증”까지 수행
# 예) PowerShell:
#   $env:PINGPONG_DB_PATH="C:\Users\user\Desktop\yp-ver2\app\ypver2.db"
DB_PATH = os.getenv("PINGPONG_DB_PATH", "").strip()

TIMEOUT_SEC = int(os.getenv("PINGPONG_TIMEOUT_SEC", "30"))
RETRY = int(os.getenv("PINGPONG_RETRY", "0"))  # 0이면 재시도 없음
SLEEP_BETWEEN_RETRY_SEC = float(os.getenv("PINGPONG_RETRY_SLEEP", "0.5"))


# =========================
# Helpers
# =========================
def now_ms() -> int:
    return int(time.time() * 1000)


def ensure_outdir() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)


def dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_json_loads(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return None


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


def base_body(question: str, *, mode: str = "read_only") -> Dict[str, Any]:
    return {
        "user_id": 1,
        "role": "buyer",
        "screen": "REFUND_FLOW",
        "context": {"deal_id": None, "reservation_id": None, "offer_id": None},
        "question": question,
        "locale": "ko",
        "mode": mode,
        "max_chat_messages": 10,
    }


@dataclass
class Case:
    name: str
    payload: Any
    expect_status: int = 200
    kind: str = "positive"  # "positive" or "negative"


def _extract_used_keys(resp_json: Any) -> List[str]:
    """
    used_policy_keys 우선순위:
    1) resp.debug.used_policy_keys
    2) resp.used_policies[].policy_key
    """
    out: List[str] = []
    if isinstance(resp_json, dict):
        dbg = resp_json.get("debug")
        if isinstance(dbg, dict) and isinstance(dbg.get("used_policy_keys"), list):
            out = [x for x in dbg.get("used_policy_keys") if isinstance(x, str)]
            if out:
                return out
        ups = resp_json.get("used_policies")
        if isinstance(ups, list):
            for p in ups:
                if isinstance(p, dict) and isinstance(p.get("policy_key"), str):
                    out.append(p["policy_key"])
    return out


def _extract_error_code(resp_json: Any) -> Optional[str]:
    if isinstance(resp_json, dict):
        dbg = resp_json.get("debug")
        if isinstance(dbg, dict) and isinstance(dbg.get("error"), str):
            return dbg.get("error")
    return None


def _extract_answer(resp_json: Any) -> str:
    if isinstance(resp_json, dict) and isinstance(resp_json.get("answer"), str):
        return resp_json["answer"]
    return ""


def _extract_used_policies(resp_json: Any) -> List[Dict[str, Any]]:
    if isinstance(resp_json, dict) and isinstance(resp_json.get("used_policies"), list):
        return [p for p in resp_json["used_policies"] if isinstance(p, dict)]
    return []


def _extract_actions(resp_json: Any) -> List[Dict[str, Any]]:
    if isinstance(resp_json, dict) and isinstance(resp_json.get("actions"), list):
        return [a for a in resp_json["actions"] if isinstance(a, dict)]
    return []


def _validate_positive(resp_json: Any) -> List[str]:
    """
    자동검증(positive):
    - answer 비어있지 않음
    - error_code는 None 이어야 함(또는 없어야 함)
    - used_policy_keys는 최소 1개 이상
    - read_only면 actions는 빈 배열이어야 함
    - used_policies에 policy_key가 있다면 used_keys와 일관성(경고 수준)
    """
    errs: List[str] = []

    if not isinstance(resp_json, dict):
        return ["response is not a JSON object"]

    ans = _extract_answer(resp_json).strip()
    if not ans:
        errs.append("answer is empty")

    err_code = _extract_error_code(resp_json)
    if err_code:
        errs.append(f"error_code is not null: {err_code}")

    used_keys = _extract_used_keys(resp_json)
    if not used_keys:
        errs.append("used_policy_keys is empty (expected >= 1)")

    # read_only이면 actions 비어야 함
    actions = _extract_actions(resp_json)
    if actions:
        errs.append("actions should be empty in read_only mode")

    # used_policies 키와 used_keys의 일관성(used_policies에 있으면 used_keys에도 있어야 함)
    used_policies = _extract_used_policies(resp_json)
    up_keys = [p.get("policy_key") for p in used_policies if isinstance(p.get("policy_key"), str)]
    if up_keys and used_keys:
        missing = [k for k in up_keys if k not in used_keys]
        if missing:
            errs.append(f"warning: used_policies has keys not in used_policy_keys: {missing[:5]}")

    return errs


def _validate_negative(status: int, expect_status: int, resp_json: Any) -> List[str]:
    """
    자동검증(negative):
    - status는 expect_status와 일치
    - FastAPI 에러면 detail 존재(가능하면)
    """
    errs: List[str] = []
    if status != expect_status:
        errs.append(f"status mismatch: got {status}, expected {expect_status}")
        return errs

    if isinstance(resp_json, dict) and ("detail" not in resp_json):
        errs.append("warning: response has no 'detail' field for negative case")
    return errs


def run_case(case: Case) -> Dict[str, Any]:
    t0 = now_ms()
    last_status = 0
    last_text = ""
    last_exc: Optional[str] = None

    attempts = 1 + max(0, RETRY)
    for i in range(attempts):
        try:
            status, text = http_post_json(ENDPOINT, case.payload, timeout=TIMEOUT_SEC)
            last_status, last_text = status, text
            last_exc = None
            break
        except Exception as e:
            last_exc = f"{type(e).__name__}: {e}"
            if i < attempts - 1:
                time.sleep(SLEEP_BETWEEN_RETRY_SEC)

    dt = now_ms() - t0
    data = safe_json_loads(last_text) if last_text else None

    # 검증
    validation_errors: List[str] = []
    if last_exc:
        validation_errors.append(f"http_error: {last_exc}")
    else:
        if case.kind == "positive":
            if last_status != case.expect_status:
                validation_errors.append(f"status mismatch: got {last_status}, expected {case.expect_status}")
            else:
                validation_errors.extend(_validate_positive(data))
        else:
            validation_errors.extend(_validate_negative(last_status, case.expect_status, data))

    ok = (len([e for e in validation_errors if not e.startswith("warning:")]) == 0)
    tag = "OK" if ok else "FAIL"

    # 출력(콘솔)
    print(f"\n=== CASE ({case.kind}): {case.name} ===")
    print(f"[{tag}] status={last_status} in {dt}ms (expect {case.expect_status})")

    if isinstance(data, dict):
        if case.kind == "positive" and last_status == 200:
            ans = _extract_answer(data)
            used = _extract_used_keys(data)
            print("answer:", (ans or "")[:220].replace("\n", " "))
            print("used:", used)
        else:
            detail = data.get("detail") if isinstance(data, dict) else None
            if detail is not None:
                print("detail:", detail)

    # 결과 저장
    result = {
        "case": case.name,
        "kind": case.kind,
        "endpoint": ENDPOINT,
        "expect_status": case.expect_status,
        "status": last_status,
        "latency_ms": dt,
        "validation_errors": validation_errors,
        "raw_text": (last_text[:4000] if last_text else None),
        "json": data,
    }
    dump_json(OUTDIR / f"{case.kind}_{case.name}.json", result)
    return result


# =========================
# Optional: DB verification (ID-based)
# =========================
def _db_connect(db_path: Path):
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _db_get_max_id(conn) -> int:
    row = conn.execute("SELECT COALESCE(MAX(id), 0) AS mx FROM pingpong_logs").fetchone()
    return int(row["mx"] if row else 0)


def db_verify(
    summary: Dict[str, Any],
    positive_ok_cases: List[Dict[str, Any]],
    *,
    baseline_max_id: int,
    expected_screen: str = "REFUND_FLOW",
) -> Dict[str, Any]:
    """
    DB_PATH가 있으면:
    - policy_declarations에 used_key가 존재하는지 + is_active=1 인지 검증
    - pingpong_logs를 "id > baseline_max_id" 기준으로 읽어:
        * positive OK 건수만큼 새 로그가 생성되었는지
        * used_policy_keys_json이 비지 않았는지
        * error_code가 비지 않았는지
        * screen이 expected_screen인지
    """
    if not DB_PATH:
        return {"enabled": False}

    db_path = Path(DB_PATH)
    if not db_path.exists():
        return {"enabled": True, "ok": False, "error": f"DB file not found: {DB_PATH}"}

    out: Dict[str, Any] = {
        "enabled": True,
        "db_path": str(db_path),
        "baseline_max_id": int(baseline_max_id),
    }
    errors: List[str] = []

    try:
        conn = _db_connect(db_path)

        # (1) used_key -> policy_declarations 존재/active 확인
        all_used: List[str] = []
        for r in positive_ok_cases:
            j = r.get("json")
            if isinstance(j, dict):
                all_used.extend(_extract_used_keys(j))
        all_used = sorted(list({k for k in all_used if isinstance(k, str) and k}))

        missing: List[str] = []
        inactive: List[str] = []

        for k in all_used:
            row = conn.execute(
                "SELECT is_active FROM policy_declarations WHERE policy_key = ? LIMIT 1",
                (k,),
            ).fetchone()
            if not row:
                missing.append(k)
            else:
                is_active = row["is_active"]
                if str(is_active) not in ("1", "True", "true"):
                    inactive.append(k)

        if missing:
            errors.append(f"policy_key not found in policy_declarations: {missing[:10]}")
        if inactive:
            errors.append(f"policy_key found but not active: {inactive[:10]}")

        out["used_keys_checked"] = len(all_used)
        out["missing_keys_count"] = len(missing)
        out["inactive_keys_count"] = len(inactive)

        # (2) logs 검증: id 기준(타임존 이슈 없음)
        rows = conn.execute(
            """
            SELECT id, screen, mode, error_code, used_policy_keys_json, created_at
            FROM pingpong_logs
            WHERE id > ?
            ORDER BY id ASC
            """,
            (int(baseline_max_id),),
        ).fetchall()

        out["new_logs_count"] = len(rows)

        need = len(positive_ok_cases)
        out["expected_min_new_logs"] = need

        if len(rows) < need:
            errors.append(f"new pingpong_logs too small: got {len(rows)}, need >= {need}")

        # screen/mode/error/empty_keys 체크
        empty_cnt = 0
        err_cnt = 0
        bad_screen_cnt = 0

        for r in rows:
            if (r["screen"] or "") != expected_screen:
                bad_screen_cnt += 1
            if (r["used_policy_keys_json"] or "") == "[]":
                empty_cnt += 1
            if (r["error_code"] or "").strip() != "":
                err_cnt += 1

        out["new_empty_used_keys_count"] = empty_cnt
        out["new_error_code_count"] = err_cnt
        out["new_bad_screen_count"] = bad_screen_cnt
        out["expected_screen"] = expected_screen

        if bad_screen_cnt > 0:
            errors.append(f"new logs have screen mismatch: {bad_screen_cnt} (expected {expected_screen})")
        if empty_cnt > 0:
            errors.append(f"new logs have empty used_policy_keys_json: {empty_cnt}")
        if err_cnt > 0:
            errors.append(f"new logs have non-empty error_code: {err_cnt}")

        conn.close()

    except Exception as e:
        return {"enabled": True, "ok": False, "error": f"db verify exception: {type(e).__name__}: {e}"}

    out["errors"] = errors
    out["ok"] = (len(errors) == 0)
    return out


# =========================
# Cases
# =========================
def build_cases() -> List[Case]:
    positive: List[Case] = [
        Case(
            name="refund_fee_buyer_before_shipping",
            kind="positive",
            payload=base_body("정산 전/발송 전 바이어 귀책 환불이면 수수료는 누가 부담해?"),
            expect_status=200,
        ),
        Case(
            name="refund_points_partial",
            kind="positive",
            payload=base_body("부분 환불하면 포인트는 어떻게 돼?"),
            expect_status=200,
        ),
        Case(
            name="refund_after_shipping_buyer_fault",
            kind="positive",
            payload=base_body("발송 후 바이어 귀책이면 환불 가능해?"),
            expect_status=200,
        ),
        Case(
            name="refund_fee_seller_before_shipping",
            kind="positive",
            payload=base_body("정산 전/발송 전 셀러 귀책 환불이면 수수료는 누가 부담해?"),
            expect_status=200,
        ),
        Case(
            name="refund_shipping_fee_partial",
            kind="positive",
            payload=base_body("부분환불이면 배송비는 환불돼?"),
            expect_status=200,
        ),
    ]

    negative: List[Case] = [
        Case(
            name="fail_empty_question",
            kind="negative",
            payload=base_body(""),
            expect_status=400,
        ),
        Case(
            name="fail_whitespace_question",
            kind="negative",
            payload=base_body("   "),
            expect_status=400,
        ),
        Case(
            name="fail_missing_question_field",
            kind="negative",
            payload={k: v for k, v in base_body("x").items() if k != "question"},
            expect_status=422,
        ),
        Case(
            name="fail_bad_context_type",
            kind="negative",
            payload={**base_body("환불 가능해?"), "context": "oops"},
            expect_status=422,
        ),
    ]

    return positive + negative


# =========================
# Main
# =========================
def main() -> int:
    ensure_outdir()

    cases = build_cases()
    pos = [c for c in cases if c.kind == "positive"]
    neg = [c for c in cases if c.kind == "negative"]

    print(f"Endpoint: {ENDPOINT}")
    print(f"OutDir:   {OUTDIR}")

    baseline_max_id = 0
    if DB_PATH:
        print(f"DB:       {DB_PATH} (db verification enabled)")
        try:
            db_path = Path(DB_PATH)
            if db_path.exists():
                conn0 = _db_connect(db_path)
                baseline_max_id = _db_get_max_id(conn0)
                conn0.close()
            else:
                print("DB:       (enabled but file not found) - will fail in verification")
        except Exception as e:
            print(f"DB:       (enabled but baseline read failed: {type(e).__name__}: {e})")
    else:
        print("DB:       (disabled)  set PINGPONG_DB_PATH to enable")

    print(f"\nCases (positive): {len(pos)}")
    print(f"Cases (negative): {len(neg)}")

    results: List[Dict[str, Any]] = []
    ok_count = 0

    for c in cases:
        r = run_case(c)
        results.append(r)
        hard_errors = [e for e in r["validation_errors"] if not e.startswith("warning:")]
        if not hard_errors:
            ok_count += 1

    total = len(cases)

    summary: Dict[str, Any] = {
        "endpoint": ENDPOINT,
        "outdir": str(OUTDIR),
        "total": total,
        "ok": ok_count,
        "fail": total - ok_count,
        "timestamp_ms": now_ms(),
        "db_path": (DB_PATH or None),
        "db_baseline_max_id": int(baseline_max_id),
        "cases": [
            {
                "name": r["case"],
                "kind": r["kind"],
                "status": r["status"],
                "latency_ms": r["latency_ms"],
                "ok": (len([e for e in r["validation_errors"] if not e.startswith("warning:")]) == 0),
                "validation_errors": r["validation_errors"],
            }
            for r in results
        ],
    }

    # DB 자동검증(옵션) - id 기반(타임존 이슈 없음)
    positive_ok_cases = [
        r for r in results
        if r.get("kind") == "positive"
        and r.get("status") == 200
        and len([e for e in r.get("validation_errors", []) if not str(e).startswith("warning:")]) == 0
    ]

    db_result = db_verify(
        summary,
        positive_ok_cases,
        baseline_max_id=baseline_max_id,
        expected_screen="REFUND_FLOW",
    )
    summary["db_verify"] = db_result

    dump_json(OUTDIR / "summary.json", summary)

    print(f"\nDone. OK {ok_count}/{total}")
    if db_result.get("enabled"):
        print(f"DB verify: {'OK' if db_result.get('ok') else 'FAIL'}")
        if not db_result.get("ok"):
            print("DB verify errors:", db_result.get("errors") or db_result.get("error"))

    # 하나라도 실패하면 exit 1
    all_ok = (ok_count == total) and (not db_result.get("enabled") or db_result.get("ok") is True)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())