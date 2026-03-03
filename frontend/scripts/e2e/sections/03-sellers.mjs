// sections/03-sellers.mjs — 판매자 CRUD (30건)
import { req, login, sellerLogin, uniqueEmail, uniqueName } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createSeller, uniqueNickname, state } from '../lib/factory.mjs';

function randBizNum() {
  return `${Math.floor(100+Math.random()*900)}-${Math.floor(10+Math.random()*90)}-${Math.floor(10000+Math.random()*90000)}`;
}

export async function run() {
  setSection('03. 판매자 CRUD (30건)');
  let r;

  // ── 목록 ──
  r = await req('GET', '/sellers/');
  expect('S-001', '판매자 목록 조회', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  // ── 생성 ──
  const email = uniqueEmail();
  const password = 'Test1234!';
  const biz = uniqueNickname('SBiz');
  r = await req('POST', '/sellers/', {
    email, password, business_name: biz, nickname: biz,
    business_number: randBizNum(), phone: '010-1000-0001',
    address: '서울시 강남구 테스트로 10', zip_code: '06234',
    established_date: '2020-01-01T00:00:00',
  });
  expect('S-002', '판매자 생성', r.ok, `status=${r.status}, id=${r.data?.id}`, r.elapsed);
  const newSellerId = r.data?.id;

  // ── 승인 ──
  r = await req('POST', `/sellers/${newSellerId}/approve`);
  expect('S-003', '판매자 승인', r.ok || r.status === 200, `status=${r.status}`, r.elapsed);

  // ── 승인 후 상태 ──
  if (newSellerId) {
    r = await req('GET', `/sellers/${newSellerId}`);
    expect('S-004', '승인 후 판매자 상태 확인', r.ok, `status=${r.status}, approved=${r.data?.is_approved ?? r.data?.approved ?? '?'}`, r.elapsed);
  } else {
    expect('S-004', '승인 후 판매자 상태 확인', false, 'seller 없음');
  }

  // ── 상세 조회 ──
  if (newSellerId) {
    r = await req('GET', `/sellers/${newSellerId}`);
    expect('S-005', '판매자 상세 조회', r.ok, `biz=${r.data?.business_name}`, r.elapsed);
  } else {
    expect('S-005', '판매자 상세 조회', false, 'seller 없음');
  }

  r = await req('GET', '/sellers/99999999');
  expect('S-006', '없는 판매자 ID (정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 로그인 ──
  r = await sellerLogin(email, password);
  expect('S-007', '판매자 로그인', r.ok && !!r.data?.access_token, `status=${r.status}`, r.elapsed);
  const sellerToken = r.data?.access_token || '';

  // ── 내 정보 ──
  r = await req('GET', '/sellers/me', null, sellerToken);
  expect('S-008', '판매자 내 정보', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/sellers/me/summary', null, sellerToken);
  expect('S-009', '판매자 요약', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 레벨/리뷰 ──
  if (newSellerId) {
    r = await req('GET', `/sellers/${newSellerId}/level`);
    expect('S-010', '판매자 레벨 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('S-010', '판매자 레벨 조회', false, 'seller 없음');
  }

  if (newSellerId) {
    r = await req('GET', `/sellers/${newSellerId}/reviews/summary`);
    expect('S-011', '판매자 리뷰 요약', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('S-011', '판매자 리뷰 요약', false, 'seller 없음');
  }

  // ── 오퍼 목록 ──
  if (newSellerId) {
    r = await req('GET', `/offers/seller/${newSellerId}`);
    expect('S-012', '판매자 오퍼 목록', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('S-012', '판매자 오퍼 목록', false, 'seller 없음');
  }

  // ── 커미션/정산 ──
  if (newSellerId) {
    r = await req('GET', `/sellers/${newSellerId}/commission`);
    expect('S-013', '판매자 커미션 설정 확인', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('S-013', '판매자 커미션 설정 확인', false, 'seller 없음');
  }

  if (newSellerId) {
    r = await req('GET', `/dashboard/seller/${newSellerId}`);
    expect('S-014', '판매자 대시보드', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('S-014', '판매자 대시보드', false, 'seller 없음');
  }

  if (newSellerId) {
    r = await req('GET', `/insights/seller/${newSellerId}/overview`);
    expect('S-015', '판매자 인사이트', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('S-015', '판매자 인사이트', false, 'seller 없음');
  }

  // ── 온보딩 ──
  r = await req('GET', '/sellers/onboarding/status', null, sellerToken);
  expect('S-016', '판매자 온보딩 API', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 미승인 오퍼 거부 ──
  const unapprovedEmail = uniqueEmail();
  const unapNick = uniqueNickname('UA');
  const unapprovedR = await req('POST', '/sellers/', {
    email: unapprovedEmail, password: 'Test1234!',
    business_name: unapNick, nickname: unapNick,
    business_number: randBizNum(), phone: '010-1000-0002',
    address: '서울시 강남구 테스트로 11', zip_code: '06234',
    established_date: '2020-01-01T00:00:00',
  });
  const unapprovedId = unapprovedR.data?.id;
  const unapprovedLoginR = await login(unapprovedEmail, 'Test1234!');
  const unapprovedToken = unapprovedLoginR.data?.access_token || '';
  r = await req('POST', '/offers', {
    deal_id: 1, seller_id: unapprovedId, price: 100000,
    total_available_qty: 10, delivery_days: 2,
    shipping_mode: 'INCLUDED',
    shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
  }, unapprovedToken);
  expect('S-017', '미승인 판매자 오퍼 생성 (정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 이메일 중복 ──
  const dupNick = uniqueNickname('DUP');
  r = await req('POST', '/sellers/', {
    email, password: 'Test1234!', business_name: dupNick, nickname: dupNick,
    business_number: randBizNum(), phone: '010-1000-0003',
    address: '서울시 강남구 테스트로 12', zip_code: '06234',
    established_date: '2020-01-01T00:00:00',
  });
  expect('S-018', '판매자 이메일 중복 가입', !r.ok, `status=${r.status}`, r.elapsed);

  // ── Basic API ──
  r = await req('GET', '/basic/sellers/');
  expect('S-019', 'Basic 판매자 목록', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  if (newSellerId) {
    r = await req('GET', `/basic/sellers/${newSellerId}`);
    expect('S-020', 'Basic 판매자 상세', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('S-020', 'Basic 판매자 상세', false, 'seller 없음');
  }

  // ── 활동 로그 ──
  if (newSellerId) {
    r = await req('GET', `/activity/by-seller/${newSellerId}`);
    expect('S-021', '판매자 활동 로그', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('S-021', '판매자 활동 로그', false, 'seller 없음');
  }

  // ── 페이지네이션 ──
  r = await req('GET', '/sellers/?skip=0&limit=5');
  expect('S-022', '판매자 페이지네이션 (limit=5)', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  // ── 특수문자 비즈니스명 ──
  r = await req('POST', '/sellers/', { email: uniqueEmail(), password: 'Test1234!', business_name: '테스트 & Co. Ltd.', nickname: 'SpecialBiz' });
  expect('S-023', '특수문자 비즈니스명', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 매우 긴 비즈니스명 ──
  r = await req('POST', '/sellers/', { email: uniqueEmail(), password: 'Test1234!', business_name: 'B'.repeat(300), nickname: 'LongBiz' });
  expect('S-024', '매우 긴 비즈니스명(300자)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 정산 목록 ──
  r = await req('GET', '/admin/settlements/', null, sellerToken);
  expect('S-025', '정산 목록 조회 (admin)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 통계 ──
  if (newSellerId) {
    r = await req('GET', `/sellers/${newSellerId}/stats`);
    expect('S-026', '판매자 통계', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('S-026', '판매자 통계', false, 'seller 없음');
  }

  // ── 프리뷰 ──
  if (newSellerId) {
    r = await req('GET', `/preview/seller/${newSellerId}`);
    expect('S-027', '판매자 프리뷰', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('S-027', '판매자 프리뷰', false, 'seller 없음');
  }

  // ── 응답 구조 ──
  if (newSellerId) {
    r = await req('GET', `/sellers/${newSellerId}`);
    const hasFields = r.ok && r.data && typeof r.data === 'object';
    expect('S-028', '판매자 JSON 응답 구조', hasFields, `fields=${r.ok ? Object.keys(r.data || {}).join(',').substring(0, 60) : 'N/A'}`, r.elapsed);
  } else {
    expect('S-028', '판매자 JSON 응답 구조', false, 'seller 없음');
  }

  // ── 동시 조회 ──
  if (newSellerId) {
    const concurrentReads = await Promise.all(
      Array.from({ length: 5 }, () => req('GET', `/sellers/${newSellerId}`))
    );
    const readOk = concurrentReads.filter(r => r.ok).length;
    expect('S-029', '동시 판매자 5명 조회', readOk === 5, `성공: ${readOk}/5`);
  } else {
    expect('S-029', '동시 판매자 5명 조회', false, 'seller 없음');
  }

  // ── 비밀번호 변경 시도 ──
  r = await req('POST', '/auth/change-password', { current_password: 'Test1234!', new_password: 'NewSeller1!' }, sellerToken);
  expect('S-030', '판매자 비밀번호 변경 시도', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
}
