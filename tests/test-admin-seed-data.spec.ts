import { test, expect } from '@playwright/test';

/**
 * 관리자 패널 시드 데이터 생성: 신고, 공지사항, 정책제안
 */

const BASE = 'https://web-production-defb.up.railway.app';

async function api(page: any, method: string, path: string, body?: any) {
  return page.evaluate(
    async ({ base, method, path, body }: any) => {
      const opts: any = { method, headers: { 'Content-Type': 'application/json' } };
      if (body) opts.body = JSON.stringify(body);
      const r = await fetch(`${base}${path}`, opts);
      const text = await r.text();
      try { return { status: r.status, data: JSON.parse(text) }; }
      catch { return { status: r.status, data: text }; }
    },
    { base: BASE, method, path, body },
  );
}

test.describe.serial('관리자 패널 시드 데이터 생성', () => {

  // ── 신고 (Reports) 3건 ──

  test('R1 신고 3건 생성', async ({ page }) => {
    await page.goto(BASE);
    const reports = [
      { reporter_id: 9, reporter_type: 'buyer', target_type: 'seller', target_id: 1, category: 'fraud', description: '[E2E] 허위 상품 정보 게시 신고' },
      { reporter_id: 9, reporter_type: 'buyer', target_type: 'deal', target_id: 1, category: 'abuse', description: '[E2E] 부적절한 딜 내용 신고' },
      { reporter_id: 9, reporter_type: 'seller', target_type: 'buyer', target_id: 9, category: 'other', description: '[E2E] 비매너 구매자 신고 테스트' },
    ];
    for (let i = 0; i < reports.length; i++) {
      const r = await api(page, 'POST', '/reports', reports[i]);
      console.log(`  Report ${i + 1}: status=${r.status} id=${r.data?.id}`);
      expect(r.status).toBe(201);
      expect(r.data?.id).toBeTruthy();
    }
  });

  test('R2 신고 목록 조회', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/admin/reports');
    console.log(`R2 reports count=${Array.isArray(r.data) ? r.data.length : '?'}`);
    expect(r.status).toBe(200);
    expect(Array.isArray(r.data) ? r.data.length : 0).toBeGreaterThanOrEqual(3);
  });

  // ── 공지사항 (Announcements) 3건 ──

  test('A1 공지사항 3건 생성', async ({ page }) => {
    await page.goto(BASE);
    const announcements = [
      { title: '[공지] 역핑 서비스 정기 점검 안내', content: '2026년 3월 15일 02:00~06:00 서비스 정기 점검이 진행됩니다. 이용에 참고 부탁드립니다.', category: 'system', is_pinned: true, is_published: true, target_role: 'all', author: 'admin' },
      { title: '[업데이트] 정산 시스템 개선 안내', content: '정산 처리 속도가 개선되었습니다. cooling_days 0일 설정 시 즉시 정산이 가능합니다.', category: 'update', is_pinned: false, is_published: true, target_role: 'seller', author: 'admin' },
      { title: '[이벤트] 신규 판매자 수수료 할인', content: '2026년 3월 한 달간 신규 가입 판매자 플랫폼 수수료 50% 할인 이벤트를 진행합니다.', category: 'event', is_pinned: false, is_published: true, target_role: 'seller', author: 'admin' },
    ];
    for (let i = 0; i < announcements.length; i++) {
      const r = await api(page, 'POST', '/admin/announcements', announcements[i]);
      console.log(`  Announcement ${i + 1}: status=${r.status} id=${r.data?.id} title=${r.data?.title}`);
      expect(r.status).toBe(201);
      expect(r.data?.id).toBeTruthy();
    }
  });

  test('A2 공지사항 목록 조회', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/admin/announcements');
    console.log(`A2 announcements total=${r.data?.total}`);
    expect(r.status).toBe(200);
    expect(r.data?.total || 0).toBeGreaterThanOrEqual(3);
  });

  // ── 정책제안 (Policy Proposals) 3건 ──

  test('P1 정책제안 3건 생성', async ({ page }) => {
    await page.goto(BASE);
    const proposals = [
      { title: '쿨링 기간 단축 제안', description: '현재 7일인 기본 쿨링 기간을 3일로 단축하여 셀러 정산 속도를 개선', proposal_type: 'settlement', target_param: 'cooling_days', current_value: '7', proposed_value: '3', evidence_summary: '셀러 설문 결과 78%가 쿨링 기간 단축 희망' },
      { title: '플랫폼 수수료율 조정', description: '현재 3.5% 수수료를 거래금액 구간별 차등 적용 제안', proposal_type: 'fee', target_param: 'platform_fee_rate', current_value: '0.035', proposed_value: '0.025~0.035', evidence_summary: '월 거래 1000만원 이상 셀러 이탈률 15% → 수수료 인하 필요' },
      { title: '자동 수취확인 기간 설정', description: '배송 완료 후 자동 수취확인까지의 기간을 설정 가능하도록 변경', proposal_type: 'delivery', target_param: 'auto_confirm_days', current_value: 'N/A', proposed_value: '7', evidence_summary: '수취확인 지연으로 인한 정산 대기 민원 월 평균 23건' },
    ];
    for (let i = 0; i < proposals.length; i++) {
      const r = await api(page, 'POST', '/admin/policy/proposals', proposals[i]);
      console.log(`  Proposal ${i + 1}: status=${r.status} id=${r.data?.id} title=${r.data?.title}`);
      expect(r.status).toBe(201);
      expect(r.data?.id).toBeTruthy();
    }
  });

  test('P2 정책제안 목록 조회', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/admin/policy/proposals');
    console.log(`P2 proposals count=${Array.isArray(r.data) ? r.data.length : '?'}`);
    expect(r.status).toBe(200);
    expect(Array.isArray(r.data) ? r.data.length : 0).toBeGreaterThanOrEqual(3);
  });

  // ── 환불 관리 엔드포인트 검증 ──

  test('V1 환불 관리 API 200 확인', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/admin/reservations?refund=true&limit=10');
    console.log(`V1 refund status=${r.status} count=${Array.isArray(r.data) ? r.data.length : '?'}`);
    expect(r.status).toBe(200);
  });

  // ── 세금계산서 검증 ──

  test('V2 세금계산서 API 200 확인', async ({ page }) => {
    await page.goto(BASE);
    const r = await api(page, 'GET', '/v3_6/tax-invoices');
    console.log(`V2 tax-invoices status=${r.status} total=${r.data?.total}`);
    expect(r.status).toBe(200);
    expect(r.data?.total || 0).toBeGreaterThanOrEqual(1);
  });
});
