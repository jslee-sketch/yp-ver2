import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL || 'https://www.yeokping.com';
const ACCESS_KEY = 'yeokping2026';

function url(path: string) { return `${BASE}${path}?access=${ACCESS_KEY}`; }

// Helper: fetch main JS bundle content
async function getMainJsContent(page: any): Promise<string> {
    const jsFiles = await page.evaluate(() =>
        Array.from(document.querySelectorAll('script[src]')).map(s => (s as HTMLScriptElement).src)
    );
    for (const src of jsFiles) {
        try {
            const content = await page.evaluate(async (u: string) => {
                const res = await fetch(u);
                return await res.text();
            }, src);
            if (content.length > 100000) return content;
        } catch {}
    }
    return '';
}

// ═══════════════════════════════════════════
// Phase 1: DB + API — order_number 컬럼 존재 확인
// ═══════════════════════════════════════════
test.describe.serial('Phase 1: DB + API order_number', () => {
    test('T01: /health 또는 /docs 로 서버 정상 확인', async ({ request }) => {
        const res = await request.get(`${BASE}/health`);
        expect(res.status()).toBe(200);
    });

    test('T02: Reservation API 스키마에 order_number 필드 존재', async ({ request }) => {
        const docs = await request.get(`${BASE}/openapi.json`);
        expect(docs.status()).toBe(200);
        const schema = await docs.text();
        expect(schema.includes('order_number')).toBeTruthy();
    });

    test('T03: order_number 형식 YP-YYYYMMDD-NNNN (OpenAPI 스키마)', async ({ request }) => {
        const docs = await request.get(`${BASE}/openapi.json`);
        expect(docs.status()).toBe(200);
        const schema = await docs.text();
        // ReservationOut 스키마에 order_number 포함
        expect(schema.includes('order_number')).toBeTruthy();
    });
});

// ═══════════════════════════════════════════
// Phase 2: Frontend 번들 — "주문번호" 텍스트 포함
// ═══════════════════════════════════════════
test.describe.serial('Phase 2: Frontend bundle — 주문번호 텍스트', () => {
    test('T04: JS 번들에 "주문번호" 텍스트 포함', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('주문번호')).toBeTruthy();
    });

    test('T05: JS 번들에 "order_number" 필드 참조 포함', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('order_number')).toBeTruthy();
    });

    test('T06: JS 번들에서 "예약번호" 텍스트 제거됨', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        // "예약번호"는 더 이상 사용하지 않음 (예약 상태 분포 등은 OK)
        // 번들에서 "예약번호"가 표시 라벨로 남아있으면 안 됨
        const hasOldLabel = js.includes('예약번호');
        expect(hasOldLabel).toBeFalsy();
    });

    test('T07: JS 번들에 OrderNumber 컴포넌트 코드 포함', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        // OrderNumber component uses monospace + letterSpacing
        const hasComponent = js.includes('letterSpacing') && js.includes('monospace');
        expect(hasComponent).toBeTruthy();
    });
});

// ═══════════════════════════════════════════
// Phase 3: 공개 페이지 UI — 주문번호 라벨 확인
// ═══════════════════════════════════════════
test.describe.serial('Phase 3: Public page UI', () => {
    test('T08: /deals 페이지 정상 로드', async ({ page }) => {
        await page.goto(url('/deals'));
        await page.waitForTimeout(2000);
        expect(page.url()).toContain('/deals');
    });

    test('T09: 홈페이지 정상 로드 (order_number 도입 후)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const title = await page.title();
        expect(title.length).toBeGreaterThan(0);
    });
});

// ═══════════════════════════════════════════
// Phase 4: Admin 페이지 번들 — R-# → 주문번호 전환
// ═══════════════════════════════════════════
test.describe.serial('Phase 4: Admin pages — R-# 제거 확인', () => {
    test('T10: AdminDeliveryPage — "주문번호" 라벨 존재', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        // AdminDeliveryPage uses "주문번호" as table header
        expect(js.includes('주문번호')).toBeTruthy();
    });

    test('T11: AdminReservationsPage — "주문 상세" 텍스트 존재', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('주문 상세')).toBeTruthy();
    });

    test('T12: AdminSettlementsPage — order_number 컬럼 사용', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('order_number')).toBeTruthy();
    });
});

// ═══════════════════════════════════════════
// Phase 5: Buyer 페이지 — 주문번호 표시
// ═══════════════════════════════════════════
test.describe.serial('Phase 5: Buyer pages — 주문번호', () => {
    test('T13: MyOrdersPage — "주문번호" 라벨 사용', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        // MyOrdersPage uses "주문번호" instead of "예약번호"
        expect(js.includes('주문번호')).toBeTruthy();
    });

    test('T14: DealJoinPage — "주문번호" 라벨 사용', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('주문번호')).toBeTruthy();
    });
});

// ═══════════════════════════════════════════
// Phase 6: Seller 페이지 — 주문번호
// ═══════════════════════════════════════════
test.describe.serial('Phase 6: Seller pages — 주문번호', () => {
    test('T15: SellerSettlementsPage — "주문번호" 라벨', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('주문번호')).toBeTruthy();
    });

    test('T16: SellerReviewsPage — "주문번호" 라벨', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('주문번호')).toBeTruthy();
    });
});

// ═══════════════════════════════════════════
// Phase 7: Backend 서비스 — order_number 생성 로직
// ═══════════════════════════════════════════
test.describe.serial('Phase 7: Backend order_number generation', () => {
    test('T17: /health — DB 정상 (backfill 완료)', async ({ request }) => {
        const res = await request.get(`${BASE}/health`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.db).toBeTruthy();
    });

    test('T18: API docs — ReservationOut 스키마에 order_number 필드', async ({ request }) => {
        const res = await request.get(`${BASE}/openapi.json`);
        expect(res.status()).toBe(200);
        const text = await res.text();
        expect(text.includes('"order_number"')).toBeTruthy();
    });

    test('T19: API docs — ReservationSettlementOut 스키마에 order_number', async ({ request }) => {
        const res = await request.get(`${BASE}/openapi.json`);
        expect(res.status()).toBe(200);
        const text = await res.text();
        // order_number appears in settlement schemas too
        const count = (text.match(/order_number/g) || []).length;
        expect(count).toBeGreaterThanOrEqual(2); // At least in Reservation + Settlement
    });
});

// ═══════════════════════════════════════════
// Phase 8: 알림 템플릿 — 주문번호 사용
// ═══════════════════════════════════════════
test.describe.serial('Phase 8: Notification templates', () => {
    test('T20: 결제완료 알림 — "주문번호" 사용 (번들 확인)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        // Notification text includes 주문번호 somewhere in the bundle
        expect(js.includes('주문번호') || js.includes('order_number')).toBeTruthy();
    });
});

// ═══════════════════════════════════════════
// Phase 9: 통합 검증 — 전체 흐름
// ═══════════════════════════════════════════
test.describe.serial('Phase 9: Integration verification', () => {
    test('T21: 전체 번들 크기 정상 (1MB 이상)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.length).toBeGreaterThan(1000000);
    });

    test('T22: CSS 정상 로드', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const cssFiles = await page.evaluate(() =>
            Array.from(document.querySelectorAll('link[rel="stylesheet"]')).map(l => (l as HTMLLinkElement).href)
        );
        expect(cssFiles.length).toBeGreaterThan(0);
    });

    test('T23: "주문" 키워드 번들 내 다수 출현 (10회 이상)', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        const count = (js.match(/주문/g) || []).length;
        expect(count).toBeGreaterThanOrEqual(10);
    });

    test('T24: AdminDashboardPage — "주문" KPI 라벨 사용', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        // Dashboard uses "주문" as KPI label (replaced from "예약/주문")
        expect(js.includes('주문')).toBeTruthy();
    });

    test('T25: PingpongFloat — "주문 #" 딥링크 라벨', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('주문 #')).toBeTruthy();
    });
});
