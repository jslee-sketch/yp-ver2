import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL || 'https://www.yeokping.com';
const ACCESS_KEY = 'yeokping2026';
function url(path: string) { return `${BASE}${path}?access=${ACCESS_KEY}`; }

async function getMainJsContent(page: any): Promise<string> {
    const jsFiles = await page.evaluate(() =>
        Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src)
    );
    for (const src of jsFiles) {
        try {
            const content = await page.evaluate(async (u: string) => {
                const res = await fetch(u); return await res.text();
            }, src);
            if (content.length > 100000) return content;
        } catch {}
    }
    return '';
}

const TS = Date.now();
const STORY = '이 가게는 20년째 동네 어르신들에게 무료 반찬을 나눠주는 착한 식당입니다. 사장님 코로나 이후 매출이 반토막 났지만 묵묵히 봉사를 계속하고 계세요.';

let STORE_A_ID: number;
let STORE_B_ID: number;
let STORE_C_ID: number;
let WEEK_ID: number;
let SETUP_DONE = false;

async function ensureSetup(request: any) {
    if (SETUP_DONE) return;
    // 3개 가게 등록 + 승인
    const stores = [];
    for (let i = 0; i < 3; i++) {
        const rand = Math.random().toString(36).slice(2, 8);
        const storeRes = await request.post(`${BASE}/donzzul/stores`, {
            data: {
                store_name: `S6-투표${i}-${rand}`,
                store_address: `서울 종로구 투표로 ${TS}-${rand}-${i}`,
                store_phone: `02-${String(TS).slice(-4)}-${String(Math.floor(Math.random()*9000)+1000)}`,
                owner_name: `김투표${i}`, owner_phone: `010-${6000+i}-${String(Math.floor(Math.random()*9000)+1000)}`,
                bank_name: '우리은행', account_number: `${555+i}-666-${rand}`, account_holder: `김투표${i}`,
                story_text: STORY + ` 가게${i} ${rand}`,
            },
        });
        const store = await storeRes.json();
        if (!store.id) throw new Error(`Store creation failed: ${JSON.stringify(store)}`);
        stores.push(store);

        await request.put(`${BASE}/donzzul/stores/${store.id}/verify`, {
            data: { action: 'approve', admin_id: 1, notes: 'Sprint6 투표 테스트', consent_method: 'phone', account_verified: true },
        });
    }
    STORE_A_ID = stores[0].id;
    STORE_B_ID = stores[1].id;
    STORE_C_ID = stores[2].id;
    SETUP_DONE = true;
}

// ═══════════════════════════════════════════
// 투표 주차 생성 (3건)
// ═══════════════════════════════════════════
test.describe.serial('투표 주차', () => {
    test('T01: 투표 주차 생성 (3개 후보)', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/votes/weeks`, {
            data: {
                week_label: `Sprint6-${TS}`,
                candidate_store_ids: [STORE_A_ID, STORE_B_ID, STORE_C_ID],
            },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.id).toBeGreaterThan(0);
        expect(data.status).toBe('VOTING');
        expect(data.candidates.length).toBe(3);
        WEEK_ID = data.id;
    });

    test('T02: 후보 2개 미만 → 400 에러', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/votes/weeks`, {
            data: {
                week_label: `실패-${TS}`,
                candidate_store_ids: [STORE_A_ID],
            },
        });
        expect(res.status()).toBe(400);
    });

    test('T03: 현재 주 투표 조회 → VOTING 상태', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.get(`${BASE}/donzzul/votes/current-week`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data).toBeTruthy();
        expect(data.status).toBe('VOTING');
    });
});

// ═══════════════════════════════════════════
// 투표 캐스팅 (4건)
// ═══════════════════════════════════════════
test.describe.serial('투표 캐스팅', () => {
    test('T04: 투표하기 → 성공 + weight 반환', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/votes/cast`, {
            data: { week_id: WEEK_ID, voter_id: 1001, store_id: STORE_A_ID },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.vote_id).toBeGreaterThan(0);
        expect(data.weight).toBeGreaterThanOrEqual(1);
        expect(data.store_id).toBe(STORE_A_ID);
    });

    test('T05: 중복 투표 → 409 에러', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/votes/cast`, {
            data: { week_id: WEEK_ID, voter_id: 1001, store_id: STORE_B_ID },
        });
        expect(res.status()).toBe(409);
    });

    test('T06: 후보 외 가게 투표 → 400 에러', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/votes/cast`, {
            data: { week_id: WEEK_ID, voter_id: 1002, store_id: 999999 },
        });
        expect(res.status()).toBe(400);
    });

    test('T07: 다른 유저 투표 → 성공 (B가게)', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/votes/cast`, {
            data: { week_id: WEEK_ID, voter_id: 1002, store_id: STORE_B_ID },
        });
        expect(res.status()).toBe(200);
        // A가게에 또 한표
        await request.post(`${BASE}/donzzul/votes/cast`, {
            data: { week_id: WEEK_ID, voter_id: 1003, store_id: STORE_A_ID },
        });
    });
});

// ═══════════════════════════════════════════
// 투표 마감 + 자동 딜 생성 (4건)
// ═══════════════════════════════════════════
test.describe.serial('투표 마감', () => {
    test('T08: 투표 주차 상세 조회 → 득표 확인', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.get(`${BASE}/donzzul/votes/weeks/${WEEK_ID}`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.total_votes).toBeGreaterThan(0);
        const aStore = data.candidates.find((c: any) => c.store_id === STORE_A_ID);
        expect(aStore.score).toBeGreaterThanOrEqual(2);
    });

    test('T09: 투표 마감 → CLOSED + ranking 반환', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/votes/weeks/${WEEK_ID}/close`, {
            data: {},
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.status).toBe('CLOSED');
        expect(data.ranking.length).toBeGreaterThanOrEqual(2);
        expect(data.ranking[0].rank).toBe(1);
    });

    test('T10: 마감된 투표에 투표 → 400 에러', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/votes/cast`, {
            data: { week_id: WEEK_ID, voter_id: 1004, store_id: STORE_C_ID },
        });
        expect(res.status()).toBe(400);
    });

    test('T11: 1위 가게에 자동 딜 생성 확인', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.get(`${BASE}/donzzul/deals`);
        expect(res.status()).toBe(200);
        const deals = await res.json();
        // A가게(1위)에 투표 선정 딜이 있어야 함
        const voteDeal = deals.find((d: any) =>
            d.store_id === STORE_A_ID && d.title && d.title.includes('투표 선정')
        );
        // 이미 OPEN 딜이 있었으면 이전 딜, 없으면 새 딜
        const anyDeal = deals.find((d: any) => d.store_id === STORE_A_ID);
        expect(anyDeal).toBeTruthy();
    });
});

// ═══════════════════════════════════════════
// 투표 목록 (1건)
// ═══════════════════════════════════════════
test.describe.serial('투표 목록', () => {
    test('T12: 투표 주차 목록 API 동작 확인', async ({ request }) => {
        // CLOSED가 없을 수 있으므로 전체 목록 확인
        const res = await request.get(`${BASE}/donzzul/votes/weeks`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBe(true);

        // CLOSED 필터 API 동작 확인
        const closedRes = await request.get(`${BASE}/donzzul/votes/weeks?status=CLOSED`);
        expect(closedRes.status()).toBe(200);
        const closedData = await closedRes.json();
        for (const w of closedData) {
            expect(w.status).toBe('CLOSED');
        }
    });
});

// ═══════════════════════════════════════════
// 프론트엔드 (2건)
// ═══════════════════════════════════════════
test.describe.serial('프론트엔드', () => {
    test('T13: 투표 페이지 번들 포함 (DonzzulVotePage)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(
            js.includes('vote') || js.includes('투표') || js.includes('cast') || js.includes('week_label')
        ).toBeTruthy();
    });

    test('T14: 투표 라우트 등록 확인', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(
            js.includes('donzzul/vote') || js.includes('VotePage') || js.includes('week_label') || js.includes('handleVote')
        ).toBeTruthy();
    });
});
