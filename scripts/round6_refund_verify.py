#!/usr/bin/env python3
"""Round 6: Refund -> 전체 반영 지점 검증"""
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
print("ROUND 6: REFUND")
print("=" * 70)

buyer_token = login('realtest1@e2e.com', 'Test1234!')
bp = decode_jwt(buyer_token)
buyer_id = int(bp['sub'])

seller_token = login('seller@yeokping.com', 'seller1234!')
sp = decode_jwt(seller_token)
seller_id = sp.get('seller_id', int(sp['sub']))

admin_token = login('admin@yeokping.com', 'admin1234!')
print(f"Buyer: id={buyer_id}, Seller: seller_id={seller_id}")

# ---- Setup: Deal + Offer + Reservation + Pay (no ship, to test refund on paid) ----
print("\n--- Setup: Pipeline for refund ---")
deal_body = {
    "product_name": "QA Round6 Refund Test Item",
    "creator_id": buyer_id, "category": "electronics", "brand": "Test",
    "condition": "new", "desired_qty": 2, "target_price": 100000,
    "market_price": 150000, "anchor_price": 150000
}
code, deal = api('POST', '/deals/', buyer_token, deal_body)
deal_id = deal['id']

offer_body = {
    'deal_id': deal_id, 'seller_id': seller_id, 'price': 95000,
    'total_available_qty': 5, 'delivery_days': 2, 'shipping_mode': 'INCLUDED',
    'option_agreement': True
}
code, offer = api('POST', '/offers', seller_token, offer_body)
offer_id = offer['id']

resv_body = {"deal_id": deal_id, "offer_id": offer_id, "buyer_id": buyer_id, "qty": 2}
code, resv = api('POST', '/v3_6/reservations', buyer_token, resv_body)
resv_id = resv['id']
order_number = resv.get('order_number')
amount = resv.get('amount_total', 190000)

pay_body = {"reservation_id": resv_id, "buyer_id": buyer_id, "paid_amount": amount}
code, pay = api('POST', '/v3_6/reservations/pay', buyer_token, pay_body)
print(f"Deal={deal_id}, Offer={offer_id}, Resv={resv_id}, Order={order_number}, Amount={amount}")
print(f"Payment status: {pay.get('status') if isinstance(pay, dict) else pay}")

# Get offer sold_qty before refund
code, od_before = api('GET', f'/offers/{offer_id}', seller_token)
sold_before = od_before.get('sold_qty', 0) if code == 200 else 0

# ---- Refund preview ----
print("\n--- Refund preview ---")
code, preview = api('GET', f'/v3_6/reservations/refund/preview/{resv_id}', buyer_token)
if check("PREVIEW: Refund preview accessible", code == 200, f"code={code}"):
    if isinstance(preview, dict):
        print(f"  Preview: {json.dumps(preview, default=str)[:200]}")

# ============================================================
print("\n" + "=" * 70)
print("STEP 2: REQUEST REFUND")
print("=" * 70)

refund_body = {
    "reservation_id": resv_id,
    "actor": "buyer_change_mind",
    "reason": "QA test refund - Round 6",
    "refund_type": "refund"
}
code, refund_result = api('POST', '/v3_6/reservations/refund', buyer_token, refund_body)
if check("REFUND: Refund accepted", code in (200, 201), f"code={code}, result={str(refund_result)[:200]}"):
    if isinstance(refund_result, dict):
        print(f"  status: {refund_result.get('status')}")
        print(f"  refunded_qty: {refund_result.get('refunded_qty')}")
        print(f"  refunded_amount: {refund_result.get('refunded_amount_total')}")

# ============================================================
print("\n" + "=" * 70)
print("STEP 3: VERIFY AFTER REFUND")
print("=" * 70)

# ---- CP-1: Reservation detail ----
print("\n--- CP-1: Reservation detail after refund ---")
code, r = api('GET', f'/v3_6/reservations/by-id/{resv_id}', buyer_token)
if check("CP-1a: Returns 200", code == 200, f"code={code}"):
    check("CP-1b: Status is CANCELLED", r.get('status') == 'CANCELLED',
          f"got={r.get('status')}")
    check("CP-1c: cancelled_at set", r.get('cancelled_at') is not None,
          f"got={r.get('cancelled_at')}")
    check("CP-1d: refunded_qty matches",
          r.get('refunded_qty') == 2 or r.get('refunded_qty') == resv.get('qty', 2),
          f"got={r.get('refunded_qty')}")
    check("CP-1e: refunded_amount_total > 0",
          (r.get('refunded_amount_total') or 0) > 0,
          f"got={r.get('refunded_amount_total')}")
    check("CP-1f: refund_type set", r.get('refund_type') is not None,
          f"got={r.get('refund_type')}")

# ---- CP-2: Buyer sees refund ----
print("\n--- CP-2: Buyer sees refunded reservation ---")
code, br = api('GET', f'/v3_6/search?buyer_id={buyer_id}&limit=10', buyer_token)
if check("CP-2a: Returns 200", code == 200, f"code={code}"):
    items = br if isinstance(br, list) else br.get('items', [])
    found = next((rv for rv in items if rv.get('id') == resv_id), None)
    check("CP-2b: Found in list", found is not None, f"checked {len(items)}")
    if found:
        check("CP-2c: Status CANCELLED", found.get('status') == 'CANCELLED',
              f"got={found.get('status')}")

# ---- CP-3: Seller sees refund ----
print("\n--- CP-3: Seller sees refunded reservation ---")
code, sr = api('GET', f'/v3_6/search?seller_id={seller_id}&limit=10', seller_token)
if check("CP-3a: Returns 200", code == 200, f"code={code}"):
    items = sr if isinstance(sr, list) else sr.get('items', [])
    found = next((rv for rv in items if rv.get('id') == resv_id), None)
    check("CP-3b: Found by seller", found is not None, f"checked {len(items)}")
    if found:
        check("CP-3c: Seller sees CANCELLED", found.get('status') == 'CANCELLED',
              f"got={found.get('status')}")

# ---- CP-4: Admin sees refund ----
print("\n--- CP-4: Admin ---")
code, ar = api('GET', '/admin/reservations?limit=20', admin_token)
if check("CP-4a: Returns 200", code == 200, f"code={code}"):
    items = ar.get('items', ar) if isinstance(ar, dict) else ar
    if isinstance(items, list):
        found = next((rv for rv in items if rv.get('id') == resv_id), None)
        check("CP-4b: Admin sees refunded", found is not None, f"checked {len(items)}")

# ---- CP-5: Offer inventory restored ----
print("\n--- CP-5: Offer inventory after refund ---")
code, od_after = api('GET', f'/offers/{offer_id}', seller_token)
if check("CP-5a: Returns 200", code == 200, f"code={code}"):
    sold_after = od_after.get('sold_qty', 0)
    check("CP-5b: sold_qty decreased",
          sold_after < sold_before or sold_after == 0,
          f"before={sold_before}, after={sold_after}")

# ---- CP-6: Settlement updated ----
print("\n--- CP-6: Settlement after refund ---")
code, settlements = api('GET', '/admin/settlements/?limit=20', admin_token)
if check("CP-6a: Returns 200", code == 200, f"code={code}"):
    items = settlements.get('items', settlements) if isinstance(settlements, dict) else settlements
    if isinstance(items, list):
        found = next((s for s in items if s.get('reservation_id') == resv_id), None)
        check("CP-6b: Settlement exists", found is not None, f"checked {len(items)}")
        if found:
            st = found.get('status', '')
            check("CP-6c: Settlement status updated",
                  st in ('CANCELLED', 'PENDING', 'HOLD'),
                  f"got={st}")

# ---- CP-7: Refund summary ----
print("\n--- CP-7: Refund summary ---")
code, rs = api('GET', f'/v3_6/reservations/refund/summary/{resv_id}', buyer_token)
check("CP-7: Refund summary accessible", code == 200,
      f"code={code}, data={str(rs)[:100]}")

# ---- CP-8: Dashboard ----
print("\n--- CP-8: Dashboard ---")
code, bd = api('GET', f'/dashboard/buyer/{buyer_id}', buyer_token)
if check("CP-8a: Returns 200", code == 200, f"code={code}"):
    cancelled = bd.get('stats', {}).get('reservations', {}).get('by_status', {}).get('CANCELLED', 0)
    check("CP-8b: Dashboard shows cancelled count > 0", cancelled > 0,
          f"CANCELLED={cancelled}")

# ============================================================
print("\n" + "=" * 70)
print("ROUND 6 SUMMARY")
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
    "round": 6, "entity": "Refund",
    "reservation_id": resv_id, "order_number": order_number,
    "checkpoints": total, "PASS": pass_count, "FAIL": fail_count,
    "details": results
}
with open('round6-refund-report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  Report saved: round6-refund-report.json")
print(f"\n  Result: {pass_count}/{total} PASS")
