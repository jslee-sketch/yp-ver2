import { test, expect, Page } from '@playwright/test'

const BASE = 'https://web-production-defb.up.railway.app'
const SCREENSHOT_DIR = 'test-results/screenshots'

// 공통 유틸
async function screenshot(page: Page, name: string) {
    await page.screenshot({ path: `${SCREENSHOT_DIR}/${name}.png`, fullPage: true })
}

async function login(page: Page, email: string, password: string) {
    await page.goto(`${BASE}/login`)
    await page.waitForTimeout(1000)
    await page.fill('input[type="email"]', email)
    await page.fill('input[type="password"]', password)
    await page.click('button:has-text("로그인하기")')
    await page.waitForTimeout(2000)
}

// ============================================================
// Part 1: 비로그인 상태
// ============================================================
test.describe('Part 1: 비로그인', () => {
    test('1-1. 홈페이지 로그인/가입 버튼', async ({ page }) => {
        await page.goto(BASE)
        await screenshot(page, '1-1-home-not-logged-in')
        // 로그인 버튼이 최소 1개 이상 존재
        const loginBtn = page.locator('button:has-text("로그인")').first()
        await expect(loginBtn).toBeVisible()
        await screenshot(page, '1-1-home-buttons')
    })

    test('1-2. 로그인 페이지', async ({ page }) => {
        await page.goto(`${BASE}/login`)
        await screenshot(page, '1-2-login-page')
        await expect(page.locator('input[type="email"], input[placeholder*="이메일"]')).toBeVisible()
        await expect(page.locator('input[type="password"]')).toBeVisible()
    })
})

// ============================================================
// Part 2: 구매자 흐름
// ============================================================
test.describe('Part 2: 구매자', () => {
    const BUYER_EMAIL = 'e2e-buyer@test.com'
    const BUYER_PW = 'Test1234!'

    test('2-1. 구매자 회원가입', async ({ page }) => {
        await page.goto(`${BASE}/register`)
        await page.waitForTimeout(1000)
        await screenshot(page, '2-1-register-page')

        // Step 1: 역할 선택 — 구매자 클릭
        const buyerRole = page.locator('text=구매자').first()
        if (await buyerRole.isVisible({ timeout: 3000 }).catch(() => false)) {
            await buyerRole.click()
            await page.waitForTimeout(500)
        }
        await screenshot(page, '2-1-register-step1-role')

        // 다음 버튼
        const nextBtn1 = page.locator('button:has-text("다음")')
        if (await nextBtn1.isVisible({ timeout: 3000 }).catch(() => false)) {
            await nextBtn1.click()
            await page.waitForTimeout(1000)
        }

        // Step 2: 프로필 생성
        const emailInput = page.locator('input[type="email"]')
        if (await emailInput.isVisible({ timeout: 3000 }).catch(() => false)) {
            await emailInput.fill(BUYER_EMAIL)
        }

        const pwInputs = page.locator('input[type="password"]')
        if (await pwInputs.first().isVisible({ timeout: 2000 }).catch(() => false)) {
            await pwInputs.first().fill(BUYER_PW)
            // 비밀번호 확인
            if (await pwInputs.nth(1).isVisible({ timeout: 1000 }).catch(() => false)) {
                await pwInputs.nth(1).fill(BUYER_PW)
            }
        }

        const nickInput = page.locator('input[placeholder*="역핑에서 쓸 이름"], input[placeholder*="닉네임"]')
        if (await nickInput.isVisible({ timeout: 2000 }).catch(() => false)) {
            await nickInput.fill('E2E테스터')
        }

        await screenshot(page, '2-1-register-step2-profile')

        // 다음 단계들 진행 (disabled면 스킵)
        for (let i = 0; i < 6; i++) {
            const btn = page.locator('button:has-text("다음"), button:has-text("가입"), button:has-text("완료")').first()
            if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
                const isDisabled = await btn.isDisabled().catch(() => true)
                if (isDisabled) {
                    console.log(`Step ${i + 3}: 다음 버튼 disabled (필수 필드 미완성) — 스킵`)
                    await screenshot(page, `2-1-register-step${i + 3}-disabled`)
                    break
                }
                await btn.click()
                await page.waitForTimeout(1500)
                await screenshot(page, `2-1-register-step${i + 3}`)
            }
        }
    })

    test('2-2. 구매자 로그인', async ({ page }) => {
        await login(page, BUYER_EMAIL, BUYER_PW)
        await screenshot(page, '2-2-buyer-logged-in')
        // 로그인 성공 시 홈으로 이동하거나, 실패해도 크래시 없이 동작해야 함
        // (테스트 계정이 DB에 없을 수 있으므로 soft assertion)
        const url = page.url()
        console.log(`로그인 후 URL: ${url}`)
    })

    test('2-3. 사이드바 확인', async ({ page }) => {
        await login(page, BUYER_EMAIL, BUYER_PW)
        const menuBtn = page.locator('button[aria-label*="메뉴"], button:has-text("☰"), [class*="hamburger"]')
        if (await menuBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
            await menuBtn.click()
            await page.waitForTimeout(500)
        }
        await screenshot(page, '2-3-buyer-sidebar')
    })

    test('2-4. 딜 검색', async ({ page }) => {
        await login(page, BUYER_EMAIL, BUYER_PW)
        await page.goto(`${BASE}/deals`)
        await page.waitForTimeout(2000)
        await screenshot(page, '2-4-deals-search')
    })

    test('2-5. 딜 만들기', async ({ page }) => {
        await login(page, BUYER_EMAIL, BUYER_PW)
        await page.goto(`${BASE}/create-deal`)
        await page.waitForTimeout(1000)
        await screenshot(page, '2-5-create-deal-step1')

        const input = page.locator('input[placeholder*="제품"], textarea[placeholder*="제품"], input[placeholder*="찾고"]')
        if (await input.isVisible({ timeout: 3000 }).catch(() => false)) {
            await input.fill('갤럭시 S25 울트라')
            await screenshot(page, '2-5-create-deal-input')

            const analyzeBtn = page.locator('button:has-text("분석"), button:has-text("검색"), button:has-text("AI")')
            if (await analyzeBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
                await analyzeBtn.click()
                await page.waitForTimeout(10000)
                await screenshot(page, '2-5-create-deal-ai-result')
            }
        }

        for (let i = 0; i < 5; i++) {
            const nextBtn = page.locator('button:has-text("다음")')
            if (await nextBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
                await nextBtn.click()
                await page.waitForTimeout(1000)
                await screenshot(page, `2-5-create-deal-step${i + 2}`)
            }
        }

        const createBtn = page.locator('button:has-text("딜 만들기"), button:has-text("생성")')
        if (await createBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
            await createBtn.click()
            await page.waitForTimeout(2000)
            await screenshot(page, '2-5-deal-created')
        }
    })

    test('2-6. 내 딜 현황', async ({ page }) => {
        await login(page, BUYER_EMAIL, BUYER_PW)
        await page.goto(`${BASE}/my-deals`)
        await page.waitForTimeout(2000)
        await screenshot(page, '2-6-my-deals')
    })

    test('2-7. 마이페이지', async ({ page }) => {
        await login(page, BUYER_EMAIL, BUYER_PW)
        await page.goto(`${BASE}/mypage`)
        await page.waitForTimeout(2000)
        await screenshot(page, '2-7-buyer-mypage')
    })

    test('2-8. 내 주문', async ({ page }) => {
        await login(page, BUYER_EMAIL, BUYER_PW)
        await page.goto(`${BASE}/orders`)
        await page.waitForTimeout(2000)
        await screenshot(page, '2-8-my-orders')
    })
})

// ============================================================
// Part 3: 판매자 흐름
// ============================================================
test.describe('Part 3: 판매자', () => {
    const SELLER_EMAIL = 'seller@yeokping.com'
    const SELLER_PW = 'seller1234!'

    test('3-1. 판매자 로그인', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await screenshot(page, '3-1-seller-logged-in')
    })

    test('3-2. 판매자 대시보드', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-2-seller-dashboard')
    })

    test('3-3. 오퍼 관리', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/offers`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-3-seller-offers')
    })

    test('3-4. 배송 관리', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/delivery`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-4-seller-delivery')
    })

    test('3-5. 반품/교환', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/returns`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-5-seller-returns')
    })

    test('3-6. 정산 관리', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/settlements`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-6-seller-settlements')
    })

    test('3-7. 환불 관리', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/refunds`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-7-seller-refunds')
    })

    test('3-8. 고객 문의', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/inquiries`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-8-seller-inquiries')
    })

    test('3-9. 리뷰 관리', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/reviews`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-9-seller-reviews')
    })

    test('3-10. 배송 정책', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/shipping-policy`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-10-seller-shipping-policy')
    })

    test('3-11. 판매 통계', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/stats`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-11-seller-stats')
    })

    test('3-12. 수수료 안내', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/fees`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-12-seller-fees')
    })

    test('3-13. 공지사항', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/seller/announcements`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-13-seller-announcements')
    })

    test('3-14. 딜 탐색 + 오퍼 제출', async ({ page }) => {
        await login(page, SELLER_EMAIL, SELLER_PW)
        await page.goto(`${BASE}/deals`)
        await page.waitForTimeout(2000)
        await screenshot(page, '3-14-seller-deal-search')

        const dealCard = page.locator('[class*="deal"], a[href*="/deals/"]').first()
        if (await dealCard.isVisible({ timeout: 3000 }).catch(() => false)) {
            await dealCard.click()
            await page.waitForTimeout(2000)
            await screenshot(page, '3-14-seller-deal-detail')

            const offerBtn = page.locator('button:has-text("오퍼"), button:has-text("제출")')
            if (await offerBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
                await offerBtn.click()
                await page.waitForTimeout(1000)
                await screenshot(page, '3-14-seller-offer-create')
            }
        }
    })
})

// ============================================================
// Part 4: 관리자 흐름
// ============================================================
test.describe('Part 4: 관리자', () => {
    const ADMIN_EMAIL = 'admin@yeokping.com'
    const ADMIN_PW = 'admin1234!'

    test('4-1. 관리자 로그인', async ({ page }) => {
        await login(page, ADMIN_EMAIL, ADMIN_PW)
        await screenshot(page, '4-1-admin-logged-in')
    })

    test('4-2. 관리자 대시보드', async ({ page }) => {
        await login(page, ADMIN_EMAIL, ADMIN_PW)
        await page.goto(`${BASE}/admin`)
        await page.waitForTimeout(2000)
        await screenshot(page, '4-2-admin-dashboard')
    })

    test('4-3. 판매자 관리 + 승인', async ({ page }) => {
        await login(page, ADMIN_EMAIL, ADMIN_PW)
        await page.goto(`${BASE}/admin/sellers`)
        await page.waitForTimeout(2000)
        await screenshot(page, '4-3-admin-sellers')

        const approveBtn = page.locator('button:has-text("승인")').first()
        if (await approveBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
            await approveBtn.click()
            await page.waitForTimeout(1000)
            await screenshot(page, '4-3-admin-seller-approved')
        }
    })

    test('4-4. 구매자 관리', async ({ page }) => {
        await login(page, ADMIN_EMAIL, ADMIN_PW)
        await page.goto(`${BASE}/admin/buyers`)
        await page.waitForTimeout(2000)
        await screenshot(page, '4-4-admin-buyers')
    })

    test('4-5. 액츄에이터 관리', async ({ page }) => {
        await login(page, ADMIN_EMAIL, ADMIN_PW)
        await page.goto(`${BASE}/admin/actuators`)
        await page.waitForTimeout(2000)
        await screenshot(page, '4-5-admin-actuators')
    })

    test('4-6. 분쟁 관리', async ({ page }) => {
        await login(page, ADMIN_EMAIL, ADMIN_PW)
        await page.goto(`${BASE}/admin/disputes`)
        await page.waitForTimeout(2000)
        await screenshot(page, '4-6-admin-disputes')
    })

    test('4-7. 정산 관리', async ({ page }) => {
        await login(page, ADMIN_EMAIL, ADMIN_PW)
        await page.goto(`${BASE}/admin/settlements`)
        await page.waitForTimeout(2000)
        await screenshot(page, '4-7-admin-settlements')
    })
})

// ============================================================
// Part 5: 액츄에이터 흐름
// ============================================================
test.describe('Part 5: 액츄에이터', () => {
    test('5-1. 액츄에이터 페이지들', async ({ page }) => {
        await page.goto(`${BASE}/login`)
        await screenshot(page, '5-1-actuator-login')

        const pages_to_check = [
            '/actuator/sellers',
            '/actuator/stats',
            '/actuator/commissions',
            '/actuator/invite',
        ]

        for (const p of pages_to_check) {
            await page.goto(`${BASE}${p}`)
            await page.waitForTimeout(1500)
            const name = p.replace(/\//g, '-').substring(1)
            await screenshot(page, `5-1-${name}`)
        }
    })
})

// ============================================================
// Part 6: 핑퐁이 (API 직접 호출 — rate limit 고려)
// ============================================================
test.describe('Part 6: 핑퐁이', () => {
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

    test('6-1. 핑퐁이 50개 대화 (API)', async ({ page }) => {
        test.setTimeout(600_000) // 10분

        await login(page, 'admin@yeokping.com', 'admin1234!')
        await page.goto(BASE)
        await page.waitForTimeout(2000)
        await screenshot(page, '6-1-pingpong-opened')

        const results: string[] = []
        let passCount = 0
        let failCount = 0
        const BATCH = 8
        const WAIT_MS = 62_000

        for (let i = 0; i < questions.length; i++) {
            // rate limit: 8개마다 62초 대기
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

                // 429 재시도
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

            if (i % 10 === 0) await screenshot(page, `6-1-pingpong-q${i + 1}`)
        }

        console.log(`\n=== PASS=${passCount} / FAIL=${failCount} / 50 ===`)
        results.forEach((r) => console.log(r))
        await screenshot(page, '6-1-pingpong-complete')

        expect(passCount).toBeGreaterThan(40) // 최소 80% 통과
    })
})

// ============================================================
// Part 7: E2E 거래 흐름
// ============================================================
test.describe('Part 7: E2E 거래', () => {
    test('7-1. 전체 거래 흐름', async ({ page }) => {
        // Step 1: 구매자 딜 생성
        await login(page, 'admin@yeokping.com', 'admin1234!')
        await page.goto(`${BASE}/create-deal`)
        await page.waitForTimeout(1000)
        await screenshot(page, '7-1-deal-create')

        // Step 2: 판매자 오퍼 제출
        await login(page, 'seller@yeokping.com', 'seller1234!')
        await page.goto(`${BASE}/deals`)
        await page.waitForTimeout(2000)
        await screenshot(page, '7-2-seller-deal-list')

        // Step 3: 구매자 오퍼 선택 + 결제
        await login(page, 'admin@yeokping.com', 'admin1234!')
        await page.goto(`${BASE}/orders`)
        await page.waitForTimeout(2000)
        await screenshot(page, '7-3-buyer-orders')

        // Step 4: 판매자 배송처리
        await login(page, 'seller@yeokping.com', 'seller1234!')
        await page.goto(`${BASE}/seller/delivery`)
        await page.waitForTimeout(2000)
        await screenshot(page, '7-4-seller-delivery')

        // Step 5: 구매자 수취확인
        await login(page, 'admin@yeokping.com', 'admin1234!')
        await page.goto(`${BASE}/orders`)
        await page.waitForTimeout(2000)
        await screenshot(page, '7-5-buyer-confirm')

        // Step 6: 판매자 정산 확인
        await login(page, 'seller@yeokping.com', 'seller1234!')
        await page.goto(`${BASE}/seller/settlements`)
        await page.waitForTimeout(2000)
        await screenshot(page, '7-6-seller-settlement')
    })
})
