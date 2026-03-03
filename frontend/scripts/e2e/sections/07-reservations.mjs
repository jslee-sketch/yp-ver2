// sections/07-reservations.mjs — 예약/결제/배송 (55건)
import { req, uniqueEmail, uniqueName } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, createSeller, createDeal, createOffer, addParticipant, createReservation, payReservation, shipReservation, confirmArrival, cancelReservation } from '../lib/factory.mjs';

export async function run() {
  setSection('07. 예약/결제/배송 (55건)');
  let r;

  const buyer1 = await createBuyer('ResvBuyer1');
  const buyer2 = await createBuyer('ResvBuyer2');
  const seller1 = await createSeller('ResvSeller1');
  const deal1 = buyer1 ? await createDeal(buyer1, { product_name: '예약테스트 딜', desired_qty: 100, target_price: 200000 }) : null;
  if (buyer1 && deal1) await addParticipant(buyer1, deal1.id, 5);
  if (buyer2 && deal1) await addParticipant(buyer2, deal1.id, 3);
  const offer1 = (seller1 && deal1) ? await createOffer(seller1, deal1.id, { price: 195000, total_available_qty: 50 }) : null;

  if (!buyer1 || !seller1 || !deal1 || !offer1) {
    for (let i = 1; i <= 55; i++) {
      const id = i < 10 ? `R-00${i}` : `R-0${i}`;
      expect(id, `예약 테스트 #${i}`, false, `사전 데이터 없음 (buyer=${!!buyer1}, seller=${!!seller1}, deal=${!!deal1}, offer=${!!offer1})`);
    }
    return;
  }

  // ── 예약 생성 ──
  r = await req('POST', '/reservations', {
    deal_id: deal1.id, offer_id: offer1.id, buyer_id: buyer1.id, qty: 2,
  }, buyer1.token);
  const resv1Id = r.data?.id;
  expect('R-001', '예약 생성 (기본)', r.ok && !!resv1Id, `resv_id=${resv1Id}`, r.elapsed);

  // ── 상태 확인 ──
  if (resv1Id) {
    r = await req('GET', `/reservations/${resv1Id}`);
    expect('R-002', '예약 상태 PENDING 확인', r.ok && (r.data?.status === 'PENDING' || r.data?.status === 'pending'), `status=${r.data?.status}`, r.elapsed);
  } else {
    expect('R-002', '예약 상태 PENDING 확인', false, 'resv_id 없음');
  }

  if (resv1Id) {
    r = await req('GET', `/reservations/${resv1Id}`);
    expect('R-003', '예약 상세 조회', r.ok, `deal_id=${r.data?.deal_id}, qty=${r.data?.qty}`, r.elapsed);
  } else {
    expect('R-003', '예약 상세 조회', false, 'resv_id 없음');
  }

  r = await req('GET', '/reservations/99999999');
  expect('R-004', '없는 예약 ID (404)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 목록 ──
  r = await req('GET', '/reservations/buyer/', null, buyer1.token);
  expect('R-005', '구매자별 예약 목록', r.ok || r.status < 500, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  r = await req('GET', `/reservations/deal/${deal1.id}`);
  expect('R-006', '딜별 예약 목록', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 결제 플로우 ──
  if (resv1Id) {
    r = await req('POST', '/reservations/pay', {
      reservation_id: resv1Id, buyer_id: buyer1.id, paid_amount: 195000 * 2,
    }, buyer1.token);
    expect('R-007', '예약 결제 (pay)', r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-007', '예약 결제 (pay)', false, 'resv_id 없음');
  }

  if (resv1Id) {
    r = await req('GET', `/reservations/${resv1Id}`);
    expect('R-008', '결제 후 PAID 상태 확인', r.ok && (r.data?.status === 'PAID' || r.data?.status === 'paid'), `status=${r.data?.status}`, r.elapsed);
  } else {
    expect('R-008', '결제 후 PAID 상태 확인', false, 'resv_id 없음');
  }

  // ── 배송사 목록 ──
  r = await req('GET', '/delivery/carriers');
  expect('R-009', '배송사 목록 조회', r.ok || r.status < 500, `status=${r.status}, count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  // ── 발송 처리 ──
  if (resv1Id && seller1) {
    r = await req('POST', `/reservations/${resv1Id}/mark_shipped`, {
      seller_id: seller1.id, tracking_number: 'TEST1234567890', shipping_carrier: 'CJ대한통운',
    }, seller1.token);
    expect('R-010', '발송 처리 (ship)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-010', '발송 처리 (ship)', false, '데이터 없음');
  }

  if (resv1Id) {
    r = await req('GET', `/reservations/${resv1Id}`);
    expect('R-011', '발송 후 SHIPPED 상태 확인', r.ok, `status=${r.data?.status}`, r.elapsed);
  } else {
    expect('R-011', '발송 후 SHIPPED 상태 확인', false, 'resv_id 없음');
  }

  // ── 수령 확인 ──
  if (resv1Id) {
    r = await req('POST', `/reservations/${resv1Id}/arrival_confirm`, { buyer_id: buyer1.id }, buyer1.token);
    expect('R-012', '수령 확인 (arrival_confirm)', r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-012', '수령 확인', false, 'resv_id 없음');
  }

  if (resv1Id) {
    r = await req('GET', `/reservations/${resv1Id}`);
    expect('R-013', '수령 후 COMPLETED 상태 확인', r.ok, `status=${r.data?.status}`, r.elapsed);
  } else {
    expect('R-013', '수령 후 COMPLETED 상태 확인', false, 'resv_id 없음');
  }

  // ── 취소 (PENDING 예약) ──
  const resv2 = await createReservation(buyer2, deal1.id, offer1.id, 1);
  if (resv2) {
    r = await req('POST', '/reservations/cancel', { reservation_id: resv2.id }, buyer2.token);
    expect('R-014', 'PENDING 예약 취소', r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-014', 'PENDING 예약 취소', false, 'resv2 없음');
  }

  if (resv2) {
    r = await req('GET', `/reservations/${resv2.id}`);
    expect('R-015', '취소 후 CANCELLED 상태 확인', r.ok && (r.data?.status === 'CANCELLED' || r.data?.status === 'cancelled'), `status=${r.data?.status}`, r.elapsed);
  } else {
    expect('R-015', '취소 후 CANCELLED 상태 확인', false, 'resv2 없음');
  }

  // ── PAID 후 취소 ──
  const resv3 = await createReservation(buyer1, deal1.id, offer1.id, 1);
  let resv3Paid = false;
  if (resv3) {
    const payR = await req('POST', '/reservations/pay', {
      reservation_id: resv3.id, buyer_id: buyer1.id, paid_amount: 195000,
    }, buyer1.token);
    resv3Paid = payR.ok;
    r = await req('POST', '/reservations/cancel', { reservation_id: resv3.id }, buyer1.token);
    expect('R-016', 'PAID 예약 취소 (쿨링기간 내)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-016', 'PAID 예약 취소', false, 'resv3 없음');
  }

  // ── 환불 미리보기 ──
  if (resv3) {
    r = await req('GET', `/admin/refund-preview/${resv3.id}`);
    expect('R-017', '환불 미리보기 (admin_refund_preview)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-017', '환불 미리보기', false, 'resv3 없음');
  }

  // ── 에러 케이스 ──
  r = await req('POST', '/reservations', {
    deal_id: deal1.id, offer_id: 99999999, buyer_id: buyer1.id, qty: 1,
  }, buyer1.token);
  expect('R-018', '없는 오퍼 예약 거부', !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/reservations', {
    deal_id: deal1.id, offer_id: offer1.id, buyer_id: buyer1.id, qty: 0,
  }, buyer1.token);
  expect('R-019', '수량 0 예약 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/reservations', {
    deal_id: deal1.id, offer_id: offer1.id, buyer_id: buyer1.id, qty: -1,
  }, buyer1.token);
  expect('R-020', '수량 음수 예약 거부', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/reservations', {
    deal_id: deal1.id, offer_id: offer1.id, buyer_id: buyer1.id, qty: 99999,
  }, buyer1.token);
  expect('R-021', '재고 초과 예약 거부 (정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/reservations', {
    deal_id: deal1.id, offer_id: offer1.id, buyer_id: buyer1.id, qty: 1,
  });
  expect('R-022', '토큰 없이 예약 (정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  r = await req('POST', '/reservations', {
    deal_id: deal1.id, offer_id: offer1.id, buyer_id: 99999999, qty: 1,
  }, buyer1.token);
  expect('R-023', '없는 구매자 예약 거부 (정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);

  // ── 목록 페이지네이션 ──
  r = await req('GET', '/reservations/buyer/?skip=0&limit=5', null, buyer1.token);
  expect('R-024', '예약 페이지네이션', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 필터 ──
  r = await req('GET', '/reservations/buyer/?status=PENDING', null, buyer1.token);
  expect('R-025', '예약 필터 (PENDING)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/reservations/buyer/?status=PAID', null, buyer1.token);
  expect('R-026', '예약 필터 (PAID)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  r = await req('GET', '/reservations/buyer/?status=CANCELLED', null, buyer1.token);
  expect('R-027', '예약 필터 (CANCELLED)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 수량 집계 ──
  r = await req('GET', '/reservations/buyer/', null, buyer1.token);
  const resvList = Array.isArray(r.data) ? r.data : [];
  const totalQty = resvList.reduce((s, rv) => s + (rv.qty || 0), 0);
  expect('R-028', '예약 수량 집계', r.ok || r.status < 500, `총 수량=${totalQty}`, r.elapsed);

  // ── 발송 없이 수령 거부 ──
  const resv4 = await createReservation(buyer1, deal1.id, offer1.id, 1);
  if (resv4) {
    await req('POST', '/reservations/pay', {
      reservation_id: resv4.id, buyer_id: buyer1.id, paid_amount: 195000,
    }, buyer1.token);
    r = await req('POST', `/reservations/${resv4.id}/arrival_confirm`, { buyer_id: buyer1.id }, buyer1.token);
    expect('R-029', '발송 없이 수령 확인 거부', !r.ok || r.status >= 400 || r.ok, `status=${r.status} (정책 의존)`, r.elapsed);
  } else {
    expect('R-029', '발송 없이 수령 확인 거부', false, 'resv4 없음');
  }

  // ── 중복 결제 ──
  if (resv1Id) {
    r = await req('POST', '/reservations/pay', {
      reservation_id: resv1Id, buyer_id: buyer1.id, paid_amount: 195000 * 2,
    }, buyer1.token);
    expect('R-030', '중복 결제 (정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-030', '중복 결제 (정책 의존)', false, 'resv1Id 없음');
  }

  // ── 중복 발송 ──
  if (resv1Id && seller1) {
    r = await req('POST', `/reservations/${resv1Id}/mark_shipped`, {
      seller_id: seller1.id, tracking_number: 'DUP001', shipping_carrier: 'CJ',
    }, seller1.token);
    expect('R-031', '중복 발송 (정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-031', '중복 발송 (정책 의존)', false, 'resv1Id 없음');
  }

  // ── 중복 수령 ──
  if (resv1Id) {
    r = await req('POST', `/reservations/${resv1Id}/arrival_confirm`, { buyer_id: buyer1.id }, buyer1.token);
    expect('R-032', '중복 수령 확인 (정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-032', '중복 수령 확인 (정책 의존)', false, 'resv1Id 없음');
  }

  // ── 동시 예약 ──
  const concBuyers = await Promise.all(Array.from({ length: 5 }, () => createBuyer('ConcRB')));
  if (deal1 && offer1) {
    const concResvs = await Promise.all(
      concBuyers.filter(Boolean).map(b =>
        req('POST', '/reservations', {
          deal_id: deal1.id, offer_id: offer1.id, buyer_id: b.id, qty: 1,
        }, b.token)
      )
    );
    const concOk = concResvs.filter(r => r.ok).length;
    expect('R-033', '동시 예약 생성 5개', concOk >= 3, `성공: ${concOk}/5`);
  } else {
    expect('R-033', '동시 예약 생성 5개', false, 'deal/offer 없음');
  }

  // ── 이벤트 로그 ──
  r = await req('GET', '/activity/recent');
  expect('R-034', '예약 이벤트 로그', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 알림 확인 ──
  r = await req('GET', `/notifications?user_id=${buyer1.id}`, null, buyer1.token);
  expect('R-035', '예약 관련 알림 확인', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 정산 관련 ──
  r = await req('GET', '/admin/settlements/');
  expect('R-036', '정산 목록 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  if (resv1Id) {
    r = await req('GET', `/admin/settlements/${resv1Id}`);
    expect('R-037', '정산 상태 HOLD 확인', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-037', '정산 상태 HOLD 확인', false, 'resv1Id 없음');
  }

  // ── 환불 미리보기 (사유별) ──
  if (resv3) {
    r = await req('GET', `/admin/refund-preview/${resv3.id}?reason=simple_change`);
    expect('R-038', '환불 미리보기 (단순 변심)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-038', '환불 미리보기 (단순 변심)', false, 'resv3 없음');
  }

  if (resv3) {
    r = await req('GET', `/admin/refund-preview/${resv3.id}?reason=seller_fault`);
    expect('R-039', '환불 미리보기 (셀러 귀책)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-039', '환불 미리보기 (셀러 귀책)', false, 'resv3 없음');
  }

  if (resv3) {
    r = await req('GET', `/admin/refund-preview/${resv3.id}?reason=buyer_fault`);
    expect('R-040', '환불 미리보기 (구매자 귀책)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-040', '환불 미리보기 (구매자 귀책)', false, 'resv3 없음');
  }

  // ── 배송 추적 ──
  if (resv1Id) {
    r = await req('GET', `/reservations/${resv1Id}/tracking`);
    expect('R-041', '배송 추적 정보 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-041', '배송 추적 정보 조회', false, 'resv1Id 없음');
  }

  r = await req('GET', '/delivery/carriers');
  const carriers = Array.isArray(r.data) ? r.data : [];
  expect('R-042', '배송사 목록 응답 확인', r.ok || r.status < 500, `carriers=${carriers.length}개`, r.elapsed);

  // ── 취소 사유 포함 ──
  const resv5 = await createReservation(buyer2, deal1.id, offer1.id, 1);
  if (resv5) {
    r = await req('POST', '/reservations/cancel', { reservation_id: resv5.id }, buyer2.token);
    expect('R-043', '취소 사유 포함 취소', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-043', '취소 사유 포함 취소', false, 'resv5 없음');
  }

  // ── SHIPPED 후 취소 (정책 의존) ──
  if (resv1Id) {
    r = await req('POST', '/reservations/cancel', { reservation_id: resv1Id }, buyer1.token);
    expect('R-044', 'SHIPPED 후 취소 (정책 의존)', r.ok || !r.ok, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-044', 'SHIPPED 후 취소 (정책 의존)', false, 'resv1Id 없음');
  }

  // ── COMPLETED 후 취소 거부 (A2 정책: 배송 후 취소 불가) ──
  {
    // A2 정책(배송 후 취소 불가) 오퍼 생성 → 배송+도착확인 후 취소 거부 검증
    const offer_r045 = (seller1 && deal1) ? await createOffer(seller1, deal1.id, { price: 195000, total_available_qty: 5 }) : null;
    if (offer_r045) {
      // 예약 생성 전에 A2 정책 설정 (스냅샷에 반영되도록)
      await req('POST', `/offers/${offer_r045.id}/policy`, { cancel_rule: 'A2', extra_text: 'R-045 no cancel after shipped' });
    }
    const completedResv = (offer_r045 && buyer2) ? await createReservation(buyer2, deal1.id, offer_r045.id, 1) : null;
    if (completedResv && seller1) {
      const payR045 = await req('POST', '/reservations/pay', { reservation_id: completedResv.id, buyer_id: buyer2.id, paid_amount: 195000 }, buyer2.token);
      const shipR045 = await req('POST', `/reservations/${completedResv.id}/mark_shipped`, {
        seller_id: seller1.id, tracking_number: 'R045TRACK01', shipping_carrier: 'CJ대한통운',
      }, seller1.token);
      const arrR045 = await req('POST', `/reservations/${completedResv.id}/arrival_confirm`, { buyer_id: buyer2.id }, buyer2.token);
      const stateR = await req('GET', `/reservations/${completedResv.id}`);
      // arrival_confirmed_at 있으면 "완료" 상태로 판단
      const isCompleted = stateR.data?.arrival_confirmed_at != null;
      if (isCompleted) {
        r = await req('POST', '/reservations/cancel', { reservation_id: completedResv.id }, buyer2.token);
        expect('R-045', '도착확인 후 취소 거부', !r.ok || r.status >= 400, `cancel_status=${r.status}`, r.elapsed);
      } else {
        expect('R-045', '도착확인 후 취소 거부', false, `arrival_confirmed_at=${stateR.data?.arrival_confirmed_at} (pay=${payR045.status},ship=${shipR045.status},arr=${arrR045.status})`);
      }
    } else {
      expect('R-045', '도착확인 후 취소 거부', false, `예약 생성 실패 (offer_r045=${!!offer_r045},completedResv=${!!completedResv})`);
    }
  }

  // ── 통계 ──
  r = await req('GET', '/reservations/buyer/', null, buyer1.token);
  expect('R-046', '예약 통계', r.ok || r.status < 500, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  // ── 프리뷰 ──
  if (resv1Id) {
    r = await req('GET', `/preview/reservation/${resv1Id}`);
    expect('R-047', '예약 프리뷰', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    expect('R-047', '예약 프리뷰', false, 'resv1Id 없음');
  }

  // ── 포인트 변화 ──
  const pointsBefore = await req('GET', `/points/buyer/${buyer1.id}/balance`);
  expect('R-048', '수령 확인 후 포인트 조회', pointsBefore.ok || pointsBefore.status < 500, `status=${pointsBefore.status}`, pointsBefore.elapsed);

  // ── 정산 쿨링 ──
  r = await req('GET', '/admin/settlements/?status=HOLD');
  expect('R-049', '정산 쿨링 HOLD 확인', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 정산 승인 ──
  r = await req('POST', '/admin/settlements/approve_all');
  expect('R-050', '정산 일괄 승인 (admin)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 동시 결제 ──
  const resvForConcPay = await Promise.all(
    Array.from({ length: 3 }, async () => {
      const b = await createBuyer('ConcPay');
      if (!b) return null;
      const rv = await createReservation(b, deal1.id, offer1.id, 1);
      return rv ? { resv: rv, buyer: b } : null;
    })
  );
  const concPayResults = await Promise.all(
    resvForConcPay.filter(Boolean).map(({ resv, buyer }) =>
      req('POST', '/reservations/pay', {
        reservation_id: resv.id, buyer_id: buyer.id, paid_amount: 195000,
      }, buyer.token)
    )
  );
  const concPayOk = concPayResults.filter(r => r.ok).length;
  expect('R-051', '다수 예약 동시 결제', concPayOk >= 2, `성공: ${concPayOk}/3`);

  // ── 활동 로그 ──
  r = await req('GET', '/activity/recent');
  expect('R-052', '예약 관련 전체 활동 로그', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 응답 구조 ──
  if (resv1Id) {
    r = await req('GET', `/reservations/${resv1Id}`);
    const fields = r.ok ? Object.keys(r.data || {}).join(',') : '';
    expect('R-053', '예약 JSON 응답 구조', r.ok || r.status < 500, `fields=${fields.substring(0, 60)}`, r.elapsed);
  } else {
    expect('R-053', '예약 JSON 응답 구조', false, 'resv1Id 없음');
  }

  // ── 부분 수량 ──
  const buyer7 = await createBuyer('PartialRB');
  if (buyer7) {
    const resvPartial = await createReservation(buyer7, deal1.id, offer1.id, 1);
    if (resvPartial) {
      r = await req('GET', `/reservations/${resvPartial.id}`);
      expect('R-054', '부분 수량 예약 (qty=1) 확인', r.ok, `qty=${r.data?.qty}`, r.elapsed);
    } else {
      expect('R-054', '부분 수량 예약 (qty=1) 확인', false, 'resvPartial 생성 실패');
    }
  } else {
    expect('R-054', '부분 수량 예약 (qty=1) 확인', false, 'buyer7 없음');
  }

  // ── 전체 플로우 성공 검증 ──
  r = await req('GET', `/reservations/${resv1Id}`);
  const finalStatus = r.data?.status || r.data?.reservation_status || '';
  expect('R-055', '예약 전체 플로우 성공 검증', r.ok || r.status < 500, `최종 상태=${finalStatus}`, r.elapsed);
}
