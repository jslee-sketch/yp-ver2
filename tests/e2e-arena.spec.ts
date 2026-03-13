// 역핑 배틀 아레나 E2E 테스트 — 30 tests
import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL || 'https://www.yeokping.com';

// ─── 헬퍼 ───
let buyerToken = '';
let buyerUserId = 0;
let arenaPlayerId = 0;

async function ensureBuyerToken(request: any) {
  if (buyerToken) return;
  const ts = Date.now();
  const email = `arena_${ts}@test.com`;
  const pw = 'Test1234!';

  // 회원가입: POST /buyers/
  await request.post(`${BASE}/buyers/`, {
    data: { email, name: `ArenaBot${ts}`, nickname: `ab${ts}`, password: pw },
  });

  // 로그인: POST /auth/login (form-urlencoded)
  const form = new URLSearchParams();
  form.append('username', email);
  form.append('password', pw);
  const loginRes = await request.post(`${BASE}/auth/login`, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    data: form.toString(),
  });
  if (loginRes.ok()) {
    const d = await loginRes.json();
    buyerToken = d.access_token || '';
    if (buyerToken) {
      try {
        const payload = JSON.parse(Buffer.from(buyerToken.split('.')[1], 'base64url').toString());
        buyerUserId = Number(payload.sub) || 0;
      } catch {}
    }
  }
}

function authHeaders() {
  return buyerToken ? { Authorization: `Bearer ${buyerToken}` } : {};
}

// ─────────────────────────────────────
// Phase 1: 아레나 기본 API (10 tests)
// ─────────────────────────────────────
test.describe('Phase 1: Arena Basic API', () => {
  test('1-01 Register arena player', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/register`, {
      headers: authHeaders(),
      data: { country: 'KR', region: '서울' },
    });
    expect([200, 201]).toContain(res.status());
    const d = await res.json();
    arenaPlayerId = d.id || 0;
    expect(d.country).toBe('KR');
  });

  test('1-02 Get arena me', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.get(`${BASE}/arena/me`, { headers: authHeaders() });
    expect([200, 404]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(d).toHaveProperty('total_points');
      expect(d).toHaveProperty('arena_level');
    }
  });

  test('1-03 Play RPS - rock', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'rps', data: { choice: 'rock' } },
    });
    expect([200, 201, 429]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(['win', 'lose', 'draw']).toContain(d.result);
      expect(d).toHaveProperty('total_points');
    }
  });

  test('1-04 Play RPS - paper', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'rps', data: { choice: 'paper' } },
    });
    expect([200, 201, 429]).toContain(res.status());
  });

  test('1-05 Play RPS - scissors', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'rps', data: { choice: 'scissors' } },
    });
    expect([200, 201, 429]).toContain(res.status());
  });

  test('1-06 Invalid game_type → 422', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'invalid_game', data: {} },
    });
    expect([422]).toContain(res.status());
  });

  test('1-07 Play without auth → 401', async ({ request }) => {
    const res = await request.post(`${BASE}/arena/play`, {
      data: { game_type: 'rps', data: { choice: 'rock' } },
    });
    expect([401, 403]).toContain(res.status());
  });

  test('1-08 Rankings endpoint', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/rankings?game_type=all&limit=10`);
    expect([200]).toContain(res.status());
    const d = await res.json();
    expect(d).toHaveProperty('rankings');
    expect(Array.isArray(d.rankings)).toBeTruthy();
  });

  test('1-09 Live feed endpoint', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/live-feed?limit=10`);
    expect([200]).toContain(res.status());
    const d = await res.json();
    expect(d).toHaveProperty('feed');
  });

  test('1-10 Map endpoint', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/map`);
    expect([200]).toContain(res.status());
    const d = await res.json();
    expect(d).toHaveProperty('particles');
    expect(d).toHaveProperty('regions');
  });
});

// ─────────────────────────────────────
// Phase 2: 6개 게임 타입별 테스트 (12 tests)
// ─────────────────────────────────────
test.describe('Phase 2: All Game Types', () => {
  test('2-01 Mukjjippa play', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'mjb', data: { choice: 'rock', is_attacker: false } },
    });
    expect([200, 201, 429]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(['win', 'lose', 'attack', 'defend']).toContain(d.result);
    }
  });

  test('2-02 Yut play', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'yut', data: {} },
    });
    expect([200, 201, 429]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(['도', '개', '걸', '윷', '모']).toContain(d.result);
    }
  });

  test('2-03 Math - new question', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'math', data: { action: 'new', difficulty: 1 } },
    });
    expect([200, 201, 429]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(d.result).toBe('question');
      expect(d).toHaveProperty('question');
    }
  });

  test('2-04 Math - answer correct', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'math', data: { action: 'answer', answer: 10, correct_answer: 10, time_ms: 2000 } },
    });
    expect([200, 201, 429]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(d.result).toBe('correct');
    }
  });

  test('2-05 Math - answer wrong', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'math', data: { action: 'answer', answer: 99, correct_answer: 10, time_ms: 2000 } },
    });
    expect([200, 201, 429]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(d.result).toBe('wrong');
    }
  });

  test('2-06 Quiz - new question', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'quiz', data: { action: 'new', lang: 'ko' } },
    });
    expect([200, 201, 429]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(d.result).toBe('question');
      expect(d).toHaveProperty('choices');
    }
  });

  test('2-07 Quiz - answer', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'quiz', data: { action: 'answer', question_id: 0, answer: 0 } },
    });
    expect([200, 201, 429]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(['correct', 'wrong']).toContain(d.result);
    }
  });

  test('2-08 Reaction play', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'reaction', data: { reaction_ms: 250 } },
    });
    expect([200, 201, 429]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(d.result).toBe('recorded');
      expect(d.reaction_ms).toBeGreaterThanOrEqual(100);
    }
  });

  test('2-09 Reaction - cheating prevention (too fast)', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.post(`${BASE}/arena/play`, {
      headers: authHeaders(),
      data: { game_type: 'reaction', data: { reaction_ms: 10 } },
    });
    expect([200, 201, 429]).toContain(res.status());
    if (res.ok()) {
      const d = await res.json();
      expect(d.reaction_ms).toBeGreaterThanOrEqual(100); // 치팅 보정
    }
  });

  test('2-10 Quiz questions endpoint', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/quiz/questions?lang=ko&count=3`);
    expect([200]).toContain(res.status());
    const d = await res.json();
    expect(d).toHaveProperty('questions');
    expect(d.questions.length).toBeLessThanOrEqual(3);
  });

  test('2-11 Quiz questions - English', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/quiz/questions?lang=en&count=2`);
    expect([200]).toContain(res.status());
    const d = await res.json();
    expect(d).toHaveProperty('questions');
  });

  test('2-12 Quiz questions - Japanese', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/quiz/questions?lang=ja&count=2`);
    expect([200]).toContain(res.status());
  });
});

// ─────────────────────────────────────
// Phase 3: 랭킹 & 통계 (5 tests)
// ─────────────────────────────────────
test.describe('Phase 3: Rankings & Stats', () => {
  test('3-01 Rankings - RPS', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/rankings?game_type=rps&limit=5`);
    expect(res.status()).toBe(200);
    const d = await res.json();
    expect(d.game_type).toBe('rps');
  });

  test('3-02 Rankings - reaction', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/rankings?game_type=reaction&limit=5`);
    expect(res.status()).toBe(200);
  });

  test('3-03 Rankings - with country filter', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/rankings?game_type=all&country=KR&limit=5`);
    expect(res.status()).toBe(200);
  });

  test('3-04 Deal banner', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/deal-banner`);
    expect(res.status()).toBe(200);
    const d = await res.json();
    expect(d).toHaveProperty('banners');
  });

  test('3-05 Game history', async ({ request }) => {
    await ensureBuyerToken(request);
    test.skip(!buyerToken, 'No buyer token');
    const res = await request.get(`${BASE}/arena/history?limit=5`, { headers: authHeaders() });
    expect([200]).toContain(res.status());
    const d = await res.json();
    expect(d).toHaveProperty('games');
  });
});

// ─────────────────────────────────────
// Phase 4: 보안 & 엣지케이스 (3 tests)
// ─────────────────────────────────────
test.describe('Phase 4: Security & Edge Cases', () => {
  test('4-01 Register without auth → 401', async ({ request }) => {
    const res = await request.post(`${BASE}/arena/register`, {
      data: { country: 'KR' },
    });
    expect([401, 403]).toContain(res.status());
  });

  test('4-02 Me without auth → 401', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/me`);
    expect([401, 403]).toContain(res.status());
  });

  test('4-03 History without auth → 401', async ({ request }) => {
    const res = await request.get(`${BASE}/arena/history`);
    expect([401, 403]).toContain(res.status());
  });
});
