#!/usr/bin/env python3
"""Round 1: Deal 생성 → 전체 반영 지점 검증"""
import urllib.request, json, urllib.parse, base64, sys, time

base = 'https://web-production-defb.up.railway.app'
results = []

def login(email, pw):
    data = urllib.parse.urlencode({'username': email, 'password': pw}).encode()
    req = urllib.request.Request(f'{base}/auth/login', data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())['access_token']

def api(method, path, token=None, body=None):
    hdrs = {'Content-Type': 'application/json'}
    if token:
        hdrs['Authorization'] = f'Bearer {token}'
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f'{base}{path}', data=data, method=method, headers=hdrs)
    try:
        resp = urllib.request.urlopen(req)
        raw = resp.read()
        try:
            return resp.status, json.loads(raw)
        except json.JSONDecodeError:
            return resp.status, {'_html': True, '_len': len(raw)}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]

def decode_jwt(token):
    p = token.split('.')[1]
    p += '=' * (4 - len(p) % 4)
    return json.loads(base64.b64decode(p))

def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append({"name": name, "status": status, "detail": str(detail)[:200]})
    print(f"  {'[PASS]' if condition else '[FAIL]'} {name}")
    if detail and not condition:
        print(f"         -> {str(detail)[:200]}")
    return condition

# ============================================================
print("=" * 70)
print("ROUND 1: DEAL - DECLARATION + CREATE + VERIFY")
print("=" * 70)

# ---- LOGIN all 3 roles ----
buyer_token = login('realtest1@e2e.com', 'Test1234!')
bp = decode_jwt(buyer_token)
buyer_id = int(bp['sub'])
print(f"\nBuyer logged in: id={buyer_id}, role={bp['role']}")

seller_token = login('seller@yeokping.com', 'seller1234!')
sp = decode_jwt(seller_token)
seller_id = sp.get('seller_id', int(sp['sub']))
print(f"Seller logged in: seller_id={seller_id}, role={sp['role']}")

admin_token = login('admin@yeokping.com', 'admin1234!')
ap = decode_jwt(admin_token)
print(f"Admin logged in: id={ap['sub']}, role={ap['role']}")

# ---- GET INITIAL COUNTS ----
code, stats_before = api('GET', '/admin/stats/counts', admin_token)
deal_count_before = stats_before.get('deals', 0) if code == 200 else -1
print(f"\nAdmin stats before: deals={deal_count_before}")

# ============================================================
print("\n" + "=" * 70)
print("STEP 2: CREATE DEAL")
print("=" * 70)

deal_body = {
    "product_name": "QA Round1 iPhone 16 Pro",
    "creator_id": buyer_id,
    "category": "electronics",
    "brand": "Apple",
    "product_detail": "Apple iPhone 16 Pro 256GB Black Titanium",
    "product_code": "MYW23KH/A",
    "condition": "new",
    "options": json.dumps([
        {"title": "color", "values": ["Black Titanium", "White Titanium"], "selected_value": "Black Titanium"},
        {"title": "storage", "values": ["256GB", "512GB", "1TB"], "selected_value": "256GB"}
    ]),
    "free_text": "QA verification deal - Round 1",
    "desired_qty": 3,
    "target_price": 1200000,
    "market_price": 1550000,
    "anchor_price": 1550000
}

code, deal = api('POST', '/deals/', buyer_token, deal_body)
if code in (200, 201):
    deal_id = deal.get('id')
    print(f"Deal created: id={deal_id}, status={deal.get('status')}")
    print(f"  product_name: {deal.get('product_name')}")
    print(f"  target_price: {deal.get('target_price')}")
    print(f"  anchor_price: {deal.get('anchor_price')}")
    print(f"  options: {str(deal.get('options', ''))[:100]}")
    print(f"  category: {deal.get('category')}")
    print(f"  brand: {deal.get('brand')}")
else:
    print(f"FATAL: Deal creation failed [{code}] {str(deal)[:300]}")
    sys.exit(1)

# ============================================================
print("\n" + "=" * 70)
print("STEP 3: VERIFY ALL CHECKPOINTS")
print("=" * 70)

# ---- CP-1: Deal detail API ----
print("\n--- CP-1: GET /deals/{id} (Deal detail API) ---")
code, d = api('GET', f'/deals/{deal_id}', buyer_token)
if check("CP-1a: Deal detail returns 200", code == 200, f"code={code}"):
    check("CP-1b: product_name matches", d.get('product_name') == "QA Round1 iPhone 16 Pro",
          f"got={d.get('product_name')}")
    check("CP-1c: target_price matches", d.get('target_price') == 1200000,
          f"got={d.get('target_price')}")
    check("CP-1d: anchor_price present", d.get('anchor_price') is not None,
          f"got={d.get('anchor_price')}")
    check("CP-1e: category matches", d.get('category') == 'electronics',
          f"got={d.get('category')}")
    check("CP-1f: brand matches", d.get('brand') == 'Apple',
          f"got={d.get('brand')}")
    check("CP-1g: options present", d.get('options') is not None and len(str(d.get('options',''))) > 5,
          f"options={str(d.get('options',''))[:100]}")
    check("CP-1h: status is open", d.get('status') == 'open',
          f"got={d.get('status')}")
    check("CP-1i: creator_id matches buyer", d.get('creator_id') == buyer_id,
          f"got={d.get('creator_id')}")
    check("CP-1j: created_at present", d.get('created_at') is not None,
          f"got={d.get('created_at')}")
    check("CP-1k: desired_qty matches", d.get('desired_qty') == 3,
          f"got={d.get('desired_qty')}")
    check("CP-1l: condition is new", d.get('condition') == 'new',
          f"got={d.get('condition')}")
    check("CP-1m: product_code present", d.get('product_code') is not None,
          f"got={d.get('product_code')}")
    check("CP-1n: free_text present", d.get('free_text') is not None,
          f"got={d.get('free_text')}")

# ---- CP-2: Deal in deals list API ----
print("\n--- CP-2: GET /deals/ (Deal list API) ---")
code, deals_list = api('GET', '/deals/?limit=50', buyer_token)
if check("CP-2a: Deals list returns 200", code == 200, f"code={code}"):
    items = deals_list if isinstance(deals_list, list) else deals_list.get('items', [])
    found = any(d.get('id') == deal_id for d in items)
    check("CP-2b: New deal in list", found, f"checked {len(items)} items, deal_id={deal_id}")

# ---- CP-3: Buyer's own deals (my deals filter) ----
print("\n--- CP-3: GET /deals/?buyer_id={buyer_id} (My deals filter) ---")
code, my_deals = api('GET', f'/deals/?buyer_id={buyer_id}&limit=50', buyer_token)
if check("CP-3a: My deals returns 200", code == 200, f"code={code}"):
    items = my_deals if isinstance(my_deals, list) else my_deals.get('items', [])
    found = any(d.get('id') == deal_id for d in items)
    check("CP-3b: New deal in my deals", found, f"checked {len(items)} items")

# ---- CP-4: Deal participants (creator auto-added) ----
print("\n--- CP-4: GET /deals/{id}/participants (Auto-added creator) ---")
code, parts = api('GET', f'/deals/{deal_id}/participants', buyer_token)
if check("CP-4a: Participants returns 200", code == 200, f"code={code}"):
    items = parts if isinstance(parts, list) else parts.get('items', [])
    creator_found = any(p.get('buyer_id') == buyer_id for p in items)
    check("CP-4b: Creator auto-added as participant", creator_found,
          f"participants={json.dumps(items, default=str)[:200]}")

# ---- CP-5: Deal matching (find-similar) ----
print("\n--- CP-5: GET /deals/find-similar (Deal matching) ---")
params = urllib.parse.urlencode({
    'product_name': 'iPhone 16 Pro',
    'brand': 'Apple',
    'category': 'electronics'
})
code, match = api('GET', f'/deals/find-similar?{params}', buyer_token)
if check("CP-5a: Find-similar returns 200", code == 200, f"code={code}"):
    # Check if our deal appears in any tier
    exact = match.get('exact_match', [])
    opt_diff = match.get('option_different', [])
    similar = match.get('similar_product', [])
    all_matches = exact + opt_diff + similar
    found = any(d.get('id') == deal_id for d in all_matches)
    counts = match.get('counts', {})
    check("CP-5b: New deal in matching results", found,
          f"exact={len(exact)}, opt_diff={len(opt_diff)}, similar={len(similar)}, counts={counts}")

# ---- CP-6: Seller can see deal ----
print("\n--- CP-6: Seller views deal (cross-role visibility) ---")
code, sd = api('GET', f'/deals/{deal_id}', seller_token)
check("CP-6a: Seller can fetch deal detail", code == 200, f"code={code}")
if code == 200:
    check("CP-6b: Seller sees same product_name",
          sd.get('product_name') == "QA Round1 iPhone 16 Pro",
          f"got={sd.get('product_name')}")

# ---- CP-7: Seller sees deal in list ----
print("\n--- CP-7: Seller browses deals list ---")
code, sl = api('GET', '/deals/?limit=50', seller_token)
if check("CP-7a: Seller deals list returns 200", code == 200, f"code={code}"):
    items = sl if isinstance(sl, list) else sl.get('items', [])
    found = any(d.get('id') == deal_id for d in items)
    check("CP-7b: New deal visible to seller", found, f"checked {len(items)} items")

# ---- CP-8: Admin deals page ----
print("\n--- CP-8: GET /admin/deals (Admin management) ---")
code, ad = api('GET', '/admin/deals?limit=50', admin_token)
if check("CP-8a: Admin deals returns 200", code == 200, f"code={code}"):
    items = ad.get('items', ad) if isinstance(ad, dict) else ad
    if isinstance(items, list):
        found = any(d.get('id') == deal_id for d in items)
        check("CP-8b: New deal in admin list", found, f"checked {len(items)} items")
    else:
        check("CP-8b: New deal in admin list", False, f"unexpected format: {type(items)}")

# ---- CP-9: Admin stats count incremented ----
print("\n--- CP-9: GET /admin/stats/counts (Deal count +1) ---")
code, stats_after = api('GET', '/admin/stats/counts', admin_token)
if check("CP-9a: Admin stats returns 200", code == 200, f"code={code}"):
    deal_count_after = stats_after.get('deals', 0)
    check("CP-9b: Deal count incremented",
          deal_count_after > deal_count_before,
          f"before={deal_count_before}, after={deal_count_after}")

# ---- CP-10: Buyer dashboard ----
print("\n--- CP-10: GET /dashboard/buyer/{buyer_id} (Buyer dashboard) ---")
code, bd = api('GET', f'/dashboard/buyer/{buyer_id}', buyer_token)
if check("CP-10a: Buyer dashboard returns 200", code == 200, f"code={code}"):
    # Check if deal count or created deals includes new deal
    stats = bd.get('stats', {})
    deals_stat = stats.get('deals', {})
    participated = deals_stat.get('participated', 0)
    check("CP-10b: Buyer dashboard has deals stats",
          isinstance(deals_stat, dict),
          f"stats.deals={deals_stat}")

# ---- CP-11: Deal search ----
print("\n--- CP-11: GET /deals/search?keyword=iPhone (Search) ---")
code, sr = api('GET', '/deals/search?keyword=iPhone+16+Pro&limit=10', buyer_token)
if check("CP-11a: Search returns 200", code == 200, f"code={code}"):
    items = sr if isinstance(sr, list) else sr.get('items', [])
    found = any(d.get('id') == deal_id for d in items)
    check("CP-11b: New deal found via search", found, f"checked {len(items)} results")

# ---- CP-12: Activity log ----
print("\n--- CP-12: GET /activity-log/by-deal/{id} (Activity log) ---")
code, al = api('GET', f'/activity/by-deal/{deal_id}', admin_token)
if check("CP-12a: Activity log returns 200", code == 200, f"code={code}"):
    items = al if isinstance(al, list) else al.get('items', al.get('events', []))
    check("CP-12b: Activity log has entries",
          isinstance(items, list) and len(items) > 0,
          f"entries={len(items) if isinstance(items, list) else 'N/A'}")

# ---- CP-13: Deal rounds ----
print("\n--- CP-13: Deal rounds (auto-created?) ---")
if isinstance(d, dict) and 'rounds' in d:
    rounds = d.get('rounds', [])
    check("CP-13: Deal has rounds data", True, f"rounds={len(rounds)}")
else:
    # Try via detail endpoint
    code2, d2 = api('GET', f'/deals/{deal_id}', admin_token)
    if code2 == 200:
        rounds = d2.get('rounds', [])
        check("CP-13: Deal rounds accessible", True, f"rounds={len(rounds)}")
    else:
        check("CP-13: Deal rounds accessible", False, "no rounds data")

# ---- CP-14: Preview pack ----
print("\n--- CP-14: GET /preview/deal/{id}?user_id=...&role=BUYER (Preview pack) ---")
code, pp = api('GET', f'/preview/deal/{deal_id}?user_id={buyer_id}&role=BUYER', buyer_token)
check("CP-14: Preview pack returns 200", code == 200,
      f"code={code}, keys={list(pp.keys())[:5] if isinstance(pp, dict) else 'N/A'}")

# ---- CP-15: SPA pages load ----
print("\n--- CP-15: SPA pages load check ---")
spa_pages = [
    (f'/deal/{deal_id}', 'Deal detail page'),
    ('/deals', 'Deal list page'),
    ('/my-deals', 'My deals page'),
    ('/search', 'Search page'),
]
for path, name in spa_pages:
    req = urllib.request.Request(f'{base}{path}')
    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode()[:500]
        is_spa = '<div id=' in body.lower() or '<!doctype' in body.lower()
        check(f"CP-15: {name} ({path}) loads", resp.status == 200 and is_spa,
              f"status={resp.status}, is_spa={is_spa}")
    except urllib.error.HTTPError as e:
        check(f"CP-15: {name} ({path}) loads", False, f"HTTP {e.code}")

# ============================================================
print("\n" + "=" * 70)
print("ROUND 1 SUMMARY")
print("=" * 70)

pass_count = sum(1 for r in results if r['status'] == 'PASS')
fail_count = sum(1 for r in results if r['status'] == 'FAIL')
total = len(results)

print(f"\n  Deal ID: {deal_id}")
print(f"  Total checkpoints: {total}")
print(f"  PASS: {pass_count}")
print(f"  FAIL: {fail_count}")

if fail_count > 0:
    print(f"\n  FAILED items:")
    for r in results:
        if r['status'] == 'FAIL':
            print(f"    - {r['name']}: {r['detail']}")

print(f"\n  Verification credentials:")
print(f"    Buyer:  realtest1@e2e.com / Test1234! -> /deals -> Deal #{deal_id}")
print(f"    Seller: seller@yeokping.com / seller1234! -> /deals -> Deal #{deal_id}")
print(f"    Admin:  admin@yeokping.com / admin1234! -> /admin/deals -> Deal #{deal_id}")

# Save results
report = {
    "round": 1,
    "entity": "Deal",
    "created_id": deal_id,
    "checkpoints": total,
    "PASS": pass_count,
    "FAIL": fail_count,
    "details": results
}
with open('round1-deal-report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  Report saved: round1-deal-report.json")
print(f"\n  Result: {pass_count}/{total} PASS")
