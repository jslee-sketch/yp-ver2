#!/usr/bin/env python3
"""Collect evidence: API tests + DB queries for all endpoints."""
import urllib.request
import urllib.parse
import json
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://web-production-defb.up.railway.app"
SCREENSHOTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def login():
    data = urllib.parse.urlencode({
        "username": "admin@yeokping.com",
        "password": "admin1234!"
    }).encode()
    req = urllib.request.Request(f"{BASE}/auth/login", data=data, method="POST")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())["access_token"]

def api_get(path, token):
    req = urllib.request.Request(f"{BASE}{path}")
    req.add_header("Authorization", f"Bearer {token}")
    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode()
        is_html = body.strip().startswith("<!doctype") or body.strip().startswith("<!")
        if is_html:
            return {"status": "HTML_FALLBACK", "code": 200, "body": "(SPA fallback)"}
        return {"status": "OK", "code": 200, "body": body}
    except urllib.error.HTTPError as e:
        return {"status": f"HTTP_{e.code}", "code": e.code, "body": e.read().decode()[:200]}
    except Exception as e:
        return {"status": "ERROR", "code": 0, "body": str(e)[:200]}

def api_post(path, token, data_dict):
    body = json.dumps(data_dict).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=body, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req)
        return {"status": "OK", "code": 200, "body": resp.read().decode()}
    except urllib.error.HTTPError as e:
        return {"status": f"HTTP_{e.code}", "code": e.code, "body": e.read().decode()[:200]}
    except Exception as e:
        return {"status": "ERROR", "code": 0, "body": str(e)[:200]}

def main():
    print("=== Evidence Collector ===")
    token = login()
    print(f"Login OK, token: {token[:20]}...")

    # ── 1. Admin API endpoints ──
    endpoints = {
        "stats_counts": "/admin/stats/counts",
        "stats": "/admin/stats",
        "deals": "/admin/deals?limit=3",
        "offers": "/admin/offers?limit=3",
        "reservations": "/admin/reservations?limit=3",
        "notifications": "/admin/notifications/all?limit=3",
        "settlements": "/admin/settlements/",
        "announcements": "/admin/announcements",
        "daily_stats": "/admin/stats/daily",
        "status_summary": "/admin/stats/status-summary",
        "anomaly": "/admin/anomaly/detect",
        "policy_status": "/admin/policy/status",
        "custom_reports": "/admin/custom-report/templates",
        "unified_search": "/admin/unified-search?q=test",
        "reports": "/admin/reports",
        "disputes": "/v3_6/disputes?limit=3",
        "arena_rankings": "/arena/rankings?limit=3",
        "arena_map": "/arena/map",
        "donzzul_stores": "/donzzul/stores",
        "insights": "/v3_6/admin/insights/trends",
        "kpi_advanced": "/v3_6/admin/kpi/advanced",
        "refund_sim": "/admin/refund-simulate",
        "delivery_summary": "/delivery/status-summary",
        "delivery_carriers": "/delivery/carriers",
        "tax_invoices": "/v3_6/tax-invoices",
        "clawback_records": "/v3_6/clawback-records",
        "resolution_actions": "/v3_6/resolution-actions",
        "refund_requests": "/v3_6/refund-requests",
        "spectator_monthly": "/spectators/monthly",
        "points_balance": "/points/balance",
    }

    api_results = []
    for name, path in endpoints.items():
        r = api_get(path, token)
        line = f"{r['status']} [{r['code']}] {name}: {path}"
        preview = r["body"][:150] if r["code"] == 200 and r["status"] == "OK" else r["body"][:100]
        api_results.append(f"{line}\n  -> {preview}\n")
        print(line)

    # ── 2. Pingpong KB tests ──
    kb_tests = [
        {"q": "PG 수수료 누가 부담해?", "expect": ["플랫폼", "역핑"], "fail": ["구매자 부담"]},
        {"q": "감가는 일수 기준이야?", "expect": ["검수", "상태"], "fail": ["일수 기준 맞"]},
        {"q": "무료배송 환불하면 배송비?", "expect": ["왕복", "차감", "배송비"], "fail": []},
        {"q": "개봉만 해도 감가 돼?", "expect": ["사용", "흔적", "검수"], "fail": []},
        {"q": "분쟁에서 교환도 가능해?", "expect": ["교환", "가능", "유형"], "fail": []},
        {"q": "판매자가 환불 무시하면?", "expect": ["자동", "승인", "2영업일"], "fail": []},
        {"q": "AI 중재 금액 마음에 안 들면?", "expect": ["거절", "Round", "재반론"], "fail": []},
        {"q": "관리자가 직접 환불 가능해?", "expect": ["ADMIN", "수동", "관리자"], "fail": []},
    ]

    kb_results = []
    for t in kb_tests:
        r = api_post("/v3_6/pingpong/ask", token, {
            "question": t["q"], "role": "buyer", "buyer_id": 1
        })
        if r["status"] == "OK":
            body = json.loads(r["body"])
            answer = body.get("answer", body.get("response", ""))
            has_expect = any(k in answer for k in t["expect"])
            has_fail = any(k in answer for k in t["fail"]) if t["fail"] else False
            status = "PASS" if has_expect and not has_fail else ("FAIL" if has_fail else "WARN")
            kb_results.append(f"{status} Q: {t['q']}\n  A: {answer[:200]}\n")
        else:
            kb_results.append(f"ERROR Q: {t['q']}\n  -> {r['body'][:100]}\n")

    # ── 3. DB table counts (via admin stats) ──
    counts_r = api_get("/admin/stats/counts", token)
    db_counts = json.loads(counts_r["body"]) if counts_r["status"] == "OK" else {}

    # ── 4. Save evidence files ──
    with open(os.path.join(SCREENSHOTS_DIR, "api_test_results.txt"), "w", encoding="utf-8") as f:
        f.write("=== Production API Test Results ===\n")
        f.write(f"Date: 2026-03-14\nBase: {BASE}\n\n")
        for line in api_results:
            f.write(line)

    with open(os.path.join(SCREENSHOTS_DIR, "pingpongi_kb_evidence.txt"), "w", encoding="utf-8") as f:
        f.write("=== Pingpong KB Accuracy Evidence ===\n\n")
        for line in kb_results:
            f.write(line)

    with open(os.path.join(SCREENSHOTS_DIR, "db_all_tables_count.txt"), "w", encoding="utf-8") as f:
        f.write("=== DB Table Counts (Production) ===\n\n")
        for k, v in sorted(db_counts.items()):
            f.write(f"{k}: {v}\n")

    # ── 5. Detailed DB evidence ──
    # Reservations with order_number
    resv_r = api_get("/admin/reservations?limit=5", token)
    if resv_r["status"] == "OK":
        resv_data = json.loads(resv_r["body"])
        with open(os.path.join(SCREENSHOTS_DIR, "db_reservations.txt"), "w", encoding="utf-8") as f:
            f.write("=== Reservations (Top 5) ===\n\n")
            for item in resv_data.get("items", [])[:5]:
                f.write(json.dumps(item, ensure_ascii=False, indent=2) + "\n---\n")
            f.write(f"\nTotal: {resv_data.get('total', 0)}\n")

    # Disputes
    disp_r = api_get("/v3_6/disputes?limit=5", token)
    if disp_r["status"] == "OK":
        disp_data = json.loads(disp_r["body"])
        with open(os.path.join(SCREENSHOTS_DIR, "db_disputes.txt"), "w", encoding="utf-8") as f:
            f.write("=== Disputes (Top 5) ===\n\n")
            items = disp_data if isinstance(disp_data, list) else disp_data.get("items", [])
            for item in items[:5]:
                f.write(json.dumps(item, ensure_ascii=False, indent=2) + "\n---\n")
            f.write(f"\nTotal: {len(items)}\n")

    # Settlements
    sett_r = api_get("/admin/settlements/", token)
    if sett_r["status"] == "OK":
        sett_data = json.loads(sett_r["body"])
        with open(os.path.join(SCREENSHOTS_DIR, "db_settlements.txt"), "w", encoding="utf-8") as f:
            f.write("=== Settlements ===\n\n")
            items = sett_data if isinstance(sett_data, list) else sett_data.get("items", sett_data.get("settlements", []))
            for item in (items[:5] if isinstance(items, list) else []):
                f.write(json.dumps(item, ensure_ascii=False, indent=2) + "\n---\n")
            f.write(f"\nTotal: {len(items) if isinstance(items, list) else 'N/A'}\n")

    # Refund requests
    ref_r = api_get("/v3_6/refund-requests", token)
    if ref_r["status"] == "OK":
        ref_data = json.loads(ref_r["body"])
        with open(os.path.join(SCREENSHOTS_DIR, "db_refund_requests.txt"), "w", encoding="utf-8") as f:
            f.write("=== Refund Requests ===\n\n")
            items = ref_data if isinstance(ref_data, list) else ref_data.get("items", [])
            for item in (items[:5] if isinstance(items, list) else []):
                f.write(json.dumps(item, ensure_ascii=False, indent=2) + "\n---\n")

    print("\n=== Evidence files saved to screenshots/ ===")
    print("Files:", os.listdir(SCREENSHOTS_DIR))

if __name__ == "__main__":
    main()
