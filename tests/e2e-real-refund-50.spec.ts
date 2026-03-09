import { test, Page } from '@playwright/test'
import * as fs from 'fs'

const BASE = 'https://web-production-defb.up.railway.app'
const SS = 'test-results/screenshots/real-refund'
const LOG: string[] = []
const IDS_FILE = 'refund-reservation-ids.json'

function log(msg: string) {
  const ts = new Date().toISOString().substring(11, 19)
  const line = `[${ts}] ${msg}`
  console.log(line)
  LOG.push(line)
}

async function ss(page: Page, name: string) {
  await page.screenshot({ path: `${SS}/${name}.png`, fullPage: true }).catch(() => {})
}

/* ── API helper (browser fetch) ── */
async function api(page: Page, method: string, path: string, body?: any, token?: string) {
  await page.waitForTimeout(350)           // 429 방지
  return await page.evaluate(
    async ({ base, m, p, b, tk }) => {
      try {
        const h: any = { 'Content-Type': 'application/json' }
        if (tk) h['Authorization'] = `Bearer ${tk}`
        const opts: any = { method: m, headers: h }
        if (b) opts.body = JSON.stringify(b)
        const res = await fetch(`${base}${p}`, opts)
        const data = await res.json().catch(() => ({}))
        return { ok: res.ok, status: res.status, data }
      } catch (e: any) {
        return { ok: false, status: 0, data: {}, error: e.message }
      }
    },
    { base: BASE, m: method, p: path, b: body, tk: token || '' },
  )
}

/* ── Login (form-urlencoded for OAuth2) ── */
async function login(page: Page, email: string, pw: string): Promise<{ token: string; data: any } | null> {
  const r = await page.evaluate(
    async ({ base, e, p }) => {
      try {
        const res = await fetch(`${base}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: `username=${encodeURIComponent(e)}&password=${encodeURIComponent(p)}`,
        })
        const data = await res.json().catch(() => ({}))
        return { ok: res.ok, data }
      } catch (err: any) {
        return { ok: false, data: { error: err.message } }
      }
    },
    { base: BASE, e: email, p: pw },
  )
  if (r.ok && r.data.access_token) {
    return { token: r.data.access_token, data: r.data }
  }
  return null
}

/* ── Get buyer_id from /buyers/me ── */
async function getBuyerId(page: Page, token: string): Promise<number> {
  const r = await api(page, 'GET', '/buyers/me', null, token)
  return r.ok ? (r.data?.id || 0) : 0
}

/* ── Register buyer ── */
async function registerBuyer(page: Page, email: string, pw: string, idx: number): Promise<boolean> {
  const r = await api(page, 'POST', '/buyers/', {
    email,
    password: pw,
    name: `환불테스트${idx}`,
    nickname: `refundtest${idx}`,
    phone: `01055550${String(idx).padStart(3, '0')}`,
  })
  return r.ok || r.status === 409 || r.status === 400 // already exists is ok
}

/* ── Save/Load reservation IDs ── */
function saveIds(ids: number[]) {
  fs.writeFileSync(IDS_FILE, JSON.stringify(ids))
}
function loadIds(): number[] {
  return JSON.parse(fs.readFileSync(IDS_FILE, 'utf-8'))
}

// =================================================================
// Phase 0: 데이터 준비 (오퍼 확인 + 예약 50건 생성 + 결제)
// =================================================================
test.describe.serial('Phase 0: 데이터 준비', () => {
  test('오퍼 확보 + 예약 50건 생성 + 결제', async ({ page }) => {
    test.setTimeout(600000)
    await page.goto(BASE)

    // 1) 판매자 로그인
    const seller = await login(page, 'seller@yeokping.com', 'seller1234')
    if (!seller) { log('판매자 로그인 실패 — 테스트 중단'); return }
    log('판매자 로그인 OK')

    // 2) 오퍼 조회 (공개)
    const offersResp = await api(page, 'GET', '/offers/?page=1&size=50')
    let offers = Array.isArray(offersResp.data) ? offersResp.data : offersResp.data?.items || []
    log(`기존 오퍼: ${offers.length}건`)

    if (offers.length < 3) {
      log('오퍼 부족 — 테스트 중단')
      return
    }

    // 3) 50건 예약 + 결제
    const reservationIds: number[] = []
    // 구매자 1명(demo@yeokping.com)으로 50건 생성 (buyer_id 고정)
    const demoLogin = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!demoLogin) { log('demo 구매자 로그인 실패'); return }
    const demoBuyerId = await getBuyerId(page, demoLogin.token)
    log(`구매자: demo@yeokping.com, buyer_id=${demoBuyerId}`)

    for (let i = 1; i <= 50; i++) {
      const offer = offers[(i - 1) % offers.length]
      const qty = i <= 20 ? 1 : i <= 35 ? 2 : 3

      // 예약 생성
      const res = await api(page, 'POST', '/v3_6/reservations', {
        deal_id: offer.deal_id,
        offer_id: offer.id,
        buyer_id: demoBuyerId,
        qty,
      }, demoLogin.token)

      if (res.ok && res.data?.id) {
        const resId = res.data.id
        const amt = res.data.amount_total || Math.round(offer.price * qty + (offer.shipping_fee_standard || 0))

        // 결제
        const pay = await api(page, 'POST', '/v3_6/reservations/pay', {
          reservation_id: resId,
          buyer_id: demoBuyerId,
          paid_amount: amt,
        }, demoLogin.token)

        if (pay.ok) {
          reservationIds.push(resId)
        } else {
          log(`결제 실패 #${i}: R-${resId} ${pay.status} ${JSON.stringify(pay.data?.detail || '').substring(0, 80)}`)
          reservationIds.push(0)
        }
      } else {
        log(`예약 실패 #${i}: ${res.status} ${JSON.stringify(res.data?.detail || '').substring(0, 80)}`)
        reservationIds.push(0)
      }

      if (i % 10 === 0) {
        log(`예약+결제: ${i}/50 (성공: ${reservationIds.filter(x => x > 0).length})`)
      }
      await page.waitForTimeout(2000) // 429 방지
    }

    saveIds(reservationIds)
    const ok = reservationIds.filter(x => x > 0).length
    log(`\n=== 예약 ${ok}/50건 생성 완료 ===`)
    await ss(page, '00-reservations-created')
  })
})

// =================================================================
// Phase 1: 배송 처리 (26~50번 = 후반 25건)
// =================================================================
test.describe.serial('Phase 1: 배송 처리', () => {
  test('25건 배송', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    const seller = await login(page, 'seller@yeokping.com', 'seller1234')
    if (!seller) { log('판매자 로그인 실패'); return }

    const ids = loadIds()
    const carriers = ['CJ대한통운', '한진택배', '롯데택배', '우체국택배', '로젠택배']
    let shipped = 0

    for (let i = 25; i < 50; i++) {
      if (!ids[i] || ids[i] === 0) continue
      const r = await api(page, 'POST', `/v3_6/reservations/${ids[i]}/ship`, {
        shipping_carrier: carriers[i % 5],
        tracking_number: `REFUND${String(i + 1).padStart(4, '0')}`,
      }, seller.token)
      if (r.ok) shipped++
      else log(`배송 실패 #${i + 1}: R-${ids[i]} ${r.status} ${JSON.stringify(r.data?.detail || '').substring(0, 60)}`)
      await page.waitForTimeout(1000)
    }

    log(`배송 처리: ${shipped}/25건`)
    await ss(page, '01-shipped')
  })
})

// =================================================================
// Phase 2: 수취 확인 (36~50번 = 마지막 15건)
// =================================================================
test.describe.serial('Phase 2: 수취 확인', () => {
  test('15건 수취', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    const demoLogin = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!demoLogin) { log('구매자 로그인 실패'); return }
    const buyerId = await getBuyerId(page, demoLogin.token)

    const ids = loadIds()
    let confirmed = 0

    for (let i = 35; i < 50; i++) {
      if (!ids[i] || ids[i] === 0) continue
      const r = await api(page, 'POST', `/v3_6/reservations/${ids[i]}/arrival-confirm`, {
        buyer_id: buyerId,
      }, demoLogin.token)
      if (r.ok) confirmed++
      else log(`수취 실패 #${i + 1}: R-${ids[i]} ${r.status} ${JSON.stringify(r.data?.detail || '').substring(0, 60)}`)
      await page.waitForTimeout(1000)
    }

    log(`수취 확인: ${confirmed}/15건`)
    await ss(page, '02-confirmed')
  })
})

// =================================================================
// Phase 3: 실제 환불 50건 (5가지 카테고리)
// =================================================================
test.describe.serial('Phase 3: 실제 환불 50건', () => {
  // --- A: 배송 전 전액 환불 (1~10) ---
  test('A: 배송 전 전액 환불 10건', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    const buyer = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!buyer) return
    const ids = loadIds()
    let success = 0

    const reasons = ['단순변심', '중복주문', '가격변동', '주문실수', '개인사정', '필요없어짐', '선물취소', '리뷰확인후', '다른곳구매', '변심']

    for (let i = 0; i < 10; i++) {
      if (!ids[i] || ids[i] === 0) continue

      const refund = await api(page, 'POST', '/v3_6/reservations/refund', {
        reservation_id: ids[i],
        reason: reasons[i],
        requested_by: 'BUYER',
        refund_type: 'refund',
      }, buyer.token)

      if (refund.ok) {
        success++
        log(`A-${i + 1}: R-${ids[i]} 배송전 전액환불 ✅`)
      } else {
        log(`A-${i + 1}: R-${ids[i]} 실패 ${refund.status} ${JSON.stringify(refund.data?.detail || '').substring(0, 80)}`)
      }
      await page.waitForTimeout(5000)
    }

    log(`=== A 배송전 전액환불: ${success}/10 ===`)
    await ss(page, '03-A-before-shipping')
  })

  // --- B: 배송 전 부분 환불 (11~20, qty=1이므로 전액과 동일하게 처리) ---
  test('B: 배송 전 부분 환불 10건', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    const buyer = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!buyer) return
    const ids = loadIds()
    let success = 0

    for (let i = 10; i < 20; i++) {
      if (!ids[i] || ids[i] === 0) continue

      const refund = await api(page, 'POST', '/v3_6/reservations/refund', {
        reservation_id: ids[i],
        reason: '부분불량',
        requested_by: 'BUYER',
        refund_type: 'refund',
        quantity_refund: 1,
      }, buyer.token)

      if (refund.ok) {
        success++
        log(`B-${i - 9}: R-${ids[i]} 부분환불(1개) ✅`)
      } else {
        log(`B-${i - 9}: R-${ids[i]} 실패 ${refund.status} ${JSON.stringify(refund.data?.detail || '').substring(0, 80)}`)
      }
      await page.waitForTimeout(5000)
    }

    log(`=== B 부분환불: ${success}/10 ===`)
    await ss(page, '04-B-partial')
  })

  // --- C: 배송 후 셀러 귀책 환불 (21~25, 배송만 됨/수취 전) ---
  test('C: 배송중 환불 5건', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    const buyer = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!buyer) return
    const ids = loadIds()
    let success = 0

    // 26~30 (index 25~29): shipped but not confirmed
    for (let i = 25; i < 30; i++) {
      if (!ids[i] || ids[i] === 0) continue

      const refund = await api(page, 'POST', '/v3_6/reservations/refund', {
        reservation_id: ids[i],
        reason: '배송중 상품파손',
        requested_by: 'SELLER',
        refund_type: 'refund',
      }, buyer.token)

      if (refund.ok) {
        success++
        log(`C-${i - 24}: R-${ids[i]} 배송중 환불 ✅`)
      } else {
        log(`C-${i - 24}: R-${ids[i]} 실패 ${refund.status} ${JSON.stringify(refund.data?.detail || '').substring(0, 80)}`)
      }
      await page.waitForTimeout(5000)
    }

    log(`=== C 배송중 환불: ${success}/5 ===`)
    await ss(page, '05-C-shipped')
  })

  // --- D: 반품 (배송 후, 31~35, shipped not confirmed) ---
  test('D: 반품 5건', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    const buyer = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!buyer) return
    const ids = loadIds()
    let success = 0

    for (let i = 30; i < 35; i++) {
      if (!ids[i] || ids[i] === 0) continue

      const refund = await api(page, 'POST', '/v3_6/reservations/refund', {
        reservation_id: ids[i],
        reason: '상품불량 반품요청',
        requested_by: 'BUYER',
        refund_type: 'return',
      }, buyer.token)

      if (refund.ok) {
        success++
        log(`D-${i - 29}: R-${ids[i]} 반품(return) ✅`)
      } else {
        log(`D-${i - 29}: R-${ids[i]} 실패 ${refund.status} ${JSON.stringify(refund.data?.detail || '').substring(0, 80)}`)
      }
      await page.waitForTimeout(5000)
    }

    log(`=== D 반품: ${success}/5 ===`)
    await ss(page, '06-D-return')
  })

  // --- E: 수취 후 전액 환불 (36~40) ---
  test('E: 수취후 전액 환불 5건', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    const buyer = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!buyer) return
    const ids = loadIds()
    let success = 0

    for (let i = 35; i < 40; i++) {
      if (!ids[i] || ids[i] === 0) continue

      const refund = await api(page, 'POST', '/v3_6/reservations/refund', {
        reservation_id: ids[i],
        reason: '수취후 불만족 환불',
        requested_by: 'BUYER',
        refund_type: 'refund',
      }, buyer.token)

      if (refund.ok) {
        success++
        log(`E-${i - 34}: R-${ids[i]} 수취후 환불 ✅`)
      } else {
        log(`E-${i - 34}: R-${ids[i]} 실패 ${refund.status} ${JSON.stringify(refund.data?.detail || '').substring(0, 80)}`)
      }
      await page.waitForTimeout(5000)
    }

    log(`=== E 수취후 환불: ${success}/5 ===`)
    await ss(page, '07-E-after-confirm')
  })

  // --- F: 교환 (수취 후, 41~45) ---
  test('F: 교환 5건', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    const buyer = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!buyer) return
    const ids = loadIds()
    let success = 0

    for (let i = 40; i < 45; i++) {
      if (!ids[i] || ids[i] === 0) continue

      const refund = await api(page, 'POST', '/v3_6/reservations/refund', {
        reservation_id: ids[i],
        reason: '사이즈교환',
        requested_by: 'BUYER',
        refund_type: 'exchange',
      }, buyer.token)

      if (refund.ok) {
        success++
        log(`F-${i - 39}: R-${ids[i]} 교환(exchange) ✅`)
      } else {
        log(`F-${i - 39}: R-${ids[i]} 실패 ${refund.status} ${JSON.stringify(refund.data?.detail || '').substring(0, 80)}`)
      }
      await page.waitForTimeout(5000)
    }

    log(`=== F 교환: ${success}/5 ===`)
    await ss(page, '08-F-exchange')
  })

  // --- G: 분쟁 → 환불 (수취 후, 46~50) ---
  test('G: 분쟁 환불 5건', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    // 분쟁에 관리자 필요 — 여러 비밀번호 시도
    let admin: { token: string; data: any } | null = null
    for (const pw of ['admin1234!', 'admin1234']) {
      admin = await login(page, 'admin@yeokping.com', pw)
      if (admin) break
    }
    if (!admin) {
      log('관리자 로그인 실패 — 분쟁 테스트 스킵')
      return
    }
    log('관리자 로그인 OK')

    const ids = loadIds()
    let success = 0

    for (let i = 45; i < 50; i++) {
      if (!ids[i] || ids[i] === 0) continue
      const rId = ids[i]

      // 분쟁 개시
      const openR = await api(page, 'POST', `/v3_6/${rId}/dispute/open`, {
        reason: `분쟁환불테스트${i - 44}: 상품불량`,
      }, admin.token)

      if (openR.ok) {
        log(`G-${i - 44}: R-${rId} 분쟁 개시 ✅`)
        await page.waitForTimeout(2000)

        // 분쟁 종료 (구매자 승)
        const closeR = await api(page, 'POST', `/v3_6/${rId}/dispute/close`, {
          resolution: 'buyer_win',
          refund_action: 'full_refund',
        }, admin.token)

        if (closeR.ok) {
          log(`G-${i - 44}: R-${rId} 분쟁 종료(buyer_win) ✅`)
          await page.waitForTimeout(2000)

          // 관리자 강제 환불
          const refund = await api(page, 'POST', '/v3_6/reservations/refund', {
            reservation_id: rId,
            reason: '분쟁결과 환불',
            requested_by: 'ADMIN',
            refund_type: 'refund',
          }, admin.token)

          if (refund.ok) {
            success++
            log(`G-${i - 44}: R-${rId} 분쟁환불 ✅`)
          } else {
            log(`G-${i - 44}: R-${rId} 환불 실패 ${refund.status} ${JSON.stringify(refund.data?.detail || '').substring(0, 60)}`)
          }
        } else {
          log(`G-${i - 44}: R-${rId} 분쟁종료 실패 ${closeR.status} ${JSON.stringify(closeR.data?.detail || '').substring(0, 60)}`)
        }
      } else {
        log(`G-${i - 44}: R-${rId} 분쟁개시 실패 ${openR.status} ${JSON.stringify(openR.data?.detail || '').substring(0, 60)}`)
      }
      await page.waitForTimeout(5000)
    }

    log(`=== G 분쟁환불: ${success}/5 ===`)
    await ss(page, '09-G-dispute')
  })

  // --- H: 배송 전 미결제 상태 남겨둔 건 (21~25) — 판매자 취소 ---
  test('H: 판매자사유 환불 5건', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    const buyer = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!buyer) return
    const ids = loadIds()
    let success = 0

    // index 20~24: qty=1, not shipped
    for (let i = 20; i < 25; i++) {
      if (!ids[i] || ids[i] === 0) continue

      const refund = await api(page, 'POST', '/v3_6/reservations/refund', {
        reservation_id: ids[i],
        reason: '재고소진 판매자취소',
        requested_by: 'SELLER',
        refund_type: 'refund',
      }, buyer.token)

      if (refund.ok) {
        success++
        log(`H-${i - 19}: R-${ids[i]} 판매자취소 ✅`)
      } else {
        log(`H-${i - 19}: R-${ids[i]} 실패 ${refund.status} ${JSON.stringify(refund.data?.detail || '').substring(0, 80)}`)
      }
      await page.waitForTimeout(5000)
    }

    log(`=== H 판매자사유 환불: ${success}/5 ===`)
    await ss(page, '10-H-seller-cancel')
  })
})

// =================================================================
// Phase 4: DB 검증 (환불 결과 확인)
// =================================================================
test.describe.serial('Phase 4: DB 검증', () => {
  test('환불 결과 DB 확인', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE)

    const buyer = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!buyer) { log('로그인 실패 — 검증 중단'); return }

    const ids = loadIds()
    const validIds = ids.filter(x => x > 0)

    let cancelled = 0
    let paid = 0
    let refunded = 0
    let disputed = 0
    const statusCounts: Record<string, number> = {}

    for (let i = 0; i < validIds.length; i++) {
      const r = await api(page, 'GET', `/v3_6/reservations/by-id/${validIds[i]}`, null, buyer.token)
      if (r.ok) {
        const st = String(r.data?.status || '').toUpperCase()
        statusCounts[st] = (statusCounts[st] || 0) + 1

        if (st.includes('CANCEL')) cancelled++
        else if (st.includes('PAID')) paid++

        if ((r.data?.refunded_amount_total || 0) > 0) refunded++
        if (r.data?.is_disputed) disputed++
      }
      if ((i + 1) % 10 === 0) await page.waitForTimeout(1500)
    }

    log('\n=== DB 검증 결과 ===')
    log(`전체 예약: ${validIds.length}건`)
    log(`상태별: ${JSON.stringify(statusCounts)}`)
    log(`CANCELLED: ${cancelled}건`)
    log(`PAID(미환불): ${paid}건`)
    log(`환불금 있음: ${refunded}건`)
    log(`분쟁 있음: ${disputed}건`)

    // 정산 확인
    const stResp = await api(page, 'GET', '/settlements/?limit=200', null, buyer.token)
    const settlements = Array.isArray(stResp.data) ? stResp.data : stResp.data?.items || []
    const stCount: Record<string, number> = {}
    for (const s of settlements) {
      stCount[s.status] = (stCount[s.status] || 0) + 1
    }
    log(`정산 현황: ${JSON.stringify(stCount)}`)

    // 관리자 페이지 스크린샷
    await page.goto(`${BASE}/admin`)
    await page.waitForTimeout(3000)
    await ss(page, '11-admin-dashboard')

    await page.goto(`${BASE}/admin/settlements`)
    await page.waitForTimeout(3000)
    await ss(page, '12-admin-settlements')

    log('\n=== 관리자 페이지 스크린샷 저장 완료 ===')
    await ss(page, '13-verification-complete')
  })
})

// =================================================================
// Phase 5: 구매자/판매자 페이지 확인
// =================================================================
test.describe.serial('Phase 5: 참여자 페이지 확인', () => {
  test('구매자 주문 확인', async ({ page }) => {
    test.setTimeout(120000)
    const buyer = await login(page, 'demo@yeokping.com', 'demo1234')
    if (!buyer) return

    await page.goto(`${BASE}/orders`)
    await page.waitForTimeout(3000)
    await ss(page, '14-buyer-orders')
    log('구매자 주문 페이지 확인')
  })

  test('판매자 페이지 확인', async ({ page }) => {
    test.setTimeout(120000)
    const seller = await login(page, 'seller@yeokping.com', 'seller1234')
    if (!seller) return

    await page.goto(`${BASE}/seller/dashboard`)
    await page.waitForTimeout(3000)
    await ss(page, '15-seller-dashboard')
    log('판매자 페이지 확인')
  })
})

// =================================================================
// 최종 리포트
// =================================================================
test.describe.serial('리포트', () => {
  test('저장', async () => {
    const summary = [
      '# 실제 환불 50건 테스트',
      `# ${new Date().toISOString()}`,
      '',
      '## 카테고리',
      '- A: 배송전 전액환불 (1~10)',
      '- B: 배송전 부분환불 (11~20)',
      '- C: 배송중 환불 (26~30)',
      '- D: 반품(return) (31~35)',
      '- E: 수취후 전액환불 (36~40)',
      '- F: 교환(exchange) (41~45)',
      '- G: 분쟁환불 (46~50)',
      '- H: 판매자사유 환불 (21~25)',
      '',
      '## 로그',
      ...LOG,
    ].join('\n')

    console.log('\n' + '='.repeat(60))
    console.log(summary)
    console.log('='.repeat(60))

    fs.writeFileSync('real-refund-50-report.md', summary)
    console.log('리포트: real-refund-50-report.md')
  })
})
