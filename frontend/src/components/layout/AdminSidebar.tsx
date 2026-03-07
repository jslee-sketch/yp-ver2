import { useLocation, useNavigate } from 'react-router-dom';

const sections = [
  {
    title: '개요',
    items: [
      { label: '대시보드', path: '/admin' },
      { label: '통계/KPI', path: '/admin/stats' },
    ],
  },
  {
    title: '회원',
    items: [
      { label: '구매자', path: '/admin/buyers' },
      { label: '판매자', path: '/admin/sellers' },
      { label: '액추에이터', path: '/admin/actuators' },
    ],
  },
  {
    title: '거래',
    items: [
      { label: '딜', path: '/admin/deals' },
      { label: '오퍼', path: '/admin/offers' },
      { label: '예약/주문', path: '/admin/reservations' },
      { label: '배송', path: '/admin/delivery' },
      { label: '환불', path: '/admin/refunds' },
    ],
  },
  {
    title: '정산',
    items: [
      { label: '정산 관리', path: '/admin/settlements' },
      { label: '분쟁', path: '/admin/disputes' },
      { label: '환불 시뮬레이터', path: '/admin/refund-simulator' },
    ],
  },
  {
    title: '정책',
    items: [
      { label: '정책 파라미터', path: '/admin/policy-params' },
      { label: '정책 문서', path: '/admin/policy-docs' },
      { label: '핑퐁이 정책제안', path: '/admin/policy-proposals' },
    ],
  },
  {
    title: '모니터링',
    items: [
      { label: '활동 로그', path: '/admin/logs' },
      { label: '이상 감지', path: '/admin/anomalies' },
      { label: '신고', path: '/admin/reports' },
    ],
  },
  {
    title: '시스템',
    items: [
      { label: '알림', path: '/admin/notifications' },
      { label: '공지사항', path: '/admin/announcements' },
      { label: '시스템 설정', path: '/admin/settings' },
    ],
  },
];

export default function AdminSidebar() {
  const location = useLocation();
  const navigate = useNavigate();

  const isActive = (path: string) => {
    if (path === '/admin') return location.pathname === '/admin';
    return location.pathname.startsWith(path);
  };

  return (
    <aside
      style={{
        width: 240,
        minWidth: 240,
        height: '100%',
        overflowY: 'auto',
        background: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}
    >
      <div
        style={{
          padding: '20px 16px 12px',
          fontSize: 18,
          fontWeight: 700,
          color: '#00e5ff',
          letterSpacing: '-0.5px',
          cursor: 'pointer',
        }}
        onClick={() => navigate('/admin')}
      >
        Admin
      </div>

      <nav style={{ flex: 1, padding: '0 8px' }}>
        {sections.map((sec) => (
          <div key={sec.title} style={{ marginBottom: 8 }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: 'var(--text-muted)',
                textTransform: 'uppercase',
                padding: '8px 8px 4px',
                letterSpacing: '0.5px',
              }}
            >
              {sec.title}
            </div>
            {sec.items.map((item) => {
              const active = isActive(item.path);
              return (
                <div
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  style={{
                    padding: '7px 12px',
                    fontSize: 13,
                    color: active ? '#00e5ff' : 'var(--text-primary)',
                    background: active ? 'rgba(0,229,255,0.08)' : 'transparent',
                    borderRight: active ? '2px solid #00e5ff' : '2px solid transparent',
                    borderRadius: '6px 0 0 6px',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    fontWeight: active ? 600 : 400,
                  }}
                  onMouseEnter={(e) => {
                    if (!active) (e.currentTarget.style.background = 'rgba(255,255,255,0.04)');
                  }}
                  onMouseLeave={(e) => {
                    if (!active) (e.currentTarget.style.background = 'transparent');
                  }}
                >
                  {item.label}
                </div>
              );
            })}
          </div>
        ))}
      </nav>

      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border-subtle)' }}>
        <button
          onClick={() => {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user');
            navigate('/login');
          }}
          style={{
            width: '100%',
            padding: '8px',
            background: 'transparent',
            border: '1px solid var(--border-subtle)',
            borderRadius: 6,
            color: 'var(--text-muted)',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          로그아웃
        </button>
      </div>
    </aside>
  );
}
