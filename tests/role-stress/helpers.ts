/**
 * 역할 스트레스 테스트 — 공통 헬퍼
 * 테스트 대상: 액추에이터, 추천인, 관전자, 등급, 안전
 */
import { type Page } from '@playwright/test';

export const BASE = 'https://web-production-defb.up.railway.app';
export const TS = Date.now();

// ── 공유 상태 ──────────────────────────────────────────
export const state: {
  adminToken: string;
  buyerToken: string;
  buyerId: number;
  buyerEmail: string;
  buyer2Token: string;
  buyer2Id: number;
  sellerToken: string;
  sellerId: number;
  sellerEmail: string;
  seller2Token: string;
  seller2Id: number;
  actuatorToken: string;
  actuatorId: number;
  actuatorEmail: string;
  actuator2Token: string;
  actuator2Id: number;
  spectatorToken: string;
  spectatorId: number;
  dealIds: number[];
  offerIds: number[];
  resIds: number[];
  paidResIds: number[];
} = {
  adminToken: '',
  buyerToken: '', buyerId: 0, buyerEmail: '',
  buyer2Token: '', buyer2Id: 0,
  sellerToken: '', sellerId: 0, sellerEmail: '',
  seller2Token: '', seller2Id: 0,
  actuatorToken: '', actuatorId: 0, actuatorEmail: '',
  actuator2Token: '', actuator2Id: 0,
  spectatorToken: '', spectatorId: 0,
  dealIds: [], offerIds: [],
  resIds: [], paidResIds: [],
};

// ── API 호출 ───────────────────────────────────────────
export async function api(page: Page, method: string, path: string, body?: any, token?: string): Promise<any> {
  return page.evaluate(
    async ({ base, method, path, body, token }) => {
      const opts: RequestInit = {
        method,
        headers: { 'Content-Type': 'application/json' } as any,
      };
      if (token) (opts.headers as any)['Authorization'] = `Bearer ${token}`;
      else {
        const t = localStorage.getItem('access_token');
        if (t) (opts.headers as any)['Authorization'] = `Bearer ${t}`;
      }
      if (body) opts.body = JSON.stringify(body);
      const r = await fetch(`${base}${path}`, opts);
      const text = await r.text();
      try { return { status: r.status, data: JSON.parse(text) }; }
      catch { return { status: r.status, data: text }; }
    },
    { base: BASE, method, path, body, token },
  );
}

export async function apiNoAuth(page: Page, method: string, path: string, body?: any): Promise<any> {
  return page.evaluate(
    async ({ base, method, path, body }) => {
      const opts: RequestInit = {
        method,
        headers: { 'Content-Type': 'application/json' } as any,
      };
      if (body) opts.body = JSON.stringify(body);
      const r = await fetch(`${base}${path}`, opts);
      const text = await r.text();
      try { return { status: r.status, data: JSON.parse(text) }; }
      catch { return { status: r.status, data: text }; }
    },
    { base: BASE, method, path, body },
  );
}

// ── 로그인 ─────────────────────────────────────────────
export async function loginForm(page: Page, email: string, password: string): Promise<{ status: number; token: string }> {
  const res = await page.evaluate(
    async ({ base, email, password }) => {
      for (const url of ['/auth/login', '/auth/seller/login']) {
        const params = new URLSearchParams();
        params.append('username', email);
        params.append('password', password);
        const r = await fetch(`${base}${url}`, { method: 'POST', body: params });
        if (r.status === 200) {
          const d = await r.json();
          if (d.access_token) return { status: 200, token: d.access_token };
        }
      }
      return { status: 401, token: '' };
    },
    { base: BASE, email, password },
  );
  return res;
}

// ── 소셜 회원가입 ──────────────────────────────────────
export async function socialRegister(page: Page, opts: {
  socialId: string; role: string; nickname: string; email: string;
  business_name?: string; business_number?: string; phone?: string; address?: string;
  [key: string]: any;
}) {
  return apiNoAuth(page, 'POST', '/auth/social/register', {
    social_provider: 'kakao',
    social_id: opts.socialId,
    role: opts.role,
    nickname: opts.nickname,
    email: opts.email,
    business_name: opts.business_name,
    business_number: opts.business_number,
    phone: opts.phone,
    address: opts.address,
    ...Object.fromEntries(Object.entries(opts).filter(([k]) =>
      !['socialId', 'role', 'nickname', 'email'].includes(k)
    )),
  });
}

// ── JWT 디코드 ─────────────────────────────────────────
export async function tokenInfo(page: Page, token: string): Promise<any> {
  return page.evaluate((t) => {
    try {
      return JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    } catch { return {}; }
  }, token);
}

// ── localStorage 세팅 ──────────────────────────────────
export async function setToken(page: Page, token: string) {
  await page.evaluate((t) => {
    localStorage.setItem('access_token', t);
    localStorage.setItem('token', t);
  }, token);
}

export async function setAuth(page: Page, token: string, id: number, email: string, role: string, extra?: Record<string, any>) {
  await page.evaluate(({ t, id, email, role, extra }) => {
    localStorage.setItem('access_token', t);
    localStorage.setItem('token', t);
    localStorage.setItem('role', role);
    const user: Record<string, any> = { id, email, name: `test_${role}`, nickname: `test_${role}`, role, level: 1, points: 0 };
    if (extra) Object.assign(user, extra);
    localStorage.setItem('user', JSON.stringify(user));
  }, { t: token, id, email, role, extra });
}

// ── 판매자 승인 ────────────────────────────────────────
export async function approveSeller(page: Page, adminToken: string, sellerId: number) {
  return api(page, 'PATCH', `/sellers/${sellerId}/approve`, {}, adminToken);
}

// ── 딜 생성 ────────────────────────────────────────────
export async function createDeal(page: Page, name: string, target: number, anchor: number, qty: number, creatorId: number) {
  return api(page, 'POST', '/deals/', {
    product_name: name,
    creator_id: creatorId,
    desired_qty: qty,
    target_price: target,
    anchor_price: anchor,
    category: 'electronics',
  });
}

// ── 오퍼 생성 ──────────────────────────────────────────
export async function createOffer(page: Page, dealId: number, sellerId: number, price: number, qty: number = 50) {
  return api(page, 'POST', '/v3_6/offers', {
    deal_id: dealId,
    seller_id: sellerId,
    price,
    total_available_qty: qty,
    delivery_days: 3,
    shipping_mode: 'INCLUDED',
  });
}

// ── 예약 + 결제 ────────────────────────────────────────
export async function createAndPayReservation(page: Page, dealId: number, offerId: number, buyerId: number, amount: number) {
  const resR = await api(page, 'POST', '/v3_6/reservations', {
    deal_id: dealId, offer_id: offerId,
    buyer_id: buyerId, qty: 1,
  });
  if (!resR.data?.id) return null;
  const payR = await api(page, 'POST', '/v3_6/reservations/pay', {
    reservation_id: resR.data.id,
    buyer_id: buyerId,
    paid_amount: amount,
  });
  if (payR.status === 200) {
    state.resIds.push(resR.data.id);
    state.paidResIds.push(resR.data.id);
    return resR.data.id;
  }
  return null;
}

// ── Setup: 전체 데이터 초기화 ──────────────────────────
export async function setupAll(page: Page) {
  await page.goto(BASE);

  // 1. Admin login
  const adminRes = await loginForm(page, 'admin@yeokping.com', 'admin1234!');
  state.adminToken = adminRes.token;
  console.log(`[Setup] admin: ${adminRes.status}`);

  // 2. Buyer
  await setToken(page, '');
  const buyerEmail = `rolebuy_${TS}@test.com`;
  const buyerReg = await socialRegister(page, {
    socialId: `rolebuy_${TS}`, role: 'buyer',
    nickname: `롤바이어${TS % 10000}`, email: buyerEmail,
  });
  state.buyerToken = buyerReg.data?.access_token || '';
  state.buyerEmail = buyerEmail;
  if (state.buyerToken) {
    const info = await tokenInfo(page, state.buyerToken);
    state.buyerId = Number(info.sub || 0);
  } else {
    console.log(`[Setup] buyer reg failed: ${JSON.stringify(buyerReg).substring(0, 300)}`);
  }
  console.log(`[Setup] buyer: ${state.buyerId}`);

  // 3. Buyer2 (추천인 테스트용)
  await setToken(page, '');
  const b2Reg = await socialRegister(page, {
    socialId: `rolebuy2_${TS}`, role: 'buyer',
    nickname: `롤바이어2_${TS % 10000}`, email: `rolebuy2_${TS}@test.com`,
    recommender_buyer_id: state.buyerId,
  });
  if (b2Reg.data?.access_token) {
    state.buyer2Token = b2Reg.data.access_token;
    const info = await tokenInfo(page, state.buyer2Token);
    state.buyer2Id = Number(info.sub || 0);
  }
  console.log(`[Setup] buyer2: ${state.buyer2Id}`);

  // 4. Seller
  await setToken(page, '');
  const sellerEmail = `rolesell_${TS}@test.com`;
  const sellerReg = await socialRegister(page, {
    socialId: `rolesell_${TS}`, role: 'seller',
    nickname: `롤셀러${TS % 10000}`, email: sellerEmail,
    business_name: '롤테스트상점', business_number: `${TS}5`,
  });
  state.sellerToken = sellerReg.data?.access_token || '';
  state.sellerEmail = sellerEmail;
  if (state.sellerToken) {
    const info = await tokenInfo(page, state.sellerToken);
    state.sellerId = Number(info.seller_id || info.sub || 0);
    await approveSeller(page, state.adminToken, state.sellerId);
  }
  console.log(`[Setup] seller: ${state.sellerId}`);

  // 5. Seller2
  await setToken(page, '');
  const s2Reg = await socialRegister(page, {
    socialId: `rolesell2_${TS}`, role: 'seller',
    nickname: `롤셀러2_${TS % 10000}`, email: `rolesell2_${TS}@test.com`,
    business_name: '롤테스트상점2', business_number: `${TS}6`,
  });
  if (s2Reg.data?.access_token) {
    state.seller2Token = s2Reg.data.access_token;
    const info = await tokenInfo(page, state.seller2Token);
    state.seller2Id = Number(info.seller_id || info.sub || 0);
    await approveSeller(page, state.adminToken, state.seller2Id);
  }
  console.log(`[Setup] seller2: ${state.seller2Id}`);

  // 6. Actuator
  await setToken(page, '');
  const actEmail = `roleact_${TS}@test.com`;
  const actReg = await socialRegister(page, {
    socialId: `roleact_${TS}`, role: 'actuator',
    nickname: `롤액추에이터${TS % 10000}`, email: actEmail,
  });
  state.actuatorToken = actReg.data?.access_token || '';
  state.actuatorEmail = actEmail;
  if (state.actuatorToken) {
    const info = await tokenInfo(page, state.actuatorToken);
    state.actuatorId = Number(info.actuator_id || info.sub || 0);
  }
  console.log(`[Setup] actuator: ${state.actuatorId}`);

  // 7. Actuator2 (사업자)
  await setToken(page, '');
  const a2Reg = await socialRegister(page, {
    socialId: `roleact2_${TS}`, role: 'actuator',
    nickname: `롤액추2_${TS % 10000}`, email: `roleact2_${TS}@test.com`,
    is_business: true, business_name: '롤액추법인', business_number: `${TS}7`,
  });
  if (a2Reg.data?.access_token) {
    state.actuator2Token = a2Reg.data.access_token;
    const info = await tokenInfo(page, state.actuator2Token);
    state.actuator2Id = Number(info.actuator_id || info.sub || 0);
  }
  console.log(`[Setup] actuator2 (biz): ${state.actuator2Id}`);

  // 8. Spectator (buyer를 관전용으로 활용)
  await setToken(page, '');
  const specReg = await socialRegister(page, {
    socialId: `rolespec_${TS}`, role: 'buyer',
    nickname: `롤관전자${TS % 10000}`, email: `rolespec_${TS}@test.com`,
  });
  if (specReg.data?.access_token) {
    state.spectatorToken = specReg.data.access_token;
    const info = await tokenInfo(page, state.spectatorToken);
    state.spectatorId = Number(info.sub || 0);
  }
  console.log(`[Setup] spectator: ${state.spectatorId}`);

  // 9. Create 3 deals (buyer)
  await setToken(page, state.buyerToken);
  const dealDefs = [
    { name: '롤테스트 갤럭시', target: 1000000, anchor: 1200000, qty: 20 },
    { name: '롤테스트 에어팟', target: 250000, anchor: 300000, qty: 30 },
    { name: '롤테스트 다이슨', target: 400000, anchor: 500000, qty: 15 },
  ];
  for (const d of dealDefs) {
    const r = await createDeal(page, d.name, d.target, d.anchor, d.qty, state.buyerId);
    if (r.data?.id) state.dealIds.push(r.data.id);
  }
  console.log(`[Setup] deals: ${JSON.stringify(state.dealIds)}`);

  // 10. Seller creates offers
  await setToken(page, state.sellerToken);
  const prices = [950000, 240000, 380000];
  for (let i = 0; i < state.dealIds.length; i++) {
    const r = await createOffer(page, state.dealIds[i], state.sellerId, prices[i]);
    if (r.data?.id) state.offerIds.push(r.data.id);
  }
  console.log(`[Setup] offers: ${JSON.stringify(state.offerIds)}`);

  // 11. Buyer creates & pays reservations
  await setToken(page, state.buyerToken);
  for (let i = 0; i < Math.min(3, state.dealIds.length); i++) {
    if (!state.offerIds[i]) continue;
    await createAndPayReservation(page, state.dealIds[i], state.offerIds[i], state.buyerId, prices[i]);
  }
  console.log(`[Setup] reservations: ${state.resIds.length}, paid: ${state.paidResIds.length}`);
  console.log('[Setup] COMPLETE');
}
