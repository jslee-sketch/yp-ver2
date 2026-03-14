#!/usr/bin/env python3
"""Round 7: Dispute -> 전체 반영 지점 검증"""
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
print("ROUND 7: DISPUTE (OPEN + CLOSE)")
print("=" * 70)

buyer_token = login('realtest1@e2e.com', 'Test1234!')
bp = decode_jwt(buyer_token)
buyer_id = int(bp['sub'])

seller_token = login('seller@yeokping.com', 'seller1234!')
sp = decode_jwt(seller_token)
seller_id = sp.get('seller_id', int(sp['sub']))

admin_token = login('admin@yeokping.com', 'admin1234!')
admin_id = int(decode_jwt(admin_token)['sub'])
print(f"Buyer: id={buyer_id}, Seller: seller_id={seller_id}, Admin: id={admin_id}")

# ---- Setup: Deal + Offer + Reservation + Pay + Ship ----
print("\n--- Setup: Pipeline for dispute ---")
deal_body = {
    "product_name": "QA Round7 Dispute Test Item",
    "creator_id": buyer_id, "category": "electronics", "brand": "Test",
    "condition": "new", "desired_qty": 2, "target_price": 200000,
    "market_price": 250000, "anchor_price": 250000
}
code, deal = api('POST', '/deals/', buyer_token, deal_body)
deal_id = deal['id']

offer_body = {
    'deal_id': deal_id, 'seller_id': seller_id, 'price': 195000,
    'total_available_qty': 5, 'delivery_days': 2, 'shipping_mode': 'INCLUDED',
    'option_agreement': True
}
code, offer = api('POST', '/offers', seller_token, offer_body)
offer_id = offer['id']

resv_body = {"deal_id": deal_id, "offer_id": offer_id, "buyer_id": buyer_id, "qty": 1}
code, resv = api('POST', '/v3_6/reservations', buyer_token, resv_body)
resv_id = resv['id']
order_number = resv.get('order_number')
amount = resv.get('amount_total', 195000)

pay_body = {"reservation_id": resv_id, "buyer_id": buyer_id, "paid_amount": amount}
code, pay = api('POST', '/v3_6/reservations/pay', buyer_token, pay_body)

ship_body = {"tracking_number": "DISPUTE123456", "shipping_carrier": "Test Carrier"}
code, ship = api('POST', f'/v3_6/reservations/{resv_id}/ship', seller_token, ship_body)
print(f"Deal={deal_id}, Offer={offer_id}, Resv={resv_id}, Order={order_number}")

# ============================================================
print("\n" + "=" * 70)
print("STEP 2A: OPEN DISPUTE")
print("=" * 70)

dispute_body = {
    "buyer_id": buyer_id,
    "reason": "Product defective - QA Round 7 test dispute"
}
code, dispute = api('POST', f'/v3_6/{resv_id}/dispute/open', buyer_token, dispute_body)
if check("DISPUTE OPEN: Accepted", code in (200, 201), f"code={code}, result={str(dispute)[:200]}"):
    if isinstance(dispute, dict):
        print(f"  is_disputed: {dispute.get('is_disputed')}")
        print(f"  dispute_opened_at: {dispute.get('dispute_opened_at')}")
        print(f"  dispute_reason: {dispute.get('dispute_reason')}")

# ---- Verify dispute open ----
print("\n--- Verify dispute open ---")
code, r = api('GET', f'/v3_6/reservations/by-id/{resv_id}', buyer_token)
if check("CP-1a: Returns 200", code == 200, f"code={code}"):
    check("CP-1b: is_disputed is True", r.get('is_disputed') == True,
          f"got={r.get('is_disputed')}")
    check("CP-1c: dispute_opened_at set", r.get('dispute_opened_at') is not None,
          f"got={r.get('dispute_opened_at')}")
    check("CP-1d: dispute_reason saved", r.get('dispute_reason') is not None,
          f"got={r.get('dispute_reason')}")

# Buyer sees disputed
code, br = api('GET', f'/v3_6/search?buyer_id={buyer_id}&limit=10', buyer_token)
if check("CP-2a: Buyer search returns 200", code == 200):
    items = br if isinstance(br, list) else []
    found = next((rv for rv in items if rv.get('id') == resv_id), None)
    check("CP-2b: Buyer sees disputed", found is not None and found.get('is_disputed') == True,
          f"found={found is not None}, is_disputed={found.get('is_disputed') if found else 'N/A'}")

# Seller sees disputed
code, sr = api('GET', f'/v3_6/search?seller_id={seller_id}&limit=10', seller_token)
if check("CP-3a: Seller search returns 200", code == 200):
    items = sr if isinstance(sr, list) else []
    found = next((rv for rv in items if rv.get('id') == resv_id), None)
    check("CP-3b: Seller sees disputed", found is not None and found.get('is_disputed') == True,
          f"found={found is not None}")

# Admin sees disputed
code, ar = api('GET', '/admin/reservations?limit=20', admin_token)
if check("CP-4a: Admin returns 200", code == 200):
    items = ar.get('items', ar) if isinstance(ar, dict) else ar
    if isinstance(items, list):
        found = next((rv for rv in items if rv.get('id') == resv_id), None)
        check("CP-4b: Admin sees disputed", found is not None,
              f"checked {len(items)}")

# Search by is_disputed filter
code, dr = api('GET', '/v3_6/search?is_disputed=true&limit=10', admin_token)
if check("CP-5a: Disputed filter returns 200", code == 200):
    items = dr if isinstance(dr, list) else []
    found = any(rv.get('id') == resv_id for rv in items)
    check("CP-5b: Found via disputed filter", found, f"checked {len(items)}")

# ============================================================
print("\n" + "=" * 70)
print("STEP 2B: CLOSE DISPUTE")
print("=" * 70)

close_body = {
    "admin_id": admin_id,
    "resolution": "Refund approved after inspection - QA test"
}
code, close_result = api('POST', f'/v3_6/{resv_id}/dispute/close', admin_token, close_body)
if check("DISPUTE CLOSE: Accepted", code in (200, 201), f"code={code}, result={str(close_result)[:200]}"):
    if isinstance(close_result, dict):
        print(f"  is_disputed: {close_result.get('is_disputed')}")
        print(f"  dispute_closed_at: {close_result.get('dispute_closed_at')}")
        print(f"  dispute_resolution: {close_result.get('dispute_resolution')}")

# ---- Verify dispute closed ----
print("\n--- Verify dispute closed ---")
code, r2 = api('GET', f'/v3_6/reservations/by-id/{resv_id}', buyer_token)
if check("CP-6a: Returns 200", code == 200):
    check("CP-6b: is_disputed now False", r2.get('is_disputed') == False,
          f"got={r2.get('is_disputed')}")
    check("CP-6c: dispute_closed_at set", r2.get('dispute_closed_at') is not None,
          f"got={r2.get('dispute_closed_at')}")
    check("CP-6d: dispute_resolution saved", r2.get('dispute_resolution') is not None,
          f"got={r2.get('dispute_resolution')}")

# ============================================================
print("\n" + "=" * 70)
print("ROUND 7 SUMMARY")
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
    "round": 7, "entity": "Dispute",
    "reservation_id": resv_id, "order_number": order_number,
    "checkpoints": total, "PASS": pass_count, "FAIL": fail_count,
    "details": results
}
with open('round7-dispute-report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  Report saved: round7-dispute-report.json")
print(f"\n  Result: {pass_count}/{total} PASS")
