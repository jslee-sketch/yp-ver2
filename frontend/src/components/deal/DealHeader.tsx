import React, { useEffect, useState } from 'react';
import { Badge } from '../common/Badge';
import type { Deal } from '../../types';

interface DealHeaderProps {
  deal: Deal;
}

function calcTimeLeft(deadline: string | null): string {
  if (!deadline) return '';
  const diff = new Date(deadline).getTime() - Date.now();
  if (diff <= 0) return '마감됨';
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (h >= 24) return `${Math.floor(h / 24)}일 남음`;
  if (h > 0) return `${h}시간 ${m}분 남음`;
  return `${m}분 남음`;
}

export const DealHeader: React.FC<DealHeaderProps> = ({ deal }) => {
  const [timeLeft, setTimeLeft] = useState(() => calcTimeLeft(deal.deadline_at));
  const isOpen = deal.status === 'OPEN';
  const isUrgent = deal.deadline_at
    && new Date(deal.deadline_at).getTime() - Date.now() < 3 * 3600000;

  useEffect(() => {
    const id = setInterval(() => setTimeLeft(calcTimeLeft(deal.deadline_at)), 30000);
    return () => clearInterval(id);
  }, [deal.deadline_at]);

  return (
    <div style={{ padding: '16px 20px 12px' }}>
      {/* 상태 + 마감 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        {isOpen ? (
          <Badge variant="live">
            <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: 'var(--accent-green)', marginRight: 4 }} />
            LIVE
          </Badge>
        ) : (
          <Badge variant="closed">마감</Badge>
        )}
        {timeLeft && (
          <span style={{
            fontSize: 12,
            fontWeight: 600,
            color: isUrgent ? 'var(--accent-red)' : 'var(--text-muted)',
          }}>
            {isUrgent && '⚡ '}{timeLeft}
          </span>
        )}
      </div>

      {/* 상품명 */}
      <h1 style={{ fontSize: 20, fontWeight: 800, lineHeight: 1.3, color: 'var(--text-primary)', marginBottom: 8 }}>
        {deal.product_name}
      </h1>

      {/* 메타 정보 */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          {deal.brand && (
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600 }}>
              {deal.brand}
            </span>
          )}
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>·</span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{deal.category}</span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>·</span>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>참여자 {deal.participants_count}명</span>
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          👀 {deal.spectator_count}명 관전 중
        </span>
      </div>
    </div>
  );
};
