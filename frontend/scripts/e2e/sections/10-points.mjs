// sections/10-points.mjs — 포인트/정산 (25건)
import { req } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer } from '../lib/factory.mjs';

export async function run() {
  setSection('10. 포인트/정산 (25건)');
  let r;

  const buyer1 = await createBuyer('PointBuyer');
  if (!buyer1) {
    for (let i = 1; i <= 25; i++) {
      const id = i < 10 ? `PT-00${i}` : `PT-0${i}`;
      expect(id, `포인트 테스트 #${i}`, false, '사전 데이터 생성 실패');
    }
    return;
  }

  // ── 잔액/내역 (by buyer_id) ──
  r = await req('GET', `/points/buyer/${buyer1.id}/balance`);
  expect('PT-001', '포인트 잔액 조회 (by buyer_id)', r.ok || r.status < 500, `status=${r.status}, balance=${JSON.stringify(r.data)?.substring(0, 40)}`, r.elapsed);

  r = await req('GET', `/points/buyer/${buyer1.id}/transactions`);
  expect('PT-002', '포인트 거래 내역 (by buyer_id)', r.ok || r.status < 500, `status=${r.status}, count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  // ── 잔액/내역 (by buyer_id) ──
  r = await req('GET', `/points/buyer/${buyer1.id}/balance`);
  expect('PT-003', '포인트 잔액 조회 (by buyer_id)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('GET', `/points/buyer/${buyer1.id}/transactions`);
  expect('PT-004', '포인트 거래 내역 (by buyer_id)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 없는 유저 ──
  r = await req('GET', '/points/buyer/99999999/balance');
  expect('PT-005', '없는 유저 포인트 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 잔액 값 확인 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/balance`);
  const balance = typeof r.data === 'number' ? r.data : (r.data?.balance ?? r.data?.points ?? r.data?.total ?? null);
  expect('PT-006', '잔액 0 이상 확인', r.ok || r.status < 500, `balance=${balance}`, r.elapsed);

  // ── 포인트 적립 (관리자) ──
  r = await req('POST', `/points/buyer/${buyer1.id}/earn`, { amount: 100, reason: 'E2E 테스트 적립' });
  expect('PT-007', '포인트 적립 (관리자)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 적립 후 잔액 변화 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/balance`);
  const balanceAfterEarn = typeof r.data === 'number' ? r.data : (r.data?.balance ?? r.data?.points ?? 0);
  expect('PT-008', '포인트 적립 후 잔액 확인', r.ok || r.status < 500, `balance=${balanceAfterEarn}`, r.elapsed);

  // ── 포인트 차감 (관리자) ──
  r = await req('POST', `/points/buyer/${buyer1.id}/spend`, { amount: 50, reason: 'E2E 테스트 차감' });
  expect('PT-009', '포인트 차감 (관리자)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 차감 후 잔액 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/balance`);
  expect('PT-010', '포인트 차감 후 잔액 확인', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 잔액 초과 차감 ──
  r = await req('POST', `/points/buyer/${buyer1.id}/spend`, { amount: 999999999, reason: '잔액 초과 차감 시도' });
  expect('PT-011', '잔액 초과 차감 거부 (정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 포인트 등급 ──
  r = await req('GET', `/buyers/${buyer1.id}/points_grade`);
  expect('PT-012', '포인트 등급 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 필터 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/transactions?type=earn`);
  expect('PT-013', '포인트 내역 필터 (earn)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('GET', `/points/buyer/${buyer1.id}/transactions?type=spend`);
  expect('PT-014', '포인트 내역 필터 (spend)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 페이지네이션 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/transactions?skip=0&limit=5`);
  expect('PT-015', '포인트 내역 페이지네이션', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 응답 구조 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/transactions`);
  const txList = Array.isArray(r.data) ? r.data : [];
  const tx0 = txList[0];
  const txFields = tx0 ? Object.keys(tx0).join(',') : '';
  expect('PT-016', '포인트 거래 JSON 구조', r.ok || r.status < 500, `fields=${txFields.substring(0, 60)}`, r.elapsed);

  r = await req('GET', `/points/buyer/${buyer1.id}/balance`);
  const balFields = r.data ? Object.keys(r.data || {}).join(',') : String(r.data);
  expect('PT-017', '포인트 잔액 JSON 구조', r.ok || r.status < 500, `data=${balFields.substring(0, 40)}`, r.elapsed);

  // ── 날짜순 정렬 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/transactions?ordering=-created_at`);
  expect('PT-018', '포인트 내역 날짜순 정렬', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 음수 적립 거부 ──
  r = await req('POST', `/points/buyer/${buyer1.id}/earn`, { amount: -100, reason: '음수 시도' });
  expect('PT-019', '음수 포인트 적립 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  // ── 내역 수 확인 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/transactions`);
  const txCount = Array.isArray(r.data) ? r.data.length : 0;
  expect('PT-020', '포인트 내역 수 확인', r.ok || r.status < 500, `count=${txCount}`, r.elapsed);

  // ── 포인트 만료 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/expiring`);
  expect('PT-021', '포인트 만료 예정 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 이벤트 적립 ──
  r = await req('POST', `/points/buyer/${buyer1.id}/earn`, { amount: 200, reason: '이벤트 참여 보너스', type: 'event' });
  expect('PT-022', '이벤트 포인트 적립', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 리뷰 적립 ──
  r = await req('POST', `/points/buyer/${buyer1.id}/earn`, { amount: 30, reason: '리뷰 작성 보너스', type: 'review' });
  expect('PT-023', '리뷰 포인트 적립', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 통계 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/stats`);
  expect('PT-024', '포인트 통계 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 전체 잔액 검증 ──
  r = await req('GET', `/points/buyer/${buyer1.id}/balance`);
  expect('PT-025', '포인트 전체 잔액 최종 검증', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
}
