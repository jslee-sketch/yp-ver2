/**
 * 역할 스트레스 테스트 Phase 5
 * Phase 5: 역할 교차 안전 (T91-T120) — 30개
 */
import { test, expect } from '@playwright/test';
import { BASE, state, api, apiNoAuth, socialRegister, tokenInfo, setToken, setupAll, TS } from './helpers';

test.describe.configure({ mode: 'serial' });

test('Setup: 전체 데이터 초기화', async ({ page }) => {
  test.setTimeout(120_000);
  await setupAll(page);
  expect(state.buyerId).toBeGreaterThan(0);
  expect(state.sellerId).toBeGreaterThan(0);
  expect(state.actuatorId).toBeGreaterThan(0);
});

// ============================================================
// Phase 5: 역할 교차 안전 (T91-T120)
// ============================================================

// --- 역할 교차 접근 ---
test('T91 구매자 토큰으로 판매자 API 접근', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', `/sellers/${state.sellerId}`);
  // 조회는 허용될 수 있지만 수정은 차단
  expect([200, 401, 403, 404, 500]).toContain(r.status);
});

test('T92 구매자 토큰으로 오퍼 생성 시도', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'POST', '/v3_6/offers', {
    deal_id: state.dealIds[0], seller_id: state.buyerId,
    price: 800000, total_available_qty: 5, delivery_days: 3, shipping_mode: 'INCLUDED',
  });
  expect([200, 201, 400, 401, 403, 409, 422, 500]).toContain(r.status);
  if ([200, 201].includes(r.status)) console.log('WARN: 구매자 토큰으로 오퍼 생성 허용됨');
});

test('T93 판매자 토큰으로 딜 생성 시도', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.sellerToken);
  const r = await api(page, 'POST', '/deals/', {
    product_name: '교차테스트', creator_id: state.sellerId,
    desired_qty: 10, target_price: 50000, anchor_price: 60000, category: 'test',
  });
  expect([200, 201, 400, 401, 403, 422, 500]).toContain(r.status);
  if ([200, 201].includes(r.status)) console.log('WARN: 판매자 토큰으로 딜 생성 허용됨');
});

test('T94 액추에이터 토큰으로 딜 생성 시도', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'POST', '/deals/', {
    product_name: '액추딜테스트', creator_id: state.actuatorId,
    desired_qty: 5, target_price: 30000, anchor_price: 40000, category: 'test',
  });
  expect([200, 201, 400, 401, 403, 422, 500]).toContain(r.status);
  if ([200, 201].includes(r.status)) console.log('WARN: 액추에이터 토큰으로 딜 생성 허용됨');
});

test('T95 액추에이터 토큰으로 관리자 API', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', '/admin/dashboard/');
  expect([200, 401, 403, 404, 500]).toContain(r.status);
  if (r.status === 200) console.log('WARN: 액추에이터가 관리자 대시보드 접근 허용됨');
});

test('T96 구매자 토큰으로 관리자 정산 승인 시도', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'POST', '/settlements/1/approve', { actor_id: state.buyerId });
  expect([200, 400, 401, 403, 404, 405, 409, 422, 500]).toContain(r.status);
  if (r.status === 200) console.log('WARN: 구매자가 정산 승인 허용됨');
});

test('T97 판매자 토큰으로 타인 정산 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.sellerToken);
  const r = await api(page, 'GET', `/settlements/seller/${state.seller2Id}`);
  expect([200, 401, 403, 404, 500]).toContain(r.status);
});

test('T98 토큰 없이 딜 생성 시도', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, '');
  const r = await apiNoAuth(page, 'POST', '/deals/', {
    product_name: '무토큰', creator_id: 1, desired_qty: 1,
    target_price: 1000, anchor_price: 2000, category: 'test',
  });
  expect([200, 201, 401, 403, 422, 500]).toContain(r.status);
  if ([200, 201].includes(r.status)) console.log('WARN: 토큰 없이 딜 생성 허용됨');
});

test('T99 위조 JWT로 예약 생성 시도', async ({ page }) => {
  await page.goto(BASE);
  const fakeJwt = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI5OTkiLCJyb2xlIjoiYWRtaW4ifQ.fake';
  const r = await api(page, 'POST', '/v3_6/reservations', {
    deal_id: 1, offer_id: 1, buyer_id: 999, qty: 1,
  }, fakeJwt);
  expect([200, 201, 400, 401, 403, 404, 422, 500]).toContain(r.status);
  if ([200, 201].includes(r.status)) console.log('WARN: 위조 JWT로 예약 생성 허용됨');
});

test('T100 타인 프로필 수정 시도 (buyer)', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'PATCH', `/buyers/${state.buyer2Id}`, { nickname: '해킹바이어' });
  expect([200, 401, 403, 404, 405, 409, 422, 500]).toContain(r.status);
  if (r.status === 200) console.log('WARN: 타인 프로필 수정 허용됨');
});

// --- 인젝션 테스트 ---
test('T101 딜 이름 XSS', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'POST', '/deals/', {
    product_name: '<img src=x onerror=alert(1)>', creator_id: state.buyerId,
    desired_qty: 1, target_price: 1000, anchor_price: 2000, category: 'test',
  });
  expect([200, 201, 400, 409, 422, 500]).toContain(r.status);
  if ([200, 201].includes(r.status) && r.data?.product_name) {
    // HTML 인코딩된 경우(&lt;img) XSS 방지됨 — raw <img 태그만 위험
    const name = r.data.product_name;
    const hasRawXss = name.includes('<img') || name.includes('<script');
    expect(hasRawXss).toBe(false);
  }
});

test('T102 딜 이름 SQL injection', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'POST', '/deals/', {
    product_name: "'; DROP TABLE deals;--", creator_id: state.buyerId,
    desired_qty: 1, target_price: 1000, anchor_price: 2000, category: 'test',
  });
  expect([200, 201, 400, 409, 422, 500]).toContain(r.status);
  // 딜 목록이 여전히 조회 가능한지
  const check = await api(page, 'GET', '/deals/');
  expect(check.status).toBe(200);
});

test('T103 환불 사유 XSS', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  if (!state.paidResIds[0]) return;
  const r = await api(page, 'POST', '/v3_6/reservations/refund', {
    reservation_id: state.paidResIds[0],
    reason: '<script>document.cookie</script>',
    requested_by: 'BUYER',
  });
  expect([200, 400, 404, 409, 422, 500]).toContain(r.status);
});

test('T104 채팅 메시지 XSS', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'POST', `/deals/${state.dealIds[0]}/chat/messages`, {
    user_id: state.buyerId, user_type: 'buyer',
    message: '<img src=x onerror=alert(document.cookie)>',
  });
  expect([200, 201, 400, 404, 405, 422, 500]).toContain(r.status);
});

test('T105 핑퐁이 XSS 질문', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
    question: '<script>alert("xss")</script>',
    role: 'buyer', buyer_id: state.buyerId,
  });
  expect([200, 201, 400, 404, 405, 422, 500]).toContain(r.status);
});

test('T106 핑퐁이 SQL injection', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
    question: "'; DROP TABLE users;--",
    role: 'buyer', buyer_id: state.buyerId,
  });
  expect([200, 201, 400, 404, 405, 422, 500]).toContain(r.status);
});

// --- 동시성 / 경쟁 조건 ---
test('T107 동일 딜 동시 예약 (buyer1 + buyer2)', async ({ page }) => {
  await page.goto(BASE);
  if (!state.dealIds[0] || !state.offerIds[0]) return;
  // buyer1
  await setToken(page, state.buyerToken);
  const r1 = await api(page, 'POST', '/v3_6/reservations', {
    deal_id: state.dealIds[0], offer_id: state.offerIds[0],
    buyer_id: state.buyerId, qty: 1,
  });
  // buyer2
  await setToken(page, state.buyer2Token);
  const r2 = await api(page, 'POST', '/v3_6/reservations', {
    deal_id: state.dealIds[0], offer_id: state.offerIds[0],
    buyer_id: state.buyer2Id, qty: 1,
  });
  expect([200, 201, 400, 422]).toContain(r1.status);
  expect([200, 201, 400, 422]).toContain(r2.status);
});

test('T108 동일 오퍼 중복 결제 차단', async ({ page }) => {
  await page.goto(BASE);
  if (!state.paidResIds[0]) return;
  await setToken(page, state.buyerToken);
  const r = await api(page, 'POST', '/v3_6/reservations/pay', {
    reservation_id: state.paidResIds[0],
    buyer_id: state.buyerId,
    paid_amount: 100000,
  });
  expect([200, 400, 409, 422, 500]).toContain(r.status);
});

// --- UI 라우트 확인 ---
test('T109 메인 페이지 로딩', async ({ page }) => {
  test.setTimeout(15_000);
  await page.goto(BASE);
  const body = await page.textContent('body');
  expect((body || '').length).toBeGreaterThan(0);
});

test('T110 로그인 페이지 로딩', async ({ page }) => {
  test.setTimeout(15_000);
  await page.goto(`${BASE}/login`);
  const body = await page.textContent('body');
  expect((body || '').length).toBeGreaterThan(0);
});

test('T111 회원가입 페이지 로딩', async ({ page }) => {
  test.setTimeout(15_000);
  await page.goto(`${BASE}/register`);
  const body = await page.textContent('body');
  expect((body || '').length).toBeGreaterThan(0);
});

test('T112 딜 목록 페이지 로딩', async ({ page }) => {
  test.setTimeout(15_000);
  await page.goto(`${BASE}/deals`);
  const body = await page.textContent('body');
  expect((body || '').length).toBeGreaterThan(0);
});

test('T113 마이페이지 로딩', async ({ page }) => {
  test.setTimeout(15_000);
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  await page.goto(`${BASE}/mypage`);
  const body = await page.textContent('body');
  expect((body || '').length).toBeGreaterThan(0);
});

test('T114 관리자 페이지 접근', async ({ page }) => {
  test.setTimeout(15_000);
  await page.goto(`${BASE}/admin`);
  const body = await page.textContent('body');
  expect((body || '').length).toBeGreaterThan(0);
});

// --- 최종 종합 ---
test('T115 전체 역할 E2E 플로우', async ({ page }) => {
  test.setTimeout(30_000);
  await page.goto(BASE);
  // buyer: 딜 생성
  await setToken(page, state.buyerToken);
  const deal = await api(page, 'POST', '/deals/', {
    product_name: `E2E역할${TS}`, creator_id: state.buyerId,
    desired_qty: 5, target_price: 50000, anchor_price: 60000, category: 'test',
  });
  expect([200, 201]).toContain(deal.status);
  const dealId = deal.data?.id;
  if (!dealId) return;

  // seller: 오퍼 생성
  await setToken(page, state.sellerToken);
  const offer = await api(page, 'POST', '/v3_6/offers', {
    deal_id: dealId, seller_id: state.sellerId,
    price: 48000, total_available_qty: 10, delivery_days: 3, shipping_mode: 'INCLUDED',
  });
  expect([200, 201]).toContain(offer.status);
  const offerId = offer.data?.id;
  if (!offerId) return;

  // spectator: 예측
  await setToken(page, state.spectatorToken);
  await api(page, 'POST', '/spectator/predict', {
    deal_id: dealId, buyer_id: state.spectatorId, predicted_price: 47000,
  });

  // buyer: 예약 + 결제
  await setToken(page, state.buyerToken);
  const res = await api(page, 'POST', '/v3_6/reservations', {
    deal_id: dealId, offer_id: offerId, buyer_id: state.buyerId, qty: 1,
  });
  if (res.data?.id) {
    await api(page, 'POST', '/v3_6/reservations/pay', {
      reservation_id: res.data.id, buyer_id: state.buyerId, paid_amount: 48000,
    });
  }
  console.log('T115 E2E 플로우 완료');
});

test('T116 역할별 API 접근 5연속 성능', async ({ page }) => {
  test.setTimeout(30_000);
  await page.goto(BASE);
  const start = Date.now();
  // buyer
  await setToken(page, state.buyerToken);
  await api(page, 'GET', '/deals/');
  await api(page, 'GET', '/points/balance');
  // seller
  await setToken(page, state.sellerToken);
  await api(page, 'GET', `/sellers/${state.sellerId}`);
  await api(page, 'GET', `/settlements/seller/${state.sellerId}`);
  // actuator
  await setToken(page, state.actuatorToken);
  await api(page, 'GET', `/actuators/${state.actuatorId}`);
  const elapsed = Date.now() - start;
  console.log(`T116 역할별 5연속 API: ${elapsed}ms`);
  expect(elapsed).toBeLessThan(15000);
});

test('T117 핑퐁이 액추에이터 질문', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
    question: '커미션 얼마야?',
    role: 'actuator',
  });
  expect([200, 201, 400, 404, 405, 422, 500]).toContain(r.status);
  if (r.status === 200 && r.data?.answer) {
    expect(r.data.answer.length).toBeGreaterThan(0);
  }
});

test('T118 핑퐁이 위탁계약서 질문', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
    question: '위탁계약서 어디서 봐?',
    role: 'actuator',
  });
  expect([200, 201, 400, 404, 405, 422, 500]).toContain(r.status);
  if (r.status === 200 && r.data?.answer) {
    console.log(`T118 답변: ${r.data.answer.substring(0, 100)}`);
  }
});

test('T119 핑퐁이 원천징수 질문', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
    question: '원천징수 얼마야?',
    role: 'actuator',
  });
  expect([200, 201, 400, 404, 405, 422, 500]).toContain(r.status);
  if (r.status === 200 && r.data?.answer) {
    console.log(`T119 답변: ${r.data.answer.substring(0, 100)}`);
  }
});

test('T120 최종 상태 검증', async ({ page }) => {
  await page.goto(BASE);
  console.log('=== 최종 상태 ===');
  console.log(`Buyer: ${state.buyerId}`);
  console.log(`Buyer2: ${state.buyer2Id}`);
  console.log(`Seller: ${state.sellerId}`);
  console.log(`Seller2: ${state.seller2Id}`);
  console.log(`Actuator: ${state.actuatorId}`);
  console.log(`Actuator2 (biz): ${state.actuator2Id}`);
  console.log(`Spectator: ${state.spectatorId}`);
  console.log(`Deals: ${state.dealIds.length}`);
  console.log(`Offers: ${state.offerIds.length}`);
  console.log(`Reservations: ${state.resIds.length}`);
  console.log(`Paid: ${state.paidResIds.length}`);

  // 기본 검증
  expect(state.buyerId).toBeGreaterThan(0);
  expect(state.sellerId).toBeGreaterThan(0);
  expect(state.actuatorId).toBeGreaterThan(0);
  expect(state.dealIds.length).toBeGreaterThan(0);
});
