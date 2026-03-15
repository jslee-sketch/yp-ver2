import { test, expect } from '@playwright/test';
const PROD = 'https://web-production-defb.up.railway.app';
const AK = 'access=yeokping2026';
function u(p: string) { return `${PROD}${p}${p.includes('?') ? '&' : '?'}${AK}`; }
const SS = 'test-results/screenshots/f-fixes-6th';

test('F-003 curve-after', async ({ page }) => {
  await page.goto(u('/deal/1689'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(4000);
  await page.screenshot({ path: `${SS}/curve-after.png`, fullPage: true });
  // Verify canvas exists
  const canvas = page.locator('canvas');
  await expect(canvas).toBeVisible();
});

test('F-006 vote test', async ({ page }) => {
  // Login first
  const resp = await page.request.post(`${PROD}/auth/login`, {
    form: { username: 'realtest1@e2e.com', password: 'Test1234!' },
  });
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  const token = data.access_token;
  const userId = data.user?.id ?? 11;

  await page.goto(u('/deal/1689'), { waitUntil: 'domcontentloaded' });
  await page.evaluate((d: any) => {
    localStorage.setItem('access_token', d.token);
    localStorage.setItem('user', JSON.stringify(d.user || { id: d.userId, role: 'buyer', nickname: 'test' }));
  }, { token, user: data.user, userId });
  await page.goto(u('/deal/1689'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  // Capture console errors
  const errors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
  });

  await page.screenshot({ path: `${SS}/vote-1-page.png`, fullPage: true });

  // Check if prediction section is visible
  const predSection = await page.textContent('body') ?? '';
  console.log('Page has prediction content:', predSection.includes('예측') || predSection.includes('예언자'));
  console.log('Console errors:', errors.join(' | '));
});

test('F-019 register highlight', async ({ page }) => {
  await page.goto(u('/register'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  // Navigate to step 2 (role selection → click 구매자 → 다음)
  const buyer = page.locator('text=구매자').first();
  if (await buyer.isVisible()) {
    await buyer.click();
    const next = page.locator('text=다음').first();
    if (await next.isVisible()) await next.click();
    await page.waitForTimeout(1000);
  }
  await page.screenshot({ path: `${SS}/hl-register.png`, fullPage: true });
});

test('F-019 deal create highlight', async ({ page }) => {
  // Login first
  const resp = await page.request.post(`${PROD}/auth/login`, {
    form: { username: 'realtest1@e2e.com', password: 'Test1234!' },
  });
  const data = await resp.json();
  await page.goto(u('/'), { waitUntil: 'domcontentloaded' });
  await page.evaluate((d: any) => {
    localStorage.setItem('access_token', d.access_token);
    localStorage.setItem('user', JSON.stringify(d.user || { id: 11, role: 'buyer', nickname: 'test' }));
  }, data);
  await page.goto(u('/deals/create'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${SS}/hl-deal.png`, fullPage: true });
});

test('F-019 dispute highlight', async ({ page }) => {
  // Login first
  const resp = await page.request.post(`${PROD}/auth/login`, {
    form: { username: 'realtest1@e2e.com', password: 'Test1234!' },
  });
  const data = await resp.json();
  await page.goto(u('/'), { waitUntil: 'domcontentloaded' });
  await page.evaluate((d: any) => {
    localStorage.setItem('access_token', d.access_token);
    localStorage.setItem('user', JSON.stringify(d.user || { id: 11, role: 'buyer', nickname: 'test' }));
  }, data);
  await page.goto(u('/my-disputes/new'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SS}/hl-dispute.png`, fullPage: true });
});
