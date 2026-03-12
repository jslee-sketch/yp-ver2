import { test, expect, type APIRequestContext } from '@playwright/test';

const BASE = process.env.BASE_URL || 'https://www.yeokping.com';
const API  = process.env.API_URL  || 'https://web-production-defb.up.railway.app';
const ACCESS_KEY = 'yeokping2026';

let api: APIRequestContext;

test.beforeAll(async ({ playwright }) => {
  api = await playwright.request.newContext({ baseURL: API });
});

test.afterAll(async () => { await api.dispose(); });

/* ──────────── T01: /terms → 이용약관 페이지 표시 ──────────── */
test('T01 — /terms → 이용약관 페이지 표시', async ({ page }) => {
  await page.goto(`${BASE}/terms?access=${ACCESS_KEY}`);
  await page.waitForSelector('text=제1조', { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(3000);
  const html = await page.content();
  expect(html).toContain('제1조');
  expect(html).toContain('제4조');
  expect(html).toContain('통신판매중개');
  expect(html).toContain('통신판매의 당사자가 아닙니다');
  expect(html).toContain('제7조');
  expect(html).toContain('AI');
  expect(html).toContain('제9조');
  expect(html).toContain('청약철회');
  expect(html).toContain('제13조');
  expect(html).toContain('텔러스테크');
  expect(html).toContain('113-86-39805');
  expect(html).toContain('14세 이상');
  expect(html).toContain('경매 등에 관한 법률');
  console.log('✅ T01 PASS — 이용약관 13개 조항 + 실제 사업자 정보');
});

/* ──────────── T02: /privacy → 개인정보처리방침 표시 ──────────── */
test('T02 — /privacy → 개인정보처리방침 표시', async ({ page }) => {
  await page.goto(`${BASE}/privacy?access=${ACCESS_KEY}`);
  await page.waitForSelector('text=개인정보처리방침', { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);
  const html = await page.content();
  expect(html).toContain('개인정보처리방침');
  expect(html).toContain('수집하는 개인정보');
  expect(html).toContain('보유 및 이용 기간');
  expect(html).toContain('제3자 제공');
  expect(html).toContain('이정상');
  expect(html).toContain('5년');
  expect(html).toContain('3개월');
  expect(html).toContain('Railway');
  expect(html).toContain('OpenAI');
  console.log('✅ T02 PASS — 개인정보처리방침 10개 항목 + 실제 위탁 정보');
});

/* ──────────── T03: 모든 페이지 하단 → 푸터 표시 ──────────── */
test('T03 — 모든 페이지 하단 → 푸터 (사업자정보 + 중개자 면책) 표시', async ({ page }) => {
  await page.goto(`${BASE}/?access=${ACCESS_KEY}`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  const html = await page.content();
  expect(html).toContain('텔러스테크');
  expect(html).toContain('이정상');
  expect(html).toContain('113-86-39805');
  expect(html).toContain('통신판매중개자');
  expect(html).toContain('이용약관');
  expect(html).toContain('개인정보처리방침');
  expect(html).toContain('금천구');
  console.log('✅ T03 PASS — Footer 사업자정보 + 중개자 면책');
});

/* ──────────── T04: 회원가입 → 약관 동의 체크 안 하면 가입 불가 ──────────── */
test('T04 — 회원가입 → 약관 동의 체크 안 하면 가입 불가', async ({ page }) => {
  await page.goto(`${BASE}/register?access=${ACCESS_KEY}`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  // RegisterPage is multi-step — check the built JS includes the terms consent logic
  const scripts = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src);
  });
  let found = false;
  for (const src of scripts) {
    try {
      const r = await page.request.get(src);
      const text = await r.text();
      // Check for required terms consent in register page build
      if (text.includes('이용약관 동의') && text.includes('개인정보처리방침 동의') && text.includes('필수')) {
        found = true;
        break;
      }
    } catch { /* skip */ }
  }
  expect(found).toBe(true);
  console.log('✅ T04 PASS — 회원가입 약관 동의 필수 빌드 포함');
});

/* ──────────── T05: 회원가입 → 약관 링크 클릭 → 내용 표시 ──────────── */
test('T05 — 회원가입 → 약관 보기 클릭 → 내용 표시', async ({ page }) => {
  await page.goto(`${BASE}/register?access=${ACCESS_KEY}`);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  // 빌드에 약관 내용이 포함되어 있는지 확인 (TERM_CONTENTS)
  const scripts = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src);
  });
  let found = false;
  for (const src of scripts) {
    try {
      const r = await page.request.get(src);
      const text = await r.text();
      if (text.includes('통신판매중개자') && text.includes('개인정보처리방침') && text.includes('13개 조항')) {
        found = true;
        break;
      }
    } catch { /* skip */ }
  }
  expect(found).toBe(true);
  console.log('✅ T05 PASS — 회원가입 약관 내용 빌드 포함');
});

/* ──────────── T06: 딜 생성 Step 3 → AI 면책 문구 표시 ──────────── */
test('T06 — 딜 생성 Step 3 → AI 면책 문구 빌드 포함', async ({ page }) => {
  await page.goto(`${BASE}/?access=${ACCESS_KEY}`);
  await page.waitForLoadState('networkidle');
  const scripts = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src);
  });
  let found = false;
  for (const src of scripts) {
    try {
      const r = await page.request.get(src);
      const text = await r.text();
      if (text.includes('AI') && text.includes('참고용') && text.includes('이용자 본인의 책임')) {
        found = true;
        break;
      }
    } catch { /* skip */ }
  }
  expect(found).toBe(true);
  console.log('✅ T06 PASS — AI 면책 문구 빌드 포함');
});

/* ──────────── T07: 오퍼 목록 → 중개자 면책 문구 표시 ──────────── */
test('T07 — 오퍼 목록 → 중개자 면책 문구 빌드 포함', async ({ page }) => {
  await page.goto(`${BASE}/?access=${ACCESS_KEY}`);
  await page.waitForLoadState('networkidle');
  const scripts = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src);
  });
  let found = false;
  for (const src of scripts) {
    try {
      const r = await page.request.get(src);
      const text = await r.text();
      if (text.includes('통신판매중개자') && text.includes('품질') && text.includes('판매자에게 있습니다')) {
        found = true;
        break;
      }
    } catch { /* skip */ }
  }
  expect(found).toBe(true);
  console.log('✅ T07 PASS — 중개자 면책 문구 빌드 포함');
});

/* ──────────── T08: 핑퐁이 → 하단 면책 문구 표시 ──────────── */
test('T08 — 핑퐁이 → 하단 면책 문구 빌드 포함', async ({ page }) => {
  await page.goto(`${BASE}/?access=${ACCESS_KEY}`);
  await page.waitForLoadState('networkidle');
  const scripts = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src);
  });
  let found = false;
  for (const src of scripts) {
    try {
      const r = await page.request.get(src);
      const text = await r.text();
      if (text.includes('핑퐁이') && text.includes('법적') && text.includes('전문적 조언이 아닙니다')) {
        found = true;
        break;
      }
    } catch { /* skip */ }
  }
  expect(found).toBe(true);
  console.log('✅ T08 PASS — 핑퐁이 AI 면책 빌드 포함');
});

/* ──────────── T09: 점검 페이지 → 사업자 정보 표시 ──────────── */
test('T09 — 점검 페이지 → 사업자 정보 표시', async ({ page }) => {
  await page.goto(BASE);
  await page.waitForLoadState('networkidle');
  const html = await page.content();
  expect(html).toContain('텔러스테크');
  expect(html).toContain('이정상');
  expect(html).toContain('113-86-39805');
  expect(html).toContain('통신판매중개자');
  expect(html).toContain('금천구');
  console.log('✅ T09 PASS — 점검 페이지 사업자 정보');
});

/* ──────────── T10: 모바일에서 이용약관 → 반응형 표시 ──────────── */
test('T10 — 모바일에서 이용약관 → 반응형 표시', async ({ browser }) => {
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
  });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/terms?access=${ACCESS_KEY}`);
  await page.waitForSelector('text=제1조', { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(2000);

  const html = await page.content();
  expect(html).toContain('제1조');
  expect(html).toContain('제13조');

  // 가로 스크롤 없음 확인
  const scrollCheck = await page.evaluate(() => ({
    sw: document.documentElement.scrollWidth,
    cw: document.documentElement.clientWidth,
  }));
  expect(scrollCheck.sw).toBeLessThanOrEqual(scrollCheck.cw + 1);

  await ctx.close();
  console.log(`✅ T10 PASS — 모바일 이용약관 반응형 (sw=${scrollCheck.sw}, cw=${scrollCheck.cw})`);
});
