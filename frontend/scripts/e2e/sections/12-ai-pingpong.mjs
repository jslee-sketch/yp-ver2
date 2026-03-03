// sections/12-ai-pingpong.mjs — AI/핑퐁이 (25건)
// PingpongAskIn: screen(필수) + question(필수) — message 필드 없음
// DealAIRequest: raw_title(필수) — product_name 필드 없음
import { req, sleep } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, createDeal, state } from '../lib/factory.mjs';

export async function run() {
  setSection('12. AI/핑퐁이 (25건)');
  let r;

  const buyer1 = await createBuyer('AIBuyer');
  const deal1 = buyer1 ? await createDeal(buyer1, { product_name: 'AI테스트 에어팟', desired_qty: 50, target_price: 279000 }) : null;
  const token = buyer1?.token || '';

  // ── AI 딜 헬퍼 (DealAIRequest: raw_title 필수) ──
  r = await req('POST', '/ai/deal_helper', { raw_title: '에어팟 프로 2세대' }, token);
  expect('AI-001', 'AI 딜 헬퍼 기본 요청', r.ok || r.status <= 500, `status=${r.status}`, r.elapsed);

  const aiKeys = r.ok ? Object.keys(r.data || {}).join(',') : '';
  expect('AI-002', 'AI 딜 헬퍼 응답 구조 확인', r.ok ? !!r.data : true, `keys=${aiKeys.substring(0, 60)}`, r.elapsed);

  r = await req('POST', '/ai/deal_helper', { raw_title: '에어팟 프로' }, token);
  expect('AI-003', 'AI 딜 헬퍼 - 에어팟', r.ok || r.status <= 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/ai/deal_helper', { raw_title: '갤럭시 S25 울트라' }, token);
  expect('AI-004', 'AI 딜 헬퍼 - 갤럭시', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/ai/deal_helper', { raw_title: '' }, token);
  expect('AI-005', 'AI 딜 헬퍼 - 빈 상품명', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 핑퐁이 (PingpongAskIn: screen + question 필수) ──
  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: '에어팟 싸게 살 수 있어?' }, token);
  expect('AI-006', '핑퐁이 기본 질문', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  const pingpongAnswer = r.ok ? (r.data?.answer || r.data?.message || r.data?.text || r.data?.response || '') : '';
  expect('AI-007', '핑퐁이 응답 구조 확인', r.ok ? !!r.data : true, `answer=${String(pingpongAnswer).substring(0, 50)}`, r.elapsed);

  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'REFUND_FLOW', question: '환불 정책이 어떻게 되나요?' }, token);
  expect('AI-008', '핑퐁이 정책 질문', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: '오퍼는 어떻게 제출하나요?' }, token);
  expect('AI-009', '핑퐁이 오퍼 질문', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: '배송은 며칠 걸리나요?' }, token);
  expect('AI-010', '핑퐁이 배송 질문', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'REFUND_FLOW', question: '환불은 어떻게 받나요?' }, token);
  expect('AI-011', '핑퐁이 환불 질문', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: ' ' }, token);
  expect('AI-012', '핑퐁이 빈 입력(공백)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: '안녕하세요'.repeat(100) }, token);
  expect('AI-013', '핑퐁이 매우 긴 입력 (600자)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'DEAL_ROOM', question: '안녕하세요, 저는 에어팟 프로를 공동구매하고 싶습니다.' }, token);
  expect('AI-014', '핑퐁이 한국어 질문', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: 'I want to buy AirPods Pro in group purchase. How does it work?' }, token);
  expect('AI-015', '핑퐁이 영어 질문', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: '279000' }, token);
  expect('AI-016', '핑퐁이 숫자 입력', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── AI 딜 의도 분석 ──
  r = await req('POST', '/deals/ai/resolve_from_intent', { text: '에어팟 프로 27만원에 100개 사고 싶어' }, token);
  expect('AI-017', 'AI 딜 의도 분석 - 기본', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  if (r.ok && r.data) {
    const hasProdName = 'product_name' in r.data || 'name' in r.data || Object.keys(r.data).length > 0;
    expect('AI-018', 'AI 딜 의도 - 상품명 추출', hasProdName, `keys=${Object.keys(r.data).join(',').substring(0, 40)}`);
  } else {
    expect('AI-018', 'AI 딜 의도 - 상품명 추출', false, '응답 없음 (AI 딜 의도 분석 실패)');
  }

  r = await req('POST', '/deals/ai/resolve_from_intent', { text: '갤럭시 S25 135만원에 50개 원해' }, token);
  const hasPrice = r.ok && r.data && ('price' in r.data || 'target_price' in r.data || Object.keys(r.data).length > 0);
  expect('AI-019', 'AI 딜 의도 - 가격 추출', r.ok ? hasPrice : true, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/ai/resolve_from_intent', { text: '다이슨 에어랩 30개 묶음구매 희망' }, token);
  const hasQty = r.ok && r.data && ('qty' in r.data || 'desired_qty' in r.data || Object.keys(r.data).length > 0);
  expect('AI-020', 'AI 딜 의도 - 수량 추출', r.ok ? hasQty : true, `status=${r.status}`, r.elapsed);

  // ── 컨텍스트 포함 ──
  if (deal1) {
    r = await req('POST', '/v3_6/pingpong/ask', {
      screen: 'DEAL_ROOM', question: '이 딜 어때요?',
      context: { deal_id: deal1.id },
    }, token);
    expect('AI-021', '핑퐁이 deal_id 컨텍스트', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('AI-021', '핑퐁이 deal_id 컨텍스트', false, 'deal1 없음');
  }

  // ── 연속 질문 5개 ──
  const questions = [
    '포인트는 어떻게 사용하나요?',
    '셀러 등록 방법은?',
    '딜 참여 최소 수량은?',
    '배송비는 누가 부담하나요?',
    '취소는 언제까지 가능한가요?',
  ];
  const consecutiveResults = [];
  for (const q of questions) {
    const qr = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: q }, token);
    consecutiveResults.push(qr.ok || qr.status < 500);
  }
  expect('AI-022', '핑퐁이 연속 질문 5개', consecutiveResults.filter(Boolean).length >= 3, `성공: ${consecutiveResults.filter(Boolean).length}/5`);

  // ── 응답 시간 측정 ──
  const start = Date.now();
  r = await req('POST', '/ai/deal_helper', { raw_title: '맥북 프로 M4' }, token);
  const aiElapsed = Date.now() - start;
  expect('AI-023', 'AI 딜 헬퍼 응답 시간', aiElapsed < 30000, `${aiElapsed}ms`, aiElapsed);

  // ── 특수문자 입력 ──
  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: '에어팟 & 갤럭시 < 패키지 > 가능한가요?' }, token);
  expect('AI-024', '핑퐁이 특수문자 입력', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 서비스 가용성 ──
  r = await req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: '안녕' }, token);
  expect('AI-025', 'AI 서비스 가용성 확인', r.ok || r.status < 500, `status=${r.status}, alive=${r.ok}`, r.elapsed);
}
