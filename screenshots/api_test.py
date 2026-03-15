import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
import io

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

BASE = "https://web-production-defb.up.railway.app"
ctx = ssl.create_default_context()

results = []

def log(msg):
    print(msg)
    results.append(msg)

def req(method, path, headers=None, data=None, form=False):
    url = BASE + path
    if headers is None:
        headers = {}
    body = None
    if data and form:
        body = urllib.parse.urlencode(data).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif data:
        body = json.dumps(data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r, context=ctx, timeout=30)
        code = resp.status
        text = resp.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        code = e.code
        text = e.read().decode('utf-8', errors='replace')
    except Exception as e:
        code = 0
        text = str(e)
    return code, text

# --- Step 1: Login ---
log("=" * 70)
log("STEP 1: Admin Login")
log("=" * 70)
code, text = req("POST", "/auth/login", data={"username": "admin@yeokping.com", "password": "admin1234!"}, form=True)
log(f"POST /auth/login => {code}")
log(f"  Body: {text[:150]}")

token = None
if code == 200:
    try:
        j = json.loads(text)
        token = j.get("access_token") or j.get("token")
        log(f"  Token obtained: {token[:30]}..." if token else "  No token found in response")
    except:
        log("  Could not parse JSON")

if not token:
    log("FATAL: No token, cannot continue authenticated tests.")
    with open("C:/dev/yp-ver2/screenshots/api_test_results.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    sys.exit(1)

auth = {"Authorization": f"Bearer {token}"}

# --- Step 2: Admin endpoints ---
log("")
log("=" * 70)
log("STEP 2: Admin Endpoints")
log("=" * 70)

admin_endpoints = [
    "GET /admin/stats/counts",
    "GET /admin/stats",
    "GET /admin/deals?limit=2",
    "GET /admin/offers?limit=2",
    "GET /admin/reservations?limit=2",
    "GET /admin/settlements/",
    "GET /admin/notifications/all?limit=2",
    "GET /admin/announcements",
    "GET /admin/reports",
    "GET /admin/policy/status",
    "GET /admin/anomaly/detect",
    "GET /admin/custom-report/templates",
    "GET /admin/unified-search?q=test",
    "GET /admin/stats/daily",
    "GET /admin/stats/status-summary",
    "GET /v3_6/admin/insights/trends",
    "GET /v3_6/admin/kpi/advanced",
]

for ep in admin_endpoints:
    method, path = ep.split(" ", 1)
    code, text = req(method, path, headers=dict(auth))
    log(f"\n{method} {path} => {code}")
    log(f"  Body: {text[:150]}")

# --- Step 3: Disputes ---
log("")
log("=" * 70)
log("STEP 3: Dispute Endpoints")
log("=" * 70)

dispute_paths = [
    "GET /disputes?limit=2",
    "GET /admin/disputes?limit=2",
    "GET /v3_6/disputes?limit=2",
    "GET /v3_6/admin/disputes?limit=2",
]
for ep in dispute_paths:
    method, path = ep.split(" ", 1)
    code, text = req(method, path, headers=dict(auth))
    log(f"\n{method} {path} => {code}")
    log(f"  Body: {text[:150]}")

# --- Step 4: Arena ---
log("")
log("=" * 70)
log("STEP 4: Arena Endpoints")
log("=" * 70)

arena_paths = [
    "GET /arena/",
    "GET /v3_6/arena/",
    "GET /arena/rooms",
    "GET /v3_6/arena/rooms",
]
for ep in arena_paths:
    method, path = ep.split(" ", 1)
    code, text = req(method, path, headers=dict(auth))
    log(f"\n{method} {path} => {code}")
    log(f"  Body: {text[:150]}")

# --- Step 5: Donzzul ---
log("")
log("=" * 70)
log("STEP 5: Donzzul Endpoints")
log("=" * 70)

donzzul_paths = [
    "GET /donzzul/stores",
    "GET /v3_6/donzzul/stores",
    "GET /donzzul/",
    "GET /v3_6/donzzul/",
]
for ep in donzzul_paths:
    method, path = ep.split(" ", 1)
    code, text = req(method, path, headers=dict(auth))
    log(f"\n{method} {path} => {code}")
    log(f"  Body: {text[:150]}")

# --- Step 6: Pingpong ---
log("")
log("=" * 70)
log("STEP 6: Pingpong AI Agent")
log("=" * 70)

pp_data = {"question": "환불 가능해?", "role": "buyer", "buyer_id": 1}
code, text = req("POST", "/v3_6/pingpong/ask", headers=dict(auth), data=pp_data)
log(f"\nPOST /v3_6/pingpong/ask => {code}")
log(f"  Body: {text[:150]}")

# --- Summary ---
log("")
log("=" * 70)
log("SUMMARY")
log("=" * 70)

with open("C:/dev/yp-ver2/screenshots/api_test_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))

log("Results saved to C:/dev/yp-ver2/screenshots/api_test_results.txt")
print("\nDone.")
