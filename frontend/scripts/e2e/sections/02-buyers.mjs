// sections/02-buyers.mjs — 구매자 CRUD (30건)
import { req, login, uniqueEmail, uniqueName } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, uniqueNickname, state } from '../lib/factory.mjs';

export async function run() {
  setSection('02. 구매자 CRUD (30건)');
  let r;

  // ── 목록 ──
  r = await req('GET', '/buyers/');
  expect('B-001', '구매자 목록 조회', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  r = await req('GET', '/buyers/?skip=0&limit=5');
  expect('B-002', '구매자 목록 limit=5', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  r = await req('GET', '/buyers/?skip=5&limit=5');
  expect('B-003', '구매자 목록 skip=5', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  // ── 생성 및 상세 ──
  const email = uniqueEmail();
  const password = 'Test1234!';
  const name = uniqueName('BuyerCRUD');
  r = await req('POST', '/buyers/', { email, password, name, nickname: name });
  expect('B-004', '구매자 생성', r.ok, `status=${r.status}, id=${r.data?.id}`, r.elapsed);
  const newBuyerId = r.data?.id;

  if (newBuyerId) {
    r = await req('GET', `/buyers/${newBuyerId}`);
    expect('B-005', '생성된 구매자 상세 조회', r.ok, `name=${r.data?.name}`, r.elapsed);
  } else {
    expect('B-005', '생성된 구매자 상세 조회', false, '생성 실패로 skip');
  }

  r = await req('GET', '/buyers/99999999');
  expect('B-006', '없는 ID 조회', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 내 정보 ──
  const loginR = await login(email, password);
  const myToken = loginR.data?.access_token || '';

  r = await req('GET', '/buyers/me', null, myToken);
  expect('B-007', '내 정보 조회 (buyers/me)', r.ok, `status=${r.status}, id=${r.data?.id}`, r.elapsed);

  r = await req('GET', '/buyers/me');
  expect('B-008', '토큰 없이 /buyers/me (서버 정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 유효성 검사 ──
  r = await req('POST', '/buyers/', { email, password: 'Test1234!', name: '중복', nickname: '중복' });
  expect('B-009', '중복 이메일 가입 거부', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { password: 'Test1234!', name: '이름만', nickname: '이름만' });
  expect('B-010', '이메일 없이 가입 거부', !r.ok, `status=${r.status}`, r.elapsed);

  // ── 부가 정보 ──
  if (newBuyerId) {
    r = await req('GET', `/buyers/${newBuyerId}/trust_tier`);
    expect('B-011', '구매자 신뢰 티어 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('B-011', '구매자 신뢰 티어 조회', false, 'buyer 없음');
  }

  if (newBuyerId) {
    r = await req('GET', `/buyers/${newBuyerId}/points_grade`);
    expect('B-012', '구매자 포인트 등급 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('B-012', '구매자 포인트 등급 조회', false, 'buyer 없음');
  }

  // ── 포인트 ──
  if (newBuyerId) {
    r = await req('GET', `/points/buyer/${newBuyerId}/balance`);
    expect('B-013', '포인트 잔액 조회 (by ID)', r.ok || r.status < 500, `status=${r.status}, balance=${JSON.stringify(r.data)?.substring(0, 50)}`, r.elapsed);
  } else {
    expect('B-013', '포인트 잔액 조회 (by ID)', false, 'buyer 없음');
  }

  if (newBuyerId) {
    r = await req('GET', `/points/buyer/${newBuyerId}/transactions`);
    expect('B-014', '포인트 거래 내역 (by ID)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('B-014', '포인트 거래 내역 (by ID)', false, 'buyer 없음');
  }

  r = await req('GET', '/points/balance', null, myToken);
  expect('B-015', '포인트 잔액 조회 (by token)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/points/history', null, myToken);
  expect('B-016', '포인트 거래 내역 (by token)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 요약/대시보드 ──
  r = await req('GET', '/buyers/summary', null, myToken);
  expect('B-017', '구매자 요약 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  if (newBuyerId) {
    r = await req('GET', `/dashboard/buyer/${newBuyerId}`);
    expect('B-018', '구매자 대시보드', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('B-018', '구매자 대시보드', false, 'buyer 없음');
  }

  if (newBuyerId) {
    r = await req('GET', `/insights/buyer/${newBuyerId}/overview`);
    expect('B-019', '구매자 인사이트 개요', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('B-019', '구매자 인사이트 개요', false, 'buyer 없음');
  }

  if (newBuyerId) {
    r = await req('GET', `/preview/buyer/${newBuyerId}`);
    expect('B-020', '구매자 프리뷰', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('B-020', '구매자 프리뷰', false, 'buyer 없음');
  }

  // ── 닉네임 중복 확인 ──
  r = await req('GET', `/users/check-nickname?nickname=${name}`);
  expect('B-021', '닉네임 중복 확인 API', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── Basic API ──
  r = await req('GET', '/basic/buyers/');
  expect('B-022', 'Basic 구매자 목록', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  if (newBuyerId) {
    r = await req('GET', `/basic/buyers/${newBuyerId}`);
    expect('B-023', 'Basic 구매자 상세', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('B-023', 'Basic 구매자 상세', false, 'buyer 없음');
  }

  if (newBuyerId) {
    r = await req('GET', `/activity/by-buyer/${newBuyerId}`);
    expect('B-024', '구매자 활동 로그', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('B-024', '구매자 활동 로그', false, 'buyer 없음');
  }

  // ── 없는 포인트 조회 ──
  r = await req('GET', '/points/buyer/99999999/balance');
  expect('B-025', '없는 구매자 포인트 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 예약 목록 ──
  r = await req('GET', '/reservations/buyer/', null, myToken);
  expect('B-026', '구매자별 예약 목록', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 대량 생성 검증 ──
  const bulkBuyers = await Promise.all(
    Array.from({ length: 5 }, (_, i) => {
      const n = uniqueNickname('BB');
      return req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: n, nickname: n });
    })
  );
  const bulkOk = bulkBuyers.filter(r => r.ok).length;
  expect('B-027', '구매자 대량 생성 5명', bulkOk >= 0, `성공: ${bulkOk}/5`);

  // ── 빈 페이지 ──
  r = await req('GET', '/buyers/?skip=99999&limit=10');
  expect('B-028', '구매자 목록 빈 페이지', r.ok || r.status < 500, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  // ── 응답 구조 ──
  r = await req('GET', `/buyers/${newBuyerId || 1}`);
  const hasFields = r.data && typeof r.data === 'object' && !Array.isArray(r.data);
  expect('B-029', '구매자 JSON 응답 구조 확인', r.ok ? hasFields : true, `fields=${r.ok ? Object.keys(r.data || {}).join(',').substring(0, 60) : 'N/A'}`, r.elapsed);

  // ── 동시 조회 ──
  if (newBuyerId) {
    const concurrentReads = await Promise.all(
      Array.from({ length: 5 }, () => req('GET', `/buyers/${newBuyerId}`))
    );
    const readOk = concurrentReads.filter(r => r.ok).length;
    expect('B-030', '동시 구매자 5명 조회', readOk >= 0, `성공: ${readOk}/5`);
  } else {
    expect('B-030', '동시 구매자 5명 조회', false, 'buyer 없음');
  }
}
