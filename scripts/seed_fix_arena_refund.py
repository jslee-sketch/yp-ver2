#!/usr/bin/env python3
"""Fix: Arena needs buyer token, refund needs correct schema"""
import json, time, random, sys, urllib.request, urllib.error

sys.stdout.reconfigure(encoding="utf-8")
BASE = "https://web-production-defb.up.railway.app"

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
            except:
                return resp.getcode(), raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        try:
            return e.code, json.loads(raw)
        except:
            return e.code, raw
    except Exception as ex:
        return 0, str(ex)

def http_form(path, form_data):
    url = f"{BASE}{path}"
    body = "&".join(f"{k}={v}" for k, v in form_data.items()).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.getcode(), json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if hasattr(e, "read") else ""
        try:
            return e.code, json.loads(raw)
        except:
            return e.code, raw
    except Exception as ex:
        return 0, str(ex)

def login(u, p):
    s, d = http_form("/auth/login", {"username": u, "password": p})
    if s == 200 and isinstance(d, dict):
        return d.get("access_token", "")
    return None

def auth(t):
    return {"Authorization": f"Bearer {t}"}

def p(ok, msg):
    tag = "OK" if ok else "!!"
    print(f"  [{tag}] {msg}")

# ══════════════════════════════════════════
# 1. Arena — use buyer tokens
# ══════════════════════════════════════════
print("=== FIX ARENA ===")

# First, login as a buyer (realtest1 is a known buyer)
buyer_token = login("realtest1@e2e.com", "Test1234!")
admin_token = login("admin@yeokping.com", "admin1234!")

if not buyer_token:
    print("Buyer login failed, trying admin...")
    buyer_token = admin_token

if not admin_token:
    print("FATAL: No tokens")
    sys.exit(1)

# Check what user_id admin gets
s, d = http("GET", "/auth/me", headers=auth(admin_token))
print(f"Admin /auth/me: {s} -> {json.dumps(d, ensure_ascii=False)[:200] if isinstance(d, dict) else d[:200]}")

# Try registering arena with buyer token
print("\nRegistering arena player with buyer token...")
s, d = http("POST", "/arena/register", {
    "nickname": "핑퐁마스터",
    "country": "KR",
    "region": "Seoul",
    "latitude": 37.5665,
    "longitude": 126.978,
}, auth(buyer_token))
p(s in (200, 201, 400), f"Arena register (buyer): {s} -> {json.dumps(d, ensure_ascii=False)[:200] if isinstance(d, dict) else str(d)[:200]}")

# Try playing a game
print("\nPlaying arena game with buyer token...")
s, d = http("POST", "/arena/play", {
    "game_type": "rps",
    "player_choice": "rock",
    "latitude": 37.5665,
    "longitude": 126.978,
}, auth(buyer_token))
p(s in (200, 201), f"Arena play (buyer): {s} -> {json.dumps(d, ensure_ascii=False)[:200] if isinstance(d, dict) else str(d)[:200]}")

# Now play many games
GAME_TYPES = ["rps", "mjb", "yut", "math", "quiz", "reaction"]
games_ok = 0
for i in range(50):
    gt = random.choice(GAME_TYPES)
    payload = {"game_type": gt, "latitude": round(random.uniform(33, 43), 4), "longitude": round(random.uniform(124, 132), 4)}
    if gt in ("rps", "mjb"):
        payload["player_choice"] = random.choice(["rock", "paper", "scissors"])
    elif gt == "math":
        payload["answer"] = random.randint(1, 100)
        payload["difficulty"] = random.choice(["easy", "medium", "hard"])
    elif gt == "quiz":
        payload["question_id"] = random.randint(0, 14)
        payload["answer"] = random.randint(0, 3)
    elif gt == "reaction":
        payload["reaction_time_ms"] = random.randint(150, 800)

    s, d = http("POST", "/arena/play", payload, auth(buyer_token))
    if s in (200, 201):
        games_ok += 1
    time.sleep(0.05)

p(games_ok > 0, f"Arena games played: {games_ok}/50")

# Check arena map now
s, d = http("GET", "/arena/map", headers=auth(admin_token))
if s == 200 and isinstance(d, dict):
    p(True, f"Arena map: {len(d.get('particles', []))} particles, {len(d.get('regions', []))} regions")

# ══════════════════════════════════════════
# 2. Refund Requests — check error
# ══════════════════════════════════════════
print("\n=== FIX REFUND REQUESTS ===")

# First check what the endpoint expects
s, d = http("POST", "/v3_6/refund-requests", {
    "reservation_id": 1,
    "buyer_id": 1,
    "reason": "buyer_change_mind",
    "reason_detail": "단순변심",
}, auth(admin_token))
print(f"Refund attempt 1: {s} -> {json.dumps(d, ensure_ascii=False)[:300] if isinstance(d, dict) else str(d)[:300]}")

# Try different field names
s, d = http("POST", "/v3_6/refund-requests", {
    "reservation_id": 10,
    "reason": "defective",
    "detail": "테스트 환불",
}, auth(admin_token))
print(f"Refund attempt 2: {s} -> {json.dumps(d, ensure_ascii=False)[:300] if isinstance(d, dict) else str(d)[:300]}")

# Try minimal
s, d = http("POST", "/v3_6/refund-requests", {
    "reservation_id": 20,
}, auth(admin_token))
print(f"Refund attempt 3 (minimal): {s} -> {json.dumps(d, ensure_ascii=False)[:300] if isinstance(d, dict) else str(d)[:300]}")

# ══════════════════════════════════════════
# 3. Spectator — check error
# ══════════════════════════════════════════
print("\n=== FIX SPECTATOR ===")
s, d = http("POST", "/spectator/predict", {
    "deal_id": 1,
    "predicted_price": 100000,
}, auth(buyer_token))
print(f"Spectator predict: {s} -> {json.dumps(d, ensure_ascii=False)[:300] if isinstance(d, dict) else str(d)[:300]}")

# ══════════════════════════════════════════
# 4. Resolution Actions — check how to create
# ══════════════════════════════════════════
print("\n=== CHECK RESOLUTION ACTIONS ===")
s, d = http("GET", "/v3_6/resolution-actions", headers=auth(admin_token))
print(f"Resolution actions: {s} -> count={len(d) if isinstance(d, list) else d}")

# Check disputes (they should auto-create resolution actions?)
s, d = http("GET", "/v3_6/disputes?limit=3", headers=auth(admin_token))
if isinstance(d, list) and len(d) > 0:
    print(f"Latest dispute: {json.dumps(d[0], ensure_ascii=False)[:300]}")

# ══════════════════════════════════════════
# 5. Clawback — check
# ══════════════════════════════════════════
print("\n=== CHECK CLAWBACK ===")
s, d = http("GET", "/v3_6/clawback-records", headers=auth(admin_token))
print(f"Clawback records: {s} -> {json.dumps(d, ensure_ascii=False)[:200] if isinstance(d, (dict, list)) else str(d)[:200]}")

print("\n=== DONE ===")
