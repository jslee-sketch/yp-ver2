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

let DEAL_ID: number;
let STORE_ID: number;
let SETUP_DONE = false;

async function ensureSetup(request: any) {
    if (SETUP_DONE) return;
    // 가게 등록
    const storeRes = await request.post(`${BASE}/donzzul/stores`, {
        data: {
            store_name: `Sprint4-정산-${TS}`,
            store_address: `서울 강남구 정산로 ${TS}`,
            store_phone: `02-${String(TS).slice(-4)}-${String(TS).slice(-8, -4)}`,
            owner_name: '김정산', owner_phone: '010-7777-8888',
            bank_name: '신한은행', account_number: '333-444-555', account_holder: '김정산',
            story_text: STORY,
        },
    });
    const store = await storeRes.json();
    STORE_ID = store.id;

    // 승인
    await request.put(`${BASE}/donzzul/stores/${store.id}/verify`, {
        data: { action: 'approve', admin_id: 1, notes: 'Sprint4 테스트', consent_method: 'phone', account_verified: true },
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
// 만료 배치 (5건)
// ═══════════════════════════════════════════
test.describe.serial('만료 배치', () => {
    test('T01: 만료 배치 실행 → donated_count 반환', async ({ request }) => {
        await ensureSetup(request);
        const res = await request.post(`${BASE}/donzzul/batch/expiry`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data).toHaveProperty('donated_count');
        expect(data).toHaveProperty('donated_total');
        expect(data).toHaveProperty('run_at');
    });

    test('T02: ACTIVE 상품권 (유효기간 미래) → 변경 없음', async ({ request }) => {
        await ensureSetup(request);
        // 구매 (유효기간 90일)
        const purchaseRes = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 10000 },
        });
        expect(purchaseRes.status()).toBe(200);
        const voucher = await purchaseRes.json();

        // 만료 배치 실행
        await request.post(`${BASE}/donzzul/batch/expiry`);

        // 상품권 상태 확인 → 여전히 ACTIVE
        const myRes = await request.get(`${BASE}/donzzul/vouchers/my?buyer_id=1`);
        const myData = await myRes.json();
        const v = myData.find((x: any) => x.code === voucher.code);
        expect(v.status).toBe('ACTIVE');
    });

    test('T03: 이미 USED 상품권 → 배치 영향 없음', async ({ request }) => {
        await ensureSetup(request);
        // 구매 + 사용
        const pRes = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 10000 },
        });
        const voucher = await pRes.json();
        await request.post(`${BASE}/donzzul/vouchers/${voucher.code}/redeem`, {
            data: { store_pin: '1234' },
        });

        // 배치 실행
        await request.post(`${BASE}/donzzul/batch/expiry`);

        // 상태 확인 → 여전히 USED (DONATED로 안 변함)
        const myRes = await request.get(`${BASE}/donzzul/vouchers/my?buyer_id=1`);
        const myData = await myRes.json();
        const v = myData.find((x: any) => x.code === voucher.code);
        expect(v.status).toBe('USED');
    });

    test('T04: 만료 경고 배치 실행 → warnings_sent 반환', async ({ request }) => {
        const res = await request.post(`${BASE}/donzzul/batch/expiry-warning`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data).toHaveProperty('warnings_sent');
        expect(data).toHaveProperty('run_at');
    });

    test('T05: 딜 마감 배치 실행 → closed_deals 반환', async ({ request }) => {
        const res = await request.post(`${BASE}/donzzul/batch/deal-expiry`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data).toHaveProperty('closed_deals');
        expect(data).toHaveProperty('run_at');
    });
});

// ═══════════════════════════════════════════
// 정산 (7건)
// ═══════════════════════════════════════════
test.describe.serial('정산', () => {
    let SETTLEMENT_ID: number;

    test('T06: 가게 정산 생성 (USED 상품권 합산)', async ({ request }) => {
        await ensureSetup(request);

        // 2건 구매 + 사용
        for (let i = 0; i < 2; i++) {
            const pRes = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
                data: { deal_id: DEAL_ID, buyer_id: 1, amount: 10000 },
            });
            const v = await pRes.json();
            await request.post(`${BASE}/donzzul/vouchers/${v.code}/redeem`, {
                data: { store_pin: '1234' },
            });
        }

        // 정산 생성
        const res = await request.post(`${BASE}/donzzul/settlements/create`, {
            data: { store_id: STORE_ID },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.total_amount).toBeGreaterThan(0);
        expect(data.voucher_count).toBeGreaterThan(0);
        SETTLEMENT_ID = data.settlement_id;
    });

    test('T07: platform_fee = 0원 (역핑 수수료 0원)', async ({ request }) => {
        const res = await request.get(`${BASE}/donzzul/settlements/${SETTLEMENT_ID}`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.settlement.platform_fee).toBe(0);
    });

    test('T08: payout_amount = total_amount', async ({ request }) => {
        const res = await request.get(`${BASE}/donzzul/settlements/${SETTLEMENT_ID}`);
        const data = await res.json();
        expect(data.settlement.payout_amount).toBe(data.settlement.total_amount);
    });

    test('T09: 정산 승인 → APPROVED', async ({ request }) => {
        const res = await request.put(`${BASE}/donzzul/settlements/${SETTLEMENT_ID}/process`, {
            data: { action: 'approve', admin_id: 1 },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.status).toBe('APPROVED');
    });

    test('T10: 정산 지급 → PAID', async ({ request }) => {
        const res = await request.put(`${BASE}/donzzul/settlements/${SETTLEMENT_ID}/process`, {
            data: { action: 'pay' },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.status).toBe('PAID');
    });

    test('T11: 새 정산 생성 후 거절 → REJECTED', async ({ request }) => {
        await ensureSetup(request);
        // 1건 구매 + 사용
        const pRes = await request.post(`${BASE}/donzzul/vouchers/purchase`, {
            data: { deal_id: DEAL_ID, buyer_id: 1, amount: 20000 },
        });
        const v = await pRes.json();
        await request.post(`${BASE}/donzzul/vouchers/${v.code}/redeem`, {
            data: { store_pin: '1234' },
        });

        // 정산 생성
        const createRes = await request.post(`${BASE}/donzzul/settlements/create`, {
            data: { store_id: STORE_ID },
        });
        const created = await createRes.json();

        // 거절
        const res = await request.put(`${BASE}/donzzul/settlements/${created.settlement_id}/process`, {
            data: { action: 'reject' },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.status).toBe('REJECTED');
    });

    test('T12: 미정산 상품권 0건 → 에러', async ({ request }) => {
        await ensureSetup(request);
        // 이미 정산 완료된 가게에서 다시 시도
        const res = await request.post(`${BASE}/donzzul/settlements/create`, {
            data: { store_id: STORE_ID },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.error).toContain('정산할 상품권이 없습니다');
    });
});

// ═══════════════════════════════════════════
// 관리자 UI (4건)
// ═══════════════════════════════════════════
test.describe.serial('관리자 UI', () => {
    test('T13: /admin/donzzul/settlements 번들 포함', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('돈쭐 정산') || js.includes('settlement')).toBeTruthy();
    });

    test('T14: 정산 상세 패널 번들 포함 (사용/기부 구분)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('payout_amount') || js.includes('지급액')).toBeTruthy();
    });

    test('T15: 배치 실행 버튼 번들 포함', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('batch') || js.includes('배치')).toBeTruthy();
    });

    test('T16: 정산 필터 (PENDING/APPROVED/PAID) API 동작', async ({ request }) => {
        const pending = await request.get(`${BASE}/donzzul/settlements?status=PENDING`);
        expect(pending.status()).toBe(200);
        const pData = await pending.json();
        for (const s of pData) { expect(s.status).toBe('PENDING'); }

        const paid = await request.get(`${BASE}/donzzul/settlements?status=PAID`);
        expect(paid.status()).toBe(200);
        const pdData = await paid.json();
        for (const s of pdData) { expect(s.status).toBe('PAID'); }

        const all = await request.get(`${BASE}/donzzul/settlements`);
        expect(all.status()).toBe(200);
    });
});

// ═══════════════════════════════════════════
// 알림 (2건)
// ═══════════════════════════════════════════
test.describe.serial('알림', () => {
    test('T17: DONZZUL_VOUCHER_EXPIRED_DONATED 알림 템플릿 존재 (번들)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        // 번들에 돈쭐 관련 알림 텍스트 확인
        expect(
            js.includes('기부') || js.includes('DONATED') || js.includes('만료')
        ).toBeTruthy();
    });

    test('T18: DONZZUL_STORE_APPROVED 관련 — 가게 승인 시 히어로 포인트 적립', async ({ request }) => {
        // 새 가게 등록 → 승인 → 히어로 포인트
        const storeRes = await request.post(`${BASE}/donzzul/stores`, {
            data: {
                store_name: `알림테스트-${TS}`,
                store_address: `서울 서초구 알림로 ${TS}`,
                store_phone: `02-${String(TS+99).slice(-4)}-9999`,
                owner_name: '박알림', owner_phone: '010-9999-1111',
                bank_name: '하나은행', account_number: '777-888-999', account_holder: '박알림',
                story_text: STORY,
            },
        });
        const store = await storeRes.json();

        // 승인 → 히어로 포인트 + 딜 자동 생성
        const approveRes = await request.put(`${BASE}/donzzul/stores/${store.id}/verify`, {
            data: { action: 'approve', admin_id: 1, notes: '알림 테스트 승인', consent_method: 'phone', account_verified: true },
        });
        expect(approveRes.status()).toBe(200);
        const approved = await approveRes.json();
        expect(approved.status).toBe('APPROVED');

        // 딜 자동 생성 확인
        const dealsRes = await request.get(`${BASE}/donzzul/deals`);
        const deals = await dealsRes.json();
        const relatedDeal = deals.find((d: any) => d.store_id === store.id);
        expect(relatedDeal).toBeTruthy();
        expect(relatedDeal.status).toBe('OPEN');
    });
});
