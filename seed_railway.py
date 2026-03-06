"""Railway DB data seeding script"""
import requests, time, sys, io, json, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "https://web-production-defb.up.railway.app"

def form_login(email, password, endpoint="/auth/login"):
    """Login with form-encoded data (OAuth2PasswordRequestForm)"""
    r = requests.post(f"{BASE}{endpoint}", data={"username": email, "password": password}, timeout=10)
    if r.status_code == 200:
        try:
            return r.json().get("access_token")
        except Exception:
            pass
    return None

def auth_h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {"Content-Type": "application/json"}

def jwt_payload(token):
    """Extract payload from JWT without verification"""
    try:
        parts = token.split(".")
        payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
        return json.loads(base64.b64decode(payload))
    except Exception:
        return {}

def safe_json(r):
    try:
        return r.json()
    except Exception:
        return {}

# ── 1. Admin login ──────────────────────────────────────
print("=== 1. Admin login ===")
admin_token = form_login("admin@yeokping.com", "admin1234!")
if admin_token:
    p = jwt_payload(admin_token)
    print(f"Admin login OK (role={p.get('role')}, sub={p.get('sub')})")
else:
    print("Admin login FAILED")

# ── 2. Seller ───────────────────────────────────────────
print("\n=== 2. Seller ===")
seller_token = None
seller_id = None
# Try seller-specific login
for ep in ["/auth/seller/login", "/auth/login"]:
    seller_token = form_login("e2e_seller@test.com", "Test1234!", ep)
    if seller_token:
        p = jwt_payload(seller_token)
        seller_id = p.get("seller_id") or int(p.get("sub", 0))
        print(f"Seller login OK via {ep} (id={seller_id})")
        break

if not seller_token:
    # Create seller
    r = requests.post(f"{BASE}/sellers/", json={
        "email": "e2e_seller@test.com", "password": "Test1234!",
        "name": "E2Eseller", "nickname": "e2eseller",
        "business_name": "E2E테스트상점", "business_number": "1234567890",
        "phone": "01012345678", "address": "Seoul", "zip_code": "06000",
        "established_date": "2024-01-01T00:00:00"
    }, timeout=10)
    d = safe_json(r)
    print(f"Seller create: {r.status_code} {str(d)[:80]}")
    if r.status_code < 300:
        seller_id = d.get("id")
    # Try login again
    for ep in ["/auth/seller/login", "/auth/login"]:
        seller_token = form_login("e2e_seller@test.com", "Test1234!", ep)
        if seller_token:
            p = jwt_payload(seller_token)
            seller_id = seller_id or p.get("seller_id") or int(p.get("sub", 0))
            print(f"Seller login OK via {ep} (id={seller_id})")
            break
    if not seller_token:
        print("Seller login FAILED")

sellerH = auth_h(seller_token)

# ── 3. Buyers 5명 ──────────────────────────────────────
print("\n=== 3. Buyers (5) ===")
buyer_tokens = []
buyer_ids = []
for i in range(1, 6):
    email = f"realtest{i}@e2e.com"
    pw = "Test1234!"
    nick = f"buyer{i}"
    # Try login first
    tok = form_login(email, pw)
    if tok:
        p = jwt_payload(tok)
        bid = int(p.get("sub", 0))
        print(f"  Buyer{i} exists, login OK (id={bid})")
    else:
        # Register
        r = requests.post(f"{BASE}/buyers/", json={
            "email": email, "password": pw, "name": nick, "nickname": nick,
            "phone": f"0109999000{i}"
        }, timeout=10)
        d = safe_json(r)
        bid = d.get("id")
        print(f"  Buyer{i} register: {r.status_code} id={bid}")
        tok = form_login(email, pw)
        if tok:
            p = jwt_payload(tok)
            bid = bid or int(p.get("sub", 0))
    buyer_tokens.append(tok)
    buyer_ids.append(bid)

b1H = auth_h(buyer_tokens[0])
b2H = auth_h(buyer_tokens[1])
b3H = auth_h(buyer_tokens[2])

print(f"Buyer IDs: {buyer_ids}")

# ── 4. 딜 3개 ──────────────────────────────────────────
print("\n=== 4. Deals (3) ===")
deal_data = [
    {"product_name": "아이폰 16 프로 256GB", "creator_id": buyer_ids[0], "desired_qty": 5,
     "target_price": 1200000, "max_budget": 1500000, "anchor_price": 1500000, "market_price": 1500000, "brand": "Apple"},
    {"product_name": "갤럭시 S25 울트라 512GB", "creator_id": buyer_ids[1], "desired_qty": 5,
     "target_price": 1400000, "max_budget": 1800000, "anchor_price": 1800000, "market_price": 1800000, "brand": "Samsung"},
    {"product_name": "다이슨 에어랩 컴플리트", "creator_id": buyer_ids[2], "desired_qty": 10,
     "target_price": 500000, "max_budget": 700000, "anchor_price": 700000, "market_price": 700000, "brand": "Dyson"},
]
deal_ids = []
for i, dd in enumerate(deal_data):
    h = auth_h(buyer_tokens[i])
    try:
        r = requests.post(f"{BASE}/deals/", json=dd, headers=h, timeout=10)
        d = safe_json(r)
        did = d.get("id")
        deal_ids.append(did)
        print(f"  Deal: id={did} '{dd['product_name']}' (status={r.status_code})")
    except Exception as e:
        deal_ids.append(None)
        print(f"  Deal FAIL: {e}")

# ── 5. 오퍼 6개 ────────────────────────────────────────
print("\n=== 5. Offers (6) ===")
offer_data = [
    {"deal_id": deal_ids[0], "seller_id": seller_id, "price": 1300000, "total_available_qty": 10, "shipping_mode": "INCLUDED", "delivery_days": 3},
    {"deal_id": deal_ids[0], "seller_id": seller_id, "price": 1250000, "total_available_qty": 5, "shipping_mode": "INCLUDED", "delivery_days": 2},
    {"deal_id": deal_ids[0], "seller_id": seller_id, "price": 1180000, "total_available_qty": 8, "shipping_mode": "PER_RESERVATION", "shipping_fee_per_reservation": 3000, "delivery_days": 5},
    {"deal_id": deal_ids[1], "seller_id": seller_id, "price": 1500000, "total_available_qty": 5, "shipping_mode": "INCLUDED", "delivery_days": 2},
    {"deal_id": deal_ids[1], "seller_id": seller_id, "price": 1420000, "total_available_qty": 3, "shipping_mode": "INCLUDED", "delivery_days": 3},
    {"deal_id": deal_ids[2], "seller_id": seller_id, "price": 550000, "total_available_qty": 10, "shipping_mode": "PER_RESERVATION", "shipping_fee_per_reservation": 5000, "delivery_days": 7},
]
offer_ids = []
for o in offer_data:
    if not o.get("deal_id") or not o.get("seller_id"):
        offer_ids.append(None)
        print(f"  Offer SKIP (missing deal_id={o.get('deal_id')} seller_id={o.get('seller_id')})")
        continue
    try:
        r = requests.post(f"{BASE}/v3_6/offers", json=o, headers=sellerH, timeout=10)
        d = safe_json(r)
        oid = d.get("id")
        offer_ids.append(oid)
        print(f"  Offer: deal={o['deal_id']} price={o['price']:,} -> id={oid} (status={r.status_code})")
    except Exception as e:
        offer_ids.append(None)
        print(f"  Offer FAIL: {e}")

# ── 6. 예약 + 결제 3건 ──────────────────────────────────
print("\n=== 6. Reservations + Pay (3) ===")
res_ids = []
reservations = [
    {"offer_idx": 2, "buyer_idx": 0, "deal_idx": 0, "qty": 1, "amount": 1183000},
    {"offer_idx": 1, "buyer_idx": 1, "deal_idx": 0, "qty": 1, "amount": 1250000},
    {"offer_idx": 4, "buyer_idx": 2, "deal_idx": 1, "qty": 2, "amount": 2840000},
]
for i, rv in enumerate(reservations):
    oi = rv["offer_idx"]; bi = rv["buyer_idx"]; di = rv["deal_idx"]
    oid = offer_ids[oi] if oi < len(offer_ids) else None
    bid = buyer_ids[bi] if bi < len(buyer_ids) else None
    did = deal_ids[di] if di < len(deal_ids) else None
    bh = auth_h(buyer_tokens[bi]) if bi < len(buyer_tokens) and buyer_tokens[bi] else {}
    if not oid or not bid or not did:
        res_ids.append(None)
        print(f"  Reservation{i+1} SKIP (offer={oid} buyer={bid} deal={did})")
        continue
    try:
        r = requests.post(f"{BASE}/v3_6/reservations", json={
            "deal_id": did, "offer_id": oid, "buyer_id": bid, "qty": rv["qty"]
        }, headers=bh, timeout=10)
        d = safe_json(r)
        rid = d.get("id")
        res_ids.append(rid)
        print(f"  Reserve{i+1}: id={rid} (status={r.status_code})")
        if rid:
            pr = requests.post(f"{BASE}/v3_6/reservations/pay", json={
                "reservation_id": rid, "buyer_id": bid, "paid_amount": rv["amount"]
            }, headers=bh, timeout=10)
            print(f"  Pay{i+1}: status={pr.status_code}")
    except Exception as e:
        res_ids.append(None)
        print(f"  Reservation{i+1} FAIL: {e}")

# ── 7. 배송 2건 ────────────────────────────────────────
print("\n=== 7. Shipping (2) ===")
ship_data = [(0, "REAL001", "CJ대한통운"), (1, "REAL002", "한진택배")]
for idx, track, carrier in ship_data:
    rid = res_ids[idx] if idx < len(res_ids) else None
    if not rid:
        print(f"  Ship{idx+1} SKIP"); continue
    try:
        r = requests.post(f"{BASE}/v3_6/reservations/{rid}/ship", json={
            "tracking_number": track, "shipping_carrier": carrier
        }, headers=sellerH, timeout=10)
        print(f"  Ship{idx+1}: reservation={rid} -> status={r.status_code}")
    except Exception as e:
        print(f"  Ship{idx+1} FAIL: {e}")

# ── 8. 수취확인 1건 ────────────────────────────────────
print("\n=== 8. Arrival confirm ===")
if res_ids and res_ids[0]:
    try:
        r = requests.post(f"{BASE}/v3_6/reservations/{res_ids[0]}/arrival-confirm",
                         json={"buyer_id": buyer_ids[0]}, headers=b1H, timeout=10)
        print(f"  Confirm: reservation={res_ids[0]} -> status={r.status_code}")
    except Exception as e:
        print(f"  Confirm FAIL: {e}")
else:
    print("  SKIP")

# ── 9. 환불 1건 ────────────────────────────────────────
print("\n=== 9. Refund ===")
if len(res_ids) > 1 and res_ids[1]:
    try:
        r = requests.post(f"{BASE}/v3_6/reservations/refund", json={
            "reservation_id": res_ids[1], "reason": "단순변심", "requested_by": "BUYER"
        }, headers=b2H, timeout=10)
        d = safe_json(r)
        print(f"  Refund: reservation={res_ids[1]} -> status={r.status_code} {str(d)[:80]}")
    except Exception as e:
        print(f"  Refund FAIL: {e}")
else:
    print("  SKIP")

# ── 10. 핑퐁이 10개 ───────────────────────────────────
print("\n=== 10. Pingpong (10) ===")
questions = ["안녕", "역핑은 뭐야?", "환불 정책", "오퍼 마감 시간", "결제 제한시간",
             "딜방 만드는법", "갤럭시 S25 최저가", "쿨링 기간", "수수료", "배송비 누가내"]
pp_pass = 0
for i, q in enumerate(questions):
    if i > 0 and i % 8 == 0:
        print("  Rate-limit pause 62s...")
        time.sleep(62)
    try:
        r = requests.post(f"{BASE}/v3_6/pingpong/ask", json={
            "question": q, "buyer_id": buyer_ids[0] if buyer_ids else 1
        }, headers=b1H, timeout=30)
        d = safe_json(r)
        if r.status_code == 200 and d.get("answer"):
            pp_pass += 1
            print(f"  [{i+1}/10] PASS: {q} -> {d['answer'][:50]}")
        else:
            print(f"  [{i+1}/10] FAIL: {q} (status={r.status_code})")
    except Exception as e:
        print(f"  [{i+1}/10] ERROR: {q} ({e})")
    time.sleep(1.5)

print(f"\n{'='*50}")
print(f"Railway DB seeding complete!")
print(f"Buyers: {len([b for b in buyer_ids if b])}/5")
print(f"Deals:  {len([d for d in deal_ids if d])}/3")
print(f"Offers: {len([o for o in offer_ids if o])}/6")
print(f"Reserv: {len([r for r in res_ids if r])}/3")
print(f"Pingpong: {pp_pass}/10")
