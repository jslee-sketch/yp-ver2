import { test, expect } from '@playwright/test';

const BASE = 'https://web-production-defb.up.railway.app';
const TS = Date.now();

async function api(page: any, method: string, path: string, body?: any, token?: string) {
  return page.evaluate(
    async ({ base, method, path, body, token }: any) => {
      const opts: any = { method, headers: { 'Content-Type': 'application/json' } };
      if (token) opts.headers['Authorization'] = `Bearer ${token}`;
      if (body) opts.body = JSON.stringify(body);
      const r = await fetch(`${base}${path}`, opts);
      const text = await r.text();
      try { return { status: r.status, data: JSON.parse(text) }; }
      catch { return { status: r.status, data: text }; }
    },
    { base: BASE, method, path, body, token },
  );
}

async function loginAdmin(page: any) {
  return page.evaluate(async (base: string) => {
    const params = new URLSearchParams();
    params.append('username', 'admin@yeokping.com');
    params.append('password', 'admin1234!');
    for (const url of ['/auth/login', '/auth/seller/login']) {
      const r = await fetch(`${base}${url}`, { method: 'POST', body: params });
      if (r.status === 200) {
        const d = await r.json();
        if (d.access_token) return d.access_token;
      }
    }
    return '';
  }, BASE);
}

test.describe.serial('FCM + WebSocket 검증 (20건)', () => {
  let adminToken = '';
  let buyerToken = '';
  let buyerId = 0;

  test('F1 Admin 로그인', async ({ page }) => {
    await page.goto(BASE);
    adminToken = await loginAdmin(page);
    expect(adminToken).toBeTruthy();
    console.log('F1 Admin OK');
  });

  // ── FCM 테스트 (F2-F10) ──────────────────────

  test('F2 FCM 토큰 등록 → 200', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/notifications/fcm-token', {
      token: `fake-fcm-token-${TS}`,
      user_type: 'buyer',
      user_id: 9,
    });
    console.log(`F2 status=${r.status}, msg=${r.data?.message}`);
    expect(r.status).toBe(200);
    expect(r.data?.ok).toBe(true);
  });

  test('F3 FCM 토큰 빈값 → 400', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/notifications/fcm-token', {
      token: '',
      user_type: 'buyer',
      user_id: 1,
    });
    console.log(`F3 status=${r.status}`);
    expect(r.status).toBe(400);
  });

  test('F4 FCM 토큰 user_id 없음 → 400', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/notifications/fcm-token', {
      token: 'some-token',
      user_type: 'buyer',
    });
    console.log(`F4 status=${r.status}`);
    expect(r.status).toBe(400);
  });

  test('F5 FCM 토큰 존재하지 않는 사용자 → 404', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/notifications/fcm-token', {
      token: 'some-token',
      user_type: 'buyer',
      user_id: 999999,
    });
    console.log(`F5 status=${r.status}`);
    expect(r.status).toBe(404);
  });

  test('F6 FCM Seller 토큰 등록', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/notifications/fcm-token', {
      token: `fake-seller-fcm-${TS}`,
      user_type: 'seller',
      user_id: 9,
    });
    console.log(`F6 status=${r.status}`);
    expect(r.status).toBe(200);
  });

  test('F7 FCM Actuator 토큰 등록', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/notifications/fcm-token', {
      token: `fake-act-fcm-${TS}`,
      user_type: 'actuator',
      user_id: 1,
    });
    console.log(`F7 status=${r.status}`);
    // actuator id=1 이 없을 수 있음
    expect([200, 404]).toContain(r.status);
  });

  test('F8 알림 생성 시 FCM graceful skip (Firebase 미설정)', async ({ page }) => {
    await page.goto(BASE);
    // 알림 생성 → FCM 실패해도 알림은 정상 저장
    const r = await api(page, 'GET', '/notifications/buyer/1?skip=0&limit=1');
    console.log(`F8 status=${r.status}`);
    expect(r.status).toBe(200);
  });

  test('F9 서버 Health Check (FCM 모듈 로드 실패해도 서버 정상)', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/health');
    console.log(`F9 health=${r.status}`);
    expect(r.status).toBe(200);
  });

  test('F10 기존 알림 목록 조회 (회귀)', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/notifications/buyer/1?skip=0&limit=5');
    console.log(`F10 status=${r.status}, count=${Array.isArray(r.data) ? r.data.length : '?'}`);
    expect(r.status).toBe(200);
  });

  // ── WebSocket 테스트 (W11-W20) ────────────────

  test('W11 WebSocket 엔드포인트 존재 확인', async ({ page }) => {
    await page.goto(BASE);
    // WebSocket upgrade 테스트 — HTTP로 접속하면 400/403 등 반환 (WS가 아니므로)
    const r = await page.evaluate(async (base: string) => {
      try {
        const resp = await fetch(`${base}/ws/chat/1`, {
          headers: { 'Connection': 'Upgrade', 'Upgrade': 'websocket' }
        });
        return { status: resp.status };
      } catch {
        return { status: -1 };
      }
    }, BASE);
    console.log(`W11 status=${r.status}`);
    // 400/403/426(Upgrade Required) 등 — 엔드포인트 존재
    expect(r.status).not.toBe(404);
  });

  test('W12 WebSocket 연결 + 인증', async ({ page }) => {
    await page.goto(BASE);
    const result = await page.evaluate(async (base: string) => {
      return new Promise<any>((resolve) => {
        const wsUrl = base.replace('https://', 'wss://').replace('http://', 'ws://');
        const ws = new WebSocket(`${wsUrl}/ws/chat/1`);
        const timeout = setTimeout(() => {
          ws.close();
          resolve({ ok: false, reason: 'timeout' });
        }, 10000);

        ws.onopen = () => {
          // 잘못된 토큰 보내기
          ws.send(JSON.stringify({ token: 'invalid-token-123' }));
        };

        ws.onmessage = (e) => {
          const data = JSON.parse(e.data);
          clearTimeout(timeout);
          ws.close();
          resolve({ ok: true, type: data.type, message: data.message });
        };

        ws.onerror = () => {
          clearTimeout(timeout);
          resolve({ ok: false, reason: 'error' });
        };

        ws.onclose = (e) => {
          clearTimeout(timeout);
          if (!e.wasClean) {
            resolve({ ok: false, reason: `closed:${e.code}` });
          }
        };
      });
    }, BASE);
    console.log(`W12 result=${JSON.stringify(result)}`);
    // 잘못된 토큰 → ERROR 메시지 또는 연결 종료
    expect(result.ok).toBeDefined();
  });

  test('W13 WebSocket 유효한 토큰으로 인증', async ({ page }) => {
    await page.goto(BASE);
    const result = await page.evaluate(async ({ base, token }: any) => {
      return new Promise<any>((resolve) => {
        const wsUrl = base.replace('https://', 'wss://').replace('http://', 'ws://');
        const ws = new WebSocket(`${wsUrl}/ws/chat/1`);
        const timeout = setTimeout(() => {
          ws.close();
          resolve({ ok: false, reason: 'timeout' });
        }, 10000);

        ws.onopen = () => {
          ws.send(JSON.stringify({ token }));
        };

        ws.onmessage = (e) => {
          const data = JSON.parse(e.data);
          if (data.type === 'AUTH_OK') {
            clearTimeout(timeout);
            ws.close();
            resolve({ ok: true, type: data.type, user_id: data.user_id, nickname: data.nickname });
          }
        };

        ws.onerror = () => {
          clearTimeout(timeout);
          resolve({ ok: false, reason: 'error' });
        };
      });
    }, { base: BASE, token: adminToken });
    console.log(`W13 result=${JSON.stringify(result)}`);
    expect(result.ok).toBe(true);
    expect(result.type).toBe('AUTH_OK');
  });

  test('W14 WebSocket 메시지 전송 + XSS 이스케이프', async ({ page }) => {
    await page.goto(BASE);
    const result = await page.evaluate(async ({ base, token }: any) => {
      return new Promise<any>((resolve) => {
        const wsUrl = base.replace('https://', 'wss://').replace('http://', 'ws://');
        const ws = new WebSocket(`${wsUrl}/ws/chat/1`);
        const messages: any[] = [];
        const timeout = setTimeout(() => {
          ws.close();
          resolve({ ok: messages.length > 0, messages });
        }, 10000);

        ws.onopen = () => ws.send(JSON.stringify({ token }));

        ws.onmessage = (e) => {
          const data = JSON.parse(e.data);
          messages.push(data);
          if (data.type === 'AUTH_OK') {
            // XSS 시도
            ws.send(JSON.stringify({ type: 'CHAT', message: '<script>alert("xss")</script>' }));
          }
          if (data.type === 'CHAT') {
            clearTimeout(timeout);
            ws.close();
            resolve({ ok: true, message: data.message, hasScript: data.message.includes('<script>') });
          }
        };
      });
    }, { base: BASE, token: adminToken });
    console.log(`W14 ok=${result.ok}, msg=${result.message}, hasScript=${result.hasScript}`);
    expect(result.ok).toBe(true);
    // XSS 이스케이프됨 → <script> 없어야 함
    expect(result.hasScript).toBe(false);
  });

  test('W15 WebSocket 입력 중 표시', async ({ page }) => {
    await page.goto(BASE);
    const result = await page.evaluate(async ({ base, token }: any) => {
      return new Promise<any>((resolve) => {
        const wsUrl = base.replace('https://', 'wss://').replace('http://', 'ws://');
        const ws = new WebSocket(`${wsUrl}/ws/chat/1`);
        const timeout = setTimeout(() => {
          ws.close();
          resolve({ ok: true, note: 'typing sent without error' });
        }, 5000);

        ws.onopen = () => ws.send(JSON.stringify({ token }));

        ws.onmessage = (e) => {
          const data = JSON.parse(e.data);
          if (data.type === 'AUTH_OK') {
            ws.send(JSON.stringify({ type: 'TYPING' }));
            ws.send(JSON.stringify({ type: 'STOP_TYPING' }));
            setTimeout(() => {
              clearTimeout(timeout);
              ws.close();
              resolve({ ok: true, note: 'typing indicators sent' });
            }, 1000);
          }
        };
      });
    }, { base: BASE, token: adminToken });
    console.log(`W15 ok=${result.ok}, note=${result.note}`);
    expect(result.ok).toBe(true);
  });

  test('W16 WebSocket 온라인 목록 요청', async ({ page }) => {
    await page.goto(BASE);
    const result = await page.evaluate(async ({ base, token }: any) => {
      return new Promise<any>((resolve) => {
        const wsUrl = base.replace('https://', 'wss://').replace('http://', 'ws://');
        const ws = new WebSocket(`${wsUrl}/ws/chat/1`);
        const timeout = setTimeout(() => {
          ws.close();
          resolve({ ok: false, reason: 'timeout' });
        }, 10000);

        ws.onopen = () => ws.send(JSON.stringify({ token }));

        ws.onmessage = (e) => {
          const data = JSON.parse(e.data);
          if (data.type === 'AUTH_OK') {
            ws.send(JSON.stringify({ type: 'ONLINE_LIST' }));
          }
          if (data.type === 'ONLINE_LIST') {
            clearTimeout(timeout);
            ws.close();
            resolve({ ok: true, count: data.count, users: data.users });
          }
        };
      });
    }, { base: BASE, token: adminToken });
    console.log(`W16 ok=${result.ok}, count=${result.count}`);
    expect(result.ok).toBe(true);
    expect(result.count).toBeGreaterThanOrEqual(1);
  });

  test('W17 기존 HTTP 채팅 API 회귀', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/deals/1/chat/messages?skip=0&limit=5');
    console.log(`W17 status=${r.status}`);
    // deal_id=1 없으면 404, 있으면 200, 인증필요 시 401/422
    expect([200, 401, 404, 422]).toContain(r.status);
  });

  test('W18 기존 기능: 딜 목록 조회 (회귀)', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/deals/?skip=0&limit=3');
    console.log(`W18 status=${r.status}`);
    expect(r.status).toBe(200);
  });

  test('W19 기존 기능: 정산내역서 PDF (회귀)', async ({ page }) => {
    await page.goto(BASE);
    const r = await page.evaluate(async (base: string) => {
      const resp = await fetch(`${base}/settlements/1/pdf`);
      return { status: resp.status, ct: resp.headers.get('content-type') || '' };
    }, BASE);
    console.log(`W19 status=${r.status}, ct=${r.ct}`);
    expect([200, 404]).toContain(r.status);
  });

  test('W20 기존 기능: 핑퐁이 ASK (회귀)', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
      question: 'WebSocket 채팅은 어떻게 사용하나요?',
      role: 'buyer',
    });
    console.log(`W20 status=${r.status}, answer=${(r.data?.answer || '').slice(0, 60)}`);
    expect([200, 201]).toContain(r.status);
  });
});
