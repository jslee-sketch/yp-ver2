import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { fetchUnreadCount } from '../../api/notificationApi';

interface NotificationBadgeProps {
  style?: React.CSSProperties;
}

export default function NotificationBadge({ style }: NotificationBadgeProps) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!user) return;
    fetchUnreadCount()
      .then(n => { if (typeof n === 'number') setCount(n); })
      .catch(() => {});

    // 30초마다 폴링
    const interval = setInterval(() => {
      fetchUnreadCount()
        .then(n => { if (typeof n === 'number') setCount(n); })
        .catch(() => {});
    }, 30000);

    return () => clearInterval(interval);
  }, [user]);

  return (
    <button
      onClick={() => navigate('/notifications')}
      style={{
        position: 'relative',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: 4,
        fontSize: 22,
        lineHeight: 1,
        ...style,
      }}
      aria-label={`알림 ${count > 0 ? `(${count}건 미읽음)` : ''}`}
    >
      <span>🔔</span>
      {count > 0 && (
        <span style={{
          position: 'absolute',
          top: 0,
          right: -2,
          minWidth: 16,
          height: 16,
          borderRadius: 8,
          background: '#ff5252',
          color: '#fff',
          fontSize: 9,
          fontWeight: 800,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 3px',
        }}>
          {count > 99 ? '99+' : count}
        </span>
      )}
    </button>
  );
}
