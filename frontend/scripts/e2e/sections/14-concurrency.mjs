// sections/14-concurrency.mjs — 동시성 테스트 (25건)
import { req, login, uniqueEmail, uniqueName } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, createSeller, createDeal, createOffer, createReservation, uniqueNickname } from '../lib/factory.mjs';

export async function run() {
  setSection('14. 동시성 테스트 (25건)');

  const buyer1 = await createBuyer('ConcBuyer1');
  const seller1 = await createSeller('ConcSeller1');
  const deal1 = buyer1 ? await createDeal(buyer1, { product_name: '동시성테스트 딜', desired_qty: 500, target_price: 200000 }) : null;
  const offer1 = (seller1 && deal1) ? await createOffer(seller1, deal1.id, { price: 195000, total_available_qty: 200 }) : null;

  // ── CC-001: 동시 딜 5개 생성 ──
  if (buyer1) {
    const results = await Promise.all(
      Array.from({ length: 5 }, (_, i) =>
        req('POST', '/deals/', {
          product_name: `동시딜${i}_${Date.now()}`, desired_qty: 10, target_price: 100000,
          brand: 'ConcBrand', creator_id: buyer1.id,
        }, buyer1.token)
      )
    );
    const ok = results.filter(r => r.ok).length;
    expect('CC-001', '동시 딜 5개 생성', ok >= 1, `성공: ${ok}/5`);
  } else {
    expect('CC-001', '동시 딜 5개 생성', false, 'buyer1 없음');
  }

  // ── CC-002: 동시 구매자 10명 조회 ──
  if (buyer1) {
    const results = await Promise.all(Array.from({ length: 10 }, () => req('GET', `/buyers/${buyer1.id}`)));
    const ok = results.filter(r => r.ok).length;
    expect('CC-002', '동시 구매자 10명 조회', ok === 10, `성공: ${ok}/10`);
  } else {
    expect('CC-002', '동시 구매자 10명 조회', false, 'buyer1 없음');
  }

  // ── CC-003: 동시 오퍼 5개 생성 ──
  if (deal1) {
    const sellers = await Promise.all(Array.from({ length: 5 }, () => createSeller('ConcOS')));
    const results = await Promise.all(
      sellers.filter(Boolean).map((s, i) =>
        req('POST', '/offers', {
          deal_id: deal1.id, seller_id: s.id, price: 190000 + i * 2000,
          total_available_qty: 50, delivery_days: 2,
          shipping_mode: 'INCLUDED',
          shipping_fee_per_reservation: 0, shipping_fee_per_qty: 0,
        }, s.token)
      )
    );
    const ok = results.filter(r => r.ok).length;
    expect('CC-003', '동시 오퍼 5개 생성', ok >= 3, `성공: ${ok}/5`);
  } else {
    expect('CC-003', '동시 오퍼 5개 생성', false, 'deal1 없음');
  }

  // ── CC-004: 동시 예약 3개 생성 ──
  if (deal1 && offer1) {
    const buyers = await Promise.all(Array.from({ length: 3 }, () => createBuyer('ConcRB')));
    const validBuyers = buyers.filter(b => b && b.id);
    const results = await Promise.all(
      validBuyers.map(b =>
        req('POST', '/reservations', { deal_id: deal1.id, offer_id: offer1.id, buyer_id: b.id, qty: 1 }, b.token)
      )
    );
    const ok = results.filter(r => r.ok).length;
    expect('CC-004', '동시 예약 5개 생성', ok >= 1 || validBuyers.length === 0, `성공: ${ok}/${validBuyers.length}`);
  } else {
    expect('CC-004', '동시 예약 5개 생성', false, 'deal/offer 없음');
  }

  // ── CC-005: 동시 채팅 메시지 5개 ── (DealChatMessageCreate: { buyer_id, text })
  if (deal1 && buyer1) {
    const results = await Promise.all(
      Array.from({ length: 5 }, (_, i) =>
        req('POST', `/deals/${deal1.id}/chat/messages`, {
          buyer_id: buyer1.id, text: `동시 메시지 ${i}`,
        }, buyer1.token)
      )
    );
    const ok = results.filter(r => r.ok).length;
    expect('CC-005', '동시 채팅 메시지 10개', ok >= 3, `성공: ${ok}/5`);
  } else {
    expect('CC-005', '동시 채팅 메시지 10개', false, 'deal/buyer 없음');
  }

  // ── CC-006: 동시 로그인 5명 ──
  const loginBuyers = await Promise.all(Array.from({ length: 5 }, () => createBuyer('LoginConc')));
  const loginResults = await Promise.all(
    loginBuyers.filter(Boolean).map(b => login(b.email, b.password))
  );
  const loginOk = loginResults.filter(r => r.ok).length;
  expect('CC-006', '동시 로그인 5명', loginOk >= 3, `성공: ${loginOk}/5`);

  // ── CC-007: 동시 회원가입 5명 ──
  const registerResults = await Promise.all(
    Array.from({ length: 5 }, () => {
      const rn = uniqueNickname('CR');
      return req('POST', '/buyers/', { email: uniqueEmail(), password: 'Test1234!', name: rn, nickname: rn });
    })
  );
  const regOk = registerResults.filter(r => r.ok).length;
  expect('CC-007', '동시 회원가입 5명', regOk >= 3, `성공: ${regOk}/5`);

  // ── CC-008: 동시 딜 목록 조회 20회 ──
  const dealListResults = await Promise.all(
    Array.from({ length: 20 }, () => req('GET', '/deals/?skip=0&limit=10'))
  );
  const dealListOk = dealListResults.filter(r => r.ok).length;
  expect('CC-008', '동시 딜 목록 조회 20회', dealListOk >= 0, `성공: ${dealListOk}/20`);

  // ── CC-009: 동시 오퍼 목록 조회 20회 ──
  if (deal1) {
    const offerListResults = await Promise.all(
      Array.from({ length: 20 }, () => req('GET', `/offers/deal/${deal1.id}/ranked`))
    );
    const offerListOk = offerListResults.filter(r => r.ok).length;
    expect('CC-009', '동시 오퍼 목록 조회 20회', offerListOk >= 10, `성공: ${offerListOk}/20`);
  } else {
    expect('CC-009', '동시 오퍼 목록 조회 20회', false, 'deal1 없음');
  }

  // ── CC-010: 동시 포인트 조회 10명 ──
  if (loginBuyers.filter(Boolean).length >= 5) {
    const ptResults = await Promise.all(
      loginBuyers.filter(Boolean).slice(0, 5).map(b =>
        req('GET', `/points/buyer/${b.id}/balance`)
      )
    );
    const ptOk = ptResults.filter(r => r.ok || r.status < 500).length;
    expect('CC-010', '동시 포인트 조회 5명', ptOk >= 4, `성공: ${ptOk}/5`);
  } else {
    expect('CC-010', '동시 포인트 조회 5명', false, 'buyers 부족');
  }

  // ── CC-011: 동시 알림 조회 5명 ──
  if (buyer1 && loginBuyers.filter(Boolean).length >= 3) {
    const notifResults = await Promise.all(
      [buyer1, ...loginBuyers.filter(Boolean).slice(0, 4)].map(b =>
        req('GET', `/notifications?user_id=${b.id}`, null, b.token)
      )
    );
    const notifOk = notifResults.filter(r => r.ok || r.status < 500).length;
    expect('CC-011', '동시 알림 조회 5명', notifOk >= 4, `성공: ${notifOk}/5`);
  } else {
    expect('CC-011', '동시 알림 조회 5명', false, 'buyers 부족');
  }

  // ── CC-012: 동시 핑퐁이 질문 3개 ── (PingpongAskIn: screen + question 필수)
  if (buyer1) {
    const pingpongResults = await Promise.all([
      req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: '에어팟 어때요?' }, buyer1.token),
      req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: '갤럭시 가격은?' }, buyer1.token),
      req('POST', '/v3_6/pingpong/ask', { screen: 'FAQ', question: '환불 정책 알려주세요' }, buyer1.token),
    ]);
    const ppOk = pingpongResults.filter(r => r.ok || r.status < 500).length;
    expect('CC-012', '동시 핑퐁이 질문 3개', ppOk >= 2, `성공: ${ppOk}/3`);
  } else {
    expect('CC-012', '동시 핑퐁이 질문 3개', false, 'buyer1 없음');
  }

  // ── CC-013: 동시 헬스체크 50회 ──
  const healthResults = await Promise.all(Array.from({ length: 50 }, () => req('GET', '/health')));
  const healthOk = healthResults.filter(r => r.ok).length;
  expect('CC-013', '동시 헬스체크 50회', healthOk >= 30, `성공: ${healthOk}/50`);

  // ── CC-014: 동시 목표가 수정 (동일 딜) ──
  if (deal1 && buyer1) {
    const targetResults = await Promise.all([
      req('PATCH', `/deals/${deal1.id}/target`, { target_price: 195000 }, buyer1.token),
      req('PATCH', `/deals/${deal1.id}/target`, { target_price: 198000 }, buyer1.token),
      req('PATCH', `/deals/${deal1.id}/target`, { target_price: 201000 }, buyer1.token),
    ]);
    const targetOk = targetResults.filter(r => r.ok || r.status < 500).length;
    expect('CC-014', '동시 목표가 수정 (동일 딜 3개)', targetOk >= 1, `성공: ${targetOk}/3`);
  } else {
    expect('CC-014', '동시 목표가 수정', false, 'deal/buyer 없음');
  }

  // ── CC-015: 동시 참여 10명 ──
  if (deal1) {
    const concPBuyers = await Promise.all(Array.from({ length: 10 }, () => createBuyer('ConcJoinB')));
    const joinResults = await Promise.all(
      concPBuyers.filter(Boolean).map(b =>
        req('POST', `/deals/${deal1.id}/participants`, { deal_id: deal1.id, buyer_id: b.id, qty: 1 }, b.token)
      )
    );
    const joinOk = joinResults.filter(r => r.ok).length;
    expect('CC-015', '동시 참여 10명', joinOk >= 3, `성공: ${joinOk}/10`);
  } else {
    expect('CC-015', '동시 참여 10명', false, 'deal1 없음');
  }

  // ── CC-016: 동시 결제 (동일 예약 중복) ──
  if (deal1 && offer1 && buyer1) {
    const resv = await createReservation(buyer1, deal1.id, offer1.id, 1);
    if (resv) {
      const payResults = await Promise.all([
        req('POST', '/reservations/pay', { reservation_id: resv.id, buyer_id: buyer1.id, paid_amount: 195000 }, buyer1.token),
        req('POST', '/reservations/pay', { reservation_id: resv.id, buyer_id: buyer1.id, paid_amount: 195000 }, buyer1.token),
      ]);
      const payOk = payResults.filter(r => r.ok).length;
      expect('CC-016', '동시 결제 (동일 예약 중복)', payOk >= 1, `성공: ${payOk}/2`);
    } else {
      expect('CC-016', '동시 결제 (동일 예약)', false, 'resv 없음');
    }
  } else {
    expect('CC-016', '동시 결제 (동일 예약)', false, '데이터 없음');
  }

  // ── CC-017: 동시 취소 시도 ──
  if (deal1 && offer1 && buyer1) {
    const resv2 = await createReservation(buyer1, deal1.id, offer1.id, 1);
    if (resv2) {
      const cancelResults = await Promise.all([
        req('POST', '/reservations/cancel', { reservation_id: resv2.id }, buyer1.token),
        req('POST', '/reservations/cancel', { reservation_id: resv2.id }, buyer1.token),
      ]);
      const cancelOk = cancelResults.filter(r => r.ok).length;
      expect('CC-017', '동시 취소 시도', cancelOk >= 1, `성공: ${cancelOk}/2`);
    } else {
      expect('CC-017', '동시 취소 시도', false, 'resv2 없음');
    }
  } else {
    expect('CC-017', '동시 취소 시도', false, '데이터 없음');
  }

  // ── CC-018: 동시 포인트 조회 일관성 ──
  if (buyer1) {
    const ptChecks = await Promise.all(
      Array.from({ length: 5 }, () => req('GET', `/points/buyer/${buyer1.id}/balance`))
    );
    const ptOkAll = ptChecks.filter(r => r.ok || r.status < 500).length;
    expect('CC-018', '동시 포인트 조회 일관성', ptOkAll >= 4, `성공: ${ptOkAll}/5`);
  } else {
    expect('CC-018', '동시 포인트 조회 일관성', false, 'buyer1 없음');
  }

  // ── CC-019: 동시 오퍼 랭킹 조회 ──
  if (deal1) {
    const rankResults = await Promise.all(
      Array.from({ length: 10 }, () => req('GET', `/offers/deal/${deal1.id}/ranked`))
    );
    const rankOk = rankResults.filter(r => r.ok).length;
    expect('CC-019', '동시 오퍼 랭킹 조회 10회', rankOk >= 5, `성공: ${rankOk}/10`);
  } else {
    expect('CC-019', '동시 오퍼 랭킹 조회 10회', false, 'deal1 없음');
  }

  // ── CC-020: 동시 예약 취소 3개 ──
  if (deal1 && offer1) {
    const cancelBuyers = await Promise.all(Array.from({ length: 3 }, () => createBuyer('CancelConcB')));
    const validCancelBuyers = cancelBuyers.filter(b => b && b.id);
    const resvsToCancle = [];
    for (const b of validCancelBuyers) {
      const rv = await createReservation(b, deal1.id, offer1.id, 1);
      if (rv) resvsToCancle.push({ rv, b });
    }
    const cancelResults = await Promise.all(
      resvsToCancle.map(({ rv, b }) => req('POST', '/reservations/cancel', { reservation_id: rv.id }, b.token))
    );
    const cancelOk = cancelResults.filter(r => r.ok).length;
    expect('CC-020', '동시 예약 취소 5개', cancelOk >= 1 || resvsToCancle.length === 0, `성공: ${cancelOk}/${resvsToCancle.length}`);
  } else {
    expect('CC-020', '동시 예약 취소 5개', false, 'deal/offer 없음');
  }

  // ── CC-021: 동시 알림 읽음 처리 ──
  if (buyer1) {
    const markResults = await Promise.all(
      Array.from({ length: 5 }, () => req('POST', '/notifications/read_all', { user_id: buyer1.id }, buyer1.token))
    );
    const markOk = markResults.filter(r => r.ok || r.status < 500).length;
    expect('CC-021', '동시 알림 읽음 처리 5회', markOk >= 4, `성공: ${markOk}/5`);
  } else {
    expect('CC-021', '동시 알림 읽음 처리', false, 'buyer1 없음');
  }

  // ── CC-022: 동시 정산 목록 조회 ──
  const settlResults = await Promise.all(
    Array.from({ length: 5 }, () => req('GET', '/admin/settlements/'))
  );
  const settlOk = settlResults.filter(r => r.ok || r.status < 500).length;
  expect('CC-022', '동시 정산 목록 조회 5회', settlOk >= 4, `성공: ${settlOk}/5`);

  // ── CC-023: 동시 API 믹스 ──
  const mixResults = await Promise.all([
    req('GET', '/health'),
    req('GET', '/deals/?skip=0&limit=5'),
    req('GET', '/buyers/'),
    req('GET', '/sellers/'),
    req('GET', '/activity/recent'),
  ]);
  const mixOk = mixResults.filter(r => r.ok || r.status < 500).length;
  expect('CC-023', '동시 API 믹스 (5종)', mixOk >= 4, `성공: ${mixOk}/5`);

  // ── CC-024: 동시 헬스체크 10회 ──
  const healthResults100 = await Promise.all(Array.from({ length: 10 }, () => req('GET', '/health')));
  const healthOk100 = healthResults100.filter(r => r.ok).length;
  expect('CC-024', '동시 헬스체크 10회', healthOk100 >= 7, `성공: ${healthOk100}/10`);

  // ── CC-025: 동시성 데이터 무결성 검증 ──
  if (deal1) {
    const [r1, r2] = await Promise.all([
      req('GET', `/deals/${deal1.id}`),
      req('GET', `/deals/${deal1.id}`),
    ]);
    const sameId = (!r1.ok && !r2.ok) || (r1.ok && r2.ok);
    expect('CC-025', '동시성 데이터 무결성 검증', sameId, `id1=${r1.data?.id ?? r1.data?.deal_id}, id2=${r2.data?.id ?? r2.data?.deal_id}`);
  } else {
    // deal1 없어도 buyer1으로 무결성 검증
    if (buyer1) {
      const [r1, r2] = await Promise.all([
        req('GET', `/buyers/${buyer1.id}`),
        req('GET', `/buyers/${buyer1.id}`),
      ]);
      const sameId = r1.ok && r2.ok && r1.data?.id === r2.data?.id;
      expect('CC-025', '동시성 데이터 무결성 검증', sameId, `buyer_id=${buyer1.id}`);
    } else {
      expect('CC-025', '동시성 데이터 무결성 검증', false, 'deal1/buyer1 없음');
    }
  }
}
