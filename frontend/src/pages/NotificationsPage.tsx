import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchNotifications, markNotificationRead, markAllRead } from '../api/notificationApi';

type NotiType = 'new_offer' | 'deadline' | 'shipped' | 'delivered' | 'points' | 'review' | 'deal_update' | 'payment';

interface NotificationItem {
  id: number;
  type: NotiType;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
  link_to?: string;
}

const TYPE_ICON: Record<NotiType, string> = {
  new_offer:   '🔔',
  deadline:    '⏰',
  shipped:     '📦',
  delivered:   '✅',
  points:      '💰',
  review:      '⭐',
  deal_update: '📊',
  payment:     '💳',
};

const MOCK: NotificationItem[] = [
  { id: 1, type: 'new_offer',   title: '에어팟 프로 딜에 새 오퍼!',    body: 'PREMIUM 오퍼가 도착했어요',           is_read: false, created_at: '2026-03-02T14:30:00', link_to: '/deal/15' },
  { id: 2, type: 'deadline',    title: '갤럭시 S25 딜 마감 임박',       body: '23시간 남았어요',                    is_read: false, created_at: '2026-03-02T12:00:00', link_to: '/deal/17' },
  { id: 3, type: 'shipped',     title: '에어팟 배송 출발!',              body: '운송장: 1234567890',                 is_read: true,  created_at: '2026-03-01T10:00:00', link_to: '/my-orders' },
  { id: 4, type: 'delivered',   title: '다이슨 에어랩 배송 완료',         body: '수령 확인을 해주세요',               is_read: true,  created_at: '2026-02-28T15:00:00', link_to: '/my-orders' },
  { id: 5, type: 'points',      title: '포인트 20P 적립',               body: '나이키 에어포스 구매 확정',           is_read: true,  created_at: '2026-02-27T09:00:00' },
  { id: 6, type: 'deal_update', title: '에어팟 딜 목표가 변경',           body: '방장이 목표가를 ₩265,000으로 변경했어요', is_read: true, created_at: '2026-02-26T16:00:00', link_to: '/deal/15' },
  { id: 7, type: 'payment',     title: '결제 시간 5분!',                 body: '에어팟 프로 오퍼가 확정됐어요. 지금 결제하세요!', is_read: true, created_at: '2026-02-25T11:00:00', link_to: '/my-orders' },
];

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', blue: 'var(--accent-blue)',
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const min = Math.floor(diff / 60000);
  if (min < 1) return '방금 전';
  if (min < 60) return `${min}분 전`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h}시간 전`;
  const d = Math.floor(h / 24);
  if (d === 1) return '어제';
  return `${d}일 전`;
}

function isToday(iso: string): boolean {
  const d = new Date(iso);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
}

export default function NotificationsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [items, setItems] = useState<NotificationItem[]>(MOCK);

  useEffect(() => {
    const load = async () => {
      const apiData = await fetchNotifications();
      if (apiData && Array.isArray(apiData) && apiData.length > 0) {
        setItems(apiData.map((n: Record<string, unknown>) => ({
          id:         typeof n.id === 'number' ? n.id : 0,
          type:       (String(n.title ?? '').includes('오퍼') ? 'new_offer'
                     : String(n.title ?? '').includes('배송') ? 'shipped'
                     : String(n.title ?? '').includes('포인트') ? 'points'
                     : 'deal_update') as NotiType,
          title:      String(n.title ?? ''),
          body:       String(n.body ?? ''),
          is_read:    Boolean(n.is_read),
          created_at: String(n.created_at ?? new Date().toISOString()),
          link_to:    typeof n.link === 'string' ? n.link : (typeof n.link_to === 'string' ? n.link_to : undefined),
        })));
      }
    };
    void load();
  }, [user]);

  const unread = items.filter(i => !i.is_read).length;

  const markRead = async (id: number) => {
    await markNotificationRead(id);
    setItems(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
  };
  const markAll = async () => {
    await markAllRead();
    setItems(prev => prev.map(n => ({ ...n, is_read: true })));
  };

  const handleClick = (item: NotificationItem) => {
    void markRead(item.id);
    if (item.link_to) navigate(item.link_to);
  };

  const todayItems = items.filter(i => isToday(i.created_at));
  const prevItems  = items.filter(i => !isToday(i.created_at));

  const renderItem = (item: NotificationItem) => (
    <button
      key={item.id}
      onClick={() => handleClick(item)}
      style={{
        width: '100%', textAlign: 'left', display: 'flex', alignItems: 'flex-start', gap: 12,
        background: item.is_read ? C.bgCard : 'rgba(0,176,255,0.07)',
        border: `1px solid ${item.is_read ? C.border : 'rgba(0,176,255,0.25)'}`,
        borderRadius: 14, padding: '13px 14px', marginBottom: 8, cursor: 'pointer',
        transition: 'background 0.15s',
      }}
    >
      <span style={{ fontSize: 20, flexShrink: 0, marginTop: 1 }}>{TYPE_ICON[item.type]}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: item.is_read ? 500 : 700, color: C.text, marginBottom: 3 }}>
          {item.title}
        </div>
        <div style={{ fontSize: 12, color: C.textSec, marginBottom: 5 }}>{item.body}</div>
        <div style={{ fontSize: 11, color: C.textDim }}>{relativeTime(item.created_at)}</div>
      </div>
      {!item.is_read && (
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: C.blue, flexShrink: 0, marginTop: 4 }} />
      )}
    </button>
  );

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      {/* TopBar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>
          알림 {unread > 0 && <span style={{ fontSize: 12, fontWeight: 700, color: C.blue }}>({unread})</span>}
        </span>
        {unread > 0 ? (
          <button onClick={markAll} style={{ fontSize: 11, fontWeight: 700, color: C.blue, cursor: 'pointer' }}>모두읽기</button>
        ) : (
          <div style={{ width: 52 }} />
        )}
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {items.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: C.textDim, fontSize: 15 }}>알림이 없어요 🔔</div>
        ) : (
          <>
            {todayItems.length > 0 && (
              <>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 8 }}>오늘</div>
                {todayItems.map(renderItem)}
              </>
            )}
            {prevItems.length > 0 && (
              <>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 8, marginTop: todayItems.length ? 8 : 0 }}>이전</div>
                {prevItems.map(renderItem)}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
