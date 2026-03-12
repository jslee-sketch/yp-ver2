import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import BottomNav from './BottomNav';
import Footer from './Footer';
import NotificationBadge from '../common/NotificationBadge';
import OnboardingGuide from '../OnboardingGuide';
import { useAuth } from '../../contexts/AuthContext';

export const Layout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const { user } = useAuth();

  const hideNav =
    ['/login', '/register', '/deal/create'].includes(location.pathname) ||
    location.pathname.includes('/offer/create') ||
    location.pathname.includes('/join') ||
    location.pathname.includes('/review/write/') ||
    location.pathname.includes('/seller/ship/');

  // 알림 배지를 보여줄 페이지 (글로벌 헤더가 없는 페이지 대응)
  const showBadge = user && !hideNav && !location.pathname.startsWith('/admin');

  const [showOnboarding, setShowOnboarding] = useState(() => {
    return user && !localStorage.getItem('onboarding_done');
  });

  const handleOnboardingComplete = () => {
    localStorage.setItem('onboarding_done', 'true');
    setShowOnboarding(false);
  };

  return (
    <div style={{ minHeight: '100dvh', position: 'relative' }}>
      <Sidebar
        isOpen={sidebarOpen}
        onOpen={() => setSidebarOpen(true)}
        onClose={() => setSidebarOpen(false)}
      />
      {showBadge && (
        <NotificationBadge style={{
          position: 'fixed', top: 12, right: 12, zIndex: 999,
        }} />
      )}
      <main style={{ minHeight: '100dvh' }}>
        <Outlet />
        <Footer />
      </main>
      {!hideNav && <BottomNav onMenuClick={() => setSidebarOpen(true)} />}
      {showOnboarding && (
        <OnboardingGuide
          role={user?.role === 'seller' ? 'seller' : 'buyer'}
          onComplete={handleOnboardingComplete}
        />
      )}
    </div>
  );
};
