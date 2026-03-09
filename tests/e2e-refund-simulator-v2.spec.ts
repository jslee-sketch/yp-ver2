import { test, Page } from '@playwright/test'

const BASE = 'https://web-production-defb.up.railway.app'
const SS = 'test-results/screenshots/simulator-v2'
const LOG: string[] = []

function log(msg: string) {
    const ts = new Date().toISOString().substring(11,19)
    console.log(`[${ts}] ${msg}`)
    LOG.push(`[${ts}] ${msg}`)
}

async function ss(page: Page, name: string) {
    await page.screenshot({ path: `${SS}/${name}.png`, fullPage: true })
}

async function api(page: Page, method: string, path: string, body?: any, headers?: any) {
    // Rate limit delay to avoid Railway 429
    await page.waitForTimeout(350)
    return await page.evaluate(async ({ base, m, p, b, h }) => {
        try {
            const opts: any = { method: m, headers: { 'Content-Type': 'application/json', ...h } }
            if (b) opts.body = JSON.stringify(b)
            const res = await fetch(`${base}${p}`, opts)
            const data = await res.json().catch(() => ({}))
            return { ok: res.ok, status: res.status, data }
        } catch (e: any) {
            return { ok: false, status: 0, data: {}, error: e.message }
        }
    }, { base: BASE, m: method, p: path, b: body, h: headers || {} })
}

async function login(page: Page, email: string, pw: string) {
    const r = await page.evaluate(async ({ base, e, p }) => {
        try {
            const body = new URLSearchParams({ username: e, password: p })
            const res = await fetch(`${base}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: body.toString(),
            })
            const data = await res.json().catch(() => ({}))
            return { ok: res.ok, data }
        } catch (e: any) {
            return { ok: false, data: {}, error: e.message }
        }
    }, { base: BASE, e: email, p: pw })
    if (r.ok && r.data.access_token) {
        log(`로그인 성공: ${email}`)
        return { h: { Authorization: `Bearer ${r.data.access_token}` } }
    }
    log(`로그인 실패: ${JSON.stringify(r.data)}`)
    return null
}

// 배송비 계산 헬퍼 (프론트 로직 동일)
function calcShipping(mode: string, baseFee: number, perItemFee: number, qty: number): number {
    if (mode === 'FREE') return 0
    if (mode === 'PER_RESERVATION') return baseFee
    // PER_ITEM: 기본 + (개당 × 수량)
    return baseFee + (perItemFee * qty)
}

// 사유 매핑 (프론트 동일)
const reasonMap: Record<string, { fault: string, trigger: string }> = {
    BUYER: { fault: 'BUYER', trigger: 'BUYER_CANCEL' },
    SELLER: { fault: 'SELLER', trigger: 'SELLER_CANCEL' },
    SYSTEM: { fault: 'SYSTEM', trigger: 'SYSTEM_ERROR' },
    DISPUTE: { fault: 'DISPUTE', trigger: 'DISPUTE_RESOLVE' },
}

// ============================================================
// Part 1: 수동 시뮬레이션 100가지 조합
// ============================================================
test.describe.serial('Part 1: 수동 100가지', () => {
    test('100 조합', async ({ page }) => {
        await page.goto(BASE)
        const auth = await login(page, 'admin@yeokping.com', 'admin1234!')
        if (!auth) { log('로그인 실패'); return }

        const prices = [30000, 150000, 500000, 1200000, 3000000]
        const shipModes = ['FREE', 'PER_RESERVATION', 'PER_ITEM']
        const baseFees = [0, 3000, 5000]
        const perItemFees = [0, 1000, 2000]
        const qtys = [1, 2, 3, 5]
        const reasons = ['BUYER', 'SELLER', 'SYSTEM', 'DISPUTE']
        const coolings = ['BEFORE_SHIPPING', 'SHIPPED_NOT_DELIVERED', 'WITHIN_COOLING', 'AFTER_COOLING']
        const settlements = ['NOT_SETTLED', 'SETTLED_TO_SELLER']

        let pass = 0, warn = 0, fail = 0
        const results: string[] = []

        for (let i = 0; i < 100; i++) {
            const price = prices[i % 5]
            const shipMode = shipModes[i % 3]
            const baseFee = shipMode === 'FREE' ? 0 : baseFees[i % 3]
            const perItemFee = shipMode === 'PER_ITEM' ? perItemFees[i % 3] : 0
            const qty = qtys[i % 4]
            const refQty = Math.min(Math.floor(Math.random() * qty) + 1, qty)
            const reason = reasons[i % 4]
            const cooling = coolings[i % 4]
            const settlement = settlements[i % 2]

            const totalShip = calcShipping(shipMode, baseFee, perItemFee, qty)
            const m = reasonMap[reason]

            const body = {
                mode: 'manual',
                product_price: price,
                shipping_fee: totalShip,
                quantity: qty,
                refund_quantity: refQty,
                fault_party: m.fault,
                trigger: m.trigger,
                cooling_state: cooling,
                settlement_state: settlement,
            }

            const r = await api(page, 'POST', '/admin/refund-simulate', body, auth.h)

            let verdict = 'PASS'
            let note = ''

            if (!r.ok) {
                verdict = 'FAIL'; fail++
                note = `API ${r.status}`
            } else if (r.data?.error) {
                verdict = 'FAIL'; fail++
                note = String(r.data.error).substring(0, 60)
            } else {
                const bd = r.data?.breakdown || {}
                const fees = r.data?.fees || {}

                // 검증 1: 상품 환불금 = 단가 × 환불수량
                const expectedGoods = price * refQty
                if (bd.goods_refund !== undefined && bd.goods_refund !== expectedGoods) {
                    verdict = 'WARN'; warn++
                    note += `상품불일치(${expectedGoods}→${bd.goods_refund}) `
                }

                // 검증 2: 배송비 정책
                const shipRefundable = bd.shipping_refund > 0
                // 구매자+배송시작 이후 → 배송비 환불 X
                if (['SHIPPED_NOT_DELIVERED','WITHIN_COOLING','AFTER_COOLING'].includes(cooling)
                    && reason === 'BUYER' && shipRefundable) {
                    verdict = 'WARN'; warn++
                    note += '구매자+배송후인데 배송비O '
                }
                // 분쟁 → 항상 배송비 환불 O (배송비 있을 때만)
                if (reason === 'DISPUTE' && totalShip > 0 && !shipRefundable) {
                    verdict = 'WARN'; warn++
                    note += '분쟁인데 배송비X '
                }
                // 판매자귀책+쿨링경과 → 배송비 X
                if (cooling === 'AFTER_COOLING' && reason === 'SELLER' && shipRefundable) {
                    verdict = 'WARN'; warn++
                    note += '판매자+쿨링경과인데 배송비O '
                }

                // 검증 3: 환불금 음수
                if (bd.total_refund < 0) {
                    verdict = 'FAIL'; fail++
                    note += `음수(${bd.total_refund}) `
                }

                // 검증 4: 수수료 부담자
                if (reason === 'BUYER' && fees.pg_fee_bearer && fees.pg_fee_bearer !== 'BUYER') {
                    verdict = 'WARN'; warn++
                    note += `PG부담=${fees.pg_fee_bearer}(예상BUYER) `
                }
                if (reason === 'SELLER' && fees.pg_fee_bearer && fees.pg_fee_bearer !== 'SELLER') {
                    verdict = 'WARN'; warn++
                    note += `PG부담=${fees.pg_fee_bearer}(예상SELLER) `
                }

                if (verdict === 'PASS') {
                    pass++
                    note = `환불=${bd.total_refund?.toLocaleString()} 배송비=${shipRefundable?'O':'X'} PG=${fees.pg_fee_bearer}`
                }
            }

            const shipLabel = shipMode === 'FREE' ? '무료'
                : shipMode === 'PER_RESERVATION' ? `건당${baseFee}`
                : `기본${baseFee}+개당${perItemFee}(총${totalShip})`

            results.push(`| ${i+1} | ${price.toLocaleString()} | ${shipLabel} | ${qty}→${refQty} | ${reason} | ${cooling} | ${settlement} | ${verdict} | ${note} |`)

            if ((i+1) % 25 === 0) log(`수동 ${i+1}/100 P=${pass} W=${warn} F=${fail}`)
        }

        log(`\n=== Part 1: PASS=${pass} WARN=${warn} FAIL=${fail} / 100 ===`)
        console.log('\n| # | 단가 | 배송비 | 수량 | 사유 | 배송상태 | 정산 | 판정 | 비고 |')
        console.log('|---|------|--------|------|------|----------|------|------|------|')
        results.forEach(r => console.log(r))
        await ss(page, 'P1-complete')
    })
})

// ============================================================
// Part 2: 실제 예약 10건
// ============================================================
test.describe.serial('Part 2: 실제 예약 10건', () => {
    test('DB 예약 기반', async ({ page }) => {
        await page.goto(BASE)
        const auth = await login(page, 'admin@yeokping.com', 'admin1234!')
        if (!auth) return

        const resResp = await api(page, 'GET', '/v3_6/search?status=PAID&limit=20', null, auth.h)
        const reservations = Array.isArray(resResp.data) ? resResp.data : resResp.data?.items || []
        log(`PAID 예약: ${reservations.length}건`)

        let pass = 0, fail = 0
        const results: string[] = []

        for (let i = 0; i < Math.min(10, reservations.length); i++) {
            const res = reservations[i]

            for (const reason of ['BUYER', 'SELLER', 'SYSTEM', 'DISPUTE']) {
                const m = reasonMap[reason]
                const body = {
                    mode: 'by_reservation',
                    reservation_id: res.id,
                    fault_party: m.fault,
                    trigger: m.trigger,
                }

                const r = await api(page, 'POST', '/admin/refund-simulate', body, auth.h)

                let verdict = 'PASS'
                let note = ''

                if (!r.ok || r.data?.error) {
                    verdict = 'FAIL'; fail++
                    note = r.data?.error || `${r.status}`
                } else {
                    pass++
                    const info = r.data?.reservation_info || {}
                    const result = r.data?.result || {}
                    note = `금액=${info.amount_total?.toLocaleString()} 결과=${JSON.stringify(result).substring(0, 80)}`
                }

                results.push(`| R-${res.id} | O-${res.offer_id||'?'} | ${reason} | ${verdict} | ${note} |`)
            }
        }

        log(`\n=== Part 2: PASS=${pass} FAIL=${fail} ===`)
        console.log('\n| 예약# | 오퍼# | 사유 | 판정 | 비고 |')
        console.log('|-------|-------|------|------|------|')
        results.forEach(r => console.log(r))
        await ss(page, 'P2-complete')
    })
})

// ============================================================
// Part 3: 분쟁 예약 10건
// ============================================================
test.describe.serial('Part 3: 분쟁 예약 10건', () => {
    test('분쟁 시뮬레이션', async ({ page }) => {
        await page.goto(BASE)
        const auth = await login(page, 'admin@yeokping.com', 'admin1234!')
        if (!auth) return

        const resResp = await api(page, 'GET', '/v3_6/search?is_disputed=true&limit=20', null, auth.h)
        let targets = Array.isArray(resResp.data) ? resResp.data : resResp.data?.items || []

        if (targets.length < 10) {
            const extra = await api(page, 'GET', '/v3_6/search?status=PAID&limit=20', null, auth.h)
            const ex = Array.isArray(extra.data) ? extra.data : extra.data?.items || []
            targets = [...targets, ...ex.slice(0, 10 - targets.length)]
        }

        log(`분쟁 대상: ${targets.length}건`)
        let pass = 0, fail = 0
        const results: string[] = []

        for (let i = 0; i < Math.min(10, targets.length); i++) {
            const res = targets[i]
            const amt = res.amount_total || 500000
            const qty = res.qty || 1

            const scenarios = [
                {
                    label: '분쟁→구매자승(전액)',
                    body: { mode:'manual', product_price:amt, shipping_fee:3000, quantity:qty, refund_quantity:qty,
                        fault_party:'DISPUTE', trigger:'DISPUTE_RESOLVE',
                        cooling_state: res.shipped_at ? 'WITHIN_COOLING' : 'BEFORE_SHIPPING',
                        settlement_state:'NOT_SETTLED' }
                },
                {
                    label: '분쟁→합의(50%)',
                    body: { mode:'manual', product_price:Math.floor(amt*0.5), shipping_fee:0, quantity:1, refund_quantity:1,
                        fault_party:'DISPUTE', trigger:'DISPUTE_RESOLVE',
                        cooling_state:'WITHIN_COOLING', settlement_state:'NOT_SETTLED' }
                },
                {
                    label: '판매자귀책+쿨링내',
                    body: { mode:'manual', product_price:amt, shipping_fee:3000, quantity:qty, refund_quantity:qty,
                        fault_party:'SELLER', trigger:'SELLER_CANCEL',
                        cooling_state:'WITHIN_COOLING', settlement_state:'NOT_SETTLED' }
                },
                {
                    label: '구매자취소+쿨링경과',
                    body: { mode:'manual', product_price:amt, shipping_fee:3000, quantity:qty, refund_quantity:1,
                        fault_party:'BUYER', trigger:'BUYER_CANCEL',
                        cooling_state:'AFTER_COOLING', settlement_state:'NOT_SETTLED' }
                },
                {
                    label: '정산완료후+분쟁환불',
                    body: { mode:'manual', product_price:amt, shipping_fee:3000, quantity:qty, refund_quantity:qty,
                        fault_party:'DISPUTE', trigger:'DISPUTE_RESOLVE',
                        cooling_state:'AFTER_COOLING', settlement_state:'SETTLED_TO_SELLER' }
                },
            ]

            for (const sc of scenarios) {
                const r = await api(page, 'POST', '/admin/refund-simulate', sc.body, auth.h)

                let verdict = 'PASS'
                let note = ''

                if (!r.ok || r.data?.error) {
                    verdict = 'FAIL'; fail++
                    note = r.data?.error || `${r.status}`
                } else {
                    pass++
                    const bd = r.data?.breakdown || {}
                    const si = r.data?.settlement_impact || {}
                    const shipRefundable = bd.shipping_refund > 0
                    note = `환불=${bd.total_refund?.toLocaleString()} 판매자=${si.seller_impact?.toLocaleString()} 배송비=${shipRefundable?'O':'X'}`

                    // 분쟁 해결인데 배송비 불가 (배송비 있을 때만) → 경고
                    if (sc.label.includes('분쟁') && sc.body.shipping_fee > 0 && !shipRefundable) {
                        verdict = 'WARN'
                        note += ' ⚠️분쟁인데배송비X'
                    }
                    // 쿨링경과+구매자인데 배송비 가능 → 경고
                    if (sc.label.includes('쿨링경과') && sc.body.fault_party === 'BUYER' && shipRefundable) {
                        verdict = 'WARN'
                        note += ' ⚠️쿨링경과+구매자인데배송비O'
                    }
                }

                results.push(`| R-${res.id} | ${res.is_disputed?'🔴':'⚪'} | ${sc.label} | ${verdict} | ${note} |`)
            }
        }

        log(`\n=== Part 3: PASS=${pass} FAIL=${fail} ===`)
        console.log('\n| 예약# | 분쟁 | 시나리오 | 판정 | 비고 |')
        console.log('|-------|------|---------|------|------|')
        results.forEach(r => console.log(r))
        await ss(page, 'P3-complete')
    })
})

// ============================================================
// Part 4: 엣지 케이스 20건
// ============================================================
test.describe.serial('Part 4: 엣지 케이스 20건', () => {
    test('경계값 + 이상 입력', async ({ page }) => {
        await page.goto(BASE)
        const auth = await login(page, 'admin@yeokping.com', 'admin1234!')
        if (!auth) return

        const cases = [
            { name: '가격 0원 무료배송', p:0, ship:0, q:1, rq:1, r:'BUYER', c:'BEFORE_SHIPPING', s:'NOT_SETTLED' },
            { name: '가격 1원', p:1, ship:0, q:1, rq:1, r:'BUYER', c:'BEFORE_SHIPPING', s:'NOT_SETTLED' },
            { name: '가격 음수', p:-100, ship:0, q:1, rq:1, r:'BUYER', c:'BEFORE_SHIPPING', s:'NOT_SETTLED' },
            { name: '수량 0', p:100000, ship:0, q:0, rq:0, r:'BUYER', c:'BEFORE_SHIPPING', s:'NOT_SETTLED' },
            { name: '환불 > 수량', p:100000, ship:0, q:1, rq:5, r:'BUYER', c:'BEFORE_SHIPPING', s:'NOT_SETTLED' },
            { name: '배송비만(상품0)', p:0, ship:5000, q:1, rq:1, r:'SELLER', c:'SHIPPED_NOT_DELIVERED', s:'NOT_SETTLED' },
            { name: '10억원 × 100개', p:1000000000, ship:50000, q:100, rq:50, r:'BUYER', c:'WITHIN_COOLING', s:'NOT_SETTLED' },
            { name: '정산완료+구매자+쿨링경과', p:500000, ship:3000, q:1, rq:1, r:'BUYER', c:'AFTER_COOLING', s:'SETTLED_TO_SELLER' },
            { name: '정산완료+판매자', p:500000, ship:3000, q:1, rq:1, r:'SELLER', c:'AFTER_COOLING', s:'SETTLED_TO_SELLER' },
            { name: '시스템+배송전', p:300000, ship:0, q:2, rq:2, r:'SYSTEM', c:'BEFORE_SHIPPING', s:'NOT_SETTLED' },
            { name: '분쟁+쿨링경과+정산완료', p:800000, ship:5000, q:1, rq:1, r:'DISPUTE', c:'AFTER_COOLING', s:'SETTLED_TO_SELLER' },
            { name: 'PER_ITEM 기본3000+개당1000×3', p:200000, ship:6000, q:3, rq:1, r:'BUYER', c:'BEFORE_SHIPPING', s:'NOT_SETTLED' },
            { name: 'PER_RESERVATION 건당5000', p:200000, ship:5000, q:5, rq:5, r:'SELLER', c:'WITHIN_COOLING', s:'NOT_SETTLED' },
            { name: '구매자+배송중', p:150000, ship:3000, q:1, rq:1, r:'BUYER', c:'SHIPPED_NOT_DELIVERED', s:'NOT_SETTLED' },
            { name: '판매자+배송중', p:150000, ship:3000, q:1, rq:1, r:'SELLER', c:'SHIPPED_NOT_DELIVERED', s:'NOT_SETTLED' },
            { name: '구매자+쿨링내', p:150000, ship:3000, q:1, rq:1, r:'BUYER', c:'WITHIN_COOLING', s:'NOT_SETTLED' },
            { name: '구매자+쿨링경과', p:150000, ship:3000, q:1, rq:1, r:'BUYER', c:'AFTER_COOLING', s:'NOT_SETTLED' },
            { name: '판매자+쿨링경과', p:150000, ship:3000, q:1, rq:1, r:'SELLER', c:'AFTER_COOLING', s:'NOT_SETTLED' },
            { name: '없는 예약 조회', p:0, ship:0, q:0, rq:0, r:'BUYER', c:'BEFORE_SHIPPING', s:'NOT_SETTLED', byRes:99999 },
            { name: '수량999 부분환불1', p:10000, ship:100000, q:999, rq:1, r:'BUYER', c:'BEFORE_SHIPPING', s:'NOT_SETTLED' },
        ]

        let pass = 0, fail = 0
        const results: string[] = []

        for (const c of cases) {
            let body: any
            if ((c as any).byRes) {
                body = { mode:'by_reservation', reservation_id:(c as any).byRes, fault_party:'BUYER', trigger:'BUYER_CANCEL' }
            } else {
                const m = reasonMap[c.r]
                body = { mode:'manual', product_price:c.p, shipping_fee:c.ship, quantity:c.q, refund_quantity:c.rq,
                    fault_party:m.fault, trigger:m.trigger, cooling_state:c.c, settlement_state:c.s }
            }

            const r = await api(page, 'POST', '/admin/refund-simulate', body, auth.h)

            let verdict = 'PASS'
            let note = ''

            if (c.name.includes('없는 예약')) {
                // Should return error for non-existent reservation
                verdict = (!r.ok || r.data?.error) ? 'PASS' : 'WARN'
                note = r.data?.error || r.data?.detail || '에러없이통과'
                if (verdict === 'PASS') pass++; else fail++
            } else if (c.p < 0 || c.q === 0) {
                // Edge cases - just record response
                verdict = 'PASS'; pass++
                const bd = r.data?.breakdown || {}
                note = `응답: 환불=${bd.total_refund ?? r.data?.error ?? '?'}`
            } else if (c.name.includes('환불 > 수량')) {
                const bd = r.data?.breakdown || {}
                verdict = (r.data?.error || (bd.total_refund <= c.p * c.q)) ? 'PASS' : 'WARN'
                note = `환불=${bd.total_refund || r.data?.error || '?'}`
                if (verdict === 'PASS') pass++; else fail++
            } else {
                if (!r.ok || r.data?.error) {
                    verdict = 'FAIL'; fail++
                    note = r.data?.error || `${r.status}`
                } else {
                    pass++
                    const bd = r.data?.breakdown || {}
                    const fees = r.data?.fees || {}
                    note = `환불=${bd.total_refund?.toLocaleString()} 배송비=${bd.shipping_refund > 0 ?'O':'X'} PG부담=${fees.pg_fee_bearer}`
                }
            }

            results.push(`| ${c.name} | ${verdict} | ${note} |`)
            log(`엣지: ${c.name} → ${verdict}`)
        }

        log(`\n=== Part 4: PASS=${pass} FAIL=${fail} ===`)
        console.log('\n| 케이스 | 판정 | 비고 |')
        console.log('|--------|------|------|')
        results.forEach(r => console.log(r))
        await ss(page, 'P4-complete')
    })
})

// ============================================================
// 최종 리포트
// ============================================================
test.describe.serial('리포트', () => {
    test('저장', async () => {
        const report = LOG.join('\n')
        console.log('\n' + '='.repeat(60))
        console.log('환불 시뮬레이터 v2 테스트 완료')
        console.log('='.repeat(60))

        const fs = require('fs')
        fs.writeFileSync('refund-simulator-v2-report.md',
            `# 환불 시뮬레이터 v2 테스트\n# ${new Date().toISOString()}\n\n${report}`)
        console.log('리포트: refund-simulator-v2-report.md')
    })
})
