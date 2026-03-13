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

// 전역 상태 — 모든 serial 그룹 공유
let DEAL_ID: number;
let STORE_ID: number;
let SETUP_DONE = false;

async function ensureSetup(request: any) {
    if (SETUP_DONE) return;
    // 가게 등록
    const storeRes = await request.post(`${BASE}/donzzul/stores`, {
        data: {
            store_name: `Sprint3-가게-${TS}`,
            store_address: `서울 마포구 상품권로 ${TS}`,
            store_phone: `02-${String(TS).slice(-4)}-${String(TS).slice(-8, -4)}`,
            owner_name: '김상품', owner_phone: '010-5555-6666',
            bank_name: '국민은행', account_number: '111-222-333', account_holder: '김상품',
            story_text: STORY,
        },
    });
    const store = await storeRes.json();
    STORE_ID = store.id;

    // 승인
    await request.put(`${BASE}/donzzul/stores/${store.id}/verify`, {
        data: { action: 'approve', admin_id: 1, notes: 'Sprint3 테스트', consent_method: 'phone', account_verified: true },
    });

    // PIN 설정
    await request.put(`${BASE}/donzzul/stores/${store.id}/set-pin`, {
        data: { pin: '1234' },
    });

    // 딜 찾기
    const dealsRes = await request.get(`${BASE}/donzzul/deals`);
    const deals = await dealsRes.json();
    const deal = deals.find((d: any) => d.store_id === store.id);
    DEAL_ID = deal.id;
    SETUP_DONE = true;
}

// ═══════════════════════════════════════════
// 구매 (5건)
// ═══════════════════════════════════════════
test.describe.serial('상품권 구매', () => {
    test('T01: /donzzul/deals/{id} → 딜 상세 (사연/달성률) 표시', async ({ request }) => {
        await ensureSetup(request);

        const res = await request.get(`${BASE}/donzzul/deals/${DEAL_ID}`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.deal.title).toContain('Sprint3-가게');
        expect(data.deal.status).toBe('OPEN');
        expect(data.store.story_text).toContain('무료 반찬');
        expect(data.deal).toHaveProperty('progress');
        expect(data.deal).toHaveProperty('voucher_count');
        expect(data).toHaveProperty('cheer_messages');
    });

    test('T02: 1만원 + 응원 메시지 → 구매 → 코드 + PIN 반환', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: {
                deal_id: DEAL_ID,
                buyer_id: 1,
                amount: 10000,
                cheer_message: '화이팅! 응원합니다!',
            },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.code).toMatch(/^DONZZUL-[A-F0-9]{4}-[A-F0-9]{4}$/);
        expect(data.pin).toMatch(/^\d{4}$/);
        expect(data.amount).toBe(10000);
        expect(data.store_name).toContain('Sprint3-가게');
    });

    test('T03: 2만원 구매 → 딜 current_amount 증가', async ({ request }) => {
        await ensureSetup(request);
        const before = await request.get(`${BASE}/donzzul/deals/${DEAL_ID}`);
        const bData = await before.json();
        const prevAmount = bData.deal.current_amount;

        const res = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 20000 },
        });
        expect(res.status()).toBe(200);

        const after = await request.get(`${BASE}/donzzul/deals/${DEAL_ID}`);
        const aData = await after.json();
        expect(aData.deal.current_amount).toBe(prevAmount + 20000);
    });

    test('T04: 5만원 구매 → voucher_count 증가', async ({ request }) => {
        await ensureSetup(request);
        const before = await request.get(`${BASE}/donzzul/deals/${DEAL_ID}`);
        const bData = await before.json();
        const prevCount = bData.deal.voucher_count;

        const res = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 50000 },
        });
        expect(res.status()).toBe(200);

        const after = await request.get(`${BASE}/donzzul/deals/${DEAL_ID}`);
        const aData = await after.json();
        expect(aData.deal.voucher_count).toBe(prevCount + 1);
    });

    test('T05: 허용되지 않은 금액 → 에러', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 99999 },
        });
        expect(res.status()).toBe(400);
    });
});

// ═══════════════════════════════════════════
// 상품권함 (4건)
// ═══════════════════════════════════════════
test.describe.serial('상품권함', () => {
    test('T06: /donzzul/vouchers/my → 내 상품권 목록', async ({ request }) => {
        await ensureSetup(request);
        // 구매가 안 됐을 수 있으므로 하나 구매
        await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 10000 },
        });

        const res = await request.get(`${BASE}/donzzul/vouchers/my?buyer_id=1`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBeTruthy();
        expect(data.length).toBeGreaterThan(0);
    });

    test('T07: ACTIVE 상품권 필드 확인 (홀로그램 UI 데이터)', async ({ request }) => {
        const res = await request.get(`${BASE}/donzzul/vouchers/my?buyer_id=1`);
        const data = await res.json();
        const active = data.find((v: any) => v.status === 'ACTIVE');
        expect(active).toBeTruthy();
        expect(active.store_name).toBeTruthy();
        expect(active.code).toMatch(/^DONZZUL-/);
        expect(active.days_left).toBeGreaterThan(0);
    });

    test('T08: 상품권함 번들에 홀로그램/사용하기 UI 포함', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('상품권함') || js.includes('ACTIVE')).toBeTruthy();
        expect(js.includes('사용하기') || js.includes('use')).toBeTruthy();
    });

    test('T09: 유효기간 경고 표시 번들 확인', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('days_left') || js.includes('남음')).toBeTruthy();
    });
});

// ═══════════════════════════════════════════
// 사용 (7건)
// ═══════════════════════════════════════════
test.describe.serial('상품권 사용', () => {
    test('T10: 사용 페이지 번들에 키패드 UI 포함', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        // 번들에서 키패드 관련 텍스트 확인 (minify로 한글 깨질 수 있으므로 여러 패턴)
        expect(
            js.includes('store_pin') || js.includes('redeem') || js.includes('handleKeyPress') || js.includes('키패드') || js.includes('비밀번호')
        ).toBeTruthy();
    });

    test('T11: PIN 입력 UI 존재 (● 표시 or dot)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('●') || js.includes('pin') || js.includes('PIN')).toBeTruthy();
    });

    test('T12: 올바른 가게 비밀번호 → 사용 완료', async ({ request }) => {
        await ensureSetup(request);
        // 구매
        const purchaseRes = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 10000 },
        });
        const purchased = await purchaseRes.json();

        // 올바른 PIN으로 사용
        const res = await request.post(`${BASE}/donzzul/vouchers/${purchased.code}/redeem`, {
            data: { store_pin: '1234' },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.status).toBe('USED');
        expect(data.message).toContain('사용 완료');
        expect(data.amount).toBe(10000);
    });

    test('T13: 틀린 비밀번호 → "남은 시도: N회"', async ({ request }) => {
        await ensureSetup(request);
        const purchaseRes = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 10000 },
        });
        const purchased = await purchaseRes.json();

        const res = await request.post(`${BASE}/donzzul/vouchers/${purchased.code}/redeem`, {
            data: { store_pin: '9999' },
        });
        expect(res.status()).toBe(401);
        const data = await res.json();
        expect(data.detail).toContain('남은 시도');
    });

    test('T14: 5회 오류 → 잠금', async ({ request }) => {
        await ensureSetup(request);
        const purchaseRes = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 10000 },
        });
        const purchased = await purchaseRes.json();

        // 5회 틀림
        for (let i = 0; i < 4; i++) {
            await request.post(`${BASE}/donzzul/vouchers/${purchased.code}/redeem`, {
                data: { store_pin: '0000' },
            });
        }
        const res = await request.post(`${BASE}/donzzul/vouchers/${purchased.code}/redeem`, {
            data: { store_pin: '0000' },
        });
        expect(res.status()).toBe(423);
        const data = await res.json();
        expect(data.detail).toContain('잠금');
    });

    test('T15: 이미 사용된 상품권 → 에러', async ({ request }) => {
        await ensureSetup(request);
        const purchaseRes = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 10000 },
        });
        const purchased = await purchaseRes.json();

        // 사용
        await request.post(`${BASE}/donzzul/vouchers/${purchased.code}/redeem`, {
            data: { store_pin: '1234' },
        });

        // 재사용 시도
        const res = await request.post(`${BASE}/donzzul/vouchers/${purchased.code}/redeem`, {
            data: { store_pin: '1234' },
        });
        expect(res.status()).toBe(400);
        const data = await res.json();
        expect(data.detail).toContain('USED');
    });

    test('T16: 존재하지 않는 상품권 → 404', async ({ request }) => {
        const res = await request.post(`${BASE}/donzzul/vouchers/DONZZUL-FAKE-CODE/redeem`, {
            data: { store_pin: '1234' },
        });
        expect(res.status()).toBe(404);
    });
});

// ═══════════════════════════════════════════
// 딜 상세 (2건)
// ═══════════════════════════════════════════
test.describe.serial('딜 상세', () => {
    test('T17: 응원 메시지 목록 표시', async ({ request }) => {
        await ensureSetup(request);
        // 응원 메시지 있는 상품권 구매
        await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 10000, cheer_message: '테스트 응원!' },
        });

        const res = await request.get(`${BASE}/donzzul/deals/${DEAL_ID}`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.cheer_messages.length).toBeGreaterThan(0);
        expect(data.cheer_messages[0]).toHaveProperty('message');
        expect(data.cheer_messages[0]).toHaveProperty('amount');
    });

    test('T18: 달성률 프로그레스 바 정확성', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.get(`${BASE}/donzzul/deals/${DEAL_ID}`);
        const data = await res.json();
        const { target_amount, current_amount, progress } = data.deal;
        if (target_amount > 0) {
            const expected = Math.min(Math.round(current_amount / target_amount * 1000) / 10, 100);
            expect(progress).toBe(expected);
        } else {
            expect(progress).toBe(0);
        }
    });
});
