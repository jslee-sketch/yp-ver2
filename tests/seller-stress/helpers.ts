/**
 * 판매자 스트레스 테스트 — 공통 헬퍼
 */
import { type Page } from '@playwright/test';

export const BASE = 'https://web-production-defb.up.railway.app';
export const TS = Date.now();

// ── 공유 상태 (모든 phase에서 import) ──────────────────
export const state: {
  adminToken: string;
  buyerToken: string;
  buyerId: number;
  sellerToken: string;
  sellerId: number;
  sellerEmail: string;
  seller2Token: string;
  seller2Id: number;
  stressTokens: string[];
  stressIds: number[];
  dealIds: number[];
  offerIds: number[];
  resIds: number[];
  paidResIds: number[];
  shippedResIds: number[];
  arrivedResIds: number[];
  refundedResIds: number[];
  settlementIds: number[];
  invoiceIds: number[];
} = {
  adminToken: '',
  buyerToken: '', buyerId: 0,
  sellerToken: '', sellerId: 0, sellerEmail: '',
  seller2Token: '', seller2Id: 0,
  stressTokens: [], stressIds: [],
  dealIds: [], offerIds: [],
  resIds: [], paidResIds: [],
  shippedResIds: [], arrivedResIds: [],
  refundedResIds: [], settlementIds: [],
  invoiceIds: [],
};

// ── API 호출 (토큰 자동 첨부) ─────────────────────────
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

// ── 인증 없이 API 호출 ────────────────────────────────
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

// ── 로그인 (form-urlencoded) ──────────────────────────
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

// ── 소셜 회원가입 ─────────────────────────────────────
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

// ── JWT 디코드 ────────────────────────────────────────
export async function tokenInfo(page: Page, token: string): Promise<any> {
  return page.evaluate((t) => {
    try {
      return JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    } catch { return {}; }
  }, token);
}

// ── localStorage 세팅 ─────────────────────────────────
export async function setToken(page: Page, token: string) {
  await page.evaluate((t) => {
    localStorage.setItem('access_token', t);
    localStorage.setItem('token', t);
  }, token);
}

export async function setSellerAuth(page: Page, token: string, sid: number, email: string, nick: string) {
  await page.evaluate(({ t, sid, email, nick }) => {
    localStorage.setItem('access_token', t);
    localStorage.setItem('token', t);
    localStorage.setItem('seller_id', String(sid));
    localStorage.setItem('role', 'seller');
    localStorage.setItem('user', JSON.stringify({
      id: sid, email, name: nick, nickname: nick,
      role: 'seller', level: 6, points: 0,
    }));
  }, { t: token, sid, email, nick });
}

export async function setAdminAuth(page: Page, token: string) {
  await page.evaluate((t) => {
    localStorage.setItem('access_token', t);
    localStorage.setItem('token', t);
    localStorage.setItem('role', 'admin');
    localStorage.setItem('user', JSON.stringify({
      id: 1, email: 'admin@yeokping.com', name: 'Admin',
      role: 'admin', level: 1, points: 0,
    }));
  }, t);
}

export async function setBuyerAuth(page: Page, token: string, bid: number, email: string) {
  await page.evaluate(({ t, bid, email }) => {
    localStorage.setItem('access_token', t);
    localStorage.setItem('token', t);
    localStorage.setItem('role', 'buyer');
    localStorage.setItem('user', JSON.stringify({
      id: bid, email, name: '테스트바이어', nickname: '테스트바이어',
      role: 'buyer', level: 1, points: 0,
    }));
  }, { t: token, bid, email });
}

// ── 판매자 승인 (관리자 권한) ─────────────────────────
export async function approveSeller(page: Page, adminToken: string, sellerId: number) {
  return api(page, 'PATCH', `/sellers/${sellerId}/approve`, {}, adminToken);
}

// ── 딜 생성 ───────────────────────────────────────────
export async function createDeal(page: Page, name: string, target: number, anchor: number, qty: number) {
  return api(page, 'POST', '/deals/', {
    product_name: name,
    creator_id: state.buyerId,
    desired_qty: qty,
    target_price: target,
    anchor_price: anchor,
    category: 'electronics',
  });
}

// ── 오퍼 생성 ─────────────────────────────────────────
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

// ── 예약 생성 + 결제 ──────────────────────────────────
export async function createAndPayReservation(page: Page, dealId: number, offerId: number, amount: number) {
  const resR = await api(page, 'POST', '/v3_6/reservations', {
    deal_id: dealId, offer_id: offerId,
    buyer_id: state.buyerId, qty: 1,
  });
  if (!resR.data?.id) return null;
  const payR = await api(page, 'POST', '/v3_6/reservations/pay', {
    reservation_id: resR.data.id,
    buyer_id: state.buyerId,
    paid_amount: amount,
  });
  if (payR.status === 200) {
    state.resIds.push(resR.data.id);
    state.paidResIds.push(resR.data.id);
    return resR.data.id;
  }
  return null;
}

// ── 배송 처리 ─────────────────────────────────────────
export async function shipReservation(page: Page, resId: number, carrier: string, tracking: string) {
  return api(page, 'POST', `/v3_6/reservations/${resId}/ship`, {
    seller_id: state.sellerId,
    shipping_carrier: carrier,
    tracking_number: tracking,
  });
}

// ── 도착 확인 ─────────────────────────────────────────
export async function confirmArrival(page: Page, resId: number) {
  return api(page, 'POST', `/v3_6/reservations/${resId}/arrival-confirm`, {
    buyer_id: state.buyerId,
  });
}

// ── 환불 ──────────────────────────────────────────────
export async function refundReservation(page: Page, resId: number, actor: string = 'buyer_cancel') {
  return api(page, 'POST', '/v3_6/reservations/refund', {
    reservation_id: resId,
    reason: '스트레스 테스트 환불',
    requested_by: actor === 'buyer_cancel' ? 'BUYER' : actor === 'seller_fault' ? 'SELLER' : 'ADMIN',
  });
}

// ── 환불 미리보기 ─────────────────────────────────────
export async function refundPreview(page: Page, resId: number, actor: string = 'buyer_cancel') {
  return api(page, 'POST', '/v3_6/reservations/refund/preview', {
    reservation_id: resId,
    actor,
  });
}

// ── Setup: 전체 테스트 데이터 초기화 ───────────────────
export async function setupAll(page: Page) {
  await page.goto(BASE);

  // 1. Admin login
  const adminRes = await loginForm(page, 'admin@yeokping.com', 'admin1234!');
  state.adminToken = adminRes.token;
  console.log(`[Setup] admin: ${adminRes.status}`);

  // 2. Buyer login or register
  const buyerLogin = await loginForm(page, 'realtest1@e2e.com', 'Test1234!');
  if (buyerLogin.status === 200) {
    state.buyerToken = buyerLogin.token;
  } else {
    await setToken(page, '');
    const reg = await socialRegister(page, {
      socialId: `buyer_stress_${TS}`, role: 'buyer',
      nickname: `스트레스바이어${TS % 10000}`, email: 'realtest1@e2e.com',
    });
    state.buyerToken = reg.data?.access_token || '';
  }
  if (state.buyerToken) {
    const info = await tokenInfo(page, state.buyerToken);
    state.buyerId = Number(info.sub || 0);
  }
  console.log(`[Setup] buyer: ${state.buyerId}`);

  // 3. Seller — always create fresh with unique email
  await setToken(page, '');
  const sellerEmail = `stressseller_${TS}@test.com`;
  const sellerReg = await socialRegister(page, {
    socialId: `seller_stress_${TS}`, role: 'seller',
    nickname: `스트레스셀러${TS % 10000}`, email: sellerEmail,
    business_name: '스트레스상점', business_number: `${TS}1`,
  });
  state.sellerToken = sellerReg.data?.access_token || '';
  state.sellerEmail = sellerEmail;
  if (state.sellerToken) {
    const info = await tokenInfo(page, state.sellerToken);
    state.sellerId = Number(info.seller_id || info.sub || 0);
    await approveSeller(page, state.adminToken, state.sellerId);
  } else {
    console.log(`[Setup] seller reg failed: ${JSON.stringify(sellerReg)}`);
  }
  console.log(`[Setup] seller: ${state.sellerId}`);

  // 4. 2nd stress seller
  await setToken(page, '');
  const s2Reg = await socialRegister(page, {
    socialId: `stress2_${TS}`, role: 'seller',
    nickname: `스트레스2_${TS % 10000}`, email: `stressseller2_${TS}@test.com`,
    business_name: '스트레스상점2', business_number: `${TS}2`,
  });
  if (s2Reg.data?.access_token) {
    state.seller2Token = s2Reg.data.access_token;
    const info = await tokenInfo(page, state.seller2Token);
    state.seller2Id = Number(info.seller_id || info.sub || 0);
    await approveSeller(page, state.adminToken, state.seller2Id);
  }
  console.log(`[Setup] seller2: ${state.seller2Id}`);

  // 5. Create 5 deals
  await setToken(page, state.buyerToken);
  const dealDefs = [
    { name: '갤럭시 S25 울트라', target: 1000000, anchor: 1200000, qty: 20 },
    { name: '에어팟 프로 2', target: 250000, anchor: 300000, qty: 30 },
    { name: '다이슨 에어랩', target: 400000, anchor: 500000, qty: 15 },
    { name: 'PS5 프로', target: 600000, anchor: 700000, qty: 20 },
    { name: '오뚜기 진라면 40개', target: 20000, anchor: 25000, qty: 50 },
  ];
  for (const d of dealDefs) {
    const r = await createDeal(page, d.name, d.target, d.anchor, d.qty);
    if (r.data?.id) state.dealIds.push(r.data.id);
    else console.log(`[Setup] deal create fail: ${JSON.stringify(r)}`);
  }
  console.log(`[Setup] deals: ${JSON.stringify(state.dealIds)}`);

  // 6. Seller creates offers on all deals
  await setToken(page, state.sellerToken);
  const prices = [950000, 240000, 380000, 580000, 18000];
  for (let i = 0; i < state.dealIds.length; i++) {
    const r = await createOffer(page, state.dealIds[i], state.sellerId, prices[i]);
    if (r.data?.id) state.offerIds.push(r.data.id);
  }
  console.log(`[Setup] offers: ${JSON.stringify(state.offerIds)}`);

  // 7. Buyer creates & pays 15 reservations (3 per deal)
  await setToken(page, state.buyerToken);
  for (let i = 0; i < state.dealIds.length; i++) {
    if (!state.offerIds[i]) continue;
    for (let q = 0; q < 3; q++) {
      await createAndPayReservation(page, state.dealIds[i], state.offerIds[i], prices[i]);
    }
  }
  console.log(`[Setup] reservations: ${state.resIds.length}, paid: ${state.paidResIds.length}`);
  console.log('[Setup] COMPLETE');
}

// ── 딜 정보 ───────────────────────────────────────────
export const DEAL_DEFS = [
  { name: '갤럭시 S25 울트라', target: 1000000, price: 950000 },
  { name: '에어팟 프로 2', target: 250000, price: 240000 },
  { name: '다이슨 에어랩', target: 400000, price: 380000 },
  { name: 'PS5 프로', target: 600000, price: 580000 },
  { name: '오뚜기 진라면 40개', target: 20000, price: 18000 },
];
