import { test, expect, Page, Browser } from '@playwright/test';

const BASE = process.env.BASE_URL || 'https://www.yeokping.com';
const ACCESS_KEY = 'yeokping2026';
const API = process.env.API_URL || 'https://web-production-defb.up.railway.app';

function url(path: string) { return `${BASE}${path}${path.includes('?') ? '&' : '?'}access=${ACCESS_KEY}`; }

const viewports = [
  { name: 'iPhone13', width: 390, height: 844 },
  { name: 'GalaxyS21', width: 360, height: 800 },
  { name: 'Desktop', width: 1920, height: 1080 },
];

interface CheckResult {
  page: string;
  viewport: string;
  issues: string[];
}

const allResults: CheckResult[] = [];

async function checkPage(page: Page, pageName: string, viewport: string): Promise<CheckResult> {
  const issues: string[] = [];

  // 1. 가로 스크롤
  const scrollW = await page.evaluate(() => document.documentElement.scrollWidth);
  const clientW = await page.evaluate(() => document.documentElement.clientWidth);
  if (scrollW > clientW + 5) issues.push(`가로스크롤: ${scrollW}>${clientW}`);

  // 2. 텍스트 잘림
  const truncated = await page.evaluate(() => {
    const results: string[] = [];
    document.querySelectorAll('*').forEach(el => {
      const s = getComputedStyle(el);
      if (s.overflow === 'hidden' && el.scrollWidth > el.clientWidth + 2) {
        const t = el.textContent?.trim().substring(0, 30);
        if (t && t.length > 5) results.push(`"${t}..."`);
      }
    });
    return results.slice(0, 3);
  });
  if (truncated.length > 0) issues.push(`텍스트잘림: ${truncated.join(', ')}`);

  // 3. 화면 밖 요소 + 크기 0 버튼
  const hidden = await page.evaluate(() => {
    const results: string[] = [];
    document.querySelectorAll('button, a, [role="button"], input[type="submit"]').forEach(btn => {
      const r = btn.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) results.push(`크기0: "${btn.textContent?.trim().substring(0, 20)}"`);
      if (r.right < 0 || r.left > window.innerWidth) results.push(`화면밖: "${btn.textContent?.trim().substring(0, 20)}"`);
    });
    return results.slice(0, 3);
  });
  if (hidden.length > 0) issues.push(`요소문제: ${hidden.join(', ')}`);

  // 4. 모바일 터치 사이즈
  if (viewport !== 'Desktop') {
    const small = await page.evaluate(() => {
      const results: string[] = [];
      document.querySelectorAll('button, a').forEach(btn => {
        const r = btn.getBoundingClientRect();
        if (r.height > 0 && r.height < 28 && r.width > 0 && btn.textContent?.trim())
          results.push(`${Math.round(r.height)}px:"${btn.textContent.trim().substring(0, 15)}"`);
      });
      return results.slice(0, 3);
    });
    if (small.length > 0) issues.push(`터치사이즈: ${small.join(', ')}`);
  }

  // 5. 빈 페이지
  const textLen = await page.evaluate(() => document.body.innerText.trim().length);
  if (textLen < 30) issues.push(`빈페이지: ${textLen}자`);

  // 6. 깨진 이미지
  const broken = await page.evaluate(() => {
    const results: string[] = [];
    document.querySelectorAll('img').forEach(img => {
      if (!img.complete || img.naturalWidth === 0) results.push(img.src.substring(0, 50));
    });
    return results;
  });
  if (broken.length > 0) issues.push(`깨진이미지: ${broken.join(', ')}`);

  // 7. 모달/팝업 잘림
  const modalClip = await page.evaluate(() => {
    const results: string[] = [];
    document.querySelectorAll('[role="dialog"], [class*="modal"], [class*="Modal"], [class*="popup"]').forEach(el => {
      const r = el.getBoundingClientRect();
      if (r.right > window.innerWidth + 5 || r.bottom > window.innerHeight + 5)
        results.push('모달잘림');
    });
    return results;
  });
  if (modalClip.length > 0) issues.push(modalClip.join(', '));

  // 스크린샷
  const safeName = pageName.replace(/\//g, '_').replace(/^_/, '') || 'home';
  await page.screenshot({
    path: `test-results/visual/${viewport}/${safeName}.png`,
    fullPage: true,
  });

  const result = { page: pageName, viewport, issues };
  allResults.push(result);
  return result;
}

// ── 로그인 헬퍼 ──
async function login(page: Page, email: string, password: string) {
  await page.goto(url('/login'));
  await page.waitForTimeout(2000);
  await page.fill('input[type="email"], input[name="email"], input[placeholder*="이메일"]', email);
  await page.fill('input[type="password"], input[name="password"], input[placeholder*="비밀번호"]', password);
  await page.click('button[type="submit"], button:has-text("로그인")');
  await page.waitForTimeout(3000);
}

// ══════════════════════════════════════════════════════════
// 공개 페이지 (비로그인)
// ══════════════════════════════════════════════════════════
test.describe.serial('공개 페이지 검사', () => {
  const publicPages = [
    { name: 'home', path: '/' },
    { name: 'deals', path: '/deals' },
    { name: 'login', path: '/login' },
    { name: 'register', path: '/register' },
    { name: 'terms', path: '/terms' },
    { name: 'privacy', path: '/privacy' },
    { name: 'faq', path: '/faq' },
    { name: '404', path: '/asdfgh' },
  ];

  for (const vp of viewports) {
    for (const pg of publicPages) {
      test(`[${vp.name}] ${pg.name}`, async ({ browser }) => {
        const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
        const page = await ctx.newPage();
        await page.goto(url(pg.path));
        await page.waitForTimeout(2500);
        const result = await checkPage(page, pg.name, vp.name);
        await ctx.close();
        // 빈페이지만 실패로 처리 (다른 이슈는 리포트에 기록)
        const critical = result.issues.filter(i => i.startsWith('빈페이지'));
        expect(critical.length, `${pg.name}@${vp.name}: ${critical.join('; ')}`).toBe(0);
      });
    }
  }
});

// ══════════════════════════════════════════════════════════
// 구매자 페이지
// ══════════════════════════════════════════════════════════
test.describe.serial('구매자 페이지 검사', () => {
  const buyerPages = [
    { name: 'buyer-home', path: '/' },
    { name: 'buyer-deals', path: '/deals' },
    { name: 'buyer-search', path: '/search' },
    { name: 'buyer-deal-create', path: '/deal/create' },
    { name: 'buyer-my-orders', path: '/my-orders' },
    { name: 'buyer-my-deals', path: '/my-deals' },
    { name: 'buyer-mypage', path: '/mypage' },
    { name: 'buyer-notifications', path: '/notifications' },
    { name: 'buyer-points', path: '/points' },
    { name: 'buyer-settings', path: '/settings' },
    { name: 'buyer-settings-notifications', path: '/settings/notifications' },
    { name: 'buyer-settings-interests', path: '/settings/interests' },
    { name: 'buyer-completed-deals', path: '/completed-deals' },
    { name: 'buyer-spectating', path: '/spectating' },
  ];

  for (const vp of viewports) {
    test(`[${vp.name}] 구매자 전체`, async ({ browser }) => {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const page = await ctx.newPage();
      await login(page, 'realtest1@e2e.com', 'Test1234!');

      for (const pg of buyerPages) {
        await page.goto(url(pg.path));
        await page.waitForTimeout(2000);
        const result = await checkPage(page, pg.name, vp.name);
        const critical = result.issues.filter(i => i.startsWith('빈페이지'));
        if (critical.length > 0) console.warn(`⚠️ ${pg.name}@${vp.name}: ${critical.join('; ')}`);
      }

      await ctx.close();
    });
  }
});

// ══════════════════════════════════════════════════════════
// 판매자 페이지
// ══════════════════════════════════════════════════════════
test.describe.serial('판매자 페이지 검사', () => {
  const sellerPages = [
    { name: 'seller-dashboard', path: '/seller' },
    { name: 'seller-offers', path: '/seller/offers' },
    { name: 'seller-delivery', path: '/seller/delivery' },
    { name: 'seller-settlements', path: '/seller/settlements' },
    { name: 'seller-tax-invoices', path: '/seller/tax-invoices' },
    { name: 'seller-refunds', path: '/seller/refunds' },
    { name: 'seller-reviews', path: '/seller/reviews' },
    { name: 'seller-business-info', path: '/seller/business-info' },
    { name: 'seller-stats', path: '/seller/stats' },
    { name: 'seller-fees', path: '/seller/fees' },
    { name: 'seller-notifications', path: '/seller/notifications' },
  ];

  for (const vp of viewports) {
    test(`[${vp.name}] 판매자 전체`, async ({ browser }) => {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const page = await ctx.newPage();
      await login(page, 'seller@yeokping.com', 'seller1234!');

      for (const pg of sellerPages) {
        await page.goto(url(pg.path));
        await page.waitForTimeout(2000);
        const result = await checkPage(page, pg.name, vp.name);
        const critical = result.issues.filter(i => i.startsWith('빈페이지'));
        if (critical.length > 0) console.warn(`⚠️ ${pg.name}@${vp.name}: ${critical.join('; ')}`);
      }

      await ctx.close();
    });
  }
});

// ══════════════════════════════════════════════════════════
// 관리자 페이지
// ══════════════════════════════════════════════════════════
test.describe.serial('관리자 페이지 검사', () => {
  const adminPages = [
    { name: 'admin-dashboard', path: '/admin' },
    { name: 'admin-deals', path: '/admin/deals' },
    { name: 'admin-offers', path: '/admin/offers' },
    { name: 'admin-reservations', path: '/admin/reservations' },
    { name: 'admin-sellers', path: '/admin/sellers' },
    { name: 'admin-buyers', path: '/admin/buyers' },
    { name: 'admin-actuators', path: '/admin/actuators' },
    { name: 'admin-settlements', path: '/admin/settlements' },
    { name: 'admin-tax-invoices', path: '/admin/tax-invoices' },
    { name: 'admin-refunds', path: '/admin/refunds' },
    { name: 'admin-delivery', path: '/admin/delivery' },
    { name: 'admin-reports', path: '/admin/reports' },
    { name: 'admin-announcements', path: '/admin/announcements' },
    { name: 'admin-search', path: '/admin/search' },
    { name: 'admin-stats', path: '/admin/stats' },
    { name: 'admin-logs', path: '/admin/logs' },
    { name: 'admin-policy-params', path: '/admin/policy-params' },
    { name: 'admin-minority-report', path: '/admin/minority-report' },
    { name: 'admin-notifications', path: '/admin/notifications' },
  ];

  for (const vp of viewports) {
    test(`[${vp.name}] 관리자 전체`, async ({ browser }) => {
      const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const page = await ctx.newPage();
      await login(page, 'admin@yeokping.com', 'admin1234!');

      for (const pg of adminPages) {
        await page.goto(url(pg.path));
        await page.waitForTimeout(2000);
        const result = await checkPage(page, pg.name, vp.name);
        const critical = result.issues.filter(i => i.startsWith('빈페이지'));
        if (critical.length > 0) console.warn(`⚠️ ${pg.name}@${vp.name}: ${critical.join('; ')}`);
      }

      await ctx.close();
    });
  }
});

// ══════════════════════════════════════════════════════════
// 이펙트 + CSS 검증
// ══════════════════════════════════════════════════════════
test.describe.serial('이펙트 + CSS 검증', () => {
  test('MatrixCodeRain 번들 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await page.evaluate(() => {
      const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src);
      return scripts;
    });
    let found = false;
    for (const src of js) {
      try {
        const content = await page.evaluate(async (u: string) => { const r = await fetch(u); return await r.text(); }, src);
        if (content.includes('시장가 분석 완료')) { found = true; break; }
      } catch {}
    }
    expect(found).toBeTruthy();
  });

  test('PingpongBallAnimation 번들 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await page.evaluate(() => {
      const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src);
      return scripts;
    });
    let found = false;
    for (const src of js) {
      try {
        const content = await page.evaluate(async (u: string) => { const r = await fetch(u); return await r.text(); }, src);
        if (content.includes('핑퐁이가 답변을 준비하고 있어요')) { found = true; break; }
      } catch {}
    }
    expect(found).toBeTruthy();
  });

  test('Premium CSS 애니메이션 포함 (shake, offerBounceIn, scaleIn)', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const cssLinks = await page.evaluate(() =>
      Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l => (l as HTMLLinkElement).href)
    );
    let allCss = '';
    for (const href of cssLinks) {
      try {
        const c = await page.evaluate(async (u: string) => { const r = await fetch(u); return await r.text(); }, href);
        allCss += c;
      } catch {}
    }
    expect(allCss.includes('shake')).toBeTruthy();
    expect(allCss.includes('offerBounceIn')).toBeTruthy();
    expect(allCss.includes('scaleIn')).toBeTruthy();
    expect(allCss.includes('premium-card')).toBeTruthy();
    expect(allCss.includes('glassmorphism') || allCss.includes('glass')).toBeTruthy();
  });

  test('Footer 법적 정보 번들 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await page.evaluate(() => {
      const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src);
      return scripts;
    });
    let found = false;
    for (const src of js) {
      try {
        const content = await page.evaluate(async (u: string) => { const r = await fetch(u); return await r.text(); }, src);
        if (content.includes('113-86-39805') && content.includes('텔러스테크')) { found = true; break; }
      } catch {}
    }
    expect(found).toBeTruthy();
  });

  test('효과음 기본 OFF 확인', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const val = await page.evaluate(() => localStorage.getItem('sound_enabled'));
    expect(val !== 'true').toBeTruthy();
  });

  test('Confetti + PaymentSuccess 번들 포함', async ({ page }) => {
    await page.goto(url('/'));
    await page.waitForTimeout(2000);
    const js = await page.evaluate(() => {
      const scripts = Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src);
      return scripts;
    });
    let hasConfetti = false;
    let hasPayment = false;
    for (const src of js) {
      try {
        const content = await page.evaluate(async (u: string) => { const r = await fetch(u); return await r.text(); }, src);
        if (content.includes('confetti') || content.includes('Confetti')) hasConfetti = true;
        if (content.includes('결제 완료')) hasPayment = true;
      } catch {}
    }
    expect(hasConfetti).toBeTruthy();
    expect(hasPayment).toBeTruthy();
  });
});

// ══════════════════════════════════════════════════════════
// 최종 리포트 생성
// ══════════════════════════════════════════════════════════
test.afterAll(async () => {
  const fs = await import('fs');
  const lines: string[] = [
    '# Visual Full Check Report',
    '',
    `검사 시간: ${new Date().toISOString()}`,
    `총 검사: ${allResults.length}건`,
    '',
    '## 이슈 요약',
    '',
  ];

  const withIssues = allResults.filter(r => r.issues.length > 0);
  const noIssues = allResults.filter(r => r.issues.length === 0);

  lines.push(`- 통과: ${noIssues.length}건`);
  lines.push(`- 이슈: ${withIssues.length}건`);
  lines.push('');

  if (withIssues.length > 0) {
    lines.push('## 이슈 상세');
    lines.push('');
    lines.push('| 페이지 | 뷰포트 | 이슈 |');
    lines.push('|--------|--------|------|');
    for (const r of withIssues) {
      lines.push(`| ${r.page} | ${r.viewport} | ${r.issues.join(' / ')} |`);
    }
    lines.push('');
  }

  lines.push('## 전체 결과');
  lines.push('');
  lines.push('| 페이지 | 뷰포트 | 결과 |');
  lines.push('|--------|--------|------|');
  for (const r of allResults) {
    const status = r.issues.length === 0 ? '✅ PASS' : `⚠️ ${r.issues.length}건`;
    lines.push(`| ${r.page} | ${r.viewport} | ${status} |`);
  }

  fs.writeFileSync('visual-full-check-report.md', lines.join('\n'));
  console.log(`\n📋 Report written: visual-full-check-report.md (${allResults.length} checks, ${withIssues.length} with issues)\n`);
});
