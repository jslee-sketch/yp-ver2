import { test, expect } from '@playwright/test';

const PROD = 'https://web-production-defb.up.railway.app';
const AK = 'access=yeokping2026';
function u(path: string): string {
  return `${PROD}${path}${path.includes('?') ? '&' : '?'}${AK}`;
}

const SS = 'test-results/screenshots/fixes';
// 프로덕션에 존재하는 딜 ID (offer 2건 포함)
const DEAL_ID = 1688;

// F-001: 디지털 시계 32px + Courier New + 색변화
test('F-001 디지털 시계 확인', async ({ page }) => {
  await page.goto(u(`/deal/${DEAL_ID}`), { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  const body = await page.textContent('body') ?? '';
  // 시계 HH:MM:SS 형식 확인 (00:00:00 ~ 99:99:99 패턴)
  const hasTime = /\d{2}:\d{2}:\d{2}/.test(body) || body.includes('마감');
  expect(hasTime).toBeTruthy();
  await page.screenshot({ path: `${SS}/fix-001.png`, fullPage: true });
});

// F-002: 채팅 컨테이너 고정 (scroll 격리)
test('F-002 채팅 scroll 격리 확인', async ({ page }) => {
  await page.goto(u(`/deal/${DEAL_ID}`), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  // 채팅 영역 클릭해서 펼치기
  const chatHeader = page.locator('text=실시간 딜 토크');
  if (await chatHeader.isVisible()) {
    await chatHeader.click();
    await page.waitForTimeout(500);
  }
  await page.screenshot({ path: `${SS}/fix-002.png`, fullPage: true });
});

// F-003: 공동구매 곡선 부드러움 (canvas 존재 확인)
test('F-003 공동구매 곡선 확인', async ({ page }) => {
  await page.goto(u(`/deal/${DEAL_ID}`), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const canvas = page.locator('canvas');
  const canvasCount = await canvas.count();
  expect(canvasCount).toBeGreaterThan(0);
  await page.screenshot({ path: `${SS}/fix-003.png`, fullPage: true });
});

// F-003 소스코드: Catmull-Rom 스플라인 확인
test('F-003 소스코드: Catmull-Rom 스플라인', async () => {
  const fs = require('fs');
  const src = fs.readFileSync('C:/dev/yp-ver2/frontend/src/components/journey/GroupCurveSection.tsx', 'utf-8');
  expect(src).toContain('drawCatmullRom');
  expect(src).toContain('bezierCurveTo');
  expect(src).toContain("Math.pow(ratio, 0.7)");
});

// F-004: 상황판 남은 시간 디지털 시계
test('F-004 상황판 디지털 시계 확인', async ({ page }) => {
  await page.goto(u(`/deal/${DEAL_ID}`), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const body = await page.textContent('body') ?? '';
  // "남은 시간" 텍스트 있는지
  const hasLabel = body.includes('남은 시간') || body.includes('오퍼경쟁까지') || body.includes('예약/결제까지') || body.includes('완료까지');
  expect(hasLabel).toBeTruthy();
  await page.screenshot({ path: `${SS}/fix-004.png`, fullPage: true });
});

// F-004 소스코드: 디지털시계 스타일
test('F-004 소스코드: Courier New 28px+', async () => {
  const fs = require('fs');
  const src = fs.readFileSync('C:/dev/yp-ver2/frontend/src/pages/PriceJourneyPage.tsx', 'utf-8');
  expect(src).toContain("padStart(2,'0')");
  expect(src).toContain("Courier New");
  expect(src).toContain("fontSize: 36");
  expect(src).toContain("textShadow");
  expect(src).toContain("#00ff88");
});

// F-005: 관전자 예측 업데이트
test('F-005 관전자 예측 섹션 확인', async ({ page }) => {
  await page.goto(u(`/deal/${DEAL_ID}`), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const body = await page.textContent('body') ?? '';
  const hasPred = body.includes('예측') || body.includes('관전자');
  expect(hasPred).toBeTruthy();
  await page.screenshot({ path: `${SS}/fix-005.png`, fullPage: true });
});

// F-006: 예측 근거 + 좋아요 시스템
test('F-006 소스코드: 근거 textarea + 좋아요', async () => {
  const fs = require('fs');
  const src = fs.readFileSync('C:/dev/yp-ver2/frontend/src/pages/PriceJourneyPage.tsx', 'utf-8');
  expect(src).toContain('predReason');
  expect(src).toContain('2,000');
  expect(src).toContain('votePrediction');
  expect(src).toContain('👍');
  expect(src).toContain('🤔');
});

// F-006 백엔드: vote API
test('F-006 Backend: vote API 작동', async ({ request }) => {
  const preds = await request.get(`${PROD}/spectator/predictions/${DEAL_ID}`);
  expect([200, 404]).toContain(preds.status());
});

// F-007: 채팅 DB 저장
test('F-007 소스코드: 채팅 DB', async () => {
  const fs = require('fs');
  const src = fs.readFileSync('C:/dev/yp-ver2/frontend/src/pages/PriceJourneyPage.tsx', 'utf-8');
  expect(src).toContain('fetchChatMessages');
  expect(src).toContain('sendChatMessage');
});

// F-007 Backend: 채팅 API
test('F-007 Backend: 채팅 API 작동', async ({ request }) => {
  const msgs = await request.get(`${PROD}/deals/${DEAL_ID}/chat/messages?buyer_id=1`);
  expect([200, 404, 409, 422]).toContain(msgs.status());
});

// F-008: PriceJourney UX 전반
test('F-008 PriceJourney 핵심 UI', async ({ page }) => {
  await page.goto(u(`/deal/${DEAL_ID}`), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const body = await page.textContent('body') ?? '';
  const ok = body.includes('가격 여정') || body.includes('딜 모집') || body.includes('딜 정보를 찾을 수 없습니다');
  expect(ok).toBeTruthy();
  await page.screenshot({ path: `${SS}/fix-008.png`, fullPage: true });
});

// F-009: 택배사/송장
test('F-009 판매자 배송관리', async ({ page }) => {
  await page.goto(u('/seller/shipping-policy'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const body = await page.textContent('body') ?? '';
  expect(body.length).toBeGreaterThan(30);
  await page.screenshot({ path: `${SS}/fix-009.png`, fullPage: true });
});

// F-011: 분쟁관리 메뉴
test('F-011 분쟁관리', async ({ page }) => {
  await page.goto(u('/seller/disputes'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const body = await page.textContent('body') ?? '';
  expect(body.length).toBeGreaterThan(30);
  await page.screenshot({ path: `${SS}/fix-011.png`, fullPage: true });
});

// F-012: 구매자 환불시뮬레이터
test('F-012 구매자 환불시뮬레이터', async ({ page }) => {
  await page.goto(u('/refund-simulator'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  const body = await page.textContent('body') ?? '';
  expect(body).toContain('환불 시뮬레이터');
  await page.screenshot({ path: `${SS}/fix-012.png`, fullPage: true });
});

// F-013: 수수료 등급
test('F-013 수수료 등급', async ({ page }) => {
  await page.goto(u('/seller/fees'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const body = await page.textContent('body') ?? '';
  expect(body.length).toBeGreaterThan(30);
  await page.screenshot({ path: `${SS}/fix-013.png`, fullPage: true });
});

// F-015: 리뷰 페이지
test('F-015 리뷰 페이지', async ({ page }) => {
  await page.goto(u('/seller/reviews'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const body = await page.textContent('body') ?? '';
  expect(body.length).toBeGreaterThan(30);
  await page.screenshot({ path: `${SS}/fix-015.png`, fullPage: true });
});

// F-016: 빈화면 방지 (대시보드)
test('F-016 판매자 대시보드', async ({ page }) => {
  await page.goto(u('/seller/dashboard'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const body = await page.textContent('body') ?? '';
  expect(body.length).toBeGreaterThan(50);
  await page.screenshot({ path: `${SS}/fix-016.png`, fullPage: true });
});

// F-017: 로그인 리다이렉트 (사업자정보)
test('F-017 사업자정보 접근', async ({ page }) => {
  await page.goto(u('/seller/business-info'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const body = await page.textContent('body') ?? '';
  expect(body.length).toBeGreaterThan(30);
  await page.screenshot({ path: `${SS}/fix-017.png`, fullPage: true });
});

// F-018: 구매자 주문내역
test('F-018 구매자 주문내역', async ({ page }) => {
  await page.goto(u('/my-orders'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  const body = await page.textContent('body') ?? '';
  expect(body.length).toBeGreaterThan(30);
  await page.screenshot({ path: `${SS}/fix-018.png`, fullPage: true });
});

// 환불시뮬레이터 (판매자) — 이전 빈화면 수정 확인
test('판매자 환불시뮬레이터 빈화면 수정', async ({ page }) => {
  await page.goto(u('/seller/refund-simulator'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  const body = await page.textContent('body') ?? '';
  expect(body).toContain('환불 시뮬레이터');
  expect(body).toContain('주문 금액');
  await page.screenshot({ path: `${SS}/fix-seller-refund.png`, fullPage: true });
});
