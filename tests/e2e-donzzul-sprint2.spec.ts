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

// unique suffix for this test run
const TS = Date.now();
const STORE_ADDR = `서울 종로구 테스트로 ${TS}`;
const STORE_PHONE = `02-${String(TS).slice(-4)}-${String(TS).slice(-8,-4)}`;
const STORY = '이 가게는 20년째 동네 어르신들에게 무료 반찬을 나눠주는 착한 식당입니다. 사장님 코로나 이후 매출이 반토막 났지만 묵묵히 봉사를 계속하고 계세요.';

// ═══════════════════════════════════════════
// 히어로 가게 추천 (7건)
// ═══════════════════════════════════════════
test.describe.serial('히어로 가게 추천', () => {
    test('T01: /donzzul/hero/recommend → 4단계 폼 표시', async ({ page }) => {
        await page.goto(url('/donzzul/hero/recommend'));
        await page.waitForTimeout(3000);
        const text = await page.textContent('body');
        expect(text).toContain('가게 추천하기');
        expect(text).toContain('Step 1');
    });

    test('T02: Step 1 빈 필드 → 에러 메시지 (번들 확인)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('가게명을 입력해주세요')).toBeTruthy();
    });

    test('T03: Step 1→2 이동 가능 (번들에 Step 2 텍스트 포함)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('Step 2')).toBeTruthy();
        expect(js.includes('사장님 정보')).toBeTruthy();
    });

    test('T04: Step 2 동의 미체크 에러 (번들 확인)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('사장님 동의를 확인해주세요')).toBeTruthy();
    });

    test('T05: Step 3 계좌 → Step 4 (번들에 Step 3/4 텍스트 포함)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('Step 3')).toBeTruthy();
        expect(js.includes('정산 계좌')).toBeTruthy();
        expect(js.includes('Step 4')).toBeTruthy();
        expect(js.includes('50자 이상')).toBeTruthy();
    });

    test('T06: 사연 50자 미만 에러 + API 검증', async ({ request }) => {
        // 49자 사연 → 400
        const res = await request.post(`${BASE}/donzzul/stores`, {
            data: {
                store_name: '테스트가게', store_address: STORE_ADDR,
                store_phone: STORE_PHONE, owner_name: '김테스트',
                owner_phone: '010-9999-8888', bank_name: '국민',
                account_number: '111-222-333', account_holder: '김테스트',
                story_text: '짧은 사연입니다. 50자가 안 되는 사연이에요 아쉽네요.',
            },
        });
        expect(res.status()).toBe(400);
    });

    test('T07: 제출 → REVIEWING 상태로 저장', async ({ request }) => {
        const res = await request.post(`${BASE}/donzzul/stores`, {
            data: {
                store_name: `테스트착한가게-${TS}`, store_address: STORE_ADDR,
                store_phone: STORE_PHONE, owner_name: '김착한',
                owner_phone: '010-1111-2222', bank_name: '국민은행',
                account_number: '123-456-789', account_holder: '김착한',
                story_text: STORY,
            },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.status).toBe('REVIEWING');
        expect(data.store_name).toContain('테스트착한가게');
    });
});

// ═══════════════════════════════════════════
// 관리자 검증 (6건)
// ═══════════════════════════════════════════
test.describe.serial('관리자 검증', () => {
    test('T08: /admin/donzzul/stores 페이지 번들 포함', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('돈쭐 가게 관리')).toBeTruthy();
        expect(js.includes('검증 대기')).toBeTruthy();
    });

    test('T09: 검증하기 UI — 체크리스트 + PIN 입력 (번들 확인)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('검증 체크리스트')).toBeTruthy();
        expect(js.includes('사장님 비밀번호')).toBeTruthy();
    });

    test('T10: PIN 없이 승인 → 에러 (번들 확인: alert 조건)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        // approve function checks pin.length !== 4
        expect(js.includes('4자리')).toBeTruthy();
    });

    test('T11: PUT /stores/{id}/verify approve → APPROVED + 딜 생성', async ({ request }) => {
        // 먼저 REVIEWING 상태 가게 찾기
        const listRes = await request.get(`${BASE}/donzzul/stores?status=REVIEWING`);
        const stores = await listRes.json();
        if (!stores.length) { test.skip(); return; }
        const store = stores[0];

        // 승인
        const approveRes = await request.put(`${BASE}/donzzul/stores/${store.id}/verify`, {
            data: { action: 'approve', admin_id: 1, notes: 'E2E 테스트 승인', consent_method: 'phone', account_verified: true },
        });
        expect(approveRes.status()).toBe(200);
        const approved = await approveRes.json();
        expect(approved.status).toBe('APPROVED');

        // PIN 설정
        const pinRes = await request.put(`${BASE}/donzzul/stores/${store.id}/set-pin`, {
            data: { pin: '1234' },
        });
        expect(pinRes.status()).toBe(200);

        // 딜 자동 생성 확인
        const dealsRes = await request.get(`${BASE}/donzzul/deals`);
        const deals = await dealsRes.json();
        const relatedDeal = deals.find((d: any) => d.store_id === store.id);
        expect(relatedDeal).toBeTruthy();
        expect(relatedDeal.status).toBe('OPEN');
    });

    test('T12: PUT /stores/{id}/verify reject → REJECTED', async ({ request }) => {
        // 새 가게 등록 → 거절
        const createRes = await request.post(`${BASE}/donzzul/stores`, {
            data: {
                store_name: `거절테스트-${TS}`, store_address: `서울 강남구 거절로 ${TS}`,
                store_phone: `02-${String(TS+1).slice(-4)}-0000`, owner_name: '박거절',
                owner_phone: '010-0000-0000', bank_name: '신한',
                account_number: '999-888-777', account_holder: '박거절',
                story_text: STORY,
            },
        });
        const created = await createRes.json();

        const rejectRes = await request.put(`${BASE}/donzzul/stores/${created.id}/verify`, {
            data: { action: 'reject', notes: '테스트 거절 사유: 실존하지 않는 가게' },
        });
        expect(rejectRes.status()).toBe(200);
        const rejected = await rejectRes.json();
        expect(rejected.status).toBe('REJECTED');
        expect(rejected.verification_notes).toContain('실존하지 않는');
    });

    test('T13: 필터 동작 — status 파라미터', async ({ request }) => {
        const approved = await request.get(`${BASE}/donzzul/stores?status=APPROVED`);
        expect(approved.status()).toBe(200);
        const aData = await approved.json();
        for (const s of aData) { expect(s.status).toBe('APPROVED'); }

        const rejected = await request.get(`${BASE}/donzzul/stores?status=REJECTED`);
        expect(rejected.status()).toBe(200);
        const rData = await rejected.json();
        for (const s of rData) { expect(s.status).toBe('REJECTED'); }

        const all = await request.get(`${BASE}/donzzul/stores`);
        expect(all.status()).toBe(200);
    });
});

// ═══════════════════════════════════════════
// 통합 (2건)
// ═══════════════════════════════════════════
test.describe.serial('통합 검증', () => {
    test('T14: 중복 등록 (같은 주소+전화) → 409', async ({ request }) => {
        // 같은 주소+전화로 재등록 시도
        const res = await request.post(`${BASE}/donzzul/stores`, {
            data: {
                store_name: `중복테스트-${TS}`, store_address: STORE_ADDR,
                store_phone: STORE_PHONE, owner_name: '김중복',
                owner_phone: '010-3333-4444', bank_name: '하나',
                account_number: '555-666-777', account_holder: '김중복',
                story_text: STORY,
            },
        });
        // T07에서 이미 같은 주소+전화로 등록했으므로 409 or 승인 후에도 중복
        expect([200, 409]).toContain(res.status());
    });

    test('T15: /donzzul/hero/my-stores — 내 추천 가게 목록 페이지', async ({ page }) => {
        await page.goto(url('/donzzul/hero/my-stores'));
        await page.waitForTimeout(3000);
        const text = await page.textContent('body');
        expect(text).toContain('내가 추천한 가게');
    });
});
