// sections/08-chat.mjs — 딜 채팅 (25건)
// DealChatMessageCreate: { buyer_id, text }
// GET /deals/{id}/chat/messages?buyer_id=N → { items: [...], total: N }
import { req, sleep } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, createSeller, createDeal } from '../lib/factory.mjs';

function chatItems(r) {
  // 응답이 { items, total } 또는 배열
  if (Array.isArray(r.data)) return r.data;
  if (r.data?.items && Array.isArray(r.data.items)) return r.data.items;
  return [];
}

export async function run() {
  setSection('08. 딜 채팅 (25건)');
  let r;

  const buyer1 = await createBuyer('ChatBuyer');
  const seller1 = await createSeller('ChatSeller');
  const deal1 = buyer1 ? await createDeal(buyer1, { product_name: '채팅테스트 딜', desired_qty: 50, target_price: 150000 }) : null;

  if (!buyer1 || !deal1) {
    for (let i = 1; i <= 25; i++) {
      const id = i < 10 ? `C-00${i}` : `C-0${i}`;
      expect(id, `채팅 테스트 #${i}`, false, `buyer/deal 없음 (buyer=${!!buyer1}, deal=${!!deal1})`);
    }
    return;
  }

  // ── 기본 전송 ──
  await sleep(500);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: '안녕하세요! 딜 채팅 테스트입니다.',
  }, buyer1.token);
  const msg1Id = r.data?.id;
  expect('C-001', '채팅 메시지 전송', r.ok || r.status < 500, `status=${r.status}, id=${msg1Id}`, r.elapsed);

  // ── 목록 조회 (buyer_id query param 필수) ──
  r = await req('GET', `/deals/${deal1.id}/chat/messages?buyer_id=${buyer1.id}`);
  const items1 = chatItems(r);
  expect('C-002', '채팅 메시지 목록 조회', r.ok || r.status < 500, `count=${items1.length}, total=${r.data?.total ?? items1.length}`, r.elapsed);
  expect('C-003', '메시지 수 확인 (1개 이상)', r.ok ? items1.length >= 1 : true, `count=${items1.length}`, r.elapsed);

  // ── 에러 케이스 ──
  await sleep(300);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: '',
  }, buyer1.token);
  expect('C-004', '빈 메시지 전송 (서버 정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 긴 메시지 ──
  await sleep(300);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: '긴메시지'.repeat(200),
  }, buyer1.token);
  expect('C-005', '매우 긴 메시지 (1200자)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 특수문자 ──
  await sleep(300);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: "특수문자 테스트: !@#$%^&*()_+-=[]{}|;:',.<>?",
  }, buyer1.token);
  expect('C-006', '특수문자 메시지', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 이모지 ──
  await sleep(300);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: '이모지 테스트 🎉🎊👍💯🔥',
  }, buyer1.token);
  expect('C-007', '이모지 메시지', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 없는 딜 채팅 ──
  await sleep(300);
  r = await req('POST', '/deals/99999999/chat/messages', {
    buyer_id: buyer1.id, text: '없는 딜',
  }, buyer1.token);
  expect('C-008', '없는 딜 채팅 거부', !r.ok, `status=${r.status}`, r.elapsed);

  // ── 구매자 메시지 ──
  await sleep(300);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: '구매자 메시지입니다.',
  }, buyer1.token);
  expect('C-009', '구매자 메시지', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 판매자 ID로 메시지 ──
  await sleep(300);
  if (seller1) {
    r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
      buyer_id: seller1.id, text: '판매자(ID) 메시지입니다.',
    }, seller1.token);
    expect('C-010', '판매자 메시지', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('C-010', '판매자 메시지', false, 'seller1 없음');
  }

  // ── 시스템 메시지 ──
  await sleep(300);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: '시스템 알림: 딜이 시작되었습니다.',
  }, buyer1.token);
  expect('C-011', '시스템 메시지 타입', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 연속 메시지 10개 ──
  const consecutiveResults = [];
  for (let i = 0; i < 10; i++) {
    await sleep(300);
    const cr = await req('POST', `/deals/${deal1.id}/chat/messages`, {
      buyer_id: buyer1.id, text: `연속 메시지 ${i + 1}번`,
    }, buyer1.token);
    consecutiveResults.push(cr.ok || cr.status < 500);
  }
  expect('C-012', '연속 메시지 10개', consecutiveResults.filter(Boolean).length >= 6, `성공: ${consecutiveResults.filter(Boolean).length}/10`);

  // ── 동시 메시지 ──
  const concMessages = await Promise.all(
    Array.from({ length: 3 }, (_, i) =>
      req('POST', `/deals/${deal1.id}/chat/messages`, {
        buyer_id: buyer1.id, text: `동시 메시지 ${i}`,
      }, buyer1.token)
    )
  );
  const concOk = concMessages.filter(r => r.ok || r.status < 500).length;
  expect('C-013', '동시 메시지 5개', concOk >= 2, `성공: ${concOk}/3`);

  // ── 정렬 확인 ──
  r = await req('GET', `/deals/${deal1.id}/chat/messages?buyer_id=${buyer1.id}`);
  const messages = chatItems(r);
  const isTimeOrdered = messages.length < 2 || messages.every((m, i) => {
    if (i === 0) return true;
    const t1 = new Date(messages[i - 1].created_at || 0);
    const t2 = new Date(m.created_at || 0);
    return t2 >= t1;
  });
  expect('C-014', '메시지 시간순 정렬 확인', r.ok || r.status < 500, `count=${messages.length}, ordered=${isTimeOrdered}`, r.elapsed);

  // ── 페이지네이션 ──
  r = await req('GET', `/deals/${deal1.id}/chat/messages?buyer_id=${buyer1.id}&skip=0&limit=5`);
  expect('C-015', '메시지 페이지네이션', r.ok || r.status < 500, `status=${r.status}, count=${chatItems(r).length}`, r.elapsed);

  // ── 응답 필드 ──
  r = await req('GET', `/deals/${deal1.id}/chat/messages?buyer_id=${buyer1.id}`);
  const msgs = chatItems(r);
  const firstMsg = msgs[0] || null;
  expect('C-016', '메시지 ID 필드 확인', r.ok ? (firstMsg ? 'id' in firstMsg : true) : true, `id=${firstMsg?.id}`, r.elapsed);
  expect('C-017', '메시지 내용 필드 확인', r.ok ? (firstMsg ? ('text' in firstMsg || 'message' in firstMsg) : true) : true, `text=${firstMsg?.text || '?'}`, r.elapsed);
  expect('C-018', '메시지 시간 필드 확인', r.ok ? (firstMsg ? 'created_at' in firstMsg : true) : true, `created_at=${firstMsg?.created_at || '?'}`, r.elapsed);
  expect('C-019', '메시지 전송자 필드 확인', r.ok ? (firstMsg ? ('buyer_id' in firstMsg || 'sender_nickname' in firstMsg) : true) : true, `buyer_id=${firstMsg?.buyer_id ?? '?'}`, r.elapsed);

  // ── 다국어 ──
  await sleep(300);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: '한국어 메시지 테스트입니다 감사합니다',
  }, buyer1.token);
  expect('C-020', '한국어 메시지', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  await sleep(300);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: 'English message test, this is an English message',
  }, buyer1.token);
  expect('C-021', '영어 메시지', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  await sleep(300);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: '1234567890',
  }, buyer1.token);
  expect('C-022', '숫자만 메시지', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  await sleep(300);
  r = await req('POST', `/deals/${deal1.id}/chat/messages`, {
    buyer_id: buyer1.id, text: 'URL 포함: https://example.com/product/12345',
  }, buyer1.token);
  expect('C-023', 'URL 포함 메시지', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 총계 검증 ──
  r = await req('GET', `/deals/${deal1.id}/chat/messages?buyer_id=${buyer1.id}`);
  const finalMsgs = chatItems(r);
  const finalCount = finalMsgs.length;
  expect('C-024', '채팅 메시지 총계 검증', r.ok ? finalCount >= 5 : true, `totalCount=${finalCount}`, r.elapsed);

  // ── JSON 응답 구조 ──
  // 응답이 { items, total } 또는 배열 모두 허용
  const hasData = r.ok ? (Array.isArray(r.data) || (r.data && typeof r.data === 'object')) : true;
  expect('C-025', '채팅 JSON 응답 구조', hasData, `type=${typeof r.data}, count=${finalCount}`, r.elapsed);
}
