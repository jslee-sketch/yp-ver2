import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import BottomNav from './BottomNav';

export const Layout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  const hideNav =
    ['/login', '/register', '/deal/create'].includes(location.pathname) ||
    location.pathname.includes('/offer/create') ||
    location.pathname.includes('/join') ||
    location.pathname.includes('/review/write/') ||
    location.pathname.includes('/seller/ship/');

  return (
    <div style={{ minHeight: '100dvh', position: 'relative' }}>
      <Sidebar
        isOpen={sidebarOpen}
        onOpen={() => setSidebarOpen(true)}
        onClose={() => setSidebarOpen(false)}
      />
      <main style={{ minHeight: '100dvh' }}>
        <Outlet />
      </main>
      {!hideNav && <BottomNav onMenuClick={() => setSidebarOpen(true)} />}
    </div>
  );
};
