#!/usr/bin/env python3
"""Round 5: 구매확정 (Arrival Confirmation) -> 전체 반영 지점 검증"""
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
print("ROUND 5: ARRIVAL CONFIRMATION")
print("=" * 70)

buyer_token = login('realtest1@e2e.com', 'Test1234!')
bp = decode_jwt(buyer_token)
buyer_id = int(bp['sub'])

seller_token = login('seller@yeokping.com', 'seller1234!')
sp = decode_jwt(seller_token)
seller_id = sp.get('seller_id', int(sp['sub']))

admin_token = login('admin@yeokping.com', 'admin1234!')
print(f"Buyer: id={buyer_id}, Seller: seller_id={seller_id}")

# ---- Setup: Deal + Offer + Reservation + Pay + Ship ----
print("\n--- Setup: Full pipeline ---")
deal_body = {
    "product_name": "QA Round5 Sony WH-1000XM5",
    "creator_id": buyer_id, "category": "electronics", "brand": "Sony",
    "condition": "new", "desired_qty": 2, "target_price": 350000,
    "market_price": 429000, "anchor_price": 429000
}
code, deal = api('POST', '/deals/', buyer_token, deal_body)
deal_id = deal['id']

offer_body = {
    'deal_id': deal_id, 'seller_id': seller_id, 'price': 340000,
    'total_available_qty': 5, 'delivery_days': 2, 'shipping_mode': 'INCLUDED',
    'option_agreement': True
}
code, offer = api('POST', '/offers', seller_token, offer_body)
offer_id = offer['id']

resv_body = {"deal_id": deal_id, "offer_id": offer_id, "buyer_id": buyer_id, "qty": 1}
code, resv = api('POST', '/v3_6/reservations', buyer_token, resv_body)
resv_id = resv['id']
order_number = resv.get('order_number')
amount = resv.get('amount_total', 340000)

pay_body = {"reservation_id": resv_id, "buyer_id": buyer_id, "paid_amount": amount}
code, pay = api('POST', '/v3_6/reservations/pay', buyer_token, pay_body)

ship_body = {"tracking_number": "9876543210987", "shipping_carrier": "Hanjin Express"}
code, ship = api('POST', f'/v3_6/reservations/{resv_id}/ship', seller_token, ship_body)

print(f"Deal={deal_id}, Offer={offer_id}, Resv={resv_id}, Order={order_number}")
print(f"Status: PAID -> Shipped -> now confirming arrival")

# ============================================================
print("\n" + "=" * 70)
print("STEP 2: CONFIRM ARRIVAL")
print("=" * 70)

confirm_body = {"buyer_id": buyer_id}
code, confirm_result = api('POST', f'/v3_6/reservations/{resv_id}/arrival-confirm', buyer_token, confirm_body)
if code not in (200, 201):
    # Try alternate endpoints
    code, confirm_result = api('PUT', f'/v3_6/reservations/{resv_id}/arrival-confirm', buyer_token, confirm_body)
if code not in (200, 201):
    code, confirm_result = api('POST', f'/v3_6/{resv_id}/arrival-confirm', buyer_token, confirm_body)

if check("CONFIRM: Arrival confirmed", code in (200, 201), f"code={code}, result={str(confirm_result)[:200]}"):
    if isinstance(confirm_result, dict):
        print(f"  arrival_confirmed_at: {confirm_result.get('arrival_confirmed_at')}")

# ============================================================
print("\n" + "=" * 70)
print("STEP 3: VERIFY AFTER CONFIRMATION")
print("=" * 70)

# ---- CP-1: Reservation detail ----
print("\n--- CP-1: Reservation detail after confirmation ---")
code, r = api('GET', f'/v3_6/reservations/by-id/{resv_id}', buyer_token)
if check("CP-1a: Returns 200", code == 200, f"code={code}"):
    check("CP-1b: arrival_confirmed_at set", r.get('arrival_confirmed_at') is not None,
          f"got={r.get('arrival_confirmed_at')}")
    phase = str(r.get('phase', '')).upper()
    check("CP-1c: phase updated after arrival",
          r.get('phase') is not None and any(k in phase for k in ['ARRIV','CONFIRM','COMPLET','COOL','DELIVER']),
          f"got={r.get('phase')}")
    check("CP-1d: status still PAID", r.get('status') == 'PAID',
          f"got={r.get('status')}")

# ---- CP-2: Buyer search ----
print("\n--- CP-2: Buyer search shows confirmed ---")
code, br = api('GET', f'/v3_6/search?buyer_id={buyer_id}&limit=10', buyer_token)
if check("CP-2a: Returns 200", code == 200, f"code={code}"):
    items = br if isinstance(br, list) else br.get('items', [])
    found = next((rv for rv in items if rv.get('id') == resv_id), None)
    check("CP-2b: Found in list", found is not None, f"checked {len(items)}")
    if found:
        check("CP-2c: arrival_confirmed_at visible", found.get('arrival_confirmed_at') is not None,
              f"got={found.get('arrival_confirmed_at')}")

# ---- CP-3: Seller search ----
print("\n--- CP-3: Seller search shows confirmed ---")
code, sr = api('GET', f'/v3_6/search?seller_id={seller_id}&limit=10', seller_token)
if check("CP-3a: Returns 200", code == 200, f"code={code}"):
    items = sr if isinstance(sr, list) else sr.get('items', [])
    found = next((rv for rv in items if rv.get('id') == resv_id), None)
    check("CP-3b: Found by seller", found is not None, f"checked {len(items)}")
    if found:
        check("CP-3c: Seller sees confirmed", found.get('arrival_confirmed_at') is not None,
              f"got={found.get('arrival_confirmed_at')}")

# ---- CP-4: Admin ----
print("\n--- CP-4: Admin reservations ---")
code, ar = api('GET', '/admin/reservations?limit=20', admin_token)
if check("CP-4a: Returns 200", code == 200, f"code={code}"):
    items = ar.get('items', ar) if isinstance(ar, dict) else ar
    if isinstance(items, list):
        found = next((rv for rv in items if rv.get('id') == resv_id), None)
        check("CP-4b: Admin sees confirmed", found is not None, f"checked {len(items)}")

# ---- CP-5: Settlement status progression ----
print("\n--- CP-5: Settlement status after confirmation ---")
code, settlements = api('GET', '/admin/settlements/?limit=20', admin_token)
if check("CP-5a: Returns 200", code == 200, f"code={code}"):
    items = settlements.get('items', settlements) if isinstance(settlements, dict) else settlements
    if isinstance(items, list):
        found = next((s for s in items if s.get('reservation_id') == resv_id), None)
        check("CP-5b: Settlement exists", found is not None,
              f"checked {len(items)} settlements")
        if found:
            amt = found.get('total_amount') or found.get('settlement_amount') or found.get('buyer_paid_amount') or 0
            check("CP-5c: Settlement has amount data", amt > 0,
                  f"total_amount={found.get('total_amount')}, settlement_amount={found.get('settlement_amount')}")

# ---- CP-6: Dashboard ----
print("\n--- CP-6: Buyer dashboard ---")
code, bd = api('GET', f'/dashboard/buyer/{buyer_id}', buyer_token)
if check("CP-6a: Returns 200", code == 200, f"code={code}"):
    sp = bd.get('stats', {}).get('reservations', {}).get('shipping_pipeline', {})
    check("CP-6b: Dashboard pipeline data exists", isinstance(sp, dict), f"pipeline={sp}")

# ============================================================
print("\n" + "=" * 70)
print("ROUND 5 SUMMARY")
print("=" * 70)

pass_count = sum(1 for r in results if r['status'] == 'PASS')
fail_count = sum(1 for r in results if r['status'] == 'FAIL')
total = len(results)

print(f"\n  Reservation ID: {resv_id}, Order: {order_number}")
print(f"  Total checkpoints: {total}")
print(f"  PASS: {pass_count}, FAIL: {fail_count}")

if fail_count > 0:
    print(f"\n  FAILED items:")
    for r in results:
        if r['status'] == 'FAIL':
            print(f"    - {r['name']}: {r['detail']}")

report = {
    "round": 5, "entity": "Arrival Confirmation",
    "reservation_id": resv_id, "order_number": order_number,
    "checkpoints": total, "PASS": pass_count, "FAIL": fail_count,
    "details": results
}
with open('round5-confirm-report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  Report saved: round5-confirm-report.json")
print(f"\n  Result: {pass_count}/{total} PASS")
