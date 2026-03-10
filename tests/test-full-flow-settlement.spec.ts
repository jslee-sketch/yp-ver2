import { test, expect } from '@playwright/test';

/**
 * 풀 플로우 E2E 테스트: 딜→오퍼→예약→결제→배송→수취확인→정산APPROVED→세금계산서
 * 5건 생성하여 /admin/settlements, /admin/tax-invoices 데이터 확보
 */

const BASE = 'https://web-production-defb.up.railway.app';
const COUNT = 5;

// ── helpers ──────────────────────────────────────────────

async function api(page: any, method: string, path: string, body?: any, token?: string) {
  return page.evaluate(
    async ({ base, method, path, body, token }: any) => {
      const opts: any = { method, headers: { 'Content-Type': 'application/json' } };
      if (token) opts.headers['Authorization'] = `Bearer ${token}`;
      if (body) opts.body = JSON.stringify(body);
      const r = await fetch(`${base}${path}`, opts);
      const text = await r.text();
      try { return { status: r.status, data: JSON.parse(text) }; }
      catch { return { status: r.status, data: text }; }
    },
    { base: BASE, method, path, body, token },
  );
}

async function formLogin(page: any, url: string, username: string, password: string) {
  return page.evaluate(
    async ({ base, url, username, password }: any) => {
      const params = new URLSearchParams();
      params.append('username', username);
      params.append('password', password);
      const r = await fetch(`${base}${url}`, { method: 'POST', body: params });
      if (r.status === 200) {
        const d = await r.json();
        return d.access_token || '';
      }
      return '';
    },
    { base: BASE, url, username, password },
  );
}

function parseJwt(token: string): any {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(payload));
  } catch { return {}; }
}

// ── shared state ──────────────────────────────────────────

let buyerToken = '';
let sellerToken = '';
let adminToken = '';
let buyerId = 0;
let sellerId = 0;

const dealIds: number[] = [];
const offerIds: number[] = [];
const reservationIds: number[] = [];
const amountTotals: number[] = [];
const settlementIds: number[] = [];

// ── tests ─────────────────────────────────────────────────

test.describe.serial('풀 플로우 정산 E2E (5건)', () => {

  // ── Phase 0: 로그인 ──

  test('T01 Buyer 로그인', async ({ page }) => {
    await page.goto(BASE);
    buyerToken = await formLogin(page, '/auth/login', 'realtest1@e2e.com', 'Test1234!');
    expect(buyerToken).toBeTruthy();
    const jwt = parseJwt(buyerToken);
    buyerId = Number(jwt.sub || jwt.user_id || 0);
    expect(buyerId).toBeGreaterThan(0);
    console.log(`T01 Buyer OK  id=${buyerId}`);
  });

  test('T02 Seller 로그인', async ({ page }) => {
    await page.goto(BASE);
    // seller 로그인: /auth/seller/login 우선, 실패 시 /auth/login
    sellerToken = await formLogin(page, '/auth/seller/login', 'seller@yeokping.com', 'seller1234!');
    if (!sellerToken) {
      sellerToken = await formLogin(page, '/auth/login', 'seller@yeokping.com', 'seller1234!');
    }
    expect(sellerToken).toBeTruthy();
    const jwt = parseJwt(sellerToken);
    sellerId = Number(jwt.seller_id || jwt.sub || 0);
    expect(sellerId).toBeGreaterThan(0);
    console.log(`T02 Seller OK  id=${sellerId}`);
  });

  test('T03 Admin 로그인', async ({ page }) => {
    await page.goto(BASE);
    adminToken = await formLogin(page, '/auth/login', 'admin@yeokping.com', 'admin1234!');
    if (!adminToken) {
      adminToken = await formLogin(page, '/auth/seller/login', 'admin@yeokping.com', 'admin1234!');
    }
    expect(adminToken).toBeTruthy();
    console.log('T03 Admin OK');
  });

  // ── Phase 1: 딜 5건 생성 ──

  test('T04 딜 5건 생성', async ({ page }) => {
    await page.goto(BASE);
    for (let i = 0; i < COUNT; i++) {
      const r = await api(page, 'POST', '/deals/', {
        product_name: `E2E 정산테스트 ${i + 1}`,
        creator_id: buyerId,
        desired_qty: 10,
        anchor_price: 50000,
      }, buyerToken);
      console.log(`  Deal ${i + 1}: status=${r.status} id=${r.data?.id}`);
      expect(r.status).toBeLessThan(300);
      const id = r.data?.id;
      expect(id).toBeTruthy();
      dealIds.push(id);
    }
    expect(dealIds).toHaveLength(COUNT);
    console.log(`T04 Deals created: ${dealIds}`);
  });

  // ── Phase 2: 오퍼 5건 (cooling_days=0) ──

  test('T05 오퍼 5건 생성 (cooling_days=0)', async ({ page }) => {
    await page.goto(BASE);
    for (let i = 0; i < COUNT; i++) {
      const r = await api(page, 'POST', '/v3_6/offers', {
        deal_id: dealIds[i],
        seller_id: sellerId,
        price: 50000,
        total_available_qty: 10,
        cooling_days: 0,
        delivery_days: 3,
        shipping_mode: 'INCLUDED',
        shipping_fee_per_reservation: 0,
      }, sellerToken);
      console.log(`  Offer ${i + 1}: status=${r.status} id=${r.data?.id}`);
      expect(r.status).toBeLessThan(300);
      const id = r.data?.id;
      expect(id).toBeTruthy();
      offerIds.push(id);
    }
    expect(offerIds).toHaveLength(COUNT);
    console.log(`T05 Offers created: ${offerIds}`);
  });

  // ── Phase 3: 예약 5건 ──

  test('T06 예약 5건 생성', async ({ page }) => {
    await page.goto(BASE);
    for (let i = 0; i < COUNT; i++) {
      const r = await api(page, 'POST', '/v3_6/reservations', {
        deal_id: dealIds[i],
        offer_id: offerIds[i],
        buyer_id: buyerId,
        qty: 2,
      }, buyerToken);
      console.log(`  Reservation ${i + 1}: status=${r.status} id=${r.data?.id} amount=${r.data?.amount_total}`);
      expect(r.status).toBeLessThan(300);
      const id = r.data?.id;
      expect(id).toBeTruthy();
      reservationIds.push(id);
      amountTotals.push(r.data?.amount_total || 100000);
    }
    expect(reservationIds).toHaveLength(COUNT);
    console.log(`T06 Reservations created: ${reservationIds}`);
  });

  // ── Phase 4: 결제 5건 ──

  test('T07 결제 5건', async ({ page }) => {
    await page.goto(BASE);
    for (let i = 0; i < COUNT; i++) {
      const r = await api(page, 'POST', '/v3_6/reservations/pay', {
        reservation_id: reservationIds[i],
        buyer_id: buyerId,
        paid_amount: amountTotals[i],
      }, buyerToken);
      console.log(`  Pay ${i + 1}: status=${r.status} phase=${r.data?.phase}`);
      expect(r.status).toBeLessThan(300);
    }
    console.log('T07 All paid');
  });

  // ── Phase 5: 배송 5건 ──

  test('T08 배송 5건', async ({ page }) => {
    await page.goto(BASE);
    for (let i = 0; i < COUNT; i++) {
      const r = await api(page, 'POST', `/v3_6/reservations/${reservationIds[i]}/ship`, {
        seller_id: sellerId,
        shipping_carrier: 'CJ대한통운',
        tracking_number: `E2ESETTLE${String(i + 1).padStart(3, '0')}`,
      }, sellerToken);
      console.log(`  Ship ${i + 1}: status=${r.status}`);
      expect(r.status).toBeLessThan(300);
    }
    console.log('T08 All shipped');
  });

  // ── Phase 6: 수취확인 5건 ──

  test('T09 수취확인 5건', async ({ page }) => {
    await page.goto(BASE);
    for (let i = 0; i < COUNT; i++) {
      const r = await api(page, 'POST', `/v3_6/reservations/${reservationIds[i]}/arrival-confirm`, {
        buyer_id: buyerId,
      }, buyerToken);
      console.log(`  Arrive ${i + 1}: status=${r.status}`);
      expect(r.status).toBeLessThan(300);
    }
    console.log('T09 All arrival-confirmed');
  });

  // ── Phase 7: 정산 refresh (PENDING/HOLD → READY) ──

  test('T10 정산 refresh-ready (cooling_days=0 → 즉시 READY)', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/settlements/refresh-ready?limit=200', undefined, adminToken);
    console.log(`T10 refresh-ready: status=${r.status}`, JSON.stringify(r.data));
    expect(r.status).toBeLessThan(300);
    // cooling_days=0이므로 backfilled + updated 모두 즉시 전환
    const updated = r.data?.updated || 0;
    console.log(`T10 updated=${updated}, backfilled=${r.data?.backfilled}`);
    // updated가 0이면 한번 더 호출 (backfill 후 ready_at이 now 이하가 됨)
    if (updated < COUNT) {
      const r2 = await api(page, 'POST', '/settlements/refresh-ready?limit=200', undefined, adminToken);
      console.log(`T10 retry: updated=${r2.data?.updated}`);
    }
  });

  // ── Phase 8: 정산 승인 5건 ──

  test('T11 정산 조회 + 승인 5건', async ({ page }) => {
    await page.goto(BASE);

    // 셀러별 정산 조회
    const listR = await api(page, 'GET', `/payments/settlements/${sellerId}`, undefined, adminToken);
    console.log(`  settlements count=${Array.isArray(listR.data) ? listR.data.length : '?'}`);
    expect(listR.status).toBeLessThan(300);

    // READY 상태인 건만 필터 → 승인
    const readyRows = (Array.isArray(listR.data) ? listR.data : [])
      .filter((s: any) => s.status === 'READY');
    console.log(`  READY count=${readyRows.length}`);

    for (const s of readyRows) {
      const appR = await page.evaluate(
        async ({ base, id, token }: any) => {
          const r = await fetch(`${base}/settlements/${id}/approve`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
              'X-Actor-Id': '999',
            },
          });
          const text = await r.text();
          try { return { status: r.status, data: JSON.parse(text) }; }
          catch { return { status: r.status, data: text }; }
        },
        { base: BASE, id: s.id, token: adminToken },
      );
      console.log(`  Approve settlement ${s.id}: status=${appR.status} → ${appR.data?.status}`);
      expect(appR.status).toBeLessThan(300);
      settlementIds.push(s.id);
    }
    console.log(`T11 Approved ${settlementIds.length} settlements`);
    expect(settlementIds.length).toBeGreaterThanOrEqual(COUNT);
  });

  // ── Phase 9: 검증 ──

  test('T12 정산 APPROVED 검증', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', `/payments/settlements/${sellerId}`, undefined, adminToken);
    expect(r.status).toBeLessThan(300);
    const approved = (Array.isArray(r.data) ? r.data : [])
      .filter((s: any) => s.status === 'APPROVED');
    console.log(`T12 APPROVED count=${approved.length}`);
    expect(approved.length).toBeGreaterThanOrEqual(COUNT);
  });

  test('T13 세금계산서 생성 검증', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/v3_6/tax-invoices', undefined, adminToken);
    console.log(`T13 tax-invoices: status=${r.status}, total=${r.data?.total}`);
    expect(r.status).toBeLessThan(300);
    const total = r.data?.total || 0;
    console.log(`T13 세금계산서 total=${total}`);
    expect(total).toBeGreaterThanOrEqual(COUNT);
  });

  test('T14 요약', async ({ page }) => {
    console.log('\n========== E2E 정산 풀플로우 요약 ==========');
    console.log(`Deals:        ${dealIds}`);
    console.log(`Offers:       ${offerIds}`);
    console.log(`Reservations: ${reservationIds}`);
    console.log(`Amounts:      ${amountTotals}`);
    console.log(`Settlements:  ${settlementIds}`);
    console.log(`Buyer ID:     ${buyerId}`);
    console.log(`Seller ID:    ${sellerId}`);
    console.log('=============================================\n');
    expect(true).toBe(true);
  });
});
