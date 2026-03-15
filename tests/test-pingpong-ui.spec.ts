import { test, expect } from '@playwright/test';

const PROD = 'https://web-production-defb.up.railway.app';
const AK = 'access=yeokping2026';

test('핑퐁이 UI 테스트', async ({ page }) => {
  const consoleLogs: string[] = [];
  page.on('console', msg => consoleLogs.push(`[${msg.type()}] ${msg.text()}`));

  const networkErrors: string[] = [];
  page.on('requestfailed', req => networkErrors.push(`FAIL: ${req.url()} ${req.failure()?.errorText}`));

  await page.goto(`${PROD}/?${AK}`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  // 핑퐁이 플로팅 버튼 찾기
  const floatBtn = page.locator('button[aria-label="핑퐁이에게 질문하기"]');
  const exists = await floatBtn.count();
  console.log('Float button exists:', exists);

  if (exists === 0) {
    const buttons = await page.locator('button').allTextContents();
    console.log('All buttons:', buttons.slice(0, 20));
    await page.screenshot({ path: 'test-results/pingpong-no-button.png', fullPage: true });
    throw new Error('핑퐁이 플로팅 버튼이 없습니다');
  }

  await floatBtn.click();
  await page.waitForTimeout(500);

  const chatPanel = page.locator('text=핑퐁이');
  await expect(chatPanel.first()).toBeVisible({ timeout: 3000 });

  const input = page.locator('input[placeholder="질문 입력..."]');
  await input.fill('환불 정책 알려줘');
  await page.keyboard.press('Enter');

  // 응답 대기
  await page.waitForTimeout(12000);

  await page.screenshot({ path: 'test-results/pingpong-response.png', fullPage: true });

  const chatText = await page.locator('.chat-scroll').textContent() ?? '';
  console.log('Chat content length:', chatText.length);
  console.log('Chat content (first 300):', chatText.slice(0, 300));

  const errors = consoleLogs.filter(l => l.includes('error') || l.includes('Error') || l.includes('FAIL'));
  if (errors.length) console.log('Console errors:', errors);
  if (networkErrors.length) console.log('Network errors:', networkErrors);

  expect(chatText).not.toContain('쉬고 있어요');
  expect(chatText.length).toBeGreaterThan(50);
});
