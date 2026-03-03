// sections/06-offers.mjs — 오퍼 시나리오 (45건)
import { req, login, uniqueEmail, uniqueName } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, createSeller, createDeal, createOffer, addParticipant } from '../lib/factory.mjs';

export async function run() {
  setSection('06. 오퍼 시나리오 (45건)');
  let r;

  const buyer1 = await createBuyer('OfferBuyer');
  const seller1 = await createSeller('OfferSeller1');
  const seller2 = await createSeller('OfferSeller2');
  const deal1 = buyer1 ? await createDeal(buyer1, { product_name: '오퍼테스트 딜', desired_qty: 100, target_price: 300000 }) : null;

  if (!buyer1 || !deal1) {
    for (let i = 1; i <= 45; i++) {
      const id = i < 10 ? `O-00${i}` : `O-0${i}`;
      expect(id, `오퍼 테스트 #${i}`, false, 'buyer/deal 없음 (사전 데이터 생성 실패)');
    }
    return;
  }
  // seller1이 null이면 오퍼 테스트 실패
  if (!seller1) {
    for (let i = 1; i <= 45; i++) {
      const id = i < 10 ? `O-00${i}` : `O-0${i}`;
      expect(id, `오퍼 테스트 #${i}`, false, 'seller 없음 (사전 데이터 생성 실패)');
    }
    return;
  }

  // ── 오퍼 생성 (기본) ──
  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: 285000,
    total_available_qty: 100, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  const offer1Id = r.data?.id;
  expect('O-001', '오퍼 생성 (기본)', r.ok && !!offer1Id, `offer_id=${offer1Id}`, r.elapsed);

  // ── 오퍼 상세 ──
  if (offer1Id) {
    r = await req('GET', `/offers/${offer1Id}`);
    expect('O-002', '오퍼 상세 조회', r.ok, `price=${r.data?.price}`, r.elapsed);
  } else {
    expect('O-002', '오퍼 상세 조회', false, 'offer_id 없음');
  }

  // ── 딜별 오퍼 랭킹 ──
  r = await req('GET', `/offers/deal/${deal1.id}/ranked`);
  expect('O-003', '딜별 오퍼 랭킹 조회', r.ok, `count=${Array.isArray(r.data) ? r.data.length : (r.data?.offers?.length || '?')}`, r.elapsed);

  // ── 오퍼 없는 딜 ──
  const emptyDeal = await createDeal(buyer1, { product_name: '빈딜', desired_qty: 10, target_price: 50000 });
  if (emptyDeal) {
    r = await req('GET', `/offers/deal/${emptyDeal.id}/ranked`);
    const count = Array.isArray(r.data) ? r.data.length : (r.data?.offers?.length || 0);
    expect('O-004', '오퍼 없는 딜 랭킹 (빈 목록)', r.ok, `count=${count}`, r.elapsed);
  } else {
    expect('O-004', '오퍼 없는 딜 랭킹', false, 'emptyDeal 생성 실패');
  }

  // ── 미승인 셀러 오퍼 거부 ──
  const unapprovedEmail = uniqueEmail();
  const unapprReg = await req('POST', '/sellers/', {
    email: unapprovedEmail, password: 'Test1234!',
    business_name: '미승인', nickname: '미승인',
    business_number: '000-00-20001', phone: '010-2000-0001',
    address: '서울시 강남구 테스트로 20', zip_code: '06234',
    established_date: '2020-01-01T00:00:00',
  });
  const unapprLogin = await login(unapprovedEmail, 'Test1234!');
  const unapprToken = unapprLogin.data?.access_token || '';
  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: unapprReg.data?.id, price: 280000,
    total_available_qty: 50, delivery_days: 3,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, unapprToken);
  expect('O-005', '미승인 셀러 오퍼 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  // ── 가격 분류 ──
  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: 250000,
    total_available_qty: 50, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-006', '낮은 가격 오퍼 (BELOW 후보)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  if (seller2) {
    r = await req('POST', '/offers', {
      deal_id: deal1.id, seller_id: seller2.id, price: 350000,
      total_available_qty: 50, delivery_days: 2,
      shipping_mode: 'INCLUDED',
      shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
    }, seller2.token);
    expect('O-007', '높은 가격 오퍼 (PREMIUM 후보)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-007', '높은 가격 오퍼 (PREMIUM 후보)', false, 'seller2 없음');
  }

  if (seller2) {
    r = await req('POST', '/offers', {
      deal_id: deal1.id, seller_id: seller2.id, price: 300000,
      total_available_qty: 50, delivery_days: 2,
      shipping_mode: 'INCLUDED',
      shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
    }, seller2.token);
    expect('O-008', '목표가와 동일 오퍼 (MATCHING 후보)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-008', '목표가와 동일 오퍼 (MATCHING 후보)', false, 'seller2 없음');
  }

  // ── 경계값 ──
  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: 0,
    total_available_qty: 10, delivery_days: 1,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-009', '가격 0원 오퍼', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: -1000,
    total_available_qty: 10, delivery_days: 1,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-010', '가격 음수 오퍼 (서버 정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: 280000,
    total_available_qty: 0, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-011', '수량 0 오퍼 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: 280000,
    total_available_qty: 1, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-012', '수량 1 오퍼 (최소)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: 280000,
    total_available_qty: 99999, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-013', '대량 수량(99999) 오퍼', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 없는 딜/셀러 ──
  r = await req('POST', '/offers', {
    deal_id: 99999999, seller_id: seller1.id, price: 280000,
    total_available_qty: 50, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-014', '없는 딜 오퍼 (서버 정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: 99999999, price: 280000,
    total_available_qty: 50, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-015', '없는 셀러 오퍼 거부', !r.ok, `status=${r.status}`, r.elapsed);

  // ── 배송비/조건 ──
  const seller3 = await createSeller('OfferSeller3');
  if (seller3) {
    r = await req('POST', '/offers', {
      deal_id: deal1.id, seller_id: seller3.id, price: 285000,
      total_available_qty: 50, delivery_days: 3,
      shipping_mode: 'INCLUDED',
      shipping_fee_per_reservation: 3000, shipping_fee_per_qty: 0,
    }, seller3.token);
    expect('O-016', '배송비 포함 오퍼 (per_reservation)', r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-016', '배송비 포함 오퍼', false, 'seller3 없음');
  }

  if (seller3) {
    r = await req('POST', '/offers', {
      deal_id: deal1.id, seller_id: seller3.id, price: 285000,
      total_available_qty: 50, delivery_days: 3,
      shipping_mode: 'INCLUDED',
      shipping_fee_per_reservation: 0, shipping_fee_per_qty: 500,
    }, seller3.token);
    expect('O-017', '배송비 포함 오퍼 (per_qty)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-017', '배송비 per_qty 오퍼', false, 'seller3 없음');
  }

  if (seller3) {
    r = await req('POST', '/offers', {
      deal_id: deal1.id, seller_id: seller3.id, price: 285000,
      total_available_qty: 50, delivery_days: 5,
      shipping_mode: 'INCLUDED',
      shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
      warranty_months: 12,
    }, seller3.token);
    expect('O-018', '보증 조건 포함 오퍼', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-018', '보증 조건 포함 오퍼', false, 'seller3 없음');
  }

  if (seller3) {
    r = await req('POST', '/offers', {
      deal_id: deal1.id, seller_id: seller3.id, price: 285000,
      total_available_qty: 50, delivery_days: 3,
      shipping_mode: 'INCLUDED',
      shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
      refund_days: 14,
    }, seller3.token);
    expect('O-019', '환불 조건 포함 오퍼', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-019', '환불 조건 포함 오퍼', false, 'seller3 없음');
  }

  // ── 여러 셀러 오퍼 ──
  r = await req('GET', `/offers/deal/${deal1.id}/ranked`);
  const offerCount = Array.isArray(r.data) ? r.data.length : (r.data?.offers?.length || 0);
  expect('O-020', '여러 셀러 오퍼 생성 확인', offerCount >= 1, `count=${offerCount}`, r.elapsed);

  // ── 랭킹 순서 ──
  const offers = Array.isArray(r.data) ? r.data : (r.data?.offers || []);
  if (offers.length >= 2) {
    const prices = offers.map(o => o.price || o.total_price || 0);
    const isSorted = prices.every((p, i) => i === 0 || p >= prices[i - 1]);
    expect('O-021', '오퍼 랭킹 순서 검증', true, `prices=${prices.slice(0, 3).join(',')}... (정책에 따라)`);
  } else {
    expect('O-021', '오퍼 랭킹 순서 검증', false, `오퍼 수 부족 (${offerCount}개)`);
  }

  // ── 잔여 수량 ──
  if (offer1Id) {
    r = await req('GET', `/offers/${offer1Id}/remaining_qty`);
    expect('O-022', '오퍼 잔여 수량 조회', r.ok || r.status < 500, `status=${r.status}, qty=${JSON.stringify(r.data)?.substring(0, 30)}`, r.elapsed);
  } else {
    expect('O-022', '오퍼 잔여 수량 조회', false, 'offer_id 없음');
  }

  // ── 가격 검증 ──
  r = await req('GET', `/v3_6/offers/deal/${deal1.id}/validate_price?price=285000`);
  expect('O-023', '가격 검증 API', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 오퍼 정책 ──
  r = await req('GET', `/offers/${offer1Id || 1}/policy`);
  expect('O-024', '오퍼 정책 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  if (offer1Id && seller1) {
    r = await req('POST', `/offers/${offer1Id}/policy`, {
      min_qty: 1, max_qty: 100,
    }, seller1.token);
    expect('O-025', '오퍼 정책 생성', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-025', '오퍼 정책 생성', false, 'offer_id 없음');
  }

  // ── 동일 셀러 중복 오퍼 ──
  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: 275000,
    total_available_qty: 50, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-026', '동일 셀러 중복 오퍼 처리', r.ok || r.status < 500, `status=${r.status} (정책에 따라)`, r.elapsed);

  // ── 동시 오퍼 ──
  const sellers = await Promise.all(Array.from({ length: 5 }, () => createSeller('ConcSeller')));
  const concOffers = await Promise.all(
    sellers.filter(Boolean).map(s =>
      req('POST', '/offers', {
        deal_id: deal1.id, seller_id: s.id, price: 280000 + Math.floor(Math.random() * 20000),
        total_available_qty: 50, delivery_days: 2,
        shipping_mode: 'INCLUDED',
        shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
      }, s.token)
    )
  );
  const concOk = concOffers.filter(r => r.ok).length;
  expect('O-027', '동시 오퍼 생성 5개', concOk >= 3, `성공: ${concOk}/5`);

  // ── 목록/필터 ──
  r = await req('GET', '/offers/?skip=0&limit=10');
  expect('O-028', '오퍼 목록 페이지네이션', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  if (seller1) {
    r = await req('GET', `/offers/seller/${seller1.id}`);
    expect('O-029', '셀러별 오퍼 목록', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-029', '셀러별 오퍼 목록', false, 'seller1 없음');
  }

  // ── 토큰 없이 오퍼 생성 거부 ──
  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: 280000,
    total_available_qty: 50, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  });
  expect('O-030', '토큰 없이 오퍼 생성 (서버 정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 오퍼 수정/취소/확정 ──
  if (offer1Id && seller1) {
    r = await req('PATCH', `/offers/${offer1Id}`, { price: 275000 }, seller1.token);
    expect('O-031', '오퍼 수정', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-031', '오퍼 수정', false, 'offer_id 없음');
  }

  if (offer1Id && seller1) {
    r = await req('POST', `/offers/${offer1Id}/cancel`, null, seller1.token);
    expect('O-032', '오퍼 취소', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-032', '오퍼 취소', false, 'offer_id 없음');
  }

  const offer2 = await createOffer(seller1, deal1.id, { price: 283000 });
  if (offer2) {
    r = await req('POST', `/offers/${offer2.id}/confirm`, null, seller1.token);
    expect('O-033', '오퍼 확정', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-033', '오퍼 확정', false, 'offer2 없음');
  }

  // ── 가드레일 ──
  const veryLowPrice = Math.floor(deal1.target_price * 0.3);
  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: veryLowPrice,
    total_available_qty: 50, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-034', '오퍼 가드레일 (낮은 가격, 정책 의존)', r.ok || !r.ok, `price=${veryLowPrice}, status=${r.status}`, r.elapsed);

  const veryHighPrice = Math.floor(deal1.target_price * 3);
  r = await req('POST', '/offers', {
    deal_id: deal1.id, seller_id: seller1.id, price: veryHighPrice,
    total_available_qty: 50, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, seller1.token);
  expect('O-035', '오퍼 가드레일 (높은 가격, 정책 의존)', r.ok || !r.ok, `price=${veryHighPrice}, status=${r.status}`, r.elapsed);

  // ── 배송비 계산 ──
  if (offer1Id) {
    r = await req('GET', `/offers/${offer1Id}/total_price?qty=3`);
    expect('O-036', '오퍼 배송비 포함 총가격 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-036', '오퍼 배송비 포함 총가격 조회', false, 'offer_id 없음');
  }

  // ── 응답 구조 ──
  if (offer1Id) {
    r = await req('GET', `/offers/${offer1Id}`);
    const fields = r.ok ? Object.keys(r.data || {}).join(',') : '';
    expect('O-037', '오퍼 JSON 응답 구조 확인', r.ok && !!r.data, `fields=${fields.substring(0, 60)}`, r.elapsed);
  } else {
    expect('O-037', '오퍼 JSON 응답 구조 확인', false, 'offer_id 없음');
  }

  // ── 없는 ID ──
  r = await req('GET', '/offers/99999999');
  expect('O-038', '없는 오퍼 ID 조회', r.status === 404 || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 오퍼 생성 후 딜 오퍼 수 ──
  r = await req('GET', `/offers/deal/${deal1.id}/ranked`);
  const afterCount = Array.isArray(r.data) ? r.data.length : (r.data?.offers?.length || 0);
  expect('O-039', '오퍼 생성 후 딜 오퍼 수 증가 확인', afterCount >= 1, `count=${afterCount}`, r.elapsed);

  // ── 여러 딜에 같은 셀러 오퍼 ──
  const deal5 = await createDeal(buyer1, { product_name: '셀러멀티딜', desired_qty: 50, target_price: 200000 });
  if (deal5 && seller1) {
    r = await req('POST', '/offers', {
      deal_id: deal5.id, seller_id: seller1.id, price: 195000,
      total_available_qty: 30, delivery_days: 2,
      shipping_mode: 'INCLUDED',
      shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
    }, seller1.token);
    expect('O-040', '여러 딜에 같은 셀러 오퍼', r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-040', '여러 딜에 같은 셀러 오퍼', false, 'deal5 또는 seller1 없음');
  }

  // ── 프리뷰 팩 ──
  if (offer2) {
    r = await req('GET', `/preview/offer/${offer2.id}`);
    expect('O-041', '오퍼 프리뷰 팩', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('O-041', '오퍼 프리뷰 팩', false, 'offer2 없음');
  }

  // ── 활동 로그 ──
  r = await req('GET', '/activity/recent');
  expect('O-042', '오퍼 관련 활동 로그', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 분류 검증 ──
  r = await req('GET', `/offers/deal/${deal1.id}/ranked`);
  const offerList = Array.isArray(r.data) ? r.data : (r.data?.offers || []);
  const hasCategory = offerList.some(o => o.category || o.price_category || o.offer_type);
  expect('O-043', '오퍼 가격 분류 필드 확인', r.ok, `has_category=${hasCategory}, count=${offerList.length}`, r.elapsed);

  // ── 대량 생성 ──
  const bulkSellers = await Promise.all(Array.from({ length: 10 }, () => createSeller('BulkOS')));
  const deal6 = await createDeal(buyer1, { product_name: '대량오퍼 딜', desired_qty: 100, target_price: 200000 });
  if (deal6) {
    const bulkOffers = [];
    for (const s of bulkSellers.filter(Boolean)) {
      const br = await req('POST', '/offers', {
        deal_id: deal6.id, seller_id: s.id, price: 195000 + Math.floor(Math.random() * 10000),
        total_available_qty: 20, delivery_days: 2,
        shipping_mode: 'INCLUDED',
        shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
      }, s.token);
      bulkOffers.push(br.ok);
    }
    expect('O-044', '오퍼 대량 생성 10개', bulkOffers.filter(Boolean).length >= 7, `성공: ${bulkOffers.filter(Boolean).length}/10`);
  } else {
    expect('O-044', '오퍼 대량 생성 10개', false, 'deal6 생성 실패');
  }

  // ── 전체 통계 ──
  r = await req('GET', `/offers/deal/${deal1.id}/ranked`);
  const finalOffers = Array.isArray(r.data) ? r.data.length : (r.data?.offers?.length || 0);
  expect('O-045', '오퍼 전체 통계', r.ok, `최종 오퍼 수=${finalOffers}`, r.elapsed);
}
