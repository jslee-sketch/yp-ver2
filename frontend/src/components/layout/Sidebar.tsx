import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { motion, AnimatePresence } from 'framer-motion';
import { fetchUnreadCount } from '../../api/notificationApi';

type BadgeColor = 'green' | 'red' | 'blue' | 'orange';

const BADGE_COLORS: Record<BadgeColor, { bg: string; color: string }> = {
  green:  { bg: 'rgba(0,230,118,0.8)',  color: '#0a0a0f' },
  red:    { bg: '#ff5252',              color: '#fff' },
  blue:   { bg: 'rgba(0,176,255,0.85)', color: '#fff' },
  orange: { bg: 'var(--accent-orange)', color: '#0a0a0f' },
};

// ── 사이드바 탭 ───────────────────────────────────────
const SidebarTab: React.FC<{ isVisible: boolean; onClick: () => void }> = ({ isVisible, onClick }) => (
  <AnimatePresence>
    {isVisible && (
      <motion.button
        key="sidebar-tab"
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.8 }}
        onClick={onClick}
        onMouseEnter={e => {
          e.currentTarget.style.background = '#38d96a';
          e.currentTarget.style.boxShadow = '0 4px 20px rgba(74, 222, 128, 0.6)';
        }}
        onMouseLeave={e => {
          e.currentTarget.style.background = '#4ade80';
          e.currentTarget.style.boxShadow = '0 2px 12px rgba(74, 222, 128, 0.4)';
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
          background: '#4ade80',
          color: '#000',
          fontSize: 22,
          fontWeight: 'bold',
          cursor: 'pointer',
          boxShadow: '0 2px 12px rgba(74, 222, 128, 0.4)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'background 0.2s ease, box-shadow 0.2s ease',
        }}
        aria-label="메뉴 열기"
      >
        ☰
      </motion.button>
    )}
  </AnimatePresence>
);

// ── 섹션 타이틀 ──────────────────────────────────────
const SectionTitle: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{
    fontSize: 11, fontWeight: 700, color: '#78909c',
    letterSpacing: '1px', textTransform: 'uppercase',
    padding: '14px 20px 5px',
  }}>
    {children}
  </div>
);

// ── 메뉴 아이템 ──────────────────────────────────────
const MenuItem: React.FC<{
  icon: string;
  label: string;
  badge?: number | string;
  badgeColor?: BadgeColor;
  desc?: string;
  danger?: boolean;
  onClick?: () => void;
}> = ({ icon, label, badge, badgeColor = 'green', desc, danger, onClick }) => (
  <button
    onClick={onClick}
    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.04)')}
    onMouseLeave={e => (e.currentTarget.style.background = 'none')}
    style={{
      width: '100%',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '11px 20px',
      background: 'none', cursor: 'pointer',
      transition: 'background 0.15s ease',
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <span style={{ fontSize: 16, width: 20, textAlign: 'center', flexShrink: 0 }}>{icon}</span>
      <span style={{ fontSize: 14, fontWeight: 500, color: danger ? '#ff5252' : '#e8eaed' }}>
        {label}
      </span>
    </div>
    {desc !== undefined && (
      <span style={{ fontSize: 11, color: '#607d8b', marginLeft: 'auto', flexShrink: 0 }}>
        {desc}
      </span>
    )}
    {badge !== undefined && (
      <span style={{
        padding: '2px 7px', borderRadius: 20,
        fontSize: 10, fontWeight: 700, flexShrink: 0,
        marginLeft: desc !== undefined ? 6 : 'auto',
        background: BADGE_COLORS[badgeColor].bg,
        color: BADGE_COLORS[badgeColor].color,
      }}>
        {badge}
      </span>
    )}
  </button>
);

// ── 메인 컴포넌트 ────────────────────────────────────
interface SidebarProps {
  isOpen: boolean;
  onOpen: () => void;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onOpen, onClose }) => {
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const [isDark, setIsDark] = useState(true);
  const [unreadCount, setUnreadCount] = useState(0);

  const isSeller = user?.role === 'seller' || user?.role === 'both';
  const isActuator = user?.role === 'actuator';
  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    if (!user) return;
    fetchUnreadCount().then(n => { if (n !== undefined) setUnreadCount(n); }).catch(() => {});
  }, [user]);

  // Escape 키로 닫기
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onClose]);

  const go = (path: string) => { navigate(path); onClose(); };

  const toggleTheme = () => {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.setAttribute('data-theme', next ? '' : 'light');
  };

  const displayName = user?.name ?? '사용자';
  const displayNickname = user?.nickname ?? '';
  const displayEmail = user?.email ?? '';
  const displayPoints = user?.points ?? 0;
  const displayLevel = user?.level ?? 1;
  const displayTier = user?.trust_tier ?? 'Bronze';

  return (
    <>
      <SidebarTab isVisible={!isOpen} onClick={onOpen} />

      <AnimatePresence>
        {isOpen && (
          <>
            {/* 오버레이 */}
            <motion.div
              key="overlay"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              onClick={onClose}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)', zIndex: 1999 }}
            />

            {/* 패널 */}
            <motion.div
              key="panel"
              initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }}
              transition={{ type: 'tween', duration: 0.3, ease: 'easeOut' }}
              style={{
                position: 'fixed', left: 0, top: 0, bottom: 0, width: 280,
                background: 'var(--bg-secondary)',
                borderRight: '1px solid var(--border-subtle)',
                zIndex: 2000,
                overflowY: 'auto',
                display: 'flex', flexDirection: 'column',
              }}
            >
              {/* 닫기 버튼 */}
              <button
                onClick={onClose}
                style={{
                  position: 'absolute', top: 14, right: 14,
                  width: 28, height: 28, borderRadius: '50%',
                  background: 'var(--bg-elevated)', color: 'var(--text-muted)',
                  fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  zIndex: 1, cursor: 'pointer',
                }}
                aria-label="사이드바 닫기"
              >✕</button>

              {/* 프로필 헤더 */}
              <button
                onClick={() => go('/mypage')}
                style={{
                  padding: '28px 20px 18px', borderBottom: '1px solid var(--border-subtle)',
                  background: 'none', cursor: 'pointer', textAlign: 'left', width: '100%',
                }}
              >
                <div style={{
                  width: 44, height: 44, borderRadius: '50%',
                  background: 'linear-gradient(135deg, #00e676, #00b0ff)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 18, fontWeight: 800, color: '#0a0a0f', marginBottom: 10,
                }}>
                  {displayName.charAt(0)}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
                  <span style={{ fontSize: 15, fontWeight: 800, color: '#e8eaed' }}>{displayName}</span>
                  <span style={{
                    padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700,
                    background: isAdmin ? 'rgba(224,64,251,0.12)' : isActuator ? 'rgba(0,229,255,0.12)' : isSeller ? 'rgba(255,145,0,0.12)' : 'rgba(0,230,118,0.12)',
                    color: isAdmin ? '#e040fb' : isActuator ? '#00e5ff' : isSeller ? '#ff9100' : '#00e676',
                  }}>
                    {isAdmin ? '관리자' : isActuator ? '액추에이터' : isSeller ? '판매자' : '구매자'}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: '#78909c', marginBottom: 10 }}>
                  {displayNickname ? `@${displayNickname} · ` : ''}{displayEmail}
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span style={{
                    padding: '4px 10px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                    background: 'rgba(0,230,118,0.08)', color: '#00e676',
                  }}>
                    {displayPoints.toLocaleString('ko-KR')}P
                  </span>
                  <span style={{
                    padding: '4px 10px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                    background: 'rgba(0,176,255,0.08)', color: '#00b0ff',
                  }}>
                    Lv.{displayLevel}
                  </span>
                  <span style={{
                    padding: '4px 10px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                    background: 'rgba(192,192,192,0.1)', color: '#c0c0c0',
                  }}>
                    {displayTier}
                  </span>
                </div>
              </button>

              {/* 메뉴 섹션 */}
              <div style={{ flex: 1, paddingBottom: 8 }}>
                {isSeller ? (
                  <>
                    <SectionTitle>판매자</SectionTitle>
                    <MenuItem icon="🏠" label="대시보드"     onClick={() => go('/seller')} />
                    <MenuItem icon="📝" label="오퍼 관리"    onClick={() => go('/seller/offers')} />
                    <MenuItem icon="📦" label="배송 관리"    onClick={() => go('/seller/delivery')} />
                    <MenuItem icon="↩️" label="반품/교환"    onClick={() => go('/seller/returns')} />
                    <MenuItem icon="💰" label="정산 관리"    onClick={() => go('/seller/settlements')} />
                    <MenuItem icon="💸" label="환불 관리"    onClick={() => go('/seller/refunds')} />
                    <MenuItem icon="💬" label="고객 문의"    onClick={() => go('/seller/inquiries')} />
                    <MenuItem icon="⭐" label="리뷰 관리"    onClick={() => go('/seller/reviews')} />
                    <MenuItem icon="🚚" label="배송 정책"    onClick={() => go('/seller/shipping-policy')} />
                    <MenuItem icon="📊" label="판매 통계"    onClick={() => go('/seller/stats')} />
                    <MenuItem icon="💎" label="수수료 안내"   onClick={() => go('/seller/fees')} />
                    <MenuItem icon="🧾" label="세금계산서"   onClick={() => go('/seller/tax-invoices')} />
                    <MenuItem icon="🏢" label="사업자 정보"  onClick={() => go('/seller/business-info')} />
                    <MenuItem icon="🔔" label="알림"         onClick={() => go('/seller/notifications')} badge={unreadCount > 0 ? unreadCount : undefined} badgeColor="red" />
                    <MenuItem icon="📢" label="공지/도움말"   onClick={() => go('/seller/announcements')} />
                    <MenuItem icon="👤" label="마이페이지"   onClick={() => go('/mypage')} />
                  </>
                ) : isActuator ? (
                  <>
                    <SectionTitle>액추에이터</SectionTitle>
                    <MenuItem icon="🏠" label="홈"            onClick={() => go('/')} />
                    <MenuItem icon="👥" label="내 판매자 관리" onClick={() => go('/actuator/sellers')} />
                    <MenuItem icon="📋" label="오퍼 현황"     onClick={() => go('/actuator/offers')} />
                    <MenuItem icon="📊" label="활동 현황"     onClick={() => go('/actuator/stats')} />
                    <MenuItem icon="💰" label="커미션 관리"   onClick={() => go('/actuator/commissions')} />
                    <MenuItem icon="📢" label="판매자 초대"   onClick={() => go('/actuator/invite')} />
                    <MenuItem icon="📝" label="위탁계약서"   onClick={() => go('/actuator/contract')} />
                    <MenuItem icon="👤" label="마이페이지"    onClick={() => go('/mypage')} />
                  </>
                ) : isAdmin ? (
                  <>
                    <SectionTitle>관리자</SectionTitle>
                    <MenuItem icon="🖥️" label="관리자 패널로 이동" onClick={() => go('/admin')} />
                  </>
                ) : (
                  <>
                    <SectionTitle>메인</SectionTitle>
                    <MenuItem icon="🏠" label="홈"          onClick={() => go('/')} />
                    <MenuItem icon="🔍" label="검색"        onClick={() => go('/search')} />
                    <MenuItem icon="➕" label="딜 만들기"    onClick={() => go('/deal/create')} />

                    <SectionTitle>내 활동</SectionTitle>
                    <MenuItem icon="👤" label="마이페이지"      onClick={() => go('/mypage')} />
                    <MenuItem icon="🔥" label="내딜 현황"       onClick={() => go('/my-deals')} />
                    <MenuItem icon="💰" label="포인트 내역"     onClick={() => go('/points')} />
                    <MenuItem icon="📦" label="참여/결제/배송"   onClick={() => go('/my-orders')} />
                    <MenuItem icon="👀" label="관전 모드"       onClick={() => go('/spectating')} />

                    <SectionTitle>탐색</SectionTitle>
                    <MenuItem icon="📊" label="지난딜 가격조회" onClick={() => go('/completed-deals')} />
                  </>
                )}
              </div>

              {/* 하단 */}
              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingBottom: 8 }}>
                {!isSeller && (
                  <MenuItem icon="🔔" label="알림"    badge={unreadCount > 0 ? unreadCount : undefined} badgeColor="red"
                    onClick={() => go('/notifications')} />
                )}
                <MenuItem icon="⚙️" label="설정"    onClick={() => go('/settings')} />
                <MenuItem icon="🎯" label="관심 상품" onClick={() => go('/settings/interests')} />
                <MenuItem icon="🔧" label="알림 설정" onClick={() => go('/settings/notifications')} />
                <MenuItem icon="📋" label="이용약관" onClick={() => go('/terms')} />
                <MenuItem icon="💬" label="고객센터" onClick={() => go('/support')} />
                <MenuItem icon="❓" label="FAQ" onClick={() => go('/faq')} />
                <MenuItem
                  icon={isDark ? '☀️' : '🌙'}
                  label={isDark ? '라이트 테마' : '다크 테마'}
                  onClick={toggleTheme}
                />
                <MenuItem icon="🚪" label="로그아웃" danger
                  onClick={() => { logout(); go('/login'); }} />
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
};
