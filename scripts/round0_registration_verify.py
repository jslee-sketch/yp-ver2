#!/usr/bin/env python3
"""Round 0: 회원가입 + 로그인 + 역할별 접근 전체 검증
Sub-rounds:
  0-A: 구매자 회원가입
  0-B: 판매자 회원가입 + 관리자 승인
  0-C: 소셜 로그인 (API 레벨)
  0-D: 비밀번호 재설정
  0-E: 역할별 접근 제어
  0-F: 참여자 상관관계 전수 검증
"""
import urllib.request, json, urllib.parse, base64, sys, time, random, string

base = 'https://web-production-defb.up.railway.app'
results = []
sub_results = {}  # sub_round -> list of results

current_sub = "0-A"

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
    global current_sub
    status = "PASS" if condition else "FAIL"
    entry = {"name": name, "status": status, "detail": str(detail)[:200], "sub_round": current_sub}
    results.append(entry)
    if current_sub not in sub_results:
        sub_results[current_sub] = []
    sub_results[current_sub].append(entry)
    print(f"  {'[PASS]' if condition else '[FAIL]'} {name}")
    if detail and not condition:
        print(f"         -> {str(detail)[:200]}")
    return condition

# Unique suffix for test accounts
suffix = ''.join(random.choices(string.digits, k=4))
buyer_email = f"qa_buyer_{suffix}@test.com"
buyer_pw = "QaTest1234!"
buyer_nickname = f"QA구매자{suffix}"
seller_email = f"qa_seller_{suffix}@test.com"
seller_pw = "QaTest1234!"
seller_nickname = f"QA판매자{suffix}"

# Admin login first
admin_token = login('admin@yeokping.com', 'admin1234!')
admin_id = int(decode_jwt(admin_token)['sub'])

# ============================================================
# ROUND 0-A: 구매자 회원가입
# ============================================================
current_sub = "0-A"
print("=" * 70)
print(f"ROUND 0-A: 구매자 회원가입 ({buyer_email})")
print("=" * 70)

# CP-1: 닉네임 중복 체크 API
print("\n--- CP-1: 닉네임 중복 체크 ---")
code, nick_chk = api('GET', f'/users/check-nickname?nickname={urllib.parse.quote(buyer_nickname)}')
if check("CP-1a: Nickname check returns 200", code == 200, f"code={code}"):
    check("CP-1b: Nickname available", nick_chk.get('available') == True,
          f"got={nick_chk}")

# CP-2: 이미 있는 닉네임 체크
code, nick_dup = api('GET', f'/users/check-nickname?nickname={urllib.parse.quote("admin")}')
if check("CP-2a: Banned nickname check returns 200", code == 200, f"code={code}"):
    check("CP-2b: Banned nickname rejected", nick_dup.get('available') == False,
          f"got={nick_dup}")

# CP-3: 이메일 중복 체크 API
print("\n--- CP-3: 이메일 중복 체크 ---")
code, email_chk = api('GET', f'/auth/check-email?email={urllib.parse.quote(buyer_email)}')
if check("CP-3a: Email check returns 200", code == 200, f"code={code}"):
    check("CP-3b: Email available", email_chk.get('available') == True,
          f"got={email_chk}")

# CP-4: 이미 가입된 이메일 체크
code, email_dup = api('GET', f'/auth/check-email?email={urllib.parse.quote("admin@yeokping.com")}')
if check("CP-4a: Existing email check returns 200", code == 200, f"code={code}"):
    check("CP-4b: Existing email rejected", email_dup.get('available') == False,
          f"got={email_dup}")

# CP-5: 구매자 회원가입
print("\n--- CP-5: 구매자 회원가입 ---")
buyer_body = {
    "email": buyer_email,
    "name": f"QA테스트구매자{suffix}",
    "nickname": buyer_nickname,
    "password": buyer_pw,
    "phone": f"010-9999-{suffix}",
    "address": "서울시 강남구 테스트로 123",
    "zip_code": "06000"
}
code, buyer = api('POST', '/buyers/', None, buyer_body)
buyer_id = None
if check("CP-5a: Buyer register returns 200/201", code in (200, 201), f"code={code}, data={str(buyer)[:200]}"):
    buyer_id = buyer.get('id')
    check("CP-5b: id returned", buyer_id is not None, f"got={buyer_id}")
    check("CP-5c: email matches", buyer.get('email') == buyer_email, f"got={buyer.get('email')}")
    check("CP-5d: nickname matches", buyer.get('nickname') == buyer_nickname, f"got={buyer.get('nickname')}")
    check("CP-5e: created_at set", buyer.get('created_at') is not None, f"got={buyer.get('created_at')}")
    print(f"  Buyer ID: {buyer_id}")

# CP-6: 가입 후 이메일 중복 체크 → 불가능
print("\n--- CP-6: 가입 후 이메일 재확인 ---")
code, email_after = api('GET', f'/auth/check-email?email={urllib.parse.quote(buyer_email)}')
if check("CP-6a: Returns 200", code == 200, f"code={code}"):
    check("CP-6b: Email no longer available", email_after.get('available') == False,
          f"got={email_after}")

# CP-7: 로그인
print("\n--- CP-7: 구매자 로그인 ---")
try:
    buyer_token = login(buyer_email, buyer_pw)
    bp = decode_jwt(buyer_token)
    check("CP-7a: Login success", True, "token received")
    check("CP-7b: JWT role is buyer", bp.get('role') == 'buyer', f"got={bp.get('role')}")
    check("CP-7c: JWT sub matches", str(bp.get('sub')) == str(buyer_id), f"sub={bp.get('sub')}, id={buyer_id}")
except Exception as e:
    check("CP-7a: Login success", False, str(e))
    buyer_token = None

# CP-8: 프로필 조회
print("\n--- CP-8: 프로필 조회 ---")
if buyer_id:
    code, profile = api('GET', f'/buyers/{buyer_id}', buyer_token)
    if check("CP-8a: Buyer profile returns 200", code == 200, f"code={code}"):
        check("CP-8b: Profile has email", profile.get('email') == buyer_email, f"got={profile.get('email')}")
        check("CP-8c: Profile has nickname", profile.get('nickname') == buyer_nickname, f"got={profile.get('nickname')}")

# CP-9: 대시보드 접근
print("\n--- CP-9: 대시보드 ---")
if buyer_id:
    code, dash = api('GET', f'/dashboard/buyer/{buyer_id}', buyer_token)
    check("CP-9: Buyer dashboard returns 200", code == 200, f"code={code}")

# CP-10: 포인트 초기값
print("\n--- CP-10: 포인트 ---")
if buyer_id:
    code, pts = api('GET', f'/points/buyer/{buyer_id}/balance', buyer_token)
    if check("CP-10a: Points endpoint returns 200", code == 200, f"code={code}"):
        bal = pts.get('balance', pts.get('points', -1)) if isinstance(pts, dict) else -1
        check("CP-10b: Initial balance >= 0", bal >= 0, f"got={bal}")

# CP-11: SPA 페이지
print("\n--- CP-11: SPA 페이지 ---")
for path, name in [('/register', 'Register Page'), ('/login', 'Login Page')]:
    req_obj = urllib.request.Request(f'{base}{path}')
    try:
        resp = urllib.request.urlopen(req_obj)
        body = resp.read().decode()[:500]
        is_spa = '<div id=' in body.lower() or '<!doctype' in body.lower()
        check(f"CP-11: {name} loads", resp.status == 200 and is_spa, f"status={resp.status}")
    except urllib.error.HTTPError as e:
        check(f"CP-11: {name} loads", False, f"HTTP {e.code}")


# ============================================================
# ROUND 0-B: 판매자 회원가입 + 관리자 승인
# ============================================================
current_sub = "0-B"
print("\n" + "=" * 70)
print(f"ROUND 0-B: 판매자 회원가입 ({seller_email})")
print("=" * 70)

# CP-1: 판매자 닉네임 체크
print("\n--- CP-1: 판매자 닉네임 체크 ---")
code, snick = api('GET', f'/users/check-nickname?nickname={urllib.parse.quote(seller_nickname)}')
if check("CP-1: Seller nickname available", code == 200 and snick.get('available') == True,
          f"code={code}, data={snick}"):
    pass

# CP-2: 판매자 이메일 체크
code, semail = api('GET', f'/auth/check-email?email={urllib.parse.quote(seller_email)}')
check("CP-2: Seller email available", code == 200 and semail.get('available') == True,
      f"code={code}, data={semail}")

# CP-3: 판매자 회원가입
print("\n--- CP-3: 판매자 회원가입 ---")
seller_body = {
    "email": seller_email,
    "business_name": f"QA테스트상점{suffix}",
    "nickname": seller_nickname,
    "business_number": f"123{suffix}67890",
    "phone": f"010-8888-{suffix}",
    "address": "서울시 서초구 테스트대로 456",
    "zip_code": "06500",
    "established_date": "2020-01-01T00:00:00",
    "password": seller_pw,
    "bank_name": "국민은행",
    "account_number": "123-456-789012",
    "account_holder": f"QA판매자{suffix}"
}
code, seller = api('POST', '/sellers/', None, seller_body)
new_seller_id = None
if check("CP-3a: Seller register returns 200/201", code in (200, 201), f"code={code}, data={str(seller)[:200]}"):
    new_seller_id = seller.get('id')
    check("CP-3b: id returned", new_seller_id is not None, f"got={new_seller_id}")
    check("CP-3c: email matches", seller.get('email') == seller_email, f"got={seller.get('email')}")
    check("CP-3d: nickname matches", seller.get('nickname') == seller_nickname, f"got={seller.get('nickname')}")
    check("CP-3e: business_name set", seller.get('business_name') is not None, f"got={seller.get('business_name')}")
    check("CP-3f: Level is 6 (default)", seller.get('level') == 6 or seller.get('level') is None,
          f"got={seller.get('level')}")
    # verified_at should be None (not yet approved)
    check("CP-3g: Not verified yet", seller.get('verified_at') is None,
          f"got={seller.get('verified_at')}")
    print(f"  Seller ID: {new_seller_id}")

# CP-4: 판매자 로그인 (미승인 상태)
print("\n--- CP-4: 판매자 로그인 (미승인) ---")
try:
    seller_token_new = login(seller_email, seller_pw)
    sp_new = decode_jwt(seller_token_new)
    check("CP-4a: Seller login success", True, "token received")
    check("CP-4b: JWT role is seller", sp_new.get('role') == 'seller', f"got={sp_new.get('role')}")
    check("CP-4c: JWT has seller_id", sp_new.get('seller_id') is not None, f"got={sp_new}")
    verified_claim = sp_new.get('verified', False)
    check("CP-4d: JWT verified=false (unverified)", verified_claim == False,
          f"got={verified_claim}")
except Exception as e:
    check("CP-4a: Seller login success", False, str(e))
    seller_token_new = None

# CP-5: 판매자 프로필 조회
print("\n--- CP-5: 판매자 프로필 ---")
if new_seller_id:
    code, sprof = api('GET', f'/sellers/{new_seller_id}', seller_token_new)
    if check("CP-5a: Seller profile returns 200", code == 200, f"code={code}"):
        check("CP-5b: Has business_number", sprof.get('business_number') is not None,
              f"got={sprof.get('business_number')}")
        check("CP-5c: Has bank_name", sprof.get('bank_name') is not None,
              f"got={sprof.get('bank_name')}")

# CP-6: 관리자 승인
print("\n--- CP-6: 관리자 승인 ---")
if new_seller_id:
    code, approve = api('POST', f'/sellers/{new_seller_id}/approve', admin_token)
    if check("CP-6a: Approve returns 200", code == 200, f"code={code}, data={str(approve)[:200]}"):
        # Re-fetch seller to verify
        code, sprof2 = api('GET', f'/sellers/{new_seller_id}', admin_token)
        if code == 200:
            check("CP-6b: verified_at is now set", sprof2.get('verified_at') is not None,
                  f"got={sprof2.get('verified_at')}")

    # Re-login to get updated JWT
    try:
        seller_token_new = login(seller_email, seller_pw)
        sp_new2 = decode_jwt(seller_token_new)
        check("CP-6c: JWT verified=true after approval", sp_new2.get('verified') == True,
              f"got={sp_new2.get('verified')}")
    except Exception as e:
        check("CP-6c: JWT verified after approval", False, str(e))

# CP-7: 판매자 대시보드
print("\n--- CP-7: 판매자 대시보드 ---")
if new_seller_id:
    code, sdash = api('GET', f'/dashboard/seller/{new_seller_id}', seller_token_new)
    check("CP-7: Seller dashboard returns 200", code == 200, f"code={code}")

# CP-8: 관리자에서 판매자 목록
print("\n--- CP-8: 관리자 판매자 목록 ---")
code, sellers_list = api('GET', '/sellers/?limit=500', admin_token)
if check("CP-8a: Sellers list returns 200", code == 200, f"code={code}"):
    items = sellers_list if isinstance(sellers_list, list) else sellers_list.get('items', [])
    if isinstance(items, list):
        found = any(s.get('id') == new_seller_id for s in items)
        check("CP-8b: New seller found in list", found, f"checked {len(items)}")


# ============================================================
# ROUND 0-C: 소셜 로그인 (API 레벨)
# ============================================================
current_sub = "0-C"
print("\n" + "=" * 70)
print("ROUND 0-C: 소셜 로그인 (API 레벨)")
print("=" * 70)

# CP-1: 카카오 OAuth URL
print("\n--- CP-1: Social OAuth URLs ---")
for provider in ['kakao', 'naver', 'google']:
    code, auth_url = api('GET', f'/auth/social/{provider}/authorize')
    if check(f"CP-1: {provider} authorize returns 200", code == 200, f"code={code}"):
        url = auth_url.get('url', '') if isinstance(auth_url, dict) else ''
        check(f"CP-1: {provider} URL contains auth domain",
              len(url) > 20 and ('kakao' in url or 'naver' in url or 'google' in url or 'accounts' in url),
              f"url={url[:100]}")

# CP-2: Social register endpoint exists (dry run with invalid data)
print("\n--- CP-2: Social register endpoint ---")
code, sr = api('POST', '/auth/social/register', None, {
    "social_provider": "kakao",
    "social_id": "test_invalid",
    "social_email": "test@invalid.com",
    "social_name": "Test",
    "role": "buyer",
    "nickname": f"SocialTest{suffix}"
})
# Should return 422 (validation) or 400 (business logic), not 404/500
check("CP-2: Social register endpoint exists", code in (200, 201, 400, 422, 409),
      f"code={code}")


# ============================================================
# ROUND 0-D: 비밀번호 재설정
# ============================================================
current_sub = "0-D"
print("\n" + "=" * 70)
print("ROUND 0-D: 비밀번호 재설정")
print("=" * 70)

# CP-1: Reset password request
print("\n--- CP-1: Password reset request ---")
code, reset = api('POST', '/auth/reset-password', None, {"email": buyer_email})
check("CP-1: Reset password request returns 200", code == 200, f"code={code}, data={str(reset)[:200]}")

# CP-2: Reset password with invalid token
print("\n--- CP-2: Reset token verify ---")
code, verify = api('GET', '/auth/reset-password/verify?token=invalid_token_12345')
# 400 or 200 both acceptable — invalid token should be rejected
if check("CP-2a: Verify endpoint responds", code in (200, 400, 422), f"code={code}"):
    if code == 200:
        check("CP-2b: Invalid token rejected", verify.get('valid') == False,
              f"got={verify}")
    else:
        check("CP-2b: Invalid token rejected (via HTTP status)", True, f"code={code}")

# CP-3: Reset confirm with invalid token
print("\n--- CP-3: Reset confirm ---")
code, confirm = api('POST', '/auth/reset-password/confirm', None, {
    "token": "invalid_token_12345",
    "new_password": "NewPass1234!"
})
check("CP-3: Invalid token confirm rejected", code in (400, 422), f"code={code}")

# CP-4: Change password (valid)
print("\n--- CP-4: Change password ---")
if buyer_token:
    code, chg = api('POST', '/auth/change-password', buyer_token, {
        "user_id": buyer_id,
        "user_type": "buyer",
        "current_password": buyer_pw,
        "new_password": "QaTest1234!New"
    })
    if check("CP-4a: Change password returns 200", code == 200, f"code={code}, data={str(chg)[:200]}"):
        # Login with new password
        try:
            new_token = login(buyer_email, "QaTest1234!New")
            check("CP-4b: Login with new password works", True, "")
            # Change back
            api('POST', '/auth/change-password', new_token, {
                "user_id": buyer_id,
                "user_type": "buyer",
                "current_password": "QaTest1234!New",
                "new_password": buyer_pw
            })
            buyer_token = login(buyer_email, buyer_pw)
        except Exception as e:
            check("CP-4b: Login with new password works", False, str(e))


# ============================================================
# ROUND 0-E: 역할별 접근 제어
# ============================================================
current_sub = "0-E"
print("\n" + "=" * 70)
print("ROUND 0-E: 역할별 접근 제어")
print("=" * 70)

# CP-1: 구매자 접근 가능 페이지
print("\n--- CP-1: 구매자 접근 ---")
buyer_ok_paths = ['/deals/', '/my-orders', '/login', '/register']
for path in buyer_ok_paths:
    req_obj = urllib.request.Request(f'{base}{path}')
    try:
        resp = urllib.request.urlopen(req_obj)
        check(f"CP-1: Buyer can access {path}", resp.status == 200, f"status={resp.status}")
    except urllib.error.HTTPError as e:
        check(f"CP-1: Buyer can access {path}", False, f"HTTP {e.code}")

# CP-2: 구매자 API 접근
print("\n--- CP-2: 구매자 API ---")
if buyer_token and buyer_id:
    code, _ = api('GET', f'/v3_6/search?buyer_id={buyer_id}&limit=5', buyer_token)
    check("CP-2a: Buyer can search own reservations", code == 200, f"code={code}")

    code, _ = api('GET', f'/dashboard/buyer/{buyer_id}', buyer_token)
    check("CP-2b: Buyer can access own dashboard", code == 200, f"code={code}")

# CP-3: 비로그인 → 보호된 API 접근 불가
print("\n--- CP-3: 비로그인 접근 ---")
code, _ = api('GET', '/admin/reservations?limit=5', None)
check("CP-3a: No-auth admin API rejected", code in (401, 403, 422), f"code={code}")

code, _ = api('POST', '/deals/', None, {"product_name": "test"})
check("CP-3b: No-auth deal creation rejected", code in (401, 403, 422), f"code={code}")

# CP-4: 구매자 → 관리자 API 접근 불가
print("\n--- CP-4: 구매자 → 관리자 접근 ---")
if buyer_token:
    code, _ = api('GET', '/admin/reservations?limit=5', buyer_token)
    check("CP-4: Buyer cannot access admin API", code in (401, 403), f"code={code}")

# CP-5: 판매자 → 관리자 API 접근 불가
print("\n--- CP-5: 판매자 → 관리자 접근 ---")
if seller_token_new:
    code, _ = api('GET', '/admin/reservations?limit=5', seller_token_new)
    check("CP-5: Seller cannot access admin API", code in (401, 403), f"code={code}")

# CP-6: 관리자 → 모든 API 접근 가능
print("\n--- CP-6: 관리자 전체 접근 ---")
code, _ = api('GET', '/admin/reservations?limit=5', admin_token)
check("CP-6a: Admin can access admin API", code == 200, f"code={code}")

code, _ = api('GET', '/admin/settlements/?limit=5', admin_token)
check("CP-6b: Admin can access settlements", code == 200, f"code={code}")

# CP-7: 공개 페이지 접근
print("\n--- CP-7: 공개 페이지 ---")
code, _ = api('GET', '/health', None)
check("CP-7a: Health check public", code == 200, f"code={code}")

code, _ = api('GET', '/deals/', None)
check("CP-7b: Deals list public", code == 200, f"code={code}")


# ============================================================
# ROUND 0-F: 참여자 상관관계 전수 검증
# ============================================================
current_sub = "0-F"
print("\n" + "=" * 70)
print("ROUND 0-F: 참여자 상관관계 전수 검증")
print("=" * 70)

# Use existing test accounts for cross-relationship testing
existing_buyer_token = login('realtest1@e2e.com', 'Test1234!')
existing_bp = decode_jwt(existing_buyer_token)
existing_buyer_id = int(existing_bp['sub'])

existing_seller_token = login('seller@yeokping.com', 'seller1234!')
existing_sp = decode_jwt(existing_seller_token)
existing_seller_id = existing_sp.get('seller_id', int(existing_sp['sub']))

# CP-1: 구매자-판매자 거래 연결
print("\n--- CP-1: 구매자-판매자 거래 연결 ---")
# Create deal → offer → reservation flow
deal_body = {
    "product_name": f"QA Round0-F Cross Test {suffix}",
    "creator_id": existing_buyer_id, "category": "electronics", "brand": "Test",
    "condition": "new", "desired_qty": 1, "target_price": 100000,
    "market_price": 120000, "anchor_price": 120000
}
code, deal = api('POST', '/deals/', existing_buyer_token, deal_body)
test_deal_id = deal.get('id') if code in (200, 201) else None
check("CP-1a: Deal created", test_deal_id is not None, f"code={code}")

if test_deal_id:
    offer_body = {
        'deal_id': test_deal_id, 'seller_id': existing_seller_id, 'price': 95000,
        'total_available_qty': 5, 'delivery_days': 2, 'shipping_mode': 'INCLUDED',
        'option_agreement': True
    }
    code, offer = api('POST', '/offers', existing_seller_token, offer_body)
    test_offer_id = offer.get('id') if code in (200, 201) else None
    check("CP-1b: Offer created", test_offer_id is not None, f"code={code}")

    if test_offer_id:
        resv_body = {"deal_id": test_deal_id, "offer_id": test_offer_id, "buyer_id": existing_buyer_id, "qty": 1}
        code, resv = api('POST', '/v3_6/reservations', existing_buyer_token, resv_body)
        test_resv_id = resv.get('id') if code in (200, 201) else None
        check("CP-1c: Reservation created", test_resv_id is not None, f"code={code}")

        if test_resv_id:
            # Buyer sees reservation
            code, br = api('GET', f'/v3_6/search?buyer_id={existing_buyer_id}&limit=10', existing_buyer_token)
            if code == 200:
                items = br if isinstance(br, list) else []
                found = any(r.get('id') == test_resv_id for r in items)
                check("CP-1d: Buyer sees own reservation", found, f"checked {len(items)}")

            # Seller sees reservation
            code, sr = api('GET', f'/v3_6/search?seller_id={existing_seller_id}&limit=10', existing_seller_token)
            if code == 200:
                items = sr if isinstance(sr, list) else []
                found = any(r.get('id') == test_resv_id for r in items)
                check("CP-1e: Seller sees buyer's reservation", found, f"checked {len(items)}")

            # Admin sees reservation
            code, ar = api('GET', '/admin/reservations?limit=20', admin_token)
            if code == 200:
                items = ar.get('items', ar) if isinstance(ar, dict) else ar
                if isinstance(items, list):
                    found = any(r.get('id') == test_resv_id for r in items)
                    check("CP-1f: Admin sees reservation", found, f"checked {len(items)}")

# CP-2: 닉네임 표시 (개인정보 보호)
print("\n--- CP-2: 닉네임 표시 ---")
# Buyer profile should show nickname
if existing_buyer_id:
    code, bp = api('GET', f'/buyers/{existing_buyer_id}', existing_buyer_token)
    if check("CP-2a: Buyer profile returns 200", code == 200, f"code={code}"):
        check("CP-2b: Buyer has nickname", bp.get('nickname') is not None, f"got={bp.get('nickname')}")

if existing_seller_id:
    code, sp = api('GET', f'/sellers/{existing_seller_id}', existing_seller_token)
    if check("CP-2c: Seller profile returns 200", code == 200, f"code={code}"):
        check("CP-2d: Seller has nickname", sp.get('nickname') is not None, f"got={sp.get('nickname')}")

# CP-3: 판매자 레벨 + 수수료
print("\n--- CP-3: 판매자 레벨/수수료 ---")
code, level_info = api('GET', f'/reviews/seller/{existing_seller_id}/level', existing_seller_token)
if check("CP-3a: Seller level returns 200", code == 200, f"code={code}"):
    level = level_info.get('level', level_info.get('seller_level'))
    check("CP-3b: Level is valid (1-6)", level is not None and 1 <= int(level) <= 6 if level else False,
          f"got={level}")

# CP-4: 알림 시스템 — 각 역할별
print("\n--- CP-4: 알림 시스템 ---")
code, bn = api('GET', f'/notifications/?user_id={existing_buyer_id}&limit=5', existing_buyer_token)
check("CP-4a: Buyer notifications accessible", code == 200, f"code={code}")

code, sn = api('GET', f'/notifications/?user_id={existing_seller_id}&limit=5', existing_seller_token)
check("CP-4b: Seller notifications accessible", code == 200, f"code={code}")

# CP-5: 핑퐁이 — 역할별 답변
print("\n--- CP-5: 핑퐁이 역할별 ---")
code, ping_b = api('POST', '/v3_6/pingpong/ask', existing_buyer_token,
                    {"question": "내 주문 현황을 알려줘"})
check("CP-5a: Pingpong responds to buyer", code in (200, 201), f"code={code}")

code, ping_s = api('POST', '/v3_6/pingpong/ask', existing_seller_token,
                    {"question": "내 정산 현황을 알려줘"})
check("CP-5b: Pingpong responds to seller", code in (200, 201), f"code={code}")

# CP-6: 신규 계정으로 거래 가능 확인
print("\n--- CP-6: 신규 계정 거래 ---")
if buyer_token and buyer_id:
    deal_body2 = {
        "product_name": f"QA NewBuyer Deal {suffix}",
        "creator_id": buyer_id, "category": "electronics", "brand": "Test",
        "condition": "new", "desired_qty": 1, "target_price": 50000,
        "market_price": 60000, "anchor_price": 60000
    }
    code, new_deal = api('POST', '/deals/', buyer_token, deal_body2)
    check("CP-6a: New buyer can create deal", code in (200, 201), f"code={code}")

    if new_seller_id and seller_token_new:
        new_deal_id = new_deal.get('id') if code in (200, 201) else None
        if new_deal_id:
            offer_body2 = {
                'deal_id': new_deal_id, 'seller_id': new_seller_id, 'price': 48000,
                'total_available_qty': 3, 'delivery_days': 3, 'shipping_mode': 'INCLUDED',
                'option_agreement': True
            }
            code, new_offer = api('POST', '/offers', seller_token_new, offer_body2)
            check("CP-6b: New seller can create offer", code in (200, 201),
                  f"code={code}, data={str(new_offer)[:200]}")


# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "=" * 70)
print("ROUND 0 FINAL SUMMARY")
print("=" * 70)

pass_count = sum(1 for r in results if r['status'] == 'PASS')
fail_count = sum(1 for r in results if r['status'] == 'FAIL')
total = len(results)

print(f"\n  Total checkpoints: {total}")
print(f"  PASS: {pass_count}, FAIL: {fail_count}")

# Sub-round summary
print("\n  Sub-round breakdown:")
for sub_id in sorted(sub_results.keys()):
    items = sub_results[sub_id]
    p = sum(1 for r in items if r['status'] == 'PASS')
    f = sum(1 for r in items if r['status'] == 'FAIL')
    t = len(items)
    print(f"    {sub_id}: {p}/{t} PASS" + (f" ({f} FAIL)" if f > 0 else ""))

if fail_count > 0:
    print(f"\n  FAILED items:")
    for r in results:
        if r['status'] == 'FAIL':
            print(f"    [{r['sub_round']}] {r['name']}: {r['detail']}")

report = {
    "round": "0",
    "entity": "Registration + Auth + Role Access",
    "checkpoints": total, "PASS": pass_count, "FAIL": fail_count,
    "sub_rounds": {},
    "created_accounts": {
        "buyer": {"email": buyer_email, "password": buyer_pw, "id": buyer_id, "nickname": buyer_nickname},
        "seller": {"email": seller_email, "password": seller_pw, "id": new_seller_id, "nickname": seller_nickname},
    },
    "details": results
}

for sub_id in sorted(sub_results.keys()):
    items = sub_results[sub_id]
    p = sum(1 for r in items if r['status'] == 'PASS')
    f = sum(1 for r in items if r['status'] == 'FAIL')
    report["sub_rounds"][sub_id] = {"checkpoints": len(items), "PASS": p, "FAIL": f}

with open('round0-registration-report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n  Report saved: round0-registration-report.json")
print(f"\n  Result: {pass_count}/{total} PASS")
print(f"\n  대표님 확인:")
print(f"    신규 구매자: {buyer_email} / {buyer_pw}")
print(f"    신규 판매자: {seller_email} / {seller_pw}")
print(f"    관리자: admin@yeokping.com / admin1234!")
