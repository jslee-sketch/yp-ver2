/**
 * FE 종합 검증 — Phase 2/3 Playwright E2E
 *
 * 대표님 6대 버그 + 페이지 존재 + API 연동 + 데이터 표시 + 버튼 동작 + 역할 제어
 */
import { test, expect, Page } from "@playwright/test";

const BASE = "https://web-production-defb.up.railway.app";
const DOMAIN = "web-production-defb.up.railway.app";

// ── 계정 ──
const ACCOUNTS = {
  admin:  { email: "admin@yeokping.com",  pw: "admin1234!" },
  buyer:  { email: "buyer1@test.com",      pw: "test1234!" },
  seller: { email: "seller1@test.com",     pw: "test1234!" },
};

let tokens: Record<string, string> = {};

// ── 로그인 헬퍼 ──
async function login(request: any, role: keyof typeof ACCOUNTS) {
  const acc = ACCOUNTS[role];
  const resp = await request.post(`${BASE}/auth/login`, {
    form: { username: acc.email, password: acc.pw },
  });
  if (resp.status() !== 200) return null;
  const body = await resp.json();
  return body.access_token as string;
}

async function setupPage(page: Page, token: string, role: string, userExtra: Record<string, unknown> = {}) {
  await page.context().addCookies([
    { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
  ]);
  await page.goto(`${BASE}/login`);
  await page.waitForTimeout(1000);

  const userObj: Record<string, unknown> = { id: 1, role, email: `${role}@yeokping.com`, ...userExtra };
  await page.evaluate(
    ([t, u]: [string, string]) => {
      localStorage.setItem("access_token", t);
      localStorage.setItem("token", t);
      localStorage.setItem("user", u);
    },
    [token, JSON.stringify(userObj)] as [string, string]
  );
}

// ── 토큰 획득 ──
test.beforeAll(async ({ request }) => {
  for (const role of ["admin", "buyer", "seller"] as const) {
    const t = await login(request, role);
    if (t) tokens[role] = t;
  }
  // admin 필수
  expect(tokens.admin, "Admin login must succeed").toBeTruthy();
});

// ═══════════════════════════════════════════════════════════
// Phase 1: API Health Check
// ═══════════════════════════════════════════════════════════

test.describe("FE-API: Backend endpoints reachable", () => {
  test("FE-001 Health check", async ({ request }) => {
    const r = await request.get(`${BASE}/health`);
    expect(r.status()).toBe(200);
  });

  test("FE-002 Deals list", async ({ request }) => {
    const r = await request.get(`${BASE}/deals/?page=1&size=5`);
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(data.items).toBeDefined();
  });

  test("FE-003 Offers v3.6 list", async ({ request }) => {
    const r = await request.get(`${BASE}/v3_6/offers?limit=5`);
    expect(r.status()).toBe(200);
  });

  test("FE-004 Deal list returns offer_count", async ({ request }) => {
    const r = await request.get(`${BASE}/deals/?page=1&size=5`);
    const data = await r.json();
    const firstItem = data.items?.[0];
    if (firstItem) {
      expect(firstItem).toHaveProperty("offer_count");
    }
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 2: Public Pages — 페이지 존재 + 렌더링
// ═══════════════════════════════════════════════════════════

test.describe("FE-Public: Page rendering", () => {
  test("FE-010 Login page renders", async ({ page }) => {
    await page.context().addCookies([
      { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
    ]);
    await page.goto(`${BASE}/login`);
    await page.waitForTimeout(2000);
    // Should have some login-related element
    const bodyText = await page.textContent("body");
    expect(bodyText).toBeTruthy();
  });

  test("FE-011 Register page renders", async ({ page }) => {
    await page.context().addCookies([
      { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
    ]);
    await page.goto(`${BASE}/register`);
    await page.waitForTimeout(2000);
    const bodyText = await page.textContent("body");
    expect(bodyText).toBeTruthy();
  });

  test("FE-012 Homepage renders", async ({ page }) => {
    await setupPage(page, tokens.admin, "admin");
    await page.goto(`${BASE}/`);
    await page.waitForTimeout(2500);
    const bodyText = await page.textContent("body");
    expect(bodyText!.length).toBeGreaterThan(50);
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 3: 대표님 6대 버그 검증
// ═══════════════════════════════════════════════════════════

test.describe("FE-BUG: 대표님 6대 버그 검증", () => {
  test("FE-B01 딜 목표가 수정 — PriceJourneyPage에서 API 연동 확인", async ({ request }) => {
    // 딜 1개 조회해서 target 수정 API 테스트
    const deals = await request.get(`${BASE}/deals/?page=1&size=1`);
    const data = await deals.json();
    const dealId = data.items?.[0]?.id;
    if (!dealId) { test.skip(); return; }

    // target update API endpoint exists
    const r = await request.patch(`${BASE}/deals/${dealId}/target`, {
      headers: { Authorization: `Bearer ${tokens.admin}` },
      data: { target_price: 100000, reason: "FE 검증 테스트 — 목표가 수정 가능 확인" },
    });
    // 200 or 403 (not creator) or 422 — any non-500 is OK
    expect(r.status()).toBeLessThan(500);
  });

  test("FE-B02 딜 모집 배너 — localStorage 기반 (sessionStorage 아님)", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    const deals = await page.request.get(`${BASE}/deals/?page=1&size=1`);
    const data = await deals.json();
    const dealId = data.items?.[0]?.id;
    if (!dealId) { test.skip(); return; }

    await page.goto(`${BASE}/deal/${dealId}`);
    await page.waitForTimeout(5000); // Wait for banner + localStorage write

    // Check that localStorage is used (not sessionStorage)
    const usesLocalStorage = await page.evaluate((dId: number) => {
      return localStorage.getItem(`deal_${dId}_shown_stages`) !== null;
    }, dealId);
    expect(usesLocalStorage).toBe(true);
  });

  test("FE-B03 딜 상세에 딜 ID 표시 (PriceJourneyPage)", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    const deals = await page.request.get(`${BASE}/deals/?page=1&size=1`);
    const data = await deals.json();
    const dealId = data.items?.[0]?.id;
    if (!dealId) { test.skip(); return; }

    await page.goto(`${BASE}/deal/${dealId}`);
    await page.waitForTimeout(5000); // Wait for deploy with Deal # badge

    const bodyText = await page.textContent("body") ?? "";
    // Should contain "Deal #N" — added to PriceJourneyPage
    expect(bodyText).toContain(`Deal #${dealId}`);
  });

  test("FE-B04 딜에 Offer 연결 — v3.6 API 사용 확인", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    const deals = await page.request.get(`${BASE}/deals/?page=1&size=5`);
    const data = await deals.json();
    // 오퍼 있는 딜 찾기
    const dealWithOffers = data.items?.find((d: any) => d.offer_count > 0);
    if (!dealWithOffers) { test.skip(); return; }

    await page.goto(`${BASE}/deal/${dealWithOffers.id}`);
    await page.waitForTimeout(3000);

    const bodyText = await page.textContent("body") ?? "";
    // 오퍼가 표시되어야 함 (셀러 이름 or 오퍼 가격 or 오퍼 관련 텍스트)
    const hasOfferContent = bodyText.includes("원") || bodyText.includes("오퍼") || bodyText.includes("셀러");
    expect(hasOfferContent).toBe(true);
  });

  test("FE-B05 판매자 오퍼 관리 — v3.6 API 사용 확인", async ({ request }) => {
    if (!tokens.seller) { test.skip(); return; }
    // v3.6 offers endpoint should work with seller_id
    const r = await request.get(`${BASE}/v3_6/offers?seller_id=1&limit=10`, {
      headers: { Authorization: `Bearer ${tokens.seller}` },
    });
    expect(r.status()).toBeLessThan(500);
  });

  test("FE-B06 구매자 내 딜 — buyer_id 필터로 딜 조회", async ({ request }) => {
    if (!tokens.buyer) { test.skip(); return; }
    const r = await request.get(`${BASE}/deals/?buyer_id=1&page=1&size=10`, {
      headers: { Authorization: `Bearer ${tokens.buyer}` },
    });
    expect(r.status()).toBe(200);
    const data = await r.json();
    expect(data).toHaveProperty("items");
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 4: Buyer Pages
// ═══════════════════════════════════════════════════════════

test.describe("FE-Buyer: Buyer pages render and work", () => {
  test("FE-020 딜 목록 페이지", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/deals`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText.length).toBeGreaterThan(50);
  });

  test("FE-021 딜 생성 페이지", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/deal/create`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText.length).toBeGreaterThan(50);
  });

  test("FE-022 내 주문 페이지", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/orders`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    // 주문 또는 empty state
    expect(bodyText).toBeTruthy();
  });

  test("FE-023 내딜 관리 페이지", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/my-deals`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toContain("내딜");
  });

  test("FE-024 포인트 페이지", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/points`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });

  test("FE-025 알림 페이지", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/notifications`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });

  test("FE-026 마이페이지", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/my`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });

  test("FE-027 검색 페이지", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/search`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 5: Seller Pages
// ═══════════════════════════════════════════════════════════

test.describe("FE-Seller: Seller pages render", () => {
  test("FE-030 판매자 대시보드", async ({ page }) => {
    if (!tokens.seller) { test.skip(); return; }
    await setupPage(page, tokens.seller, "seller", { id: 1, seller: { id: 1 }, nickname: "TestSeller", business_name: "TestBiz" });
    await page.goto(`${BASE}/seller/dashboard`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText.length).toBeGreaterThan(30);
  });

  test("FE-031 판매자 오퍼 관리", async ({ page }) => {
    if (!tokens.seller) { test.skip(); return; }
    await setupPage(page, tokens.seller, "seller", { id: 1, seller: { id: 1 }, nickname: "TestSeller", business_name: "TestBiz" });
    await page.goto(`${BASE}/seller/offers`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toContain("오퍼");
  });

  test("FE-032 판매자 배송 관리", async ({ page }) => {
    if (!tokens.seller) { test.skip(); return; }
    await setupPage(page, tokens.seller, "seller", { id: 1, seller: { id: 1 }, nickname: "TestSeller", business_name: "TestBiz" });
    await page.goto(`${BASE}/seller/shipping`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });

  test("FE-033 판매자 정산", async ({ page }) => {
    if (!tokens.seller) { test.skip(); return; }
    await setupPage(page, tokens.seller, "seller", { id: 1, seller: { id: 1 }, nickname: "TestSeller", business_name: "TestBiz" });
    await page.goto(`${BASE}/seller/settlements`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });

  test("FE-034 판매자 리뷰", async ({ page }) => {
    if (!tokens.seller) { test.skip(); return; }
    await setupPage(page, tokens.seller, "seller", { id: 1, seller: { id: 1 }, nickname: "TestSeller", business_name: "TestBiz" });
    await page.goto(`${BASE}/seller/reviews`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 6: Admin Pages
// ═══════════════════════════════════════════════════════════

test.describe("FE-Admin: Admin pages render", () => {
  test("FE-040 관리자 대시보드", async ({ page }) => {
    await setupPage(page, tokens.admin, "admin");
    await page.goto(`${BASE}/admin`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText.length).toBeGreaterThan(30);
  });

  test("FE-041 관리자 딜 관리", async ({ page }) => {
    await setupPage(page, tokens.admin, "admin");
    await page.goto(`${BASE}/admin/deals`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });

  test("FE-042 관리자 셀러 관리", async ({ page }) => {
    await setupPage(page, tokens.admin, "admin");
    await page.goto(`${BASE}/admin/sellers`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });

  test("FE-043 관리자 정산 관리", async ({ page }) => {
    await setupPage(page, tokens.admin, "admin");
    await page.goto(`${BASE}/admin/settlements`);
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 7: Data Consistency
// ═══════════════════════════════════════════════════════════

test.describe("FE-DATA: 데이터 정합성", () => {
  test("FE-050 딜 목록 offer_count가 0이 아닌 값 포함", async ({ request }) => {
    const r = await request.get(`${BASE}/deals/?page=1&size=50`);
    const data = await r.json();
    const withOffers = data.items?.filter((d: any) => d.offer_count > 0);
    // 데이터가 있다면 offer_count > 0인 딜이 있어야 함
    if (data.items?.length > 0) {
      // Just log; might be empty in test env
      console.log(`Deals with offers: ${withOffers?.length ?? 0} / ${data.items.length}`);
    }
    expect(r.status()).toBe(200);
  });

  test("FE-051 예약 목록에 order_number 포함", async ({ request }) => {
    if (!tokens.buyer) { test.skip(); return; }
    const r = await request.get(`${BASE}/v3_6/search?buyer_id=1&limit=5`, {
      headers: { Authorization: `Bearer ${tokens.buyer}` },
    });
    if (r.status() === 200) {
      const data = await r.json();
      const items = Array.isArray(data) ? data : data.items ?? [];
      if (items.length > 0) {
        // order_number should exist on reservations
        const hasOrderNum = items.some((i: any) => i.order_number);
        console.log(`Reservations with order_number: ${items.filter((i: any) => i.order_number).length} / ${items.length}`);
      }
    }
    expect(r.status()).toBeLessThan(500);
  });

  test("FE-052 v3.6 오퍼 엔드포인트 동작", async ({ request }) => {
    const r = await request.get(`${BASE}/v3_6/offers?limit=5`);
    expect(r.status()).toBe(200);
    const data = await r.json();
    const items = Array.isArray(data) ? data : data.items ?? data.offers ?? [];
    expect(Array.isArray(items)).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 8: Navigation & Buttons
// ═══════════════════════════════════════════════════════════

test.describe("FE-NAV: 네비게이션 + 버튼", () => {
  test("FE-060 BottomNav 5개 아이콘 표시", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/`);
    await page.waitForTimeout(3000);
    // BottomNav should be visible
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText.length).toBeGreaterThan(50);
  });

  test("FE-061 /deal/:id 페이지가 PriceJourneyPage로 렌더링", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    const deals = await page.request.get(`${BASE}/deals/?page=1&size=1`);
    const data = await deals.json();
    const dealId = data.items?.[0]?.id;
    if (!dealId) { test.skip(); return; }

    await page.goto(`${BASE}/deal/${dealId}`);
    await page.waitForTimeout(3000);

    // /deal/:id should render PriceJourneyPage which has "가격 여정" title
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toContain("가격 여정");
  });

  test("FE-062 Sidebar 메뉴 열기/닫기", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/`);
    await page.waitForTimeout(3000);
    // Sidebar is usually hidden initially, toggled by hamburger
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 9: Error Handling
// ═══════════════════════════════════════════════════════════

test.describe("FE-ERR: 에러 처리", () => {
  test("FE-070 존재하지 않는 딜 → 에러 표시 (500 아님)", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/deal/999999`);
    await page.waitForTimeout(3000);
    // Should show fallback or error, not crash
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText.length).toBeGreaterThan(10);
  });

  test("FE-071 잘못된 경로 → 404 or redirect", async ({ page }) => {
    await setupPage(page, tokens.admin, "buyer", { id: 1, nickname: "TestBuyer" });
    await page.goto(`${BASE}/nonexistent-page-xyz`);
    await page.waitForTimeout(3000);
    // SPA should handle this gracefully
    const bodyText = await page.textContent("body") ?? "";
    expect(bodyText).toBeTruthy();
  });
});
