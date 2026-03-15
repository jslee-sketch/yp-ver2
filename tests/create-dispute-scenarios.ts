/**
 * 분쟁 시나리오 생성 스크립트
 * 다양한 단계의 분쟁을 생성하여 시스템 검증
 *
 * 실행: npx tsx tests/create-dispute-scenarios.ts
 */

const PROD = 'https://web-production-defb.up.railway.app';

async function post(path: string, body: Record<string, unknown>) {
  const res = await fetch(`${PROD}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function put(path: string, body: Record<string, unknown>) {
  const res = await fetch(`${PROD}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function get(path: string) {
  const res = await fetch(`${PROD}${path}`);
  return res.json();
}

// ── 시나리오 생성 ──

async function main() {
  const results: Array<{
    scenario: string;
    disputeId: number;
    status: string;
    initiator: string;
    respondent: string;
    category: string;
  }> = [];

  // ━━━ 판매자 시나리오 (판매자가 분쟁 대응) ━━━

  // S1: 구매자가 시작 → 판매자 응답 대기 (ROUND1_RESPONSE)
  console.log('S1: 구매자 시작, 판매자 응답 대기...');
  const s1 = await post('/v3_6/disputes', {
    reservation_id: 1,
    initiator_id: 11,  // buyer #11
    respondent_id: 10, // seller #10
    initiator_role: 'buyer',
    category: 'defective',
    title: '[시나리오S1] 불량품 수령 - 판매자 응답 대기',
    description: '제품 개봉 시 화면 깨짐 확인. 판매자 응답을 기다리는 단계입니다.',
    requested_resolution: 'FULL_REFUND',
    requested_amount: 350000,
  });
  results.push({
    scenario: 'S1: 분쟁시작 (판매자 응답 대기)',
    disputeId: s1.dispute_id ?? s1.id ?? 0,
    status: 'ROUND1_RESPONSE',
    initiator: 'buyer#11 (buyer1)',
    respondent: 'seller#10 (막팔아)',
    category: 'defective',
  });

  // S2: 구매자 시작 → 판매자 응답 완료 → AI 중재 → 검토 대기 (ROUND1_REVIEW)
  console.log('S2: R1 응답 후 검토 대기...');
  const s2 = await post('/v3_6/disputes', {
    reservation_id: 2,
    initiator_id: 12,  // buyer #12
    respondent_id: 10, // seller #10
    initiator_role: 'buyer',
    category: 'wrong_item',
    title: '[시나리오S2] 오배송 - R1 검토 대기',
    description: '주문한 블랙 대신 실버 배송됨. 판매자가 교환을 제안한 상태.',
    requested_resolution: 'EXCHANGE',
    requested_amount: 0,
  });
  const s2id = s2.dispute_id ?? s2.id ?? 0;
  if (s2id) {
    await put(`/v3_6/disputes/${s2id}/round1-response`, {
      respondent_id: 10,
      reply: '재고 확인 중입니다. 교환 처리 가능합니다.',
      proposal_type: 'EXCHANGE',
      proposal_amount: 0,
    });
  }
  results.push({
    scenario: 'S2: R1 응답 완료 → AI 중재 후 검토 대기',
    disputeId: s2id,
    status: 'ROUND1_REVIEW',
    initiator: 'buyer#12 (buyer2)',
    respondent: 'seller#10 (막팔아)',
    category: 'wrong_item',
  });

  // S3: 분쟁 → R2 반론 진행 중 (ROUND2_RESPONSE)
  console.log('S3: R2 반론 진행 중...');
  const s3 = await post('/v3_6/disputes', {
    reservation_id: 3,
    initiator_id: 13,  // buyer #13
    respondent_id: 10,
    initiator_role: 'buyer',
    category: 'description_mismatch',
    title: '[시나리오S3] 상품설명불일치 - R2 반론 진행 중',
    description: '상품 설명과 실물 차이가 심합니다. 전액 환불 요청.',
    requested_resolution: 'FULL_REFUND',
    requested_amount: 280000,
  });
  const s3id = s3.dispute_id ?? s3.id ?? 0;
  if (s3id) {
    await put(`/v3_6/disputes/${s3id}/round1-response`, {
      respondent_id: 10,
      reply: '상품 설명에 차이 없다고 판단합니다. 부분 환불 제안.',
      proposal_type: 'PARTIAL_REFUND',
      proposal_amount: 50000,
    });
    // 신청자가 AI 중재안 거부 → R2로 이동
    await put(`/v3_6/disputes/${s3id}/decision`, {
      user_id: 13,
      decision: 'REJECT',
    });
  }
  results.push({
    scenario: 'S3: R2 반론 진행 중',
    disputeId: s3id,
    status: 'ROUND2_RESPONSE',
    initiator: 'buyer#13 (buyer3)',
    respondent: 'seller#10 (막팔아)',
    category: 'description_mismatch',
  });

  // S4: 분쟁 종료 — 합의 성공 (CLOSED_AGREED)
  console.log('S4: 분쟁 종료 (합의 성공)...');
  const s4 = await post('/v3_6/disputes', {
    reservation_id: 4,
    initiator_id: 14,
    respondent_id: 10,
    initiator_role: 'buyer',
    category: 'damaged',
    title: '[시나리오S4] 파손 - 합의 종료',
    description: '배송 중 파손. 부분 환불로 합의.',
    requested_resolution: 'PARTIAL_REFUND',
    requested_amount: 150000,
  });
  const s4id = s4.dispute_id ?? s4.id ?? 0;
  if (s4id) {
    await put(`/v3_6/disputes/${s4id}/round1-response`, {
      respondent_id: 10,
      reply: '파손 확인. 부분 환불 동의합니다.',
      proposal_type: 'PARTIAL_REFUND',
      proposal_amount: 120000,
    });
    await put(`/v3_6/disputes/${s4id}/decision`, {
      user_id: 14,
      decision: 'ACCEPT',
    });
  }
  results.push({
    scenario: 'S4: 분쟁 종료 (합의 성공)',
    disputeId: s4id,
    status: 'CLOSED_AGREED',
    initiator: 'buyer#14 (buyer4)',
    respondent: 'seller#10 (막팔아)',
    category: 'damaged',
  });

  // ━━━ 구매자 시나리오 (구매자가 분쟁 신청) ━━━

  // B1: 구매자 시작 — 미배송 (FILED → ROUND1_RESPONSE)
  console.log('B1: 구매자 미배송 분쟁 신청...');
  const b1 = await post('/v3_6/disputes', {
    reservation_id: 5,
    initiator_id: 11,
    respondent_id: 10,
    initiator_role: 'buyer',
    category: 'not_delivered',
    title: '[시나리오B1] 미배송 - 분쟁 시작',
    description: '결제 후 2주 경과했으나 배송이 시작되지 않았습니다.',
    requested_resolution: 'FULL_REFUND',
    requested_amount: 550000,
  });
  results.push({
    scenario: 'B1: 구매자 미배송 분쟁 시작',
    disputeId: b1.dispute_id ?? b1.id ?? 0,
    status: 'ROUND1_RESPONSE',
    initiator: 'buyer#11 (buyer1)',
    respondent: 'seller#10 (막팔아)',
    category: 'not_delivered',
  });

  // B2: 수량 부족 → 보상금 요청
  console.log('B2: 수량 부족 보상 요청...');
  const b2 = await post('/v3_6/disputes', {
    reservation_id: 6,
    initiator_id: 12,
    respondent_id: 10,
    initiator_role: 'buyer',
    category: 'quantity_shortage',
    title: '[시나리오B2] 수량부족 - 보상금 요청',
    description: '5개 주문했는데 3개만 도착. 부족분 보상 요청.',
    requested_resolution: 'COMPENSATION',
    requested_amount: 200000,
  });
  results.push({
    scenario: 'B2: 구매자 수량부족 보상 요청',
    disputeId: b2.dispute_id ?? b2.id ?? 0,
    status: 'ROUND1_RESPONSE',
    initiator: 'buyer#12 (buyer2)',
    respondent: 'seller#10 (막팔아)',
    category: 'quantity_shortage',
  });

  // B3: 불량 → R1 합의 → R2 → 최종 결렬 시뮬
  console.log('B3: 최종 결렬 시나리오...');
  const b3 = await post('/v3_6/disputes', {
    reservation_id: 7,
    initiator_id: 13,
    respondent_id: 10,
    initiator_role: 'buyer',
    category: 'defective',
    title: '[시나리오B3] 불량 - R2 최종 결렬',
    description: '불량품인데 판매자가 인정하지 않음. 최종 결렬 예상.',
    requested_resolution: 'FULL_REFUND',
    requested_amount: 420000,
  });
  const b3id = b3.dispute_id ?? b3.id ?? 0;
  if (b3id) {
    await put(`/v3_6/disputes/${b3id}/round1-response`, {
      respondent_id: 10,
      reply: '정상품 출고 확인. 사용 후 클레임으로 판단.',
      proposal_type: 'NO_REFUND',
      proposal_amount: 0,
    });
    // 거부 → R2
    await put(`/v3_6/disputes/${b3id}/decision`, {
      user_id: 13,
      decision: 'REJECT',
    });
    // R2 반론
    await put(`/v3_6/disputes/${b3id}/round2-rebuttal`, {
      user_id: 13,
      rebuttal: '개봉 직후 불량 확인. 증거 사진 있음.',
      proposal_type: 'FULL_REFUND',
      proposal_amount: 420000,
    });
  }
  results.push({
    scenario: 'B3: R2 최종 결렬 시나리오',
    disputeId: b3id,
    status: 'ROUND2_REVIEW (or CLOSED)',
    initiator: 'buyer#13 (buyer3)',
    respondent: 'seller#10 (막팔아)',
    category: 'defective',
  });

  // B4: 단순변심 → 빠른 합의
  console.log('B4: 단순변심 빠른 합의...');
  const b4 = await post('/v3_6/disputes', {
    reservation_id: 8,
    initiator_id: 14,
    respondent_id: 10,
    initiator_role: 'buyer',
    category: 'buyer_change_mind',
    title: '[시나리오B4] 단순변심 - 빠른 합의',
    description: '단순변심으로 환불 요청. 배송비 부담 의향 있음.',
    requested_resolution: 'FULL_REFUND',
    requested_amount: 180000,
  });
  const b4id = b4.dispute_id ?? b4.id ?? 0;
  if (b4id) {
    await put(`/v3_6/disputes/${b4id}/round1-response`, {
      respondent_id: 10,
      reply: '반품 확인 후 환불 처리하겠습니다. 왕복 배송비 차감.',
      proposal_type: 'FULL_REFUND',
      proposal_amount: 174000,
    });
    await put(`/v3_6/disputes/${b4id}/decision`, {
      user_id: 14,
      decision: 'ACCEPT',
    });
  }
  results.push({
    scenario: 'B4: 단순변심 빠른 합의',
    disputeId: b4id,
    status: 'CLOSED_AGREED',
    initiator: 'buyer#14 (buyer4)',
    respondent: 'seller#10 (막팔아)',
    category: 'buyer_change_mind',
  });

  // ── 결과 출력 ──
  console.log('\n' + '='.repeat(80));
  console.log('분쟁 시나리오 생성 결과');
  console.log('='.repeat(80));
  console.log('');
  console.log('| # | 시나리오 | 분쟁ID | 상태 | 신청자 | 상대방 | 카테고리 |');
  console.log('|---|----------|--------|------|--------|--------|----------|');
  results.forEach((r, i) => {
    console.log(`| ${i + 1} | ${r.scenario} | #${r.disputeId} | ${r.status} | ${r.initiator} | ${r.respondent} | ${r.category} |`);
  });

  console.log('');
  console.log('로그인 정보:');
  console.log('  buyer1:  realtest1@e2e.com / test1234');
  console.log('  buyer2:  realtest2@e2e.com / test1234');
  console.log('  buyer3:  realtest3@e2e.com / test1234');
  console.log('  buyer4:  realtest4@e2e.com / test1234');
  console.log('  seller:  jslee@tellustech.co.kr / test1234');
}

main().catch(console.error);
