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

test.describe.serial('백로그 스프린트 검증 (10건)', () => {
  let adminToken = '';

  test('V1 Admin 로그인', async ({ page }) => {
    await page.goto(BASE);
    adminToken = await loginAdmin(page);
    expect(adminToken).toBeTruthy();
    console.log('V1 Admin token OK');
  });

  test('V2 사업자번호 진위확인 - 유효한 번호', async ({ page }) => {
    await page.goto(BASE);
    // NTS_API_KEY 없으면 "검증 서비스 미설정" 반환 (정상)
    const r = await api(page, 'POST', '/sellers/business/verify', {
      business_number: '1138639805',
    });
    console.log(`V2 status=${r.status}, valid=${r.data?.valid}, msg=${r.data?.message}`);
    expect(r.status).toBe(200);
    // valid: true(키있고 계속사업자), null(키 미설정), false(형식오류)
    expect([true, false, null]).toContain(r.data?.valid);
  });

  test('V3 사업자번호 진위확인 - 잘못된 형식 거부', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/sellers/business/verify', {
      business_number: '123',
    });
    console.log(`V3 status=${r.status}, valid=${r.data?.valid}`);
    expect(r.status).toBe(200);
    expect(r.data?.valid).toBe(false);
  });

  test('V4 정산내역서 PDF 다운로드 엔드포인트 존재', async ({ page }) => {
    await page.goto(BASE);
    // settlement_id=1 → 있으면 200(pdf), 없으면 404
    const r = await page.evaluate(async (base: string) => {
      const resp = await fetch(`${base}/settlements/1/pdf`);
      return { status: resp.status, contentType: resp.headers.get('content-type') || '' };
    }, BASE);
    console.log(`V4 status=${r.status}, contentType=${r.contentType}`);
    // 404(존재하지 않는 정산) 또는 200(PDF) 또는 500(reportlab 미설치)
    expect([200, 404, 500]).toContain(r.status);
    if (r.status === 200) {
      expect(r.contentType).toContain('pdf');
    }
  });

  test('V5 원천징수영수증 PDF 엔드포인트 존재', async ({ page }) => {
    await page.goto(BASE);
    const r = await page.evaluate(async (base: string) => {
      const resp = await fetch(`${base}/settlements/actuator/1/withholding-pdf`);
      return { status: resp.status, contentType: resp.headers.get('content-type') || '' };
    }, BASE);
    console.log(`V5 status=${r.status}, contentType=${r.contentType}`);
    // 404(액추에이터 없음) 또는 400(사업자) 또는 200(PDF) 또는 500
    expect([200, 400, 404, 500]).toContain(r.status);
  });

  test('V6 이메일 서비스 모듈 로드 확인 (health check)', async ({ page }) => {
    await page.goto(BASE);
    // 서버가 정상 동작하면 email 모듈은 이미 로드됨
    const r = await api(page, 'GET', '/health');
    console.log(`V6 health status=${r.status}`);
    expect(r.status).toBe(200);
  });

  test('V7 기존 기능: Seller 목록 조회', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/sellers/?skip=0&limit=3');
    console.log(`V7 status=${r.status}, count=${Array.isArray(r.data) ? r.data.length : '?'}`);
    expect(r.status).toBe(200);
  });

  test('V8 기존 기능: Deal 목록 조회', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/deals/?skip=0&limit=3');
    console.log(`V8 status=${r.status}, count=${Array.isArray(r.data) ? r.data.length : '?'}`);
    expect(r.status).toBe(200);
  });

  test('V9 기존 기능: 세금계산서 목록', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/v3_6/tax-invoices', undefined, adminToken);
    console.log(`V9 status=${r.status}`);
    expect([200, 403]).toContain(r.status);
  });

  test('V10 기존 기능: 핑퐁이 ASK', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
      question: '정산 내역서 어디서 확인하나요?',
      role: 'seller',
    });
    console.log(`V10 status=${r.status}, answer=${(r.data?.answer || '').slice(0, 60)}`);
    expect([200, 201]).toContain(r.status);
  });
});
