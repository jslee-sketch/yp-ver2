// scripts/e2e/lib/factory.mjs
import { req, login as doLogin, sellerLogin, uniqueEmail, uniqueName, sleep } from './client.mjs';

export const state = {
  buyers: [],     // { id, email, password, token, name }
  sellers: [],    // { id, email, password, token, business_name }
  deals: [],
  offers: [],
  reservations: [],
  participants: [],
};

// 15자 이하, 타임스탬프 포함 고유 닉네임
export function uniqueNickname(prefix = 'U') {
  const ts = Date.now().toString(36);      // ~8자
  const rand = Math.random().toString(36).slice(2, 5); // 3자
  return `${prefix}${ts}${rand}`.slice(0, 15);
}

// ── getExistingBuyer ──────────────────────────────────────
// state.buyers에서 기존 구매자 반환 (섹션 간 공유 state 활용)
export function getExistingBuyer() {
  if (state.buyers.length === 0) return null;
  // 토큰이 있는 buyer 우선
  const withToken = state.buyers.filter(b => b.token && b.id);
  if (withToken.length > 0) return withToken[Math.floor(Math.random() * withToken.length)];
  return state.buyers[0] || null;
}

// ── getExistingSeller ──────────────────────────────────────
// DB에서 기존 승인된 seller 반환 (verified_at != null)
// 빈 결과는 캐시하지 않음 → 재시도 허용
let _cachedSellers = null;

export async function getExistingSeller() {
  // 캐시가 없거나 비어 있으면 재조회 (최대 3회 재시도)
  if (!_cachedSellers || _cachedSellers.length === 0) {
    for (let attempt = 0; attempt < 3; attempt++) {
      const res = await req('GET', '/sellers/?skip=0&limit=100');
      if (res.ok && Array.isArray(res.data)) {
        const filtered = res.data.filter(s => s.id && s.verified_at); // 승인된 seller만
        if (filtered.length > 0) {
          _cachedSellers = filtered;
          break;
        }
      }
      if (attempt < 2) await sleep(1000 * (attempt + 1));
    }
    if (!_cachedSellers || _cachedSellers.length === 0) {
      // state.sellers에서 fallback
      if (state.sellers.length > 0) {
        return state.sellers.find(s => s.id) || null;
      }
      return null;
    }
  }
  // 랜덤 선택
  const s = _cachedSellers[Math.floor(Math.random() * _cachedSellers.length)];
  return {
    id: s.id || s.seller_id,
    email: s.email,
    token: null,  // DB 조회 fallback — 토큰 없음 (sellerLogin으로 취득 필요 시 별도 호출)
    business_name: s.business_name || s.company_name || s.nickname || `Seller-${s.id}`,
  };
}

// ── createBuyer ────────────────────────────────────────────
export async function createBuyer(namePrefix = 'B') {
  await sleep(200); // rate limit 대응
  const email = uniqueEmail();
  const password = 'Test1234!';
  const name = uniqueNickname(namePrefix);
  // 429 rate limit 시 최대 3회 재시도
  let regRes;
  for (let attempt = 0; attempt < 3; attempt++) {
    regRes = await req('POST', '/buyers/', { email, password, name, nickname: name });
    if (regRes.ok || regRes.status === 201) break;
    if (regRes.status === 429) {
      console.log(`  ℹ createBuyer rate limited, retry ${attempt + 1}/3 after 3s...`);
      await sleep(3000 * (attempt + 1));
    } else {
      break;
    }
  }
  if (!regRes.ok && regRes.status !== 201) {
    console.error(`  ⚠ createBuyer 가입 실패: status=${regRes.status}`);
    // ✅ 핵심 fallback: state에 있는 기존 구매자 재사용
    const existing = getExistingBuyer();
    if (existing) {
      console.log(`  ℹ createBuyer fallback → state buyer id=${existing.id}`);
      return existing;
    }
    return null;
  }
  const loginRes = await doLogin(email, password);
  if (!loginRes.ok || !loginRes.data?.access_token) {
    console.error(`  ⚠ createBuyer 로그인 실패: status=${loginRes.status}`);
    return null;
  }
  const buyer = {
    id: regRes.data?.id,
    email, password,
    token: loginRes.data.access_token,
    name,
  };
  state.buyers.push(buyer);
  return buyer;
}

// ── createSeller ───────────────────────────────────────────
// /auth/login 은 Buyer 테이블만 조회 → seller 로그인 항상 401
// 생성 실패 시 DB에 있는 기존 승인된 seller 사용 (fallback)
export async function createSeller(namePrefix = 'S') {
  await sleep(200);
  const email = uniqueEmail();
  const password = 'Test1234!';
  const biz = uniqueNickname(namePrefix);
  const bizNum = `${Math.floor(100 + Math.random() * 900)}-${Math.floor(10 + Math.random() * 90)}-${Math.floor(10000 + Math.random() * 90000)}`;

  // 429 rate limit 시 최대 3회 재시도
  let regRes;
  for (let attempt = 0; attempt < 3; attempt++) {
    regRes = await req('POST', '/sellers/', {
      email, password,
      business_name: biz,
      nickname: biz,
      business_number: bizNum,
      phone: '010-0000-0000',
      address: '서울시 강남구 테헤란로 1',
      zip_code: '06234',
      established_date: '2020-01-01T00:00:00',
    });
    if (regRes.ok || regRes.status === 201) break;
    if (regRes.status === 429) {
      console.log(`  ℹ createSeller rate limited, retry ${attempt + 1}/3 after ${3 * (attempt + 1)}s...`);
      await sleep(3000 * (attempt + 1));
    } else {
      break;
    }
  }

  if (regRes.ok || regRes.status === 201) {
    const sellerId = regRes.data?.id || regRes.data?.seller_id;
    if (sellerId) {
      // 승인 시도
      await req('POST', `/sellers/${sellerId}/approve`);

      // seller 로그인 → 토큰 취득
      const loginRes = await sellerLogin(email, password);
      const token = (loginRes.ok && loginRes.data?.access_token) ? loginRes.data.access_token : null;
      if (!token) console.warn(`  ⚠ createSeller 로그인 실패: status=${loginRes.status}`);

      const seller = { id: sellerId, email, password, token, business_name: biz };
      state.sellers.push(seller);
      return seller;
    }
  }

  // ✅ 핵심 fallback: 실패 시 DB에서 기존 승인 seller 사용
  console.log(`  ℹ seller 생성 실패(${regRes.status}), 기존 DB seller 사용`);
  const existing = await getExistingSeller();
  if (existing) {
    state.sellers.push(existing);
    return existing;
  }

  console.error(`  ⚠ seller 생성 실패 + 기존 seller 없음`);
  return null;
}

// ── createDeal ─────────────────────────────────────────────
export async function createDeal(buyer, overrides = {}) {
  if (!buyer?.id) return null;
  await sleep(80);
  const data = {
    product_name: uniqueName('Product'),
    desired_qty: 50,
    target_price: 279000,
    creator_id: buyer.id,
    ...overrides,
  };
  // 429 rate limit 시 최대 3회 재시도
  let r;
  for (let attempt = 0; attempt < 3; attempt++) {
    r = await req('POST', '/deals/', data, buyer.token);
    if (r.ok || r.status === 201) break;
    if (r.status === 429) {
      console.log(`  ℹ createDeal rate limited, retry ${attempt + 1}/3 after ${3 * (attempt + 1)}s...`);
      await sleep(3000 * (attempt + 1));
    } else {
      break;
    }
  }
  if (!r.ok && r.status !== 201) {
    console.error(`  ⚠ createDeal 실패: ${r.status}`);
    // fallback: state에 있는 기존 딜 재사용
    if (state.deals.length > 0) {
      const existing = state.deals.find(d => d.id);
      if (existing) {
        console.log(`  ℹ createDeal fallback → state deal id=${existing.id}`);
        return existing;
      }
    }
    return null;
  }
  const deal = { id: r.data?.id, ...data };
  state.deals.push(deal);
  return deal;
}

// ── createOffer ────────────────────────────────────────────
// OfferCreate 필수: price, total_available_qty, deal_id, seller_id
// ⚠️ shipping_mode: "INCLUDED" 기본값 필수 (없으면 NONE → 422 에러)
export async function createOffer(seller, dealId, overrides = {}) {
  if (!seller?.id || !dealId) return null;
  await sleep(80);
  const data = {
    deal_id: dealId,
    seller_id: seller.id,
    price: 265000,
    total_available_qty: 100,
    shipping_mode: 'INCLUDED',   // ← 반드시 필요
    ...overrides,
  };
  // seller.token이 null이어도 OK (토큰 없이도 오퍼 생성 가능)
  const r = await req('POST', '/offers', data, seller.token);
  if (!r.ok && r.status !== 201) {
    console.error(`  ⚠ createOffer 실패: ${r.status}, ${JSON.stringify(r.data)?.slice(0, 150)}`);
    return null;
  }
  const offer = { id: r.data?.id, price: data.price, ...data };
  state.offers.push(offer);
  return offer;
}

// ── addParticipant ─────────────────────────────────────────
// DealParticipantCreate 필수: deal_id, buyer_id, qty
export async function addParticipant(buyer, dealId, qty = 2) {
  if (!buyer?.id || !dealId) return null;
  await sleep(80);
  const r = await req('POST', `/deals/${dealId}/participants`, {
    deal_id: dealId,
    buyer_id: buyer.id,
    qty,
  }, buyer.token);
  if (!r.ok && r.status !== 201) {
    console.error(`  ⚠ addParticipant 실패: ${r.status}, ${JSON.stringify(r.data)?.slice(0, 150)}`);
    return null;
  }
  const p = { id: r.data?.id, deal_id: dealId, buyer_id: buyer.id, qty };
  state.participants.push(p);
  return p;
}

// ── createReservation ──────────────────────────────────────
export async function createReservation(buyer, dealId, offerId, qty = 1) {
  if (!buyer?.id || !dealId || !offerId) return null;
  await sleep(80);
  const r = await req('POST', '/reservations', {
    deal_id: dealId, offer_id: offerId, buyer_id: buyer.id, qty,
  }, buyer.token);
  if (!r.ok && r.status !== 201) return null;
  const resv = { id: r.data?.id, deal_id: dealId, offer_id: offerId, buyer_id: buyer.id, qty };
  state.reservations.push(resv);
  return resv;
}

// ── payReservation ─────────────────────────────────────────
// POST /reservations/pay  { reservation_id, buyer_id, paid_amount }
export async function payReservation(resv, buyer, offerPrice = null) {
  if (!resv?.id || !buyer?.id) return { ok: false, status: 400, data: null };
  const paid_amount = offerPrice != null ? offerPrice * (resv.qty || 1) : 100000;
  return req('POST', '/reservations/pay', {
    reservation_id: resv.id,
    buyer_id: buyer.id,
    paid_amount,
  }, buyer.token);
}

// ── shipReservation ────────────────────────────────────────
// POST /reservations/{id}/mark_shipped  { seller_id, tracking_number, shipping_carrier }
export async function shipReservation(resv, seller, trackingNumber = 'TRACK001') {
  if (!resv?.id || !seller?.id) return { ok: false, status: 400, data: null };
  return req('POST', `/reservations/${resv.id}/mark_shipped`, {
    seller_id: seller.id,
    tracking_number: trackingNumber,
    shipping_carrier: 'CJ대한통운',
  }, seller.token);
}

// ── confirmArrival ─────────────────────────────────────────
// POST /reservations/{id}/arrival_confirm  { buyer_id }
export async function confirmArrival(resv, buyer) {
  if (!resv?.id || !buyer?.id) return { ok: false, status: 400, data: null };
  return req('POST', `/reservations/${resv.id}/arrival_confirm`, {
    buyer_id: buyer.id,
  }, buyer.token);
}

// ── cancelReservation ──────────────────────────────────────
// POST /reservations/cancel  { reservation_id }
export async function cancelReservation(resv, buyer) {
  if (!resv?.id) return { ok: false, status: 400, data: null };
  return req('POST', '/reservations/cancel', {
    reservation_id: resv.id,
  }, buyer?.token);
}
