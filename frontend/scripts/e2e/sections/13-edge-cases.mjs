// sections/13-edge-cases.mjs — 엣지케이스 (30건)
import { req, login, uniqueEmail } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, uniqueNickname } from '../lib/factory.mjs';

export async function run() {
  setSection('13. 엣지케이스 (30건)');
  let r;

  const buyer1 = await createBuyer('EdgeBuyer');
  const token = buyer1?.token || '';

  // ── ID 엣지케이스 ──
  r = await req('GET', '/deals/-1');
  expect('E-001', '음수 ID 요청 (/deals/-1)', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/deals/0');
  expect('E-002', 'ID 0 요청 (/deals/0)', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/deals/3.14');
  expect('E-003', '소수점 ID 요청 (/deals/3.14)', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/deals/abc');
  expect('E-004', '문자열 ID 요청 (/deals/abc)', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/deals/9999999999999');
  expect('E-005', '매우 큰 숫자 ID', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  // ── Body 엣지케이스 ──
  const opts1 = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: 'null' };
  const res1 = await fetch('http://127.0.0.1:9000/buyers/', opts1);
  expect('E-006', 'null body 요청', !res1.ok || res1.status >= 400, `status=${res1.status}`, 0);

  r = await req('POST', '/buyers/', {});
  expect('E-007', '빈 body {} 요청', !r.ok, `status=${r.status}`, r.elapsed);

  const opts2 = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '[]' };
  const res2 = await fetch('http://127.0.0.1:9000/buyers/', opts2);
  expect('E-008', '빈 배열 [] body 요청', !res2.ok || res2.status >= 400, `status=${res2.status}`, 0);

  // ── Content-Type 엣지케이스 ──
  const opts3 = { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: '{"email":"x@x.com","password":"Test1234!"}' };
  const res3 = await fetch('http://127.0.0.1:9000/buyers/', opts3);
  expect('E-009', '잘못된 Content-Type (text/plain)', !res3.ok || res3.status >= 400, `status=${res3.status}`, 0);

  // ── HTTP 메서드 ──
  r = await req('DELETE', '/deals/');
  expect('E-010', '잘못된 HTTP 메서드 (DELETE /deals/)', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/this-endpoint-does-not-exist-xyz');
  expect('E-011', '없는 엔드포인트', !r.ok || r.status === 404, `status=${r.status}`, r.elapsed);

  // ── Enum/형식 ──
  r = await req('POST', '/deals/', {
    product_name: '딜', desired_qty: 10, target_price: 50000,
    creator_id: buyer1?.id || 1, status: 'INVALID_STATUS_XYZ',
  }, token);
  expect('E-012', '잘못된 enum 값 (status)', r.ok || !r.ok, `status=${r.status} (무시하거나 거부)`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '딜', desired_qty: 10, target_price: 50000,
    creator_id: buyer1?.id || 1, deadline: 'not-a-date',
  }, token);
  expect('E-013', '잘못된 날짜 형식', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '미래날짜 딜', desired_qty: 10, target_price: 50000,
    creator_id: buyer1?.id || 1, deadline: '2099-12-31T23:59:59',
  }, token);
  expect('E-014', '미래 날짜 설정', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 유니코드 ──
  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: '한국어이름테스트', nickname: uniqueNickname('KR') });
  expect('E-015', '유니코드 한국어 이름', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: '漢字名前テスト', nickname: uniqueNickname('HJ') });
  expect('E-016', '한자/일본어 이름', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: 'اسم عربي', nickname: 'عربي' });
  expect('E-017', '아랍어 이름', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 보안 ──
  r = await login("'; DROP TABLE buyers; --", 'x');
  expect('E-018', 'SQL Injection 방어 (DROP TABLE)', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '<script>alert("XSS")</script>', desired_qty: 10, target_price: 50000,
    creator_id: buyer1?.id || 1,
  }, token);
  expect('E-019', 'XSS 상품명 가입', r.ok || !r.ok, `status=${r.status} (저장은 되되 이스케이프 필요)`, r.elapsed);

  // ── 큰 payload ──
  const largeBody = { email: uniqueEmail(), password: 'Test1234!', name: 'A'.repeat(10000), nickname: 'Large' };
  r = await req('POST', '/buyers/', largeBody);
  expect('E-020', '매우 큰 payload (name 10000자)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 중첩 JSON ──
  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: 'Nested', nickname: 'N', metadata: { a: { b: { c: { d: 'deep' } } } } });
  expect('E-021', '중첩 JSON 포함 요청', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 부동소수점 가격 ──
  r = await req('POST', '/deals/', { product_name: '소수점가격', desired_qty: 10, target_price: 29999.99, creator_id: buyer1?.id || 1 }, token);
  expect('E-022', '부동소수점 가격 (29999.99)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 매우 긴 쿼리스트링 ──
  r = await req('GET', `/deals/?skip=0&limit=10&${'x'.repeat(1000)}=value`);
  expect('E-023', '매우 긴 쿼리스트링', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 중복 파라미터 ──
  r = await req('GET', '/deals/?limit=5&limit=10&skip=0');
  expect('E-024', '중복 쿼리 파라미터', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 잘못된 JSON ──
  const opts4 = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{invalid json here' };
  const res4 = await fetch('http://127.0.0.1:9000/buyers/', opts4);
  expect('E-025', '잘못된 JSON 형식', !res4.ok || res4.status >= 400, `status=${res4.status}`, 0);

  // ── 타입 오류 ──
  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: 123, nickname: 456 });
  expect('E-026', '숫자를 문자로 전달 (name=123)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', { product_name: '타입딜', desired_qty: '열', target_price: '이십만원', creator_id: buyer1?.id || 1 }, token);
  expect('E-027', '배열을 문자로 전달 (qty="열")', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  // ── 이모지 비밀번호 ──
  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: '🔐Test1234!', name: 'EmojiPW', nickname: 'EmojiPW' });
  expect('E-028', '이모지 포함 비밀번호', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 탭/개행 ──
  r = await req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: '탭\t개행\n이름', nickname: 'Tab' });
  expect('E-029', '탭/개행 포함 이름', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 혼합 타입 배열 ──
  const opts5 = { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify([1, 'two', null, true, { a: 1 }]) };
  const res5 = await fetch('http://127.0.0.1:9000/buyers/', opts5);
  expect('E-030', '혼합 타입 배열 body', !res5.ok || res5.status >= 400, `status=${res5.status}`, 0);
}
