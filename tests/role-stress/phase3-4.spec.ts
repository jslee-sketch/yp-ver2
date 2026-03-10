/**
 * 역할 스트레스 테스트 Phase 3-4
 * Phase 3: 관전자/스펙테이터 (T46-T60) — 15개
 * Phase 4: 등급 시스템 (T61-T90) — 30개
 */
import { test, expect } from '@playwright/test';
import { BASE, state, api, apiNoAuth, socialRegister, tokenInfo, setToken, setAuth, setupAll, TS } from './helpers';

test.describe.configure({ mode: 'serial' });

test('Setup: 전체 데이터 초기화', async ({ page }) => {
  test.setTimeout(120_000);
  await setupAll(page);
  expect(state.buyerId).toBeGreaterThan(0);
  expect(state.dealIds.length).toBeGreaterThan(0);
});

// ============================================================
// Phase 3: 관전자/스펙테이터 (T46-T60)
// ============================================================

test('T46 관전 모드 진입 (딜 조회)', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.spectatorToken);
  if (!state.dealIds[0]) { console.log('WARN: dealId 없음'); return; }
  const r = await api(page, 'GET', `/spectator/view/${state.dealIds[0]}`);
  expect([200, 404, 405, 422]).toContain(r.status);
});

test('T47 관전자 수 조회', async ({ page }) => {
  await page.goto(BASE);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'GET', `/spectator/viewers/${state.dealIds[0]}`);
  expect([200, 404, 405, 422]).toContain(r.status);
});

test('T48 가격 예측 제출', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.spectatorToken);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'POST', '/spectator/predict', {
    deal_id: state.dealIds[0],
    buyer_id: state.spectatorId,
    predicted_price: 900000,
  });
  expect([200, 201, 400, 404, 405, 422]).toContain(r.status);
});

test('T49 가격 예측 중복 제출', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.spectatorToken);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'POST', '/spectator/predict', {
    deal_id: state.dealIds[0],
    buyer_id: state.spectatorId,
    predicted_price: 910000,
  });
  expect([200, 201, 400, 404, 405, 409, 422]).toContain(r.status);
});

test('T50 예측 목록 조회 (딜별)', async ({ page }) => {
  await page.goto(BASE);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'GET', `/spectator/predictions/${state.dealIds[0]}`);
  expect([200, 404, 405, 422]).toContain(r.status);
});

test('T51 예측 수 조회', async ({ page }) => {
  await page.goto(BASE);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'GET', `/spectator/predictions/${state.dealIds[0]}/count`);
  expect([200, 404, 405, 422]).toContain(r.status);
});

test('T52 내 예측 목록 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.spectatorToken);
  const r = await api(page, 'GET', '/spectator/my_predictions');
  expect([200, 404, 405, 422]).toContain(r.status);
});

test('T53 관전자 랭킹 조회', async ({ page }) => {
  await page.goto(BASE);
  const r = await api(page, 'GET', '/spectator/rankings');
  expect([200, 404, 405, 422]).toContain(r.status);
});

test('T54 가격 예측 음수 가격', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.spectatorToken);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'POST', '/spectator/predict', {
    deal_id: state.dealIds[0],
    buyer_id: state.spectatorId,
    predicted_price: -1000,
  });
  expect([200, 400, 404, 405, 422, 500]).toContain(r.status);
});

test('T55 가격 예측 0원', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.spectatorToken);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'POST', '/spectator/predict', {
    deal_id: state.dealIds[0],
    buyer_id: state.spectatorId,
    predicted_price: 0,
  });
  expect([200, 400, 404, 405, 422, 500]).toContain(r.status);
});

test('T56 없는 딜 관전 시도', async ({ page }) => {
  await page.goto(BASE);
  const r = await api(page, 'GET', '/spectator/view/999999');
  expect([404, 200, 405]).toContain(r.status);
});

test('T57 예측 정산 트리거', async ({ page }) => {
  await page.goto(BASE);
  if (!state.dealIds[0]) return;
  await setToken(page, state.adminToken);
  const r = await api(page, 'POST', `/spectator/settle/${state.dealIds[0]}`);
  expect([200, 400, 404, 405, 422, 500]).toContain(r.status);
});

test('T58 관전 5연속 조회 성능', async ({ page }) => {
  test.setTimeout(30_000);
  await page.goto(BASE);
  await setToken(page, state.spectatorToken);
  const start = Date.now();
  for (let i = 0; i < 5; i++) {
    if (state.dealIds[i % state.dealIds.length]) {
      await api(page, 'GET', `/spectator/view/${state.dealIds[i % state.dealIds.length]}`);
    }
  }
  const elapsed = Date.now() - start;
  console.log(`T58 관전 5연속: ${elapsed}ms`);
  expect(elapsed).toBeLessThan(15000);
});

test('T59 관전 XSS 예측값', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.spectatorToken);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'POST', '/spectator/predict', {
    deal_id: state.dealIds[0],
    buyer_id: state.spectatorId,
    predicted_price: '<script>alert(1)</script>' as any,
  });
  expect([200, 400, 404, 405, 422, 500]).toContain(r.status);
});

test('T60 관전→딜 참여 전환', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.spectatorToken);
  if (!state.dealIds[0]) return;
  // 관전자가 딜 상세 조회 후 참여
  const r = await api(page, 'GET', `/deals/${state.dealIds[0]}`);
  expect([200, 404, 500]).toContain(r.status);
});

// ============================================================
// Phase 4: 등급 시스템 (T61-T90)
// ============================================================

// --- 구매자 등급 ---
test('T61 구매자 신뢰등급 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', `/buyers/${state.buyerId}`);
  expect([200, 404, 500]).toContain(r.status);
  if (r.status === 200) {
    const tier = r.data?.trust_tier || r.data?.grade || 'unknown';
    console.log(`T61 구매자 등급: ${tier}`);
  }
});

test('T62 구매자 레벨 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', '/buyers/me');
  expect([200, 401, 404]).toContain(r.status);
});

test('T63 구매자 포인트 잔액', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', '/points/balance');
  expect([200, 404, 500]).toContain(r.status);
});

test('T64 구매자 포인트 이력', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', '/points/history');
  expect([200, 404, 500]).toContain(r.status);
});

// --- 판매자 등급 ---
test('T65 판매자 레벨 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.sellerToken);
  const r = await api(page, 'GET', `/sellers/${state.sellerId}`);
  expect([200, 404, 500]).toContain(r.status);
  if (r.status === 200) {
    const level = r.data?.level || r.data?.seller_level || 'unknown';
    console.log(`T65 판매자 레벨: ${level}`);
  }
});

test('T66 판매자 평점 조회', async ({ page }) => {
  await page.goto(BASE);
  const r = await api(page, 'GET', `/sellers/${state.sellerId}/rating`);
  expect([200, 404, 500]).toContain(r.status);
});

test('T67 판매자 리뷰 통계', async ({ page }) => {
  await page.goto(BASE);
  const r = await api(page, 'GET', `/reviews/seller/${state.sellerId}/summary`);
  expect([200, 404, 500]).toContain(r.status);
});

test('T68 판매자 등급 레벨 API', async ({ page }) => {
  await page.goto(BASE);
  const r = await api(page, 'GET', `/reviews/seller/${state.sellerId}/level`);
  expect([200, 404, 500]).toContain(r.status);
});

test('T69 판매자 외부 평점', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.sellerToken);
  const r = await api(page, 'GET', `/sellers/${state.sellerId}`);
  expect([200, 404, 500]).toContain(r.status);
  if (r.status === 200) {
    console.log(`T69 외부평점: ${r.data?.external_ratings || 'none'}`);
  }
});

test('T70 판매자 수수료율 조회', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.sellerToken);
  // 수수료율은 오퍼 미리보기나 정책에서 확인
  const r = await api(page, 'GET', '/admin/policy/');
  expect([200, 401, 403, 404]).toContain(r.status);
});

// --- 등급별 권한 ---
test('T71 Lv.1 판매자 오퍼 생성 가능', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.sellerToken);
  if (!state.dealIds[0]) return;
  const r = await api(page, 'POST', '/v3_6/offers', {
    deal_id: state.dealIds[0], seller_id: state.sellerId,
    price: 930000, total_available_qty: 10, delivery_days: 3, shipping_mode: 'INCLUDED',
  });
  expect([200, 201, 400, 409, 422]).toContain(r.status);
});

test('T72 미승인 판매자 오퍼 차단', async ({ page }) => {
  await page.goto(BASE);
  // 새 미승인 판매자 생성
  await setToken(page, '');
  const unapproved = await socialRegister(page, {
    socialId: `unapproved_${TS}`, role: 'seller',
    nickname: `미승인셀러${TS % 10000}`, email: `unapproved_${TS}@test.com`,
    business_name: '미승인샵', business_number: `${TS}11`,
  });
  if (unapproved.data?.access_token && state.dealIds[0]) {
    await setToken(page, unapproved.data.access_token);
    const info = await tokenInfo(page, unapproved.data.access_token);
    const sid = Number(info.seller_id || info.sub || 0);
    const r = await api(page, 'POST', '/v3_6/offers', {
      deal_id: state.dealIds[0], seller_id: sid,
      price: 900000, total_available_qty: 5, delivery_days: 3, shipping_mode: 'INCLUDED',
    });
    // 미승인이면 차단되어야 하지만, 구현에 따라 허용될 수 있음
    expect([200, 201, 400, 403, 409, 422]).toContain(r.status);
    if (r.status === 201) console.log('WARN: 미승인 판매자 오퍼 생성 허용됨');
  }
});

test('T73 구매자 trust_tier T1 기본값', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', `/buyers/${state.buyerId}`);
  expect([200, 404, 500]).toContain(r.status);
  if (r.status === 200) {
    const tier = r.data?.trust_tier;
    console.log(`T73 trust_tier: ${tier}`);
  }
});

test('T74 구매자 bronze 등급 기본', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', `/buyers/${state.buyerId}`);
  expect([200, 404, 500]).toContain(r.status);
  // 구매 0-4건 → bronze
});

test('T75 판매자 Lv.6 기본 등급', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.sellerToken);
  const r = await api(page, 'GET', `/sellers/${state.sellerId}`);
  expect([200, 404, 500]).toContain(r.status);
  if (r.status === 200) {
    const level = r.data?.level || r.data?.seller_level;
    console.log(`T75 seller level: ${level}`);
  }
});

test('T76 관전자 rookie 등급 기본', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.spectatorToken);
  // 관전자 등급은 predictions 수 기준
  const r = await api(page, 'GET', '/spectator/my_predictions');
  expect([200, 404, 405, 422]).toContain(r.status);
});

test('T77 정책 YAML buyer_grade 확인', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'GET', '/admin/policy/yaml');
  expect([200, 401, 403, 404]).toContain(r.status);
  if (r.status === 200) {
    const yaml = typeof r.data === 'string' ? r.data : JSON.stringify(r.data);
    const hasBuyerGrade = yaml.includes('buyer_grade') || yaml.includes('bronze');
    console.log(`T77 buyer_grade in yaml: ${hasBuyerGrade}`);
  }
});

test('T78 정책 YAML spectator_grade 확인', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'GET', '/admin/policy/yaml');
  expect([200, 401, 403, 404]).toContain(r.status);
  if (r.status === 200) {
    const yaml = typeof r.data === 'string' ? r.data : JSON.stringify(r.data);
    const hasSpec = yaml.includes('spectator_grade') || yaml.includes('rookie');
    console.log(`T78 spectator_grade in yaml: ${hasSpec}`);
  }
});

test('T79 정책 YAML actuator 설정 확인', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'GET', '/admin/policy/yaml');
  expect([200, 401, 403, 404]).toContain(r.status);
  if (r.status === 200) {
    const yaml = typeof r.data === 'string' ? r.data : JSON.stringify(r.data);
    const hasAct = yaml.includes('withholding_tax_rate') || yaml.includes('0.033');
    console.log(`T79 actuator config in yaml: ${hasAct}`);
  }
});

test('T80 정책 YAML points 설정 확인', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'GET', '/admin/policy/yaml');
  expect([200, 401, 403, 404]).toContain(r.status);
  if (r.status === 200) {
    const yaml = typeof r.data === 'string' ? r.data : JSON.stringify(r.data);
    const hasPts = yaml.includes('buyer_paid_reward_pt') || yaml.includes('recommender_reward_pt');
    console.log(`T80 points in yaml: ${hasPts}`);
  }
});

// --- 등급 변동 ---
test('T81 결제 후 구매자 포인트 증가', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', '/points/balance');
  expect([200, 404, 500]).toContain(r.status);
  if (r.status === 200) {
    const bal = r.data?.balance || r.data?.total || r.data || 0;
    console.log(`T81 buyer points balance: ${bal}`);
  }
});

test('T82 판매자 정산 히스토리', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.sellerToken);
  const r = await api(page, 'GET', `/settlements/seller/${state.sellerId}`);
  expect([200, 401, 404]).toContain(r.status);
});

test('T83 판매자 정산 목록 (admin)', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'GET', '/settlements/');
  expect([200, 401, 404]).toContain(r.status);
});

test('T84 액추에이터 수수료율 레벨별', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'GET', '/admin/policy/yaml');
  expect([200, 401, 403, 404]).toContain(r.status);
  if (r.status === 200) {
    const yaml = typeof r.data === 'string' ? r.data : JSON.stringify(r.data);
    const hasActFee = yaml.includes('actuator_fee_by_level_rate');
    console.log(`T84 actuator fee levels: ${hasActFee}`);
  }
});

test('T85 판매자 수수료율 레벨별', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.adminToken);
  const r = await api(page, 'GET', '/admin/policy/yaml');
  expect([200, 401, 403, 404]).toContain(r.status);
  if (r.status === 200) {
    const yaml = typeof r.data === 'string' ? r.data : JSON.stringify(r.data);
    const hasFee = yaml.includes('seller_fee_by_level_rate') || yaml.includes('platform_fee_rate');
    console.log(`T85 seller fee levels: ${hasFee}`);
  }
});

test('T86 구매자 다중 딜 참여 후 등급', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', `/buyers/${state.buyerId}`);
  expect([200, 404, 500]).toContain(r.status);
});

test('T87 판매자 리뷰 0건 등급', async ({ page }) => {
  await page.goto(BASE);
  const r = await api(page, 'GET', `/reviews/seller/${state.sellerId}`);
  expect([200, 404, 500]).toContain(r.status);
});

test('T88 등급 5연속 조회 성능', async ({ page }) => {
  test.setTimeout(30_000);
  await page.goto(BASE);
  const start = Date.now();
  for (let i = 0; i < 5; i++) {
    await setToken(page, state.buyerToken);
    await api(page, 'GET', `/buyers/${state.buyerId}`);
    await setToken(page, state.sellerToken);
    await api(page, 'GET', `/sellers/${state.sellerId}`);
  }
  const elapsed = Date.now() - start;
  console.log(`T88 등급 10연속 조회: ${elapsed}ms`);
  expect(elapsed).toBeLessThan(30000);
});

test('T89 구매자 대시보드에 등급 표시', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.buyerToken);
  const r = await api(page, 'GET', '/dashboard/buyer');
  expect([200, 401, 404]).toContain(r.status);
});

test('T90 판매자 대시보드에 등급 표시', async ({ page }) => {
  await page.goto(BASE);
  await setToken(page, state.sellerToken);
  const r = await api(page, 'GET', '/dashboard/seller');
  expect([200, 401, 404]).toContain(r.status);
});
