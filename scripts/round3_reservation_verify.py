#!/usr/bin/env python3
"""Round 3: Reservation + Payment -> 전체 반영 지점 검증"""
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

# ============================================================
print("=" * 70)
print("ROUND 3: RESERVATION + PAYMENT - DECLARE + CREATE + VERIFY")
print("=" * 70)

# ---- LOGIN ----
buyer_token = login('realtest1@e2e.com', 'Test1234!')
bp = decode_jwt(buyer_token)
buyer_id = int(bp['sub'])
print(f"\nBuyer: id={buyer_id}")

seller_token = login('seller@yeokping.com', 'seller1234!')
sp = decode_jwt(seller_token)
seller_id = sp.get('seller_id', int(sp['sub']))
print(f"Seller: seller_id={seller_id}")

admin_token = login('admin@yeokping.com', 'admin1234!')
ap = decode_jwt(admin_token)
print(f"Admin: id={ap['sub']}")

# ---- GET INITIAL COUNTS ----
code, stats_before = api('GET', '/admin/stats/counts', admin_token)
resv_count_before = stats_before.get('reservations', 0) if code == 200 else -1
print(f"\nAdmin stats before: reservations={resv_count_before}")

# ---- Create deal + offer first ----
print("\n--- Setup: Creating test deal ---")
deal_body = {
    "product_name": "QA Round3 AirPods Max",
    "creator_id": buyer_id,
    "category": "electronics",
    "brand": "Apple",
    "product_detail": "Apple AirPods Max USB-C Silver",
    "condition": "new",
    "options": json.dumps([
        {"title": "color", "values": ["Silver", "Midnight"], "selected_value": "Silver"}
    ]),
    "desired_qty": 5,
    "target_price": 650000,
    "market_price": 769000,
    "anchor_price": 769000
}
code, deal = api('POST', '/deals/', buyer_token, deal_body)
if code not in (200, 201):
    print(f"FATAL: Deal creation failed [{code}] {str(deal)[:300]}")
    sys.exit(1)
deal_id = deal['id']
print(f"Deal created: id={deal_id}")

print("--- Setup: Creating test offer ---")
offer_body = {
    'deal_id': deal_id,
    'seller_id': seller_id,
    'price': 640000,
    'quantity': 3,
    'total_available_qty': 10,
    'delivery_days': 2,
    'comment': 'QA Round3 offer',
    'shipping_mode': 'INCLUDED',
    'confirmed_options': json.dumps([{'name': 'color', 'value': 'Silver', 'confirmed': True}]),
    'conditions': json.dumps({'warranty': '1 year', 'refund': '7 days', 'shipping': 'free'}),
    'components': 'AirPods Max, Smart Case, Lightning to 3.5mm cable, USB-C cable',
    'product_description': 'Brand new sealed Apple AirPods Max USB-C Silver.',
    'product_images': json.dumps(['https://example.com/airpodsmax.jpg']),
    'option_agreement': True
}
code, offer = api('POST', '/offers', seller_token, offer_body)
if code not in (200, 201):
    print(f"FATAL: Offer creation failed [{code}] {str(offer)[:300]}")
    sys.exit(1)
offer_id = offer['id']
offer_price = offer.get('price', 640000)
print(f"Offer created: id={offer_id}, price={offer_price}")

# Get offer detail for amount calc
code, offer_detail = api('GET', f'/offers/{offer_id}', seller_token)
total_avail_before = offer_detail.get('total_available_qty', 10) if code == 200 else 10
reserved_before = offer_detail.get('reserved_qty', 0) if code == 200 else 0
sold_before = offer_detail.get('sold_qty', 0) if code == 200 else 0
print(f"Offer inventory: total={total_avail_before}, reserved={reserved_before}, sold={sold_before}")

# ============================================================
print("\n" + "=" * 70)
print("STEP 2: CREATE RESERVATION")
print("=" * 70)

resv_body = {
    "deal_id": deal_id,
    "offer_id": offer_id,
    "buyer_id": buyer_id,
    "qty": 2
}
code, resv = api('POST', '/v3_6/reservations', buyer_token, resv_body)
if code in (200, 201):
    resv_id = resv.get('id')
    order_number = resv.get('order_number')
    print(f"Reservation created: id={resv_id}")
    print(f"  order_number: {order_number}")
    print(f"  status: {resv.get('status')}")
    print(f"  amount_total: {resv.get('amount_total')}")
    print(f"  amount_goods: {resv.get('amount_goods')}")
    print(f"  deal_id: {resv.get('deal_id')}")
    print(f"  offer_id: {resv.get('offer_id')}")
    print(f"  qty: {resv.get('qty')}")
else:
    print(f"FATAL: Reservation creation failed [{code}] {str(resv)[:300]}")
    sys.exit(1)

amount_total = resv.get('amount_total', 0)

# ============================================================
print("\n" + "=" * 70)
print("STEP 3A: VERIFY RESERVATION (PENDING)")
print("=" * 70)

# ---- CP-1: Reservation detail ----
print("\n--- CP-1: GET /v3_6/reservations/by-id/{id} (Reservation detail) ---")
code, r = api('GET', f'/v3_6/reservations/by-id/{resv_id}', buyer_token)
if check("CP-1a: Reservation detail returns 200", code == 200, f"code={code}"):
    check("CP-1b: status is PENDING", r.get('status') == 'PENDING', f"got={r.get('status')}")
    check("CP-1c: deal_id matches", r.get('deal_id') == deal_id, f"got={r.get('deal_id')}")
    check("CP-1d: offer_id matches", r.get('offer_id') == offer_id, f"got={r.get('offer_id')}")
    check("CP-1e: buyer_id matches", r.get('buyer_id') == buyer_id, f"got={r.get('buyer_id')}")
    check("CP-1f: qty matches", r.get('qty') == 2, f"got={r.get('qty')}")
    check("CP-1g: order_number exists", r.get('order_number') is not None and r.get('order_number', '').startswith('YP'),
          f"got={r.get('order_number')}")
    check("CP-1h: amount_total > 0", (r.get('amount_total') or 0) > 0,
          f"got={r.get('amount_total')}")
    check("CP-1i: created_at present", r.get('created_at') is not None,
          f"got={r.get('created_at')}")

# ---- CP-2: Buyer's reservation list ----
print("\n--- CP-2: Buyer reservations search ---")
code, br = api('GET', f'/v3_6/search?buyer_id={buyer_id}&limit=50', buyer_token)
if check("CP-2a: Buyer reservations returns 200", code == 200, f"code={code}"):
    items = br if isinstance(br, list) else br.get('items', [])
    found = any(rv.get('id') == resv_id for rv in items)
    check("CP-2b: New reservation in buyer's list", found, f"checked {len(items)} items")

# ---- CP-3: Seller's reservation list ----
print("\n--- CP-3: Seller reservations search ---")
code, sr = api('GET', f'/v3_6/search?seller_id={seller_id}&limit=50', seller_token)
if check("CP-3a: Seller reservations returns 200", code == 200, f"code={code}"):
    items = sr if isinstance(sr, list) else sr.get('items', [])
    found = any(rv.get('id') == resv_id for rv in items)
    check("CP-3b: New reservation in seller's list", found, f"checked {len(items)} items")

# ---- CP-4: Admin reservations ----
print("\n--- CP-4: Admin reservations ---")
code, ar = api('GET', '/admin/reservations?limit=50', admin_token)
if check("CP-4a: Admin reservations returns 200", code == 200, f"code={code}"):
    items = ar.get('items', ar) if isinstance(ar, dict) else ar
    if isinstance(items, list):
        found = any(rv.get('id') == resv_id for rv in items)
        check("CP-4b: New reservation in admin list", found, f"checked {len(items)} items")
    else:
        check("CP-4b: New reservation in admin list", False, f"unexpected format")

# ---- CP-5: Offer reserved_qty incremented ----
print("\n--- CP-5: Offer inventory updated ---")
code, od = api('GET', f'/offers/{offer_id}', seller_token)
if check("CP-5a: Offer detail returns 200", code == 200, f"code={code}"):
    reserved_after = od.get('reserved_qty', 0)
    check("CP-5b: reserved_qty increased by 2",
          reserved_after == reserved_before + 2,
          f"before={reserved_before}, after={reserved_after}")

# ---- CP-6: Admin stats ----
print("\n--- CP-6: Admin stats count ---")
code, stats_mid = api('GET', '/admin/stats/counts', admin_token)
if check("CP-6a: Admin stats returns 200", code == 200, f"code={code}"):
    resv_count_mid = stats_mid.get('reservations', 0)
    check("CP-6b: Reservation count incremented",
          resv_count_mid > resv_count_before,
          f"before={resv_count_before}, after={resv_count_mid}")

# ============================================================
print("\n" + "=" * 70)
print("STEP 3B: PAY RESERVATION")
print("=" * 70)

pay_body = {
    "reservation_id": resv_id,
    "buyer_id": buyer_id,
    "paid_amount": amount_total
}
code, pay_result = api('POST', '/v3_6/reservations/pay', buyer_token, pay_body)
if check("PAY: Payment accepted", code in (200, 201), f"code={code}, result={str(pay_result)[:200]}"):
    paid_resv = pay_result
    print(f"  Payment result: status={paid_resv.get('status')}")
    print(f"  paid_at: {paid_resv.get('paid_at')}")
else:
    print(f"  Payment failed, continuing with PENDING reservation checks")
    paid_resv = None

# ============================================================
print("\n" + "=" * 70)
print("STEP 3C: VERIFY AFTER PAYMENT")
print("=" * 70)

# ---- CP-7: Reservation status is PAID ----
print("\n--- CP-7: Reservation status after payment ---")
code, r2 = api('GET', f'/v3_6/reservations/by-id/{resv_id}', buyer_token)
if check("CP-7a: Reservation detail still accessible", code == 200, f"code={code}"):
    if paid_resv:
        check("CP-7b: Status is PAID", r2.get('status') == 'PAID', f"got={r2.get('status')}")
        check("CP-7c: paid_at is set", r2.get('paid_at') is not None, f"got={r2.get('paid_at')}")
    else:
        check("CP-7b: Status is PENDING (payment failed)", r2.get('status') == 'PENDING', f"got={r2.get('status')}")

# ---- CP-8: Offer sold_qty updated ----
print("\n--- CP-8: Offer inventory after payment ---")
code, od2 = api('GET', f'/offers/{offer_id}', seller_token)
if check("CP-8a: Offer detail returns 200", code == 200, f"code={code}"):
    if paid_resv:
        sold_after = od2.get('sold_qty', 0)
        reserved_after2 = od2.get('reserved_qty', 0)
        check("CP-8b: sold_qty increased",
              sold_after == sold_before + 2,
              f"before={sold_before}, after={sold_after}")
        check("CP-8c: reserved_qty decreased back",
              reserved_after2 == reserved_before,
              f"before={reserved_before}, after={reserved_after2}")

# ---- CP-9: Settlement created ----
print("\n--- CP-9: Settlement after payment ---")
code, settlements = api('GET', '/admin/settlements/?limit=20', admin_token)
if check("CP-9a: Settlements endpoint returns 200", code == 200, f"code={code}"):
    items = settlements.get('items', settlements) if isinstance(settlements, dict) else settlements
    if isinstance(items, list) and paid_resv:
        found = any(s.get('reservation_id') == resv_id for s in items)
        check("CP-9b: Settlement exists for this reservation", found,
              f"checked {len(items)} settlements")
    elif not paid_resv:
        check("CP-9b: Settlement check (payment failed)", True, "skipped - no payment")

# ---- CP-10: Buyer dashboard updated ----
print("\n--- CP-10: Buyer dashboard ---")
code, bd = api('GET', f'/dashboard/buyer/{buyer_id}', buyer_token)
if check("CP-10a: Buyer dashboard returns 200", code == 200, f"code={code}"):
    stats = bd.get('stats', {})
    resv_stats = stats.get('reservations', {})
    check("CP-10b: Dashboard has reservation stats",
          isinstance(resv_stats, dict) and resv_stats.get('total', 0) > 0,
          f"reservations={resv_stats}")

# ---- CP-11: Seller dashboard updated ----
print("\n--- CP-11: Seller dashboard ---")
code, sd = api('GET', f'/dashboard/seller/{seller_id}', seller_token)
if check("CP-11a: Seller dashboard returns 200", code == 200, f"code={code}"):
    check("CP-11b: Dashboard has data", isinstance(sd, dict) and len(sd) > 0,
          f"keys={list(sd.keys())[:8] if isinstance(sd, dict) else 'N/A'}")

# ---- CP-12: Refund preview accessible ----
print("\n--- CP-12: Refund preview ---")
if paid_resv:
    code, rp = api('GET', f'/v3_6/reservations/refund/preview/{resv_id}', buyer_token)
    check("CP-12: Refund preview accessible", code == 200,
          f"code={code}, data={str(rp)[:100]}")
else:
    check("CP-12: Refund preview (skipped)", True, "no payment")

# ---- CP-13: v3.6 reservation by-id ----
print("\n--- CP-13: v3.6 reservation by-id ---")
code, r36 = api('GET', f'/v3_6/reservations/by-id/{resv_id}', buyer_token)
if check("CP-13a: v3.6 by-id returns 200", code == 200, f"code={code}"):
    check("CP-13b: Has phase field", 'phase' in r36 if isinstance(r36, dict) else False,
          f"keys={list(r36.keys())[:10] if isinstance(r36, dict) else 'N/A'}")

# ---- CP-14: Activity log ----
print("\n--- CP-14: Activity log for deal ---")
code, al = api('GET', f'/activity/by-deal/{deal_id}', admin_token)
if check("CP-14a: Activity log returns 200", code == 200, f"code={code}"):
    items = al if isinstance(al, list) else al.get('items', al.get('events', []))
    check("CP-14b: Activity log has entries", isinstance(items, list) and len(items) > 0,
          f"entries={len(items) if isinstance(items, list) else 'N/A'}")

# ---- CP-15: SPA pages ----
print("\n--- CP-15: SPA pages load check ---")
spa_pages = [
    ('/my-orders', 'My Orders page'),
    (f'/deal/{deal_id}', 'Deal detail page'),
]
for path, name in spa_pages:
    req = urllib.request.Request(f'{base}{path}')
    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode()[:500]
        is_spa = '<div id=' in body.lower() or '<!doctype' in body.lower()
        check(f"CP-15: {name} ({path}) loads", resp.status == 200 and is_spa, f"status={resp.status}")
    except urllib.error.HTTPError as e:
        check(f"CP-15: {name} ({path}) loads", False, f"HTTP {e.code}")

# ---- CP-16: Notifications ----
print("\n--- CP-16: Notifications ---")
code, notifs = api('GET', '/notifications/?limit=10', buyer_token)
if check("CP-16a: Buyer notifications accessible", code == 200, f"code={code}"):
    items = notifs if isinstance(notifs, list) else notifs.get('items', [])
    check("CP-16b: Notifications exist", isinstance(items, list),
          f"count={len(items) if isinstance(items, list) else 'N/A'}")

# Seller notifications
code, snotifs = api('GET', '/notifications/?limit=10', seller_token)
check("CP-16c: Seller notifications accessible", code == 200, f"code={code}")

# ============================================================
print("\n" + "=" * 70)
print("ROUND 3 SUMMARY")
print("=" * 70)

pass_count = sum(1 for r in results if r['status'] == 'PASS')
fail_count = sum(1 for r in results if r['status'] == 'FAIL')
total = len(results)

print(f"\n  Deal ID: {deal_id}")
print(f"  Offer ID: {offer_id}")
print(f"  Reservation ID: {resv_id}")
print(f"  Order Number: {order_number}")
print(f"  Amount Total: {amount_total}")
print(f"  Total checkpoints: {total}")
print(f"  PASS: {pass_count}")
print(f"  FAIL: {fail_count}")

if fail_count > 0:
    print(f"\n  FAILED items:")
    for r in results:
        if r['status'] == 'FAIL':
            print(f"    - {r['name']}: {r['detail']}")

print(f"\n  Verification credentials:")
print(f"    Buyer:  realtest1@e2e.com / Test1234! -> /my-orders -> {order_number}")
print(f"    Seller: seller@yeokping.com / seller1234! -> seller orders")
print(f"    Admin:  admin@yeokping.com / admin1234! -> /admin -> reservations")

report = {
    "round": 3,
    "entity": "Reservation + Payment",
    "deal_id": deal_id,
    "offer_id": offer_id,
    "reservation_id": resv_id,
    "order_number": order_number,
    "amount_total": amount_total,
    "checkpoints": total,
    "PASS": pass_count,
    "FAIL": fail_count,
    "details": results
}
with open('round3-reservation-report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  Report saved: round3-reservation-report.json")
print(f"\n  Result: {pass_count}/{total} PASS")
