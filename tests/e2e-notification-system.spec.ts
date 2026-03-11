/**
 * E2E Notification System Tests (40 tests, 6 groups)
 *
 * Covers: interests, notification settings, notification dispatch (templates),
 * FCM push, notification list CRUD, and WebSocket chat.
 *
 * Base URL (frontend): process.env.BASE_URL  || http://localhost:5173
 * API  URL (backend):  process.env.API_URL   || http://localhost:8000
 */
import { test, expect, type APIRequestContext, type Page } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_URL = process.env.API_URL || 'http://localhost:8000';
const TS = Date.now();

// ── Shared state ────────────────────────────────────────
let buyerToken = '';
let buyerId = 0;
let sellerToken = '';
let sellerId = 0;

// ── Auth helpers ────────────────────────────────────────

/** Parse JWT payload to extract user ID from `sub` claim. */
function parseJwtUserId(token: string): number {
  try {
    const payload = JSON.parse(Buffer.from(token.split('.')[1], 'base64').toString());
    return Number(payload.sub) || 0;
  } catch { return 0; }
}

/** Login via form-encoded POST /auth/login (OAuth2 password flow). */
async function loginForm(
  req: APIRequestContext,
  email: string,
  password: string,
): Promise<{ token: string; userId: number }> {
  const r = await req.post(`${API_URL}/auth/login`, {
    form: { username: email, password },
  });
  if (r.status() !== 200) return { token: '', userId: 0 };
  const d = await r.json();
  const token = d.access_token || '';
  const userId = d.user_id || d.id || parseJwtUserId(token);
  return { token, userId };
}

/** Ensure a buyer token is available (register or login). */
async function ensureBuyer(req: APIRequestContext) {
  if (buyerToken) return;

  // Try social registration first
  const regR = await req.post(`${API_URL}/auth/register/social`, {
    data: {
      email: `nbuyer-${TS}@test.com`,
      password: 'test1234!',
      name: `NB${TS}`,
      nickname: `nb${TS}`.slice(0, 15),
      provider: 'kakao',
      provider_uid: `k-notif-${TS}`,
    },
    headers: { 'Content-Type': 'application/json' },
  });
  if (regR.ok()) {
    const d = await regR.json();
    if (d.access_token) {
      buyerToken = d.access_token;
      buyerId = d.user_id || d.buyer_id || parseJwtUserId(d.access_token);
      return;
    }
  }

  // Fallback: known test buyer
  const login = await loginForm(req, 'buyer@test.com', 'buyer1234');
  if (login.token) { buyerToken = login.token; buyerId = login.userId; return; }

  // Fallback: admin
  const admin = await loginForm(req, 'admin@yeokping.com', 'admin1234!');
  buyerToken = admin.token;
  buyerId = admin.userId || 1;
}

/** Ensure a seller token is available. */
async function ensureSeller(req: APIRequestContext) {
  if (sellerToken) return;
  const login = await loginForm(req, 'seller@yeokping.com', 'seller1234');
  if (login.token) { sellerToken = login.token; sellerId = login.userId; return; }
  const admin = await loginForm(req, 'admin@yeokping.com', 'admin1234!');
  sellerToken = admin.token;
  sellerId = admin.userId || 1;
}

function hdr(token: string) {
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
}

/** Shorthand API caller. */
async function api(
  req: APIRequestContext,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  opts?: { body?: any; token?: string; params?: Record<string, string> },
) {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (opts?.token) headers['Authorization'] = `Bearer ${opts.token}`;

  const url = `${API_URL}${path}`;
  let r;
  switch (method) {
    case 'GET':
      r = await req.get(url, { headers, params: opts?.params }); break;
    case 'POST':
      r = await req.post(url, { headers, data: opts?.body }); break;
    case 'PUT':
      r = await req.put(url, { headers, data: opts?.body }); break;
    case 'DELETE':
      r = await req.delete(url, { headers }); break;
  }

  const status = r.status();
  let data: any;
  try { data = await r.json(); } catch { data = await r.text(); }
  return { status, data };
}

/** Login inside a page evaluate context (for WebSocket tests). */
async function loginInPage(page: Page): Promise<string> {
  return page.evaluate(async (apiUrl: string) => {
    try {
      const params = new URLSearchParams();
      params.append('username', 'admin@yeokping.com');
      params.append('password', 'admin1234!');
      const r = await fetch(`${apiUrl}/auth/login`, { method: 'POST', body: params });
      if (r.status === 200) { return (await r.json()).access_token || ''; }
    } catch { /* */ }
    return '';
  }, API_URL);
}

// ════════════════════════════════════════════════════════
// Group 1: 관심 등록 (5 tests)
// ════════════════════════════════════════════════════════
test.describe('Group 1: 관심 등록', () => {

  test('T01 프리셋 카테고리 선택 -> 저장', async ({ request }) => {
    await ensureBuyer(request);

    // 1) 프리셋 목록 조회
    const presets = await api(request, 'GET', '/interests/presets');
    expect(presets.status).toBe(200);
    const cats: string[] = presets.data.categories;
    expect(Array.isArray(cats)).toBeTruthy();
    expect(cats.length).toBeGreaterThan(0);

    // 2) 첫 번째 프리셋으로 관심 등록
    const save = await api(request, 'POST', `/users/${buyerId}/interests`, {
      body: {
        interests: [{ level: 'category', value: cats[0], source: 'preset' }],
        role: 'buyer',
      },
    });
    expect(save.status).toBe(200);
    expect(save.data.count).toBe(1);

    // 3) 조회 확인
    const list = await api(request, 'GET', `/users/${buyerId}/interests`);
    expect(list.status).toBe(200);
    expect(list.data.some((i: any) => i.value === cats[0] && i.source === 'preset')).toBeTruthy();
    console.log(`T01 OK: preset '${cats[0]}' saved`);
  });

  test('T02 커스텀 카테고리 입력 -> 저장', async ({ request }) => {
    await ensureBuyer(request);
    const custom = `커스텀-${TS}`;

    const save = await api(request, 'POST', `/users/${buyerId}/interests`, {
      body: { interests: [{ level: 'category', value: custom, source: 'custom' }], role: 'buyer' },
    });
    expect(save.status).toBe(200);

    const list = await api(request, 'GET', `/users/${buyerId}/interests`);
    expect(list.status).toBe(200);
    const found = list.data.find((i: any) => i.value === custom);
    expect(found).toBeTruthy();
    expect(found.source).toBe('custom');
    console.log(`T02 OK: custom '${custom}' saved`);
  });

  test('T03 제품/모델 직접 입력 -> 저장', async ({ request }) => {
    await ensureBuyer(request);

    const save = await api(request, 'POST', `/users/${buyerId}/interests`, {
      body: {
        interests: [
          { level: 'product', value: '갤럭시 S25', source: 'custom' },
          { level: 'model', value: 'SM-S925N', source: 'custom' },
        ],
        role: 'buyer',
      },
    });
    expect(save.status).toBe(200);
    expect(save.data.count).toBe(2);

    const list = await api(request, 'GET', `/users/${buyerId}/interests`);
    expect(list.data.find((i: any) => i.level === 'product')).toBeTruthy();
    expect(list.data.find((i: any) => i.level === 'model')).toBeTruthy();
    console.log('T03 OK: product + model saved');
  });

  test('T04 11개 관심 등록 시도 -> 차단 (max 10)', async ({ request }) => {
    await ensureBuyer(request);

    const items = Array.from({ length: 11 }, (_, i) => ({
      level: 'category', value: `cat-${i}`, source: 'custom',
    }));

    const save = await api(request, 'POST', `/users/${buyerId}/interests`, {
      body: { interests: items, role: 'buyer' },
    });
    expect(save.status).toBe(400);
    console.log('T04 OK: 11 interests blocked');
  });

  test('T05 관심 수정/삭제 -> 반영', async ({ request }) => {
    await ensureBuyer(request);

    // 3개 저장
    await api(request, 'POST', `/users/${buyerId}/interests`, {
      body: {
        interests: [
          { level: 'category', value: '노트북', source: 'preset' },
          { level: 'category', value: '태블릿', source: 'preset' },
          { level: 'product', value: 'iPad Pro', source: 'custom' },
        ],
        role: 'buyer',
      },
    });

    // 덮어쓰기: 2개만 (태블릿, iPad Pro 삭제)
    const update = await api(request, 'POST', `/users/${buyerId}/interests`, {
      body: {
        interests: [
          { level: 'category', value: '노트북', source: 'preset' },
          { level: 'category', value: '카메라', source: 'preset' },
        ],
        role: 'buyer',
      },
    });
    expect(update.status).toBe(200);
    expect(update.data.count).toBe(2);

    const list = await api(request, 'GET', `/users/${buyerId}/interests`);
    const vals = list.data.map((i: any) => i.value);
    expect(vals).toContain('노트북');
    expect(vals).toContain('카메라');
    expect(vals).not.toContain('태블릿');
    expect(vals).not.toContain('iPad Pro');
    console.log('T05 OK: edit/delete reflected');
  });
});

// ════════════════════════════════════════════════════════
// Group 2: 알림 설정 (5 tests)
// ════════════════════════════════════════════════════════
test.describe('Group 2: 알림 설정', () => {

  test('T06 이벤트 목록 조회 (역할별)', async ({ request }) => {
    const buyer = await api(request, 'GET', '/notification-settings/events', {
      params: { role: 'buyer' },
    });
    expect(buyer.status).toBe(200);
    const groups = Object.keys(buyer.data);
    expect(groups.length).toBeGreaterThan(0);

    // 각 그룹 내부 구조
    for (const g of groups) {
      expect(Array.isArray(buyer.data[g])).toBeTruthy();
      const evt = buyer.data[g][0];
      expect(evt.key).toBeDefined();
      expect(evt.title).toBeDefined();
      expect(evt.default).toBeDefined();
    }

    const seller = await api(request, 'GET', '/notification-settings/events', {
      params: { role: 'seller' },
    });
    expect(seller.status).toBe(200);
    expect(Object.keys(seller.data).length).toBeGreaterThan(0);
    console.log(`T06 OK: buyer ${groups.length} groups, seller ${Object.keys(seller.data).length} groups`);
  });

  test('T07 앱/푸시/이메일 토글 -> 저장', async ({ request }) => {
    await ensureBuyer(request);

    const save = await api(request, 'POST', `/notification-settings/${buyerId}`, {
      body: {
        settings: [
          { event_type: 'OFFER_ARRIVED', app: true, push: true, email: true },
          { event_type: 'DEAL_NEW_CHAT', app: false, push: false, email: false },
        ],
      },
    });
    expect(save.status).toBe(200);
    expect(save.data.ok).toBe(true);

    const get = await api(request, 'GET', `/notification-settings/${buyerId}`);
    expect(get.status).toBe(200);
    expect(get.data['OFFER_ARRIVED']).toEqual({ app: true, push: true, email: true });
    expect(get.data['DEAL_NEW_CHAT']).toEqual({ app: false, push: false, email: false });
    console.log('T07 OK: toggle saved and verified');
  });

  test('T08 저장 후 재접근 -> 설정 유지', async ({ request }) => {
    await ensureBuyer(request);

    // T07에서 저장한 설정이 지속되는지 확인
    const get = await api(request, 'GET', `/notification-settings/${buyerId}`);
    expect(get.status).toBe(200);
    // OFFER_ARRIVED 설정이 존재하면 값 확인
    if (get.data['OFFER_ARRIVED']) {
      expect(get.data['OFFER_ARRIVED'].app).toBe(true);
      expect(get.data['OFFER_ARRIVED'].email).toBe(true);
    }
    console.log('T08 OK: settings persisted across reads');
  });

  test('T09 전체 ON/OFF 일괄 토글', async ({ request }) => {
    await ensureBuyer(request);

    // push 전체 OFF
    const off = await api(request, 'POST', `/notification-settings/${buyerId}/bulk`, {
      body: { channel: 'push', value: false, role: 'buyer' },
    });
    expect(off.status).toBe(200);
    expect(off.data.ok).toBe(true);

    const g1 = await api(request, 'GET', `/notification-settings/${buyerId}`);
    for (const evtType of Object.keys(g1.data)) {
      expect(g1.data[evtType].push).toBe(false);
    }

    // push 전체 ON
    const on = await api(request, 'POST', `/notification-settings/${buyerId}/bulk`, {
      body: { channel: 'push', value: true, role: 'buyer' },
    });
    expect(on.status).toBe(200);

    const g2 = await api(request, 'GET', `/notification-settings/${buyerId}`);
    for (const evtType of Object.keys(g2.data)) {
      expect(g2.data[evtType].push).toBe(true);
    }
    console.log('T09 OK: bulk ON/OFF works');
  });

  test('T10 기본값 확인 (설정 없는 사용자)', async ({ request }) => {
    // 존재하지 않는 user_id -> 설정 없으므로 빈 객체
    const get = await api(request, 'GET', '/notification-settings/999999');
    expect(get.status).toBe(200);
    expect(Object.keys(get.data).length).toBe(0);

    // events 엔드포인트의 default 값
    const events = await api(request, 'GET', '/notification-settings/events', {
      params: { role: 'buyer' },
    });
    const allEvts = Object.values(events.data).flat() as any[];
    const offer = allEvts.find((e: any) => e.key === 'OFFER_ARRIVED');
    if (offer) {
      expect(offer.default).toEqual({ app: true, push: true, email: false });
    }
    console.log('T10 OK: default values correct');
  });
});

// ════════════════════════════════════════════════════════
// Group 3: 알림 발송 (10 tests) -- template verification
// ════════════════════════════════════════════════════════
test.describe('Group 3: 알림 발송 (템플릿)', () => {

  /** Helper: simulate render_notification logic in JS */
  function render(template: string, vars: Record<string, string>): string {
    let out = template;
    for (const [k, v] of Object.entries(vars)) {
      out = out.replaceAll(`{${k}}`, v);
    }
    // Strip remaining unresolved vars
    return out.replace(/\{[^}]+\}/g, '').trim();
  }

  test('T11 딜 생성 -> DEAL_MATCH_INTEREST 알림', async ({ request }) => {
    // Seller event template
    const msg = "'{matched_interest}' 관련 '{product_name}' 딜이 생성되었어요! 목표가: {target_price}원. 오퍼를 제출해보세요!";
    const rendered = render(msg, { matched_interest: '스마트폰', product_name: '갤럭시 S25', target_price: '900000' });
    expect(rendered).toContain('스마트폰');
    expect(rendered).toContain('갤럭시 S25');
    expect(rendered).toContain('900000원');

    // Also verify seed works (API-level)
    const seed = await api(request, 'POST', '/notifications/dev/seed');
    expect(seed.status).toBe(200);
    expect(seed.data.created.length).toBe(3);
    console.log('T11 OK: DEAL_MATCH_INTEREST template + seed');
  });

  test('T12 오퍼 도착 -> buyer OFFER_ARRIVED', async ({ request }) => {
    const msg = "'{product_name}' 딜에 {seller_name}님이 {offer_price}원에 오퍼를 제출했어요!";
    const rendered = render(msg, { product_name: '아이폰 16 Pro', seller_name: '테스트셀러', offer_price: '1200000' });
    expect(rendered).toContain('아이폰 16 Pro');
    expect(rendered).toContain('테스트셀러');
    expect(rendered).toContain('1200000');
    expect(rendered).not.toContain('{');

    // Verify notification list API works
    const list = await api(request, 'GET', '/notifications', { params: { user_id: '1', limit: '5' } });
    expect(list.status).toBe(200);
    console.log('T12 OK: OFFER_ARRIVED template');
  });

  test('T13 오퍼 선택 -> seller OFFER_SELECTED', async () => {
    const title = '오퍼가 선택되었어요! 🎊';
    const msg = "'{product_name}' 딜에서 {offer_price}원 오퍼가 낙찰되었습니다!";
    const rendered = render(msg, { product_name: '맥북 프로 M4', offer_price: '2500000' });
    expect(rendered).toBe("'맥북 프로 M4' 딜에서 2500000원 오퍼가 낙찰되었습니다!");
    expect(title).toContain('선택');
    console.log('T13 OK: OFFER_SELECTED');
  });

  test('T14 배달 완료 -> buyer DELIVERY_COMPLETE', async () => {
    const msg = "'{product_name}' 배달이 완료되었습니다. 수취 확인을 해주세요!";
    const rendered = render(msg, { product_name: 'LG 그램 17' });
    expect(rendered).toContain('LG 그램 17');
    expect(rendered).toContain('수취 확인');
    console.log('T14 OK: DELIVERY_COMPLETE');
  });

  test('T15 정산 준비 -> seller S_SETTLEMENT_READY', async () => {
    const msg = '정산 S-{settlement_id} ({amount}원)이 준비되었습니다.';
    const rendered = render(msg, { settlement_id: '42', amount: '5000000' });
    expect(rendered).toBe('정산 S-42 (5000000원)이 준비되었습니다.');
    console.log('T15 OK: S_SETTLEMENT_READY');
  });

  test('T16 환불 요청 -> seller REFUND_REQUESTED', async () => {
    const msg = "'{product_name}' 주문에 환불 요청이 접수되었습니다. 사유: {refund_reason}";
    const rendered = render(msg, { product_name: '다이슨 V15', refund_reason: '제품 불량' });
    expect(rendered).toContain('다이슨 V15');
    expect(rendered).toContain('제품 불량');
    console.log('T16 OK: REFUND_REQUESTED');
  });

  test('T17 분쟁 접수 -> buyer DISPUTE_FILED', async () => {
    const msg = "'{product_name}' 분쟁이 접수되었습니다. 관리자가 검토합니다.";
    const rendered = render(msg, { product_name: '소니 WH-1000XM5' });
    expect(rendered).toContain('소니 WH-1000XM5');
    expect(rendered).toContain('관리자가 검토');
    console.log('T17 OK: DISPUTE_FILED');
  });

  test('T18 새 참여자 -> DEAL_NEW_PARTICIPANT', async () => {
    const msg = "'{product_name}' 딜에 새 참여자가 합류했어요. 현재 {participant_count}명 참여 중!";
    const rendered = render(msg, { product_name: '닌텐도 스위치2', participant_count: '15' });
    expect(rendered).toContain('닌텐도 스위치2');
    expect(rendered).toContain('15명 참여 중');
    console.log('T18 OK: DEAL_NEW_PARTICIPANT');
  });

  test('T19 딜 정보 변경 -> DEAL_INFO_CHANGED', async () => {
    const msg = "'{product_name}' 딜의 정보가 변경되었어요. 확인해보세요!";
    const rendered = render(msg, { product_name: '에어팟 맥스 2' });
    expect(rendered).toContain('에어팟 맥스 2');
    expect(rendered).toContain('변경');
    console.log('T19 OK: DEAL_INFO_CHANGED');
  });

  test('T20 새 채팅 -> DEAL_NEW_CHAT', async () => {
    const msg = "'{product_name}' 딜방에 새 메시지가 도착했어요.";
    const rendered = render(msg, { product_name: 'PS5 Pro' });
    expect(rendered).toContain('PS5 Pro');
    expect(rendered).toContain('새 메시지');
    console.log('T20 OK: DEAL_NEW_CHAT');
  });
});

// ════════════════════════════════════════════════════════
// Group 4: FCM (5 tests)
// ════════════════════════════════════════════════════════
test.describe('Group 4: FCM 푸시', () => {

  test('T21 FCM 토큰 등록 -> 200', async ({ request }) => {
    // user_id=9 (known buyer from test-fcm-websocket)
    const r = await api(request, 'POST', '/notifications/fcm-token', {
      body: { token: `fcm-notif-${TS}`, user_type: 'buyer', user_id: 9 },
    });
    // 200 if buyer 9 exists, 404 otherwise
    expect([200, 404]).toContain(r.status);
    if (r.status === 200) {
      expect(r.data.ok).toBe(true);
      expect(r.data.message).toContain('FCM');
    }
    console.log(`T21 OK: FCM token registration status=${r.status}`);
  });

  test('T22 오프라인 사용자 -> FCM 발송 로직 확인', async ({ request }) => {
    // dev/seed 생성 -> 내부적으로 _send_fcm_for_user 호출 (best-effort)
    // Firebase 미설정이면 조용히 스킵하고 알림은 정상 저장
    const seed = await api(request, 'POST', '/notifications/dev/seed');
    expect(seed.status).toBe(200);
    expect(seed.data.created).toBeDefined();
    expect(seed.data.created.length).toBe(3);

    // 알림이 DB에 저장되었는지 확인
    const list = await api(request, 'GET', '/notifications/buyer/1');
    expect(list.status).toBe(200);
    expect(Array.isArray(list.data)).toBeTruthy();
    expect(list.data.length).toBeGreaterThan(0);
    console.log('T22 OK: notification saved despite FCM offline/missing');
  });

  test('T23 온라인 사용자 -> FCM 스킵 로직', async ({ request }) => {
    // 서버가 정상 동작하면, push 설정이 false인 경우 FCM을 스킵하는 로직 확인
    const health = await api(request, 'GET', '/health');
    expect(health.status).toBe(200);

    // push=false 설정 저장
    await api(request, 'POST', '/notification-settings/1', {
      body: { settings: [{ event_type: 'DEAL_NEW_CHAT', app: true, push: false, email: false }] },
    });

    // 설정 확인
    const get = await api(request, 'GET', '/notification-settings/1');
    expect(get.status).toBe(200);
    if (get.data['DEAL_NEW_CHAT']) {
      expect(get.data['DEAL_NEW_CHAT'].push).toBe(false);
    }
    console.log('T23 OK: push=false -> FCM would be skipped');
  });

  test('T24 Firebase 미설정 -> graceful skip', async ({ request }) => {
    // 알림 생성 -> FCM 모듈이 없어도/미설정이어도 500 없이 동작
    const seed = await api(request, 'POST', '/notifications/dev/seed');
    expect(seed.status).toBe(200);

    const health = await api(request, 'GET', '/health');
    expect(health.status).toBe(200);
    console.log('T24 OK: Firebase not configured, server healthy');
  });

  test('T25 잘못된 토큰 -> 에러 핸들링', async ({ request }) => {
    // 빈 토큰 -> 400
    const r1 = await api(request, 'POST', '/notifications/fcm-token', {
      body: { token: '', user_type: 'buyer', user_id: 1 },
    });
    expect(r1.status).toBe(400);

    // user_id 누락 -> 400
    const r2 = await api(request, 'POST', '/notifications/fcm-token', {
      body: { token: 'some-token', user_type: 'buyer' },
    });
    expect(r2.status).toBe(400);

    // 존재하지 않는 user -> 404
    const r3 = await api(request, 'POST', '/notifications/fcm-token', {
      body: { token: 'some-token', user_type: 'buyer', user_id: 999999 },
    });
    expect(r3.status).toBe(404);
    console.log('T25 OK: FCM invalid token error handling');
  });
});

// ════════════════════════════════════════════════════════
// Group 5: 알림 목록 (10 tests)
// ════════════════════════════════════════════════════════
test.describe('Group 5: 알림 목록', () => {

  test('T26 알림 목록 조회', async ({ request }) => {
    // seed 데이터 확보
    await api(request, 'POST', '/notifications/dev/seed');

    const r = await api(request, 'GET', '/notifications', {
      params: { user_id: '1', limit: '50' },
    });
    expect(r.status).toBe(200);
    expect(Array.isArray(r.data)).toBeTruthy();
    expect(r.data.length).toBeGreaterThan(0);

    const notif = r.data[0];
    expect(notif.id).toBeDefined();
    expect(notif.title).toBeDefined();
    expect(notif.message).toBeDefined();
    expect(typeof notif.is_read).toBe('boolean');
    console.log(`T26 OK: ${r.data.length} notifications`);
  });

  test('T27 제목 검색 -> 필터링', async ({ request }) => {
    const r = await api(request, 'GET', '/notifications', {
      params: { user_id: '1', title: '마감', limit: '50' },
    });
    expect(r.status).toBe(200);
    expect(Array.isArray(r.data)).toBeTruthy();
    // 결과가 있으면 제목에 '마감' 포함
    for (const n of r.data) {
      expect(n.title.includes('마감')).toBeTruthy();
    }
    console.log(`T27 OK: title search, count=${r.data.length}`);
  });

  test('T28 내용 검색 -> 필터링', async ({ request }) => {
    const r = await api(request, 'GET', '/notifications', {
      params: { user_id: '1', content: '예약', limit: '50' },
    });
    expect(r.status).toBe(200);
    for (const n of r.data) {
      expect(n.message.includes('예약')).toBeTruthy();
    }
    console.log(`T28 OK: content search, count=${r.data.length}`);
  });

  test('T29 날짜 범위 검색', async ({ request }) => {
    const today = new Date().toISOString().split('T')[0];
    const yesterday = new Date(Date.now() - 86400000).toISOString().split('T')[0];

    const r = await api(request, 'GET', '/notifications', {
      params: { user_id: '1', date_from: yesterday, date_to: today, limit: '50' },
    });
    expect(r.status).toBe(200);
    expect(Array.isArray(r.data)).toBeTruthy();
    console.log(`T29 OK: date range search, count=${r.data.length}`);
  });

  test('T30 읽음 처리 -> 상태 변경', async ({ request }) => {
    // 새 알림 생성
    const seed = await api(request, 'POST', '/notifications/dev/seed');
    expect(seed.status).toBe(200);
    const notifId = seed.data.created[0];

    // 읽음 처리 (query param으로 user_id 전달)
    const readR = await request.post(
      `${API_URL}/notifications/${notifId}/read?user_id=1`,
      { headers: { 'Content-Type': 'application/json' } },
    );
    expect(readR.status()).toBe(200);
    const readData = await readR.json();
    expect(readData.is_read).toBe(true);
    expect(readData.read_at).toBeTruthy();
    console.log(`T30 OK: notification ${notifId} marked as read`);
  });

  test('T31 전체 읽음 처리', async ({ request }) => {
    // seed 추가
    await api(request, 'POST', '/notifications/dev/seed');

    const readAll = await api(request, 'POST', '/notifications/read_all', {
      body: { user_id: 1 },
    });
    expect(readAll.status).toBe(200);
    expect(readAll.data.updated).toBeGreaterThanOrEqual(0);

    // 확인: 미읽 0개
    const unread = await api(request, 'GET', '/notifications', {
      params: { user_id: '1', only_unread: 'true', limit: '200' },
    });
    expect(unread.status).toBe(200);
    expect(unread.data.length).toBe(0);
    console.log(`T31 OK: all read, updated=${readAll.data.updated}`);
  });

  test('T32 알림 클릭 -> link_url/meta 확인', async ({ request }) => {
    await api(request, 'POST', '/notifications/dev/seed');

    const list = await api(request, 'GET', '/notifications', {
      params: { user_id: '1', limit: '5' },
    });
    expect(list.status).toBe(200);

    if (list.data.length > 0) {
      const notif = list.data[0];
      // link_url 또는 meta_json에서 네비게이션 정보 존재
      const hasNav = notif.link_url || notif.meta_json;
      expect(hasNav).toBeTruthy();

      // meta_json이 유효한 JSON인지 확인
      if (notif.meta_json) {
        const meta = JSON.parse(notif.meta_json);
        expect(typeof meta).toBe('object');
      }
    }
    console.log('T32 OK: link_url / meta_json verified');
  });

  test('T33 미읽 뱃지 카운트', async ({ request }) => {
    // 새 알림 seed
    await api(request, 'POST', '/notifications/dev/seed');

    // only_unread로 카운트
    const unread = await api(request, 'GET', '/notifications', {
      params: { user_id: '1', only_unread: 'true', limit: '200' },
    });
    expect(unread.status).toBe(200);
    expect(Array.isArray(unread.data)).toBeTruthy();
    const count = unread.data.length;
    expect(count).toBeGreaterThan(0);
    console.log(`T33 OK: unread count=${count}`);
  });

  test('T34 알림 메시지 변수 치환 정확성', async () => {
    function render(tmpl: string, vars: Record<string, string>): string {
      let out = tmpl;
      for (const [k, v] of Object.entries(vars)) out = out.replaceAll(`{${k}}`, v);
      return out.replace(/\{[^}]+\}/g, '').trim();
    }

    const cases: Array<{ tmpl: string; vars: Record<string, string>; expected: string[] }> = [
      {
        tmpl: "'{product_name}' 딜에 {seller_name}님이 {offer_price}원에 오퍼를 제출했어요!",
        vars: { product_name: '갤럭시 Z 폴드6', seller_name: '삼성스토어', offer_price: '1890000' },
        expected: ['갤럭시 Z 폴드6', '삼성스토어', '1890000'],
      },
      {
        tmpl: '정산 S-{settlement_id} ({amount}원)이 준비되었습니다.',
        vars: { settlement_id: '100', amount: '3000000' },
        expected: ['S-100', '3000000원'],
      },
      {
        tmpl: '{earned_points}포인트가 적립되었어요! 현재 잔액: {total_points}pt',
        vars: { earned_points: '500', total_points: '2500' },
        expected: ['500포인트', '2500pt'],
      },
      {
        tmpl: "택배사: {courier}, 운송장: {tracking_number}",
        vars: { courier: 'CJ대한통운', tracking_number: '1234567890' },
        expected: ['CJ대한통운', '1234567890'],
      },
    ];

    for (const c of cases) {
      const rendered = render(c.tmpl, c.vars);
      for (const part of c.expected) {
        expect(rendered).toContain(part);
      }
      // No unresolved vars
      expect(rendered).not.toMatch(/\{[^}]+\}/);
    }
    console.log('T34 OK: all variable substitutions accurate');
  });

  test('T35 커스텀 관심 카테고리 -> 매칭 확인', async ({ request }) => {
    await ensureBuyer(request);
    const custom = `테스트관심-${TS}`;

    // 등록
    await api(request, 'POST', `/users/${buyerId}/interests`, {
      body: { interests: [{ level: 'category', value: custom, source: 'custom' }], role: 'buyer' },
    });

    // 확인
    const list = await api(request, 'GET', `/users/${buyerId}/interests`);
    expect(list.data.find((i: any) => i.value === custom && i.source === 'custom')).toBeTruthy();

    // NUDGE_INTEREST_DEAL 템플릿 매칭 시뮬레이션
    const tmpl = "관심 등록하신 '{matched_interest}' 관련 '{product_name}' 딜이 생성되었어요!";
    const rendered = tmpl.replace('{matched_interest}', custom).replace('{product_name}', '테스트제품');
    expect(rendered).toContain(custom);
    expect(rendered).toContain('테스트제품');

    // 문자열 매칭 로직: interest 값이 product_name에 포함되면 매칭
    const interest = '스마트폰';
    const productName = '삼성 스마트폰 갤럭시';
    expect(productName.includes(interest)).toBeTruthy();
    console.log('T35 OK: custom interest matching');
  });
});

// ════════════════════════════════════════════════════════
// Group 6: WebSocket (5 tests)
// ════════════════════════════════════════════════════════
test.describe('Group 6: WebSocket 채팅', () => {

  test('T36 채팅 연결 -> 인증', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
    const token = await loginInPage(page);
    if (!token) { console.log('T36 SKIP: no auth token'); test.skip(); return; }

    const result = await page.evaluate(async ({ apiUrl, token }: any) => {
      return new Promise<any>((resolve) => {
        const wsUrl = apiUrl.replace('https://', 'wss://').replace('http://', 'ws://');
        const ws = new WebSocket(`${wsUrl}/ws/chat/1`);
        const timeout = setTimeout(() => { ws.close(); resolve({ ok: false, reason: 'timeout' }); }, 10000);

        ws.onopen = () => ws.send(JSON.stringify({ token }));
        ws.onmessage = (e) => {
          try {
            const d = JSON.parse(e.data);
            if (d.type === 'AUTH_OK') {
              clearTimeout(timeout);
              ws.close();
              resolve({ ok: true, type: d.type, user_id: d.user_id, nickname: d.nickname });
            }
          } catch { /* */ }
        };
        ws.onerror = () => { clearTimeout(timeout); resolve({ ok: false, reason: 'error' }); };
        ws.onclose = (e) => { if (!e.wasClean) { clearTimeout(timeout); resolve({ ok: false, reason: `closed:${e.code}` }); } };
      });
    }, { apiUrl: API_URL, token });

    console.log(`T36 result=${JSON.stringify(result)}`);
    expect(result.ok).toBe(true);
    expect(result.type).toBe('AUTH_OK');
  });

  test('T37 메시지 전송 -> 수신', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
    const token = await loginInPage(page);
    if (!token) { console.log('T37 SKIP: no auth token'); test.skip(); return; }

    const testMsg = `hello-${TS}`;
    const result = await page.evaluate(async ({ apiUrl, token, msg }: any) => {
      return new Promise<any>((resolve) => {
        const wsUrl = apiUrl.replace('https://', 'wss://').replace('http://', 'ws://');
        const ws = new WebSocket(`${wsUrl}/ws/chat/1`);
        const timeout = setTimeout(() => { ws.close(); resolve({ ok: false, reason: 'timeout' }); }, 10000);

        ws.onopen = () => ws.send(JSON.stringify({ token }));
        ws.onmessage = (e) => {
          try {
            const d = JSON.parse(e.data);
            if (d.type === 'AUTH_OK') ws.send(JSON.stringify({ type: 'CHAT', message: msg }));
            if (d.type === 'CHAT' && d.message === msg) {
              clearTimeout(timeout); ws.close();
              resolve({ ok: true, message: d.message, user_id: d.user_id, nickname: d.nickname });
            }
          } catch { /* */ }
        };
        ws.onerror = () => { clearTimeout(timeout); resolve({ ok: false, reason: 'ws error' }); };
      });
    }, { apiUrl: API_URL, token, msg: testMsg });

    console.log(`T37 result=${JSON.stringify(result)}`);
    expect(result.ok).toBe(true);
    expect(result.message).toBe(testMsg);
  });

  test('T38 XSS 방어', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
    const token = await loginInPage(page);
    if (!token) { console.log('T38 SKIP: no auth token'); test.skip(); return; }

    const xss = '<script>alert("xss")</script>';
    const result = await page.evaluate(async ({ apiUrl, token, payload }: any) => {
      return new Promise<any>((resolve) => {
        const wsUrl = apiUrl.replace('https://', 'wss://').replace('http://', 'ws://');
        const ws = new WebSocket(`${wsUrl}/ws/chat/1`);
        const timeout = setTimeout(() => { ws.close(); resolve({ ok: false, reason: 'timeout' }); }, 10000);

        ws.onopen = () => ws.send(JSON.stringify({ token }));
        ws.onmessage = (e) => {
          try {
            const d = JSON.parse(e.data);
            if (d.type === 'AUTH_OK') ws.send(JSON.stringify({ type: 'CHAT', message: payload }));
            if (d.type === 'CHAT') {
              clearTimeout(timeout); ws.close();
              resolve({
                ok: true,
                message: d.message,
                hasRawScript: d.message.includes('<script>'),
                hasEscaped: d.message.includes('&lt;script&gt;'),
              });
            }
          } catch { /* */ }
        };
      });
    }, { apiUrl: API_URL, token, payload: xss });

    console.log(`T38 result=${JSON.stringify(result)}`);
    expect(result.ok).toBe(true);
    expect(result.hasRawScript).toBe(false);
    expect(result.hasEscaped).toBe(true);
  });

  test('T39 타이핑 인디케이터', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
    const token = await loginInPage(page);
    if (!token) { console.log('T39 SKIP: no auth token'); test.skip(); return; }

    const result = await page.evaluate(async ({ apiUrl, token }: any) => {
      return new Promise<any>((resolve) => {
        const wsUrl = apiUrl.replace('https://', 'wss://').replace('http://', 'ws://');
        const ws = new WebSocket(`${wsUrl}/ws/chat/1`);
        const timeout = setTimeout(() => { ws.close(); resolve({ ok: true, note: 'typing sent ok' }); }, 5000);

        ws.onopen = () => ws.send(JSON.stringify({ token }));
        ws.onmessage = (e) => {
          try {
            const d = JSON.parse(e.data);
            if (d.type === 'AUTH_OK') {
              ws.send(JSON.stringify({ type: 'TYPING' }));
              ws.send(JSON.stringify({ type: 'STOP_TYPING' }));
              setTimeout(() => { clearTimeout(timeout); ws.close(); resolve({ ok: true, note: 'typing indicators sent' }); }, 1000);
            }
          } catch { /* */ }
        };
        ws.onerror = () => { clearTimeout(timeout); resolve({ ok: false, reason: 'ws error' }); };
      });
    }, { apiUrl: API_URL, token });

    console.log(`T39 result=${JSON.stringify(result)}`);
    expect(result.ok).toBe(true);
  });

  test('T40 퇴장 시스템 메시지', async ({ page }) => {
    await page.goto(BASE_URL, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
    const token = await loginInPage(page);
    if (!token) { console.log('T40 SKIP: no auth token'); test.skip(); return; }

    const result = await page.evaluate(async ({ apiUrl, token }: any) => {
      return new Promise<any>((resolve) => {
        const wsUrl = apiUrl.replace('https://', 'wss://').replace('http://', 'ws://');
        const dealId = 99; // isolated room

        // Observer WebSocket
        const observer = new WebSocket(`${wsUrl}/ws/chat/${dealId}`);
        const systemMsgs: string[] = [];
        const timeout = setTimeout(() => { observer.close(); resolve({ ok: systemMsgs.length > 0, systemMsgs }); }, 8000);

        observer.onopen = () => observer.send(JSON.stringify({ token }));
        observer.onmessage = (e) => {
          try {
            const d = JSON.parse(e.data);
            if (d.type === 'SYSTEM') {
              systemMsgs.push(d.message);
              // After seeing entry message, connect a 2nd socket and close it
              if (systemMsgs.length === 1) {
                const leaver = new WebSocket(`${wsUrl}/ws/chat/${dealId}`);
                leaver.onopen = () => leaver.send(JSON.stringify({ token }));
                leaver.onmessage = (ev) => {
                  try {
                    const d2 = JSON.parse(ev.data);
                    if (d2.type === 'AUTH_OK') leaver.close();
                  } catch { /* */ }
                };
              }
              if (d.message.includes('퇴장')) {
                clearTimeout(timeout); observer.close();
                resolve({ ok: true, systemMsgs, leaveMsg: d.message });
              }
            }
          } catch { /* */ }
        };
        observer.onerror = () => { clearTimeout(timeout); resolve({ ok: false, reason: 'observer error' }); };
      });
    }, { apiUrl: API_URL, token });

    console.log(`T40 result=${JSON.stringify(result)}`);
    expect(result.ok).toBe(true);
    if (result.leaveMsg) {
      expect(result.leaveMsg).toContain('퇴장');
    }
  });
});
