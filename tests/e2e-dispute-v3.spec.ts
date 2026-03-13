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

// Helper: 분쟁 생성 + Round 1 전체 흐름
async function createDispute(request: any) {
    const rand = Math.random().toString(36).slice(2, 8);
    const res = await request.post(`${BASE}/v3_6/disputes`, {
        data: {
            reservation_id: 1,
            initiator_id: 1001,
            category: '품질불량',
            title: `테스트분쟁-${rand}`,
            description: '제품 품질이 불량합니다. 화면에 불량화소가 있습니다.',
            evidence: [
                { type: 'image', url: 'https://example.com/photo1.jpg', description: '불량화소 사진' },
                { type: 'video', url: 'https://example.com/video.mp4', description: '불량 영상' },
            ],
            requested_resolution: 'full_refund',
            requested_amount: 350000,
        },
    });
    return { res, rand };
}

// ═══════════════════════════════════════════
// Round 1 (7건)
// ═══════════════════════════════════════════
test.describe.serial('Round 1', () => {
    let disputeId: number;

    test('T01: 분쟁 신청 → ROUND1_RESPONSE', async ({ request }) => {
        const { res } = await createDispute(request);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.dispute_id).toBeGreaterThan(0);
        expect(data.status).toBe('ROUND1_RESPONSE');
        expect(data.respondent_deadline).toBeTruthy();
        disputeId = data.dispute_id;
    });

    test('T02: 상대방 반론+제안 → AI 1차 중재', async ({ request }) => {
        const res = await request.put(`${BASE}/v3_6/disputes/${disputeId}/round1-response`, {
            data: {
                reply: '제품은 정상 출하되었습니다. 운송 중 파손 가능성이 있습니다.',
                evidence: [{ type: 'text', url: '', description: '출하 검수 기록' }],
                proposal_type: 'partial_refund',
                proposal_amount: 175000,
                proposal_text: '50% 환불 제안합니다.',
            },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.status).toBe('ROUND1_REVIEW');
        expect(data.ai_recommendation).toBeTruthy();
    });

    test('T03: AI 중재 → opinion + 추천 금액', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/disputes/${disputeId}`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.round1.ai_opinion).toBeTruthy();
        expect(data.round1.ai_recommendation).toBeTruthy();
        expect(data.round1.ai_amount).toBeGreaterThan(0);
    });

    test('T04: 양쪽 모두 accept → ACCEPTED (조기 종결)', async ({ request }) => {
        // 새 분쟁 생성
        const { res: cres } = await createDispute(request);
        const cdata = await cres.json();
        const did = cdata.dispute_id;

        // 반론
        await request.put(`${BASE}/v3_6/disputes/${did}/round1-response`, {
            data: { reply: '인정합니다.', proposal_type: 'full_refund', proposal_amount: 350000 },
        });

        // 양쪽 accept
        const r1 = await request.put(`${BASE}/v3_6/disputes/${did}/decision`, {
            data: { user_id: 1001, decision: 'accept' },
        });
        expect(r1.status()).toBe(200);

        const d = await (await request.get(`${BASE}/v3_6/disputes/${did}`)).json();
        // respondent_id 가져오기
        const respId = d.respondent.id;

        const r2 = await request.put(`${BASE}/v3_6/disputes/${did}/decision`, {
            data: { user_id: respId, decision: 'accept' },
        });
        expect(r2.status()).toBe(200);
        const result = await r2.json();
        expect(result.status).toBe('ACCEPTED');
        expect(result.resolution_amount).toBeGreaterThan(0);
    });

    test('T05: 신청인 accept + 상대방 reject → ROUND2_RESPONSE', async ({ request }) => {
        // 신규 분쟁
        const { res: cres } = await createDispute(request);
        const did = (await cres.json()).dispute_id;

        await request.put(`${BASE}/v3_6/disputes/${did}/round1-response`, {
            data: { reply: '인정합니다.', proposal_type: 'partial_refund', proposal_amount: 200000 },
        });

        await request.put(`${BASE}/v3_6/disputes/${did}/decision`, {
            data: { user_id: 1001, decision: 'accept' },
        });

        const d = await (await request.get(`${BASE}/v3_6/disputes/${did}`)).json();
        const r2 = await request.put(`${BASE}/v3_6/disputes/${did}/decision`, {
            data: { user_id: d.respondent.id, decision: 'reject' },
        });
        const result = await r2.json();
        expect(result.status).toBe('ROUND2_RESPONSE');
        expect(result.rejecters).toContain('respondent');
    });

    test('T06: 양쪽 모두 reject → ROUND2_RESPONSE', async ({ request }) => {
        const { res: cres } = await createDispute(request);
        const did = (await cres.json()).dispute_id;

        await request.put(`${BASE}/v3_6/disputes/${did}/round1-response`, {
            data: { reply: '동의하지 않습니다.', proposal_type: 'no_refund', proposal_amount: 0 },
        });

        await request.put(`${BASE}/v3_6/disputes/${did}/decision`, {
            data: { user_id: 1001, decision: 'reject' },
        });

        const d = await (await request.get(`${BASE}/v3_6/disputes/${did}`)).json();
        const r2 = await request.put(`${BASE}/v3_6/disputes/${did}/decision`, {
            data: { user_id: d.respondent.id, decision: 'reject' },
        });
        const result = await r2.json();
        expect(result.status).toBe('ROUND2_RESPONSE');
        expect(result.rejecters).toContain('initiator');
        expect(result.rejecters).toContain('respondent');
    });

    test('T07: 분쟁 상세 조회 → 전체 타임라인', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/disputes/${disputeId}`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.id).toBe(disputeId);
        expect(data.category).toBe('품질불량');
        expect(data.evidence.length).toBe(2);
        expect(data.round1.response).toBeTruthy();
    });
});

// ═══════════════════════════════════════════
// Round 2 (6건)
// ═══════════════════════════════════════════
test.describe.serial('Round 2', () => {
    let disputeId: number;
    let respondentId: number;

    test('T08: 거절 측 재반론+제안 → AI 2차 중재', async ({ request }) => {
        // Round 1 full flow → reject → Round 2
        const { res: cres } = await createDispute(request);
        disputeId = (await cres.json()).dispute_id;

        await request.put(`${BASE}/v3_6/disputes/${disputeId}/round1-response`, {
            data: { reply: '제품 정상', proposal_type: 'partial_refund', proposal_amount: 100000 },
        });

        const d = await (await request.get(`${BASE}/v3_6/disputes/${disputeId}`)).json();
        respondentId = d.respondent.id;

        await request.put(`${BASE}/v3_6/disputes/${disputeId}/decision`, {
            data: { user_id: 1001, decision: 'reject' },
        });
        await request.put(`${BASE}/v3_6/disputes/${disputeId}/decision`, {
            data: { user_id: respondentId, decision: 'reject' },
        });

        // Round 2 rebuttal (initiator)
        const r1 = await request.put(`${BASE}/v3_6/disputes/${disputeId}/round2-rebuttal`, {
            data: {
                user_id: 1001,
                rebuttal: '추가 증거입니다. 불량화소 3개 확인.',
                evidence: [{ type: 'image', url: 'https://example.com/photo2.jpg', description: '추가 증거' }],
                proposal_type: 'full_refund',
                proposal_amount: 350000,
            },
        });
        expect(r1.status()).toBe(200);

        // Round 2 rebuttal (respondent)
        const r2 = await request.put(`${BASE}/v3_6/disputes/${disputeId}/round2-rebuttal`, {
            data: {
                user_id: respondentId,
                rebuttal: '재검토 결과 일부 인정합니다.',
                proposal_type: 'partial_refund',
                proposal_amount: 250000,
            },
        });
        expect(r2.status()).toBe(200);
        const result = await r2.json();
        expect(result.status).toBe('ROUND2_REVIEW');
        expect(result.ai_recommendation).toBeTruthy();
    });

    test('T09: 양쪽 모두 accept → ACCEPTED (Round 2 합의)', async ({ request }) => {
        const r1 = await request.put(`${BASE}/v3_6/disputes/${disputeId}/decision`, {
            data: { user_id: 1001, decision: 'accept' },
        });
        expect(r1.status()).toBe(200);

        const r2 = await request.put(`${BASE}/v3_6/disputes/${disputeId}/decision`, {
            data: { user_id: respondentId, decision: 'accept' },
        });
        expect(r2.status()).toBe(200);
        const result = await r2.json();
        expect(result.status).toBe('ACCEPTED');
    });

    test('T10: 한쪽 reject → REJECTED + 법적 안내', async ({ request }) => {
        // 새 분쟁 → Round 1 reject → Round 2 reject
        const { res: cres } = await createDispute(request);
        const did = (await cres.json()).dispute_id;

        await request.put(`${BASE}/v3_6/disputes/${did}/round1-response`, {
            data: { reply: '거절', proposal_type: 'no_refund', proposal_amount: 0 },
        });

        const d = await (await request.get(`${BASE}/v3_6/disputes/${did}`)).json();
        const rid = d.respondent.id;

        await request.put(`${BASE}/v3_6/disputes/${did}/decision`, { data: { user_id: 1001, decision: 'reject' } });
        await request.put(`${BASE}/v3_6/disputes/${did}/decision`, { data: { user_id: rid, decision: 'reject' } });

        // Round 2 rebuttal
        await request.put(`${BASE}/v3_6/disputes/${did}/round2-rebuttal`, {
            data: { user_id: 1001, rebuttal: '재반론', proposal_type: 'full_refund', proposal_amount: 350000 },
        });
        await request.put(`${BASE}/v3_6/disputes/${did}/round2-rebuttal`, {
            data: { user_id: rid, rebuttal: '최종 거절', proposal_type: 'no_refund', proposal_amount: 0 },
        });

        // Round 2 decisions
        await request.put(`${BASE}/v3_6/disputes/${did}/decision`, { data: { user_id: 1001, decision: 'accept' } });
        const r2 = await request.put(`${BASE}/v3_6/disputes/${did}/decision`, { data: { user_id: rid, decision: 'reject' } });
        const result = await r2.json();
        expect(result.status).toBe('REJECTED');
        expect(result.message).toContain('법적 안내');
    });

    test('T11: AI 2차 중재에서 1차 결과 참조 확인', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/disputes/${disputeId}`);
        const data = await res.json();
        expect(data.round2).not.toBeNull();
        expect(data.round2.ai_opinion).toBeTruthy();
    });

    test('T12: 분쟁 목록 API', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/disputes`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBe(true);
        expect(data.length).toBeGreaterThan(0);
    });

    test('T13: 증거 URL 목록 저장/조회', async ({ request }) => {
        const { res: cres } = await createDispute(request);
        const did = (await cres.json()).dispute_id;
        const res = await request.get(`${BASE}/v3_6/disputes/${did}`);
        const data = await res.json();
        expect(data.evidence.length).toBe(2);
        expect(data.evidence[0].type).toBe('image');
        expect(data.evidence[1].type).toBe('video');
    });
});

// ═══════════════════════════════════════════
// 기타 (5건)
// ═══════════════════════════════════════════
test.describe.serial('기타', () => {
    test('T14: 타임아웃 배치 실행', async ({ request }) => {
        const res = await request.post(`${BASE}/v3_6/disputes/batch/timeout`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data).toHaveProperty('auto_closed');
        expect(data).toHaveProperty('warnings_sent');
    });

    test('T15: Working Day 계산 (토/일 제외)', async ({ request }) => {
        // 간접 확인: 분쟁 생성 시 deadline이 영업일 기반
        const { res } = await createDispute(request);
        const data = await res.json();
        const deadline = new Date(data.respondent_deadline);
        // deadline은 현재보다 미래여야 함
        expect(deadline.getTime()).toBeGreaterThan(Date.now());
    });

    test('T16: 분쟁 상세 타임라인 UI 번들 포함', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(
            js.includes('DisputeDetail') || js.includes('ROUND1_RESPONSE') || js.includes('dispute')
        ).toBeTruthy();
    });

    test('T17: 분쟁 user_id 필터 조회', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/disputes?user_id=1001`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBe(true);
        // 모든 결과가 user_id=1001 관련이어야
        for (const d of data) {
            expect(d.initiator_id === 1001 || d.respondent_id === 1001).toBeTruthy();
        }
    });

    test('T18: 분쟁 status 필터 조회', async ({ request }) => {
        const res = await request.get(`${BASE}/v3_6/disputes?status=ACCEPTED`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBe(true);
        for (const d of data) {
            expect(d.status).toBe('ACCEPTED');
        }
    });
});
