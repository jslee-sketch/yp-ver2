import { useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import AdminSidebar from './AdminSidebar';

export default function AdminLayout() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && (!user || user.role !== 'admin')) {
      navigate('/', { replace: true });
    }
  }, [user, isLoading, navigate]);

  if (isLoading) return null;
  if (!user || user.role !== 'admin') return null;

  return (
    <div
      className="admin-layout"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        backgroundColor: 'var(--bg-primary)',
        zIndex: 2000,
      }}
    >
      <AdminSidebar />
      <main
        style={{
          flex: 1,
          height: '100vh',
          overflowY: 'auto',
          overflowX: 'auto',
          padding: '24px 32px',
          minWidth: 0,
        }}
      >
        <Outlet />
      </main>
    </div>
  );
}
