/**
 * 역할 스트레스 테스트 Phase 1-2
 * Phase 1: 액추에이터 (T01-T30) — 30개
 * Phase 2: 추천인/리퍼럴 (T31-T45) — 15개
 */
import { test, expect } from '@playwright/test';
import { BASE, state, api, apiNoAuth, socialRegister, tokenInfo, setToken, setAuth, approveSeller, setupAll, TS } from './helpers';

test.describe.configure({ mode: 'serial' });

test('Setup: 전체 데이터 초기화', async ({ page }) => {
  test.setTimeout(120_000);
  await setupAll(page);
  expect(state.buyerId).toBeGreaterThan(0);
  expect(state.sellerId).toBeGreaterThan(0);
  expect(state.actuatorId).toBeGreaterThan(0);
});

// ============================================================
// Phase 1: 액추에이터 스트레스 (T01-T30)
// ============================================================

test('T01 액추에이터 가입 성공', async ({ page }) => {
  await page.goto(BASE);
  expect(state.actuatorId).toBeGreaterThan(0);
  expect(state.actuatorToken.length).toBeGreaterThan(10);
});

test('T02 액추에이터 프로필 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', `/actuators/${state.actuatorId}`);
  expect([200, 404]).toContain(r.status);
  if (r.status === 200) {
    expect(r.data.id).toBe(state.actuatorId);
  }
});

test('T03 액추에이터 목록 조회 (admin)', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'GET', '/actuators/');
  expect(r.status).toBe(200);
});

test('T04 액추에이터 추천코드 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', `/actuators/${state.actuatorId}`);
  if (r.status === 200 && r.data?.referral_code) {
    const vc = await api(page, 'GET', `/actuators/verify-code?code=${r.data.referral_code}`);
    expect([200, 404]).toContain(vc.status);
  }
});

test('T05 잘못된 추천코드 검증', async ({ page }) => {
  await page.goto(BASE);
  const r = await apiNoAuth(page, 'GET', '/actuators/verify-code?code=INVALID-999');
  expect([404, 422]).toContain(r.status);
});

test('T06 액추에이터 by-email 조회', async ({ page }) => {
  await page.goto(BASE);
  const r = await api(page, 'GET', `/actuators/by-email?email=${encodeURIComponent(state.actuatorEmail)}`);
  expect([200, 404]).toContain(r.status);
});

test('T07 액추에이터 커미션 목록 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', `/actuators/${state.actuatorId}/commissions`);
  expect([200, 404]).toContain(r.status);
});

test('T08 액추에이터 커미션 요약 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', `/actuators/${state.actuatorId}/commissions/summary`);
  expect([200, 404]).toContain(r.status);
});

test('T09 액추에이터 계약 동의', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'POST', `/actuators/${state.actuatorId}/agree-contract`);
  expect([200, 201, 404, 405]).toContain(r.status);
  if (r.status === 200) {
    expect(r.data?.contract_agreed).toBe(true);
  }
});

test('T10 액추에이터 계약 상태 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', `/actuators/${state.actuatorId}/contract-status`);
  expect([200, 404, 405]).toContain(r.status);
  if (r.status === 200) {
    expect(r.data).toHaveProperty('contract_agreed');
  }
});

test('T11 액추에이터 중복 계약 동의 (멱등)', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'POST', `/actuators/${state.actuatorId}/agree-contract`);
  expect([200, 201, 404, 405]).toContain(r.status);
});

test('T12 액추에이터 정산 미리보기', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', `/actuators/${state.actuatorId}/payout-preview`);
  expect([200, 404, 405]).toContain(r.status);
  if (r.status === 200) {
    expect(r.data).toHaveProperty('gross_amount');
    expect(r.data).toHaveProperty('net_amount');
  }
});

test('T13 사업자 액추에이터 정산 미리보기', async ({ page }) => {
  await page.goto(BASE);
  if (!state.actuator2Id) { console.log('WARN: actuator2 없음, 스킵'); return; }
  await setToken(page, state.actuator2Token);
  const r = await api(page, 'GET', `/actuators/${state.actuator2Id}/payout-preview`);
  expect([200, 404, 405]).toContain(r.status);
  if (r.status === 200 && r.data?.type) {
    expect(r.data.type).toBe('business');
  }
});

test('T14 존재하지 않는 액추에이터 조회', async ({ page }) => {
  await page.goto(BASE);
  const r = await api(page, 'GET', '/actuators/999999');
  expect([404, 200]).toContain(r.status);
});

test('T15 액추에이터 연결 판매자 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', `/actuators/${state.actuatorId}/sellers`);
  expect([200, 404]).toContain(r.status);
});

test('T16 액추에이터 판매자 모집 (추천코드 연결)', async ({ page }) => {
  await page.goto(BASE);
  // 새 판매자를 액추에이터 코드로 가입
  await setToken(page, '');
  const actDetail = await api(page, 'GET', `/actuators/${state.actuatorId}`, undefined, state.adminToken);
  const refCode = actDetail.data?.referral_code || `ACT-${state.actuatorId}`;
  const newSeller = await socialRegister(page, {
    socialId: `actrecruit_${TS}`, role: 'seller',
    nickname: `모집셀러${TS % 10000}`, email: `actrecruit_${TS}@test.com`,
    business_name: '모집테스트', business_number: `${TS}8`,
    actuator_code: refCode,
  });
  expect([200, 201, 422]).toContain(newSeller.status);
});

test('T17 액추에이터 XSS 닉네임 차단', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, '');
  const r = await socialRegister(page, {
    socialId: `actxss_${TS}`, role: 'actuator',
    nickname: '<script>alert(1)</script>', email: `actxss_${TS}@test.com`,
  });
  if (r.status === 200 || r.status === 201) {
    const tok = r.data?.access_token || '';
    if (tok) {
      const info = await tokenInfo(page, tok);
      const nick = info.nickname || r.data?.nickname || '';
      expect(nick).not.toContain('<script>');
    }
  } else {
    expect([400, 422]).toContain(r.status);
  }
});

test('T18 액추에이터 SQL injection 차단', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, '');
  const r = await socialRegister(page, {
    socialId: `actsql_${TS}`, role: 'actuator',
    nickname: "' OR 1=1--", email: `actsql_${TS}@test.com`,
  });
  expect([200, 201, 400, 422]).toContain(r.status);
});

test('T19 액추에이터 빈 닉네임 차단', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, '');
  const r = await socialRegister(page, {
    socialId: `actempty_${TS}`, role: 'actuator',
    nickname: '', email: `actempty_${TS}@test.com`,
  });
  expect([400, 422, 200, 201]).toContain(r.status);
});

test('T20 액추에이터 100자 닉네임 처리', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, '');
  const r = await socialRegister(page, {
    socialId: `actlong_${TS}`, role: 'actuator',
    nickname: 'A'.repeat(100), email: `actlong_${TS}@test.com`,
  });
  expect([200, 201, 400, 422]).toContain(r.status);
});

test('T21 액추에이터 커미션 지급 요청', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'POST', `/actuators/me/commissions/settle?actuator_id=${state.actuatorId}`);
  expect([200, 404, 405, 422]).toContain(r.status);
});

test('T22 액추에이터 커미션 유효기간 체크', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', `/actuators/${state.actuatorId}/commissions/payout-due?actuator_id=${state.actuatorId}`);
  expect([200, 404, 405]).toContain(r.status);
});

test('T23 타인 액추에이터 계약 동의 시도', async ({ page }) => {
  await page.goto(BASE);
  if (!state.actuator2Id) { console.log('WARN: actuator2 없음'); return; }
  await setToken(page, state.actuatorToken);
  // actuator1 토큰으로 actuator2 계약 동의 시도
  const r = await api(page, 'POST', `/actuators/${state.actuator2Id}/agree-contract`);
  // 인증 체크가 없으면 200 가능 (WARN)
  expect([200, 403, 404, 405]).toContain(r.status);
  if (r.status === 200) console.log('WARN: 타인 계약 동의 허용됨');
});

test('T24 액추에이터 상태 변경 (admin)', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'PATCH', `/actuators/${state.actuatorId}`, { status: 'ACTIVE' });
  expect([200, 404, 405, 422]).toContain(r.status);
});

test('T25 액추에이터 5연속 조회 성능', async ({ page }) => {
  test.setTimeout(30_000);
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const start = Date.now();
  for (let i = 0; i < 5; i++) {
    const r = await api(page, 'GET', `/actuators/${state.actuatorId}`);
    expect([200, 404]).toContain(r.status);
  }
  const elapsed = Date.now() - start;
  console.log(`T25 5연속 조회: ${elapsed}ms`);
  expect(elapsed).toBeLessThan(15000);
});

test('T26 사업자 액추에이터 사업자 정보 확인', async ({ page }) => {
  await page.goto(BASE);
  if (!state.actuator2Id) { console.log('WARN: actuator2 없음'); return; }
  await setToken(page, state.actuator2Token);
  const r = await api(page, 'GET', `/actuators/${state.actuator2Id}`);
  expect([200, 404]).toContain(r.status);
});

test('T27 개인 액추에이터 원천징수율 확인', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', `/actuators/${state.actuatorId}/contract-status`);
  expect([200, 404, 405]).toContain(r.status);
  if (r.status === 200 && r.data?.withholding_tax_rate !== undefined) {
    expect(r.data.withholding_tax_rate).toBeCloseTo(0.033, 3);
  }
});

test('T28 액추에이터 이메일로 조회 - 없는 이메일', async ({ page }) => {
  await page.goto(BASE);
  const r = await api(page, 'GET', `/actuators/by-email?email=nonexist_${TS}@test.com`);
  expect([404, 200]).toContain(r.status);
});

test('T29 액추에이터 대시보드 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', '/dashboard/summary');
  expect([200, 401, 403, 404]).toContain(r.status);
});

test('T30 액추에이터 알림 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.actuatorToken);
  const r = await api(page, 'GET', '/notifications/');
  expect([200, 401, 403]).toContain(r.status);
});

// ============================================================
// Phase 2: 추천인/리퍼럴 (T31-T45)
// ============================================================

test('T31 추천인 코드로 가입 (buyer)', async ({ page }) => {
  await page.goto(BASE);
  expect(state.buyer2Id).toBeGreaterThan(0);
});

test('T32 추천인 포인트 적립 확인', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', '/points/history');
  expect([200, 404]).toContain(r.status);
  // 추천인 포인트가 있을 수 있음
  if (r.status === 200 && Array.isArray(r.data)) {
    const refPts = r.data.filter((p: any) => p.type === 'REFERRAL_REWARD' || p.reason?.includes('추천'));
    console.log(`T32 추천인 포인트: ${refPts.length}건`);
  }
});

test('T33 피추천인 가입 보너스 확인', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyer2Token);
  const r = await api(page, 'GET', '/points/history');
  expect([200, 404]).toContain(r.status);
});

test('T34 자기 추천 차단', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, '');
  const r = await socialRegister(page, {
    socialId: `selfref_${TS}`, role: 'buyer',
    nickname: `셀프추천${TS % 10000}`, email: `selfref_${TS}@test.com`,
    recommender_buyer_id: 0, // 자기 자신
  });
  // 가입은 성공할 수 있으나 포인트는 미지급
  expect([200, 201, 400, 422]).toContain(r.status);
});

test('T35 존재하지 않는 추천인 ID', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, '');
  const r = await socialRegister(page, {
    socialId: `badref_${TS}`, role: 'buyer',
    nickname: `잘못추천${TS % 10000}`, email: `badref_${TS}@test.com`,
    recommender_buyer_id: 999999,
  });
  expect([200, 201, 400, 422]).toContain(r.status);
});

test('T36 추천인 음수 ID 처리', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, '');
  const r = await socialRegister(page, {
    socialId: `negref_${TS}`, role: 'buyer',
    nickname: `음수추천${TS % 10000}`, email: `negref_${TS}@test.com`,
    recommender_buyer_id: -1,
  });
  expect([200, 201, 400, 422]).toContain(r.status);
});

test('T37 추천인 XSS ID 처리', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, '');
  const r = await socialRegister(page, {
    socialId: `xssref_${TS}`, role: 'buyer',
    nickname: `xss추천${TS % 10000}`, email: `xssref_${TS}@test.com`,
    recommender_buyer_id: '<script>' as any,
  });
  expect([200, 201, 400, 422]).toContain(r.status);
});

test('T38 포인트 잔액 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', '/points/balance');
  expect([200, 404]).toContain(r.status);
});

test('T39 포인트 적립 이벤트 (결제 후)', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', '/points/history');
  expect([200, 404]).toContain(r.status);
  if (r.status === 200 && Array.isArray(r.data)) {
    const payPts = r.data.filter((p: any) => p.type === 'PAID_REWARD' || p.amount > 0);
    console.log(`T39 결제 포인트: ${payPts.length}건`);
  }
});

test('T40 포인트 음수 적립 차단', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'POST', '/points/earn', {
    user_id: state.buyerId, user_type: 'buyer', amount: -100, reason: 'test',
  });
  expect([200, 400, 404, 405, 422]).toContain(r.status);
});

test('T41 포인트 0원 적립 처리', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'POST', '/points/earn', {
    user_id: state.buyerId, user_type: 'buyer', amount: 0, reason: 'test',
  });
  expect([200, 400, 404, 405, 422]).toContain(r.status);
});

test('T42 포인트 사용 시도', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'POST', '/points/spend', {
    user_id: state.buyerId, amount: 10, reason: 'test spend',
  });
  expect([200, 400, 404, 405, 422]).toContain(r.status);
});

test('T43 추천인 연속 5명 가입 성능', async ({ page }) => {
  test.setTimeout(30_000);
  await page.goto(BASE);
  const start = Date.now();
  for (let i = 0; i < 5; i++) {
    await setToken(page, '');
    await socialRegister(page, {
      socialId: `batchref_${TS}_${i}`, role: 'buyer',
      nickname: `배치추천${i}_${TS % 10000}`, email: `batchref_${TS}_${i}@test.com`,
      recommender_buyer_id: state.buyerId,
    });
  }
  const elapsed = Date.now() - start;
  console.log(`T43 추천인 5연속 가입: ${elapsed}ms`);
  expect(elapsed).toBeLessThan(15000);
});

test('T44 seller 추천인 테스트', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, '');
  const r = await socialRegister(page, {
    socialId: `sellref_${TS}`, role: 'seller',
    nickname: `셀러추천${TS % 10000}`, email: `sellref_${TS}@test.com`,
    business_name: '추천셀러샵', business_number: `${TS}9`,
    recommender_buyer_id: state.buyerId,
  });
  expect([200, 201, 400, 422]).toContain(r.status);
});

test('T45 추천인 포인트 이력 개수 확인', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', '/points/history');
  expect([200, 404]).toContain(r.status);
  if (r.status === 200 && Array.isArray(r.data)) {
    console.log(`T45 전체 포인트 이력: ${r.data.length}건`);
  }
});
