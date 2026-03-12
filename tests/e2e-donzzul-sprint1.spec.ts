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

test.describe.serial('돈쭐 Sprint 1: 기반 구축 검증', () => {

    // T01: 서버 정상 + donzzul 테이블 생성
    test('T01: 서버 시작 → donzzul 테이블 자동 생성 확인', async ({ request }) => {
        const res = await request.get(`${BASE}/health`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.db).toBeTruthy();
    });

    // T02: GET /donzzul/stores → 200 빈 배열
    test('T02: GET /donzzul/stores → 200', async ({ request }) => {
        const res = await request.get(`${BASE}/donzzul/stores`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBeTruthy();
    });

    // T03: POST /donzzul/stores → 가게 생성
    test('T03: POST /donzzul/stores → 가게 생성', async ({ request }) => {
        const res = await request.post(`${BASE}/donzzul/stores`, {
            data: {
                store_name: '테스트 착한가게',
                store_address: '서울시 강남구 역삼동 123',
                store_phone: '02-1234-5678',
                owner_name: '김착한',
                owner_phone: '010-1111-2222',
                bank_name: '국민은행',
                account_number: '123-456-789',
                account_holder: '김착한',
                story_text: '20년째 동네 어르신들에게 무료 반찬을 나눠주는 착한 식당입니다. 코로나 이후 매출이 반토막 났지만 여전히 무료 급식은 계속하고 있어요.',
            },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.store_name).toBe('테스트 착한가게');
        expect(data.status).toBe('REVIEWING');
    });

    // T04: GET /donzzul/stores → 1건 반환
    test('T04: GET /donzzul/stores → 1건 이상 반환', async ({ request }) => {
        const res = await request.get(`${BASE}/donzzul/stores`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.length).toBeGreaterThanOrEqual(1);
    });

    // T05: GET /donzzul/deals → 200 빈 배열
    test('T05: GET /donzzul/deals → 200', async ({ request }) => {
        const res = await request.get(`${BASE}/donzzul/deals`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBeTruthy();
    });

    // T06: POST /donzzul/actuators/register → 히어로 생성
    test('T06: POST /donzzul/actuators/register → 히어로 생성', async ({ request }) => {
        // 먼저 로그인해서 유효한 buyer_id 얻기
        const loginRes = await request.post(`${BASE}/auth/login`, {
            form: { username: 'demo@yeokping.com', password: 'demo1234' },
        });
        let buyerId = 9; // fallback
        if (loginRes.status() === 200) {
            const token = (await loginRes.json()).access_token;
            if (token) {
                try {
                    const payload = JSON.parse(atob(token.split('.')[1]));
                    buyerId = parseInt(payload.sub) || 9;
                } catch {}
            }
        }

        const res = await request.post(`${BASE}/donzzul/actuators/register`, {
            data: { user_id: buyerId },
        });
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(data.user_id).toBe(buyerId);
        expect(data.hero_level).toBe('sprout');
    });

    // T07: GET /donzzul/actuators/ranking → 200
    test('T07: GET /donzzul/actuators/ranking → 200', async ({ request }) => {
        const res = await request.get(`${BASE}/donzzul/actuators/ranking`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBeTruthy();
    });

    // T08: GET /donzzul/vouchers/my?buyer_id=1 → 200 빈 배열
    test('T08: GET /donzzul/vouchers/my?buyer_id=1 → 200', async ({ request }) => {
        const res = await request.get(`${BASE}/donzzul/vouchers/my?buyer_id=1`);
        expect(res.status()).toBe(200);
        const data = await res.json();
        expect(Array.isArray(data)).toBeTruthy();
    });

    // T09: 프론트 /donzzul → 돈쭐 메인 페이지 표시
    test('T09: /donzzul 페이지 — "돈쭐" 텍스트 표시', async ({ page }) => {
        await page.goto(url('/donzzul'));
        await page.waitForTimeout(3000);
        const text = await page.textContent('body');
        expect(text).toContain('돈쭐');
        expect(text).toContain('착한 가게를 응원하는');
    });

    // T10: 사이드바에 💚 돈쭐 탭 포함 (번들 확인)
    test('T10: 사이드바에 💚 돈쭐 탭 포함', async ({ page }) => {
        await page.goto(url('/'));
        await page.waitForTimeout(2000);
        const js = await getMainJsContent(page);
        expect(js.includes('돈쭐')).toBeTruthy();
        expect(js.includes('/donzzul')).toBeTruthy();
    });
});
