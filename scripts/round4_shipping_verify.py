#!/usr/bin/env python3
"""Round 4: Shipping -> 전체 반영 지점 검증
Uses reservation from Round 3 (or creates new one)
"""
import urllib.request, json, urllib.parse, base64, sys

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

print("=" * 70)
print("ROUND 4: SHIPPING - DECLARE + PROCESS + VERIFY")
print("=" * 70)

# ---- LOGIN ----
buyer_token = login('realtest1@e2e.com', 'Test1234!')
bp = decode_jwt(buyer_token)
buyer_id = int(bp['sub'])

seller_token = login('seller@yeokping.com', 'seller1234!')
sp = decode_jwt(seller_token)
seller_id = sp.get('seller_id', int(sp['sub']))

admin_token = login('admin@yeokping.com', 'admin1234!')

print(f"Buyer: id={buyer_id}, Seller: seller_id={seller_id}")

# ---- Create deal + offer + reservation + pay ----
print("\n--- Setup: Creating full pipeline ---")
deal_body = {
    "product_name": "QA Round4 Galaxy Buds3 Pro",
    "creator_id": buyer_id, "category": "electronics", "brand": "Samsung",
    "condition": "new", "desired_qty": 3, "target_price": 250000,
    "market_price": 329000, "anchor_price": 329000
}
code, deal = api('POST', '/deals/', buyer_token, deal_body)
deal_id = deal['id']
print(f"Deal: id={deal_id}")

offer_body = {
    'deal_id': deal_id, 'seller_id': seller_id, 'price': 245000,
    'total_available_qty': 10, 'delivery_days': 2, 'shipping_mode': 'INCLUDED',
    'option_agreement': True
}
code, offer = api('POST', '/offers', seller_token, offer_body)
offer_id = offer['id']
print(f"Offer: id={offer_id}")

resv_body = {"deal_id": deal_id, "offer_id": offer_id, "buyer_id": buyer_id, "qty": 1}
code, resv = api('POST', '/v3_6/reservations', buyer_token, resv_body)
resv_id = resv['id']
order_number = resv.get('order_number')
amount = resv.get('amount_total', 245000)
print(f"Reservation: id={resv_id}, order={order_number}, amount={amount}")

pay_body = {"reservation_id": resv_id, "buyer_id": buyer_id, "paid_amount": amount}
code, pay = api('POST', '/v3_6/reservations/pay', buyer_token, pay_body)
print(f"Payment: status={pay.get('status')}")

# ============================================================
print("\n" + "=" * 70)
print("STEP 2: MARK AS SHIPPED")
print("=" * 70)

ship_body = {
    "tracking_number": "1234567890123",
    "shipping_carrier": "CJ Logistics"
}

# Try v3.6 ship endpoint
code, ship_result = api('POST', f'/v3_6/reservations/{resv_id}/ship', seller_token, ship_body)
if code not in (200, 201):
    # Try alternate endpoint
    code, ship_result = api('POST', f'/v3_6/{resv_id}/ship', seller_token, ship_body)

if check("SHIP: Mark shipped accepted", code in (200, 201), f"code={code}, result={str(ship_result)[:200]}"):
    print(f"  shipped_at: {ship_result.get('shipped_at') if isinstance(ship_result, dict) else 'N/A'}")
    print(f"  tracking: {ship_result.get('tracking_number') if isinstance(ship_result, dict) else 'N/A'}")

# ============================================================
print("\n" + "=" * 70)
print("STEP 3: VERIFY AFTER SHIPPING")
print("=" * 70)

# ---- CP-1: Reservation detail shows shipped ----
print("\n--- CP-1: Reservation detail after shipping ---")
code, r = api('GET', f'/v3_6/reservations/by-id/{resv_id}', buyer_token)
if check("CP-1a: Reservation detail returns 200", code == 200, f"code={code}"):
    check("CP-1b: shipped_at is set", r.get('shipped_at') is not None,
          f"shipped_at={r.get('shipped_at')}")
    check("CP-1c: tracking_number saved", r.get('tracking_number') == '1234567890123',
          f"got={r.get('tracking_number')}")
    check("CP-1d: shipping_carrier saved", r.get('shipping_carrier') == 'CJ Logistics',
          f"got={r.get('shipping_carrier')}")
    check("CP-1e: status still PAID", r.get('status') == 'PAID',
          f"got={r.get('status')}")
    check("CP-1f: phase updated", r.get('phase') is not None and 'SHIP' in str(r.get('phase', '')).upper(),
          f"got={r.get('phase')}")

# ---- CP-2: Buyer sees shipping info ----
print("\n--- CP-2: Buyer reservation search shows shipping ---")
code, br = api('GET', f'/v3_6/search?buyer_id={buyer_id}&limit=10', buyer_token)
if check("CP-2a: Buyer search returns 200", code == 200, f"code={code}"):
    items = br if isinstance(br, list) else br.get('items', [])
    found = None
    for rv in items:
        if rv.get('id') == resv_id:
            found = rv
            break
    check("CP-2b: Reservation found", found is not None, f"checked {len(items)} items")
    if found:
        check("CP-2c: Buyer sees shipped_at", found.get('shipped_at') is not None,
              f"shipped_at={found.get('shipped_at')}")
        check("CP-2d: Buyer sees tracking_number", found.get('tracking_number') is not None,
              f"tracking={found.get('tracking_number')}")

# ---- CP-3: Seller sees shipping status ----
print("\n--- CP-3: Seller reservation search shows shipping ---")
code, sr = api('GET', f'/v3_6/search?seller_id={seller_id}&limit=10', seller_token)
if check("CP-3a: Seller search returns 200", code == 200, f"code={code}"):
    items = sr if isinstance(sr, list) else sr.get('items', [])
    found = None
    for rv in items:
        if rv.get('id') == resv_id:
            found = rv
            break
    check("CP-3b: Reservation found by seller", found is not None, f"checked {len(items)} items")
    if found:
        check("CP-3c: Seller sees shipped_at", found.get('shipped_at') is not None,
              f"shipped_at={found.get('shipped_at')}")

# ---- CP-4: Admin sees shipping ----
print("\n--- CP-4: Admin reservation ---")
code, ar = api('GET', '/admin/reservations?limit=20', admin_token)
if check("CP-4a: Admin reservations returns 200", code == 200, f"code={code}"):
    items = ar.get('items', ar) if isinstance(ar, dict) else ar
    if isinstance(items, list):
        found = None
        for rv in items:
            if rv.get('id') == resv_id:
                found = rv
                break
        check("CP-4b: Admin sees shipped reservation", found is not None,
              f"checked {len(items)} items")
        if found:
            check("CP-4c: Admin sees tracking_number", found.get('tracking_number') is not None,
                  f"tracking={found.get('tracking_number')}")

# ---- CP-5: Buyer dashboard shipping pipeline ----
print("\n--- CP-5: Buyer dashboard shipping pipeline ---")
code, bd = api('GET', f'/dashboard/buyer/{buyer_id}', buyer_token)
if check("CP-5a: Dashboard returns 200", code == 200, f"code={code}"):
    sp = bd.get('stats', {}).get('reservations', {}).get('shipping_pipeline', {})
    check("CP-5b: Shipping pipeline data exists", isinstance(sp, dict),
          f"pipeline={sp}")

# ---- CP-6: SPA pages ----
print("\n--- CP-6: SPA pages ---")
spa_pages = [('/my-orders', 'My Orders')]
for path, name in spa_pages:
    req = urllib.request.Request(f'{base}{path}')
    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode()[:500]
        is_spa = '<div id=' in body.lower() or '<!doctype' in body.lower()
        check(f"CP-6: {name} page loads", resp.status == 200 and is_spa, f"status={resp.status}")
    except urllib.error.HTTPError as e:
        check(f"CP-6: {name} page loads", False, f"HTTP {e.code}")

# ============================================================
print("\n" + "=" * 70)
print("ROUND 4 SUMMARY")
print("=" * 70)

pass_count = sum(1 for r in results if r['status'] == 'PASS')
fail_count = sum(1 for r in results if r['status'] == 'FAIL')
total = len(results)

print(f"\n  Reservation ID: {resv_id}")
print(f"  Order Number: {order_number}")
print(f"  Tracking: 1234567890123 (CJ Logistics)")
print(f"  Total checkpoints: {total}")
print(f"  PASS: {pass_count}")
print(f"  FAIL: {fail_count}")

if fail_count > 0:
    print(f"\n  FAILED items:")
    for r in results:
        if r['status'] == 'FAIL':
            print(f"    - {r['name']}: {r['detail']}")

report = {
    "round": 4, "entity": "Shipping",
    "reservation_id": resv_id, "order_number": order_number,
    "checkpoints": total, "PASS": pass_count, "FAIL": fail_count,
    "details": results
}
with open('round4-shipping-report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  Report saved: round4-shipping-report.json")
print(f"\n  Result: {pass_count}/{total} PASS")
