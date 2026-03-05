import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';

interface BottomNavProps {
  onMenuClick?: () => void;
}

export default function BottomNav({ onMenuClick }: BottomNavProps) {
  const navigate  = useNavigate();
  const location  = useLocation();
  const { user }  = useAuth();

  const role = (user?.role ?? '').toLowerCase();
  const isSeller = role === 'seller' || role === 'both';
  const isAdmin  = role === 'admin';

  // 역할별 중앙 버튼
  const centerItem = isAdmin
    ? { icon: '📊', label: '대시보드', path: '/admin' }
    : isSeller
      ? { icon: '🔍', label: '딜 탐색',  path: '/deals' }
      : { icon: '➕', label: '딜만들기', path: '/deal/create' };

  const NAV_ITEMS = [
    { icon: '🏠', label: '홈',   path: '/' },
    { icon: '🔍', label: '검색', path: '/search' },
    { ...centerItem, special: true },
    { icon: '📋', label: '마이', path: '/mypage' },
    { icon: '☰', label: '메뉴', action: 'menu' as const },
  ];

  return (
    <nav style={{
      position: 'fixed',
      bottom: 0,
      left: '50%',
      transform: 'translateX(-50%)',
      width: '100%',
      maxWidth: 500,
      background: '#0a0e1a',
      borderTop: '1px solid rgba(255,255,255,0.08)',
      display: 'flex',
      justifyContent: 'space-around',
      alignItems: 'flex-end',
      padding: '8px 0',
      paddingBottom: 'max(8px, env(safe-area-inset-bottom))',
      zIndex: 1000,
    }}>
      {NAV_ITEMS.map((item, i) => {
        const isActive = 'path' in item && item.path === location.pathname;
        const isSpecial = 'special' in item && item.special;

        if (isSpecial) {
          return (
            <button
              key={item.label}
              onClick={() => navigate(item.path)}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                padding: '0 8px',
              }}
              aria-label={item.label}
            >
              <div style={{
                width: 48, height: 48,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, #00ff88, #00d4ff)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginTop: -20,
                boxShadow: '0 4px 15px rgba(0,255,136,0.3)',
                fontSize: 22,
              }}>
                {item.icon}
              </div>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginTop: 2 }}>{item.label}</span>
            </button>
          );
        }

        return (
          <button
            key={i}
            onClick={() => {
              if ('action' in item && item.action === 'menu') {
                onMenuClick?.();
              } else if ('path' in item) {
                navigate(item.path);
              }
            }}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
              padding: '4px 12px',
              color: isActive ? '#00ff88' : 'rgba(255,255,255,0.4)',
              transition: 'color 0.2s',
            }}
          >
            <span style={{ fontSize: 20 }}>{item.icon}</span>
            <span style={{ fontSize: 10, fontWeight: isActive ? 600 : 400 }}>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
