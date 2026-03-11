import { test, expect } from '@playwright/test';

const BASE = 'https://web-production-defb.up.railway.app';
const TS = Date.now();

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

async function loginAdmin(page: any) {
  return page.evaluate(async (base: string) => {
    const params = new URLSearchParams();
    params.append('username', 'admin@yeokping.com');
    params.append('password', 'admin1234!');
    for (const url of ['/auth/login', '/auth/seller/login']) {
      const r = await fetch(`${base}${url}`, { method: 'POST', body: params });
      if (r.status === 200) {
        const d = await r.json();
        if (d.access_token) return d.access_token;
      }
    }
    return '';
  }, BASE);
}

test.describe.serial('세금계산서 이메일 분리 테스트', () => {
  let adminToken = '';
  let sellerToken = '';
  let sellerId = 0;
  let actToken = '';
  let actId = 0;

  test('T1 Admin 로그인', async ({ page }) => {
    await page.goto(BASE);
    adminToken = await loginAdmin(page);
    expect(adminToken).toBeTruthy();
    console.log('Admin token OK');
  });

  test('T2 Seller 가입 시 tax_invoice_email 전달', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/auth/social/register', {
      social_provider: 'kakao',
      social_id: `taxtest_sell_${TS}`,
      role: 'seller',
      nickname: `택스셀러${TS % 10000}`,
      email: `taxsell_${TS}@test.com`,
      business_name: '택스테스트상점',
      business_number: `${String(TS).slice(-10)}`,
      tax_invoice_email: `tax_sell_${TS}@invoice.com`,
    });
    console.log(`T2 status=${r.status}`);
    expect([200, 201]).toContain(r.status);
    sellerToken = r.data?.access_token || '';
    expect(sellerToken).toBeTruthy();

    // JWT에서 seller_id 추출
    const info = await page.evaluate((t: string) => {
      try { return JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))); }
      catch { return {}; }
    }, sellerToken);
    sellerId = Number(info.seller_id || info.sub || 0);
    console.log(`T2 sellerId=${sellerId}, token OK`);
  });

  test('T3 Seller 프로필에서 tax_invoice_email 확인', async ({ page }) => {
    await page.goto(BASE);
    if (!sellerId) { console.log('SKIP: no sellerId'); return; }
    // admin으로 seller 조회
    const r = await api(page, 'GET', `/sellers/${sellerId}`, undefined, adminToken);
    console.log(`T3 status=${r.status}, tax_invoice_email=${r.data?.tax_invoice_email}`);
    expect(r.status).toBe(200);
    expect(r.data?.tax_invoice_email).toBe(`tax_sell_${TS}@invoice.com`);
  });

  test('T4 Seller business-info PATCH로 tax_invoice_email 변경', async ({ page }) => {
    await page.goto(BASE);
    if (!sellerId) { console.log('SKIP'); return; }
    const newEmail = `updated_tax_${TS}@invoice.com`;
    const r = await api(page, 'PATCH', `/sellers/${sellerId}/business-info`, {
      tax_invoice_email: newEmail,
    }, adminToken);
    console.log(`T4 status=${r.status}, changed=${JSON.stringify(r.data?.changed_fields)}`);
    expect(r.status).toBe(200);
    expect(r.data?.changed_fields).toContain('tax_invoice_email');

    // 확인
    const check = await api(page, 'GET', `/sellers/${sellerId}`, undefined, adminToken);
    expect(check.data?.tax_invoice_email).toBe(newEmail);
  });

  test('T5 Seller business-info 잘못된 이메일 형식 거부', async ({ page }) => {
    await page.goto(BASE);
    if (!sellerId) { console.log('SKIP'); return; }
    const r = await api(page, 'PATCH', `/sellers/${sellerId}/business-info`, {
      tax_invoice_email: 'not-an-email',
    }, adminToken);
    console.log(`T5 status=${r.status}`);
    expect(r.status).toBe(400);
  });

  test('T6 Actuator(사업자) 가입 시 tax_invoice_email 전달', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/auth/social/register', {
      social_provider: 'kakao',
      social_id: `taxtest_act_${TS}`,
      role: 'actuator',
      nickname: `택스액추${TS % 10000}`,
      email: `taxact_${TS}@test.com`,
      is_business: true,
      business_name: '택스액추법인',
      business_number: `${String(TS + 1).slice(-10)}`,
      tax_invoice_email: `tax_act_${TS}@invoice.com`,
    });
    console.log(`T6 status=${r.status}`);
    expect([200, 201]).toContain(r.status);
    actToken = r.data?.access_token || '';
    expect(actToken).toBeTruthy();

    const info = await page.evaluate((t: string) => {
      try { return JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))); }
      catch { return {}; }
    }, actToken);
    actId = Number(info.actuator_id || info.sub || 0);
    console.log(`T6 actId=${actId}`);
  });

  test('T7 Actuator 프로필에서 tax_invoice_email 확인', async ({ page }) => {
    await page.goto(BASE);
    if (!actId) { console.log('SKIP'); return; }
    const r = await api(page, 'GET', `/actuators/${actId}`, undefined, adminToken);
    console.log(`T7 status=${r.status}, tax_invoice_email=${r.data?.tax_invoice_email}`);
    expect(r.status).toBe(200);
    expect(r.data?.tax_invoice_email).toBe(`tax_act_${TS}@invoice.com`);
  });

  test('T8 Actuator business-info PATCH로 tax_invoice_email 변경', async ({ page }) => {
    await page.goto(BASE);
    if (!actId) { console.log('SKIP'); return; }
    const newEmail = `updated_act_tax_${TS}@invoice.com`;
    const r = await api(page, 'PATCH', `/actuators/${actId}/business-info`, {
      tax_invoice_email: newEmail,
    }, adminToken);
    console.log(`T8 status=${r.status}, changed=${JSON.stringify(r.data?.changed_fields)}`);
    expect(r.status).toBe(200);
    expect(r.data?.changed_fields).toContain('tax_invoice_email');
  });

  test('T9 Actuator business-info 잘못된 이메일 형식 거부', async ({ page }) => {
    await page.goto(BASE);
    if (!actId) { console.log('SKIP'); return; }
    const r = await api(page, 'PATCH', `/actuators/${actId}/business-info`, {
      tax_invoice_email: 'bad-email-format',
    }, adminToken);
    console.log(`T9 status=${r.status}`);
    expect(r.status).toBe(400);
  });

  test('T10 회원가입 시 잘못된 tax_invoice_email 거부', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/auth/social/register', {
      social_provider: 'kakao',
      social_id: `taxtest_bad_${TS}`,
      role: 'seller',
      nickname: `택스배드${TS % 10000}`,
      email: `taxbad_${TS}@test.com`,
      business_name: '배드테스트',
      business_number: `${String(TS + 2).slice(-10)}`,
      tax_invoice_email: 'not-valid',
    });
    console.log(`T10 status=${r.status}`);
    expect(r.status).toBe(400);
  });
});
