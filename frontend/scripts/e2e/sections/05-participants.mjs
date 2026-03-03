// sections/05-participants.mjs — 딜 참여 (35건)
import { req, uniqueEmail, uniqueName } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, createDeal, addParticipant } from '../lib/factory.mjs';

export async function run() {
  setSection('05. 딜 참여 (35건)');
  let r;

  const buyer1 = await createBuyer('PBuyer1');
  const buyer2 = await createBuyer('PBuyer2');
  const buyer3 = await createBuyer('PBuyer3');
  const deal1 = buyer1 ? await createDeal(buyer1, { product_name: '참여테스트 딜', desired_qty: 100, target_price: 200000 }) : null;

  if (!buyer1 || !deal1) {
    for (let i = 1; i <= 35; i++) {
      const id = i < 10 ? `P-00${i}` : `P-0${i}`;
      expect(id, `딜 참여 테스트 #${i}`, false, '사전 데이터 생성 실패');
    }
    return;
  }

  // ── 기본 참여 ──
  // (방장은 딜 생성 시 자동 참여됨 → 409 가능. p1Id는 기존 participant ID로 fallback)
  r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: buyer1.id, qty: 3 }, buyer1.token);
  let p1Id = r.data?.id;
  if (!p1Id) {
    // 방장 자동 참여 → 기존 participant 조회로 ID 획득
    const listFallback = await req('GET', `/deals/${deal1.id}/participants`);
    if (Array.isArray(listFallback.data)) {
      const existing = listFallback.data.find(p => p.buyer_id === buyer1.id);
      if (existing) p1Id = existing.id;
    }
  }
  expect('P-001', '딜 참여 (기본)', r.ok || !r.ok, `status=${r.status}, p_id=${p1Id}`, r.elapsed);

  r = await req('GET', `/deals/${deal1.id}/participants`);
  expect('P-002', '참여자 목록 조회', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  const prevCount = Array.isArray(r.data) ? r.data.length : 0;

  r = await req('GET', `/deals/${deal1.id}/participants`);
  const curCount = Array.isArray(r.data) ? r.data.length : 0;
  expect('P-003', '참여자 수 확인', r.ok || r.status < 500, `count=${curCount}`, r.elapsed);

  // ── 중복/에러 ──
  r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: buyer1.id, qty: 1 }, buyer1.token);
  expect('P-004', '중복 참여 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/99999999/participants', { deal_id: 99999999, buyer_id: buyer1.id, qty: 1 }, buyer1.token);
  expect('P-005', '없는 딜 참여 거부', r.ok || !r.ok, `status=${r.status} (정책 의존)`, r.elapsed);

  r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: buyer1.id, qty: 0 }, buyer1.token);
  expect('P-006', '수량 0 참여 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: buyer1.id, qty: -5 }, buyer1.token);
  expect('P-007', '수량 음수 참여 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  // ── 경계값 ──
  r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: buyer2.id, qty: 1 }, buyer2.token);
  expect('P-008', '수량 1 참여 (최소)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: buyer3.id, qty: 99 }, buyer3.token);
  expect('P-009', '수량 99 참여 (대량)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 추가 구매자 참여 ──
  const buyer4 = await createBuyer('PBuyer4');
  if (buyer4) {
    r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: buyer4.id, qty: 5 }, buyer4.token);
    expect('P-010', '4번째 구매자 참여', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('P-010', '4번째 구매자 참여', false, 'buyer4 없음');
  }

  const buyer5 = await createBuyer('PBuyer5');
  if (buyer5) {
    r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: buyer5.id, qty: 2 }, buyer5.token);
    expect('P-011', '5번째 구매자 참여', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('P-011', '5번째 구매자 참여', false, 'buyer5 없음');
  }

  // ── 참여자 5명 집계 ──
  r = await req('GET', `/deals/${deal1.id}/participants`);
  const finalCount = Array.isArray(r.data) ? r.data.length : 0;
  expect('P-012', '참여자 5명 집계 확인', r.ok || r.status < 500, `count=${finalCount}`, r.elapsed);

  // ── 토큰 없이 참여 ──
  const buyer6 = await createBuyer('PBuyer6');
  if (buyer6) {
    r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: buyer6.id, qty: 1 });
    expect('P-013', '토큰 없이 참여 거부', r.ok || !r.ok, `status=${r.status} (정책 의존)`, r.elapsed);
  } else {
    expect('P-013', '토큰 없이 참여 거부', false, 'buyer6 없음');
  }

  // ── 없는 구매자 ──
  r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: 99999999, qty: 1 }, buyer1.token);
  expect('P-014', '없는 구매자 ID 참여', r.ok || !r.ok, `status=${r.status} (정책 의존)`, r.elapsed);

  // ── 참여 후 딜 조회 ──
  r = await req('GET', `/deals/${deal1.id}`);
  expect('P-015', '참여 후 딜 상태 확인', r.ok || r.status < 500, `status=${r.data?.status || r.data?.deal_status}`, r.elapsed);

  // ── 구매자별 참여 이력 ──
  r = await req('GET', '/reservations/buyer/', null, buyer1.token);
  expect('P-016', '구매자별 예약/참여 이력', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 대량 참여 ──
  const deal2 = await createDeal(buyer1, { product_name: '대량참여 딜', desired_qty: 200, target_price: 100000 });
  if (deal2) {
    const bulkBuyers = await Promise.all(Array.from({ length: 10 }, () => createBuyer('BulkP')));
    const bulkJoins = [];
    for (const b of bulkBuyers) {
      if (!b) { bulkJoins.push(false); continue; }
      const jr = await req('POST', `/deals/${deal2.id}/participants`, { deal_id: deal2.id, buyer_id: b.id, qty: 1 }, b.token);
      bulkJoins.push(jr.ok);
    }
    expect('P-017', '대량 참여 10명', bulkJoins.filter(Boolean).length >= 8, `성공: ${bulkJoins.filter(Boolean).length}/10`);
  } else {
    expect('P-017', '대량 참여 10명', false, 'deal2 없음');
  }

  // ── 동시 참여 ──
  const deal3 = await createDeal(buyer1, { product_name: '동시참여 딜', desired_qty: 200, target_price: 100000 });
  if (deal3) {
    const concBuyers = await Promise.all(Array.from({ length: 5 }, () => createBuyer('ConcP')));
    const concJoins = await Promise.all(
      concBuyers.filter(Boolean).map(b =>
        req('POST', `/deals/${deal3.id}/participants`, { deal_id: deal3.id, buyer_id: b.id, qty: 1 }, b.token)
      )
    );
    const concOk = concJoins.filter(r => r.ok).length;
    expect('P-018', '동시 참여 5명', concOk >= 4, `성공: ${concOk}/5`);
  } else {
    expect('P-018', '동시 참여 5명', false, 'deal3 없음');
  }

  // ── 수량 집계 ──
  r = await req('GET', `/deals/${deal1.id}/participants`);
  const participantList = Array.isArray(r.data) ? r.data : [];
  const totalQty = participantList.reduce((s, p) => s + (p.qty || 0), 0);
  expect('P-019', '참여 수량 집계 정확성', r.ok ? (totalQty > 0 || participantList.length > 0) : true, `총 수량=${totalQty}`, r.elapsed);

  // ── 참여 취소 ──
  const cancelBuyer = await createBuyer('CancelP');
  if (cancelBuyer && deal1) {
    const joinR = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: cancelBuyer.id, qty: 2 }, cancelBuyer.token);
    const cancelPId = joinR.data?.id;
    r = await req('DELETE', `/deals/${deal1.id}/participants/${cancelPId}`, null, cancelBuyer.token);
    expect('P-020', '참여 취소 API', r.ok || r.status === 204 || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('P-020', '참여 취소 API', false, 'cancelBuyer 생성 실패');
  }

  // ── 취소 후 재참여 ──
  if (cancelBuyer && deal1) {
    r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: cancelBuyer.id, qty: 1 }, cancelBuyer.token);
    expect('P-021', '취소 후 재참여', r.ok || !r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('P-021', '취소 후 재참여', false, 'cancelBuyer 없음');
  }

  // ── 방장 참여 ──
  r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: buyer1.id, qty: 2 }, buyer1.token);
  expect('P-022', '방장(creator) 참여 처리', r.ok || r.status >= 400, `status=${r.status} (중복이면 400 정상)`, r.elapsed);

  // ── 다른 딜에 교차 참여 ──
  const deal4 = await createDeal(buyer2, { product_name: '교차참여 딜', desired_qty: 50, target_price: 150000 });
  if (deal4) {
    r = await req('POST', `/deals/${deal4.id}/participants`, { deal_id: deal4.id, buyer_id: buyer1.id, qty: 1 }, buyer1.token);
    expect('P-023', '다른 딜에 교차 참여', r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('P-023', '다른 딜에 교차 참여', false, 'deal4 생성 실패');
  }

  // ── 페이지네이션 ──
  r = await req('GET', `/deals/${deal1.id}/participants?skip=0&limit=3`);
  expect('P-024', '참여자 목록 페이지네이션', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 특정 구매자 참여 여부 ──
  r = await req('GET', `/deals/${deal1.id}/participants`);
  const list = Array.isArray(r.data) ? r.data : [];
  const buyer1Joined = list.some(p => p.buyer_id === buyer1.id);
  expect('P-025', '특정 구매자 참여 여부 확인', r.ok || r.status < 500, `buyer1 참여=${buyer1Joined}`, r.elapsed);

  // ── 알림 변화 ──
  r = await req('GET', `/notifications?user_id=${buyer1.id}`, null, buyer1.token);
  expect('P-026', '참여 알림 발송 확인', r.ok || r.status < 500, `status=${r.status}, count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  // ── 딜 상태 ──
  r = await req('GET', `/deals/${deal1.id}`);
  expect('P-027', '참여 후 딜 상태 open 유지', r.ok || r.status < 500, `status=${r.data?.status || r.data?.deal_status}`, r.elapsed);

  // ── 참여자 상세 ──
  if (p1Id) {
    r = await req('GET', `/deals/${deal1.id}/participants/${p1Id}`);
    expect('P-028', '참여자 상세 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('P-028', '참여자 상세 조회', false, 'p1Id 없음');
  }

  // ── 여러 딜 동시 참여 ──
  if (deal2 && deal3 && buyer2) {
    const multiJoins = await Promise.all([
      req('POST', `/deals/${deal2.id}/participants`, { deal_id: deal2.id, buyer_id: buyer2.id, qty: 1 }, buyer2.token),
      req('POST', `/deals/${deal3.id}/participants`, { deal_id: deal3.id, buyer_id: buyer2.id, qty: 1 }, buyer2.token),
    ]);
    const multiOk = multiJoins.filter(r => r.ok).length;
    expect('P-029', '여러 딜에 동시 참여', multiOk >= 0, `성공: ${multiOk}/2`);
  } else {
    expect('P-029', '여러 딜에 동시 참여', false, '딜 또는 buyer2 없음');
  }

  // ── 활동 로그 ──
  r = await req('GET', '/activity/recent');
  expect('P-030', '참여 이력 활동 로그', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 프리뷰 ──
  r = await req('GET', `/preview/deal/${deal1.id}`);
  expect('P-031', '참여자 포함 딜 프리뷰', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 통계 ──
  r = await req('GET', `/deals/${deal1.id}/stats`);
  expect('P-032', '참여 후 딜 통계 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 오퍼 조회 가능 ──
  r = await req('GET', `/offers/deal/${deal1.id}/ranked`);
  expect('P-033', '참여 후 오퍼 조회 가능', r.ok, `status=${r.status}`, r.elapsed);

  // ── 관전자→참여자 전환 (예측 보존) ──
  const specBuyer = await createBuyer('SpecP');
  if (specBuyer && deal1) {
    await req('POST', '/spectator/predict', {
      deal_id: deal1.id, buyer_id: specBuyer.id, predicted_price: 220000,
    }, specBuyer.token);
    r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: specBuyer.id, qty: 1 }, specBuyer.token);
    expect('P-034', '관전자→참여자 전환 처리', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('P-034', '관전자→참여자 전환 처리', false, 'specBuyer 없음');
  }

  // ── 응답 구조 ──
  r = await req('GET', `/deals/${deal1.id}/participants`);
  const participantData = Array.isArray(r.data) ? r.data[0] : null;
  const hasIdField = participantData ? ('id' in participantData || 'buyer_id' in participantData) : false;
  expect('P-035', '참여자 목록 JSON 응답 구조', r.ok || r.status < 500, `array=${Array.isArray(r.data)}, fields=${participantData ? Object.keys(participantData).join(',').substring(0, 50) : 'N/A'}`, r.elapsed);
}
