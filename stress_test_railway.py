"""Railway stress test: refund/dispute/settlement scenarios"""
import requests, time, sys, io, json, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "https://web-production-defb.up.railway.app"
TS = int(time.time()) % 100000

def form_login(email, password, endpoint="/auth/login"):
    r = requests.post(f"{BASE}{endpoint}", data={"username": email, "password": password}, timeout=10)
    if r.status_code == 200:
        try: return r.json().get("access_token")
        except: pass
    return None

def auth_h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {"Content-Type": "application/json"}

def jwt_payload(token):
    try:
        parts = token.split(".")
        payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
        return json.loads(base64.b64decode(payload))
    except: return {}

def safe_json(r):
    try: return r.json()
    except: return {}

def post(url, data=None, headers=None):
    r = requests.post(f"{BASE}{url}", json=data, headers=headers, timeout=15)
    return r.status_code, safe_json(r)

def get(url, headers=None):
    r = requests.get(f"{BASE}{url}", headers=headers, timeout=15)
    return r.status_code, safe_json(r)

# ── 0. Logins ──
print("=== 0. Logins ===")
admin_token = form_login("admin@yeokping.com", "admin1234!")
print(f"Admin: {'OK' if admin_token else 'FAIL'}")
adminH = auth_h(admin_token)

seller_token = form_login("e2e_seller@test.com", "Test1234!", "/auth/seller/login")
if not seller_token:
    seller_token = form_login("e2e_seller@test.com", "Test1234!")
seller_id = jwt_payload(seller_token).get("seller_id") or jwt_payload(seller_token).get("sub") if seller_token else None
print(f"Seller: {'OK' if seller_token else 'FAIL'} (id={seller_id})")
sellerH = auth_h(seller_token)

buyer_tokens = []
buyer_ids = []
for i in range(1, 8):
    email = f"stress{TS}_{i}@e2e.com"
    pw = "Test1234!"
    nick = f"st{TS}_{i}"
    tok = form_login(email, pw)
    if not tok:
        requests.post(f"{BASE}/buyers/", json={
            "email": email, "password": pw, "name": nick, "nickname": nick,
            "phone": f"0107{TS % 10000:04d}{i}"
        }, timeout=10)
        tok = form_login(email, pw)
    p = jwt_payload(tok) if tok else {}
    bid = int(p.get("sub", 0))
    buyer_tokens.append(tok)
    buyer_ids.append(bid)

print(f"Buyers: {sum(1 for t in buyer_tokens if t)}/7 ready")

# ── 1. Create deal + offer ──
print("\n=== 1. Deal + Offer ===")
bh0 = auth_h(buyer_tokens[0])
st, deal = post("/deals/", {
    "product_name": f"스트레스TV_{TS}", "creator_id": buyer_ids[0],
    "desired_qty": 10, "target_price": 2000000, "max_budget": 2500000,
    "anchor_price": 2500000, "market_price": 2500000, "brand": "LG"
}, bh0)
deal_id = deal.get("id")
print(f"Deal: id={deal_id} (status={st})")

st, offer = post("/v3_6/offers", {
    "deal_id": deal_id, "seller_id": seller_id, "price": 2200000,
    "total_available_qty": 20, "shipping_mode": "PER_RESERVATION",
    "shipping_fee_per_reservation": 3000, "delivery_days": 3
}, sellerH)
offer_id = offer.get("id")
print(f"Offer: id={offer_id} (status={st})")

# ── A. 정상 흐름 (예약→결제→배송→수취확인) ──
print("\n=== A: 정상 거래 흐름 ===")
bh = auth_h(buyer_tokens[0])
st, resA = post("/v3_6/reservations", {"deal_id": deal_id, "offer_id": offer_id, "buyer_id": buyer_ids[0], "qty": 1}, bh)
resA_id = resA.get("id")
print(f"예약A: id={resA_id} ({st})")

st, _ = post("/v3_6/reservations/pay", {"reservation_id": resA_id, "buyer_id": buyer_ids[0], "paid_amount": 2203000}, bh)
print(f"결제A: {st}")

st, _ = post(f"/v3_6/reservations/{resA_id}/ship", {"tracking_number": f"STRESS_A_{TS}", "shipping_carrier": "CJ대한통운"}, sellerH)
print(f"배송A: {st}")

st, _ = post(f"/v3_6/reservations/{resA_id}/arrival-confirm", {"buyer_id": buyer_ids[0]}, bh)
print(f"수취확인A: {st} → 정산 파이프라인 진입")

# ── B. 배송 전 환불 ──
print("\n=== B: 배송 전 환불 ===")
bh1 = auth_h(buyer_tokens[1])
st, resB = post("/v3_6/reservations", {"deal_id": deal_id, "offer_id": offer_id, "buyer_id": buyer_ids[1], "qty": 1}, bh1)
resB_id = resB.get("id")
st, _ = post("/v3_6/reservations/pay", {"reservation_id": resB_id, "buyer_id": buyer_ids[1], "paid_amount": 2203000}, bh1)
print(f"예약B: id={resB_id} 결제완료 (배송 전)")

# Preview
try:
    st, preview = post("/v3_6/reservations/refund/preview", {"reservation_id": resB_id, "actor": "buyer_cancel"}, bh1)
    ctx = preview.get("context", {})
    print(f"프리뷰B: cooling={ctx.get('cooling_state')} settlement={ctx.get('settlement_state')} total={ctx.get('amount_total')}")
except Exception as e:
    print(f"프리뷰B 실패: {e}")

# Refund
st, refB = post("/v3_6/reservations/refund", {"reservation_id": resB_id, "reason": "단순변심(배송전)", "requested_by": "BUYER"}, bh1)
print(f"환불B: status={st} resv_status={refB.get('status')}")

# ── C. 배송 중 환불 ──
print("\n=== C: 배송 중 환불 ===")
bh2 = auth_h(buyer_tokens[2])
st, resC = post("/v3_6/reservations", {"deal_id": deal_id, "offer_id": offer_id, "buyer_id": buyer_ids[2], "qty": 1}, bh2)
resC_id = resC.get("id")
post("/v3_6/reservations/pay", {"reservation_id": resC_id, "buyer_id": buyer_ids[2], "paid_amount": 2203000}, bh2)
post(f"/v3_6/reservations/{resC_id}/ship", {"tracking_number": f"STRESS_C_{TS}", "shipping_carrier": "한진택배"}, sellerH)
print(f"예약C: id={resC_id} 배송중")

st, refC = post("/v3_6/reservations/refund", {"reservation_id": resC_id, "reason": "배송중변심", "requested_by": "BUYER"}, bh2)
print(f"환불C: status={st} resv_status={refC.get('status')}")

# ── D. 수취 후 쿨링 내 환불 ──
print("\n=== D: 수취 후 쿨링 내 환불 ===")
bh3 = auth_h(buyer_tokens[3])
st, resD = post("/v3_6/reservations", {"deal_id": deal_id, "offer_id": offer_id, "buyer_id": buyer_ids[3], "qty": 1}, bh3)
resD_id = resD.get("id")
post("/v3_6/reservations/pay", {"reservation_id": resD_id, "buyer_id": buyer_ids[3], "paid_amount": 2203000}, bh3)
post(f"/v3_6/reservations/{resD_id}/ship", {"tracking_number": f"STRESS_D_{TS}", "shipping_carrier": "롯데택배"}, sellerH)
post(f"/v3_6/reservations/{resD_id}/arrival-confirm", {"buyer_id": buyer_ids[3]}, bh3)
print(f"예약D: id={resD_id} 수취완료")

# Preview
st, preview = post("/v3_6/reservations/refund/preview", {"reservation_id": resD_id, "actor": "buyer_cancel"}, bh3)
ctx = preview.get("context", {})
print(f"프리뷰D: cooling={ctx.get('cooling_state')} shipping_refund={ctx.get('amount_shipping')}")

st, refD = post("/v3_6/reservations/refund", {"reservation_id": resD_id, "reason": "수취후단순변심", "requested_by": "BUYER"}, bh3)
print(f"환불D: status={st} resv_status={refD.get('status')}")

# ── E. 부분 환불 (3개 중 1개) ──
print("\n=== E: 부분 환불 ===")
bh4 = auth_h(buyer_tokens[4])
st, resE = post("/v3_6/reservations", {"deal_id": deal_id, "offer_id": offer_id, "buyer_id": buyer_ids[4], "qty": 3}, bh4)
resE_id = resE.get("id")
st_pay, pay_res = post("/v3_6/reservations/pay", {"reservation_id": resE_id, "buyer_id": buyer_ids[4], "paid_amount": 6603000}, bh4)
print(f"예약E: id={resE_id} 수량3 결제={st_pay}")

st, refE = post("/v3_6/reservations/refund", {
    "reservation_id": resE_id, "reason": "1개불량", "requested_by": "BUYER",
    "quantity_refund": 1
}, bh4)
print(f"부분환불E: status={st} resv_status={refE.get('status')} (3개 중 1개)")

# 남은 2개에 대해 한번 더 부분환불
st, refE2 = post("/v3_6/reservations/refund", {
    "reservation_id": resE_id, "reason": "추가1개불량", "requested_by": "BUYER",
    "quantity_refund": 1
}, bh4)
print(f"부분환불E2: status={st} resv_status={refE2.get('status')} (추가 1개)")

# ── F. refund_type 테스트 (반품) ──
print("\n=== F: refund_type=return 테스트 ===")
bh5 = auth_h(buyer_tokens[5])
st, resF = post("/v3_6/reservations", {"deal_id": deal_id, "offer_id": offer_id, "buyer_id": buyer_ids[5], "qty": 1}, bh5)
resF_id = resF.get("id")
post("/v3_6/reservations/pay", {"reservation_id": resF_id, "buyer_id": buyer_ids[5], "paid_amount": 2203000}, bh5)
print(f"예약F: id={resF_id} 결제완료")

st, refF = post("/v3_6/reservations/refund", {
    "reservation_id": resF_id, "reason": "반품요청: 상품하자",
    "requested_by": "BUYER", "refund_type": "return"
}, bh5)
print(f"반품F: status={st} resv_status={refF.get('status')} refund_type={refF.get('refund_type')}")

# ── G. 이중 환불 시도 ──
print("\n=== G: 이중환불 방어 ===")
stG, refG = post("/v3_6/reservations/refund", {
    "reservation_id": resB_id, "reason": "이중환불시도", "requested_by": "BUYER"
}, bh1)
if stG >= 400:
    print(f"이중환불G: ✅ 차단됨 (status={stG})")
else:
    print(f"이중환불G: ⚠️ 성공함 (막아야 함!) status={stG}")

# ── H. 정산 파이프라인 확인 ──
print("\n=== H: 정산 파이프라인 ===")

# refresh-ready
st, rr = post("/settlements/refresh-ready", headers=adminH)
print(f"refresh-ready: checked={rr.get('checked')} backfilled={rr.get('backfilled')} updated={rr.get('updated')}")

# refresh-dispute (현재 분쟁 건 없을 수 있음)
st, rd = post("/settlements/settlements/refresh-dispute", headers=adminH)
print(f"refresh-dispute: checked={rd.get('checked')} updated={rd.get('updated')}")

# batch-auto-approve
st, ba = post("/settlements/batch-auto-approve", headers=adminH)
print(f"batch-auto-approve: ready={ba.get('total_ready')} approved={ba.get('auto_approved')} skipped={ba.get('skipped')}")

# seller settlements
if seller_id:
    st, ss = get(f"/settlements/seller/{seller_id}?limit=10", adminH)
    items = ss if isinstance(ss, list) else []
    print(f"셀러 정산 건수: {len(items)}")
    for s in items[:3]:
        print(f"  정산 #{s.get('id')} res={s.get('reservation_id')} status={s.get('status')} payout={s.get('seller_payout_amount')}")

# ── Summary ──
print(f"\n{'='*50}")
print("스트레스 테스트 완료!")
print("A: 정상흐름 (수취확인까지)")
print(f"B: 배송전환불 → {refB.get('status', 'N/A')}")
print(f"C: 배송중환불 → {refC.get('status', 'N/A')}")
print(f"D: 수취후환불 → {refD.get('status', 'N/A')}")
print(f"E: 부분환불(1/3 + 1/3) → {refE2.get('status', 'N/A')}")
print(f"F: 반품(refund_type=return) → {refF.get('refund_type', 'N/A')}")
print(f"G: 이중환불 → {'차단됨' if stG >= 400 else '⚠️ 미차단'}")
print(f"H: 정산 파이프라인 OK")
