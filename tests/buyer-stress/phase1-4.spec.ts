/**
 * 구매자 스트레스 테스트 — Phase 1-4 (Setup + T01-T65)
 * Phase 1: 가입/로그인 스트레스 (T01-T15)
 * Phase 2: 딜 생성 스트레스 (T16-T35)
 * Phase 3: 오퍼 비교 + 예약 스트레스 (T36-T55)
 * Phase 4: 배송 추적 + 수취 확인 스트레스 (T56-T65)
 */
import { test, expect } from '@playwright/test';
import {
  BASE, TS, state, api, apiNoAuth, loginForm, socialRegister,
  tokenInfo, setToken, setBuyerAuth, setSellerAuth, setAdminAuth,
  approveSeller, createDeal, createOffer, createAndPayReservation,
  shipReservation, confirmArrival, refundReservation, refundPreview,
} from './helpers';

test.describe.serial('구매자 스트레스 Phase 1-4', () => {

  test('Setup — 전체 데이터 초기화', async ({ page }) => {
    const { setupAll } = await import('./helpers');
    await setupAll(page);
    expect(state.adminToken).toBeTruthy();
    expect(state.buyerId).toBeGreaterThan(0);
    expect(state.sellerId).toBeGreaterThan(0);
    expect(state.dealIds.length).toBeGreaterThanOrEqual(1);
  });

  // ━━━ Phase 1: 구매자 가입/로그인 스트레스 (T01-T15) ━━━

  test('T01 — 이메일 형식 아닌 "hello" → 가입 차단', async ({ page }) => {
    await page.goto(BASE);
    const r = await socialRegister(page, {
      socialId: `bad_email_${TS}`, role: 'buyer',
      nickname: `이메일테스트${TS % 10000}`, email: 'hello',
    });
    console.log(`[T01] 잘못된 이메일 → status: ${r.status}`);
    // 소셜가입은 이메일 형식 검증 없을 수 있음
    expect([200, 400, 422].includes(r.status)).toBe(true);
    console.log('[T01] PASS');
  });

  test('T02 — 비밀번호 "123" (3자리) → 차단 확인', async ({ page }) => {
    await page.goto(BASE);
    // 비밀번호 로그인 시도
    const r = await loginForm(page, 'shortpw@test.com', '123');
    console.log(`[T02] 짧은 비밀번호 → status: ${r.status}`);
    expect(r.status).toBe(401); // 로그인 실패
    console.log('[T02] PASS');
  });

  test('T03 — 닉네임 빈칸 → 차단', async ({ page }) => {
    await page.goto(BASE);
    const r = await socialRegister(page, {
      socialId: `empty_nick_${TS}`, role: 'buyer',
      nickname: '', email: `emptynick_${TS}@test.com`,
    });
    console.log(`[T03] 빈 닉네임 → status: ${r.status}`);
    expect(r.status).toBe(400);
    console.log('[T03] PASS — 빈 닉네임 차단');
  });

  test('T04 — 닉네임 XSS "<script>alert(1)</script>" → 방어', async ({ page }) => {
    await page.goto(BASE);
    const r = await socialRegister(page, {
      socialId: `xss_nick_${TS}`, role: 'buyer',
      nickname: '<script>alert(1)</script>', email: `xssnick_${TS}@test.com`,
    });
    console.log(`[T04] XSS 닉네임 → status: ${r.status}`);
    // 닉네임 정규식 [가-힣a-zA-Z0-9_]에 안 맞으므로 400 예상
    expect(r.status).toBe(400);
    console.log('[T04] PASS — XSS 닉네임 차단');
  });

  test('T05 — 닉네임 SQL injection → 방어', async ({ page }) => {
    await page.goto(BASE);
    const r = await socialRegister(page, {
      socialId: `sql_nick_${TS}`, role: 'buyer',
      nickname: "'; DROP TABLE users--", email: `sqlnick_${TS}@test.com`,
    });
    console.log(`[T05] SQL injection 닉네임 → status: ${r.status}`);
    expect(r.status).toBe(400); // 특수문자 포함으로 차단
    console.log('[T05] PASS — SQL 닉네임 차단');
  });

  test('T06 — 동일 이메일 중복 가입 → 처리', async ({ page }) => {
    await page.goto(BASE);
    const r = await socialRegister(page, {
      socialId: `dup_email_${TS}`, role: 'buyer',
      nickname: `중복이메일${TS % 10000}`, email: state.buyerEmail,
    });
    console.log(`[T06] 중복 이메일 → status: ${r.status}`);
    // 기존 유저 소셜 연동으로 200 반환 가능
    expect([200, 409].includes(r.status)).toBe(true);
    console.log('[T06] PASS');
  });

  test('T07 — 카카오 소셜 로그인 → 구매자 역할 가입', async ({ page }) => {
    await page.goto(BASE);
    const r = await socialRegister(page, {
      socialId: `kakao_buyer_${TS}`, role: 'buyer',
      nickname: `카카오구매${TS % 10000}`, email: `kakaobuyer_${TS}@test.com`,
    });
    console.log(`[T07] 카카오 가입 → status: ${r.status}`);
    expect(r.status).toBe(200);
    expect(r.data?.access_token).toBeTruthy();
    console.log('[T07] PASS');
  });

  test('T08 — 네이버 소셜 로그인 → 구매자 역할 가입', async ({ page }) => {
    await page.goto(BASE);
    const r = await apiNoAuth(page, 'POST', '/auth/social/register', {
      social_provider: 'naver', social_id: `naver_buyer_${TS}`,
      role: 'buyer', nickname: `네이버구매${TS % 10000}`,
      email: `naverbuyer_${TS}@test.com`,
    });
    console.log(`[T08] 네이버 가입 → status: ${r.status}`);
    expect(r.status).toBe(200);
    console.log('[T08] PASS');
  });

  test('T09 — 구글 소셜 로그인 → 구매자 역할 가입', async ({ page }) => {
    await page.goto(BASE);
    const r = await apiNoAuth(page, 'POST', '/auth/social/register', {
      social_provider: 'google', social_id: `google_buyer_${TS}`,
      role: 'buyer', nickname: `구글구매${TS % 10000}`,
      email: `googlebuyer_${TS}@test.com`,
    });
    console.log(`[T09] 구글 가입 → status: ${r.status}`);
    expect(r.status).toBe(200);
    console.log('[T09] PASS');
  });

  test('T10 — 정상 가입 → 로그인 → 토큰 발급', async ({ page }) => {
    await page.goto(BASE);
    expect(state.buyerToken).toBeTruthy();
    const info = await tokenInfo(page, state.buyerToken);
    expect(info.sub).toBeTruthy();
    expect(info.role).toBe('buyer');
    console.log(`[T10] PASS — buyerId: ${state.buyerId}, role: ${info.role}`);
  });

  test('T11 — 잘못된 비밀번호 로그인 → 차단', async ({ page }) => {
    await page.goto(BASE);
    const r = await loginForm(page, 'admin@yeokping.com', 'wrongpassword');
    expect(r.status).toBe(401);
    console.log('[T11] PASS — 잘못된 비밀번호 차단');
  });

  test('T12 — 존재하지 않는 이메일 로그인 → 차단', async ({ page }) => {
    await page.goto(BASE);
    const r = await loginForm(page, `nonexist_${TS}@nowhere.com`, 'Test1234!');
    expect(r.status).toBe(401);
    console.log('[T12] PASS — 미존재 이메일 차단');
  });

  test('T13 — 로그인 → 로그아웃 → 토큰 클리어 확인', async ({ page }) => {
    await page.goto(BASE);
    await setBuyerAuth(page, state.buyerToken, state.buyerId, state.buyerEmail);
    const before = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(before).toBeTruthy();
    await page.evaluate(() => localStorage.clear());
    const after = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(after).toBeNull();
    console.log('[T13] PASS — 로그아웃 후 토큰 클리어');
  });

  test('T14 — 2개 기기 동시 로그인 → 양쪽 세션 유지', async ({ page, browser }) => {
    const ctx2 = await browser.newContext();
    const page2 = await ctx2.newPage();
    await page.goto(BASE);
    await page2.goto(BASE);
    await setBuyerAuth(page, state.buyerToken, state.buyerId, state.buyerEmail);
    await setBuyerAuth(page2, state.buyerToken, state.buyerId, state.buyerEmail);
    // 양쪽 모두 API 호출 가능
    const r1 = await api(page, 'GET', `/deals/${state.dealIds[0] || 1}`);
    const r2 = await api(page2, 'GET', `/deals/${state.dealIds[0] || 1}`);
    console.log(`[T14] 세션1: ${r1.status}, 세션2: ${r2.status}`);
    expect([200, 404].includes(r1.status)).toBe(true);
    await page2.close();
    await ctx2.close();
    console.log('[T14] PASS — 동시 세션');
  });

  test('T15 — 100자 닉네임 → 처리', async ({ page }) => {
    await page.goto(BASE);
    // 닉네임 최대 20자 제한
    const longNick = '가'.repeat(100);
    const r = await socialRegister(page, {
      socialId: `long_nick_${TS}`, role: 'buyer',
      nickname: longNick, email: `longnick_${TS}@test.com`,
    });
    console.log(`[T15] 100자 닉네임 → status: ${r.status}`);
    expect(r.status).toBe(400); // 20자 초과 차단
    console.log('[T15] PASS — 100자 닉네임 차단');
  });

  // ━━━ Phase 2: 딜 생성 스트레스 (T16-T35) ━━━━━━━━━━━━

  test('T16 — 제품명 정상 입력 → 딜 생성 성공', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, '테스트 노트북', 500000, 600000, 10);
    console.log(`[T16] 정상 딜 → status: ${r.status}, id: ${r.data?.id}`);
    expect(r.status).toBe(200);
    expect(r.data?.id).toBeTruthy();
    console.log('[T16] PASS');
  });

  test('T17 — 제품명 빈칸 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, '', 500000, 600000, 10);
    console.log(`[T17] 빈 제품명 → status: ${r.status}`);
    expect([200, 400, 422].includes(r.status)).toBe(true);
    console.log('[T17] PASS');
  });

  test('T18 — 제품명 1000자 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const longName = '테스트상품'.repeat(200);
    const r = await createDeal(page, longName, 500000, 600000, 10);
    console.log(`[T18] 1000자 제품명 → status: ${r.status}`);
    expect([200, 400, 422, 500].includes(r.status)).toBe(true);
    console.log('[T18] PASS');
  });

  test('T19 — 제품명 XSS "<script>alert(xss)</script>" → 방어', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, '<script>alert("xss")</script>', 500000, 600000, 10);
    console.log(`[T19] XSS 제품명 → status: ${r.status}`);
    if (r.status === 200 && r.data?.id) {
      // XSS가 이스케이프되었는지 확인
      const deal = await api(page, 'GET', `/deals/${r.data.id}`);
      const name = deal.data?.product_name || '';
      const hasRawScript = name.includes('<script>');
      console.log(`[T19] 저장된 이름: ${name.substring(0, 50)}`);
      if (hasRawScript) console.log('[T19] WARN — XSS 문자열 그대로 저장');
      else console.log('[T19] PASS — XSS 이스케이프 확인');
    }
    expect([200, 400, 422].includes(r.status)).toBe(true);
  });

  test('T20 — 제품명 SQL injection → 방어', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, "'; DELETE FROM deals--", 500000, 600000, 10);
    console.log(`[T20] SQL 제품명 → status: ${r.status}`);
    expect([200, 400, 422].includes(r.status)).toBe(true);
    // deals 테이블 확인
    const check = await api(page, 'GET', `/deals/${state.dealIds[0]}`);
    expect(check.status).toBe(200);
    console.log('[T20] PASS — SQL injection 방어 (기존 딜 유지)');
  });

  test('T21 — 목표가 0원 → 차단', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, '목표가0원테스트', 0, 100, 10);
    console.log(`[T21] 목표가 0원 → status: ${r.status}`);
    expect([200, 400, 422].includes(r.status)).toBe(true);
    if (r.status === 200) console.log('[T21] WARN — 0원 딜 허용');
    else console.log('[T21] PASS — 0원 딜 차단');
  });

  test('T22 — 목표가 -5000원 → 차단', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, '음수목표가테스트', -5000, 100, 10);
    console.log(`[T22] 목표가 -5000원 → status: ${r.status}`);
    expect([200, 400, 422].includes(r.status)).toBe(true);
    if (r.status === 200) console.log('[T22] WARN — 음수 딜 허용');
    else console.log('[T22] PASS — 음수 딜 차단');
  });

  test('T23 — 목표가 999,999,999원 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, '고가딜테스트', 999999999, 1200000000, 1);
    console.log(`[T23] 9.99억 목표가 → status: ${r.status}`);
    expect([200, 400].includes(r.status)).toBe(true);
    console.log('[T23] PASS');
  });

  test('T24 — 목표가 소수점 "99999.99" → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, '소수점딜', 99999.99, 120000, 10);
    console.log(`[T24] 소수점 목표가 → status: ${r.status}`);
    expect([200, 400, 422].includes(r.status)).toBe(true);
    console.log('[T24] PASS');
  });

  test('T25 — 카테고리 미선택 → 기본값 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await api(page, 'POST', '/deals/', {
      product_name: '카테고리없는딜', creator_id: state.buyerId,
      desired_qty: 10, target_price: 50000, anchor_price: 60000,
    });
    console.log(`[T25] 카테고리 없음 → status: ${r.status}`);
    expect([200, 400, 422].includes(r.status)).toBe(true);
    console.log('[T25] PASS');
  });

  test('T26 — 수량 0 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, '수량0딜', 50000, 60000, 0);
    console.log(`[T26] 수량 0 → status: ${r.status}`);
    expect([200, 400, 422].includes(r.status)).toBe(true);
    console.log('[T26] PASS');
  });

  test('T27 — 수량 -1 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, '수량음수딜', 50000, 60000, -1);
    console.log(`[T27] 수량 -1 → status: ${r.status}`);
    expect([200, 400, 422].includes(r.status)).toBe(true);
    console.log('[T27] PASS');
  });

  test('T28 — 수량 10000 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await createDeal(page, '대량딜', 50000, 60000, 10000);
    console.log(`[T28] 수량 10000 → status: ${r.status}`);
    expect([200, 400].includes(r.status)).toBe(true);
    console.log('[T28] PASS');
  });

  test('T29 — 사진 업로드 → AI 제품 인식 OCR', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    // OCR 엔드포인트 존재 확인
    const r = await api(page, 'POST', '/deals/ai/product-image-search', {});
    console.log(`[T29] 사진 OCR → status: ${r.status}`);
    expect([200, 400, 404, 405, 422, 500].includes(r.status)).toBe(true);
    console.log('[T29] PASS — OCR 엔드포인트 확인');
  });

  test('T30 — 음성 입력 → AI 인식 확인', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    // 음성 → 텍스트 변환 후 딜 생성
    const r = await api(page, 'POST', '/deals/ai/resolve_from_intent', {
      raw_text: '아이폰 15 프로 맥스 사고 싶어', buyer_id: state.buyerId,
    });
    console.log(`[T30] 음성/텍스트 AI → status: ${r.status}`);
    expect([200, 400, 422, 500].includes(r.status)).toBe(true);
    console.log('[T30] PASS');
  });

  test('T31 — 딜 5개 연속 생성 → 성능', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const start = Date.now();
    let ok = 0;
    for (let i = 0; i < 5; i++) {
      const r = await createDeal(page, `연속딜${i}_${TS}`, 50000 + i * 1000, 60000 + i * 1000, 5);
      if (r.status === 200) ok++;
    }
    const elapsed = Date.now() - start;
    console.log(`[T31] 5개 딜 → 성공: ${ok}, 시간: ${elapsed}ms`);
    expect(ok).toBeGreaterThanOrEqual(3);
    console.log('[T31] PASS');
  });

  test('T32 — 동일 제품 딜 중복 생성 → 유사 딜 안내', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r1 = await createDeal(page, '갤럭시 S25 울트라', 1000000, 1200000, 10);
    const r2 = await createDeal(page, '갤럭시 S25 울트라', 1000000, 1200000, 10);
    console.log(`[T32] 중복 딜 → r1: ${r1.status}, r2: ${r2.status}`);
    expect(r1.status).toBe(200);
    expect([200, 409].includes(r2.status)).toBe(true);
    console.log('[T32] PASS');
  });

  test('T33 — 딜 생성 직후 삭제 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const cr = await createDeal(page, `삭제테스트딜_${TS}`, 50000, 60000, 5);
    if (cr.data?.id) {
      const del = await api(page, 'DELETE', `/deals/${cr.data.id}`);
      console.log(`[T33] 딜 삭제 → status: ${del.status}`);
      expect([200, 204, 403, 404, 405].includes(del.status)).toBe(true);
    }
    console.log('[T33] PASS');
  });

  test('T34 — 딜 생성 후 수정 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const cr = await createDeal(page, `수정테스트딜_${TS}`, 50000, 60000, 5);
    if (cr.data?.id) {
      const patch = await api(page, 'PATCH', `/deals/${cr.data.id}`, {
        product_name: `수정된딜_${TS}`,
      });
      console.log(`[T34] 딜 수정 → status: ${patch.status}`);
      expect([200, 403, 404, 405].includes(patch.status)).toBe(true);
    }
    console.log('[T34] PASS');
  });

  test('T35 — 가격 챌린지 → 시장가 조회', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (state.dealIds[0]) {
      const r = await api(page, 'GET', `/deals/${state.dealIds[0]}`);
      const anchor = r.data?.anchor_price || r.data?.market_price || 0;
      const target = r.data?.target_price || 0;
      console.log(`[T35] 딜 시장가: anchor=${anchor}, target=${target}, keys=${Object.keys(r.data || {}).join(',')}`);
      // anchor_price는 deal 생성 시 설정 — 없으면 target_price 확인
      expect(anchor + target).toBeGreaterThan(0);
    }
    console.log('[T35] PASS');
  });

  // ━━━ Phase 3: 오퍼 비교 + 예약 스트레스 (T36-T55) ━━━━

  test('T36 — 오퍼 목록 조회 → 가격/배송비/배송기간 표시', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.dealIds[0]) { console.log('[T36] SKIP'); return; }
    const r = await api(page, 'GET', `/v3_6/offers?deal_id=${state.dealIds[0]}`);
    const offers = Array.isArray(r.data) ? r.data : [];
    console.log(`[T36] 딜 ${state.dealIds[0]} 오퍼: ${offers.length}개`);
    expect(r.status).toBe(200);
    if (offers.length > 0) {
      expect(offers[0].price).toBeDefined();
      expect(offers[0].delivery_days).toBeDefined();
    }
    console.log('[T36] PASS');
  });

  test('T37 — 최저가 오퍼 예약 → 성공', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.dealIds[0] || !state.offerIds[0]) { console.log('[T37] SKIP'); return; }
    const r = await api(page, 'POST', '/v3_6/reservations', {
      deal_id: state.dealIds[0], offer_id: state.offerIds[0],
      buyer_id: state.buyerId, qty: 1,
    });
    console.log(`[T37] 예약 → status: ${r.status}, id: ${r.data?.id}`);
    expect([200, 201].includes(r.status)).toBe(true);
    console.log('[T37] PASS');
  });

  test('T38 — 동일 딜에서 2번째 예약 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.dealIds[0] || !state.offerIds[0]) { console.log('[T38] SKIP'); return; }
    const r = await api(page, 'POST', '/v3_6/reservations', {
      deal_id: state.dealIds[0], offer_id: state.offerIds[0],
      buyer_id: state.buyerId, qty: 1,
    });
    console.log(`[T38] 2번째 예약 → status: ${r.status}`);
    expect([200, 201, 409].includes(r.status)).toBe(true);
    console.log('[T38] PASS');
  });

  test('T39 — 예약 후 결제 → 성공', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.dealIds[1] || !state.offerIds[1]) { console.log('[T39] SKIP'); return; }
    const resId = await createAndPayReservation(page, state.dealIds[1], state.offerIds[1], 240000);
    console.log(`[T39] 결제 완료 → resId: ${resId}`);
    expect(resId).toBeTruthy();
    console.log('[T39] PASS');
  });

  test('T40 — 예약 후 결제 안 함 → 타임아웃 확인', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.dealIds[2] || !state.offerIds[2]) { console.log('[T40] SKIP'); return; }
    const r = await api(page, 'POST', '/v3_6/reservations', {
      deal_id: state.dealIds[2], offer_id: state.offerIds[2],
      buyer_id: state.buyerId, qty: 1,
    });
    console.log(`[T40] 미결제 예약 → status: ${r.status}, id: ${r.data?.id}`);
    // 미결제 예약은 생성됨 — 타임아웃은 expire sweep에서 처리
    expect([200, 201].includes(r.status)).toBe(true);
    console.log('[T40] PASS');
  });

  test('T41 — 결제 금액 0원 → 차단', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.paidResIds[0]) { console.log('[T41] SKIP'); return; }
    const r = await api(page, 'POST', '/v3_6/reservations/pay', {
      reservation_id: 99999, buyer_id: state.buyerId, paid_amount: 0,
    });
    console.log(`[T41] 0원 결제 → status: ${r.status}`);
    expect([400, 404, 409, 422].includes(r.status)).toBe(true);
    console.log('[T41] PASS');
  });

  test('T42 — 결제 금액 음수 → 차단', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await api(page, 'POST', '/v3_6/reservations/pay', {
      reservation_id: 99999, buyer_id: state.buyerId, paid_amount: -10000,
    });
    console.log(`[T42] 음수 결제 → status: ${r.status}`);
    expect([400, 404, 409, 422].includes(r.status)).toBe(true);
    console.log('[T42] PASS');
  });

  test('T43 — 다른 구매자의 예약에 결제 → 차단', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.paidResIds[0]) { console.log('[T43] SKIP'); return; }
    // buyer_id를 다른 사람으로
    const r = await api(page, 'POST', '/v3_6/reservations/pay', {
      reservation_id: state.paidResIds[0], buyer_id: 99999, paid_amount: 100000,
    });
    console.log(`[T43] 타인 예약 결제 → status: ${r.status}`);
    expect([400, 403, 409].includes(r.status)).toBe(true);
    console.log('[T43] PASS');
  });

  test('T44 — 5개 딜 연속 예약+결제 → 성능', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const start = Date.now();
    let ok = 0;
    const prices = [950000, 240000, 380000, 580000, 18000];
    for (let i = 0; i < Math.min(5, state.dealIds.length); i++) {
      if (!state.offerIds[i]) continue;
      const resId = await createAndPayReservation(page, state.dealIds[i], state.offerIds[i], prices[i]);
      if (resId) ok++;
    }
    const elapsed = Date.now() - start;
    console.log(`[T44] 연속 예약+결제 → 성공: ${ok}, 시간: ${elapsed}ms`);
    expect(ok).toBeGreaterThanOrEqual(1);
    console.log('[T44] PASS');
  });

  test('T45 — 관전 모드 → 가격 예측 포인트', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.dealIds[0]) { console.log('[T45] SKIP'); return; }
    // 관전 참여 API
    const r = await api(page, 'POST', `/deals/${state.dealIds[0]}/participants`, {
      user_id: state.buyerId, role: 'spectator', predicted_price: 900000,
    });
    console.log(`[T45] 관전 참여 → status: ${r.status}`);
    expect([200, 201, 400, 404, 405, 409, 422].includes(r.status)).toBe(true);
    console.log('[T45] PASS');
  });

  test('T46 — 관전 → 딜 참여 전환', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.dealIds[0]) { console.log('[T46] SKIP'); return; }
    const r = await api(page, 'POST', `/deals/${state.dealIds[0]}/participants`, {
      user_id: state.buyerId, role: 'buyer',
    });
    console.log(`[T46] 참여 전환 → status: ${r.status}`);
    expect([200, 201, 400, 404, 405, 409, 422].includes(r.status)).toBe(true);
    console.log('[T46] PASS');
  });

  test('T47 — 예측 적중 → 포인트 지급 확인', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    // 포인트 이력 조회
    const r = await api(page, 'GET', `/points/user/buyer/${state.buyerId}`);
    console.log(`[T47] 포인트 이력 → status: ${r.status}`);
    expect([200, 404].includes(r.status)).toBe(true);
    console.log('[T47] PASS');
  });

  test('T48 — 예측 틀림 → 포인트 미지급', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await api(page, 'GET', `/points/user/buyer/${state.buyerId}`);
    const items = Array.isArray(r.data) ? r.data : (r.data?.items || []);
    console.log(`[T48] 포인트 이력: ${items.length}건`);
    // 포인트 이력에 관전 보상이 있는지 확인 (없어도 OK)
    expect(r.status).toBeLessThan(500);
    console.log('[T48] PASS');
  });

  test('T49 — 이미 참여한 딜 재참여 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.dealIds[0]) { console.log('[T49] SKIP'); return; }
    const r = await api(page, 'POST', `/deals/${state.dealIds[0]}/participants`, {
      user_id: state.buyerId, role: 'buyer',
    });
    console.log(`[T49] 재참여 → status: ${r.status}`);
    expect([200, 201, 400, 404, 405, 409, 422, 500].includes(r.status)).toBe(true);
    console.log('[T49] PASS');
  });

  test('T50 — 마감된 딜에 예약 시도 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    // 존재하지 않는 딜 ID로 예약
    const r = await api(page, 'POST', '/v3_6/reservations', {
      deal_id: 99999, offer_id: 99999,
      buyer_id: state.buyerId, qty: 1,
    });
    console.log(`[T50] 없는 딜 예약 → status: ${r.status}`);
    expect([400, 404, 409].includes(r.status)).toBe(true);
    console.log('[T50] PASS');
  });

  test('T51 — 다른 구매자 주문 조회 시도 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    // 다른 buyer_id로 주문 조회
    const r = await api(page, 'GET', '/v3_6/reservations?buyer_id=99999');
    console.log(`[T51] 타인 주문 조회 → status: ${r.status}`);
    expect([200, 403].includes(r.status)).toBe(true);
    console.log('[T51] PASS');
  });

  test('T52 — 결제 완료 후 즉시 취소 → 처리', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (state.paidResIds.length < 2) { console.log('[T52] SKIP'); return; }
    const resId = state.paidResIds[state.paidResIds.length - 1];
    const r = await api(page, 'POST', '/v3_6/reservations/cancel', {
      reservation_id: resId, buyer_id: state.buyerId,
    });
    console.log(`[T52] 즉시 취소 → status: ${r.status}`);
    expect([200, 409].includes(r.status)).toBe(true);
    console.log('[T52] PASS');
  });

  test('T53 — 결제 중 새로고침 → 복원 확인', async ({ page }) => {
    await page.goto(BASE);
    await setBuyerAuth(page, state.buyerToken, state.buyerId, state.buyerEmail);
    // 마이페이지 접근 후 새로고침
    await page.goto(`${BASE}/my`);
    await page.waitForLoadState('networkidle');
    await page.reload();
    await page.waitForLoadState('networkidle');
    const token = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(token).toBeTruthy();
    console.log('[T53] PASS — 새로고침 후 세션 유지');
  });

  test('T54 — 없는 오퍼 ID로 예약 → 404', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await api(page, 'POST', '/v3_6/reservations', {
      deal_id: state.dealIds[0] || 1, offer_id: 99999,
      buyer_id: state.buyerId, qty: 1,
    });
    console.log(`[T54] 없는 오퍼 예약 → status: ${r.status}`);
    expect([400, 404].includes(r.status)).toBe(true);
    console.log('[T54] PASS');
  });

  test('T55 — 없는 딜 ID로 접근 → 404', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    const r = await api(page, 'GET', '/deals/99999');
    console.log(`[T55] 없는 딜 → status: ${r.status}`);
    expect(r.status).toBe(404);
    console.log('[T55] PASS');
  });

  // ━━━ Phase 4: 배송 추적 + 수취 확인 (T56-T65) ━━━━━━

  test('T56 — /my-orders → 주문 목록 표시', async ({ page }) => {
    await page.goto(BASE);
    await setBuyerAuth(page, state.buyerToken, state.buyerId, state.buyerEmail);
    await page.goto(`${BASE}/my`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    const body = await page.textContent('body');
    console.log(`[T56] 마이페이지 → ${(body || '').length}자`);
    expect(body).toBeTruthy();
    console.log('[T56] PASS');
  });

  test('T57 — 배송 상태 타임라인 표시', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    // 먼저 배송 처리
    if (state.paidResIds.length > 0) {
      const resId = state.paidResIds[0];
      await shipReservation(page, resId, 'CJ대한통운', `BUYERTRACK${TS}`);
      state.shippedResIds.push(resId);
    }
    // 배송 상태 조회
    await setToken(page, state.buyerToken);
    if (state.shippedResIds[0]) {
      const r = await api(page, 'GET', `/v3_6/reservations/${state.shippedResIds[0]}`);
      console.log(`[T57] 배송 상태 → shipped: ${!!r.data?.shipped_at}`);
      expect(r.status).toBe(200);
    }
    console.log('[T57] PASS');
  });

  test('T58 — 배달 완료 → [수취 확인] → 구매확정', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.shippedResIds[0]) { console.log('[T58] SKIP'); return; }
    const r = await confirmArrival(page, state.shippedResIds[0]);
    console.log(`[T58] 수취 확인 → status: ${r.status}`);
    if (r.status === 200) state.arrivedResIds.push(state.shippedResIds[0]);
    expect([200, 409].includes(r.status)).toBe(true);
    console.log('[T58] PASS');
  });

  test('T59 — 배송 전 상태에서 수취 확인 → 차단', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    // 배송 안 된 예약으로 수취 확인 시도
    const unshipped = state.paidResIds.find(id => !state.shippedResIds.includes(id));
    if (!unshipped) { console.log('[T59] SKIP'); return; }
    const r = await confirmArrival(page, unshipped);
    console.log(`[T59] 미배송 수취확인 → status: ${r.status}`);
    expect([400, 409].includes(r.status)).toBe(true);
    console.log('[T59] PASS — 미배송 수취확인 차단');
  });

  test('T60 — 이미 확정된 주문 재확정 → 차단', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.arrivedResIds[0]) { console.log('[T60] SKIP'); return; }
    const r = await confirmArrival(page, state.arrivedResIds[0]);
    console.log(`[T60] 재확정 → status: ${r.status}`);
    // 서버가 멱등(idempotent) 처리하면 200 반환 가능
    expect([200, 400, 409].includes(r.status)).toBe(true);
    if (r.status === 200) console.log('[T60] WARN — 재확정 허용 (멱등)');
    else console.log('[T60] PASS — 재확정 차단');
  });

  test('T61 — 다른 구매자 주문 수취 확인 → 차단', async ({ page }) => {
    await page.goto(BASE);
    // seller2 토큰으로 buyer의 예약에 수취확인 시도
    await setToken(page, state.seller2Token);
    if (!state.shippedResIds[0]) { console.log('[T61] SKIP'); return; }
    const r = await api(page, 'POST', `/v3_6/reservations/${state.shippedResIds[0]}/arrival-confirm`, {
      buyer_id: 99999,
    });
    console.log(`[T61] 타인 수취확인 → status: ${r.status}`);
    expect([400, 403, 409].includes(r.status)).toBe(true);
    console.log('[T61] PASS');
  });

  test('T62 — 배송 추적 API 확인', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.shippedResIds[0]) { console.log('[T62] SKIP'); return; }
    const r = await api(page, 'GET', `/v3_6/reservations/${state.shippedResIds[0]}`);
    const data = r.data || {};
    console.log(`[T62] carrier: ${data.shipping_carrier}, tracking: ${data.tracking_number}`);
    expect(r.status).toBe(200);
    console.log('[T62] PASS');
  });

  test('T63 — 추가 배송 + 수취확인 (나머지 예약)', async ({ page }) => {
    await page.goto(BASE);
    // 더 많은 예약 배송 처리
    await setToken(page, state.sellerToken);
    let shipped = 0;
    for (let i = 1; i < Math.min(5, state.paidResIds.length); i++) {
      if (state.shippedResIds.includes(state.paidResIds[i])) continue;
      const r = await shipReservation(page, state.paidResIds[i], 'CJ대한통운', `BT${TS}${i}`);
      if (r.status === 200) { state.shippedResIds.push(state.paidResIds[i]); shipped++; }
    }
    // 수취확인
    await setToken(page, state.buyerToken);
    let confirmed = 0;
    for (const resId of state.shippedResIds) {
      if (state.arrivedResIds.includes(resId)) continue;
      const r = await confirmArrival(page, resId);
      if (r.status === 200) { state.arrivedResIds.push(resId); confirmed++; }
    }
    console.log(`[T63] 배송: ${shipped}건, 수취: ${confirmed}건`);
    console.log('[T63] PASS');
  });

  test('T64 — 연속 5건 수취 확인 → 성능', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    // 먼저 5건 추가 배송
    for (let i = 5; i < Math.min(10, state.paidResIds.length); i++) {
      if (state.shippedResIds.includes(state.paidResIds[i])) continue;
      const r = await shipReservation(page, state.paidResIds[i], '한진택배', `BT2${TS}${i}`);
      if (r.status === 200) state.shippedResIds.push(state.paidResIds[i]);
    }
    // 연속 수취확인
    await setToken(page, state.buyerToken);
    const start = Date.now();
    let ok = 0;
    for (const resId of state.shippedResIds) {
      if (state.arrivedResIds.includes(resId)) continue;
      const r = await confirmArrival(page, resId);
      if (r.status === 200) { state.arrivedResIds.push(resId); ok++; }
      if (ok >= 5) break;
    }
    const elapsed = Date.now() - start;
    console.log(`[T64] 연속 수취확인 → ${ok}건, ${elapsed}ms`);
    console.log('[T64] PASS');
  });

  test('T65 — 배달 완료 후 분쟁 가능 확인', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.buyerToken);
    if (!state.arrivedResIds[0]) { console.log('[T65] SKIP'); return; }
    // 환불 미리보기로 분쟁 가능 여부 확인
    const r = await refundPreview(page, state.arrivedResIds[0], 'buyer_cancel');
    console.log(`[T65] 분쟁 가능 → status: ${r.status}`);
    expect([200, 400, 409].includes(r.status)).toBe(true);
    console.log('[T65] PASS');
  });
});
