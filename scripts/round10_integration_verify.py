#!/usr/bin/env python3
"""Round 10: 전체 통합 검증 (Cross-cutting)
- Notification system
- Activity log
- Dashboard consistency
- Search / filter
- Admin overview
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
        except (json.JSONDecodeError, UnicodeDecodeError):
            return resp.status, {'_binary': True, '_len': len(raw)}
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode()[:500]
        except UnicodeDecodeError:
            return e.code, f"HTTP {e.code}"

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
print("ROUND 10: CROSS-CUTTING INTEGRATION")
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

# ============================================================
print("\n" + "=" * 70)
print("PHASE 1: NOTIFICATION SYSTEM")
print("=" * 70)

# CP-1: Buyer notifications
print("\n--- CP-1: Buyer notifications ---")
code, notif = api('GET', f'/notifications/?user_id={buyer_id}&limit=20', buyer_token)
if check("CP-1a: Buyer notifications returns 200", code == 200, f"code={code}"):
    items = notif.get('items', notif) if isinstance(notif, dict) else notif
    if isinstance(items, list):
        check("CP-1b: Buyer has notifications", len(items) > 0, f"count={len(items)}")
        if items:
            n = items[0]
            check("CP-1c: Notification has title", n.get('title') is not None,
                  f"got={n.get('title')}")
            check("CP-1d: Notification has created_at", n.get('created_at') is not None,
                  f"got={n.get('created_at')}")

# CP-2: Seller notifications
print("\n--- CP-2: Seller notifications ---")
code, notif_s = api('GET', f'/notifications/?user_id={seller_id}&limit=20', seller_token)
if check("CP-2a: Seller notifications returns 200", code == 200, f"code={code}"):
    items = notif_s.get('items', notif_s) if isinstance(notif_s, dict) else notif_s
    if isinstance(items, list):
        check("CP-2b: Seller has notifications", len(items) > 0, f"count={len(items)}")

# CP-3: Mark as read (POST /notifications/read_all with body)
print("\n--- CP-3: Mark notification as read ---")
code, mark = api('POST', '/notifications/read_all', buyer_token, {"user_id": buyer_id})
check("CP-3a: Mark all read returns 200", code == 200, f"code={code}, data={str(mark)[:200]}")
if isinstance(mark, dict):
    check("CP-3b: Updated count returned", 'updated' in mark, f"keys={list(mark.keys())}")

# CP-4: Verify all read (only_unread should return 0)
print("\n--- CP-4: Verify all read ---")
code, unread = api('GET', f'/notifications/?user_id={buyer_id}&only_unread=true&limit=100', buyer_token)
if check("CP-4a: Unread query returns 200", code == 200, f"code={code}"):
    items = unread if isinstance(unread, list) else unread.get('items', []) if isinstance(unread, dict) else []
    cnt = len(items)
    check("CP-4b: Unread count is 0 after mark-read", cnt == 0, f"unread={cnt}")

# ============================================================
print("\n" + "=" * 70)
print("PHASE 2: ACTIVITY LOG")
print("=" * 70)

# CP-5: Activity log exists
print("\n--- CP-5: Activity log ---")
code, activity = api('GET', '/activity-log/?limit=20', admin_token)
if check("CP-5a: Activity log returns 200", code == 200, f"code={code}"):
    items = activity.get('items', activity) if isinstance(activity, dict) else activity
    if isinstance(items, list):
        check("CP-5b: Activity log has entries", len(items) > 0, f"count={len(items)}")
        if items:
            entry = items[0]
            check("CP-5c: Entry has event_type", entry.get('event_type') is not None,
                  f"got={entry.get('event_type')}")

# CP-6: Activity log by deal
print("\n--- CP-6: Activity log by deal ---")
# Use a recent deal_id
code, deals = api('GET', '/deals/?limit=3', buyer_token)
recent_deal_id = None
if code == 200 and isinstance(deals, list) and len(deals) > 0:
    recent_deal_id = deals[0].get('id')
elif code == 200 and isinstance(deals, dict):
    dl = deals.get('items', [])
    if dl:
        recent_deal_id = dl[0].get('id')

if recent_deal_id:
    code, deal_log = api('GET', f'/activity-log/?deal_id={recent_deal_id}&limit=10', admin_token)
    check("CP-6: Deal activity log returns 200", code == 200, f"code={code}")
else:
    check("CP-6: Deal activity log (no deal found)", False, "no recent deal_id")

# ============================================================
print("\n" + "=" * 70)
print("PHASE 3: BUYER DASHBOARD")
print("=" * 70)

# CP-7: Buyer dashboard
print("\n--- CP-7: Buyer dashboard ---")
code, bd = api('GET', f'/dashboard/buyer/{buyer_id}', buyer_token)
if check("CP-7a: Returns 200", code == 200, f"code={code}"):
    check("CP-7b: Has stats", 'stats' in bd if isinstance(bd, dict) else False,
          f"keys={list(bd.keys()) if isinstance(bd, dict) else 'N/A'}")
    if isinstance(bd, dict):
        stats = bd.get('stats', {})
        resv_stats = stats.get('reservations', {})
        check("CP-7c: Has reservation stats", isinstance(resv_stats, dict),
              f"type={type(resv_stats)}")
        by_status = resv_stats.get('by_status', {})
        check("CP-7d: Has by_status breakdown", isinstance(by_status, dict),
              f"keys={list(by_status.keys()) if isinstance(by_status, dict) else 'N/A'}")
        pipeline = resv_stats.get('shipping_pipeline', {})
        check("CP-7e: Has shipping pipeline", isinstance(pipeline, dict),
              f"pipeline={pipeline}")

# ============================================================
print("\n" + "=" * 70)
print("PHASE 4: SELLER DASHBOARD")
print("=" * 70)

# CP-8: Seller dashboard
print("\n--- CP-8: Seller dashboard ---")
code, sd = api('GET', f'/dashboard/seller/{seller_id}', seller_token)
if check("CP-8a: Returns 200", code == 200, f"code={code}"):
    check("CP-8b: Has stats", 'stats' in sd if isinstance(sd, dict) else False,
          f"keys={list(sd.keys()) if isinstance(sd, dict) else 'N/A'}")

# ============================================================
print("\n" + "=" * 70)
print("PHASE 5: ADMIN ENDPOINTS")
print("=" * 70)

# CP-9: Admin reservations
print("\n--- CP-9: Admin reservations ---")
code, admin_resv = api('GET', '/admin/reservations?limit=10', admin_token)
if check("CP-9a: Admin reservations returns 200", code == 200, f"code={code}"):
    items = admin_resv.get('items', admin_resv) if isinstance(admin_resv, dict) else admin_resv
    if isinstance(items, list):
        check("CP-9b: Has reservation entries", len(items) > 0, f"count={len(items)}")

# CP-10: Admin settlements
print("\n--- CP-10: Admin settlements ---")
code, admin_stl = api('GET', '/admin/settlements/?limit=10', admin_token)
if check("CP-10a: Admin settlements returns 200", code == 200, f"code={code}"):
    items = admin_stl if isinstance(admin_stl, list) else admin_stl.get('items', [])
    check("CP-10b: Has settlement entries", isinstance(items, list) and len(items) > 0,
          f"count={len(items) if isinstance(items, list) else 'N/A'}")

# ============================================================
print("\n" + "=" * 70)
print("PHASE 6: SEARCH & FILTER CROSS-CHECK")
print("=" * 70)

# CP-11: Reservation search - buyer
print("\n--- CP-11: Buyer search ---")
code, bs = api('GET', f'/v3_6/search?buyer_id={buyer_id}&limit=10', buyer_token)
if check("CP-11a: Buyer search returns 200", code == 200, f"code={code}"):
    items = bs if isinstance(bs, list) else bs.get('items', [])
    check("CP-11b: Buyer has reservations", isinstance(items, list) and len(items) > 0,
          f"count={len(items) if isinstance(items, list) else 'N/A'}")
    if isinstance(items, list) and items:
        r = items[0]
        check("CP-11c: Has deal_id", r.get('deal_id') is not None,
              f"keys={list(r.keys())[:10]}")
        check("CP-11d: Has offer_id", r.get('offer_id') is not None,
              f"got={r.get('offer_id')}")
        check("CP-11e: Has order_number", r.get('order_number') is not None,
              f"got={r.get('order_number')}")

# CP-12: Reservation search - seller
print("\n--- CP-12: Seller search ---")
code, ss = api('GET', f'/v3_6/search?seller_id={seller_id}&limit=10', seller_token)
if check("CP-12a: Seller search returns 200", code == 200, f"code={code}"):
    items = ss if isinstance(ss, list) else ss.get('items', [])
    check("CP-12b: Seller has reservations", isinstance(items, list) and len(items) > 0,
          f"count={len(items) if isinstance(items, list) else 'N/A'}")

# ============================================================
print("\n" + "=" * 70)
print("PHASE 7: SPA PAGES")
print("=" * 70)

# CP-13: SPA pages
print("\n--- CP-13: SPA pages ---")
spa_pages = [
    ('/', 'Home'),
    ('/my-orders', 'My Orders'),
    ('/login', 'Login'),
]
for path, name in spa_pages:
    req = urllib.request.Request(f'{base}{path}')
    try:
        resp = urllib.request.urlopen(req)
        body = resp.read().decode()[:500]
        is_spa = '<div id=' in body.lower() or '<!doctype' in body.lower()
        check(f"CP-13: {name} page loads", resp.status == 200 and is_spa, f"status={resp.status}")
    except urllib.error.HTTPError as e:
        check(f"CP-13: {name} page loads", False, f"HTTP {e.code}")

# ============================================================
print("\n" + "=" * 70)
print("PHASE 8: HEALTH & CONFIG")
print("=" * 70)

# CP-14: Health check
print("\n--- CP-14: Health & config ---")
code, health = api('GET', '/health', None)
check("CP-14a: Health check returns 200", code == 200, f"code={code}")

# CP-15: Pingpong endpoint (uses "question" key)
print("\n--- CP-15: Pingpong AI ---")
ping_body = {"question": "플랫폼 수수료는 얼마인가요?"}
code, ping = api('POST', '/v3_6/pingpong/ask', buyer_token, ping_body)
check("CP-15: Pingpong responds", code in (200, 201), f"code={code}")

# CP-16: Preview pack
print("\n--- CP-16: Preview pack ---")
if recent_deal_id:
    code, pp = api('GET', f'/preview-pack/{recent_deal_id}', buyer_token)
    check("CP-16: Preview pack returns 200", code == 200, f"code={code}")
else:
    check("CP-16: Preview pack (no deal)", False, "no deal_id")

# ============================================================
print("\n" + "=" * 70)
print("ROUND 10 SUMMARY")
print("=" * 70)

pass_count = sum(1 for r in results if r['status'] == 'PASS')
fail_count = sum(1 for r in results if r['status'] == 'FAIL')
total = len(results)

print(f"\n  Total checkpoints: {total}")
print(f"  PASS: {pass_count}, FAIL: {fail_count}")

if fail_count > 0:
    print(f"\n  FAILED items:")
    for r in results:
        if r['status'] == 'FAIL':
            print(f"    - {r['name']}: {r['detail']}")

report = {
    "round": 10, "entity": "Cross-cutting Integration",
    "checkpoints": total, "PASS": pass_count, "FAIL": fail_count,
    "details": results
}
with open('round10-integration-report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  Report saved: round10-integration-report.json")
print(f"\n  Result: {pass_count}/{total} PASS")
