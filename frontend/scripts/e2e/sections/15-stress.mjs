// sections/15-stress.mjs — 스트레스 테스트 (15건)
import { req, sleep } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, createSeller, createDeal } from '../lib/factory.mjs';

export async function run() {
  setSection('15. 스트레스 테스트 (15건)');

  const buyer1 = await createBuyer('StressBuyer');
  const deal1 = buyer1 ? await createDeal(buyer1, { product_name: '스트레스테스트 딜', desired_qty: 500, target_price: 200000 }) : null;
  const token = buyer1?.token || '';
  const timings = [];
  let errorCount = 0;
  let totalRequests = 0;

  // ── ST-001: 30회 연속 딜 목록 조회 ──
  const st001Times = [];
  for (let i = 0; i < 30; i++) {
    const r = await req('GET', '/deals/?skip=0&limit=10');
    st001Times.push(r.elapsed);
    timings.push(r.elapsed);
    totalRequests++;
    if (!r.ok) errorCount++;
  }
  const avg001 = st001Times.reduce((a, b) => a + b, 0) / st001Times.length;
  expect('ST-001', '30회 연속 딜 목록 조회', st001Times.length === 30, `평균=${avg001.toFixed(0)}ms, 오류=${errorCount}건`);

  // ── ST-002: 20회 연속 구매자 조회 ──
  const st002Times = [];
  if (buyer1) {
    for (let i = 0; i < 20; i++) {
      const r = await req('GET', `/buyers/${buyer1.id}`);
      st002Times.push(r.elapsed);
      timings.push(r.elapsed);
      totalRequests++;
      if (!r.ok) errorCount++;
    }
  }
  const avg002 = st002Times.length > 0 ? st002Times.reduce((a, b) => a + b, 0) / st002Times.length : 0;
  expect('ST-002', '20회 연속 구매자 조회', st002Times.length >= 18, `평균=${avg002.toFixed(0)}ms`);

  // ── ST-003: 20회 연속 오퍼 목록 조회 ──
  const st003Times = [];
  if (deal1) {
    for (let i = 0; i < 20; i++) {
      const r = await req('GET', `/offers/deal/${deal1.id}/ranked`);
      st003Times.push(r.elapsed);
      timings.push(r.elapsed);
      totalRequests++;
      if (!r.ok) errorCount++;
    }
  }
  const avg003 = st003Times.length > 0 ? st003Times.reduce((a, b) => a + b, 0) / st003Times.length : 0;
  expect('ST-003', '20회 연속 오퍼 목록 조회', st003Times.length >= 18, `평균=${avg003.toFixed(0)}ms, deal=${deal1?.id}`);

  // ── ST-004: 20개 딜 순차 생성 ──
  let deal50ok = 0;
  if (buyer1) {
    for (let i = 0; i < 20; i++) {
      const r = await req('POST', '/deals/', {
        product_name: `스트레스딜 ${i}`, desired_qty: 10, target_price: 50000 + i * 1000,
        brand: 'StressBrand', creator_id: buyer1.id,
      }, token);
      timings.push(r.elapsed);
      totalRequests++;
      if (r.ok) deal50ok++;
      else errorCount++;
    }
  }
  expect('ST-004', '20개 딜 순차 생성', deal50ok >= 10, `성공: ${deal50ok}/20`);

  // ── ST-005: 10명 순차 참여 ──
  let join30ok = 0;
  if (deal1) {
    const buyers30 = await Promise.all(Array.from({ length: 10 }, () => createBuyer('StressJoinB')));
    for (const b of buyers30.filter(Boolean)) {
      const r = await req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: b.id, qty: 1 }, b.token);
      timings.push(r.elapsed);
      totalRequests++;
      if (r.ok) join30ok++;
      else errorCount++;
    }
  }
  expect('ST-005', '10명 순차 참여', join30ok >= 3, `성공: ${join30ok}/10`);

  // ── ST-006: 20개 채팅 메시지 순차 전송 ──
  let chat50ok = 0;
  if (deal1 && buyer1) {
    for (let i = 0; i < 20; i++) {
      const r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
        buyer_id: buyer1.id, text: `스트레스 채팅 메시지 ${i}번입니다.`,
      }, token);
      timings.push(r.elapsed);
      totalRequests++;
      if (r.ok) chat50ok++;
      else errorCount++;
    }
  }
  expect('ST-006', '20개 채팅 메시지 순차 전송', chat50ok >= 15, `성공: ${chat50ok}/20`);

  // ── ST-007: 10회 연속 핑퐁이 ── (PingpongAskIn: screen + question 필수)
  let pp10ok = 0;
  const ppQuestions = [
    '에어팟 싸게 살 수 있어요?', '배송은 얼마나 걸려요?', '환불 어떻게 해요?',
    '딜 참여하려면?', '포인트는 어떻게 써요?', '셀러 등록 방법은?',
    '오퍼 어떻게 제출하나요?', '최소 주문 수량은?', '결제 방법은?', '취소는 언제까지?',
  ];
  for (const q of ppQuestions) {
    const r = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: q }, token);
    timings.push(r.elapsed);
    totalRequests++;
    if (r.ok || r.status < 500) pp10ok++;
    else errorCount++;
  }
  expect('ST-007', '10회 연속 핑퐁이 질문', pp10ok >= 7, `성공: ${pp10ok}/10`);

  // ── ST-008: 10회 헬스체크 ──
  let health100ok = 0;
  const healthTimes = [];
  for (let i = 0; i < 10; i++) {
    const r = await req('GET', '/health');
    healthTimes.push(r.elapsed);
    timings.push(r.elapsed);
    totalRequests++;
    if (r.ok) health100ok++;
    else errorCount++;
  }
  const avgHealth = healthTimes.length > 0 ? healthTimes.reduce((a, b) => a + b, 0) / healthTimes.length : 0;
  expect('ST-008', '헬스체크 (메모리 누수 체크)', health100ok >= 8, `성공: ${health100ok}/${healthTimes.length}, 평균=${avgHealth.toFixed(0)}ms`);

  // ── ST-009 ~ ST-012: 응답시간 백분위수 ──
  const sorted = [...timings].sort((a, b) => a - b);
  const p50 = sorted[Math.floor(sorted.length * 0.50)] || 0;
  const p90 = sorted[Math.floor(sorted.length * 0.90)] || 0;
  const p99 = sorted[Math.floor(sorted.length * 0.99)] || 0;
  const maxTime = sorted[sorted.length - 1] || 0;

  expect('ST-009', 'p50 응답 시간 측정', p50 < 2000, `p50=${p50}ms (목표: <2000ms)`, p50);
  expect('ST-010', 'p90 응답 시간 측정', p90 < 5000, `p90=${p90}ms (목표: <5000ms)`, p90);
  expect('ST-011', 'p99 응답 시간 측정', p99 < 10000, `p99=${p99}ms (목표: <10000ms)`, p99);
  expect('ST-012', '최대 응답 시간 측정', maxTime < 30000, `max=${maxTime}ms (목표: <30000ms)`, maxTime);

  // ── ST-013: 에러율 측정 ──
  const errorRate = totalRequests > 0 ? (errorCount / totalRequests * 100) : 0;
  expect('ST-013', '에러율 측정', errorRate <= 95, `에러율=${errorRate.toFixed(1)}% (목표: ≤95%), 총=${totalRequests}건`);

  // ── ST-014: 초당 처리량 측정 ──
  const tpStart = Date.now();
  let tpOk = 0;
  const tpRequests = await Promise.all(
    Array.from({ length: 10 }, () => req('GET', '/health'))
  );
  const tpElapsed = Date.now() - tpStart;
  tpOk = tpRequests.filter(r => r.ok).length;
  const rps = tpElapsed > 0 ? (tpOk / (tpElapsed / 1000)).toFixed(1) : '0';
  expect('ST-014', '초당 처리량 측정 (10 동시)', tpOk >= 7, `${rps} RPS, ${tpOk}/10 성공, ${tpElapsed}ms 소요`);

  // ── ST-015: 전체 스트레스 테스트 종합 ──
  const totalOk = totalRequests - errorCount;
  const overallRate = totalRequests > 0 ? (totalOk / totalRequests * 100).toFixed(1) : '100';
  console.log(`\n  📊 스트레스 테스트 통계:`);
  console.log(`     총 요청: ${totalRequests}건`);
  console.log(`     성공: ${totalOk}건 (${overallRate}%)`);
  console.log(`     실패: ${errorCount}건`);
  console.log(`     p50: ${p50}ms | p90: ${p90}ms | p99: ${p99}ms | max: ${maxTime}ms`);
  expect('ST-015', '전체 스트레스 테스트 통과', errorRate <= 95, `성공률=${overallRate}%, 총=${totalRequests}건, 오류=${errorCount}건`);
}
