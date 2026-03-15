#!/usr/bin/env python3
"""Full journey test: deal create → offer create → CRUD connectivity"""
import urllib.request, json, urllib.parse, base64

base = 'https://web-production-defb.up.railway.app'
results = []

def login(email, pw):
    data = urllib.parse.urlencode({'username': email, 'password': pw}).encode()
    req = urllib.request.Request(f'{base}/auth/login', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
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
            return resp.status, {'_html': True, '_body': raw.decode()[:100]}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

def decode_jwt(token):
    p = token.split('.')[1]
    p += '=' * (4 - len(p) % 4)
    return json.loads(base64.b64decode(p))

print("=" * 60)
print("JOURNEY A: BUYER - DEAL CREATION")
print("=" * 60)

# A-1: Buyer login
buyer_token = login('realtest1@e2e.com', 'Test1234!')
bp = decode_jwt(buyer_token)
buyer_id = int(bp['sub'])
print(f"A-1 Buyer login: PASS (id={buyer_id}, role={bp['role']})")
results.append("PASS A-1 Buyer login")

# A-2: Create deal
deal_body = {
    "product_name": "에어팟 프로 2세대",
    "creator_id": buyer_id,
    "category": "electronics",
    "brand": "Apple",
    "product_detail": "Apple AirPods Pro 2nd Gen USB-C",
    "product_code": "MTJV3KH/A",
    "condition": "new",
    "options": json.dumps([
        {"title": "색상", "values": ["화이트"], "selected_value": "화이트"},
        {"title": "연결", "values": ["USB-C", "Lightning"], "selected_value": "USB-C"}
    ]),
    "free_text": "미개봉 정품만",
    "desired_qty": 1,
    "target_price": 280000,
    "market_price": 359000,
    "anchor_price": 359000
}
code, deal = api('POST', '/deals/', buyer_token, deal_body)
if code in (200, 201):
    deal_id = deal.get('id')
    print(f"A-2 Deal created: PASS (id={deal_id})")
    results.append(f"PASS A-2 Deal created")
else:
    print(f"A-2 Deal created: FAIL [{code}] {str(deal)[:200]}")
    results.append("FAIL A-2 Deal creation")
    deal_id = None

# A-3: Deal fetch
if deal_id:
    code, data = api('GET', f'/deals/{deal_id}', buyer_token)
    if code == 200:
        print(f"A-3 Deal fetch: PASS (name={data.get('product_name')})")
        results.append("PASS A-3 Deal fetch")
    else:
        print(f"A-3 Deal fetch: FAIL [{code}]")
        results.append("FAIL A-3")

# A-4: Deal matching
params = urllib.parse.urlencode({'product_name': '에어팟', 'brand': 'Apple', 'category': 'electronics'})
code, match = api('GET', f'/deals/find-similar?{params}', buyer_token)
if code == 200:
    c = match.get('counts', {})
    print(f"A-4 Deal matching: PASS (exact={c.get('exact', 0)}, opt_diff={c.get('option_different', 0)}, similar={c.get('similar', 0)})")
    results.append("PASS A-4 Deal matching")
else:
    print(f"A-4 Deal matching: FAIL [{code}]")
    results.append("FAIL A-4")

# A-5: Deal in admin
admin_token = login('admin@yeokping.com', 'admin1234!')
if deal_id:
    code, data = api('GET', '/admin/deals?limit=5', admin_token)
    if code == 200:
        items = data.get('items', data) if isinstance(data, dict) else data
        found = any(d.get('id') == deal_id for d in (items if isinstance(items, list) else []))
        print(f"A-5 Deal in admin: {'PASS' if found else 'CHECK'} (found={found})")
        results.append(f"{'PASS' if found else 'CHECK'} A-5 Admin deals")

print()
print("=" * 60)
print("JOURNEY C: SELLER - OFFER CREATION")
print("=" * 60)

# C-1: Seller login
seller_token = login('seller@yeokping.com', 'seller1234!')
sp = decode_jwt(seller_token)
seller_id = sp.get('seller_id', int(sp['sub']))
print(f"C-1 Seller login: PASS (seller_id={seller_id}, role={sp['role']})")
results.append("PASS C-1 Seller login")

# C-2: Browse deals
code, deals_data = api('GET', '/deals/?limit=3', seller_token)
if code == 200:
    items = deals_data if isinstance(deals_data, list) else deals_data.get('items', [])
    print(f"C-2 Browse deals: PASS ({len(items)} deals)")
    results.append("PASS C-2 Browse deals")
    target_deal_id = deal_id if deal_id else (items[0]['id'] if items else 1621)
else:
    print(f"C-2 Browse deals: FAIL [{code}]")
    results.append("FAIL C-2")
    target_deal_id = deal_id or 1621

# C-3: Deal detail
code, dd = api('GET', f'/deals/{target_deal_id}', seller_token)
if code == 200:
    opts = dd.get('options', '')
    print(f"C-3 Deal detail: PASS (name={dd.get('product_name')}, has_options={'yes' if opts else 'no'})")
    results.append("PASS C-3 Deal detail")
else:
    print(f"C-3 Deal detail: FAIL [{code}]")
    results.append("FAIL C-3")

# C-4: Create offer with 4-step fields
offer_body = {
    'deal_id': target_deal_id,
    'seller_id': seller_id,
    'price': 275000,
    'quantity': 5,
    'total_available_qty': 20,
    'delivery_days': 2,
    'comment': 'Journey test offer',
    'shipping_mode': 'INCLUDED',
    'confirmed_options': json.dumps([
        {'name': '색상', 'value': '화이트', 'confirmed': True},
        {'name': '연결', 'value': 'USB-C', 'confirmed': True}
    ]),
    'extra_options': json.dumps([{'key': '보증서', 'value': '포함'}]),
    'conditions': json.dumps({'warranty': '1년', 'refund': '7일', 'shipping': '무료', 'delivery': '1~3일'}),
    'components': '에어팟 프로 본체, 충전케이스, 이어팁(S/M/L), USB-C 케이블',
    'product_description': '정품 미개봉 에어팟 프로 2세대 USB-C. 시리얼넘버 확인 가능, A/S 1년.',
    'product_images': json.dumps(['https://example.com/airpods1.jpg']),
    'option_agreement': True
}
code, offer = api('POST', '/offers', seller_token, offer_body)
if code in (200, 201):
    offer_id = offer.get('id')
    print(f"C-4 Offer created: PASS (id={offer_id})")
    for k in ['confirmed_options', 'conditions', 'components', 'product_description', 'option_agreement']:
        v = offer.get(k, 'N/A')
        if isinstance(v, str) and len(v) > 60:
            v = v[:60] + '...'
        print(f"     {k}: {v}")
    results.append(f"PASS C-4 Offer created")
else:
    print(f"C-4 Offer created: FAIL [{code}] {str(offer)[:200]}")
    results.append("FAIL C-4")
    offer_id = None

print()
print("=" * 60)
print("CRUD CONNECTIVITY - offer visible everywhere?")
print("=" * 60)

# D-1: Seller own offers
code, data = api('GET', f'/offers/?seller_id={seller_id}', seller_token)
if code == 200:
    items = data if isinstance(data, list) else data.get('items', [])
    count = len(items) if isinstance(items, list) else '?'
    found = offer_id and any(o.get('id') == offer_id for o in (items if isinstance(items, list) else []))
    print(f"D-1 Seller own offers: PASS (count={count}, new_found={found})")
    results.append(f"{'PASS' if found else 'CHECK'} D-1 Seller offers")
else:
    print(f"D-1 Seller own offers: FAIL [{code}] {str(data)[:200]}")
    results.append("FAIL D-1")

# D-2: Offer in deal's offer list
code, data = api('GET', f'/offers/?deal_id={target_deal_id}', seller_token)
if code == 200:
    items = data if isinstance(data, list) else data.get('items', [])
    count = len(items) if isinstance(items, list) else '?'
    found = offer_id and any(o.get('id') == offer_id for o in (items if isinstance(items, list) else []))
    print(f"D-2 Deal offer list: PASS (count={count}, new_found={found})")
    results.append(f"{'PASS' if found else 'CHECK'} D-2 Deal offers")
else:
    print(f"D-2 Deal offer list: FAIL [{code}] {str(data)[:200]}")
    results.append("FAIL D-2")

# D-3: Admin offers
code, data = api('GET', '/admin/offers?limit=5', admin_token)
if code == 200:
    items = data.get('items', data) if isinstance(data, dict) else data
    found = offer_id and any(o.get('id') == offer_id for o in (items if isinstance(items, list) else []))
    print(f"D-3 Admin offers: PASS (new_found={found})")
    results.append(f"{'PASS' if found else 'CHECK'} D-3 Admin offers")
else:
    print(f"D-3 Admin offers: FAIL [{code}]")
    results.append("FAIL D-3")

# D-4: Admin deals
if deal_id:
    code, data = api('GET', '/admin/deals?limit=5', admin_token)
    if code == 200:
        items = data.get('items', data) if isinstance(data, dict) else data
        found = any(d.get('id') == deal_id for d in (items if isinstance(items, list) else []))
        print(f"D-4 Admin deals: PASS (new_deal_found={found})")
        results.append(f"{'PASS' if found else 'CHECK'} D-4 Admin deals")

print()
print("=" * 60)
print("FRONTEND SPA PAGES LOAD CHECK")
print("=" * 60)
pages = [
    ('/', 'Home'),
    ('/deals', 'Deal list'),
    ('/deal/create', 'Deal create'),
    (f'/deal/{target_deal_id}', 'Deal detail'),
    (f'/deal/{target_deal_id}/offer/create', 'Offer create'),
    ('/my-deals', 'My deals'),
    ('/my-orders', 'My orders'),
    ('/seller/offers', 'Seller offers'),
    ('/seller', 'Seller dashboard'),
]
for path, name in pages:
    req = urllib.request.Request(f'{base}{path}')
    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode()[:300]
        is_spa = '<div id=' in body.lower() or '<!doctype' in body.lower()
        status = 'SPA' if is_spa else 'API'
        print(f"  {name:20s} {path:40s} [{resp.status}] {status}")
    except urllib.error.HTTPError as e:
        print(f"  {name:20s} {path:40s} [{e.code}] FAIL")

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
for r in results:
    print(f"  {r}")

pass_count = sum(1 for r in results if r.startswith('PASS'))
total = len(results)
print(f"\n  {pass_count}/{total} PASS")
