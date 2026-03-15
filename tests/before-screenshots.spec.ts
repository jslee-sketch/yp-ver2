import { test } from '@playwright/test';
const PROD = 'https://web-production-defb.up.railway.app';
const AK = 'access=yeokping2026';
function u(p: string) { return `${PROD}${p}${p.includes('?') ? '&' : '?'}${AK}`; }
const SS = 'test-results/screenshots/f-fixes-6th';

test('before-curve', async ({ page }) => {
  await page.goto(u('/deal/1689'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(4000);
  await page.screenshot({ path: `${SS}/curve-before.png`, fullPage: true });
});

test('before-register', async ({ page }) => {
  await page.goto(u('/register'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SS}/hl-register-before.png`, fullPage: true });
});
