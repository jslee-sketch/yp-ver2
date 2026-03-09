import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';

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
      { label: '세금계산서', path: '/admin/tax-invoices' },
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
      { label: '마이너리티 리포트', path: '/admin/minority-report' },
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
  const [isOpen, setIsOpen] = useState(false);

  // Escape 키로 닫기
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setIsOpen(false); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen]);

  const isActive = (path: string) => {
    if (path === '/admin') return location.pathname === '/admin';
    return location.pathname.startsWith(path);
  };

  const handleMenuClick = (path: string) => {
    navigate(path);
    setIsOpen(false);
  };

  return (
    <>
      {/* 햄버거 토글 버튼 */}
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            key="admin-tab"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            onClick={() => setIsOpen(true)}
            onMouseEnter={e => {
              e.currentTarget.style.background = '#00c8e0';
              e.currentTarget.style.boxShadow = '0 4px 20px rgba(0, 229, 255, 0.6)';
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = '#00e5ff';
              e.currentTarget.style.boxShadow = '0 2px 12px rgba(0, 229, 255, 0.4)';
            }}
            style={{
              position: 'fixed',
              top: 12,
              left: 12,
              zIndex: 1000,
              width: 44,
              height: 44,
              borderRadius: 12,
              border: 'none',
              background: '#00e5ff',
              color: '#000',
              fontSize: 22,
              fontWeight: 'bold',
              cursor: 'pointer',
              boxShadow: '0 2px 12px rgba(0, 229, 255, 0.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'background 0.2s ease, box-shadow 0.2s ease',
            }}
            aria-label="관리자 메뉴 열기"
          >
            ☰
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isOpen && (
          <>
            {/* 오버레이 — 클릭하면 닫힘 */}
            <motion.div
              key="admin-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              onClick={() => setIsOpen(false)}
              style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0,0,0,0.5)',
                zIndex: 1040,
              }}
            />

            {/* 사이드바 패널 */}
            <motion.aside
              key="admin-panel"
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ type: 'tween', duration: 0.3, ease: 'easeOut' }}
              style={{
                position: 'fixed',
                left: 0,
                top: 0,
                bottom: 0,
                width: 260,
                overflowY: 'auto',
                background: 'var(--bg-secondary)',
                borderRight: '1px solid var(--border-subtle)',
                display: 'flex',
                flexDirection: 'column',
                zIndex: 1050,
              }}
            >
              {/* 상단: 홈 + 닫기 */}
              <div style={{
                display: 'flex', justifyContent: 'space-between',
                alignItems: 'center', padding: '12px 16px',
                borderBottom: '1px solid var(--border-subtle)',
              }}>
                <button
                  onClick={() => handleMenuClick('/admin')}
                  style={{
                    background: 'none', border: 'none',
                    color: '#00e5ff', cursor: 'pointer',
                    fontSize: 16, display: 'flex',
                    alignItems: 'center', gap: 6,
                    padding: '4px 0',
                  }}
                >
                  🏠 <span style={{ fontSize: 14, fontWeight: 700 }}>Admin 홈</span>
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  style={{
                    background: 'none', border: 'none',
                    color: '#888', cursor: 'pointer',
                    fontSize: 20, padding: '4px 8px',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                  aria-label="닫기"
                >
                  ✕
                </button>
              </div>

              {/* 메뉴 섹션 */}
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
                          onClick={() => handleMenuClick(item.path)}
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

              {/* 하단: 로그아웃 */}
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
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
