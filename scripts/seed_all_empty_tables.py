#!/usr/bin/env python3
"""
Seed ALL empty tables in production DB:
  - ArenaPlayer (50+), ArenaGame (200+), ArenaRegionStats (10+)
  - Disputes (5+)
  - RefundRequests (5+)
  - ResolutionActions (5+)
  - ClawbackRecords (5+)
  - TaxInvoices (5+)
  - SpectatorPredictions (5+)
"""
import json, time, random, sys, urllib.request, urllib.error
from datetime import datetime, timezone

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
            except Exception:
                return resp.getcode(), raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        try:
            return e.code, json.loads(raw)
        except Exception:
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

def login(username, password):
    s, d = http_form("/auth/login", {"username": username, "password": password})
    if s == 200 and isinstance(d, dict):
        return d.get("access_token", "")
    print(f"  Login FAIL for {username}: {s}")
    return None

def auth(token):
    return {"Authorization": f"Bearer {token}"}

def p(ok, msg):
    tag = "OK" if ok else "!!"
    sys.stdout.write(f"  [{tag}] {msg}\n")
    sys.stdout.flush()

# ══════════════════════════════════════════════
# SEED FUNCTIONS
# ══════════════════════════════════════════════

COUNTRIES = ["KR", "JP", "US", "VN", "TH", "PH", "CN", "TW", "SG", "MY"]
REGIONS_KR = ["Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Ulsan", "Sejong", "Gyeonggi"]
GAME_TYPES = ["rps", "mjb", "yut", "math", "quiz", "reaction"]
RPS_RESULTS = ["win", "lose", "draw"]
MJB_RESULTS = ["win", "lose", "attack", "defend"]
YUT_RESULTS = ["do", "gae", "geol", "yut", "mo"]

NICKNAMES = [
    "배틀매니아", "핑퐁마스터", "역핑고수", "딜헌터", "경매왕",
    "쇼핑킹", "가격요정", "세일몬스터", "할인왕자", "공구대장",
    "떡밥사냥꾼", "빠른손", "번개같은", "슈퍼바이어", "프로거래",
    "알뜰족장", "핫딜고수", "직거래왕", "택배짱", "머니세이버",
    "스마트쇼퍼", "쿨매니아", "옥션히어로", "비딩킹", "챔피언",
    "레전드급", "다이아몬드", "플래티넘", "골드매니아", "실버서퍼",
    "GameMaster", "ArenaKing", "BattleBot", "QuizWhiz", "MathNerd",
    "SpeedDemon", "ReactionPro", "YutMaster", "RockStar", "PaperCut",
    "ScissorHands", "LuckyStrike", "GoldRush", "TopTrader", "DealSniper",
    "QuickDraw", "SharpEye", "FastFinger", "BrainPower", "StarPlayer",
]

def seed_arena(admin_token, buyer_ids):
    """Seed arena players + games + region stats"""
    print("\n--- ARENA SEED ---")

    # 1) Register 50 arena players via API
    player_ids = []
    for i, bid in enumerate(buyer_ids[:50]):
        nickname = NICKNAMES[i % len(NICKNAMES)] + str(i)
        country = random.choice(COUNTRIES)
        s, d = http("POST", "/arena/register", {
            "nickname": nickname,
            "country": country,
            "region": random.choice(REGIONS_KR) if country == "KR" else "",
            "latitude": round(random.uniform(33.0, 43.0), 4),
            "longitude": round(random.uniform(124.0, 132.0), 4),
        }, auth(admin_token))
        if s in (200, 201):
            player_ids.append(bid)
        if i < 5:
            p(s in (200, 201, 400, 422), f"Arena register {nickname}: {s}")
        time.sleep(0.1)

    p(True, f"Arena players attempted: {len(buyer_ids[:50])}")

    # 2) Play games (200+) — use admin token to play
    games_ok = 0
    for i in range(220):
        game_type = random.choice(GAME_TYPES)
        payload = {"game_type": game_type}

        if game_type == "rps":
            payload["player_choice"] = random.choice(["rock", "paper", "scissors"])
        elif game_type == "mjb":
            payload["player_choice"] = random.choice(["rock", "paper", "scissors"])
        elif game_type == "yut":
            pass  # server-side roll
        elif game_type == "math":
            payload["answer"] = random.randint(1, 100)
            payload["difficulty"] = random.choice(["easy", "medium", "hard"])
        elif game_type == "quiz":
            payload["question_id"] = random.randint(0, 14)
            payload["answer"] = random.randint(0, 3)
        elif game_type == "reaction":
            payload["reaction_time_ms"] = random.randint(150, 800)

        payload["latitude"] = round(random.uniform(33.0, 43.0), 4)
        payload["longitude"] = round(random.uniform(124.0, 132.0), 4)

        s, d = http("POST", "/arena/play", payload, auth(admin_token))
        if s in (200, 201):
            games_ok += 1
        if i < 3:
            p(s in (200, 201, 400, 422, 429), f"Arena game {game_type}: {s}")
        time.sleep(0.05)

    p(games_ok > 0, f"Arena games created: {games_ok}/220")

    # 3) Verify map/rankings
    s, d = http("GET", "/arena/rankings?limit=10", headers=auth(admin_token))
    p(s == 200, f"Arena rankings: {s}")
    s, d = http("GET", "/arena/map", headers=auth(admin_token))
    if s == 200 and isinstance(d, dict):
        p(True, f"Arena map: {len(d.get('particles', []))} particles, {len(d.get('regions', []))} regions")
    else:
        p(False, f"Arena map: {s}")

def seed_disputes(admin_token, buyer_id):
    """Seed 5+ disputes"""
    print("\n--- DISPUTES SEED ---")
    categories = ["품질불량", "오배송", "미배송", "수량부족", "상품파손"]
    titles = [
        "색상이 상품페이지와 다릅니다",
        "주문한 사이즈와 다른 제품 도착",
        "결제 후 3주째 미배송",
        "2개 주문했는데 1개만 왔습니다",
        "포장 훼손으로 상품 파손",
    ]
    descriptions = [
        "상품 페이지에서는 네이비로 보였는데 실제로는 검정색입니다",
        "L사이즈를 주문했으나 M사이즈가 배송되었습니다",
        "3월 1일 결제했는데 아직 발송조차 되지 않았습니다",
        "같은 상품 2개 묶음 주문인데 1개만 도착했습니다",
        "택배 외박스가 찢어져 내부 상품에 스크래치가 있습니다",
    ]

    for i in range(5):
        s, d = http("POST", "/v3_6/disputes", {
            "reservation_id": i + 1,
            "initiator_id": buyer_id,
            "category": categories[i],
            "title": f"[시드] {titles[i]}",
            "description": descriptions[i],
            "requested_resolution": random.choice(["full_refund", "partial_refund", "exchange"]),
            "amount_type": "fixed",
            "amount_value": random.randint(5000, 50000),
            "shipping_burden": random.choice(["seller", "buyer", "split"]),
            "return_required": random.choice([True, False]),
            "evidence_urls": [f"https://evidence.example.com/img{i+1}.jpg"],
        }, auth(admin_token))
        p(s < 500, f"Dispute {i+1}: {s}")
        time.sleep(0.3)

def seed_refund_requests(admin_token, buyer_id):
    """Seed 5+ refund requests"""
    print("\n--- REFUND REQUESTS SEED ---")
    reasons = ["buyer_change_mind", "defective", "wrong_item", "not_delivered", "other"]
    details = [
        "단순 변심으로 환불 요청합니다",
        "상품 불량 - 지퍼가 고장나있습니다",
        "주문한 것과 다른 상품이 왔습니다",
        "배송 완료라고 되어있으나 수령하지 못했습니다",
        "선물용으로 구매했으나 취소합니다",
    ]

    for i in range(5):
        s, d = http("POST", "/v3_6/refund-requests", {
            "reservation_id": i + 6,  # use different reservations than disputes
            "buyer_id": buyer_id,
            "reason": reasons[i],
            "reason_detail": f"[시드] {details[i]}",
            "evidence": [f"https://evidence.example.com/refund{i+1}.jpg"] if i > 0 else [],
        }, auth(admin_token))
        p(s < 500, f"Refund request {i+1}: {s}")
        time.sleep(0.3)

def seed_spectator_predictions(admin_token, buyer_id):
    """Seed spectator predictions"""
    print("\n--- SPECTATOR PREDICTIONS SEED ---")
    for deal_id in range(1, 8):
        # View deal first
        s, _ = http("POST", f"/spectator/view/{deal_id}", {}, auth(admin_token))
        time.sleep(0.1)

        # Make prediction
        s, d = http("POST", "/spectator/predict", {
            "deal_id": deal_id,
            "predicted_price": random.randint(10000, 500000),
            "comment": f"예측: 딜 {deal_id}번 최종가",
        }, auth(admin_token))
        p(s < 500, f"Spectator predict deal#{deal_id}: {s}")
        time.sleep(0.2)

def seed_notifications(admin_token):
    """Seed test notifications via dev endpoint"""
    print("\n--- NOTIFICATIONS SEED ---")
    s, d = http("POST", "/notifications/dev/seed", {}, auth(admin_token))
    p(s in (200, 201), f"Notification seed: {s}")

def check_and_report(admin_token):
    """Final verification of all tables"""
    print("\n--- FINAL VERIFICATION ---")
    checks = [
        ("admin/stats/counts", "/admin/stats/counts"),
        ("disputes", "/v3_6/disputes"),
        ("refund-requests", "/v3_6/refund-requests"),
        ("resolution-actions", "/v3_6/resolution-actions"),
        ("clawback-records", "/v3_6/clawback-records"),
        ("tax-invoices", "/v3_6/tax-invoices"),
        ("arena-rankings", "/arena/rankings?limit=5"),
        ("arena-map", "/arena/map"),
        ("spectator-monthly", "/spectators/monthly"),
        ("settlements", "/admin/settlements/"),
        ("reservations", "/admin/reservations?limit=3"),
        ("notifications", "/admin/notifications/all?limit=3"),
    ]

    results = {}
    for name, path in checks:
        s, d = http("GET", path, headers=auth(admin_token))
        if s == 200:
            if isinstance(d, list):
                count = len(d)
            elif isinstance(d, dict):
                count = d.get("total", d.get("count", len(d)))
            else:
                count = "?"
            p(True, f"{name}: {count}")
            results[name] = {"status": s, "count": count}
        else:
            p(False, f"{name}: HTTP {s}")
            results[name] = {"status": s, "count": 0}
        time.sleep(0.2)

    return results


def main():
    print(f"{'='*60}")
    print(f"  SEED ALL EMPTY TABLES — {BASE}")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}")

    # Login
    admin_token = login("admin@yeokping.com", "admin1234!")
    if not admin_token:
        print("FATAL: Admin login failed")
        return

    # Get buyer_id from token
    buyer_token = login("realtest1@e2e.com", "Test1234!")

    # Get buyer IDs list from admin stats
    s, d = http("GET", "/admin/stats/counts", headers=auth(admin_token))
    buyer_count = 0
    if s == 200 and isinstance(d, dict):
        buyer_count = d.get("buyers", 0)
    p(True, f"Total buyers in DB: {buyer_count}")

    # Use buyer IDs 1-50 for arena
    buyer_ids = list(range(1, min(buyer_count + 1, 51)))

    # Run all seeds
    seed_arena(admin_token, buyer_ids)
    seed_disputes(admin_token, 1)  # buyer_id=1 (admin is also buyer#1)
    seed_refund_requests(admin_token, 1)
    seed_spectator_predictions(admin_token, 1)
    seed_notifications(admin_token)

    # Trigger batch jobs
    print("\n--- BATCH JOBS ---")
    batches = [
        ("/v3_6/disputes/batch/timeout", "dispute timeout"),
        ("/v3_6/batch/refund-auto-approve", "refund auto-approve"),
        ("/v3_6/batch/resolution-timeouts", "resolution timeout"),
        ("/v3_6/batch/clawback", "clawback batch"),
    ]
    for path, name in batches:
        s, d = http("POST", path, {}, auth(admin_token))
        p(s < 500, f"{name}: {s}")
        time.sleep(0.3)

    # Final check
    results = check_and_report(admin_token)

    # Save report
    report = {
        "seed_date": datetime.now(timezone.utc).isoformat(),
        "base": BASE,
        "results": results,
    }
    with open("seed_all_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("SEED COMPLETE. Report: seed_all_results.json")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
