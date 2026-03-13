"""
Test data seed — Production DB에 실제 데이터 생성
테스트 계정으로 딜→오퍼→예약→배송→구매확정→정산→환불→분쟁 흐름 실행
"""
import json, time, urllib.request, urllib.error, sys
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://www.yeokping.com"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = PROJECT_ROOT / "seed_test_data_results.json"

# Test accounts
BUYER_CREDS = {"username": "realtest1@e2e.com", "password": "Test1234!"}
SELLER_CREDS = {"username": "seller@yeokping.com", "password": "seller1234!"}
ADMIN_CREDS = {"username": "admin@yeokping.com", "password": "admin1234!"}

def http(method, path, data=None, headers=None, timeout=15):
    url = f"{BASE}{path}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    hdrs = {"Content-Type": "application/json; charset=utf-8"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.getcode(), json.loads(raw)
            except Exception:
                return resp.getcode(), raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return e.code, raw
    except Exception as ex:
        return 0, str(ex)

def http_form(path, form_data, timeout=15):
    url = f"{BASE}{path}"
    body = "&".join(f"{k}={v}" for k, v in form_data.items()).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.getcode(), json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        return e.code, raw
    except Exception as ex:
        return 0, str(ex)

def login(creds):
    status, data = http_form("/auth/login", creds)
    if status == 200 and isinstance(data, dict):
        token = data.get("access_token", "")
        uid = data.get("user_id", data.get("id", 0))
        return {"token": token, "headers": {"Authorization": f"Bearer {token}"}, "user_id": uid}
    return None

def p(ok, msg):
    tag = "OK" if ok else "!!"
    sys.stdout.write(f"  [{tag}] {msg}\n")
    sys.stdout.flush()

def seed():
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace')
    print(f"\nSeed start: {BASE}\n{'='*50}")

    buyer = login(BUYER_CREDS)
    seller = login(SELLER_CREDS)
    admin = login(ADMIN_CREDS)

    p(buyer is not None, f"Buyer login: {'OK' if buyer else 'FAIL'}")
    p(seller is not None, f"Seller login: {'OK' if seller else 'FAIL'}")
    p(admin is not None, f"Admin login: {'OK' if admin else 'FAIL'}")

    if not buyer or not admin:
        print("Login failed. Aborting.")
        return

    results = []

    # 1. Check existing data
    print("\n--- Current DB status ---")
    endpoints = [
        ("deals", "/v3_6/deals/?limit=1000"),
        ("disputes", "/v3_6/disputes"),
        ("resolution-actions", "/v3_6/resolution-actions"),
        ("refund-requests", "/v3_6/refund-requests"),
        ("settlements", "/v3_6/settlements/"),
    ]
    for name, path in endpoints:
        s, d = http("GET", path, headers=admin["headers"] if admin else None)
        count = len(d) if s == 200 and isinstance(d, list) else "?"
        p(s == 200, f"{name}: {count} records")
        results.append({"check": name, "count": count, "status": s})
        time.sleep(0.3)

    # 2. Create test dispute
    print("\n--- Creating test dispute ---")
    s, d = http("POST", "/v3_6/disputes", {
        "reservation_id": 1,
        "initiator_id": buyer["user_id"],
        "category": "품질불량",
        "title": "[E2E] 테스트 분쟁 - 색상 차이",
        "description": "테스트: 주문 색상과 실제 색상 상이",
        "requested_resolution": "partial_refund",
        "amount_type": "fixed",
        "amount_value": 30000,
        "shipping_burden": "seller",
        "return_required": False,
    }, buyer["headers"])
    p(s < 502, f"Dispute create: {s}")
    results.append({"action": "dispute_create", "status": s})
    time.sleep(1)

    # 3. Create test refund request
    print("\n--- Creating test refund request ---")
    s, d = http("POST", "/v3_6/refund-requests", {
        "reservation_id": 2,
        "buyer_id": buyer["user_id"],
        "reason": "buyer_change_mind",
        "reason_detail": "[E2E] 테스트: 단순 변심 환불 요청",
        "evidence": [],
    }, buyer["headers"])
    p(s < 502, f"Refund request: {s}")
    results.append({"action": "refund_request", "status": s})
    time.sleep(1)

    # 4. Trigger batch jobs
    print("\n--- Running batch jobs ---")
    batches = [
        ("settlement refresh", "/v3_6/settlements/refresh-ready"),
        ("timeout batch", "/v3_6/disputes/batch/timeout"),
        ("clawback batch", "/v3_6/batch/clawback"),
        ("resolution timeout", "/v3_6/batch/resolution-timeouts"),
    ]
    for name, path in batches:
        s, d = http("POST", path, {}, admin["headers"] if admin else None)
        p(s in (200, 201), f"{name}: {s}")
        results.append({"batch": name, "status": s})
        time.sleep(0.5)

    # 5. Final DB check
    print("\n--- Final DB status ---")
    for name, path in endpoints:
        s, d = http("GET", path, headers=admin["headers"] if admin else None)
        count = len(d) if s == 200 and isinstance(d, list) else "?"
        p(s == 200, f"{name}: {count} records")
        time.sleep(0.3)

    # Save results
    output = {
        "seed_date": datetime.now(timezone.utc).isoformat(),
        "endpoint": BASE,
        "results": results,
    }
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'='*50}")
    print(f"Seed complete. Report: {OUT_PATH}")

if __name__ == "__main__":
    seed()
