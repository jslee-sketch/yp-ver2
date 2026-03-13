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

// ═══════════════════════════════════════════
// A. 외부평점 (5건)
// ═══════════════════════════════════════════
test.describe.serial('외부평점', () => {
    let ratingId: number;

    test('A01: 외부평점 등록 → PENDING', async ({ request }) => {
        const res = await request.post(`${BASE}/v3_6/seller/external-ratings`, {
            data: {
                seller_id: 1,
                platform_name: '스마트스토어',
                platform_url: 'https://smartstore.naver.com/test-shop',
                claimed_rating: 4.5,
                claimed_review_count: 120,
            },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.id).toBeGreaterThan(0);
        expect(data.status).toBe('PENDING');
        ratingId = data.id;
    });

    test('A02: 외부평점 검증 → VERIFIED', async ({ request }) => {
        const res = await request.post(`${BASE}/v3_6/seller/external-ratings/${ratingId}/verify`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.status).toBe('VERIFIED');
        expect(typeof data.verified_rating).toBe('number');
    });

    test('A03: 판매자별 평점 목록 조회', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/seller/1/external-ratings`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBe(true);
        expect(data.length).toBeGreaterThan(0);
        expect(data[0]).toHaveProperty('platform_name');
        expect(data[0]).toHaveProperty('verified_rating');
    });

    test('A04: 배치 검증 실행', async ({ request }) => {
        const res = await request.post(`${BASE}/v3_6/seller/external-ratings/batch`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data).toHaveProperty('checked');
        expect(data).toHaveProperty('zeroed');
    });

    test('A05: is_trusted 판정 (gap <= 0.5)', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/seller/1/external-ratings`);
        const data = await res.json();
        const verified = data.find((r: any) => r.id === ratingId);
        expect(verified).toBeTruthy();
        expect(typeof verified.is_trusted).toBe('boolean');
    });
});

// ═══════════════════════════════════════════
// B. AI 스코어링 (5건)
// ═══════════════════════════════════════════
test.describe.serial('AI 스코어링', () => {
    test('B01: 판매자 종합 점수 계산', async ({ request }) => {
        const res = await request.post(`${BASE}/v3_6/seller/1/score`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.total_score).toBeGreaterThanOrEqual(0);
        expect(data.auto_decision).toBeTruthy();
        expect(data.scores).toHaveProperty('age');
        expect(data.scores).toHaveProperty('rating');
    });

    test('B02: 점수 조회', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/seller/1/score`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data).toHaveProperty('total_score');
        expect(data).toHaveProperty('seller_message');
    });

    test('B03: 승인/수동검토 시 사유 메시지', async ({ request }) => {
        const res = await request.post(`${BASE}/v3_6/seller/1/score`);
        const data = await res.json();
        expect(data.seller_message).toBeTruthy();
        expect(data.admin_message).toBeTruthy();
        expect(Array.isArray(data.reasons)).toBe(true);
    });

    test('B04: 관리자 수동 결정', async ({ request }) => {
        // 먼저 스코어 계산
        await request.post(`${BASE}/v3_6/seller/1/score`);

        const res = await request.put(`${BASE}/v3_6/admin/seller/1/decision`, {
            data: { decision: 'approve', notes: 'E2E 테스트 승인' },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.decision).toBe('ADMIN_APPROVED');
    });

    test('B05: weak_points 목록', async ({ request }) => {
        // seller 2 (없을 수 있음)
        const res = await request.post(`${BASE}/v3_6/seller/1/score`);
        const data = await res.json();
        if (data.auto_decision === 'MANUAL_REVIEW') {
            expect(data.weak_points.length).toBeGreaterThan(0);
        }
    });
});

// ═══════════════════════════════════════════
// C. 액츄에이터-판매자 해지 (5건)
// ═══════════════════════════════════════════
test.describe.serial('해지 프로세스', () => {
    let disconnectId: number;

    test('C01: 해지 신청 → GRACE_PERIOD', async ({ request }) => {
        const res = await request.post(`${BASE}/v3_6/actuator-seller/disconnect`, {
            data: {
                actuator_id: 9001,
                seller_id: 9002,
                requested_by: 'actuator',
                reason: 'trust_issue',
                reason_detail: '소통 불량 테스트',
                agreement_accepted: true,
            },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.status).toBe('GRACE_PERIOD');
        expect(data.grace_period_ends).toBeTruthy();
        disconnectId = data.id;
    });

    test('C02: 약관 미동의 → 에러', async ({ request }) => {
        const res = await request.post(`${BASE}/v3_6/actuator-seller/disconnect`, {
            data: {
                actuator_id: 9003,
                seller_id: 9004,
                requested_by: 'seller',
                reason: 'personal_reason',
                agreement_accepted: false,
            },
        });
        expect(res.status()).toBe(400);
    });

    test('C03: 유예 기간 내 철회 → CANCELLED', async ({ request }) => {
        const res = await request.put(`${BASE}/v3_6/actuator-seller/disconnect/${disconnectId}/cancel`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.ok).toBe(true);
    });

    test('C04: 유예 만료 배치 → CONFIRMED', async ({ request }) => {
        const res = await request.post(`${BASE}/v3_6/actuator-seller/disconnect/batch/confirm`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data).toHaveProperty('confirmed');
    });

    test('C05: 해지 목록 조회', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/actuator-seller/disconnections?actuator_id=9001`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBe(true);
        expect(data.length).toBeGreaterThan(0);
    });
});

// ═══════════════════════════════════════════
// D. KPI 고도화 (4건)
// ═══════════════════════════════════════════
test.describe.serial('KPI', () => {
    test('D01: KPI API → 전체 반환', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/admin/kpi/advanced?period=30d`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data).toHaveProperty('gmv');
        expect(data).toHaveProperty('aov');
        expect(data).toHaveProperty('order_count');
        expect(data).toHaveProperty('conversion_rate');
        expect(data).toHaveProperty('mau');
        expect(data).toHaveProperty('retention_rate');
    });

    test('D02: GMV >= 0', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/admin/kpi/advanced?period=all`);
        const data = await res.json();
        expect(data.gmv).toBeGreaterThanOrEqual(0);
    });

    test('D03: 기간별 쿼리 동작', async ({ request }) => {
        for (const period of ['7d', '30d', '90d']) {
            const res = await request.get(`${BASE}/v3_6/admin/kpi/advanced?period=${period}`);
            expect(res.status()).toBe(200);
            const data = await res.json();
            expect(data.period).toBe(period);
        }
    });

    test('D04: conversion_rate 범위 0~100', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/admin/kpi/advanced?period=all`);
        const data = await res.json();
        expect(data.conversion_rate).toBeGreaterThanOrEqual(0);
        expect(data.conversion_rate).toBeLessThanOrEqual(100);
    });
});

// ═══════════════════════════════════════════
// E. 금맥 인사이트 (4건)
// ═══════════════════════════════════════════
test.describe.serial('인사이트', () => {
    test('E01: 인사이트 API → 카테고리/브랜드/가격대/키워드', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/admin/insights/trends`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data).toHaveProperty('categories');
        expect(data).toHaveProperty('brands');
        expect(data).toHaveProperty('price_ranges');
        expect(data).toHaveProperty('hot_keywords');
    });

    test('E02: 카테고리별 정렬 (딜 수 내림차순)', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/admin/insights/trends`);
        const data = await res.json();
        if (data.categories.length >= 2) {
            expect(data.categories[0].count).toBeGreaterThanOrEqual(data.categories[1].count);
        }
    });

    test('E03: 가격대별 분포 5구간', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/admin/insights/trends`);
        const data = await res.json();
        expect(data.price_ranges.length).toBe(5);
    });

    test('E04: 핫 키워드 15개 이내', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/admin/insights/trends`);
        const data = await res.json();
        expect(data.hot_keywords.length).toBeLessThanOrEqual(15);
    });
});

// ═══════════════════════════════════════════
// F. 환불 시뮬레이터 (6건)
// ═══════════════════════════════════════════
test.describe.serial('환불 시뮬레이터', () => {
    test('F01: 구매자 시뮬레이터 → 환불 예상 금액', async ({ request }) => {
        const res = await request.get(
            `${BASE}/v3_6/refund-simulator/calculate?amount=350000&reason=buyer_change_mind&delivery_status=delivered&shipping_mode=free&shipping_cost=3000&days_since_delivery=1&role=buyer`
        );
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.can_refund).toBe(true);
        expect(data.refund_amount).toBeLessThanOrEqual(350000);
        expect(data.deductions.length).toBeGreaterThan(0);
    });

    test('F02: 판매자 시뮬레이터 → 정산 영향', async ({ request }) => {
        const res = await request.get(
            `${BASE}/v3_6/refund-simulator/calculate?amount=350000&reason=buyer_change_mind&delivery_status=delivered&shipping_mode=free&shipping_cost=3000&days_since_delivery=1&role=seller`
        );
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.settlement_impact).toBeTruthy();
        expect(data.settlement_impact.before_refund).toBeGreaterThan(0);
        expect(data.settlement_impact.settlement_loss).toBeGreaterThan(0);
    });

    test('F03: 품질 불량 → 전액 환불', async ({ request }) => {
        const res = await request.get(
            `${BASE}/v3_6/refund-simulator/calculate?amount=350000&reason=defective&delivery_status=delivered&shipping_mode=free&shipping_cost=3000&days_since_delivery=1&role=buyer`
        );
        const data = await res.json();
        expect(data.refund_amount).toBe(350000);
        expect(data.deductions.length).toBe(0);
    });

    test('F04: 단순 변심 + 배송 후 → 배송비 차감', async ({ request }) => {
        const res = await request.get(
            `${BASE}/v3_6/refund-simulator/calculate?amount=350000&reason=buyer_change_mind&delivery_status=delivered&shipping_mode=free&shipping_cost=3000&days_since_delivery=1&role=buyer`
        );
        const data = await res.json();
        expect(data.refund_amount).toBeLessThan(350000);
    });

    test('F05: 쿨링 기간 초과 → 환불 불가', async ({ request }) => {
        const res = await request.get(
            `${BASE}/v3_6/refund-simulator/calculate?amount=350000&reason=buyer_change_mind&delivery_status=delivered&shipping_mode=free&shipping_cost=3000&days_since_delivery=10&role=buyer`
        );
        const data = await res.json();
        expect(data.can_refund).toBe(false);
    });

    test('F06: 구매자 role → settlement_impact 없음', async ({ request }) => {
        const res = await request.get(
            `${BASE}/v3_6/refund-simulator/calculate?amount=100000&reason=buyer_change_mind&delivery_status=before&role=buyer`
        );
        const data = await res.json();
        expect(data.settlement_impact).toBeUndefined();
    });
});

// ═══════════════════════════════════════════
// G. 프론트엔드 번들 (2건)
// ═══════════════════════════════════════════
test.describe.serial('프론트엔드', () => {
    test('G01: 분쟁 타임라인 UI 번들', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(
            js.includes('DisputeDetail') || js.includes('ROUND1') || js.includes('dispute')
        ).toBeTruthy();
    });

    test('G02: 환불 시뮬레이터 UI 번들', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(
            js.includes('RefundSimulator') || js.includes('refund-simulator') || js.includes('settlement_impact')
        ).toBeTruthy();
    });
});
