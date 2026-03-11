/**
 * Production Security E2E Tests — 20건
 * 프로덕션 보안 강화 검증 테스트
 */
import { test, expect, request as pwRequest } from "@playwright/test";

const BASE = process.env.BASE_URL || "http://localhost:8000";

// ─── Helpers ───────────────────────────────────────────────

/** Login via password and return {token, userId} */
async function loginPassword(
  ctx: ReturnType<typeof pwRequest>,
  email: string,
  password: string,
): Promise<{ token: string; userId: number }> {
  const api = await ctx.newContext({ baseURL: BASE });
  const res = await api.post("/auth/login", {
    form: { username: email, password },
  });
  expect(res.status()).toBe(200);
  const body = await res.json();
  const token = body.access_token;
  const payload = JSON.parse(
    Buffer.from(token.split(".")[1], "base64").toString(),
  );
  return { token, userId: Number(payload.sub) || 0 };
}

/** Login or register via social and return {token, userId, role} */
async function loginSocial(
  ctx: ReturnType<typeof pwRequest>,
  role: string = "buyer",
  suffix: string = "sectest",
): Promise<{ token: string; userId: number; role: string }> {
  const api = await ctx.newContext({ baseURL: BASE });
  // Try social login first
  const loginRes = await api.post("/auth/social/login", {
    data: { social_provider: "kakao", social_id: `${suffix}_${role}` },
  });
  let token: string;
  if (loginRes.status() === 200) {
    const body = await loginRes.json();
    token = body.access_token;
  } else {
    // Register
    const regRes = await api.post("/auth/social/register", {
      data: {
        social_provider: "kakao",
        social_id: `${suffix}_${role}`,
        email: `${suffix}_${role}@test.yeokping.com`,
        name: `Test${role}`,
        nickname: `${suffix}${role}${Date.now() % 10000}`,
        role,
      },
    });
    expect(regRes.status()).toBe(200);
    const body = await regRes.json();
    token = body.access_token;
  }
  const payload = JSON.parse(
    Buffer.from(token.split(".")[1], "base64").toString(),
  );
  return { token, userId: Number(payload.sub) || 0, role: payload.role };
}

/** Login as admin */
async function loginAdmin(ctx: ReturnType<typeof pwRequest>) {
  return loginPassword(ctx, "admin@yeokping.com", "admin1234!");
}

/** Login as buyer (social) */
async function loginBuyer(ctx: ReturnType<typeof pwRequest>) {
  return loginSocial(ctx, "buyer", "sectest");
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

// ═══════════════════════════════════════════════════════════
// Phase 1: Admin Endpoint Protection (5건)
// ═══════════════════════════════════════════════════════════

test.describe("Phase 1: Admin Endpoint Protection", () => {
  test("1. GET /admin/settlements/ without token → 401", async () => {
    const api = await (await pwRequest.newContext({ baseURL: BASE })).get(
      "/admin/settlements/",
    );
    expect(api.status()).toBe(401);
    const body = await api.json();
    expect(body.detail).toContain("Not authenticated");
  });

  test("2. GET /admin/stats/counts without token → 401", async () => {
    const api = await (await pwRequest.newContext({ baseURL: BASE })).get(
      "/admin/stats/counts",
    );
    expect(api.status()).toBe(401);
  });

  test("3. POST /admin/users/ban without token → 401", async () => {
    const api = await (await pwRequest.newContext({ baseURL: BASE })).post(
      "/admin/users/ban",
      { data: { user_id: 1, reason: "test" } },
    );
    expect(api.status()).toBe(401);
  });

  test("4. Admin endpoint with buyer token → 403 (not admin role)", async () => {
    const { token } = await loginBuyer(pwRequest);
    const ctx = await authedContext(pwRequest, token);
    const res = await ctx.get("/admin/settlements/");
    expect(res.status()).toBe(403);
    const body = await res.json();
    expect(body.detail).toContain("Admin access required");
  });

  test("5. Admin endpoint with admin token → 200", async () => {
    const { token } = await loginAdmin(pwRequest);
    const ctx = await authedContext(pwRequest, token);
    const res = await ctx.get("/admin/settlements/");
    expect([200, 422]).toContain(res.status()); // 200 or 422 (missing query params)
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 2: Public Endpoints Remain Accessible (5건)
// ═══════════════════════════════════════════════════════════

test.describe("Phase 2: Public Endpoints Accessible", () => {
  test("6. GET /health → 200 (no auth needed)", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    const res = await ctx.get("/health");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    expect(body.db).toBe("ok");
    expect(body.version).toBeDefined();
    expect(body.timestamp).toBeDefined();
  });

  test("7. GET /health/deep → 200 (no auth needed)", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    const res = await ctx.get("/health/deep");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
    expect(body.checks).toBeDefined();
  });

  test("8. GET /deals/ → 200 (public list, no auth)", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    const res = await ctx.get("/deals/");
    // deals list is public — should return 200 even without token
    expect([200, 307]).toContain(res.status());
  });

  test("9. POST /auth/login with valid admin creds → 200 + token", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    const res = await ctx.post("/auth/login", {
      form: { username: "admin@yeokping.com", password: "admin1234!" },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.access_token).toBeDefined();
    expect(body.token_type).toBe("bearer");
  });

  test("10. POST /auth/login with wrong password → 401", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    const res = await ctx.post("/auth/login", {
      form: { username: "admin@yeokping.com", password: "wrongpassword" },
    });
    expect(res.status()).toBe(401);
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 3: Rate Limiting & Error Handling (5건)
// ═══════════════════════════════════════════════════════════

test.describe("Phase 3: Rate Limiting & Error Handling", () => {
  test("11. Rate limiter returns 429 after burst", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    // Send many requests to a specific path to trigger rate limit
    // AI endpoint has limit of 10/min
    const promises: Promise<any>[] = [];
    for (let i = 0; i < 15; i++) {
      promises.push(ctx.post("/v3_6/pingpong/ask", { data: { question: "test" } }));
    }
    const results = await Promise.all(promises);
    const statuses = results.map((r) => r.status());
    // At least one should be 429
    expect(statuses).toContain(429);
  });

  test("12. 500 error hides details in production mode", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    // Hit a path that might cause an internal error
    // We test that the error response format is correct (not leaking stack traces)
    const res = await ctx.get("/api/env-check");
    if (res.status() === 500) {
      const body = await res.json();
      // Should not contain traceback or class names
      expect(typeof body.detail).toBe("string");
      expect(body.detail).not.toContain("Traceback");
    }
    // If it returns 200, that's fine too (endpoint exists)
    expect([200, 500]).toContain(res.status());
  });

  test("13. Invalid JSON body → 422 (not 500)", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    const res = await ctx.post("/auth/login", {
      headers: { "Content-Type": "application/json" },
      data: "not valid json{{{",
    });
    // FastAPI should return 422 for invalid input, not 500
    expect([400, 422]).toContain(res.status());
  });

  test("14. Non-existent API path → handled gracefully", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    const res = await ctx.get("/api/this-does-not-exist-xyz");
    // Should return either 404 or SPA fallback (200), not 500
    expect([200, 404]).toContain(res.status());
  });

  test("15. CORS headers present on response", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    const res = await ctx.get("/health", {
      headers: { Origin: "http://localhost:3000" },
    });
    expect(res.status()).toBe(200);
    const headers = res.headers();
    // CORS should allow the origin (default is *)
    expect(
      headers["access-control-allow-origin"] === "*" ||
        headers["access-control-allow-origin"] === "http://localhost:3000",
    ).toBeTruthy();
  });
});

// ═══════════════════════════════════════════════════════════
// Phase 4: JWT Security & Auth Flow (5건)
// ═══════════════════════════════════════════════════════════

test.describe("Phase 4: JWT Security & Auth Flow", () => {
  test("16. Expired/invalid JWT → 401", async () => {
    const ctx = await pwRequest.newContext({
      baseURL: BASE,
      extraHTTPHeaders: {
        Authorization: "Bearer invalid.jwt.token",
      },
    });
    const res = await ctx.get("/admin/settlements/");
    expect(res.status()).toBe(401);
  });

  test("17. JWT with tampered payload → 401", async () => {
    // Get a valid token first
    const { token } = await loginBuyer(pwRequest);
    // Tamper with the payload (change a character)
    const parts = token.split(".");
    parts[1] = parts[1].slice(0, -2) + "XX"; // corrupt payload
    const tampered = parts.join(".");

    const ctx = await pwRequest.newContext({
      baseURL: BASE,
      extraHTTPHeaders: { Authorization: `Bearer ${tampered}` },
    });
    const res = await ctx.get("/admin/settlements/");
    expect([401, 403]).toContain(res.status());
  });

  test("18. Admin login returns JWT with role=admin", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    const res = await ctx.post("/auth/login", {
      form: { username: "admin@yeokping.com", password: "admin1234!" },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    const payload = JSON.parse(
      Buffer.from(body.access_token.split(".")[1], "base64").toString(),
    );
    expect(payload.role).toBe("admin");
    expect(payload.sub).toBeDefined();
    expect(payload.exp).toBeDefined();
  });

  test("19. Buyer social login returns JWT with role=buyer", async () => {
    const { token, role } = await loginBuyer(pwRequest);
    expect(token).toBeDefined();
    expect(role).toBe("buyer");
  });

  test("20. Health check returns DB status + version + timestamp", async () => {
    const ctx = await pwRequest.newContext({ baseURL: BASE });
    const res = await ctx.get("/health");
    expect(res.status()).toBe(200);
    const body = await res.json();
    // Verify enhanced health check fields
    expect(body).toHaveProperty("ok");
    expect(body).toHaveProperty("status");
    expect(body).toHaveProperty("db");
    expect(body).toHaveProperty("version");
    expect(body).toHaveProperty("timestamp");
    expect(body.ok).toBe(true);
    expect(body.status).toBe("ok");
    expect(body.db).toBe("ok");
    expect(body.version).toMatch(/^\d+\.\d+\.\d+$/); // semver format
    // timestamp should be valid ISO 8601
    expect(new Date(body.timestamp).getTime()).toBeGreaterThan(0);
  });
});
