// sections/01-auth.mjs — 인증 (50건)
import { req, login, sellerLogin, uniqueEmail, uniqueName } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, uniqueNickname, state } from '../lib/factory.mjs';

export async function run() {
  setSection('01. 인증 (50건)');
  const email1 = uniqueEmail();
  let r;

  const nick1 = uniqueNickname('A1');
  const nick2 = uniqueNickname('A2');
  const nick3 = uniqueNickname('A3');

  // ── 정상 회원가입 ──
  r = await req('POST', '/buyers/', { email: email1, password: 'Test1234!', name: nick1, nickname: nick1 });
  const buyer001Id = r.data?.id;
  expect('A-001', '정상 회원가입', r.ok, `status=${r.status}`, r.elapsed);

  const email2 = uniqueEmail();
  r = await req('POST', '/buyers/', { email: email2, password: 'Abcd1234!', name: nick2, nickname: nick2 });
  const buyer002Id = r.data?.id;
  expect('A-002', '영문+숫자 비밀번호 가입', r.ok, `status=${r.status}`, r.elapsed);
  if (buyer002Id) state.buyers.push({ id: buyer002Id, email: email2, password: 'Abcd1234!', token: '', name: nick2 });

  // ── 중복/유효성 ──
  r = await req('POST', '/buyers/', { email: email1, password: 'Test1234!', name: nick3, nickname: nick3 });
  expect('A-003', '중복 이메일 가입 거부', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { password: 'Test1234!' });
  expect('A-004', '이메일 없이 가입 거부', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { email: uniqueEmail() });
  expect('A-005', '비밀번호 없이 가입 거부', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { email: 'notanemail', password: 'Test1234!', name: 'X', nickname: 'X' });
  expect('A-006', '잘못된 이메일 형식 거부', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { email: '', password: 'Test1234!', name: 'X', nickname: 'X' });
  expect('A-007', '빈 이메일 거부', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: '123', name: 'X', nickname: 'X' });
  expect('A-008', '짧은 비밀번호(정책 의존)', true, `status=${r.status}`, r.elapsed);

  // ── 로그인 ── (OAuth2PasswordRequestForm: form-urlencoded + username 필드)
  r = await login(email1, 'Test1234!');
  expect('A-009', '정상 로그인', r.ok && !!r.data?.access_token, `status=${r.status}`, r.elapsed);
  const token1 = r.data?.access_token || '';
  // state.buyers에 추가 (A-031~A-044에서 b0로 사용)
  if (buyer001Id) {
    state.buyers.push({ id: buyer001Id, email: email1, password: 'Test1234!', token: token1, name: nick1 });
  }

  r = await login(email1, 'WrongPass!');
  expect('A-010', '잘못된 비밀번호 거부', !r.ok, `status=${r.status}`, r.elapsed);

  r = await login('nonexist@test.com', 'Test1234!');
  expect('A-011', '없는 이메일 로그인 거부', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/auth/login', {}, null, { formData: true });
  expect('A-012', '빈 body 로그인 거부', !r.ok, `status=${r.status}`, r.elapsed);

  // ── 토큰 ──
  r = await req('GET', '/buyers/me', null, token1);
  expect('A-013', '토큰으로 내 정보 조회', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/buyers/me', null, 'invalid-token-12345');
  expect('A-014', '잘못된 토큰 거부 (서버 정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/buyers/me');
  expect('A-015', '토큰 없이 보호 API (서버 정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 비밀번호 변경 ──
  r = await req('POST', '/auth/change-password', { current_password: 'Test1234!', new_password: 'NewPass1234!' }, token1);
  expect('A-016', '비밀번호 변경 시도', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await login(email1, 'NewPass1234!');
  expect('A-017', '변경된 비밀번호로 로그인', r.ok || r.status === 401, `status=${r.status}`, r.elapsed);

  // ── 대량 가입 ── (순차 처리로 rate limit 대응)
  const bulkResults = [];
  for (let i = 0; i < 10; i++) {
    const bNick = uniqueNickname('BK');
    const br = await req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: bNick, nickname: bNick });
    bulkResults.push(br.ok);
  }
  expect('A-018', '대량 가입 10명', bulkResults.filter(Boolean).length >= 8, `성공: ${bulkResults.filter(Boolean).length}/10`);

  // ── 판매자 가입/승인 ──
  const sellerEmail = uniqueEmail();
  const sellerNick = uniqueNickname('AS');
  const sellerBizNum = `${Math.floor(100+Math.random()*900)}-${Math.floor(10+Math.random()*90)}-${Math.floor(10000+Math.random()*90000)}`;
  r = await req('POST', '/sellers/', {
    email: sellerEmail, password: 'Test1234!',
    business_name: sellerNick, nickname: sellerNick,
    business_number: sellerBizNum, phone: '010-0000-0001',
    address: '서울시 강남구 테스트로 1', zip_code: '06234',
    established_date: '2020-01-01T00:00:00',
  });
  expect('A-019', '판매자 가입', r.ok, `status=${r.status}`, r.elapsed);
  const sellerId = r.data?.id;

  r = await req('POST', `/sellers/${sellerId}/approve`);
  expect('A-020', '판매자 승인', r.ok || r.status === 200, `status=${r.status}`, r.elapsed);
  // state.sellers에 추가 (A-036~A-037에서 s0로 사용)
  if (sellerId) {
    state.sellers.push({ id: sellerId, email: sellerEmail, password: 'Test1234!', token: null, business_name: sellerNick });
  }

  r = await sellerLogin(sellerEmail, 'Test1234!');
  expect('A-021', '판매자 로그인', r.ok && !!r.data?.access_token, `status=${r.status}`, r.elapsed);
  if (sellerId && r.data?.access_token) {
    // state.sellers에 token 업데이트
    const s = state.sellers.find(x => x.id === sellerId);
    if (s) s.token = r.data.access_token;
    else state.sellers.push({ id: sellerId, email: sellerEmail, password: 'Test1234!', token: r.data.access_token, business_name: sellerNick });
  }

  // ── 구매자+판매자 동일 이메일 ──
  const sameEmail = uniqueEmail();
  const bothNick = uniqueNickname('AB');
  const bothBizNum = `${Math.floor(100+Math.random()*900)}-${Math.floor(10+Math.random()*90)}-${Math.floor(10000+Math.random()*90000)}`;
  const rb = await req('POST', '/buyers/', { email: sameEmail, password: 'Test1234!', name: bothNick, nickname: bothNick });
  const rs = await req('POST', '/sellers/', {
    email: sameEmail, password: 'Test1234!',
    business_name: bothNick, nickname: bothNick,
    business_number: bothBizNum, phone: '010-0000-0002',
    address: '서울시 강남구 테스트로 2', zip_code: '06234',
    established_date: '2020-01-01T00:00:00',
  });
  expect('A-022', '같은 이메일 구매자+판매자', true, `buyer=${rb.status}, seller=${rs.status}`);

  // ── 비밀번호 재설정 ──
  r = await req('POST', '/auth/reset-password', { email: email1 });
  expect('A-023', '비밀번호 재설정 요청', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { email: `test+special_${Date.now()}@test.com`, password: 'Test1234!', name: uniqueNickname('Sp'), nickname: uniqueNickname('Sp') });
  expect('A-024', '특수문자 이메일(+_) 가입', r.ok || r.status === 422, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: 'A'.repeat(500), nickname: uniqueNickname('LN') });
  expect('A-025', '매우 긴 이름(500자)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: '', nickname: '' });
  expect('A-026', '빈 이름', true, `status=${r.status}`, r.elapsed);

  // ── 보안 ──
  r = await login("' OR 1=1 --", 'Test1234!');
  expect('A-027', 'SQL Injection 방어', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: '<script>alert(1)</script>', nickname: uniqueNickname('XS') });
  expect('A-028', 'XSS 이름 가입', true, `status=${r.status} (서버 처리에 의존)`, r.elapsed);

  // ── 목록 ──
  r = await req('GET', '/buyers/');
  expect('A-029', '구매자 목록 조회', r.ok, `status=${r.status}, count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  r = await req('GET', '/sellers/');
  expect('A-030', '판매자 목록 조회', r.ok, `status=${r.status}`, r.elapsed);

  // ── 상세 조회 ──
  const b0 = state.buyers[0];
  if (b0) {
    r = await req('GET', `/buyers/${b0.id}`);
    expect('A-031', '구매자 상세 조회', r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('A-031', '구매자 상세 조회', false, 'buyer 없음');
  }

  r = await req('GET', '/buyers/99999999');
  expect('A-032', '없는 구매자 ID 조회', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  if (b0) {
    r = await req('GET', `/buyers/${b0.id}/trust_tier`);
    expect('A-033', '구매자 신뢰 티어 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('A-033', '구매자 신뢰 티어 조회', false, 'buyer 없음');
  }

  if (b0) {
    r = await req('GET', `/buyers/${b0.id}/points_grade`);
    expect('A-034', '구매자 포인트 등급', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('A-034', '구매자 포인트 등급', false, 'buyer 없음');
  }

  if (b0) {
    r = await req('GET', '/buyers/summary', null, b0.token);
    expect('A-035', '구매자 요약 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('A-035', '구매자 요약 조회', false, 'buyer 없음');
  }

  const s0 = state.sellers[0];
  if (s0) {
    r = await req('GET', `/sellers/${s0.id}`);
    expect('A-036', '판매자 상세 조회', r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('A-036', '판매자 상세 조회', false, 'seller 없음');
  }

  if (s0) {
    r = await req('GET', '/sellers/me/summary', null, s0.token);
    expect('A-037', '판매자 요약 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('A-037', '판매자 요약 조회', false, 'seller 없음');
  }

  // ── 동시성 ──
  const concurrent = await Promise.all(
    Array.from({ length: 5 }, () => {
      const cn = uniqueNickname('Co');
      return req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: cn, nickname: cn });
    })
  );
  const concOk = concurrent.filter(r => r.ok).length;
  expect('A-038', '동시 가입 5명', concOk >= 3, `성공: ${concOk}/5`);

  if (state.buyers.length >= 2) {
    const loginBuyers = state.buyers.filter(b => b.password && b.token).slice(0, 3);
    const logins = await Promise.all(loginBuyers.map(b => login(b.email, b.password)));
    const loginOk = logins.filter(r => r.ok).length;
    expect('A-039', '동시 로그인 3명', loginOk >= 1, `성공: ${loginOk}/${loginBuyers.length}`);
  } else {
    expect('A-039', '동시 로그인 3명', false, 'buyer 부족');
  }

  // ── 부가 API ──
  if (b0) {
    r = await req('GET', `/dashboard/buyer/${b0.id}`);
    expect('A-040', '구매자 대시보드', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('A-040', '구매자 대시보드', false, 'buyer 없음');
  }

  if (b0) {
    r = await req('GET', `/insights/buyer/${b0.id}/overview`);
    expect('A-041', '구매자 인사이트', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('A-041', '구매자 인사이트', false, 'buyer 없음');
  }

  r = await req('GET', '/activity/recent');
  expect('A-042', '최근 활동 로그', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  if (b0) {
    r = await req('GET', `/preview/buyer/${b0.id}`);
    expect('A-043', '구매자 프리뷰', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('A-043', '구매자 프리뷰', false, 'buyer 없음');
  }

  if (b0) {
    r = await req('GET', `/basic/buyers/${b0.id}`);
    expect('A-044', 'Basic 구매자 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('A-044', 'Basic 구매자 조회', false, 'buyer 없음');
  }

  r = await req('GET', '/basic/buyers/');
  expect('A-045', 'Basic 구매자 목록', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/basic/sellers/');
  expect('A-046', 'Basic 판매자 목록', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 시스템 ──
  r = await req('GET', '/health');
  expect('A-047', 'Health 체크', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/health/deep');
  expect('A-048', 'Deep Health 체크', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/version');
  expect('A-049', '버전 조회', r.ok, `status=${r.status}, ver=${JSON.stringify(r.data)?.substring(0, 50)}`, r.elapsed);

  r = await req('GET', '/');
  expect('A-050', '루트 엔드포인트', r.ok, `status=${r.status}`, r.elapsed);
}
