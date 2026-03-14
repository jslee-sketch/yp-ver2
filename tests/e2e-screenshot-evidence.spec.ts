import { test, expect } from "@playwright/test";

const BASE = "https://web-production-defb.up.railway.app";
const DOMAIN = "web-production-defb.up.railway.app";

let adminToken = "";

test.beforeAll(async ({ request }) => {
  const resp = await request.post(`${BASE}/auth/login`, {
    form: { username: "admin@yeokping.com", password: "admin1234!" },
  });
  const body = await resp.json();
  adminToken = body.access_token;
});

/**
 * Navigate to any SPA page with maintenance bypass + auth.
 *
 * Key insight: Some paths (e.g., /admin/reservations) collide with API GET routes.
 * For those, we must load the SPA first at a non-colliding path, set auth,
 * then use client-side link navigation.
 */
async function gotoPage(
  page: any,
  path: string,
  role: string = "admin",
  opts?: { apiCollision?: boolean }
) {
  // 1. Set maintenance bypass cookie
  await page.context().addCookies([
    { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
  ]);

  // 2. Navigate to a NEUTRAL page first (no auth required, no API collision)
  await page.goto(`${BASE}/login`);
  await page.waitForTimeout(1500);

  // 3. Set auth in localStorage BEFORE navigating to target
  const userObj: any = { id: 1, role, email: `${role}@yeokping.com` };
  if (role === "buyer") userObj.nickname = "TestBuyer";
  if (role === "seller") userObj.business_name = "TestSeller";

  await page.evaluate(
    ([t, u]: [string, string]) => {
      localStorage.setItem("access_token", t);
      localStorage.setItem("token", t);
      localStorage.setItem("user", u);
    },
    [adminToken, JSON.stringify(userObj)]
  );

  // 4. Navigate to target path
  if (opts?.apiCollision) {
    // For paths that collide with API routes, load a safe admin page first
    // then use sidebar link click for SPA navigation
    const safePath = role === "admin" ? "/admin" : "/";
    await page.goto(`${BASE}${safePath}`);
    await page.waitForTimeout(2500);
    // Try to find and click a sidebar link to the target
    const linkSel = `a[href="${path}"], a[href*="${path.split("/").pop()}"]`;
    const link = await page.$(linkSel);
    if (link) {
      await link.click();
      await page.waitForTimeout(3000);
    } else {
      // Fallback: pushState for React Router
      await page.evaluate((p: string) => {
        window.history.pushState({}, "", p);
        window.dispatchEvent(new PopStateEvent("popstate"));
      }, path);
      await page.waitForTimeout(3000);
    }
  } else {
    await page.goto(`${BASE}${path}`);
    await page.waitForTimeout(3000);
  }
}

// ══════════════════════════════════════════
// Admin Panel Screenshots
// ══════════════════════════════════════════
test.describe("Admin Panel", () => {
  test("admin-dashboard", async ({ page }) => {
    await gotoPage(page, "/admin", "admin");
    await page.screenshot({ path: "screenshots/admin-dashboard.png", fullPage: true });
  });

  // ALL admin sub-pages collide with API routes — use SPA navigation
  const adminPages = [
    "reservations", "deals", "offers", "settlements",
    "notifications", "announcements",
    "disputes", "refunds", "delivery", "tax-invoices",
    "buyers", "sellers", "stats", "logs",
    "anomalies", "reports", "policy-params",
  ];
  for (const pg of adminPages) {
    test(`admin-${pg}`, async ({ page }) => {
      await gotoPage(page, `/admin/${pg}`, "admin", { apiCollision: true });
      await page.screenshot({ path: `screenshots/admin-${pg}.png`, fullPage: true });
    });
  }
});

// ══════════════════════════════════════════
// Public Pages
// ══════════════════════════════════════════
test.describe("Public Pages", () => {
  test("homepage", async ({ page }) => {
    await gotoPage(page, "/", "buyer");
    await page.screenshot({ path: "screenshots/homepage.png", fullPage: true });
  });

  test("login-page", async ({ page }) => {
    await page.context().addCookies([
      { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
    ]);
    await page.goto(`${BASE}/login`);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "screenshots/login-page.png", fullPage: true });
  });

  test("register-page", async ({ page }) => {
    await page.context().addCookies([
      { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
    ]);
    await page.goto(`${BASE}/register`);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "screenshots/register-page.png", fullPage: true });
  });
});

// ══════════════════════════════════════════
// Buyer Pages
// ══════════════════════════════════════════
test.describe("Buyer Pages", () => {
  test("buyer-orders", async ({ page }) => {
    await gotoPage(page, "/my-orders", "buyer");
    await page.screenshot({ path: "screenshots/buyer-orders.png", fullPage: true });
  });

  test("deal-create", async ({ page }) => {
    await gotoPage(page, "/deal/create", "buyer");
    await page.screenshot({ path: "screenshots/deal-create.png", fullPage: true });
  });

  test("refund-simulator", async ({ page }) => {
    await gotoPage(page, "/buyer/refund-simulator", "buyer");
    await page.screenshot({ path: "screenshots/buyer-refund-simulator.png", fullPage: true });
  });

  test("deals-list", async ({ page }) => {
    await gotoPage(page, "/deals", "buyer");
    await page.screenshot({ path: "screenshots/deals-list.png", fullPage: true });
  });

  test("notifications", async ({ page }) => {
    await gotoPage(page, "/notifications", "buyer");
    await page.screenshot({ path: "screenshots/buyer-notifications.png", fullPage: true });
  });

  test("points", async ({ page }) => {
    await gotoPage(page, "/points", "buyer");
    await page.screenshot({ path: "screenshots/buyer-points.png", fullPage: true });
  });

  test("settings", async ({ page }) => {
    await gotoPage(page, "/settings", "buyer");
    await page.screenshot({ path: "screenshots/buyer-settings.png", fullPage: true });
  });
});

// ══════════════════════════════════════════
// Seller Pages
// ══════════════════════════════════════════
test.describe("Seller Pages", () => {
  test("seller-dashboard", async ({ page }) => {
    await gotoPage(page, "/seller", "seller");
    await page.screenshot({ path: "screenshots/seller-dashboard.png", fullPage: true });
  });

  test("seller-settlements", async ({ page }) => {
    await gotoPage(page, "/seller/settlements", "seller");
    await page.screenshot({ path: "screenshots/seller-settlements.png", fullPage: true });
  });

  test("seller-refunds", async ({ page }) => {
    await gotoPage(page, "/seller/refunds", "seller");
    await page.screenshot({ path: "screenshots/seller-refunds.png", fullPage: true });
  });

  test("seller-offers", async ({ page }) => {
    await gotoPage(page, "/seller/offers", "seller");
    await page.screenshot({ path: "screenshots/seller-offers.png", fullPage: true });
  });
});

// ══════════════════════════════════════════
// Arena Pages
// ══════════════════════════════════════════
test.describe("Arena Pages", () => {
  test("arena-main", async ({ page }) => {
    await page.context().addCookies([
      { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
    ]);
    await page.goto(`${BASE}/arena`);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "screenshots/arena-main.png", fullPage: true });
  });

  test("arena-rankings", async ({ page }) => {
    await page.context().addCookies([
      { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
    ]);
    // /arena/rankings collides with API — use SPA nav
    await page.goto(`${BASE}/arena`);
    await page.waitForTimeout(2000);
    const link = await page.$('a[href="/arena/rankings"]');
    if (link) {
      await link.click();
      await page.waitForTimeout(3000);
    } else {
      await page.evaluate(() => {
        window.history.pushState({}, "", "/arena/rankings");
        window.dispatchEvent(new PopStateEvent("popstate"));
      });
      await page.waitForTimeout(3000);
    }
    await page.screenshot({ path: "screenshots/arena-rankings.png", fullPage: true });
  });

  test("arena-map", async ({ page }) => {
    await page.context().addCookies([
      { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
    ]);
    // /arena/map collides with API
    await page.goto(`${BASE}/arena`);
    await page.waitForTimeout(2000);
    const link = await page.$('a[href="/arena/map"]');
    if (link) {
      await link.click();
      await page.waitForTimeout(3000);
    } else {
      await page.evaluate(() => {
        window.history.pushState({}, "", "/arena/map");
        window.dispatchEvent(new PopStateEvent("popstate"));
      });
      await page.waitForTimeout(3000);
    }
    await page.screenshot({ path: "screenshots/arena-map.png", fullPage: true });
  });
});

// ══════════════════════════════════════════
// Donzzul & Dispute
// ══════════════════════════════════════════
test.describe("Other Pages", () => {
  test("donzzul-main", async ({ page }) => {
    await page.context().addCookies([
      { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
    ]);
    await page.goto(`${BASE}/donzzul`);
    await page.waitForTimeout(3000);
    await page.screenshot({ path: "screenshots/donzzul-main.png", fullPage: true });
  });

  test("dispute-detail", async ({ page }) => {
    await gotoPage(page, "/disputes/1", "admin");
    await page.screenshot({ path: "screenshots/dispute-detail.png", fullPage: true });
  });

  test("terms", async ({ page }) => {
    await page.context().addCookies([
      { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
    ]);
    await page.goto(`${BASE}/terms`);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "screenshots/terms-page.png", fullPage: true });
  });

  test("privacy", async ({ page }) => {
    await page.context().addCookies([
      { name: "yp_access", value: "yeokping2026", domain: DOMAIN, path: "/" },
    ]);
    await page.goto(`${BASE}/privacy`);
    await page.waitForTimeout(2000);
    await page.screenshot({ path: "screenshots/privacy-page.png", fullPage: true });
  });
});
