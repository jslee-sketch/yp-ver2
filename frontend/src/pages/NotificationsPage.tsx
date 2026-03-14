import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchNotifications, markNotificationRead, markAllRead } from '../api/notificationApi';

interface NotificationItem {
  id: number;
  type: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
  link_to?: string;
  sent_app?: boolean;
  sent_push?: boolean;
  sent_email?: boolean;
}

const TYPE_ICON: Record<string, string> = {
  new_offer: '🔔', deadline: '⏰', shipped: '📦', delivered: '✅',
  points: '💰', review: '⭐', deal_update: '📊', payment: '💳',
  interest_match: '🎯', refund: '↩️', settlement: '💵', dispute: '⚠️',
};

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

const channelBadge = (label: string, sent: boolean) => (
  <span style={{
    fontSize: 9, padding: '1px 5px', borderRadius: 4, fontWeight: 600,
    background: sent ? 'rgba(74,222,128,0.15)' : 'rgba(255,255,255,0.05)',
    color: sent ? '#4ade80' : '#555',
    border: `1px solid ${sent ? 'rgba(74,222,128,0.3)' : 'rgba(255,255,255,0.08)'}`,
  }}>{label}</span>
);

export default function NotificationsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTitle, setSearchTitle] = useState('');
  const [filterRead, setFilterRead] = useState<'all' | 'unread' | 'read'>('all');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const apiData = await fetchNotifications(user?.id);
      if (apiData && Array.isArray(apiData) && apiData.length > 0) {
        setItems(apiData.map((n: Record<string, unknown>) => ({
          id:         typeof n.id === 'number' ? n.id : 0,
          type:       String(n.type ?? 'deal_update'),
          title:      String(n.title ?? ''),
          body:       String(n.body ?? n.message ?? ''),
          is_read:    Boolean(n.is_read),
          created_at: String(n.created_at ?? new Date().toISOString()),
          link_to:    typeof n.link === 'string' ? n.link : (typeof n.link_to === 'string' ? n.link_to : (typeof n.link_url === 'string' ? n.link_url : undefined)),
          sent_app:   typeof n.sent_app === 'boolean' ? n.sent_app : undefined,
          sent_push:  typeof n.sent_push === 'boolean' ? n.sent_push : undefined,
          sent_email: typeof n.sent_email === 'boolean' ? n.sent_email : undefined,
        })));
      }
      setLoading(false);
    };
    void load();
  }, [user]);

  const filtered = items.filter(i => {
    if (filterRead === 'unread' && i.is_read) return false;
    if (filterRead === 'read' && !i.is_read) return false;
    if (searchTitle && !i.title.toLowerCase().includes(searchTitle.toLowerCase()) &&
        !i.body.toLowerCase().includes(searchTitle.toLowerCase())) return false;
    return true;
  });

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

  const todayItems = filtered.filter(i => isToday(i.created_at));
  const prevItems  = filtered.filter(i => !isToday(i.created_at));

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
      <span style={{ fontSize: 20, flexShrink: 0, marginTop: 1 }}>
        {TYPE_ICON[item.type] || '📌'}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: item.is_read ? 500 : 700, color: C.text, marginBottom: 3 }}>
          {item.title}
        </div>
        <div style={{ fontSize: 12, color: C.textSec, marginBottom: 5 }}>{item.body}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: 11, color: C.textDim }}>{relativeTime(item.created_at)}</span>
          {item.sent_app !== undefined && (
            <div style={{ display: 'flex', gap: 3, marginLeft: 4 }}>
              {channelBadge('앱', !!item.sent_app)}
              {channelBadge('푸시', !!item.sent_push)}
              {channelBadge('이메일', !!item.sent_email)}
            </div>
          )}
        </div>
      </div>
      {!item.is_read && (
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: C.blue, flexShrink: 0, marginTop: 4 }} />
      )}
    </button>
  );

  const filterBtnStyle = (active: boolean): React.CSSProperties => ({
    padding: '5px 12px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
    background: active ? 'rgba(74,222,128,0.15)' : 'transparent',
    border: `1px solid ${active ? 'rgba(74,222,128,0.4)' : C.border}`,
    color: active ? '#4ade80' : C.textDim,
  });

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
        {/* Search + Filter */}
        <div style={{ marginBottom: 12 }}>
          <input
            value={searchTitle}
            onChange={e => setSearchTitle(e.target.value)}
            placeholder="알림 검색 (제목/내용)"
            style={{
              width: '100%', padding: '10px 14px', borderRadius: 10,
              background: C.bgEl, color: C.text, border: `1px solid ${C.border}`,
              fontSize: 13, marginBottom: 8, boxSizing: 'border-box',
            }}
          />
          <div style={{ display: 'flex', gap: 6 }}>
            <button style={filterBtnStyle(filterRead === 'all')} onClick={() => setFilterRead('all')}>전체</button>
            <button style={filterBtnStyle(filterRead === 'unread')} onClick={() => setFilterRead('unread')}>안읽음</button>
            <button style={filterBtnStyle(filterRead === 'read')} onClick={() => setFilterRead('read')}>읽음</button>
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: C.textDim, fontSize: 14 }}>로딩 중...</div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: C.textDim, fontSize: 15 }}>
            {searchTitle || filterRead !== 'all' ? '검색 결과가 없어요' : '알림이 없어요 🔔'}
          </div>
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
