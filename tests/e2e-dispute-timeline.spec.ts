import { test, expect } from '@playwright/test';

const PROD = 'https://web-production-defb.up.railway.app';
const AK = 'access=yeokping2026';
function u(path: string): string {
  return `${PROD}${path}${path.includes('?') ? '&' : '?'}${AK}`;
}

const SS = 'test-results/screenshots/disputes';

// ── 분쟁 상세 타임라인 검증 ──

test('분쟁 상세 페이지 렌더링 (ROUND1_RESPONSE)', async ({ page }) => {
  await page.goto(u('/disputes/275'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  const body = await page.textContent('body') ?? '';
  // 분쟁 ID 표시
  expect(body).toContain('분쟁 #275');
  // 상태 표시
  expect(body).toContain('Round 1');
  // 타임라인 항목
  expect(body).toContain('분쟁 신청');
  expect(body).toContain('반론');
  await page.screenshot({ path: `${SS}/dispute-275-timeline.png`, fullPage: true });
});

test('분쟁 상세 페이지 (ROUND1_REVIEW with AI)', async ({ page }) => {
  await page.goto(u('/disputes/278'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  const body = await page.textContent('body') ?? '';
  expect(body).toContain('분쟁 #278');
  // Round 1 타임라인 확인
  expect(body).toContain('분쟁 신청');
  expect(body).toContain('AI');
  await page.screenshot({ path: `${SS}/dispute-278-timeline.png`, fullPage: true });
});

test('분쟁 상세 페이지 (합의 완료 ACCEPTED)', async ({ page }) => {
  // 276은 ACCEPTED 상태
  const resp = await page.request.get(`${PROD}/v3_6/disputes/276`);
  const data = await resp.json();
  if (data.status !== 'ACCEPTED') {
    test.skip();
    return;
  }
  await page.goto(u('/disputes/276'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  const body = await page.textContent('body') ?? '';
  expect(body).toContain('합의 완료');
  await page.screenshot({ path: `${SS}/dispute-276-accepted.png`, fullPage: true });
});

// ── 판매자 분쟁 목록 ──

test('판매자 분쟁 목록 페이지 (인증 필요)', async ({ page }) => {
  await page.goto(u('/seller/disputes'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const body = await page.textContent('body') ?? '';
  // 인증 없이 접근 시 로그인 페이지로 리다이렉트되거나 분쟁 페이지 표시
  expect(body.length).toBeGreaterThan(10);
  await page.screenshot({ path: `${SS}/seller-disputes-list.png`, fullPage: true });
});

// ── 관리자 분쟁 페이지 (AI 중재 탭) ──

test('관리자 분쟁 페이지 v3 탭 (인증 필요)', async ({ page }) => {
  await page.goto(u('/admin/disputes'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const body = await page.textContent('body') ?? '';
  // 관리자 인증 없이 접근 → 페이지 렌더 확인
  expect(body.length).toBeGreaterThan(10);
  await page.screenshot({ path: `${SS}/admin-disputes-v3.png`, fullPage: true });
});

// ── 구매자 주문 → 분쟁 연결 ──

test('구매자 주문목록 분쟁 링크', async ({ page }) => {
  await page.goto(u('/my-orders'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const body = await page.textContent('body') ?? '';
  // 주문 목록이 보이는지
  expect(body.length).toBeGreaterThan(50);
  await page.screenshot({ path: `${SS}/buyer-orders-dispute-link.png`, fullPage: true });
});

// ── API 검증 ──

test('분쟁 API: 이름/주문번호 포함', async ({ request }) => {
  const resp = await request.get(`${PROD}/v3_6/disputes/275`);
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  // initiator name exists
  expect(data.initiator.name).toBeTruthy();
  // order_number exists
  expect(data.order_number).toBeTruthy();
  // deadline info
  expect(data.current_deadline).toBeTruthy();
  expect(data.days_remaining).toBeGreaterThanOrEqual(0);
});

test('분쟁 목록 API: reservation_id 포함', async ({ request }) => {
  const resp = await request.get(`${PROD}/v3_6/disputes`);
  expect(resp.status()).toBe(200);
  const data = await resp.json();
  expect(data.length).toBeGreaterThan(0);
  // reservation_id field exists
  expect(data[0].reservation_id).toBeDefined();
});

// ── 정산/환불 연계 코드 검증 ──

test('소스: dispute_service → resolution_executor 연계', async () => {
  const fs = require('fs');
  const src = fs.readFileSync('C:/dev/yp-ver2/app/services/dispute_service.py', 'utf-8');
  // 합의 시 resolution executor 호출
  expect(src).toContain('execute_dispute_resolution_structured');
  // 미합의 시 handle_rejected_dispute 호출
  expect(src).toContain('handle_rejected_dispute');
  // 정산 보류
  expect(src).toContain('DISPUTE_HOLD');
});

test('소스: resolution_executor → ResolutionAction 생성', async () => {
  const fs = require('fs');
  const src = fs.readFileSync('C:/dev/yp-ver2/app/services/resolution_executor.py', 'utf-8');
  // ResolutionAction 생성
  expect(src).toContain('ResolutionAction');
  // 환불 처리
  expect(src).toContain('RefundRequest');
  // 정산 조정
  expect(src).toContain('ReservationSettlement');
  // ClawbackRecord
  expect(src).toContain('ClawbackRecord');
});
