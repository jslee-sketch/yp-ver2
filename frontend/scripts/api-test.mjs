// scripts/api-test.mjs
// 실행: node scripts/api-test.mjs

const BASE = 'http://127.0.0.1:9000';
const results = [];
let TOKEN = '';
let BUYER_ID = 0;
let DEAL_ID = 0;
let SELLER_ID = 0;
let OFFER_ID = 0;

// ── 유틸 ──

async function request(method, path, body = null, token = null) {
  const url = `${BASE}${path}`;
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  const res = await fetch(url, opts);
  let data = null;
  try { data = await res.json(); } catch {}
  return { status: res.status, ok: res.ok, data };
}

function record(name, pass, detail = '') {
  const icon = pass ? '✅' : '❌';
  results.push({ name, pass, detail });
  console.log(`${icon} ${name}${detail ? ' — ' + detail : ''}`);
}

// ── 테스트 ──

async function test01_health() {
  try {
    const r = await request('GET', '/health');
    record('1. 서버 연결', r.ok, `status=${r.status}`);
  } catch (e) {
    record('1. 서버 연결', false, `연결 실패: ${e.message}`);
  }
}

async function test02_register() {
  const email = `test_${Date.now()}@test.com`;
  const r = await request('POST', '/buyers/', {
    email,
    password: 'Test1234!',
    name: '테스트유저',
    nickname: '테스트유저',
  });

  if (r.ok || r.status === 201) {
    BUYER_ID = r.data?.id || 0;
    record('2. 회원가입', true, `buyer_id=${BUYER_ID}, email=${email}`);
    globalThis.__testEmail = email;
  } else {
    record('2. 회원가입', false, `status=${r.status}, detail=${JSON.stringify(r.data?.detail || r.data)}`);
    globalThis.__testEmail = 'test1@test.com';
  }
}

async function test03_login() {
  const email = globalThis.__testEmail || 'test1@test.com';

  // OAuth2PasswordRequestForm: application/x-www-form-urlencoded + username 필드
  const params = new URLSearchParams();
  params.append('username', email);
  params.append('password', 'Test1234!');

  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  });
  let data = null;
  try { data = await res.json(); } catch {}

  if (res.ok && data?.access_token) {
    TOKEN = data.access_token;
    record('3. 로그인', true, `token=${TOKEN.substring(0, 20)}...`);
  } else {
    record('3. 로그인', false, `status=${res.status}, detail=${JSON.stringify(data?.detail || data)}`);
  }
}

async function test04_buyers_me() {
  if (!TOKEN) { record('4. 내 정보', false, '토큰 없음'); return; }

  const r = await request('GET', '/buyers/me', null, TOKEN);
  if (r.ok && r.data) {
    BUYER_ID = r.data.id || BUYER_ID;
    record('4. 내 정보 (buyers/me)', true, `id=${r.data.id}, name=${r.data.name || r.data.nickname}`);
  } else {
    record('4. 내 정보 (buyers/me)', false, `status=${r.status}`);
  }
}

async function test05_deals_list() {
  const r = await request('GET', '/deals/?skip=0&limit=10');
  if (r.ok) {
    const count = Array.isArray(r.data) ? r.data.length : 0;
    record('5. 딜 목록', true, `${count}개 딜`);
    if (count > 0) DEAL_ID = r.data[0].id;
  } else {
    record('5. 딜 목록', false, `status=${r.status}`);
  }
}

async function test06_deal_create() {
  if (!TOKEN) { record('6. 딜 생성', false, '토큰 없음'); return; }

  const r = await request('POST', '/deals/', {
    product_name: `API테스트 에어팟 ${Date.now()}`,
    desired_qty: 50,
    target_price: 279000,
    brand: 'Apple',
    creator_id: BUYER_ID,
  }, TOKEN);

  if (r.ok || r.status === 201) {
    DEAL_ID = r.data?.id || 0;
    record('6. 딜 생성', true, `deal_id=${DEAL_ID}`);
  } else {
    record('6. 딜 생성', false, `status=${r.status}, detail=${JSON.stringify(r.data?.detail || r.data)}`);
  }
}

async function test07_deal_detail() {
  if (!DEAL_ID) { record('7. 딜 상세', false, 'deal_id 없음'); return; }

  const r = await request('GET', `/deals/${DEAL_ID}`);
  if (r.ok && r.data) {
    record('7. 딜 상세', true, `product=${r.data.product_name}, status=${r.data.status}`);
  } else {
    record('7. 딜 상세', false, `status=${r.status}`);
  }
}

async function test08_deal_participate() {
  if (!DEAL_ID || !BUYER_ID) { record('8. 딜 참여', false, 'ID 없음'); return; }

  const r = await request('POST', `/deals/${DEAL_ID}/participants`, {
    buyer_id: BUYER_ID,
    qty: 3,
  }, TOKEN);

  if (r.ok || r.status === 201) {
    record('8. 딜 참여', true, `participant_id=${r.data?.id}`);
  } else {
    record('8. 딜 참여', false, `status=${r.status}, detail=${JSON.stringify(r.data?.detail || r.data)}`);
  }
}

async function test09_deal_participants() {
  if (!DEAL_ID) { record('9. 참여자 목록', false, 'deal_id 없음'); return; }

  const r = await request('GET', `/deals/${DEAL_ID}/participants`);
  if (r.ok) {
    const count = Array.isArray(r.data) ? r.data.length : 0;
    record('9. 참여자 목록', true, `${count}명 참여`);
  } else {
    record('9. 참여자 목록', false, `status=${r.status}`);
  }
}

async function test10_offers_by_deal() {
  if (!DEAL_ID) { record('10. 딜별 오퍼', false, 'deal_id 없음'); return; }

  const r = await request('GET', `/offers/deal/${DEAL_ID}/ranked`);
  if (r.ok) {
    const count = Array.isArray(r.data) ? r.data.length : (r.data?.offers?.length || 0);
    record('10. 딜별 오퍼 목록', true, `${count}개 오퍼`);
  } else {
    record('10. 딜별 오퍼 목록', false, `status=${r.status}`);
  }
}

async function test11_deal_chat() {
  if (!DEAL_ID) { record('11. 딜 채팅', false, 'deal_id 없음'); return; }

  const sendR = await request('POST', `/deals/${DEAL_ID}/chat/messages`, {
    message: 'API 테스트 메시지입니다!',
    user_id: BUYER_ID,
    user_type: 'buyer',
  }, TOKEN);

  const listR = await request('GET', `/deals/${DEAL_ID}/chat/messages`);

  if (sendR.ok || sendR.status === 201) {
    const count = Array.isArray(listR.data) ? listR.data.length : 0;
    record('11. 딜 채팅', true, `전송 OK, 총 ${count}개 메시지`);
  } else {
    record('11. 딜 채팅', false, `전송 status=${sendR.status}, 조회 status=${listR.status}`);
  }
}

async function test12_notifications() {
  const r = await request('GET', `/notifications?user_id=${BUYER_ID}`, null, TOKEN);
  if (r.ok) {
    const count = Array.isArray(r.data) ? r.data.length : 0;
    record('12. 알림', true, `${count}개 알림`);
  } else {
    record('12. 알림', false, `status=${r.status}`);
  }
}

async function test13_points() {
  if (!BUYER_ID) { record('13. 포인트', false, 'buyer_id 없음'); return; }

  const balR = await request('GET', `/points/buyer/${BUYER_ID}/balance`);
  const txR = await request('GET', `/points/buyer/${BUYER_ID}/transactions`);

  if (balR.ok) {
    record('13. 포인트', true, `잔액=${JSON.stringify(balR.data)}, 내역=${txR.ok ? '조회OK' : '조회실패'}`);
  } else {
    record('13. 포인트', false, `잔액 status=${balR.status}`);
  }
}

async function test14_pingpong() {
  // PingpongAskIn: screen(필수) + question(필수)
  const r = await request('POST', '/v3_6/pingpong/ask', {
    screen: 'FAQ',
    question: '에어팟 싸게 살 수 있어?',
  }, TOKEN);

  if (r.ok && r.data) {
    const answer = typeof r.data === 'string' ? r.data.substring(0, 50) :
                   (r.data.answer || r.data.message || r.data.text || '').substring(0, 50);
    record('14. 핑퐁이', true, `응답: "${answer}..."`);
  } else {
    record('14. 핑퐁이', false, `status=${r.status}`);
  }
}

async function test15_target_update() {
  if (!DEAL_ID) { record('15. 목표가 수정', false, 'deal_id 없음'); return; }

  const r = await request('PATCH', `/deals/${DEAL_ID}/target`, {
    target_price: 265000,
    reason: 'API 테스트: 목표가를 265,000원으로 변경합니다.',
  }, TOKEN);

  if (r.ok) {
    record('15. 목표가 수정', true, `변경 완료`);
  } else {
    record('15. 목표가 수정', false, `status=${r.status}, detail=${JSON.stringify(r.data?.detail || r.data)}`);
  }
}

async function test16_ai_deal_helper() {
  // DealAIRequest: raw_title(필수)
  const r = await request('POST', '/ai/deal_helper', {
    raw_title: '에어팟 프로 2세대',
  }, TOKEN);

  if (r.ok && r.data) {
    record('16. AI 딜 헬퍼', true, `응답 키: ${Object.keys(r.data).join(', ')}`);
  } else {
    record('16. AI 딜 헬퍼', false, `status=${r.status}`);
  }
}

// ── 실행 ──

async function runAll() {
  console.log('═══════════════════════════════════════════');
  console.log('  Phase 2-B: API 자동 테스트');
  console.log(`  백엔드: ${BASE}`);
  console.log(`  시간: ${new Date().toLocaleString('ko-KR')}`);
  console.log('═══════════════════════════════════════════\n');

  await test01_health();

  if (!results[0]?.pass) {
    console.log('\n🔴 서버에 연결할 수 없습니다. 백엔드를 먼저 실행해주세요.');
    printSummary();
    return;
  }

  await test02_register();
  await test03_login();
  await test04_buyers_me();
  await test05_deals_list();
  await test06_deal_create();
  await test07_deal_detail();
  await test08_deal_participate();
  await test09_deal_participants();
  await test10_offers_by_deal();
  await test11_deal_chat();
  await test12_notifications();
  await test13_points();
  await test14_pingpong();
  await test15_target_update();
  await test16_ai_deal_helper();

  printSummary();
}

function printSummary() {
  console.log('\n═══════════════════════════════════════════');
  console.log('  테스트 결과 요약');
  console.log('═══════════════════════════════════════════\n');

  const passed = results.filter(r => r.pass).length;
  const failed = results.filter(r => !r.pass).length;

  console.log(`✅ 성공: ${passed}개`);
  console.log(`❌ 실패: ${failed}개`);
  console.log(`📊 총계: ${results.length}개\n`);

  if (failed > 0) {
    console.log('── 실패 항목 ──');
    results.filter(r => !r.pass).forEach(r => {
      console.log(`  ❌ ${r.name}: ${r.detail}`);
    });
  }

  console.log('\n── 전체 결과 ──');
  results.forEach(r => {
    console.log(`  ${r.pass ? '✅' : '❌'} ${r.name}${r.detail ? ' — ' + r.detail : ''}`);
  });

  console.log('\n── 프론트엔드 수정 필요 사항 ──');

  if (!results.find(r => r.name.includes('3.'))?.pass) {
    console.log('  🔧 로그인 API 응답 구조 확인 → LoginPage.tsx 수정 필요');
  }
  if (!results.find(r => r.name.includes('6.'))?.pass) {
    console.log('  🔧 딜 생성 요청 body 확인 → dealApi.ts / DealCreatePage.tsx 수정 필요');
  }
  if (!results.find(r => r.name.includes('8.'))?.pass) {
    console.log('  🔧 딜 참여 요청 body 확인 → dealApi.ts / DealJoinPage.tsx 수정 필요');
  }
  if (!results.find(r => r.name.includes('11.'))?.pass) {
    console.log('  🔧 채팅 API 요청/응답 확인 → chatApi.ts 수정 필요');
  }
  if (!results.find(r => r.name.includes('14.'))?.pass) {
    console.log('  🔧 핑퐁이 API 요청/응답 확인 → pingpongApi.ts 수정 필요');
  }
}

runAll().catch(err => {
  console.error('테스트 실행 오류:', err);
});
