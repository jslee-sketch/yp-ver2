import { test, expect, type Page } from '@playwright/test';

/* ──────────────────────────────────────────────────────────
 *  E2E Deep Test — 10 Phase End-to-End Transaction Flow
 *
 *  Run:
 *    npx playwright test tests/e2e-deep.spec.ts --headed --timeout 300000
 *
 *  Phases:
 *    1. 구매자 회원가입 (UI + API fallback)
 *    2. 구매자 로그인 (UI + API fallback)
 *    3. 딜 생성 (API + UI verify)
 *    4. 판매자 가입 + 로그인 + 오퍼 제출 (API reg + UI login + UI offer)
 *    5. 구매자 예약 + 결제 (API + UI verify)
 *    6. 판매자 배송 처리 (API)
 *    7. 구매자 수취확인 (UI — MyOrdersPage)
 *    8. 구매자 환불 요청 (UI — refund modal)
 *    9. 핑퐁이 대화 20개 (API via browser)
 *   10. 관리자 대시보드 (UI navigation)
 * ────────────────────────────────────────────────────────── */

const TS = Date.now();

/* ── Test Accounts (unique per run) ─────────────────────── */
const BUYER = {
  email:    `deep_buyer_${TS}@test.com`,
  password: 'Test1234!',
  nickname: `buyer${TS % 10000}`,
  phone:    `010${String(TS % 10000).padStart(4, '0')}${String((TS + 1) % 10000).padStart(4, '0')}`,
};
const SELLER = {
  email:    `deep_seller_${TS}@test.com`,
  password: 'Test1234!',
  nickname: `seller${TS % 10000}`,
  phone:    `010${String((TS + 2) % 10000).padStart(4, '0')}${String((TS + 3) % 10000).padStart(4, '0')}`,
};
const ADMIN = { email: 'admin@yp.com', password: 'Admin123!' };

/* ── Shared state across phases ─────────────────────────── */
let buyerId:       number;
let sellerId:      number;
let dealId:        number;
let offerId:       number;
let reservationId: number;

/* ── Helpers ────────────────────────────────────────────── */

/** Login via form-encoded API (tries both buyer and seller endpoints) */
async function apiLogin(page: Page, email: string, password: string): Promise<string | null> {
  return page.evaluate(async ({ email, password }) => {
    const params = new URLSearchParams();
    params.append('username', email);
    params.append('password', password);
    // Try buyer login first, then seller login
    for (const url of ['/auth/login', '/auth/seller/login']) {
      const r = await fetch(url, { method: 'POST', body: params });
      if (r.status === 200) {
        const data = await r.json();
        const token = data.access_token;
        if (token) {
          localStorage.setItem('access_token', token);
          localStorage.setItem('token', token);
        }
        return token;
      }
    }
    return null;
  }, { email, password });
}

/** Navigate to login page, fill form, click button. If UI fails, fallback to API login. */
async function login(page: Page, email: string, password: string) {
  await page.evaluate(() => localStorage.clear());
  await page.goto('/login');
  await page.waitForTimeout(1200);
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', password);
  await page.click('button:has-text("로그인하기")');
  await page.waitForTimeout(2500);

  // If still on login page, try API fallback
  if (page.url().includes('/login')) {
    console.log(`  [login] UI login failed for ${email}, trying API fallback...`);
    const token = await apiLogin(page, email, password);
    if (token) {
      await page.goto('/');
      await page.waitForTimeout(1500);
      console.log(`  [login] API login succeeded`);
    } else {
      console.log(`  [login] API login also failed for ${email}`);
    }
  }
}

async function apiPost(page: Page, url: string, body: Record<string, unknown>) {
  return page.evaluate(async ({ url, body }) => {
    const token = localStorage.getItem('access_token') || localStorage.getItem('token') || '';
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token && { Authorization: `Bearer ${token}` }) },
      body: JSON.stringify(body),
    });
    return { status: r.status, data: await r.json().catch(() => null) };
  }, { url, body });
}

async function apiGet(page: Page, url: string) {
  return page.evaluate(async (url) => {
    const token = localStorage.getItem('access_token') || localStorage.getItem('token') || '';
    const r = await fetch(url, {
      headers: { ...(token && { Authorization: `Bearer ${token}` }) },
    });
    return { status: r.status, data: await r.json().catch(() => null) };
  }, url);
}

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `test-results/deep/${name}.png`, fullPage: true });
}

/** Ensure buyer exists: try API login, if fails create via API */
async function ensureBuyer(page: Page): Promise<void> {
  const token = await apiLogin(page, BUYER.email, BUYER.password);
  if (token) return; // already exists
  // Create via API
  console.log('  [ensureBuyer] Creating buyer via API...');
  await page.evaluate(async (data) => {
    await fetch('/buyers/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  }, { email: BUYER.email, password: BUYER.password, name: BUYER.nickname, nickname: BUYER.nickname, phone: BUYER.phone });
}

/** Ensure seller exists: try API login, if fails create via API */
async function ensureSeller(page: Page): Promise<void> {
  // Try seller login
  const token = await page.evaluate(async ({ email, password }) => {
    const params = new URLSearchParams();
    params.append('username', email);
    params.append('password', password);
    const r = await fetch('/auth/seller/login', { method: 'POST', body: params });
    if (r.status !== 200) return null;
    const data = await r.json();
    return data.access_token || null;
  }, { email: SELLER.email, password: SELLER.password });
  if (token) return;
  // Create via API
  console.log('  [ensureSeller] Creating seller via API...');
  await page.evaluate(async (data) => {
    await fetch('/sellers/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  }, {
    email: SELLER.email, password: SELLER.password,
    nickname: SELLER.nickname, name: SELLER.nickname,
    business_name: `DeepShop${TS % 10000}`,
    business_number: `1234567${String(TS % 1000).padStart(3, '0')}`,
    phone: SELLER.phone,
    address: 'Seoul Test', zip_code: '12345',
    established_date: '2024-01-01T00:00:00',
  });
}

/** Click "다음" if visible + enabled */
async function clickNext(page: Page): Promise<boolean> {
  const btn = page.locator('button:has-text("다음")').first();
  if ((await btn.count()) > 0 && !(await btn.isDisabled())) {
    await btn.click();
    await page.waitForTimeout(700);
    return true;
  }
  return false;
}

/* ── Pingpong 20 Questions ──────────────────────────────── */
const PINGPONG_QS = [
  '역핑이 뭐야?', '공동구매 딜은 어떻게 만들어?', '결제 후 취소할 수 있어?',
  '배송은 얼마나 걸려?', '환불 정책이 어떻게 돼?', '포인트는 어떻게 모아?',
  '셀러 등급은 어떻게 올라?', '수수료가 얼마야?', '분쟁이 생기면 어떻게 해?',
  '딜이 성사되려면 조건이 뭐야?', '에어팟 프로 시세가 얼마야?', '갤럭시 S25 울트라 시세?',
  '플랫폼 수수료 알려줘', '정산은 언제 돼?', '쿨링 기간이 뭐야?',
  '배송비는 누가 내?', '리뷰는 어떻게 써?', '딜 채팅은 어떻게 해?',
  '예약금은 얼마야?', '구매자 레벨 시스템 설명해줘',
];

/* ══════════════════════════════════════════════════════════ */
test.describe.serial('E2E Deep Flow', () => {
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    page = await browser.newPage();
  });
  test.afterAll(async () => {
    await page.close();
  });

  /* ── Phase 1: 구매자 회원가입 ──────────────────────────── */
  test('Phase 1: 구매자 회원가입', async () => {
    await page.goto('/register');
    await page.waitForTimeout(1200);
    await shot(page, '01-start');

    // Step 1: Role → click "구매자"
    const roleBtn = page.locator('button').filter({ hasText: '구매자' }).first();
    await roleBtn.waitFor({ state: 'visible', timeout: 5000 });
    await roleBtn.click();
    await page.waitForTimeout(500);
    await clickNext(page);

    // Step 2: Profile
    const emailInput = page.locator('input[placeholder="example@email.com"]');
    if ((await emailInput.count()) > 0) {
      await emailInput.fill(BUYER.email);
      await page.waitForTimeout(200);
      await page.fill('input[placeholder="8자 이상, 영문+숫자+특수문자"]', BUYER.password);
      await page.waitForTimeout(200);
      await page.fill('input[placeholder="비밀번호를 한 번 더 입력해주세요"]', BUYER.password);
      await page.waitForTimeout(200);
      await page.fill('input[placeholder="역핑에서 쓸 이름"]', BUYER.nickname);
      await page.waitForTimeout(500);
      await shot(page, '01-profile');
      await clickNext(page);
    }

    // Step 3: Phone
    const phoneInput = page.locator('input[placeholder="010-0000-0000"]');
    if ((await phoneInput.count()) > 0) {
      await phoneInput.fill(BUYER.phone);
      await page.waitForTimeout(400);
      await clickNext(page);
    }

    // Step 4: Terms — click "전체 동의" label
    const allAgreeLabel = page.locator('span:has-text("전체 동의")');
    if ((await allAgreeLabel.count()) > 0) {
      await allAgreeLabel.click();
      await page.waitForTimeout(500);
      await shot(page, '01-terms');
      await clickNext(page); // This triggers the registration API call
      await page.waitForTimeout(3000); // Wait for API response + redirect
    }
    await shot(page, '01-after-terms');

    // Step 6 (success): Click "역핑 시작하기 →" if it appears
    const startBtn = page.locator('button').filter({ hasText: /역핑.*시작|시작하기/ }).first();
    if ((await startBtn.count()) > 0 && !(await startBtn.isDisabled())) {
      await startBtn.click();
      await page.waitForTimeout(1500);
    }

    // VERIFY: Ensure buyer was actually created (API fallback if UI registration failed)
    await ensureBuyer(page);
    await shot(page, '01-done');
    console.log(`[Phase 1] Buyer ensured: ${BUYER.email}`);
  });

  /* ── Phase 2: 구매자 로그인 ────────────────────────────── */
  test('Phase 2: 구매자 로그인', async () => {
    await login(page, BUYER.email, BUYER.password);
    await shot(page, '02-login');

    const url = page.url();
    console.log(`[Phase 2] After login URL: ${url}`);

    // Get buyer info
    const me = await apiGet(page, '/auth/me');
    if (me.status === 200 && me.data) {
      buyerId = me.data.id ?? me.data.buyer_id;
    }
    // Fallback: try /buyers/me
    if (!buyerId) {
      const meAlt = await apiGet(page, '/buyers/me');
      if (meAlt.status === 200 && meAlt.data) {
        buyerId = meAlt.data.id;
      }
    }
    console.log(`[Phase 2] Buyer ID: ${buyerId}`);
    expect(buyerId).toBeTruthy();
  });

  /* ── Phase 3: 딜 생성 ─────────────────────────────────── */
  test('Phase 3: 딜 생성', async () => {
    const dealRes = await apiPost(page, '/deals/', {
      product_name: `DeepTest AirPods Pro ${TS % 10000}`,
      creator_id: buyerId,
      desired_qty: 10,
      target_price: 280000,
      max_budget: 320000,
      anchor_price: 339000,
      market_price: 339000,
      brand: 'Apple',
    });
    console.log(`[Phase 3] Create deal: ${dealRes.status}`, JSON.stringify(dealRes.data)?.slice(0, 200));

    if (dealRes.status < 300 && dealRes.data) {
      dealId = dealRes.data.id ?? dealRes.data.deal_id;
    }
    expect(dealId).toBeTruthy();
    console.log(`[Phase 3] Deal ID: ${dealId}`);

    // Verify in browser
    await page.goto(`/deal/${dealId}`);
    await page.waitForTimeout(2000);
    await shot(page, '03-deal');
    const body = await page.textContent('body');
    expect(body).toContain('DeepTest');
  });

  /* ── Phase 4: 판매자 가입 → 로그인 → 오퍼 제출 ─────────── */
  test('Phase 4: 판매자 가입 + 로그인 + 오퍼 제출', async () => {
    // 4a. Ensure seller exists
    await ensureSeller(page);
    console.log(`[Phase 4a] Seller ensured: ${SELLER.email}`);

    // 4b. Login as seller (UI + API fallback)
    await login(page, SELLER.email, SELLER.password);

    // If buyer login was used (auth router), try seller-specific login
    if (page.url().includes('/login')) {
      // Seller might use /auth/seller/login
      const sellerToken = await page.evaluate(async ({ email, password }) => {
        const params = new URLSearchParams();
        params.append('username', email);
        params.append('password', password);
        const r = await fetch('/auth/seller/login', { method: 'POST', body: params });
        if (r.status !== 200) return null;
        const data = await r.json();
        const token = data.access_token;
        if (token) {
          localStorage.setItem('access_token', token);
          localStorage.setItem('token', token);
        }
        return token;
      }, { email: SELLER.email, password: SELLER.password });
      if (sellerToken) {
        await page.goto('/');
        await page.waitForTimeout(1500);
      }
    }
    await shot(page, '04-seller-login');

    // Get seller ID
    for (const endpoint of ['/auth/me', '/auth/seller/me', '/sellers/me']) {
      const r = await apiGet(page, endpoint);
      if (r.status === 200 && r.data) {
        sellerId = r.data.id ?? r.data.seller_id;
        if (sellerId) break;
      }
    }
    console.log(`[Phase 4b] Seller ID: ${sellerId}`);

    // 4c. Navigate to offer create page
    await page.goto(`/deal/${dealId}/offer/create`);
    await page.waitForTimeout(2000);
    await shot(page, '04-offer-step1');

    // Step 1: Price & Quantity
    const priceInput = page.locator('input[placeholder="0"]').first();
    if ((await priceInput.count()) > 0) {
      await priceInput.click();
      await priceInput.fill('290000');
      await page.waitForTimeout(300);
    }

    const next1 = page.locator('button').filter({ hasText: /다음/ }).first();
    if ((await next1.count()) > 0 && !(await next1.isDisabled())) {
      await next1.click();
      await page.waitForTimeout(1000);
    }
    await shot(page, '04-offer-step2');

    // Step 2: Shipping & Policy
    const freeShip = page.locator('label, button, div, span').filter({ hasText: /무료배송/ }).first();
    if ((await freeShip.count()) > 0) await freeShip.click();
    await page.waitForTimeout(200);

    const day3 = page.locator('button:has-text("3일")').first();
    if ((await day3.count()) > 0) await day3.click();
    await page.waitForTimeout(200);

    const noWarranty = page.locator('button:has-text("없음")').first();
    if ((await noWarranty.count()) > 0) await noWarranty.click();
    await page.waitForTimeout(200);

    const ruleA1 = page.locator('label, div, span').filter({ hasText: /A1/ }).first();
    if ((await ruleA1.count()) > 0) await ruleA1.click();
    await page.waitForTimeout(200);

    const next2 = page.locator('button').filter({ hasText: /다음/ }).first();
    if ((await next2.count()) > 0 && !(await next2.isDisabled())) {
      await next2.click();
      await page.waitForTimeout(1000);
    }
    await shot(page, '04-offer-step3');

    // Step 3: Submit
    const submitOffer = page.locator('button').filter({ hasText: /오퍼.*제출|제출하기/ }).first();
    if ((await submitOffer.count()) > 0 && !(await submitOffer.isDisabled())) {
      await submitOffer.click();
      await page.waitForTimeout(3000);
    }
    await shot(page, '04-offer-submitted');

    // Check if offer was created
    const offersRes = await apiGet(page, `/v3_6/offers?deal_id=${dealId}`);
    if (offersRes.status === 200 && Array.isArray(offersRes.data) && offersRes.data.length > 0) {
      offerId = offersRes.data[0].id;
    }

    // Fallback: create offer via API
    if (!offerId) {
      console.log('[Phase 4c] UI offer failed, creating via API...');
      const offerApi = await apiPost(page, '/v3_6/offers', {
        deal_id: dealId,
        seller_id: sellerId,
        price: 290000,
        total_available_qty: 20,
        delivery_days: 3,
        shipping_mode: 'INCLUDED',
      });
      console.log(`[Phase 4c] API offer: ${offerApi.status}`, JSON.stringify(offerApi.data)?.slice(0, 200));
      if (offerApi.status < 300 && offerApi.data) {
        offerId = offerApi.data.id ?? offerApi.data.offer_id;
      }
      // Re-check
      if (!offerId) {
        const retry = await apiGet(page, `/v3_6/offers?deal_id=${dealId}`);
        if (retry.status === 200 && Array.isArray(retry.data) && retry.data.length > 0) {
          offerId = retry.data[0].id;
        }
      }
    }

    console.log(`[Phase 4c] Offer ID: ${offerId}`);
    expect(offerId).toBeTruthy();
  });

  /* ── Phase 5: 구매자 예약 + 결제 ───────────────────────── */
  test('Phase 5: 구매자 예약 + 결제', async () => {
    // Login as buyer
    await login(page, BUYER.email, BUYER.password);

    // Create reservation via API
    const resv = await apiPost(page, '/v3_6/reservations', {
      deal_id: dealId,
      offer_id: offerId,
      buyer_id: buyerId,
      qty: 2,
    });
    console.log(`[Phase 5] Reserve: ${resv.status}`, JSON.stringify(resv.data)?.slice(0, 200));

    if (resv.status < 300 && resv.data) {
      reservationId = resv.data.id ?? resv.data.reservation_id;
    }
    expect(reservationId).toBeTruthy();
    console.log(`[Phase 5] Reservation ID: ${reservationId}`);

    // Pay
    const pay = await apiPost(page, '/v3_6/reservations/pay', {
      reservation_id: reservationId,
      buyer_id: buyerId,
      paid_amount: 580000,
    });
    console.log(`[Phase 5] Pay: ${pay.status}`, JSON.stringify(pay.data)?.slice(0, 200));
    expect(pay.status).toBeLessThan(300);

    // Verify in MyOrdersPage
    await page.goto('/my-orders');
    await page.waitForTimeout(2000);
    await shot(page, '05-paid');
    const body = await page.textContent('body');
    console.log(`[Phase 5] MyOrders shows order: ${body?.includes('결제완료') || body?.includes('DeepTest')}`);
  });

  /* ── Phase 6: 판매자 배송 처리 ─────────────────────────── */
  test('Phase 6: 판매자 배송 처리', async () => {
    // Login as seller (API for efficiency)
    await page.evaluate(() => localStorage.clear());
    const sellerToken = await page.evaluate(async ({ email, password }) => {
      const params = new URLSearchParams();
      params.append('username', email);
      params.append('password', password);
      // Try both login endpoints
      for (const url of ['/auth/seller/login', '/auth/login']) {
        const r = await fetch(url, { method: 'POST', body: params });
        if (r.status === 200) {
          const data = await r.json();
          if (data.access_token) {
            localStorage.setItem('access_token', data.access_token);
            return data.access_token;
          }
        }
      }
      return null;
    }, { email: SELLER.email, password: SELLER.password });
    console.log(`[Phase 6] Seller login: ${sellerToken ? 'OK' : 'FAIL'}`);

    // Ship via API
    const ship = await apiPost(page, `/v3_6/reservations/${reservationId}/ship`, {
      tracking_number: `DEEP${TS % 100000}`,
      shipping_carrier: 'CJ대한통운',
    });
    console.log(`[Phase 6] Ship: ${ship.status}`, JSON.stringify(ship.data)?.slice(0, 200));
    expect(ship.status).toBeLessThan(300);
    await shot(page, '06-shipped');
  });

  /* ── Phase 7: 구매자 수취확인 (UI) ─────────────────────── */
  test('Phase 7: 구매자 수취확인', async () => {
    await login(page, BUYER.email, BUYER.password);

    await page.goto('/my-orders');
    await page.waitForTimeout(2000);

    // Click "배송중" filter
    const shippedTab = page.locator('button').filter({ hasText: /배송중/ }).first();
    if ((await shippedTab.count()) > 0) {
      await shippedTab.click();
      await page.waitForTimeout(1000);
    }
    await shot(page, '07-shipped-orders');

    // Click "수령 확인"
    const confirmBtn = page.locator('button').filter({ hasText: /수령.*확인/ }).first();
    if ((await confirmBtn.count()) > 0) {
      await confirmBtn.click();
      await page.waitForTimeout(2500);
      console.log('[Phase 7] Clicked arrival confirm in UI');
    } else {
      console.log('[Phase 7] UI button not found, using API');
      const confirm = await apiPost(page, `/v3_6/reservations/${reservationId}/arrival-confirm`, {
        buyer_id: buyerId,
      });
      console.log(`[Phase 7] API confirm: ${confirm.status}`);
    }
    await shot(page, '07-confirmed');

    // Verify
    await page.goto('/my-orders');
    await page.waitForTimeout(2000);
    const body = await page.textContent('body');
    console.log(`[Phase 7] Shows delivered: ${body?.includes('배송완료')}`);
  });

  /* ── Phase 8: 구매자 환불 요청 (UI) ────────────────────── */
  test('Phase 8: 구매자 환불 요청', async () => {
    await page.goto('/my-orders');
    await page.waitForTimeout(2000);

    // Show all orders
    const allTab = page.locator('button').filter({ hasText: /^전체$/ }).first();
    if ((await allTab.count()) > 0) {
      await allTab.click();
      await page.waitForTimeout(1000);
    }
    await shot(page, '08-before-refund');

    // Click "환불요청"
    const refundBtn = page.locator('button').filter({ hasText: /환불요청|환불 요청/ }).first();
    if ((await refundBtn.count()) > 0) {
      await refundBtn.click();
      await page.waitForTimeout(1200);

      // Select reason
      const reasonBtn = page.locator('button').filter({ hasText: '단순 변심' }).first();
      if ((await reasonBtn.count()) > 0) {
        await reasonBtn.click();
        await page.waitForTimeout(500);
      }
      await shot(page, '08-refund-modal');

      // Submit
      const submitRefund = page.locator('button').filter({ hasText: /환불.*요청하기/ }).first();
      if ((await submitRefund.count()) > 0 && !(await submitRefund.isDisabled())) {
        await submitRefund.click();
        await page.waitForTimeout(2500);
        console.log('[Phase 8] Refund requested via UI');
      }
    } else {
      console.log('[Phase 8] UI refund button not found, using API');
      const refund = await apiPost(page, '/v3_6/reservations/refund', {
        reservation_id: reservationId,
        reason: '단순 변심',
        requested_by: 'BUYER',
      });
      console.log(`[Phase 8] API refund: ${refund.status}`);
    }
    await shot(page, '08-refund-done');

    await page.goto('/my-orders');
    await page.waitForTimeout(2000);
    const body = await page.textContent('body');
    console.log(`[Phase 8] Shows cancel/refund: ${body?.includes('취소') || body?.includes('환불')}`);
  });

  /* ── Phase 9: 핑퐁이 대화 20개 ─────────────────────────── */
  test('Phase 9: 핑퐁이 대화 20개', async () => {
    await page.goto('/');
    await page.waitForTimeout(1000);

    let passed = 0;

    for (let i = 0; i < PINGPONG_QS.length; i++) {
      if (i > 0 && i % 8 === 0) {
        console.log(`[Phase 9] Rate-limit pause... (${i}/${PINGPONG_QS.length} done)`);
        await page.waitForTimeout(62000);
      }

      const q = PINGPONG_QS[i];
      try {
        const res = await apiPost(page, '/v3_6/pingpong/ask', { question: q, buyer_id: buyerId });
        const ok = res.status === 200 && res.data?.answer;
        if (ok) passed++;
        console.log(`  [${i + 1}/20] ${ok ? 'PASS' : 'FAIL'} "${q}" → ${String(res.data?.answer || res.data?.detail || '').slice(0, 60)}`);
      } catch {
        console.log(`  [${i + 1}/20] ERROR "${q}"`);
      }
    }

    console.log(`[Phase 9] Pingpong: ${passed}/${PINGPONG_QS.length} PASS`);
    await shot(page, '09-pingpong');
    expect(passed).toBeGreaterThanOrEqual(15);
  });

  /* ── Phase 10: 관리자 대시보드 ─────────────────────────── */
  test('Phase 10: 관리자 대시보드 + 정산', async () => {
    await login(page, ADMIN.email, ADMIN.password);
    await shot(page, '10-admin-login');
    console.log(`[Phase 10] Admin login URL: ${page.url()}`);

    // Dashboard
    await page.goto('/admin');
    await page.waitForTimeout(2000);
    await shot(page, '10-dashboard');
    const dash = await page.textContent('body');
    console.log(`[Phase 10] Dashboard: buyers=${dash?.includes('구매자')}, sellers=${dash?.includes('판매자')}, deals=${dash?.includes('딜')}`);

    // Sellers
    await page.goto('/admin/sellers');
    await page.waitForTimeout(2000);
    await shot(page, '10-sellers');

    // Settlements
    await page.goto('/admin/settlements');
    await page.waitForTimeout(2000);
    await shot(page, '10-settlements');

    // Disputes
    await page.goto('/admin/disputes');
    await page.waitForTimeout(2000);
    await shot(page, '10-disputes');

    // Buyers
    await page.goto('/admin/buyers');
    await page.waitForTimeout(2000);
    await shot(page, '10-buyers');

    console.log('[Phase 10] Admin navigation complete');
  });
});
