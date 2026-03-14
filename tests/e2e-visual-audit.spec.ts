/**
 * Visual Audit E2E Tests — Production Deployment
 * Verifies public pages, auth flow, admin API, admin panel, and Pingpong KB accuracy.
 */
import { test, expect, request as pwRequest } from "@playwright/test";

const BASE = "https://web-production-defb.up.railway.app";

// ─── Helpers ───────────────────────────────────────────────

/** Login via password and return { token, userId } */
async function loginPassword(
  ctx: ReturnType<typeof pwRequest>,
  email: string,
  password: string,
): Promise<{ token: string; userId: number }> {
  const api = await ctx.newContext({ baseURL: BASE });
  const res = await api.post("/auth/login", {
    form: { username: email, password },
    timeout: 30_000,
  });
  expect(res.status()).toBe(200);
  const body = await res.json();
  const token: string = body.access_token;
  const payload = JSON.parse(
    Buffer.from(token.split(".")[1], "base64").toString(),
  );
  return { token, userId: Number(payload.sub) || 0 };
}

/** Login as admin */
async function loginAdmin(ctx: ReturnType<typeof pwRequest>) {
  return loginPassword(ctx, "admin@yeokping.com", "admin1234!");
}

/** Create API context with auth header */
async function authedContext(
  ctx: ReturnType<typeof pwRequest>,
  token: string,
) {
  return ctx.newContext({
    baseURL: BASE,
    extraHTTPHeaders: { Authorization: `Bearer ${token}` },
  });
}

// ─── Phase 1: Public Pages Load ───────────────────────────

test.describe("Phase 1 — Public pages load (no auth)", () => {
  test("Homepage (/) loads with content", async ({ page }) => {
    await page.goto(BASE + "/", { timeout: 60_000, waitUntil: "domcontentloaded" });
    // Page should have visible content (not blank)
    await expect(page.locator("body")).not.toBeEmpty();
    const content = await page.textContent("body");
    expect(content && content.trim().length).toBeGreaterThan(0);
  });

  test("Login page (/login) loads", async ({ page }) => {
    await page.goto(BASE + "/login", { timeout: 60_000, waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).not.toBeEmpty();
    const content = await page.textContent("body");
    expect(content && content.trim().length).toBeGreaterThan(0);
  });

  test("Register page (/register) loads", async ({ page }) => {
    await page.goto(BASE + "/register", { timeout: 60_000, waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).not.toBeEmpty();
    const content = await page.textContent("body");
    expect(content && content.trim().length).toBeGreaterThan(0);
  });
});

// ─── Phase 2: Auth Flow ───────────────────────────────────

test.describe("Phase 2 — Auth flow", () => {
  test("Admin login returns JWT token", async () => {
    const api = await pwRequest.newContext({ baseURL: BASE });
    const res = await api.post("/auth/login", {
      form: { username: "admin@yeokping.com", password: "admin1234!" },
      timeout: 30_000,
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.access_token).toBeTruthy();
    expect(typeof body.access_token).toBe("string");

    // Verify JWT structure (3 parts)
    const parts = body.access_token.split(".");
    expect(parts.length).toBe(3);

    // Decode payload and check role
    const payload = JSON.parse(Buffer.from(parts[1], "base64").toString());
    expect(payload.role).toBe("admin");
    await api.dispose();
  });

  test("Buyer login attempt (may fail gracefully)", async () => {
    const api = await pwRequest.newContext({ baseURL: BASE });
    const res = await api.post("/auth/login", {
      form: { username: "testbuyer@test.com", password: "test1234!" },
      timeout: 30_000,
    });
    // May return 200 or 401 — both are acceptable
    expect([200, 401, 404, 422]).toContain(res.status());
    if (res.status() === 200) {
      const body = await res.json();
      expect(body.access_token).toBeTruthy();
    }
    await api.dispose();
  });
});

// ─── Phase 3: Admin API Endpoints ─────────────────────────

test.describe("Phase 3 — Admin API endpoints return data", () => {
  let adminToken: string;

  test.beforeAll(async () => {
    const { token } = await loginAdmin(pwRequest);
    adminToken = token;
  });

  test("GET /admin/stats/counts — has buyers/sellers/deals keys", async () => {
    const api = await authedContext(pwRequest, adminToken);
    const res = await api.get("/admin/stats/counts", { timeout: 30_000 });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toHaveProperty("buyers");
    expect(body).toHaveProperty("sellers");
    expect(body).toHaveProperty("deals");
    await api.dispose();
  });

  test("GET /admin/deals?limit=2 — returns items array", async () => {
    const api = await authedContext(pwRequest, adminToken);
    const res = await api.get("/admin/deals?limit=2", { timeout: 30_000 });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toHaveProperty("items");
    expect(Array.isArray(body.items)).toBe(true);
    await api.dispose();
  });

  test("GET /admin/offers?limit=2 — returns items array", async () => {
    const api = await authedContext(pwRequest, adminToken);
    const res = await api.get("/admin/offers?limit=2", { timeout: 30_000 });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toHaveProperty("items");
    expect(Array.isArray(body.items)).toBe(true);
    await api.dispose();
  });

  test("GET /admin/reservations?limit=2 — returns items with order_number", async () => {
    const api = await authedContext(pwRequest, adminToken);
    const res = await api.get("/admin/reservations?limit=2", { timeout: 30_000 });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body).toHaveProperty("items");
    expect(Array.isArray(body.items)).toBe(true);
    if (body.items.length > 0) {
      expect(body.items[0]).toHaveProperty("order_number");
    }
    await api.dispose();
  });
});

// ─── Phase 4: Admin Panel Pages Render ────────────────────

test.describe("Phase 4 — Admin panel pages render", () => {
  let adminToken: string;

  test.beforeAll(async () => {
    const { token, userId } = await loginAdmin(pwRequest);
    adminToken = token;
  });

  async function setupAdminAuth(page: any) {
    // Navigate to base first to set localStorage on the correct origin
    await page.goto(BASE + "/", { timeout: 60_000, waitUntil: "domcontentloaded" });
    await page.evaluate(
      ({ token }: { token: string }) => {
        localStorage.setItem("token", token);
        localStorage.setItem(
          "user",
          JSON.stringify({ role: "admin", email: "admin@yeokping.com" }),
        );
      },
      { token: adminToken },
    );
  }

  test("/admin — renders (not blank)", async ({ page }) => {
    await setupAdminAuth(page);
    await page.goto(BASE + "/admin", { timeout: 60_000, waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000); // Allow SPA to render
    const content = await page.textContent("body");
    expect(content && content.trim().length).toBeGreaterThan(0);
  });

  test("/admin/deals — content renders", async ({ page }) => {
    await setupAdminAuth(page);
    await page.goto(BASE + "/admin/deals", { timeout: 60_000, waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const content = await page.textContent("body");
    expect(content && content.trim().length).toBeGreaterThan(0);
  });

  test("/admin/reservations — content renders", async ({ page }) => {
    await setupAdminAuth(page);
    await page.goto(BASE + "/admin/reservations", { timeout: 60_000, waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const content = await page.textContent("body");
    expect(content && content.trim().length).toBeGreaterThan(0);
  });
});

// ─── Phase 5: Pingpong KB Accuracy ────────────────────────

test.describe("Phase 5 — Pingpong KB accuracy", () => {
  let adminToken: string;

  test.beforeAll(async () => {
    const { token } = await loginAdmin(pwRequest);
    adminToken = token;
  });

  test("PG 수수료 질문 — '플랫폼' 또는 '역핑' 포함", async () => {
    const api = await authedContext(pwRequest, adminToken);
    const res = await api.post("/v3_6/pingpong/ask", {
      data: {
        question: "PG 수수료 누가 부담해?",
        role: "buyer",
        buyer_id: 1,
      },
      timeout: 30_000,
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    const answer: string = body.answer || body.reply || body.text || JSON.stringify(body);
    // Should mention platform/yeokping, NOT say buyer pays
    const hasCorrectKeyword =
      answer.includes("플랫폼") || answer.includes("역핑");
    const hasWrongAnswer = answer.includes("구매자 부담");
    expect(hasCorrectKeyword).toBe(true);
    expect(hasWrongAnswer).toBe(false);
    await api.dispose();
  });

  test("감가 기준 질문 — '검수' 또는 '상태' 포함", async () => {
    const api = await authedContext(pwRequest, adminToken);
    const res = await api.post("/v3_6/pingpong/ask", {
      data: {
        question: "감가는 일수 기준이야?",
        role: "buyer",
        buyer_id: 1,
      },
      timeout: 30_000,
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    const answer: string = body.answer || body.reply || body.text || JSON.stringify(body);
    // Should mention inspection/condition, NOT confirm date-based
    const hasCorrectKeyword =
      answer.includes("검수") || answer.includes("상태");
    const hasWrongAnswer = answer.includes("일수 기준 맞");
    expect(hasCorrectKeyword).toBe(true);
    expect(hasWrongAnswer).toBe(false);
    await api.dispose();
  });
});
