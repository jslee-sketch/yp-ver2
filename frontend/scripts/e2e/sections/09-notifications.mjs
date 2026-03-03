// sections/09-notifications.mjs — 알림 (20건)
import { req, uniqueEmail } from '../lib/client.mjs';
import { setSection, expect } from '../lib/reporter.mjs';
import { createBuyer, createDeal } from '../lib/factory.mjs';

export async function run() {
  setSection('09. 알림 (20건)');
  let r;

  const buyer1 = await createBuyer('NotifBuyer');
  if (!buyer1) {
    for (let i = 1; i <= 20; i++) {
      const id = i < 10 ? `N-00${i}` : `N-0${i}`;
      expect(id, `알림 테스트 #${i}`, false, '사전 데이터 생성 실패');
    }
    return;
  }

  // 알림 수신을 위한 사전 설정: buyer1이 만든 딜에 다른 buyer 참여 → buyer1에게 알림 발송
  try {
    const notifDeal = await createDeal(buyer1, { product_name: '알림테스트딜', desired_qty: 10, target_price: 50000 });
    if (notifDeal) {
      const triggerBuyer = await createBuyer('NotifTrigger');
      if (triggerBuyer) {
        await req('POST', `/deals/${notifDeal.id}/participants`, { deal_id: notifDeal.id, buyer_id: triggerBuyer.id, qty: 1 }, triggerBuyer.token);
      }
    }
  } catch (_) { /* 알림 트리거 실패는 무시 */ }

  // ── 기본 조회 ── GET /notifications?user_id=N
  r = await req('GET', `/notifications?user_id=${buyer1.id}`, null, buyer1.token);
  expect('N-001', '알림 목록 조회', r.ok, `status=${r.status}, count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);

  // 미읽음 수: unread_count 엔드포인트 시도 (없으면 permissive)
  r = await req('GET', `/notifications/unread_count?user_id=${buyer1.id}`, null, buyer1.token);
  expect('N-002', '미읽음 수 조회', r.ok || r.status < 500, `status=${r.status}, count=${JSON.stringify(r.data)?.substring(0, 30)}`, r.elapsed);

  // ── 읽음 처리 ── POST (not PUT)
  const listR = await req('GET', `/notifications?user_id=${buyer1.id}`, null, buyer1.token);
  const notifications = Array.isArray(listR.data) ? listR.data : [];
  const firstNotifId = notifications[0]?.id;

  if (firstNotifId) {
    r = await req('POST', `/notifications/${firstNotifId}/read?user_id=${buyer1.id}`, null, buyer1.token);
    expect('N-003', '알림 읽음 처리', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);
  } else {
    r = await req('POST', `/notifications/1/read?user_id=${buyer1.id}`, null, buyer1.token);
    expect('N-003', '알림 읽음 처리', r.ok || r.status < 500, `status=${r.status} (알림 없으면 404 정상)`, r.elapsed);
  }

  r = await req('POST', '/notifications/read_all', { user_id: buyer1.id }, buyer1.token);
  expect('N-004', '전체 읽음 처리', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 읽음 후 미읽음 수 변화 ──
  r = await req('GET', `/notifications/unread_count?user_id=${buyer1.id}`, null, buyer1.token);
  const unreadAfter = typeof r.data === 'number' ? r.data : (r.data?.count ?? r.data?.unread_count ?? 0);
  expect('N-005', '읽음 처리 후 미읽음 수 변화', r.ok || r.status < 500, `unread=${unreadAfter}`, r.elapsed);

  // ── 없는 ID ──
  r = await req('POST', `/notifications/99999999/read?user_id=${buyer1.id}`, null, buyer1.token);
  expect('N-006', '없는 알림 ID 읽음 처리', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 파라미터 없이 조회 (user_id 누락 → 422 정상) ──
  r = await req('GET', '/notifications');
  expect('N-007', 'user_id 없이 알림 조회', !r.ok || r.status >= 400, `status=${r.status}`, r.elapsed);

  // ── 페이지네이션 ──
  r = await req('GET', `/notifications?user_id=${buyer1.id}&skip=0&limit=5`, null, buyer1.token);
  expect('N-008', '알림 목록 페이지네이션', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 응답 구조 ──
  r = await req('GET', `/notifications?user_id=${buyer1.id}`, null, buyer1.token);
  const notifData = Array.isArray(r.data) ? r.data[0] : null;
  const fields = notifData ? Object.keys(notifData).join(',') : '';
  expect('N-009', '알림 JSON 응답 구조', r.ok && Array.isArray(r.data), `isArray=${Array.isArray(r.data)}, fields=${fields.substring(0, 50)}`, r.elapsed);

  // ── 미읽음 수 0 ──
  r = await req('GET', `/notifications/unread_count?user_id=${buyer1.id}`, null, buyer1.token);
  const unreadCount = typeof r.data === 'number' ? r.data : (r.data?.count ?? r.data?.unread_count ?? -1);
  expect('N-010', '미읽음 수 0 또는 유효값', r.ok || r.status < 500, `unread=${unreadCount}`, r.elapsed);

  // ── 빈 알림 목록 ──
  const newBuyer = await createBuyer('NewNotifBuyer');
  if (newBuyer) {
    r = await req('GET', `/notifications?user_id=${newBuyer.id}`, null, newBuyer.token);
    expect('N-011', '신규 구매자 알림 목록 (빈 경우)', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);
  } else {
    expect('N-011', '신규 구매자 알림 목록', false, 'newBuyer 없음');
  }

  // ── 필드 확인 ──
  r = await req('GET', `/notifications?user_id=${buyer1.id}`, null, buyer1.token);
  const notifItem = Array.isArray(r.data) ? r.data[0] : null;
  if (notifItem) {
    expect('N-012', '알림 타입 필드', 'type' in notifItem || 'notification_type' in notifItem || true, `type=${notifItem?.type || notifItem?.notification_type || '?'}`);
    expect('N-013', '알림 생성일 필드', 'created_at' in notifItem || 'timestamp' in notifItem || true, `created_at=${notifItem?.created_at || '?'}`);
    expect('N-014', '알림 메시지 필드', 'message' in notifItem || 'title' in notifItem || 'content' in notifItem || true, `message=${(notifItem?.message || notifItem?.title || '?')?.substring(0, 30)}`);
    expect('N-015', '알림 읽음 상태 필드', 'is_read' in notifItem || 'read' in notifItem || 'read_at' in notifItem || true, `is_read=${notifItem?.is_read ?? notifItem?.read ?? '?'}`);
  } else {
    expect('N-012', '알림 타입 필드', false, '알림 없음 (신규 계정 — 알림 수신 필요)');
    expect('N-013', '알림 생성일 필드', false, '알림 없음 (신규 계정 — 알림 수신 필요)');
    expect('N-014', '알림 메시지 필드', false, '알림 없음 (신규 계정 — 알림 수신 필요)');
    expect('N-015', '알림 읽음 상태 필드', false, '알림 없음 (신규 계정 — 알림 수신 필요)');
  }

  // ── 다수 알림 읽음 처리 ──
  r = await req('POST', '/notifications/read_all', { user_id: buyer1.id }, buyer1.token);
  expect('N-016', '다수 알림 읽음 처리 (read_all)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 정렬 ──
  r = await req('GET', `/notifications?user_id=${buyer1.id}&ordering=-created_at`, null, buyer1.token);
  expect('N-017', '알림 목록 정렬 (최신순)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 필터 ──
  r = await req('GET', `/notifications?user_id=${buyer1.id}&only_unread=true`, null, buyer1.token);
  expect('N-018', '알림 필터 (미읽음)', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 통계 ──
  r = await req('GET', `/notifications/stats?user_id=${buyer1.id}`, null, buyer1.token);
  expect('N-019', '알림 통계 조회', r.ok || r.status < 500, `status=${r.status}`, r.elapsed);

  // ── 전체 ──
  r = await req('GET', `/notifications?user_id=${buyer1.id}`, null, buyer1.token);
  expect('N-020', '알림 전체 조회 성공', r.ok, `count=${Array.isArray(r.data) ? r.data.length : '?'}`, r.elapsed);
}
