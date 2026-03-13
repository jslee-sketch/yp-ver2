// 공개 수요 대시보드 E2E 테스트 — 8 tests
import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL || 'https://www.yeokping.com';

test.describe('Public Demand Dashboard', () => {

  test('1. GET /public/demand — 로그인 없이 접근', async ({ request }) => {
    const res = await request.get(`${BASE}/public/demand`);
    expect(res.status()).toBe(200);
    const d = await res.json();
    expect(d).toHaveProperty('top_demands');
    expect(d).toHaveProperty('categories');
    expect(d).toHaveProperty('stats');
    expect(d).toHaveProperty('recent_successes');
    expect(d).toHaveProperty('updated_at');
    expect(Array.isArray(d.top_demands)).toBeTruthy();
  });

  test('2. 통계 카드 필드 존재', async ({ request }) => {
    const res = await request.get(`${BASE}/public/demand`);
    expect(res.status()).toBe(200);
    const d = await res.json();
    expect(d.stats).toHaveProperty('total_active_deals');
    expect(d.stats).toHaveProperty('total_buyers_30d');
    expect(d.stats).toHaveProperty('total_completed');
    expect(typeof d.stats.total_active_deals).toBe('number');
    expect(typeof d.stats.total_buyers_30d).toBe('number');
    expect(typeof d.stats.total_completed).toBe('number');
  });

  test('3. 카테고리 필터 데이터 구조', async ({ request }) => {
    const res = await request.get(`${BASE}/public/demand`);
    const d = await res.json();
    expect(Array.isArray(d.categories)).toBeTruthy();
    for (const c of d.categories) {
      expect(c).toHaveProperty('category');
      expect(c).toHaveProperty('count');
      expect(c).toHaveProperty('avg_price');
    }
  });

  test('4. 수요 목록 항목 구조', async ({ request }) => {
    const res = await request.get(`${BASE}/public/demand`);
    const d = await res.json();
    for (const item of d.top_demands) {
      expect(item).toHaveProperty('id');
      expect(item).toHaveProperty('title');
      expect(item).toHaveProperty('category');
      expect(item).toHaveProperty('target_price');
      expect(item).toHaveProperty('demand_count');
      expect(item).toHaveProperty('days_ago');
    }
  });

  test('5. 최근 성사 사례 구조', async ({ request }) => {
    const res = await request.get(`${BASE}/public/demand`);
    const d = await res.json();
    expect(Array.isArray(d.recent_successes)).toBeTruthy();
    for (const s of d.recent_successes) {
      expect(s).toHaveProperty('title');
      expect(s).toHaveProperty('category');
    }
  });

  test('6. 수요 목록은 demand_count 내림차순', async ({ request }) => {
    const res = await request.get(`${BASE}/public/demand`);
    const d = await res.json();
    const demands = d.top_demands;
    for (let i = 1; i < demands.length; i++) {
      expect(demands[i - 1].demand_count).toBeGreaterThanOrEqual(demands[i].demand_count);
    }
  });

  test('7. 반복 호출 안정성 (자동 갱신 시뮬레이션)', async ({ request }) => {
    // 3회 연속 호출
    for (let i = 0; i < 3; i++) {
      const res = await request.get(`${BASE}/public/demand`);
      expect(res.status()).toBe(200);
      const d = await res.json();
      expect(d).toHaveProperty('updated_at');
    }
  });

  test('8. top_demands 최대 20건', async ({ request }) => {
    const res = await request.get(`${BASE}/public/demand`);
    const d = await res.json();
    expect(d.top_demands.length).toBeLessThanOrEqual(20);
  });
});
