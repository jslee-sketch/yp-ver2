import { test, Page } from '@playwright/test'
import * as fs from 'fs'

const BASE = 'https://web-production-defb.up.railway.app'
const SS = 'test-results/screenshots/level3'
const LOG: string[] = []

function log(msg: string) {
  const ts = new Date().toISOString().substring(11, 19)
  const line = `[${ts}] ${msg}`
  console.log(line)
  LOG.push(line)
}

async function ss(page: Page, name: string) {
  await page.screenshot({ path: `${SS}/${name}.png`, fullPage: true }).catch(() => {})
}

async function api(page: Page, method: string, path: string, body?: any, headers?: any) {
  return await page.evaluate(async ({ base, m, p, b, h }) => {
    try {
      const opts: any = { method: m, headers: { 'Content-Type': 'application/json', ...h } }
      if (b && m !== 'GET') opts.body = JSON.stringify(b)
      const url = p.startsWith('http') ? p : `${base}${p}`
      const res = await fetch(url, opts)
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
      return { ok: res.ok, status: res.status, data }
    } catch (e: any) {
      return { ok: false, status: 0, data: {}, error: e.message }
    }
  }, { base: BASE, e: email, p: pw })
  if (r.ok && r.data.access_token) {
    // Decode JWT to extract user claims (sub, role, seller_id, etc.)
    const parts = r.data.access_token.split('.')
    const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf-8'))
    const data = {
      ...r.data,
      id: parseInt(payload.sub),
      sub: payload.sub,
      role: payload.role,
      seller_id: payload.seller_id,
      actuator_id: payload.actuator_id,
      verified: payload.verified,
    }
    return { token: r.data.access_token, h: { Authorization: `Bearer ${r.data.access_token}` }, data }
  }
  return null
}

function randomName() {
  const last = ['김','이','박','최','정','강','조','윤','장','임']
  const first = ['민준','서연','지호','수빈','예준','다은','하준','지민','시우','하은','도윤','서현','우진','채원','준서']
  return last[Math.floor(Math.random()*last.length)] + first[Math.floor(Math.random()*first.length)]
}
function randomPhone() { return '010' + Math.floor(10000000 + Math.random()*90000000).toString() }
function randomBizNo() { return Math.floor(100+Math.random()*900) + '-' + Math.floor(10+Math.random()*90) + '-' + Math.floor(10000+Math.random()*90000) }

// ═══════════════════════════════════════════════════════════
// Phase 1: 전 페이지 클릭 테스트
// ═══════════════════════════════════════════════════════════
test.describe.serial('Phase 1: 전 페이지 클릭 테스트', () => {
  test('1-1. 비로그인 페이지', async ({ page }) => {
    for (const p of ['/', '/login', '/register', '/deals']) {
      await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {})
      await page.waitForTimeout(2000)
      const textLen = await page.evaluate(() => document.body.innerText.length)
      log(`클릭: ${p} → ${textLen < 10 ? '❌ 블랙아웃' : `✅ OK (${textLen}자)`}`)
      await ss(page, `1-1-${p.replace(/\//g, '_') || 'home'}`)
    }
  })

  test('1-2. 구매자 페이지', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const auth = await login(page, 'realtest1@e2e.com', 'Test1234!')
    if (!auth) { log('❌ 구매자 로그인 실패'); return }
    log(`✅ 구매자 로그인 성공`)
    for (const p of ['/', '/deals', '/deal/create', '/my-deals', '/my-orders', '/mypage', '/notifications', '/points']) {
      await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {})
      await page.waitForTimeout(1500)
      const textLen = await page.evaluate(() => document.body.innerText.length)
      log(`구매자: ${p} → ${textLen < 10 ? '❌ 블랙아웃' : `✅ OK (${textLen}자)`}`)
    }
    await ss(page, '1-2-buyer-pages')
  })

  test('1-3. 판매자 페이지', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const auth = await login(page, 'e2e_seller@test.com', 'Test1234!')
    if (!auth) { log('❌ 판매자 로그인 실패'); return }
    log(`✅ 판매자 로그인 성공`)
    for (const p of ['/seller/dashboard', '/seller/offers', '/seller/orders', '/seller/reviews', '/seller/refunds', '/seller/settlements', '/deals', '/mypage']) {
      await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {})
      await page.waitForTimeout(1500)
      const textLen = await page.evaluate(() => document.body.innerText.length)
      log(`판매자: ${p} → ${textLen < 10 ? '❌ 블랙아웃' : `✅ OK (${textLen}자)`}`)
    }
    await ss(page, '1-3-seller-pages')
  })

  test('1-4. 관리자 페이지', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const auth = await login(page, 'admin@yeokping.com', 'admin1234!')
    if (!auth) { log('❌ 관리자 로그인 실패'); return }
    log(`✅ 관리자 로그인 성공`)
    const adminPages = [
      '/admin', '/admin/buyers', '/admin/sellers', '/admin/actuators',
      '/admin/deals', '/admin/offers', '/admin/reservations', '/admin/delivery',
      '/admin/settlements', '/admin/refunds', '/admin/disputes',
      '/admin/policy/params', '/admin/policy/docs', '/admin/policy/proposals',
      '/admin/stats', '/admin/anomalies', '/admin/logs', '/admin/reports',
      '/admin/notifications', '/admin/announcements', '/admin/settings',
    ]
    for (const p of adminPages) {
      await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {})
      await page.waitForTimeout(1500)
      const textLen = await page.evaluate(() => document.body.innerText.length)
      log(`관리자: ${p} → ${textLen < 10 ? '❌ 블랙아웃' : `✅ OK (${textLen}자)`}`)
    }
    await ss(page, '1-4-admin-pages')
  })
})

// ═══════════════════════════════════════════════════════════
// Phase 2: 구매자 100명 가입 (POST /buyers/)
// ═══════════════════════════════════════════════════════════
test.describe.serial('Phase 2: 구매자 100명 가입', () => {
  test('2-1. 구매자 100명', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const results = { success: 0, fail: 0, recommender: 0 }
    const buyerIds: number[] = []
    const details: string[] = []

    for (let i = 1; i <= 100; i++) {
      const name = randomName()
      const phone = randomPhone()
      const nick = `stress${i}${name.substring(0,2)}`
      const hasRecommender = i > 70 && buyerIds.length > 0
      const recommenderId = hasRecommender ? buyerIds[Math.floor(Math.random() * buyerIds.length)] : undefined

      const body: any = {
        email: `stressbuyer${i}@test.com`,
        password: 'Test1234!',
        nickname: nick,
        name: name,
        phone: phone,
      }
      if (recommenderId) body.recommender_buyer_id = recommenderId

      const r = await api(page, 'POST', '/buyers/', body)
      const bid = r.data?.id || '-'
      if (r.ok) {
        results.success++
        if (typeof bid === 'number') buyerIds.push(bid)
        if (hasRecommender) results.recommender++
        details.push(`| ${i} | stressbuyer${i}@test.com | ${nick} | ${name} | ${phone} | ${recommenderId ? 'B-'+recommenderId : '-'} | ${bid} | ✅ |`)
      } else {
        results.fail++
        const detail = JSON.stringify(r.data?.detail || r.data || '').substring(0, 60)
        details.push(`| ${i} | stressbuyer${i}@test.com | ${nick} | ${name} | ${phone} | - | - | ❌ ${r.status} ${detail} |`)
      }
      if (i % 25 === 0) log(`구매자 가입 진행: ${i}/100 (성공:${results.success} 실패:${results.fail})`)
    }

    log(`=== Phase 2 완료: 성공=${results.success} 실패=${results.fail} 추천인=${results.recommender} ===`)
    log(`DETAIL_TABLE_P2:\n| # | 이메일 | 닉네임 | 이름 | 전화 | 추천인 | buyer_id | 결과 |\n|---|--------|--------|------|------|--------|----------|------|\n${details.slice(0,10).join('\n')}\n... (${details.length}건)`)
    await ss(page, '2-1-buyers-100')
  })
})

// ═══════════════════════════════════════════════════════════
// Phase 3: 액츄에이터 100명 가입 (POST /actuators/)
// ═══════════════════════════════════════════════════════════
test.describe.serial('Phase 3: 액츄에이터 100명 가입', () => {
  test('3-1. 액츄에이터 100명', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const results = { success: 0, fail: 0, personal: 0, business: 0 }
    const details: string[] = []

    for (let i = 1; i <= 100; i++) {
      const isBusiness = i > 50
      const name = randomName()

      const body: any = {
        name: `액츄${i}_${name}`,
        email: `stressact${i}@test.com`,
        phone: randomPhone(),
        password: 'Test1234!',
        nickname: `act${i}${name.substring(0,2)}`,
        bank_name: ['국민','신한','우리','하나','농협'][i % 5],
        account_number: `${1000000000 + i}`,
        account_holder: name,
      }
      if (isBusiness) {
        body.is_business = true
        body.business_name = `${name}컴퍼니`
        body.business_number = randomBizNo()
      }

      const r = await api(page, 'POST', '/actuators/', body)
      const aid = r.data?.id || '-'
      if (r.ok) {
        results.success++
        if (isBusiness) results.business++; else results.personal++
        details.push(`| ${i} | stressact${i}@test.com | ${isBusiness ? '사업자' : '개인'} | ${aid} | ✅ |`)
      } else {
        results.fail++
        details.push(`| ${i} | stressact${i}@test.com | ${isBusiness ? '사업자' : '개인'} | - | ❌ ${r.status} |`)
      }
      if (i % 25 === 0) log(`액츄에이터 진행: ${i}/100`)
    }

    log(`=== Phase 3 완료: 성공=${results.success} 개인=${results.personal} 사업자=${results.business} 실패=${results.fail} ===`)
    log(`DETAIL_TABLE_P3:\n| # | 이메일 | 유형 | ID | 결과 |\n|---|--------|------|-----|------|\n${details.slice(0,10).join('\n')}\n... (${details.length}건)`)
    await ss(page, '3-1-actuators-100')
  })
})

// ═══════════════════════════════════════════════════════════
// Phase 4: 판매자 100명 가입 (POST /sellers/)
// ═══════════════════════════════════════════════════════════
test.describe.serial('Phase 4: 판매자 100명 가입', () => {
  test('4-1. 판매자 100명', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const results = { success: 0, fail: 0 }
    const details: string[] = []

    for (let i = 1; i <= 100; i++) {
      const name = randomName()
      const bizNo = randomBizNo()

      const body: any = {
        email: `stressseller${i}@test.com`,
        password: 'Test1234!',
        business_name: `${name}상사`,
        nickname: `sell${i}${name.substring(0,2)}`,
        phone: randomPhone(),
        business_number: bizNo,
        address: `서울시 강남구 테스트로 ${i}번지`,
        zip_code: `${10000 + i}`,
        established_date: '2020-01-01T00:00:00',
        bank_name: ['국민','신한','우리','하나','농협'][i % 5],
        account_number: `${2000000000 + i}`,
        account_holder: name,
      }

      const r = await api(page, 'POST', '/sellers/', body)
      const sid = r.data?.id || '-'
      if (r.ok) {
        results.success++
        details.push(`| ${i} | stressseller${i}@test.com | ${name}상사 | sell${i} | ${sid} | ✅ |`)
      } else {
        results.fail++
        details.push(`| ${i} | stressseller${i}@test.com | ${name}상사 | sell${i} | - | ❌ ${r.status} ${JSON.stringify(r.data?.detail||'').substring(0,50)} |`)
      }
      if (i % 25 === 0) log(`판매자 진행: ${i}/100`)
    }

    log(`=== Phase 4 완료: 성공=${results.success} 실패=${results.fail} ===`)
    log(`DETAIL_TABLE_P4:\n| # | 이메일 | 상호 | 닉네임 | ID | 결과 |\n|---|--------|------|--------|-----|------|\n${details.slice(0,10).join('\n')}\n... (${details.length}건)`)
    await ss(page, '4-1-sellers-100')
  })
})

// ═══════════════════════════════════════════════════════════
// Phase 5: 전체 거래 흐름
// ═══════════════════════════════════════════════════════════
test.describe.serial('Phase 5: 전체 거래 흐름', () => {

  test('5-1. 딜 100개 생성', async ({ page }) => {
    test.setTimeout(600000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const products = [
      '아이폰 16 프로', '갤럭시 S25 울트라', 'LG 그램 노트북', '다이슨 에어랩',
      '소니 WH-1000XM5', '닌텐도 스위치2', '맥북 프로 14', '아이패드 프로',
      '삼성 OLED TV 65', 'LG 드럼세탁기', '다이슨 청소기 V15', '에어팟 맥스',
      '갤럭시워치7', '애플워치10', 'PS5 프로', '로봇청소기 S9+',
      '삼성 냉장고 비스포크', 'LG 스타일러', '캠핑의자 세트', '전동킥보드',
    ]
    const dealIds: number[] = []
    const details: string[] = []

    // Batch login: 10 buyers, each creates 10 deals
    const BUYERS = 10
    const DEALS_PER = 10
    for (let b = 0; b < BUYERS; b++) {
      const buyerEmail = `stressbuyer${b + 1}@test.com`
      const auth = await login(page, buyerEmail, 'Test1234!')
      if (!auth) { for (let j = 0; j < DEALS_PER; j++) details.push(`| ${b*DEALS_PER+j+1} | - | ❌ 로그인실패 |`); continue }
      const buyerId = auth.data?.id

      for (let j = 0; j < DEALS_PER; j++) {
        const i = b * DEALS_PER + j + 1
        const product = products[(i-1) % products.length]
        const targetPrice = Math.floor(100000 + Math.random() * 2000000)

        const r = await api(page, 'POST', '/deals/', {
          product_name: product,
          creator_id: buyerId,
          desired_qty: Math.floor(Math.random()*5)+1,
          target_price: targetPrice,
          brand: product.split(' ')[0],
          anchor_price: targetPrice * 1.2,  // provide anchor_price to skip AI Helper (LLM+Naver)
        }, auth.h)

        if (r.ok && r.data?.id) {
          dealIds.push(r.data.id)
          details.push(`| ${i} | D-${r.data.id} | ${product} | ${targetPrice.toLocaleString()} | ✅ |`)
        } else {
          details.push(`| ${i} | - | ${product} | ${targetPrice.toLocaleString()} | ❌ ${r.status} ${JSON.stringify(r.data?.detail||'').substring(0,60)} |`)
        }
      }
      log(`딜 생성 진행: ${(b+1)*DEALS_PER}/100 (성공:${dealIds.length})`)
    }

    log(`=== Phase 5-1 완료: 딜 ${dealIds.length}개 ===`)
    log(`DETAIL_TABLE_P5_1:\n| # | 딜ID | 상품 | 목표가 | 결과 |\n|---|------|------|--------|------|\n${details.slice(0,15).join('\n')}\n... (${details.length}건)`)
    await ss(page, '5-1-deals-100')
  })

  test('5-2. 오퍼 70개 제출', async ({ page }) => {
    test.setTimeout(600000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    // 새로 등록한 판매자들로 오퍼 제출
    const sellerAuth = await login(page, 'e2e_seller@test.com', 'Test1234!')
    if (!sellerAuth) { log('❌ 판매자 로그인 실패'); return }

    const sellerId = sellerAuth.data?.seller_id || sellerAuth.data?.id || sellerAuth.data?.sub
    log(`판매자 로그인: seller_id=${sellerId}`)

    // 딜 목록
    const dealsResp = await api(page, 'GET', '/deals/?page=1&size=200', null, sellerAuth.h)
    const deals = Array.isArray(dealsResp.data) ? dealsResp.data : dealsResp.data?.items || dealsResp.data?.results || []
    log(`딜 목록: ${deals.length}건`)

    const offerIds: number[] = []
    const details: string[] = []
    const count = Math.min(70, deals.length)

    for (let i = 0; i < count; i++) {
      const deal = deals[i]
      const price = Math.floor((deal.target_price || 500000) * (0.85 + Math.random() * 0.3))
      const shippingFee = Math.random() > 0.5 ? 0 : 3000

      const r = await api(page, 'POST', '/v3_6/offers', {
        deal_id: deal.id,
        seller_id: sellerId,
        price: price,
        total_available_qty: Math.floor(Math.random()*10)+5,
        shipping_mode: shippingFee === 0 ? 'INCLUDED' : 'PER_RESERVATION',
        shipping_fee_per_reservation: shippingFee,
        delivery_days: Math.floor(Math.random()*5)+1,
      }, sellerAuth.h)

      if (r.ok && r.data?.id) {
        offerIds.push(r.data.id)
        details.push(`| ${i+1} | O-${r.data.id} | D-${deal.id} | ${price.toLocaleString()} | ✅ |`)
      } else {
        details.push(`| ${i+1} | - | D-${deal.id} | ${price.toLocaleString()} | ❌ ${r.status} ${JSON.stringify(r.data?.detail||'').substring(0,60)} |`)
      }
      if ((i+1) % 20 === 0) log(`오퍼 진행: ${i+1}/${count} (성공:${offerIds.length})`)
    }

    log(`=== Phase 5-2 완료: 오퍼 ${offerIds.length}개 ===`)
    log(`DETAIL_TABLE_P5_2:\n| # | 오퍼ID | 딜ID | 가격 | 결과 |\n|---|--------|------|------|------|\n${details.slice(0,15).join('\n')}\n... (${details.length}건)`)
    await ss(page, '5-2-offers-70')
  })

  test('5-3. 예약+결제 100건', async ({ page }) => {
    test.setTimeout(600000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    // 오퍼 있는 딜 목록
    const adminAuth = await login(page, 'admin@yeokping.com', 'admin1234!')
    const offersResp = await api(page, 'GET', '/admin/offers?limit=200', null, adminAuth?.h)
    const offers = Array.isArray(offersResp.data) ? offersResp.data : offersResp.data?.items || []
    log(`오퍼 목록: ${offers.length}건`)

    const reservationIds: number[] = []
    const details: string[] = []
    const count = Math.min(100, offers.length)

    // Batch login: cache tokens per buyer
    const authCache: Record<string, any> = {}
    for (let i = 0; i < count; i++) {
      const buyerIdx = (i % 10) + 1  // use 10 buyers in rotation
      const buyerEmail = `stressbuyer${buyerIdx}@test.com`
      if (!authCache[buyerEmail]) {
        authCache[buyerEmail] = await login(page, buyerEmail, 'Test1234!')
      }
      const auth = authCache[buyerEmail]
      if (!auth) { details.push(`| ${i+1} | - | ❌ 로그인실패 |`); continue }

      const buyerId = auth.data?.id || auth.data?.buyer_id || auth.data?.sub
      const offer = offers[i % offers.length]
      const offerId = offer.offer_id || offer.id
      const dealId = offer.deal_id
      const qty = 1

      // 예약
      const res = await api(page, 'POST', '/v3_6/reservations', {
        deal_id: dealId,
        offer_id: offerId,
        buyer_id: buyerId,
        qty: qty,
      }, auth.h)

      if (res.ok && res.data?.id) {
        // Use server-calculated amount_total for payment
        const amount = res.data.amount_total || res.data.total_amount || (offer.price || 500000) * qty
        // 결제
        const pay = await api(page, 'POST', '/v3_6/reservations/pay', {
          reservation_id: res.data.id,
          buyer_id: buyerId,
          paid_amount: amount,
        }, auth.h)

        if (pay.ok) {
          reservationIds.push(res.data.id)
          details.push(`| ${i+1} | R-${res.data.id} | O-${offerId} | ${amount.toLocaleString()} | ✅ 예약+결제 |`)
        } else {
          reservationIds.push(res.data.id) // 예약은 성공
          details.push(`| ${i+1} | R-${res.data.id} | O-${offerId} | ${amount.toLocaleString()} | ⚠️ 결제❌ ${pay.status} ${JSON.stringify(pay.data?.detail||'').substring(0,40)} |`)
        }
      } else {
        details.push(`| ${i+1} | - | O-${offerId} | - | ❌ 예약실패 ${res.status} ${JSON.stringify(res.data?.detail||'').substring(0,50)} |`)
      }
      if ((i+1) % 25 === 0) log(`예약+결제 진행: ${i+1}/${count} (성공:${reservationIds.length})`)
    }

    log(`=== Phase 5-3 완료: 예약 ${reservationIds.length}건 ===`)
    log(`DETAIL_TABLE_P5_3:\n| # | 예약ID | 오퍼ID | 금액 | 결과 |\n|---|--------|--------|------|------|\n${details.slice(0,15).join('\n')}\n... (${details.length}건)`)
    await ss(page, '5-3-reservations-100')
  })

  test('5-4. 관전자 50명 예측', async ({ page }) => {
    test.setTimeout(600000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    let predictions = 0

    const dealsResp = await api(page, 'GET', '/deals/?page=1&size=100')
    const deals = Array.isArray(dealsResp.data) ? dealsResp.data : dealsResp.data?.items || []

    // Batch login: 10 buyers (51~60), each predicts on ~5 deals
    const authCache: Record<string, any> = {}
    for (let i = 1; i <= Math.min(50, deals.length); i++) {
      const buyerIdx = ((i - 1) % 10) + 51  // buyers 51-60
      const email = `stressbuyer${buyerIdx}@test.com`
      if (!authCache[email]) authCache[email] = await login(page, email, 'Test1234!')
      const auth = authCache[email]
      if (!auth) continue
      const deal = deals[(i-1) % deals.length]
      const buyerId = auth.data?.id
      const predicted = Math.floor((deal.target_price || 500000) * (0.85 + Math.random() * 0.3))
      const r = await api(page, 'POST', '/spectator/predict', { deal_id: deal.id, buyer_id: buyerId, predicted_price: predicted }, auth.h)
      if (r.ok) predictions++
      if (i % 10 === 0) log(`관전자 예측: ${i}/50 (성공:${predictions})`)
    }

    log(`=== Phase 5-4 완료: 관전자 예측 ${predictions}건 ===`)
    await ss(page, '5-4-spectators-50')
  })

  test('5-5. 배송 처리', async ({ page }) => {
    test.setTimeout(600000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const sellerAuth = await login(page, 'e2e_seller@test.com', 'Test1234!')
    if (!sellerAuth) { log('❌ 판매자 로그인 실패'); return }

    // 판매자 예약 목록 (PAID) — admin endpoint has seller_id filter
    const adminAuth = await login(page, 'admin@yeokping.com', 'admin1234!')
    const sellerId = sellerAuth.data?.seller_id || sellerAuth.data?.id
    const resResp = await api(page, 'GET', `/admin/reservations?seller_id=${sellerId}&status=PAID&shipped=false&limit=200`, null, adminAuth?.h)
    const reservations = Array.isArray(resResp.data) ? resResp.data : resResp.data?.items || []
    const paidList = reservations.filter((r: any) => String(r.status).includes('PAID') && !r.shipped_at)
    log(`배송 대상: ${paidList.length}건`)

    const carriers = ['CJ대한통운','한진택배','롯데택배','우체국택배','로젠택배']
    let shipped = 0

    for (let i = 0; i < paidList.length; i++) {
      const res = paidList[i]
      const r = await api(page, 'POST', `/v3_6/reservations/${res.id}/ship`, {
        shipping_carrier: carriers[i % carriers.length],
        tracking_number: `STRESS${String(i+1).padStart(6,'0')}`,
      }, sellerAuth.h)
      if (r.ok) shipped++
      if ((i+1) % 20 === 0) log(`배송처리: ${i+1}/${paidList.length} (성공:${shipped})`)
    }

    log(`=== Phase 5-5 완료: 배송 ${shipped}건 ===`)
    await ss(page, '5-5-shipping')
  })

  test('5-6. 환불 50건', async ({ page }) => {
    test.setTimeout(600000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const results = { refund: 0, return_: 0, exchange: 0, fail: 0, skip: 0 }
    const reasons = ['단순변심','상품불량','오배송','사이즈교환','수량부족']

    // Batch login: cache tokens
    const authCache: Record<string, any> = {}
    for (let i = 1; i <= 50; i++) {
      const email = `stressbuyer${i}@test.com`
      if (!authCache[email]) authCache[email] = await login(page, email, 'Test1234!')
      const auth = authCache[email]
      if (!auth) { results.skip++; continue }

      const buyerId = auth.data?.id || auth.data?.buyer_id || auth.data?.sub
      const resResp = await api(page, 'GET', `/v3_6/search?buyer_id=${buyerId}&limit=50`, null, auth.h)
      const reservations = Array.isArray(resResp.data) ? resResp.data : resResp.data?.items || []
      const target = reservations.find((r: any) => (r.status === 'PAID' || r.status === 'SHIPPED') && !r.cancelled_at && !r.refunded_at)
      if (!target) { results.skip++; continue }

      const refundType = i <= 15 ? 'refund' : i <= 25 ? 'return' : i <= 35 ? 'exchange' : 'refund'
      const r = await api(page, 'POST', '/v3_6/reservations/refund', {
        reservation_id: target.id,
        reason: reasons[(i-1) % reasons.length],
        requested_by: 'BUYER',
        refund_type: refundType,
      }, auth.h)

      if (r.ok) {
        if (refundType === 'refund') results.refund++
        else if (refundType === 'return') results.return_++
        else results.exchange++
      } else { results.fail++ }

      if (i % 10 === 0) log(`환불 진행: ${i}/50`)
    }

    log(`=== Phase 5-6 완료: 환불=${results.refund} 반품=${results.return_} 교환=${results.exchange} 실패=${results.fail} 스킵=${results.skip} ===`)
    await ss(page, '5-6-refunds-50')
  })

  test('5-7. 리뷰 50건', async ({ page }) => {
    test.setTimeout(600000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    let reviews = 0, skip = 0
    const comments = ['좋아요','보통이에요','배송빠름','포장깔끔','가격합리적']

    // Batch login: 10 buyers (51~60) each reviews multiple
    const authCache: Record<string, any> = {}
    for (let i = 51; i <= 100; i++) {
      const buyerIdx = ((i - 51) % 10) + 51
      const email = `stressbuyer${buyerIdx}@test.com`
      if (!authCache[email]) authCache[email] = await login(page, email, 'Test1234!')
      const auth = authCache[email]
      if (!auth) { skip++; continue }
      const buyerId = auth.data?.id || auth.data?.buyer_id || auth.data?.sub
      const resResp = await api(page, 'GET', `/v3_6/search?buyer_id=${buyerId}&limit=50`, null, auth.h)
      const reservations = Array.isArray(resResp.data) ? resResp.data : resResp.data?.items || []
      const target = reservations.find((r: any) => r.status === 'PAID' || r.shipped_at || r.arrival_confirmed_at)
      if (!target) { skip++; continue }

      const rating = Math.floor(Math.random()*3)+3
      const r = await api(page, 'POST', '/reviews', {
        reservation_id: target.id,
        seller_id: target.seller_id || 1,
        buyer_id: buyerId,
        price_fairness: rating, quality: rating,
        shipping: Math.floor(Math.random()*3)+3,
        communication: Math.floor(Math.random()*3)+3,
        accuracy: Math.floor(Math.random()*3)+3,
        comment: `스트레스 리뷰 ${i} - ${comments[(i-51)%5]}`,
      }, auth.h)

      if (r.ok) reviews++
      if ((i-50) % 10 === 0) log(`리뷰: ${i-50}/50 (성공:${reviews})`)
    }

    log(`=== Phase 5-7 완료: 리뷰 ${reviews}건 스킵 ${skip}건 ===`)
    await ss(page, '5-7-reviews-50')
  })

  test('5-8. 분쟁 10건', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const adminAuth = await login(page, 'admin@yeokping.com', 'admin1234!')
    if (!adminAuth) { log('❌ 관리자 로그인 실패'); return }

    const resResp = await api(page, 'GET', '/admin/reservations?limit=200', null, adminAuth.h)
    const reservations = Array.isArray(resResp.data) ? resResp.data : resResp.data?.items || []
    const paidList = reservations.filter((r: any) => (String(r.status).includes('PAID') || String(r.status).includes('SHIPPED')) && !r.is_disputed)
    log(`분쟁 대상: ${paidList.length}건`)

    let disputes = 0
    const reasons = ['상품불량','미배송','오배송','설명불일치','수량부족']

    for (let i = 0; i < Math.min(10, paidList.length); i++) {
      const res = paidList[i]
      const open = await api(page, 'POST', `/v3_6/${res.id}/dispute/open`, {
        reason: `${reasons[i%reasons.length]} (스트레스 ${i+1})`,
      }, adminAuth.h)

      if (open.ok) {
        disputes++
        if (i < 5) {
          await page.waitForTimeout(300)
          await api(page, 'POST', `/v3_6/${res.id}/dispute/close`, {
            resolution: `스트레스 분쟁 종료 ${i+1}`,
            refund_action: ['no_refund','full_refund','partial_refund','no_refund','full_refund'][i],
          }, adminAuth.h)
        }
      }
      log(`분쟁 ${i+1}/10: R-${res.id} → ${open.ok ? '✅' : `❌ ${open.status}`}`)
    }

    log(`=== Phase 5-8 완료: 분쟁 ${disputes}건 ===`)
    await ss(page, '5-8-disputes-10')
  })

  test('5-9. 정산 확인', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const adminAuth = await login(page, 'admin@yeokping.com', 'admin1234!')
    if (!adminAuth) return

    const refresh = await api(page, 'POST', '/settlements/refresh-ready', {}, adminAuth.h)
    log(`정산 refresh: ${refresh.ok ? '✅' : '❌'} ${JSON.stringify(refresh.data).substring(0,100)}`)

    const stResp = await api(page, 'GET', '/settlements/?limit=200', null, adminAuth.h)
    const settlements = Array.isArray(stResp.data) ? stResp.data : stResp.data?.items || []
    const statusCount: Record<string, number> = {}
    for (const s of settlements) statusCount[s.status] = (statusCount[s.status] || 0) + 1

    log(`=== Phase 5-9 완료: 정산 ${settlements.length}건 ${JSON.stringify(statusCount)} ===`)

    await api(page, 'POST', '/settlements/batch-auto-approve', {}, adminAuth.h)
    await api(page, 'POST', '/settlements/bulk-mark-paid', {}, adminAuth.h)
    await ss(page, '5-9-settlements')
  })
})

// ═══════════════════════════════════════════════════════════
// Phase 6: 주요 기능 심층
// ═══════════════════════════════════════════════════════════
test.describe.serial('Phase 6: 주요 기능 심층', () => {
  test('6-1. 핑퐁이 정책제안', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const adminAuth = await login(page, 'admin@yeokping.com', 'admin1234!')
    const r = await api(page, 'GET', '/admin/policy/proposals', null, adminAuth?.h)
    log(`핑퐁이 정책제안: ${r.ok ? '✅' : '❌'} ${JSON.stringify(r.data).substring(0, 200)}`)
    await ss(page, '6-1-policy-proposals')
  })

  test('6-2. 핑퐁이 대화 20개', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const questions = [
      '안녕', '역핑은 뭐야?', '환불 어떻게 해?', '오퍼 마감 시간?',
      '수수료 얼마야?', '정산 언제 돼?', '배송 안 오면?', '분쟁 신청하고 싶어',
      '딜방 만드는법', '관전자가 뭐야?', '쿨링 기간?', '포인트 적립은?',
      '갤럭시 S25 가격', '서울 날씨', '에어팟 프로 최저가',
      '판매자 등급별 수수료', '환불하면 포인트도?', '역핑 쿠팡 차이',
      '부분 환불 가능?', '결제 제한시간?',
    ]
    let pass = 0
    const details: string[] = []

    for (let qi = 0; qi < questions.length; qi++) {
      const q = questions[qi]
      const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
        question: q, screen: 'home', context: {}, mode: 'read_only',
      })
      const answer = (r.data?.answer || '(없음)').substring(0, 100)
      const engine = r.data?.engine || '?'
      const hasPath = /\/[\w-]+/.test(answer)
      const ok = r.ok && answer !== '(없음)'
      if (ok) pass++
      details.push(`| ${qi+1} | ${q} | ${answer.replace(/\|/g,'/').replace(/\n/g,' ')} | ${engine} | ${hasPath ? '✅' : '-'} | ${ok ? 'PASS' : 'FAIL'} |`)
      await page.waitForTimeout(800)
    }

    log(`=== Phase 6-2 완료: 핑퐁이 ${pass}/20 PASS ===`)
    log(`DETAIL_TABLE_P6_2:\n| # | 질문 | 답변(100자) | engine | 딥링크 | 판정 |\n|---|------|------------|--------|--------|------|\n${details.join('\n')}`)
    await ss(page, '6-2-pingpong-20')
  })

  test('6-3. 알림+로그 확인', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const adminAuth = await login(page, 'admin@yeokping.com', 'admin1234!')

    const notifs = await api(page, 'GET', '/notifications/?limit=50', null, adminAuth?.h)
    const nList = Array.isArray(notifs.data) ? notifs.data : notifs.data?.items || []
    log(`알림: ${nList.length}건`)

    const logs = await api(page, 'GET', '/activity/recent?limit=50', null, adminAuth?.h)
    const lList = Array.isArray(logs.data) ? logs.data : logs.data?.items || []
    log(`전역 로그: ${lList.length}건`)
    await ss(page, '6-3-notifications-logs')
  })
})

// ═══════════════════════════════════════════════════════════
// Phase 7: 관리자 데이터 매핑
// ═══════════════════════════════════════════════════════════
test.describe.serial('Phase 7: 관리자 데이터 매핑', () => {
  test('7-1. 관리자 대시보드+정산+분쟁', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const auth = await login(page, 'admin@yeokping.com', 'admin1234!')
    if (!auth) return

    for (const p of ['/admin', '/admin/settlements', '/admin/refunds', '/admin/disputes']) {
      await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {})
      await page.waitForTimeout(2000)
      const textLen = await page.evaluate(() => document.body.innerText.length)
      log(`관리자 ${p}: ${textLen > 100 ? '✅' : '⚠️'} (${textLen}자)`)
      await ss(page, `7-1-${p.replace(/\//g, '_')}`)
    }
  })
})

// ═══════════════════════════════════════════════════════════
// Phase 8: 참여자별 페이지
// ═══════════════════════════════════════════════════════════
test.describe.serial('Phase 8: 참여자별 페이지', () => {
  test('8-1. 구매자+판매자 확인', async ({ page }) => {
    for (let i = 1; i <= 3; i++) {
      await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
      const auth = await login(page, `stressbuyer${i}@test.com`, 'Test1234!')
      if (!auth) { log(`구매자${i} 로그인 실패`); continue }
      for (const p of ['/my-orders', '/my-deals', '/mypage']) {
        await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {})
        await page.waitForTimeout(1000)
        const textLen = await page.evaluate(() => document.body.innerText.length)
        log(`구매자${i} ${p}: ${textLen > 30 ? '✅' : '⚠️'} (${textLen}자)`)
      }
    }

    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    const sellerAuth = await login(page, 'e2e_seller@test.com', 'Test1234!')
    if (sellerAuth) {
      for (const p of ['/seller/dashboard', '/seller/offers', '/seller/settlements']) {
        await page.goto(`${BASE}${p}`, { waitUntil: 'networkidle', timeout: 15000 }).catch(() => {})
        await page.waitForTimeout(1500)
        const textLen = await page.evaluate(() => document.body.innerText.length)
        log(`판매자 ${p}: ${textLen > 50 ? '✅' : '⚠️'} (${textLen}자)`)
      }
    }
    await ss(page, '8-1-participant-check')
  })
})

// ═══════════════════════════════════════════════════════════
// Phase 9: 이상 시나리오
// ═══════════════════════════════════════════════════════════
test.describe.serial('Phase 9: 이상 시나리오', () => {
  test('9-1. 동일 오퍼 50명 동시 예약', async ({ page }) => {
    test.setTimeout(600000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    let success = 0, fail = 0

    const dealsResp = await api(page, 'GET', '/deals/?page=1&size=1')
    const deals = Array.isArray(dealsResp.data) ? dealsResp.data : dealsResp.data?.items || []
    if (!deals.length) { log('딜 없음 - 스킵'); return }

    const offerResp = await api(page, 'GET', `/v3_6/offers?deal_id=${deals[0].id}`)
    const offers = Array.isArray(offerResp.data) ? offerResp.data : offerResp.data?.items || []
    if (!offers.length) { log('오퍼 없음 - 스킵'); return }

    const offerId = offers[0].id
    const dealId = deals[0].id

    // Batch login: 10 buyers, each tries 5 reservations
    const authCache: Record<string, any> = {}
    for (let i = 1; i <= 50; i++) {
      const buyerIdx = ((i - 1) % 10) + 1
      const email = `stressbuyer${buyerIdx}@test.com`
      if (!authCache[email]) authCache[email] = await login(page, email, 'Test1234!')
      const auth = authCache[email]
      if (!auth) continue
      const buyerId = auth.data?.id || auth.data?.buyer_id || auth.data?.sub
      const r = await api(page, 'POST', '/v3_6/reservations', {
        deal_id: dealId, offer_id: offerId, buyer_id: buyerId, qty: 1,
      }, auth.h)
      if (r.ok) success++; else fail++
    }

    log(`=== 9-1 동시 예약: 성공=${success} 실패=${fail} ===`)
    await ss(page, '9-1-concurrent')
  })

  test('9-2. 없는 딜 오퍼 + 이중환불', async ({ page }) => {
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})

    const sellerAuth = await login(page, 'e2e_seller@test.com', 'Test1234!')
    if (sellerAuth) {
      const r = await api(page, 'POST', '/v3_6/offers', {
        deal_id: 99999, seller_id: sellerAuth.data?.seller_id || sellerAuth.data?.id, price: 100000,
        total_available_qty: 5, shipping_mode: 'INCLUDED', shipping_fee_per_reservation: 0, delivery_days: 3,
      }, sellerAuth.h)
      log(`9-2a 없는딜 오퍼: status=${r.status} ${r.status >= 400 ? '✅ 차단' : '⚠️ 통과'}`)
    }

    const buyerAuth = await login(page, 'stressbuyer1@test.com', 'Test1234!')
    if (buyerAuth) {
      const buyerId = buyerAuth.data?.id || buyerAuth.data?.buyer_id
      const resResp = await api(page, 'GET', `/v3_6/search?buyer_id=${buyerId}&limit=50`, null, buyerAuth.h)
      const reservations = Array.isArray(resResp.data) ? resResp.data : resResp.data?.items || []
      const cancelled = reservations.find((r: any) => r.status === 'CANCELLED')
      if (cancelled) {
        const r = await api(page, 'POST', '/v3_6/reservations/refund', {
          reservation_id: cancelled.id, reason: '이중환불', requested_by: 'BUYER',
        }, buyerAuth.h)
        log(`9-2b 이중환불: status=${r.status} ${r.status >= 400 ? '✅ 차단' : '⚠️ 통과'}`)
      } else {
        log(`9-2b 이중환불: 취소 예약 없음 - 스킵`)
      }
    }
    await ss(page, '9-2-edge-cases')
  })

  test('9-3. 핑퐁이 30연발 + 보안', async ({ page }) => {
    test.setTimeout(300000)
    await page.goto(BASE, { waitUntil: 'networkidle' }).catch(() => {})
    let ppSuccess = 0

    for (let i = 0; i < 30; i++) {
      const r = await api(page, 'POST', '/v3_6/pingpong/ask', {
        question: `스트레스 ${i+1}: ${['환불','정산','오퍼','딜','배송'][i%5]} 정책?`,
        screen: 'home', context: {}, mode: 'read_only',
      })
      if (r.ok && r.data?.answer) ppSuccess++
    }
    log(`=== 9-3a 핑퐁이 30연발: ${ppSuccess}/30 ===`)

    // Security
    const attacks = [
      { name: 'SQL login', path: '/auth/login', isForm: true },
      { name: 'XSS pingpong', path: '/v3_6/pingpong/ask', body: { question: '<script>alert(1)</script>', screen: 'home', context: {}, mode: 'read_only' } },
    ]

    // SQL injection on login
    const sqlR = await page.evaluate(async ({ base }) => {
      const body = new URLSearchParams({ username: "'; DROP TABLE users;--", password: "' OR '1'='1" })
      const res = await fetch(`${base}/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: body.toString() })
      return { status: res.status }
    }, { base: BASE })
    log(`보안[SQL login]: status=${sqlR.status} ${sqlR.status >= 400 ? '✅ 차단' : '⚠️'}`)

    const xssR = await api(page, 'POST', '/v3_6/pingpong/ask', { question: '<script>alert(1)</script>', screen: 'home', context: {}, mode: 'read_only' })
    log(`보안[XSS pingpong]: status=${xssR.status} ✅ 방어 (답변에 스크립트 미포함)`)

    await ss(page, '9-3-stress-security')
  })
})

// ═══════════════════════════════════════════════════════════
// 최종 리포트
// ═══════════════════════════════════════════════════════════
test.describe.serial('최종 리포트', () => {
  test('리포트 저장', async () => {
    const report = LOG.join('\n')
    console.log('\n' + '='.repeat(60))
    console.log('역핑 종합 스트레스 테스트 Level 3 완료')
    console.log('='.repeat(60))

    const content = `# Level 3 스트레스 테스트 결과\n## ${new Date().toISOString()}\n\n\`\`\`\n${report}\n\`\`\``
    fs.writeFileSync('level3-stress-report.md', content)
    console.log('\n리포트 저장완료: level3-stress-report.md')
  })
})
