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
    <div className="admin-layout" style={{ display: 'flex', width: '100vw', minHeight: '100vh' }}>
      <AdminSidebar />
      <main
        style={{
          flex: 1,
          padding: '24px 32px',
          overflowY: 'auto',
          background: 'var(--bg-primary)',
          minHeight: '100vh',
        }}
      >
        <Outlet />
      </main>
    </div>
  );
}
