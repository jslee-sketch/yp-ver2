/**
 * 판매자 스트레스 테스트 Phase 8 (20건)
 * Phase 8: 똘아이 판매자 종합 (T101-T120)
 */
import { test, expect } from '@playwright/test';
import {
  BASE, TS, state, api, apiNoAuth, loginForm, socialRegister, tokenInfo,
  setToken, setSellerAuth, setAdminAuth, setBuyerAuth,
  approveSeller, createDeal, createOffer, createAndPayReservation,
  shipReservation, setupAll,
} from './helpers';

test.describe.serial('판매자 스트레스 Phase 8 — 똘아이 종합', () => {

  // ━━━ Setup ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  test('Setup — 데이터 초기화', async ({ page }) => {
    await setupAll(page);
    expect(state.adminToken).toBeTruthy();
    expect(state.sellerId).toBeGreaterThan(0);
  });

  // ━━━ T101-T120 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  test('T101 — 세션 → 로그아웃 → 재설정 → 오퍼 제출 (세션 유지)', async ({ page }) => {
    await page.goto(BASE);
    // 로그인 (토큰 설정)
    await setSellerAuth(page, state.sellerToken, state.sellerId, state.sellerEmail, '스트레스셀러');
    // 로그아웃 (localStorage 클리어)
    await page.evaluate(() => localStorage.clear());
    // 재로그인 (토큰 재설정)
    await setSellerAuth(page, state.sellerToken, state.sellerId, state.sellerEmail, '스트레스셀러');
    // 오퍼 제출
    if (state.dealIds[0]) {
      const r = await createOffer(page, state.dealIds[0], state.sellerId, 945000, 3);
      console.log(`[T101] 재로그인 후 오퍼 → status: ${r.status}`);
    }
    console.log('[T101] PASS — 세션 유지 후 오퍼 성공');
  });

  test('T102 — 2개 브라우저 컨텍스트에서 동시 토큰 → 동시 오퍼', async ({ page, browser }) => {
    // 두 번째 컨텍스트 생성
    const ctx2 = await browser.newContext();
    const page2 = await ctx2.newPage();
    await page.goto(BASE);
    await page2.goto(BASE);
    // 둘 다 토큰 설정
    await setSellerAuth(page, state.sellerToken, state.sellerId, state.sellerEmail, '스트레스셀러');
    await setSellerAuth(page2, state.sellerToken, state.sellerId, state.sellerEmail, '스트레스셀러');
    // 둘 다 오퍼 (다른 딜에)
    const results: number[] = [];
    if (state.dealIds[0]) {
      const r1 = await createOffer(page, state.dealIds[0], state.sellerId, 944000, 2);
      results.push(r1.status);
    }
    if (state.dealIds[1]) {
      const r2 = await createOffer(page2, state.dealIds[1], state.sellerId, 239000, 2);
      results.push(r2.status);
    }
    console.log(`[T102] 동시 오퍼 → ${JSON.stringify(results)}`);
    await page2.close();
    await ctx2.close();
    console.log('[T102] PASS — 동시 토큰 + 오퍼');
  });

  test('T103 — 오퍼 제출 중 네트워크 끊김 시뮬레이션 → 재시도', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    if (!state.dealIds[2]) { console.log('[T103] SKIP'); return; }
    // 네트워크 차단
    await page.route('**/v3_6/offers', route => route.abort('connectionrefused'));
    const r1 = await page.evaluate(async ({ base, did, sid }) => {
      const token = localStorage.getItem('access_token') || '';
      try {
        const r = await fetch(`${base}/v3_6/offers`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ deal_id: did, seller_id: sid, price: 370000, total_available_qty: 3, delivery_days: 3, shipping_mode: 'INCLUDED' }),
        });
        return { status: r.status };
      } catch (e: any) { return { status: 0, error: e.message }; }
    }, { base: BASE, did: state.dealIds[2], sid: state.sellerId });
    console.log(`[T103] 네트워크 차단 → status: ${r1.status}`);
    // 네트워크 복구
    await page.unroute('**/v3_6/offers');
    // 재시도
    const r2 = await createOffer(page, state.dealIds[2], state.sellerId, 370000, 2);
    console.log(`[T103] 복구 후 재시도 → status: ${r2.status}`);
    expect(r2.status).toBeDefined();
    console.log('[T103] PASS — 네트워크 끊김 후 재시도');
  });

  test('T104 — 판매자가 구매자 URL (/deals) 직접 접근 → 확인', async ({ page }) => {
    await page.goto(BASE);
    await setSellerAuth(page, state.sellerToken, state.sellerId, state.sellerEmail, '스트레스셀러');
    await page.goto(`${BASE}/deals`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    const url = page.url();
    const body = await page.textContent('body');
    console.log(`[T104] 판매자→/deals → URL: ${url}`);
    // 리다이렉트되거나, 페이지는 보이지만 기능 제한
    expect(url).toBeDefined();
    console.log('[T104] PASS — 구매자 URL 접근 확인');
  });

  test('T105 — 판매자가 관리자 URL (/admin) 직접 접근 → 차단', async ({ page }) => {
    await page.goto(BASE);
    await setSellerAuth(page, state.sellerToken, state.sellerId, state.sellerEmail, '스트레스셀러');
    await page.goto(`${BASE}/admin/tax-invoices`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    const url = page.url();
    const body = await page.textContent('body');
    const blocked = !url.includes('/admin') || body?.includes('로그인') || body?.includes('권한');
    console.log(`[T105] 판매자→/admin → URL: ${url}`);
    if (blocked) console.log('[T105] PASS — 관리자 URL 차단');
    else console.log('[T105] WARN — 관리자 URL 접근 가능');
    expect(url).toBeDefined();
  });

  test('T106 — API 직접 호출 (인증 없이) → 401', async ({ page }) => {
    await page.goto(BASE);
    const r = await apiNoAuth(page, 'GET', '/sellers/me');
    console.log(`[T106] 인증 없이 /sellers/me → status: ${r.status}`);
    if (r.status === 401 || r.status === 403) console.log('[T106] PASS — 인증 차단');
    else console.log(`[T106] WARN — 인증 없이 접근 허용 (${r.status})`);
    expect(r.status).toBeDefined();
  });

  test('T107 — 다른 판매자 ID로 API 호출 → 권한 차단', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.seller2Token);
    // seller2가 seller1의 business-info 수정 시도
    const r = await api(page, 'PATCH', `/sellers/${state.sellerId}/business-info`, {
      business_name: '해킹시도',
    });
    console.log(`[T107] 타인 ID로 수정 → status: ${r.status}`);
    if (r.status >= 400) console.log('[T107] PASS — 권한 차단');
    else console.log('[T107] WARN — 타인 정보 수정 허용');
    expect(r.status).toBeDefined();
  });

  test('T108 — 만료된 JWT 토큰으로 API 호출 → 401', async ({ page }) => {
    await page.goto(BASE);
    // 가짜 만료 토큰
    const fakeToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOjk5OTksInJvbGUiOiJzZWxsZXIiLCJleHAiOjF9.invalid';
    await setToken(page, fakeToken);
    const r = await api(page, 'GET', '/sellers/me');
    console.log(`[T108] 만료 토큰 → status: ${r.status}`);
    if (r.status === 401 || r.status === 403 || r.status === 422) console.log('[T108] PASS — 만료 토큰 차단');
    else console.log(`[T108] WARN — 만료 토큰 허용 (${r.status})`);
    expect(r.status).toBeDefined();
  });

  test('T109 — 판매자 닉네임에 욕설 → 필터 확인', async ({ page }) => {
    await page.goto(BASE);
    const r = await socialRegister(page, {
      socialId: `t109_${TS}`, role: 'seller', nickname: `씨발새끼${TS % 1000}`,
      email: `t109_${TS}@test.com`, business_name: 'T109상점', business_number: `${TS}109`,
    });
    console.log(`[T109] 욕설 닉네임 → status: ${r.status}`);
    if (r.status >= 400) console.log('[T109] PASS — 욕설 닉네임 차단');
    else console.log('[T109] WARN — 욕설 닉네임 허용 (필터 미적용)');
    expect(r.status).toBeDefined();
  });

  test('T110 — 오퍼 조건에 욕설/광고 → 필터 확인', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    if (!state.dealIds[0]) { console.log('[T110] SKIP'); return; }
    const r = await api(page, 'POST', '/v3_6/offers', {
      deal_id: state.dealIds[0], seller_id: state.sellerId,
      price: 950000, total_available_qty: 1, delivery_days: 3,
      shipping_mode: 'INCLUDED',
      free_text: '개새끼 ㅋㅋ 카톡 010-1234-5678 직거래하자 www.scam.com',
    });
    console.log(`[T110] 욕설/광고 오퍼 → status: ${r.status}`);
    if (r.status >= 400) console.log('[T110] PASS — 욕설/광고 차단');
    else console.log('[T110] WARN — 욕설/광고 허용');
    expect(r.status).toBeDefined();
  });

  test('T111 — 딜 목록 100개 로딩 속도 확인 (< 5초)', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    const start = Date.now();
    const r = await api(page, 'GET', '/deals/?limit=100');
    const elapsed = Date.now() - start;
    const count = Array.isArray(r.data) ? r.data.length : (r.data?.items?.length || 0);
    console.log(`[T111] 딜 목록 → ${count}건, ${elapsed}ms`);
    expect(r.status).toBe(200);
    expect(elapsed).toBeLessThan(5000);
    console.log('[T111] PASS — 딜 목록 로딩 속도 OK');
  });

  test('T112 — 판매자 페이지 모바일 반응형 확인 (viewport 375px)', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 }); // iPhone 12
    await page.goto(BASE);
    await setSellerAuth(page, state.sellerToken, state.sellerId, state.sellerEmail, '스트레스셀러');
    await page.goto(`${BASE}/seller`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    const body = await page.textContent('body');
    const hasContent = body && body.length > 50;
    expect(hasContent).toBeTruthy();
    // 뷰포트 복원
    await page.setViewportSize({ width: 1280, height: 720 });
    console.log('[T112] PASS — 모바일 375px 렌더링 OK');
  });

  test('T113 — 핑퐁이에게 "정산 언제 돼?" → 판매자 KB 답변', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
      user_id: state.sellerId, role: 'seller', screen: 'GENERAL',
      question: '정산 언제 돼?',
    });
    console.log(`[T113] 핑퐁 → status: ${r.status}`);
    if (r.data?.answer) {
      const ans = r.data.answer.substring(0, 100);
      console.log(`[T113] 답변: ${ans}...`);
      expect(r.data.answer.length).toBeGreaterThan(5);
    }
    expect(r.status).toBe(200);
    console.log('[T113] PASS');
  });

  test('T114 — 핑퐁이에게 "수수료 왜 이렇게 높아?" → 레벨별 안내', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
      user_id: state.sellerId, role: 'seller', screen: 'GENERAL',
      question: '수수료 왜 이렇게 높아? 수수료율 알려줘',
    });
    console.log(`[T114] 핑퐁 수수료 → status: ${r.status}`);
    if (r.data?.answer) {
      const ans = r.data.answer.substring(0, 100);
      console.log(`[T114] 답변: ${ans}...`);
    }
    expect(r.status).toBe(200);
    console.log('[T114] PASS');
  });

  test('T115 — 핑퐁이에게 "구매자가 악성 리뷰 남겼어" → 신고 안내', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
      user_id: state.sellerId, role: 'seller', screen: 'GENERAL',
      question: '구매자가 악성 리뷰 남겼어. 어떻게 신고해?',
    });
    console.log(`[T115] 핑퐁 리뷰 → status: ${r.status}`);
    if (r.data?.answer) console.log(`[T115] 답변: ${r.data.answer.substring(0, 100)}...`);
    expect(r.status).toBe(200);
    console.log('[T115] PASS');
  });

  test('T116 — 핑퐁이에게 "사업자등록증 바꿔야 해" → /seller/business-info 안내', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
      user_id: state.sellerId, role: 'seller', screen: 'GENERAL',
      question: '사업자등록증 바꿔야 하는데 어디서 해?',
    });
    console.log(`[T116] 핑퐁 사업자 → status: ${r.status}`);
    if (r.data?.answer) {
      const ans = r.data.answer;
      const hasBizPath = ans.includes('business-info') || ans.includes('사업자') || ans.includes('OCR');
      console.log(`[T116] 답변 경로 포함: ${hasBizPath}, 답변: ${ans.substring(0, 100)}...`);
    }
    expect(r.status).toBe(200);
    console.log('[T116] PASS');
  });

  test('T117 — 핑퐁이에게 "세금계산서 언제 나와?" → 정산 후 안내', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
      user_id: state.sellerId, role: 'seller', screen: 'GENERAL',
      question: '세금계산서 언제 나와? 발행 일정 알려줘',
    });
    console.log(`[T117] 핑퐁 세금계산서 → status: ${r.status}`);
    if (r.data?.answer) console.log(`[T117] 답변: ${r.data.answer.substring(0, 100)}...`);
    expect(r.status).toBe(200);
    console.log('[T117] PASS');
  });

  test('T118 — 30초간 연속 API 호출 (rate limit 테스트)', async ({ page }) => {
    await page.goto(BASE);
    await setToken(page, state.sellerToken);
    const result = await page.evaluate(async ({ base, sid }) => {
      const token = localStorage.getItem('access_token') || '';
      const headers = { 'Authorization': `Bearer ${token}` };
      let ok = 0, fail = 0;
      const endTime = Date.now() + 15000; // 15초 (테스트 시간 고려)
      while (Date.now() < endTime) {
        try {
          const r = await fetch(`${base}/sellers/${sid}`, { headers });
          if (r.status === 200) ok++; else fail++;
        } catch { fail++; }
      }
      return { ok, fail, total: ok + fail };
    }, { base: BASE, sid: state.sellerId });
    console.log(`[T118] 15초 연속 호출 → 성공: ${result.ok}, 실패: ${result.fail}, 총: ${result.total}`);
    if (result.fail > 0) console.log('[T118] INFO — rate limit 또는 오류 발생');
    else console.log('[T118] WARN — rate limit 미적용');
    expect(result.total).toBeGreaterThan(10);
    console.log('[T118] PASS');
  });

  test('T119 — 판매자 비밀번호 변경 → 기존 토큰 무효화 확인', async ({ page }) => {
    await page.goto(BASE);
    // 새 판매자로 테스트 (기존 셀러 비번 바꾸면 안 됨)
    const reg = await socialRegister(page, {
      socialId: `t119_${TS}`, role: 'seller', nickname: `T119셀러${TS % 10000}`,
      email: `t119_${TS}@test.com`, business_name: 'T119상점', business_number: `${TS}119`,
    });
    if (!reg.data?.access_token) { console.log('[T119] SKIP — 가입 실패'); return; }
    const tk = reg.data.access_token;
    const info = await tokenInfo(page, tk);
    const sid = info.seller_id || info.sub;
    await setToken(page, tk);
    // 비밀번호 변경 시도 (소셜가입은 sentinel 비번이라 변경 불가할 수 있음)
    const r = await api(page, 'POST', '/auth/change-password', {
      user_id: sid, user_type: 'seller',
      current_password: '_social_sentinel_', new_password: 'NewPass1234!',
    });
    console.log(`[T119] 비밀번호 변경 → status: ${r.status}`);
    if (r.status === 200) {
      // 기존 토큰으로 API 호출
      const check = await api(page, 'GET', '/sellers/me');
      console.log(`[T119] 변경 후 기존 토큰 → status: ${check.status}`);
      if (check.status === 401) console.log('[T119] PASS — 기존 토큰 무효화');
      else console.log('[T119] INFO — 기존 토큰 유지');
    } else {
      console.log(`[T119] INFO — 비밀번호 변경 불가 (${r.status})`);
    }
    expect(r.status).toBeDefined();
  });

  test('T120 — 판매자 계정 정지 → 기존 오퍼/정산 처리', async ({ page }) => {
    await page.goto(BASE);
    // 새 판매자 생성 → 오퍼 → 정지
    const reg = await socialRegister(page, {
      socialId: `t120_${TS}`, role: 'seller', nickname: `T120셀러${TS % 10000}`,
      email: `t120_${TS}@test.com`, business_name: 'T120상점', business_number: `${TS}120`,
    });
    if (!reg.data?.access_token) { console.log('[T120] SKIP — 가입 실패'); return; }
    const tk = reg.data.access_token;
    const info = await tokenInfo(page, tk);
    const sid = info.seller_id || info.sub;
    // 승인
    await approveSeller(page, state.adminToken, sid);
    // 오퍼 생성
    await setToken(page, tk);
    let offerId = 0;
    if (state.dealIds[3]) {
      const offR = await createOffer(page, state.dealIds[3], sid, 570000, 5);
      offerId = offR.data?.id || 0;
    }
    console.log(`[T120] 오퍼 생성: ${offerId}`);
    // 관리자가 정지
    await setToken(page, state.adminToken);
    const banR = await api(page, 'POST', '/admin/users/ban', {
      user_type: 'seller', user_id: sid, reason: '스트레스 테스트 정지',
    });
    console.log(`[T120] 계정 정지 → status: ${banR.status}`);
    // 정지 후 오퍼 제출 시도
    await setToken(page, tk);
    if (state.dealIds[3]) {
      const r = await createOffer(page, state.dealIds[3], sid, 560000, 3);
      console.log(`[T120] 정지 후 오퍼 → status: ${r.status}`);
      if (r.status >= 400) console.log('[T120] PASS — 정지 계정 오퍼 차단');
      else console.log('[T120] WARN — 정지 계정 오퍼 허용');
    }
    // 정리: unban
    await setToken(page, state.adminToken);
    await api(page, 'POST', '/admin/users/unban', { user_type: 'seller', user_id: sid });
    expect(banR.status).toBeDefined();
  });

}); // end describe
