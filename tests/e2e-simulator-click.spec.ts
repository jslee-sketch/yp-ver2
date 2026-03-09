import { test, Page } from '@playwright/test'

const BASE = 'https://web-production-defb.up.railway.app'
const SS = 'test-results/screenshots/sim-click'
const LOG: string[] = []

function log(msg: string) {
    const ts = new Date().toISOString().substring(11, 19)
    console.log(`[${ts}] ${msg}`)
    LOG.push(`[${ts}] ${msg}`)
}

async function ss(page: Page, name: string) {
    await page.screenshot({ path: `${SS}/${name}.png`, fullPage: true })
}

// 관리자 로그인 (UI form-data via fetch, then set token + navigate)
async function adminLogin(page: Page) {
    await page.goto(BASE)
    await page.waitForTimeout(500)
    const token = await page.evaluate(async (base) => {
        const body = new URLSearchParams({ username: 'admin@yeokping.com', password: 'admin1234!' })
        const res = await fetch(`${base}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: body.toString(),
        })
        const data = await res.json()
        if (data.access_token) {
            localStorage.setItem('access_token', data.access_token)
            localStorage.setItem('user', JSON.stringify({ id: 1, role: 'admin', email: 'admin@yeokping.com' }))
            return data.access_token
        }
        return null
    }, BASE)
    if (!token) throw new Error('Login failed')
    log('로그인 성공')
}

// 시뮬레이터 페이지 이동
async function goSimulator(page: Page) {
    await page.goto(`${BASE}/admin/refund-simulator`)
    await page.waitForTimeout(2000)
}

// 라벨 텍스트로 가장 가까운 input 찾기
async function fillByLabel(page: Page, labelText: string, value: string) {
    // label 요소 찾기, 그 부모 div 안의 input
    const container = page.locator(`div:has(> label:has-text("${labelText}"))`).first()
    const input = container.locator('input').first()
    if (await input.isVisible({ timeout: 1000 }).catch(() => false)) {
        await input.click()
        await page.keyboard.press('Control+a')
        await page.keyboard.type(value, { delay: 15 })
        await page.waitForTimeout(100)
    }
}

// 버튼 텍스트 클릭 (부분 매칭)
async function clickBtn(page: Page, text: string) {
    // 정확한 텍스트 매칭 우선, 없으면 부분 매칭
    const btn = page.locator(`button`).filter({ hasText: text }).first()
    if (await btn.isVisible({ timeout: 1000 }).catch(() => false)) {
        await btn.click()
        await page.waitForTimeout(200)
    }
}

// 결과 영역에서 특정 라벨의 값 읽기
async function readResultValue(page: Page, label: string): Promise<string> {
    const row = page.locator(`div:has(> span:has-text("${label}"))`).first()
    if (await row.isVisible({ timeout: 500 }).catch(() => false)) {
        return (await row.innerText()).replace(label, '').trim()
    }
    return ''
}

// 결과 패널 전체 텍스트 (오른쪽 그리드 영역)
async function readResultPanel(page: Page): Promise<string> {
    // 결과 패널은 grid의 두 번째 child
    const panels = page.locator('div[style*="grid-template-columns"] > div')
    const resultPanel = panels.nth(1)
    if (await resultPanel.isVisible({ timeout: 2000 }).catch(() => false)) {
        return await resultPanel.innerText()
    }
    return await page.evaluate(() => document.body.innerText)
}

// ============================================================
// 50건 시나리오 정의
// ============================================================
interface Scenario {
    name: string
    price: string
    qty: string
    rQty: string
    shipMode: 'FREE' | 'PER_RESERVATION' | 'PER_ITEM'
    shipBase?: string    // 기본 배송비 (PER_RESERVATION 또는 PER_ITEM)
    shipPerItem?: string // 개당 배송비 (PER_ITEM only)
    reason: string       // 사유 버튼 텍스트
    reasonDetail?: string // 드롭다운 옵션
    cooling: string      // 배송상태 버튼 텍스트
    settlement: string   // 정산상태 버튼 텍스트
}

const scenarios: Scenario[] = [
    // --- 기본 케이스 (1~10) ---
    { name: '기본: 10만 무료 구매자 배송전', price: '100000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '구매자 사유', reasonDetail: '단순 변심', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '기본: 50만 무료 판매자 배송전', price: '500000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '판매자 사유', reasonDetail: '상품 불량/하자', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '기본: 120만 무료 시스템 배송전', price: '1200000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '시스템 오류', reasonDetail: 'PG 결제 오류', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '기본: 30만 무료 분쟁 배송전', price: '300000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '분쟁 결과', reasonDetail: '분쟁 결과: 구매자 승', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '기본: 80만 건당3000 구매자 배송전', price: '800000', qty: '1', rQty: '1', shipMode: 'PER_RESERVATION', shipBase: '3000', reason: '구매자 사유', reasonDetail: '개인 사정 변경', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '기본: 20만 수량당 구매자 배송전', price: '200000', qty: '3', rQty: '3', shipMode: 'PER_ITEM', shipBase: '3000', shipPerItem: '2000', reason: '구매자 사유', reasonDetail: '중복 주문', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '기본: 150만 무료 판매자 배송중', price: '1500000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '판매자 사유', reasonDetail: '오배송 (다른 상품 수령)', cooling: '배송 중', settlement: '정산 미완료' },
    { name: '기본: 60만 건당5000 구매자 배송중', price: '600000', qty: '2', rQty: '2', shipMode: 'PER_RESERVATION', shipBase: '5000', reason: '구매자 사유', reasonDetail: '배송 지연으로 인한 취소', cooling: '배송 중', settlement: '정산 미완료' },
    { name: '기본: 45만 무료 판매자 쿨링내', price: '450000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '판매자 사유', reasonDetail: '상품 설명과 다름', cooling: '수취 완료', settlement: '정산 미완료' },
    { name: '기본: 90만 무료 구매자 쿨링경과', price: '900000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '구매자 사유', reasonDetail: '상품 필요 없어짐', cooling: '쿨링 경과', settlement: '정산 미완료' },

    // --- 부분환불 (11~20) ---
    { name: '부분: 10만×5 중 1', price: '100000', qty: '5', rQty: '1', shipMode: 'FREE', reason: '구매자 사유', reasonDetail: '단순 변심', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '부분: 30만×3 중 2 건당3000', price: '300000', qty: '3', rQty: '2', shipMode: 'PER_RESERVATION', shipBase: '3000', reason: '판매자 사유', reasonDetail: '수량 부족', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '부분: 50만×2 중 1 배송중', price: '500000', qty: '2', rQty: '1', shipMode: 'FREE', reason: '구매자 사유', reasonDetail: '주문 실수 (수량/옵션 오류)', cooling: '배송 중', settlement: '정산 미완료' },
    { name: '부분: 20만×5 중 3 수량당 쿨링내', price: '200000', qty: '5', rQty: '3', shipMode: 'PER_ITEM', shipBase: '3000', shipPerItem: '1000', reason: '판매자 사유', reasonDetail: '파손된 상태로 배송', cooling: '수취 완료', settlement: '정산 미완료' },
    { name: '부분: 80만×2 중 1 분쟁 쿨링내', price: '800000', qty: '2', rQty: '1', shipMode: 'FREE', reason: '분쟁 결과', reasonDetail: '분쟁 결과: 합의 (부분 환불)', cooling: '수취 완료', settlement: '정산 미완료' },
    { name: '부분: 15만×10 중 5 건당5000', price: '150000', qty: '10', rQty: '5', shipMode: 'PER_RESERVATION', shipBase: '5000', reason: '구매자 사유', reasonDetail: '가격 변동 (더 저렴해짐)', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '부분: 1만×99 중 1 수량당500', price: '10000', qty: '99', rQty: '1', shipMode: 'PER_ITEM', shipBase: '3000', shipPerItem: '500', reason: '판매자 사유', reasonDetail: '부품/액세서리 누락', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '부분: 200만×3 중 2 정산완료', price: '2000000', qty: '3', rQty: '2', shipMode: 'FREE', reason: '판매자 사유', reasonDetail: '작동 불량', cooling: '쿨링 경과', settlement: '정산 완료' },
    { name: '부분: 5만×5 중 4 시스템', price: '50000', qty: '5', rQty: '4', shipMode: 'FREE', reason: '시스템 오류', reasonDetail: '시스템 장애로 인한 이중 결제', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '부분: 40만×4 중 1 쿨링경과 구매자', price: '400000', qty: '4', rQty: '1', shipMode: 'PER_RESERVATION', shipBase: '3000', reason: '구매자 사유', reasonDetail: '리뷰 확인 후 취소', cooling: '쿨링 경과', settlement: '정산 미완료' },

    // --- 배송비 변형 (21~30) ---
    { name: '배송: 건당3000 전체 배송전 구매자', price: '200000', qty: '2', rQty: '2', shipMode: 'PER_RESERVATION', shipBase: '3000', reason: '구매자 사유', reasonDetail: '단순 변심', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '배송: 건당5000 배송중 판매자', price: '200000', qty: '1', rQty: '1', shipMode: 'PER_RESERVATION', shipBase: '5000', reason: '판매자 사유', reasonDetail: '오배송 (다른 상품 수령)', cooling: '배송 중', settlement: '정산 미완료' },
    { name: '배송: 수량당1000 5개전체 배송전', price: '100000', qty: '5', rQty: '5', shipMode: 'PER_ITEM', shipBase: '3000', shipPerItem: '1000', reason: '구매자 사유', reasonDetail: '개인 사정 변경', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '배송: 수량당2000 3중1 쿨링내 판매자', price: '300000', qty: '3', rQty: '1', shipMode: 'PER_ITEM', shipBase: '3000', shipPerItem: '2000', reason: '판매자 사유', reasonDetail: '사이즈/색상 불일치', cooling: '수취 완료', settlement: '정산 미완료' },
    { name: '배송: 건당3000 쿨링경과 구매자', price: '500000', qty: '1', rQty: '1', shipMode: 'PER_RESERVATION', shipBase: '3000', reason: '구매자 사유', reasonDetail: '단순 변심', cooling: '쿨링 경과', settlement: '정산 미완료' },
    { name: '배송: 건당5000 쿨링경과 판매자', price: '500000', qty: '1', rQty: '1', shipMode: 'PER_RESERVATION', shipBase: '5000', reason: '판매자 사유', reasonDetail: '허위 광고', cooling: '쿨링 경과', settlement: '정산 미완료' },
    { name: '배송: 수량당3000 분쟁 쿨링경과', price: '400000', qty: '2', rQty: '2', shipMode: 'PER_ITEM', shipBase: '3000', shipPerItem: '3000', reason: '분쟁 결과', reasonDetail: '분쟁 결과: 구매자 승', cooling: '쿨링 경과', settlement: '정산 미완료' },
    { name: '배송: 무료 정산완료 쿨링경과 구매자', price: '1000000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '구매자 사유', reasonDetail: '단순 변심', cooling: '쿨링 경과', settlement: '정산 완료' },
    { name: '배송: 건당10000 정산완료 쿨링내 판매자', price: '800000', qty: '1', rQty: '1', shipMode: 'PER_RESERVATION', shipBase: '10000', reason: '판매자 사유', reasonDetail: '상품 불량/하자', cooling: '수취 완료', settlement: '정산 완료' },
    { name: '배송: 수량당5000 10개 시스템 배송전', price: '50000', qty: '10', rQty: '10', shipMode: 'PER_ITEM', shipBase: '5000', shipPerItem: '5000', reason: '시스템 오류', reasonDetail: '가격 표기 오류', cooling: '배송 전', settlement: '정산 미완료' },

    // --- 분쟁 시나리오 (31~40) ---
    { name: '분쟁: 구매자승 전액 배송전', price: '500000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '분쟁 결과', reasonDetail: '분쟁 결과: 구매자 승', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '분쟁: 판매자승 배송중 건당3000', price: '300000', qty: '2', rQty: '2', shipMode: 'PER_RESERVATION', shipBase: '3000', reason: '분쟁 결과', reasonDetail: '분쟁 결과: 판매자 승', cooling: '배송 중', settlement: '정산 미완료' },
    { name: '분쟁: 합의부분 쿨링내', price: '1000000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '분쟁 결과', reasonDetail: '분쟁 결과: 합의 (부분 환불)', cooling: '수취 완료', settlement: '정산 미완료' },
    { name: '분쟁: 합의전액 쿨링경과 건당5000', price: '700000', qty: '1', rQty: '1', shipMode: 'PER_RESERVATION', shipBase: '5000', reason: '분쟁 결과', reasonDetail: '분쟁 결과: 합의 (전액 환불)', cooling: '쿨링 경과', settlement: '정산 미완료' },
    { name: '분쟁: 상호취소 배송전', price: '200000', qty: '3', rQty: '3', shipMode: 'FREE', reason: '분쟁 결과', reasonDetail: '분쟁 결과: 상호 취소', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '분쟁: 시한초과 쿨링내', price: '600000', qty: '2', rQty: '1', shipMode: 'FREE', reason: '분쟁 결과', reasonDetail: '분쟁 시한 초과 자동 판정', cooling: '수취 완료', settlement: '정산 미완료' },
    { name: '분쟁: 관리자직권 쿨링경과', price: '1500000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '분쟁 결과', reasonDetail: '관리자 직권 판정', cooling: '쿨링 경과', settlement: '정산 미완료' },
    { name: '분쟁: 직접입력 배송중 수량당', price: '450000', qty: '1', rQty: '1', shipMode: 'PER_ITEM', shipBase: '3000', shipPerItem: '3000', reason: '분쟁 결과', reasonDetail: '직접 입력', cooling: '배송 중', settlement: '정산 미완료' },
    { name: '분쟁: 관리자직권 정산완료', price: '1500000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '분쟁 결과', reasonDetail: '관리자 직권 판정', cooling: '쿨링 경과', settlement: '정산 완료' },
    { name: '분쟁: 합의부분 3중2 수량당2000', price: '250000', qty: '3', rQty: '2', shipMode: 'PER_ITEM', shipBase: '3000', shipPerItem: '2000', reason: '분쟁 결과', reasonDetail: '분쟁 결과: 합의 (부분 환불)', cooling: '수취 완료', settlement: '정산 미완료' },

    // --- 고가/대량/정산완료 (41~50) ---
    { name: '고가: 300만 무료 구매자 배송전', price: '3000000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '구매자 사유', reasonDetail: '다른 곳에서 더 저렴하게 구매', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '고가: 500만 건당10000 판매자 배송중', price: '5000000', qty: '1', rQty: '1', shipMode: 'PER_RESERVATION', shipBase: '10000', reason: '판매자 사유', reasonDetail: '상품 불량/하자', cooling: '배송 중', settlement: '정산 미완료' },
    { name: '대량: 1만×50 중 25 수량당500', price: '10000', qty: '50', rQty: '25', shipMode: 'PER_ITEM', shipBase: '5000', shipPerItem: '500', reason: '구매자 사유', reasonDetail: '단순 변심', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '대량: 5천×100 전체 시스템', price: '5000', qty: '100', rQty: '100', shipMode: 'FREE', reason: '시스템 오류', reasonDetail: '서버 오류로 인한 주문 오류', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '정산완료: 200만 구매자 쿨링내', price: '2000000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '구매자 사유', reasonDetail: '단순 변심', cooling: '수취 완료', settlement: '정산 완료' },
    { name: '정산완료: 100만×2 판매자 쿨링경과 건당5000', price: '1000000', qty: '2', rQty: '2', shipMode: 'PER_RESERVATION', shipBase: '5000', reason: '판매자 사유', reasonDetail: '작동 불량', cooling: '쿨링 경과', settlement: '정산 완료' },
    { name: '정산완료: 50만 분쟁 쿨링경과', price: '500000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '분쟁 결과', reasonDetail: '분쟁 결과: 구매자 승', cooling: '쿨링 경과', settlement: '정산 완료' },
    { name: '정산완료: 80만 시스템 배송전', price: '800000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '시스템 오류', reasonDetail: '자동 취소 기한 초과', cooling: '배송 전', settlement: '정산 완료' },
    { name: '최소: 1000원 무료 구매자 배송전', price: '1000', qty: '1', rQty: '1', shipMode: 'FREE', reason: '구매자 사유', reasonDetail: '단순 변심', cooling: '배송 전', settlement: '정산 미완료' },
    { name: '최대: 1000만×5 중3 수량당10000 분쟁 정산완료', price: '10000000', qty: '5', rQty: '3', shipMode: 'PER_ITEM', shipBase: '5000', shipPerItem: '10000', reason: '분쟁 결과', reasonDetail: '관리자 직권 판정', cooling: '쿨링 경과', settlement: '정산 완료' },
]

// 배송비 모드 버튼 텍스트 매핑
const shipBtnText: Record<string, string> = {
    FREE: '무료배송',
    PER_RESERVATION: '건당 배송비',
    PER_ITEM: '수량당 배송비',
}

// ============================================================
// 한 시나리오 실행 함수
// ============================================================
async function runScenario(page: Page, sc: Scenario, idx: number): Promise<{ verdict: string; note: string }> {
    // 1. 시뮬레이터 페이지 이동 (매번 fresh state)
    await goSimulator(page)
    await page.waitForTimeout(1000)

    // 2. 수동 시뮬레이션 탭 확인 (기본값)
    await clickBtn(page, '수동 시뮬레이션')
    await page.waitForTimeout(300)

    // 3. 상품 단가 입력
    await fillByLabel(page, '상품 단가', sc.price)

    // 4. 총 수량 입력
    await fillByLabel(page, '총 수량', sc.qty)

    // 5. 환불 수량 입력
    await fillByLabel(page, '환불 수량', sc.rQty)

    // 6. 배송비 유형 선택
    await clickBtn(page, shipBtnText[sc.shipMode])
    await page.waitForTimeout(500)

    // 7. 배송비 금액 입력
    if (sc.shipMode === 'PER_RESERVATION' && sc.shipBase) {
        await fillByLabel(page, '배송비 (건당', sc.shipBase)
    } else if (sc.shipMode === 'PER_ITEM') {
        if (sc.shipBase) await fillByLabel(page, '배송비 (기본', sc.shipBase)
        await page.waitForTimeout(200)
        if (sc.shipPerItem) await fillByLabel(page, '배송비 (개당', sc.shipPerItem)
    }
    await page.waitForTimeout(300)

    // 8. 배송 상태 선택
    await clickBtn(page, sc.cooling)
    await page.waitForTimeout(300)

    // 9. 환불 사유 주체 선택
    await clickBtn(page, sc.reason)
    await page.waitForTimeout(500)

    // 10. 상세 사유 드롭다운
    if (sc.reasonDetail) {
        const dropdown = page.locator('select').first()
        if (await dropdown.isVisible({ timeout: 1000 }).catch(() => false)) {
            try {
                await dropdown.selectOption({ label: sc.reasonDetail })
            } catch {
                // label not found, select first option
                await dropdown.selectOption({ index: 1 })
            }
        }
        await page.waitForTimeout(300)

        // "직접 입력" 선택 시 텍스트 입력
        if (sc.reasonDetail === '직접 입력') {
            const customInput = page.locator('input[placeholder*="사유를 직접"]').first()
            if (await customInput.isVisible({ timeout: 500 }).catch(() => false)) {
                await customInput.fill('테스트 직접 입력 사유')
            }
        }
    }

    // 11. 정산 상태 선택
    await clickBtn(page, sc.settlement)
    await page.waitForTimeout(300)

    // 12. 스크린샷 (입력 완료)
    await ss(page, `${String(idx).padStart(2, '0')}-input`)

    // 13. [시뮬레이션 실행] 버튼 클릭
    await clickBtn(page, '시뮬레이션 실행')
    await page.waitForTimeout(2500)

    // 14. 결과 읽기
    const resultText = await readResultPanel(page)

    // 15. 스크린샷 (결과)
    await ss(page, `${String(idx).padStart(2, '0')}-result`)

    // 16. 판정
    let verdict = 'PASS'
    let note = ''

    if (resultText.includes('시뮬레이션 실패') || resultText.includes('Internal error')) {
        verdict = 'FAIL'
        note = 'API 에러'
    } else if (resultText.includes('환불 금액 분석') || resultText.includes('총 환불액')) {
        // 결과가 정상적으로 표시됨
        const refundMatch = resultText.match(/총 환불액\s*([\d,]+)원/)
        const reasonMatch = resultText.match(/사유 주체\s*(.+)/)
        const policyMatch = resultText.match(/배송비 환불\s*(가능|불가)/)

        note = refundMatch ? `환불=${refundMatch[1]}원` : '환불금 표시됨'
        if (reasonMatch) note += ` 사유=${reasonMatch[1].trim()}`
        if (policyMatch) note += ` 배송비=${policyMatch[1]}`

        // 사유 주체 표시 확인 (결과에 "환불 사유" 섹션 존재)
        if (!resultText.includes('환불 사유') && !resultText.includes('사유 주체')) {
            note += ' ⚠️사유미표시'
        }
    } else if (resultText.includes('조건을 입력')) {
        verdict = 'FAIL'
        note = '결과 미표시 (버튼 미클릭?)'
    } else {
        note = '결과 텍스트 확인 필요'
    }

    return { verdict, note }
}

// ============================================================
// 테스트 실행 (5개씩 묶어서 batch)
// ============================================================
const BATCH_SIZE = 5

for (let batch = 0; batch < Math.ceil(scenarios.length / BATCH_SIZE); batch++) {
    const batchStart = batch * BATCH_SIZE
    const batchEnd = Math.min(batchStart + BATCH_SIZE, scenarios.length)
    const batchName = `Batch ${batch + 1}: 시나리오 ${batchStart + 1}~${batchEnd}`

    test.describe.serial(batchName, () => {
        test(batchName, async ({ page }) => {
            // Login once per batch
            await adminLogin(page)

            for (let i = batchStart; i < batchEnd; i++) {
                const sc = scenarios[i]
                const idx = i + 1

                try {
                    const { verdict, note } = await runScenario(page, sc, idx)
                    log(`[${idx}/50] ${sc.name} → ${verdict} | ${note}`)
                } catch (err: any) {
                    log(`[${idx}/50] ${sc.name} → ERROR | ${err.message?.substring(0, 80)}`)
                    await ss(page, `${String(idx).padStart(2, '0')}-error`)
                }

                // 429 방지: 5초 대기
                if (i < batchEnd - 1) {
                    await page.waitForTimeout(5000)
                }
            }
        })
    })
}

// ============================================================
// 최종 리포트
// ============================================================
test.describe.serial('리포트', () => {
    test('저장', async () => {
        console.log('\n' + '='.repeat(60))
        console.log('환불 시뮬레이터 브라우저 클릭 50건 완료')
        console.log('='.repeat(60))
        console.log(LOG.join('\n'))

        let pass = 0, fail = 0, error = 0
        for (const l of LOG) {
            if (l.includes('→ PASS')) pass++
            else if (l.includes('→ FAIL')) fail++
            else if (l.includes('→ ERROR')) error++
        }
        console.log(`\nPASS: ${pass} / FAIL: ${fail} / ERROR: ${error} / Total: ${pass + fail + error}`)

        const fs = require('fs')
        fs.writeFileSync('simulator-click-50-report.md',
            `# 환불 시뮬레이터 브라우저 클릭 50건\n` +
            `# ${new Date().toISOString()}\n\n` +
            `## 요약: PASS=${pass} FAIL=${fail} ERROR=${error}\n\n` +
            '| # | 시나리오 | 판정 | 비고 |\n|---|---------|------|------|\n' +
            LOG.map(l => {
                const m = l.match(/\[(\d+)\/50\] (.+?) → (\w+) \| (.*)/)
                return m ? `| ${m[1]} | ${m[2]} | ${m[3]} | ${m[4]} |` : `| | ${l} | | |`
            }).join('\n'))
        console.log('리포트: simulator-click-50-report.md')
    })
})
