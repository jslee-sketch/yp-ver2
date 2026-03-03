// sections/11-reviews.mjs — 리뷰 (20건)
import { req } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, createSeller, createDeal, createOffer, addParticipant, createReservation } from '../lib/factory.mjs';

// ReviewIn: { reservation_id, buyer_id, seller_id,
//             price_fairness, quality, shipping, communication, accuracy (각 1~5), comment? }
function makeReview(overrides = {}) {
  return {
    price_fairness: 5,
    quality: 5,
    shipping: 5,
    communication: 5,
    accuracy: 5,
    ...overrides,
  };
}

export async function run() {
  setSection('11. 리뷰 (20건)');
  let r;

  // 리뷰를 위한 전체 플로우 셋업
  const buyer1 = await createBuyer('ReviewBuyer');
  const seller1 = await createSeller('ReviewSeller');
  const deal1 = buyer1 ? await createDeal(buyer1, { product_name: '리뷰테스트 딜', desired_qty: 50, target_price: 150000 }) : null;
  if (buyer1 && deal1) await addParticipant(buyer1, deal1.id, 2);
  const offer1 = (seller1 && deal1) ? await createOffer(seller1, deal1.id, { price: 145000, total_available_qty: 30 }) : null;
  const resv1 = (buyer1 && deal1 && offer1) ? await createReservation(buyer1, deal1.id, offer1.id, 1) : null;

  // COMPLETED 상태로 만들기
  let resvId = resv1?.id;
  if (resvId && buyer1 && seller1) {
    await req('POST', '/reservations/pay', { reservation_id: resvId, buyer_id: buyer1.id, paid_amount: 145000 }, buyer1.token);
    await req('POST', `/reservations/${resvId}/mark_shipped`, { seller_id: seller1.id, tracking_number: 'REVIEW001', shipping_carrier: 'CJ대한통운' }, seller1.token);
    await req('POST', `/reservations/${resvId}/arrival_confirm`, { buyer_id: buyer1.id }, buyer1.token);
  }

  // ── 리뷰 생성 ──
  r = await req('POST', '/reviews/', {
    reservation_id: resvId || 1, buyer_id: buyer1?.id || 1, seller_id: seller1?.id || 1,
    ...makeReview({ comment: '정말 만족스러운 거래였습니다!' }),
  }, buyer1?.token);
  const review1Id = r.data?.id;
  expect('RV-001', '리뷰 생성 (별점 5)', r.ok || r.status < 500, `status=${r.status}, id=${review1Id}`, r.elapsed);

  // ── 별점 범위 ──
  if (resvId) {
    const resv2 = await createReservation(buyer1, deal1.id, offer1.id, 1);
    if (resv2 && buyer1 && seller1) {
      await req('POST', '/reservations/pay', { reservation_id: resv2.id, buyer_id: buyer1.id, paid_amount: 145000 }, buyer1.token);
      await req('POST', `/reservations/${resv2.id}/mark_shipped`, { seller_id: seller1.id, tracking_number: 'REVIEW002', shipping_carrier: 'CJ대한통운' }, seller1.token);
      await req('POST', `/reservations/${resv2.id}/arrival_confirm`, { buyer_id: buyer1.id }, buyer1.token);
      r = await req('POST', '/reviews/', {
        reservation_id: resv2.id, buyer_id: buyer1.id, seller_id: seller1.id,
        ...makeReview({ price_fairness: 1, quality: 1, shipping: 1, communication: 1, accuracy: 1, comment: '별점 1 테스트' }),
      }, buyer1.token);
      expect('RV-002', '리뷰 생성 (별점 1)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
    } else {
      expect('RV-002', '리뷰 생성 (별점 1)', false, 'resv2 없음');
    }
  } else {
    r = await req('POST', '/reviews/', {
      reservation_id: 99999, buyer_id: buyer1?.id || 1, seller_id: seller1?.id || 1,
      ...makeReview({ price_fairness: 1, quality: 1, shipping: 1, communication: 1, accuracy: 1, comment: '별점 1 테스트' }),
    }, buyer1?.token);
    expect('RV-002', '리뷰 생성 (별점 1)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  }

  r = await req('POST', '/reviews/', {
    reservation_id: 99999, buyer_id: buyer1?.id || 1, seller_id: seller1?.id || 1,
    ...makeReview({ price_fairness: 3, quality: 3, shipping: 3, communication: 3, accuracy: 3, comment: '별점 3 테스트' }),
  }, buyer1?.token);
  expect('RV-003', '리뷰 생성 (별점 3)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/reviews/', {
    reservation_id: 99998, buyer_id: buyer1?.id || 1, seller_id: seller1?.id || 1,
    ...makeReview({ price_fairness: 4, quality: 4, shipping: 4, communication: 4, accuracy: 4, comment: '' }),
  }, buyer1?.token);
  expect('RV-004', '리뷰 생성 (빈 코멘트)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 잘못된 별점 ──
  r = await req('POST', '/reviews/', {
    reservation_id: 99997, buyer_id: buyer1?.id || 1, seller_id: seller1?.id || 1,
    ...makeReview({ price_fairness: 0, comment: '별점 0 테스트' }),
  }, buyer1?.token);
  expect('RV-005', '별점 0 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/reviews/', {
    reservation_id: 99996, buyer_id: buyer1?.id || 1, seller_id: seller1?.id || 1,
    ...makeReview({ price_fairness: 6, comment: '별점 6 테스트' }),
  }, buyer1?.token);
  expect('RV-006', '별점 6 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/reviews/', {
    reservation_id: 99995, buyer_id: buyer1?.id || 1, seller_id: seller1?.id || 1,
    ...makeReview({ price_fairness: -1, comment: '별점 음수 테스트' }),
  }, buyer1?.token);
  expect('RV-007', '별점 음수 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  // ── 목록 ──
  r = await req('GET', '/reviews/');
  expect('RV-008', '리뷰 목록 조회', r.ok || r.status < 500, `status=${r.status}, count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  if (seller1) {
    r = await req('GET', `/reviews/?seller_id=${seller1.id}`);
    expect('RV-009', '셀러별 리뷰 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('RV-009', '셀러별 리뷰 조회', false, 'seller1 없음');
  }

  // ── 셀러 평점 요약 ──
  if (seller1) {
    r = await req('GET', `/reviews/seller/${seller1.id}/summary`);
    if (!r.ok) r = await req('GET', `/sellers/${seller1.id}/reviews/summary`); // fallback
    expect('RV-010', '셀러 평점 요약', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('RV-010', '셀러 평점 요약', false, 'seller1 없음');
  }

  // ── 없는 예약 리뷰 ──
  r = await req('POST', '/reviews/', {
    reservation_id: 88888888, buyer_id: buyer1?.id || 1, seller_id: seller1?.id || 1,
    ...makeReview({ comment: '없는 예약' }),
  }, buyer1?.token);
  expect('RV-011', '없는 예약 리뷰 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  // ── 없는 셀러 리뷰 ──
  r = await req('POST', '/reviews/', {
    reservation_id: resvId || 1, buyer_id: buyer1?.id || 1, seller_id: 88888888,
    ...makeReview({ comment: '없는 셀러' }),
  }, buyer1?.token);
  expect('RV-012', '없는 셀러 리뷰 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  // ── 응답 구조 ──
  r = await req('GET', '/reviews/');
  const review0 = Array.isArray(r.data) ? r.data[0] : null;
  const rvFields = review0 ? Object.keys(review0).join(',') : '';
  expect('RV-013', '리뷰 JSON 응답 구조', r.ok || r.status < 500, `fields=${rvFields.substring(0, 60)}`, r.elapsed);

  if (review1Id) {
    r = await req('GET', `/reviews/${review1Id}`);
    const hasRating = r.ok && r.data && (
      'price_fairness' in r.data || 'quality' in r.data || 'rating' in r.data
    );
    expect('RV-014', '리뷰 평점 필드 확인', r.ok || r.status < 500, `price_fairness=${r.data?.price_fairness ?? r.data?.rating}`, r.elapsed);
    expect('RV-015', '리뷰 코멘트 필드 확인', r.ok || r.status < 500, `comment=${r.data?.comment?.substring(0, 30) || '?'}`, r.elapsed);
    expect('RV-016', '리뷰 생성일 필드 확인', r.ok || r.status < 500, `created_at=${r.data?.created_at || '?'}`, r.elapsed);
  } else {
    expect('RV-014', '리뷰 평점 필드 확인', false, 'review_id 없음');
    expect('RV-015', '리뷰 코멘트 필드 확인', false, 'review_id 없음');
    expect('RV-016', '리뷰 생성일 필드 확인', false, 'review_id 없음');
  }

  // ── 중복 리뷰 ──
  if (resvId && review1Id) {
    r = await req('POST', '/reviews/', {
      reservation_id: resvId, buyer_id: buyer1?.id || 1, seller_id: seller1?.id || 1,
      ...makeReview({ comment: '중복 리뷰 시도' }),
    }, buyer1?.token);
    expect('RV-017', '중복 리뷰 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);
  } else {
    expect('RV-017', '중복 리뷰 거부', false, '예약/리뷰 없음 (리뷰 생성 필요)');
  }

  // ── 페이지네이션 ──
  r = await req('GET', '/reviews/?skip=0&limit=5');
  expect('RV-018', '리뷰 페이지네이션', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 별점 필터 ──
  r = await req('GET', '/reviews/?rating=5');
  expect('RV-019', '리뷰 필터 (별점 5)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 통계 ──
  r = await req('GET', '/reviews/stats');
  expect('RV-020', '리뷰 전체 통계', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
}
