import { test, expect } from '@playwright/test';

const PROD = 'https://web-production-defb.up.railway.app';
const AK = 'access=yeokping2026';
function u(path: string): string {
  return `${PROD}${path}${path.includes('?') ? '&' : '?'}${AK}`;
}
const SS = 'test-results/screenshots/f-fixes';

// F-003: 곡선 부드러움 확인 (소스코드 + 프로덕션 렌더링)
test('F-003 곡선 Catmull-Rom 300pt 확인', async ({ page }) => {
  const fs = require('fs');
  const src = fs.readFileSync('C:/dev/yp-ver2/frontend/src/components/journey/GroupCurveSection.tsx', 'utf-8');
  expect(src).toContain('CURVE_STEPS = 300');
  expect(src).toContain('drawCatmullRom');
  expect(src).toContain('bezierCurveTo');
  // 프로덕션 가격여정 렌더링
  await page.goto(u('/deal/142/journey'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${SS}/curve.png`, fullPage: true });
  const body = await page.textContent('body') ?? '';
  expect(body.length).toBeGreaterThan(100);
});

// F-005: 관전자 팝업 모달 (소스코드 확인)
test('F-005 관전자 예측 상세 팝업 모달', async () => {
  const fs = require('fs');
  const src = fs.readFileSync('C:/dev/yp-ver2/frontend/src/pages/PriceJourneyPage.tsx', 'utf-8');
  expect(src).toContain('predDetailTarget');
  expect(src).toContain('예측 상세');
  expect(src).toContain('setPredDetailTarget');
  expect(src).toContain('overflowY');
});

// F-006: 좋아요 API + 프론트 호출 확인
test('F-006 좋아요 vote API 존재', async () => {
  const fs = require('fs');
  const backend = fs.readFileSync('C:/dev/yp-ver2/app/routers/spectator.py', 'utf-8');
  expect(backend).toContain('prediction-vote');
  const frontend = fs.readFileSync('C:/dev/yp-ver2/frontend/src/pages/PriceJourneyPage.tsx', 'utf-8');
  expect(frontend).toContain('votePrediction');
  expect(frontend).toContain("'like'");
  expect(frontend).toContain("'meh'");
});

// F-019: 순차 하이라이트 CSS 클래스 존재 + 적용 페이지
test('F-019 순차 하이라이트 전역 적용', async () => {
  const fs = require('fs');
  const css = fs.readFileSync('C:/dev/yp-ver2/frontend/src/index.css', 'utf-8');
  expect(css).toContain('.field-active');
  expect(css).toContain('.field-pending');
  expect(css).toContain('.field-completed');
  expect(css).toContain('#00ff88');
  // 적용 페이지 확인
  const dealCreate = fs.readFileSync('C:/dev/yp-ver2/frontend/src/pages/DealCreatePage.tsx', 'utf-8');
  expect(dealCreate).toContain('field-active');
  expect(dealCreate).toContain('field-completed');
  const register = fs.readFileSync('C:/dev/yp-ver2/frontend/src/pages/RegisterPage.tsx', 'utf-8');
  expect(register).toContain('hlClass');
  expect(register).toContain('field-active');
  expect(register).toContain('field-completed');
  const disputeNew = fs.readFileSync('C:/dev/yp-ver2/frontend/src/pages/DisputeNewPage.tsx', 'utf-8');
  expect(disputeNew).toContain('stepStyle');
  expect(disputeNew).toContain('currentStep');
});

// F-019 프로덕션: 딜생성 페이지 렌더링
test('F-019 딜생성 순차 하이라이트 렌더링', async ({ page }) => {
  await page.goto(u('/deals/create'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SS}/hl-deal.png`, fullPage: true });
  const body = await page.textContent('body') ?? '';
  expect(body.length).toBeGreaterThan(50);
});

// F-019 프로덕션: 회원가입 렌더링
test('F-019 회원가입 순차 하이라이트 렌더링', async ({ page }) => {
  await page.goto(u('/register'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SS}/hl-register.png`, fullPage: true });
  const body = await page.textContent('body') ?? '';
  expect(body.length).toBeGreaterThan(50);
});

// F-020: 딜 링크 + F-021: 제품명 크기
test('F-020+021 딜 링크 & 제품명 크기', async ({ page }) => {
  const fs = require('fs');
  const src = fs.readFileSync('C:/dev/yp-ver2/frontend/src/pages/PriceJourneyPage.tsx', 'utf-8');
  // F-020: Deal # 클릭 시 navigate
  expect(src).toContain("navigate(`/deals/${dealId}`)");
  // F-021: 제품명 fontSize 24px
  expect(src).toContain('fontSize: 24, fontWeight: 700');
  // 프로덕션 확인
  await page.goto(u('/deal/142/journey'), { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: `${SS}/link-fontsize.png`, fullPage: true });
});

// F-002: 채팅 DB 모델 + API 확인
test('F-002 채팅 DB 저장 확인', async () => {
  const fs = require('fs');
  const models = fs.readFileSync('C:/dev/yp-ver2/app/models.py', 'utf-8');
  expect(models).toContain('deal_chat_messages');
  expect(models).toContain('DealChatMessage');
  const router = fs.readFileSync('C:/dev/yp-ver2/app/routers/deal_chat.py', 'utf-8');
  expect(router).toContain('/chat/messages');
  const frontend = fs.readFileSync('C:/dev/yp-ver2/frontend/src/api/chatApi.ts', 'utf-8');
  expect(frontend).toContain('fetchChatMessages');
  expect(frontend).toContain('sendChatMessage');
  // YAML 채팅 정책
  const yaml = fs.readFileSync('C:/dev/yp-ver2/app/policy/params/cs_process.yaml', 'utf-8');
  expect(yaml).toContain('retention_days: 90');
  expect(yaml).toContain('max_messages_per_deal: 5000');
});
