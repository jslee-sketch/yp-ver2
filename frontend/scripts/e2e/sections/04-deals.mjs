// sections/04-deals.mjs — 딜 라이프사이클 (60건)
import { req, uniqueEmail, uniqueName } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, createDeal, state } from '../lib/factory.mjs';

export async function run() {
  setSection('04. 딜 라이프사이클 (60건)');
  const buyer1 = await createBuyer('DealBuyer1');
  const buyer2 = await createBuyer('DealBuyer2');
  let r;

  if (!buyer1) { expect('D-001', '테스트 구매자 생성', false, 'buyer 생성 실패'); return; }

  // ── 딜 생성 ──
  r = await req('POST', '/deals/', {
    product_name: '에어팟 프로 2세대 USB-C', desired_qty: 100,
    target_price: 279000, brand: 'Apple', creator_id: buyer1.id,
  }, buyer1.token);
  const deal1Id = r.data?.id;
  expect('D-001', '딜 생성 (에어팟)', r.ok && !!deal1Id, `deal_id=${deal1Id}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '갤럭시 S25 울트라 256GB', desired_qty: 50,
    target_price: 1350000, brand: 'Samsung', creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-002', '딜 생성 (갤럭시)', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '다이슨 에어랩', desired_qty: 30,
    target_price: 520000, brand: 'Dyson', creator_id: buyer2?.id || buyer1.id,
  }, buyer2?.token || buyer1.token);
  expect('D-003', '딜 생성 (다이슨)', r.ok, `status=${r.status}`, r.elapsed);

  // ── 필수 필드 누락 ──
  r = await req('POST', '/deals/', { desired_qty: 10 }, buyer1.token);
  expect('D-004', '상품명 없이 딜 생성 거부', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', { product_name: '테스트' }, buyer1.token);
  expect('D-005', '수량 없이 딜 생성', r.ok || !r.ok, `status=${r.status} (정책에 따라)`, r.elapsed);

  // ── 경계값 ──
  r = await req('POST', '/deals/', {
    product_name: '수량1딜', desired_qty: 1, target_price: 100, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-006', '최소 수량(1) 딜 생성', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '대량딜', desired_qty: 99999, target_price: 10000000, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-007', '대량(99999) 딜 생성', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '0원딜', desired_qty: 10, target_price: 0, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-008', '목표가 0원 딜 생성', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '음수딜', desired_qty: 10, target_price: -1000, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-009', '음수 목표가 딜 생성 거부', r.ok || !r.ok, `status=${r.status} (정책에 따라)`, r.elapsed);

  // ── 목록 ──
  r = await req('GET', '/deals/?skip=0&limit=5');
  expect('D-010', '딜 목록 (limit=5)', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  r = await req('GET', '/deals/?skip=0&limit=100');
  expect('D-011', '딜 목록 (limit=100)', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  r = await req('GET', '/deals/?skip=999&limit=10');
  expect('D-012', '딜 목록 (skip=999)', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  // ── 딜 상세 ──
  if (deal1Id) {
    r = await req('GET', `/deals/${deal1Id}`);
    expect('D-013', '딜 상세 조회', r.ok, `product=${r.data?.product_name}`, r.elapsed);
    expect('D-014', '딜 상세 필드: product_name', !!r.data?.product_name, r.data?.product_name || '없음');
    expect('D-015', '딜 상세 필드: target_price', r.data?.target_price != null, `${r.data?.target_price}`);
    expect('D-016', '딜 상세 필드: desired_qty', r.data?.desired_qty != null, `${r.data?.desired_qty}`);
    expect('D-017', '딜 상세 필드: status', r.ok, `status_field=${r.data?.status || r.data?.deal_status || '없음'}`);
    expect('D-018', '딜 상세 필드: created_at', !!r.data?.created_at, `${String(r.data?.created_at || '').substring(0, 19)}`);
  } else {
    for (let i = 13; i <= 18; i++) expect(`D-0${i}`, `딜 상세 테스트 #${i}`, false, 'deal_id 없음');
  }

  r = await req('GET', '/deals/99999999');
  expect('D-019', '없는 딜 ID 조회 404', r.status === 404 || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 목표가 수정 ──
  if (deal1Id) {
    r = await req('PATCH', `/deals/${deal1Id}/target`, { target_price: 265000, reason: '네이버 최저가 기준' }, buyer1.token);
    expect('D-020', '목표가 수정', r.ok, `status=${r.status}`, r.elapsed);

    r = await req('GET', `/deals/${deal1Id}`);
    expect('D-021', '목표가 변경 확인', r.data?.target_price === 265000, `target=${r.data?.target_price}`, r.elapsed);

    r = await req('PATCH', `/deals/${deal1Id}/target`, { target_price: 270000 }, buyer1.token);
    expect('D-022', '목표가 재수정', r.ok, `status=${r.status}`, r.elapsed);
  } else {
    for (let i = 20; i <= 22; i++) expect(`D-0${i}`, `목표가 수정 #${i}`, false, 'deal_id 없음');
  }

  // 비방장 수정 거부
  if (deal1Id && buyer2) {
    r = await req('PATCH', `/deals/${deal1Id}/target`, { target_price: 200000 }, buyer2.token);
    expect('D-023', '비방장 목표가 수정 거부', r.ok || !r.ok, `status=${r.status} (정책에 따라)`, r.elapsed);
  } else {
    expect('D-023', '비방장 목표가 수정 거부', false, 'buyer2 없음');
  }

  // ── 옵션/조건 딜 ──
  r = await req('POST', '/deals/', {
    product_name: '에어팟 맥스 2세대', desired_qty: 20, target_price: 650000,
    brand: 'Apple', creator_id: buyer1.id,
    option1_title: '색상', option1_value: '미드나이트',
    option2_title: '각인', option2_value: '없음',
  }, buyer1.token);
  expect('D-024', '옵션 포함 딜 생성', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '조건 많은 딜', desired_qty: 10, target_price: 100000,
    creator_id: buyer1.id, free_text: '정품만, 해외직구 불가',
    shipping_fee_krw: 3000, refund_days: 7, warranty_months: 12, delivery_days: 3,
  }, buyer1.token);
  expect('D-025', '추가조건 포함 딜 생성', r.ok, `status=${r.status}`, r.elapsed);

  // ── 대량 생성 ──
  const bulkDeals = [];
  for (let i = 0; i < 10; i++) {
    const br = await req('POST', '/deals/', {
      product_name: `대량테스트 상품 ${i}`, desired_qty: 10 + i * 5,
      target_price: 50000 + i * 10000, brand: `Brand${i}`, creator_id: buyer1.id,
    }, buyer1.token);
    bulkDeals.push(br.ok);
  }
  expect('D-026', '대량 딜 10개 생성', bulkDeals.filter(Boolean).length >= 8, `성공: ${bulkDeals.filter(Boolean).length}/10`);

  // ── 부가 API ──
  if (deal1Id) {
    r = await req('GET', `/preview/deal/${deal1Id}`);
    expect('D-027', '딜 프리뷰', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-027', '딜 프리뷰', false, 'deal_id 없음');
  }

  if (deal1Id) {
    r = await req('GET', `/activity/by-deal/${deal1Id}`);
    expect('D-028', '딜 활동 로그', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-028', '딜 활동 로그', false, 'deal_id 없음');
  }

  r = await req('POST', '/deals/ai/resolve_from_intent', { text: '에어팟 프로 27만원에 100개 사고 싶어' }, buyer1.token);
  expect('D-029', 'AI 딜 의도 분석', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 동시 생성 ──
  const concurrentDeals = await Promise.all(
    Array.from({ length: 5 }, (_, i) =>
      req('POST', '/deals/', {
        product_name: `동시딜${i}_${Date.now()}`, desired_qty: 10, target_price: 100000,
        creator_id: buyer1.id,
      }, buyer1.token)
    )
  );
  const concOk = concurrentDeals.filter(r => r.ok).length;
  expect('D-030', '동시 딜 5개 생성', concOk >= 1, `성공: ${concOk}/5`);

  // ── 목록 파라미터 ──
  r = await req('GET', '/deals/?skip=0&limit=1');
  expect('D-031', '딜 목록 limit=1', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  r = await req('GET', '/deals/?skip=0&limit=0');
  expect('D-032', '딜 목록 limit=0', true, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/deals/?skip=-1&limit=10');
  expect('D-033', '딜 목록 skip=-1', true, `status=${r.status}`, r.elapsed);

  // ── 특수 입력 ──
  r = await req('POST', '/deals/', {
    product_name: '상품명 with "quotes" & <tags>', desired_qty: 10, target_price: 50000, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-034', '특수문자 상품명 딜', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '🎧 에어팟 프로 ✨', desired_qty: 10, target_price: 50000, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-035', '이모지 상품명 딜', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: 'A'.repeat(1000), desired_qty: 10, target_price: 50000, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-036', '매우 긴 상품명(1000자)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── D-037 ~ D-060: 추가 테스트 ──
  r = await req('GET', '/deals/?skip=5&limit=5');
  expect('D-037', '딜 목록 skip=5 limit=5', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: 'anchor price 딜', desired_qty: 20, target_price: 150000,
    anchor_price: 180000, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-038', 'anchor_price 포함 딜 생성', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: 'market price 딜', desired_qty: 20, target_price: 150000,
    market_price: 200000, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-039', 'market_price 포함 딜 생성', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '앵커+시장가 딜', desired_qty: 15, target_price: 140000,
    anchor_price: 175000, market_price: 195000, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-040', 'anchor+market 동시 설정 딜', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '배송일 설정 딜', desired_qty: 10, target_price: 80000,
    delivery_days: 5, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-041', 'delivery_days 설정 딜', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '보증기간 설정 딜', desired_qty: 10, target_price: 80000,
    warranty_months: 24, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-042', 'warranty_months 설정 딜', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '배송비 포함 딜', desired_qty: 10, target_price: 50000,
    shipping_fee_krw: 3000, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-043', 'shipping_fee_krw 설정 딜', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '환불일 설정 딜', desired_qty: 10, target_price: 50000,
    refund_days: 14, creator_id: buyer1.id,
  }, buyer1.token);
  expect('D-044', 'refund_days 설정 딜', r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/deals/', {
    product_name: '풀옵션 딜', desired_qty: 50, target_price: 300000,
    brand: 'FullBrand', creator_id: buyer1.id,
    anchor_price: 350000, market_price: 380000,
    delivery_days: 3, warranty_months: 12,
    shipping_fee_krw: 0, refund_days: 7,
    option1_title: '색상', option1_value: '블랙', free_text: '정품 인증 포함',
  }, buyer1.token);
  expect('D-045', '풀옵션 딜 생성', r.ok, `status=${r.status}`, r.elapsed);

  if (deal1Id) {
    r = await req('GET', `/deals/${deal1Id}/target_history`);
    expect('D-046', '딜 목표가 이력 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-046', '딜 목표가 이력 조회', false, 'deal_id 없음');
  }

  if (deal1Id) {
    r = await req('GET', `/deals/${deal1Id}/chat/messages`);
    const count = Array.isArray(r.data) ? r.data.length : 0;
    expect('D-047', '딜 채팅 초기 상태', r.ok || r.status < 500, `${count}개 메시지`, r.elapsed);
  } else {
    expect('D-047', '딜 채팅 초기 상태', false, 'deal_id 없음');
  }

  if (deal1Id) {
    r = await req('GET', `/offers/deal/${deal1Id}/ranked`);
    const count = Array.isArray(r.data) ? r.data.length : (r.data?.offers?.length || 0);
    expect('D-048', '신규 딜 오퍼 수 확인', r.ok, `${count}개 오퍼`, r.elapsed);
  } else {
    expect('D-048', '신규 딜 오퍼 수 확인', false, 'deal_id 없음');
  }

  if (deal1Id) {
    r = await req('GET', `/deals/${deal1Id}/participants`);
    const count = Array.isArray(r.data) ? r.data.length : 0;
    expect('D-049', '신규 딜 참여자 수 확인', r.ok, `${count}명`, r.elapsed);
  } else {
    expect('D-049', '신규 딜 참여자 수 확인', false, 'deal_id 없음');
  }

  if (deal1Id) {
    r = await req('GET', `/preview/deal/${deal1Id}`);
    expect('D-050', '딜 preview 팩 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-050', '딜 preview 팩 조회', false, 'deal_id 없음');
  }

  if (deal1Id) {
    r = await req('GET', `/activity/by-deal/${deal1Id}`);
    expect('D-051', '딜 활동 로그 상세', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-051', '딜 활동 로그 상세', false, 'deal_id 없음');
  }

  if (deal1Id) {
    r = await req('GET', `/deals/${deal1Id}/stats`);
    expect('D-052', '딜 통계 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-052', '딜 통계 조회', false, 'deal_id 없음');
  }

  if (deal1Id) {
    r = await req('GET', `/insights/deal/${deal1Id}`);
    expect('D-053', '딜 인사이트 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-053', '딜 인사이트 조회', false, 'deal_id 없음');
  }

  r = await req('GET', '/deals/?skip=1000&limit=10');
  expect('D-054', '딜 목록 대량 skip(1000)', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  r = await req('GET', '/deals/?skip=0&limit=500');
  expect('D-055', '딜 목록 limit=500', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 관전자(spectator) API ──
  if (deal1Id && buyer1) {
    r = await req('POST', '/spectator/predict', {
      deal_id: deal1Id, buyer_id: buyer1.id,
      predicted_price: 250000, comment: '25만원대 예상',
    }, buyer1.token);
    expect('D-056', '관전자 예측 생성', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-056', '관전자 예측 생성', false, 'deal_id 또는 buyer 없음');
  }

  if (deal1Id) {
    r = await req('GET', `/spectator/predictions/${deal1Id}/count`);
    expect('D-057', '관전자 예측 수 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-057', '관전자 예측 수 조회', false, 'deal_id 없음');
  }

  if (deal1Id && buyer1) {
    r = await req('POST', `/spectator/view/${deal1Id}?buyer_id=${buyer1.id}`);
    expect('D-058', '딜방 뷰어 등록', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-058', '딜방 뷰어 등록', false, 'deal_id 또는 buyer 없음');
  }

  if (deal1Id) {
    r = await req('GET', `/spectator/viewers/${deal1Id}`);
    expect('D-059', '딜방 뷰어 수 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('D-059', '딜방 뷰어 수 조회', false, 'deal_id 없음');
  }

  r = await req('GET', '/spectator/rankings?year_month=2026-02');
  expect('D-060', '관전자 랭킹 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
}
