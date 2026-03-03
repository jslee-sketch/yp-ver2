// scripts/e2e/lib/client.mjs
export const BASE = process.env.API_URL || 'http://127.0.0.1:9000';

export async function req(method, path, body = null, token = null, options = {}) {
  const url = `${BASE}${path}`;
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const opts = { method, headers };

  if (options.formData) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
    if (body && typeof body === 'object') {
      const params = new URLSearchParams();
      for (const [k, v] of Object.entries(body)) params.append(k, String(v));
      opts.body = params.toString();
    } else {
      opts.body = '';
    }
  } else if (body !== null) {
    headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }

  const start = Date.now();
  const res = await fetch(url, opts);
  const elapsed = Date.now() - start;
  let data = null;
  const text = await res.text();
  try { data = JSON.parse(text); } catch { data = text; }
  return { status: res.status, ok: res.ok, data, elapsed, url, method };
}

// OAuth2PasswordRequestForm: form-urlencoded + username 필드
export async function login(email, password) {
  return req('POST', '/auth/login', { username: email, password }, null, { formData: true });
}

export async function sellerLogin(email, password) {
  return req('POST', '/auth/seller/login', { username: email, password }, null, { formData: true });
}

export function uniqueEmail() {
  return `e2e_${Date.now()}_${Math.random().toString(36).slice(2, 6)}@test.com`;
}

// nickname max 15자, pattern: ^[가-힣a-zA-Z0-9_]+$
export function uniqueName(prefix = 'E2E') {
  const rand = Math.random().toString(36).slice(2, 5); // 3자
  const ts = Date.now().toString(36).slice(-4);        // 타임스탬프 끝 4자
  return `${prefix}${ts}${rand}`.slice(0, 15);         // 최대 15자
}

export function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
