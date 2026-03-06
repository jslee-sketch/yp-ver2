import { test, expect, Page } from '@playwright/test'

const BASE = 'https://web-production-defb.up.railway.app'
const SS = 'test-results/screenshots/level2'

async function ss(page: Page, name: string) {
    await page.screenshot({ path: `${SS}/${name}.png`, fullPage: true })
}

async function login(page: Page, email: string, password: string) {
    await page.goto(`${BASE}/login`)
    await page.waitForTimeout(500)
    await page.fill('input[type="email"]', email)
    await page.fill('input[type="password"]', password)
    await page.click('button:has-text("로그인하기")')
    await page.waitForTimeout(2000)
}

// API 직접 호출 헬퍼
async function apiPost(page: Page, path: string, body: unknown) {
    return await page.evaluate(
        async ({ url, data }) => {
            const token = localStorage.getItem('token') || ''
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                body: JSON.stringify(data),
            })
            return { status: res.status, data: await res.json().catch(() => ({})) }
        },
        { url: `${BASE}${path}`, data: body },
    )
}

async function apiGet(page: Page, path: string) {
    return await page.evaluate(
        async ({ url }) => {
            const token = localStorage.getItem('token') || ''
            const res = await fetch(url, {
                headers: { Authorization: `Bearer ${token}` },
            })
            return { status: res.status, data: await res.json().catch(() => ({})) }
        },
        { url: `${BASE}${path}` },
    )
}

// ============================================================
// 시나리오 1: 다중 구매자 회원가입 (5명)
// ============================================================
test.describe('시나리오 1: 다중 회원가입', () => {
    const buyers = [
        { email: 'buyer1@e2e.com', pw: 'Test1234!', nick: '구매자일' },
        { email: 'buyer2@e2e.com', pw: 'Test1234!', nick: '구매자이' },
        { email: 'buyer3@e2e.com', pw: 'Test1234!', nick: '구매자삼' },
        { email: 'buyer4@e2e.com', pw: 'Test1234!', nick: '구매자사' },
        { email: 'buyer5@e2e.com', pw: 'Test1234!', nick: '구매자오' },
    ]

    for (const b of buyers) {
        test(`가입: ${b.nick}`, async ({ page }) => {
            await page.goto(`${BASE}/register`)
            await page.waitForTimeout(1000)

            const emailInput = page.locator('input[placeholder*="이메일"], input[name="email"]')
            if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) await emailInput.fill(b.email)

            const pwInput = page.locator('input[placeholder*="비밀번호"], input[name="password"]')
            if (await pwInput.isVisible({ timeout: 3000 }).catch(() => false)) await pwInput.fill(b.pw)

            const confirmPw = page.locator('input[placeholder*="비밀번호 확인"]')
            if (await confirmPw.isVisible({ timeout: 2000 }).catch(() => false)) await confirmPw.fill(b.pw)

            const nickInput = page.locator('input[placeholder*="닉네임"], input[name="nickname"]')
            if (await nickInput.isVisible({ timeout: 2000 }).catch(() => false)) await nickInput.fill(b.nick)

            const nameInput = page.locator('input[placeholder*="이름"], input[name="name"]')
            if (await nameInput.isVisible({ timeout: 2000 }).catch(() => false)) await nameInput.fill(b.nick)

            await ss(page, `1-register-${b.nick}`)

            for (let i = 0; i < 6; i++) {
                const btn = page.locator('button:has-text("다음"), button:has-text("가입"), button:has-text("완료")').first()
                if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
                    const isDisabled = await btn.isDisabled().catch(() => true)
                    if (isDisabled) {
                        console.log(`${b.nick}: Step ${i + 1} 다음 버튼 disabled — 스킵`)
                        break
                    }
                    await btn.click()
                    await page.waitForTimeout(1000)
                }
            }
            await ss(page, `1-register-complete-${b.nick}`)
        })
    }
})

// ============================================================
// 시나리오 2: 구매자 3명이 각각 딜 생성
// ============================================================
test.describe('시나리오 2: 다중 딜 생성', () => {
    const deals = [
        { buyer: 'buyer1@e2e.com', product: '아이폰 16 프로' },
        { buyer: 'buyer2@e2e.com', product: '삼성 갤럭시 S25' },
        { buyer: 'buyer3@e2e.com', product: 'LG 그램 노트북' },
    ]

    for (const d of deals) {
        test(`딜 생성: ${d.product}`, async ({ page }) => {
            await login(page, d.buyer, 'Test1234!')
            await page.goto(`${BASE}/create-deal`)
            await page.waitForTimeout(1000)

            const input = page.locator('input[placeholder*="제품"], textarea, input[placeholder*="찾고"]')
            if (await input.isVisible({ timeout: 3000 }).catch(() => false)) {
                await input.fill(d.product)
                const btn = page.locator('button:has-text("분석"), button:has-text("AI")')
                if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
                    await btn.click()
                    await page.waitForTimeout(10000)
                }
            }
            await ss(page, `2-deal-${d.product.replace(/\s/g, '')}`)

            for (let i = 0; i < 5; i++) {
                const nextBtn = page
                    .locator('button:has-text("다음"), button:has-text("딜 만들기")')
                    .first()
                if (await nextBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
                    await nextBtn.click()
                    await page.waitForTimeout(1000)
                }
            }
            await ss(page, `2-deal-created-${d.product.replace(/\s/g, '')}`)
        })
    }
})

// ============================================================
// 시나리오 3: 판매자가 같은 딜에 오퍼 경쟁
// ============================================================
test.describe('시나리오 3: 오퍼 경쟁', () => {
    test('3명이 같은 딜에 오퍼 제출', async ({ page }) => {
        await login(page, 'seller@yeokping.com', 'seller1234!')

        const dealsResp = await apiGet(page, '/deals/?page=1&size=10')
        await ss(page, '3-offer-competition-deals')
        console.log(`딜 목록: ${JSON.stringify(dealsResp.data).substring(0, 200)}`)

        const prices = [1500000, 1450000, 1400000]
        for (let i = 0; i < prices.length; i++) {
            const offerResp = await apiPost(page, '/v3_6/offers', {
                deal_id: 1,
                price: prices[i],
                total_available_qty: 10,
                shipping_mode: 'FREE',
                shipping_fee_standard: 0,
                delivery_days: 3,
            })
            console.log(`오퍼 ${i + 1} (${prices[i]}원): status=${offerResp.status}`)
        }
        await ss(page, '3-offer-competition-submitted')
    })
})

// ============================================================
// 시나리오 4: 여러 구매자가 같은 오퍼에 예약
// ============================================================
test.describe('시나리오 4: 동시 예약', () => {
    test('구매자 3명이 같은 오퍼에 예약', async ({ page }) => {
        const buyers = ['buyer1@e2e.com', 'buyer2@e2e.com', 'buyer3@e2e.com']

        for (let i = 0; i < buyers.length; i++) {
            await login(page, buyers[i], 'Test1234!')

            const reserveResp = await apiPost(page, '/v3_6/reservations/', {
                offer_id: 1,
                buyer_id: i + 1,
                qty: 1,
                deal_id: 1,
            })
            console.log(
                `예약 ${buyers[i]}: status=${reserveResp.status}, data=${JSON.stringify(reserveResp.data).substring(0, 100)}`,
            )

            if (reserveResp.status === 200 || reserveResp.status === 201) {
                const resId = reserveResp.data?.id || reserveResp.data?.reservation_id
                if (resId) {
                    const payResp = await apiPost(page, `/v3_6/reservations/${resId}/pay`, {
                        buyer_id: i + 1,
                    })
                    console.log(`결제 ${buyers[i]}: status=${payResp.status}`)
                }
            }
            await ss(page, `4-reservation-${i + 1}`)
        }
    })
})

// ============================================================
// 시나리오 5: 배송 + 환불 다중 케이스
// ============================================================
test.describe('시나리오 5: 배송+환불 시나리오', () => {
    test('판매자 배송처리 + 구매자 수취확인', async ({ page }) => {
        await login(page, 'seller@yeokping.com', 'seller1234!')
        await page.goto(`${BASE}/seller/delivery`)
        await page.waitForTimeout(2000)
        await ss(page, '5-delivery-list')

        const shipResp = await apiPost(page, '/v3_6/reservations/1/ship', {
            shipping_carrier: 'CJ대한통운',
            tracking_number: 'E2E123456789',
        })
        console.log(`배송처리: status=${shipResp.status}`)
        await ss(page, '5-shipped')
    })

    test('구매자 수취확인', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const confirmResp = await apiPost(page, '/v3_6/reservations/1/arrival-confirm', {
            buyer_id: 1,
        })
        console.log(`수취확인: status=${confirmResp.status}`)
        await ss(page, '5-arrival-confirmed')
    })

    test('환불 Case A: 배송 전 환불', async ({ page }) => {
        await login(page, 'buyer2@e2e.com', 'Test1234!')

        const previewResp = await apiGet(page, '/v3_6/refund/preview/2?actor=buyer_cancel')
        console.log(
            `환불프리뷰: status=${previewResp.status}, data=${JSON.stringify(previewResp.data).substring(0, 200)}`,
        )

        const refundResp = await apiPost(page, '/v3_6/refund', {
            reservation_id: 2,
            actor: 'buyer_cancel',
        })
        console.log(`환불실행: status=${refundResp.status}`)
        await ss(page, '5-refund-case-a')
    })

    test('환불 Case E: 부분 환불', async ({ page }) => {
        await login(page, 'buyer3@e2e.com', 'Test1234!')

        const refundResp = await apiPost(page, '/v3_6/refund', {
            reservation_id: 3,
            actor: 'buyer_cancel',
        })
        console.log(`부분환불: status=${refundResp.status}`)
        await ss(page, '5-refund-case-e')
    })
})

// ============================================================
// 시나리오 6: 분쟁 흐름
// ============================================================
test.describe('시나리오 6: 분쟁', () => {
    test('분쟁 개시 -> 관리자 종료', async ({ page }) => {
        await login(page, 'admin@yeokping.com', 'admin1234!')

        const openResp = await apiPost(page, '/v3_6/3/dispute/open', {
            reason: 'E2E 테스트 분쟁',
        })
        console.log(`분쟁개시: status=${openResp.status}`)

        await page.goto(`${BASE}/admin/disputes`)
        await page.waitForTimeout(2000)
        await ss(page, '6-dispute-list')

        const closeResp = await apiPost(page, '/v3_6/3/dispute/close', {
            note: 'E2E 테스트 분쟁 종료',
        })
        console.log(`분쟁종료: status=${closeResp.status}`)
        await ss(page, '6-dispute-closed')
    })
})

// ============================================================
// 시나리오 7: 배드 케이스 — 잘못된 입력
// ============================================================
test.describe('시나리오 7: 배드 케이스', () => {
    test('7-1. 빈 이메일로 로그인', async ({ page }) => {
        await page.goto(`${BASE}/login`)
        await page.click('button:has-text("로그인")')
        await page.waitForTimeout(1000)
        await ss(page, '7-1-empty-login')
    })

    test('7-2. 틀린 비밀번호로 로그인', async ({ page }) => {
        await page.goto(`${BASE}/login`)
        await page.fill('input[type="email"]', 'admin@yeokping.com')
        await page.fill('input[type="password"]', 'wrongpassword')
        await page.click('button:has-text("로그인")')
        await page.waitForTimeout(2000)
        await ss(page, '7-2-wrong-password')
    })

    test('7-3. 음수 가격으로 오퍼 제출', async ({ page }) => {
        await login(page, 'seller@yeokping.com', 'seller1234!')

        const resp = await apiPost(page, '/v3_6/offers', {
            deal_id: 1,
            price: -100,
            total_available_qty: 10,
            shipping_mode: 'FREE',
            delivery_days: 3,
        })
        console.log(`음수 가격 오퍼: status=${resp.status}, data=${JSON.stringify(resp.data).substring(0, 200)}`)
        await ss(page, '7-3-negative-price')
        expect(resp.status).toBeGreaterThanOrEqual(400)
    })

    test('7-4. 0원 가격으로 오퍼 제출', async ({ page }) => {
        await login(page, 'seller@yeokping.com', 'seller1234!')

        const resp = await apiPost(page, '/v3_6/offers', {
            deal_id: 1,
            price: 0,
            total_available_qty: 10,
            shipping_mode: 'FREE',
            delivery_days: 3,
        })
        console.log(`0원 오퍼: status=${resp.status}`)
        await ss(page, '7-4-zero-price')
    })

    test('7-5. 수량 0으로 예약', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const resp = await apiPost(page, '/v3_6/reservations/', {
            offer_id: 1,
            buyer_id: 1,
            qty: 0,
            deal_id: 1,
        })
        console.log(`수량0 예약: status=${resp.status}`)
        await ss(page, '7-5-zero-quantity')
        expect(resp.status).toBeGreaterThanOrEqual(400)
    })

    test('7-6. 음수 수량으로 예약', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const resp = await apiPost(page, '/v3_6/reservations/', {
            offer_id: 1,
            buyer_id: 1,
            qty: -5,
            deal_id: 1,
        })
        console.log(`음수 예약: status=${resp.status}`)
        await ss(page, '7-6-negative-quantity')
        expect(resp.status).toBeGreaterThanOrEqual(400)
    })

    test('7-7. 존재하지 않는 오퍼에 예약', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const resp = await apiPost(page, '/v3_6/reservations/', {
            offer_id: 99999,
            buyer_id: 1,
            qty: 1,
            deal_id: 1,
        })
        console.log(`없는 오퍼 예약: status=${resp.status}`)
        await ss(page, '7-7-nonexistent-offer')
        expect(resp.status).toBeGreaterThanOrEqual(400)
    })

    test('7-8. 이미 결제된 예약 재결제', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const resp = await apiPost(page, '/v3_6/reservations/1/pay', {
            buyer_id: 1,
        })
        console.log(`이중결제: status=${resp.status}`)
        await ss(page, '7-8-double-payment')
    })

    test('7-9. 닉네임 1글자로 가입', async ({ page }) => {
        await page.goto(`${BASE}/register`)
        await page.waitForTimeout(500)
        const nickInput = page.locator('input[placeholder*="닉네임"]')
        if (await nickInput.isVisible({ timeout: 3000 }).catch(() => false)) {
            await nickInput.fill('A')
            await page.waitForTimeout(500)
            await ss(page, '7-9-short-nickname')
        }
    })

    test('7-10. SQL injection 시도', async ({ page }) => {
        await page.goto(`${BASE}/login`)
        await page.fill('input[type="email"]', "admin'; DROP TABLE users;--")
        await page.fill('input[type="password"]', "' OR '1'='1")
        await page.click('button:has-text("로그인")')
        await page.waitForTimeout(2000)
        await ss(page, '7-10-sql-injection')
    })

    test('7-11. XSS 시도', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const resp = await apiPost(page, '/v3_6/pingpong/ask', {
            question: '<script>alert("xss")</script>',
            screen: 'home',
            context: {},
            mode: 'read_only',
        })
        console.log(`XSS 시도: status=${resp.status}`)
        await ss(page, '7-11-xss-attempt')
    })

    test('7-12. 초대형 텍스트 입력', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const hugeText = 'A'.repeat(100000)
        const resp = await apiPost(page, '/v3_6/pingpong/ask', {
            question: hugeText,
            screen: 'home',
            context: {},
            mode: 'read_only',
        })
        console.log(`초대형 텍스트: status=${resp.status}`)
        await ss(page, '7-12-huge-text')
    })
})

// ============================================================
// 시나리오 8: 권한 위반 테스트
// ============================================================
test.describe('시나리오 8: 권한 위반', () => {
    test('8-1. 구매자가 판매자 API 호출', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const resp = await apiPost(page, '/v3_6/offers', {
            deal_id: 1,
            price: 100000,
            total_available_qty: 5,
            shipping_mode: 'FREE',
            delivery_days: 3,
        })
        console.log(`구매자->오퍼제출: status=${resp.status}`)
        await ss(page, '8-1-buyer-creates-offer')
    })

    test('8-2. 판매자가 딜 생성 시도', async ({ page }) => {
        await login(page, 'seller@yeokping.com', 'seller1234!')
        await page.goto(`${BASE}/create-deal`)
        await page.waitForTimeout(1000)
        await ss(page, '8-2-seller-create-deal')
    })

    test('8-3. 구매자가 관리자 페이지 접근', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')
        await page.goto(`${BASE}/admin`)
        await page.waitForTimeout(1000)
        await ss(page, '8-3-buyer-admin-access')
    })

    test('8-4. 구매자가 다른 구매자의 주문 환불 시도', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const resp = await apiPost(page, '/v3_6/refund', {
            reservation_id: 999,
            actor: 'buyer_cancel',
        })
        console.log(`타인 환불 시도: status=${resp.status}`)
        await ss(page, '8-4-other-user-refund')
    })

    test('8-5. 비로그인 상태로 API 호출', async ({ page }) => {
        await page.goto(BASE)

        const resp = await page.evaluate(async (url) => {
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ offer_id: 1, buyer_id: 1, qty: 1, deal_id: 1 }),
            })
            return { status: res.status }
        }, `${BASE}/v3_6/reservations/`)
        console.log(`비로그인 예약: status=${resp.status}`)
        await ss(page, '8-5-no-auth-api')
    })
})

// ============================================================
// 시나리오 9: 만료/타임아웃 시나리오
// ============================================================
test.describe('시나리오 9: 만료/타임아웃', () => {
    test('9-1. 만료된 딜에 오퍼 제출', async ({ page }) => {
        await login(page, 'seller@yeokping.com', 'seller1234!')

        const resp = await apiPost(page, '/v3_6/offers', {
            deal_id: 999,
            price: 100000,
            total_available_qty: 5,
            shipping_mode: 'FREE',
            delivery_days: 3,
        })
        console.log(`만료딜 오퍼: status=${resp.status}`)
        await ss(page, '9-1-expired-deal-offer')
    })

    test('9-2. 이미 취소된 예약 결제', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const resp = await apiPost(page, '/v3_6/reservations/2/pay', {
            buyer_id: 1,
        })
        console.log(`취소된 예약 결제: status=${resp.status}`)
        await ss(page, '9-2-cancelled-reservation-pay')
    })

    test('9-3. 배송 전 수취확인 시도', async ({ page }) => {
        await login(page, 'buyer1@e2e.com', 'Test1234!')

        const resp = await apiPost(page, '/v3_6/reservations/99/arrival-confirm', {
            buyer_id: 1,
        })
        console.log(`배송전 수취확인: status=${resp.status}`)
        await ss(page, '9-3-premature-arrival')
    })

    test('9-4. 이미 환불된 예약 재환불', async ({ page }) => {
        await login(page, 'buyer2@e2e.com', 'Test1234!')

        const resp = await apiPost(page, '/v3_6/refund', {
            reservation_id: 2,
            actor: 'buyer_cancel',
        })
        console.log(`이중환불: status=${resp.status}`)
        await ss(page, '9-4-double-refund')
    })
})

// ============================================================
// 시나리오 10: 핑퐁이 50개 대화 (API 직접)
// ============================================================
test.describe('시나리오 10: 핑퐁이 50개 대화', () => {
    const questions = [
        '안녕', '오늘 기분이 좋아', '카리나는 어느 그룹이야?',
        '맛있는 저녁 메뉴 추천해줘', '핑퐁이 넌 누구야?',
        '역핑은 어떤 플랫폼이야?', '딜방이 뭐야?', '오퍼가 뭐야?',
        '액츄에이터가 뭐야?', '관전자는 뭐하는 사람이야?',
        '환불 정책 알려줘', '환불 가능 기간이 며칠이야?',
        '배송 전에 환불 가능해?', '배송 후에도 환불 돼?',
        '부분 환불도 가능해?', '결제 제한시간이 몇 분이야?',
        '정산은 언제 되나요?', '쿨링 기간이 뭐야?',
        '수수료는 얼마야?', '포인트는 어떻게 적립돼?',
        '오퍼 마감이 몇 시간이야?', '딜방 모집 기간은?',
        '오퍼 수정 가능해?', '오퍼 취소는 어떻게 해?',
        '딜방은 어떻게 만들어?', '예약번호 13번 환불 가능해?',
        '딜 15번 상태가 어때?', '오퍼 10번 마감 언제야?',
        '내 포인트 잔액 얼마야?', '예약 7번 배송 어디까지 왔어?',
        '오늘 서울 날씨 어때?', '미국 관련 뉴스 알려줘',
        '갤럭시 S25 최저가 얼마야?', '환율 알려줘',
        '에어팟 프로 가격 비교해줘', '딜 만들고 싶은데 어떻게 해?',
        '오퍼 중에 어떤 걸 선택하면 좋아?', '배송이 안 오면 어떻게 해?',
        '리뷰는 어디서 써?', '분쟁 신청하고 싶어',
        '오퍼를 어떻게 제출해?', '정산 내역은 어디서 확인해?',
        '배송 처리는 어떻게 하나요?', '구매자가 환불 요청했는데 어떻게 해?',
        '내 판매 수수료율이 얼마야?',
        '김치 먹다가 갤럭시 봤는데 가격이 궁금해',
        '쿨링 기간 지나면 정산 돼?', '환불하면 포인트도 돌려받아?',
        '역핑이랑 쿠팡이랑 뭐가 달라?',
        '판매자 등급이 올라가면 수수료가 달라져?',
    ]

    test('핑퐁이 50개 대화', async ({ page }) => {
        test.setTimeout(600_000) // 10분

        await login(page, 'admin@yeokping.com', 'admin1234!')
        await page.goto(BASE)
        await page.waitForTimeout(2000)

        const results: string[] = []
        let passCount = 0
        let failCount = 0
        const BATCH = 8
        const WAIT_MS = 62_000

        for (let i = 0; i < questions.length; i++) {
            if (i > 0 && i % BATCH === 0) {
                console.log(`  [WAIT] rate limit pause 62s... (after ${i})`)
                await page.waitForTimeout(WAIT_MS)
            }

            const q = questions[i]
            try {
                const resp = await page.evaluate(
                    async ({ url, question }) => {
                        const res = await fetch(url, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ question, screen: 'home', context: {}, mode: 'read_only' }),
                        })
                        if (res.status === 429) return { status: 429, answer: 'RATE_LIMITED', engine: 'rate_limit' }
                        const d = await res.json()
                        return { status: res.status, answer: d.answer || '', engine: d.engine || 'unknown' }
                    },
                    { url: `${BASE}/v3_6/pingpong/ask`, question: q },
                )

                let answer = resp.answer
                let engine = resp.engine

                if (resp.status === 429) {
                    console.log(`  [429] retrying after 62s...`)
                    await page.waitForTimeout(WAIT_MS)
                    const retry = await page.evaluate(
                        async ({ url, question }) => {
                            const res = await fetch(url, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ question, screen: 'home', context: {}, mode: 'read_only' }),
                            })
                            const d = await res.json().catch(() => ({}))
                            return { answer: d.answer || '', engine: d.engine || 'unknown' }
                        },
                        { url: `${BASE}/v3_6/pingpong/ask`, question: q },
                    )
                    answer = retry.answer
                    engine = retry.engine
                }

                const truncated = (answer || '(empty)').replace(/\|/g, '/').replace(/\n/g, ' ').substring(0, 200)
                const pass =
                    !answer || answer.includes('확인 중이에요') || answer.includes('네트워크 연결')
                        ? 'FAIL'
                        : 'PASS'

                if (pass === 'PASS') passCount++
                else failCount++

                results.push(`| ${i + 1} | ${q} | ${truncated} | ${engine} | ${pass} |`)
                console.log(`[${i + 1}/50] ${pass} ${engine} - ${q}`)
            } catch (e) {
                failCount++
                results.push(`| ${i + 1} | ${q} | ERROR | error | FAIL |`)
                console.log(`[${i + 1}/50] FAIL error - ${q}`)
            }
        }

        console.log(`\n=== PASS=${passCount} / FAIL=${failCount} / 50 ===`)
        await ss(page, '10-pingpong-complete')

        expect(passCount).toBeGreaterThan(40)
    })
})
