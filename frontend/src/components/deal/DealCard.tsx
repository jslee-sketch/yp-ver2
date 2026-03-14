import { useNavigate } from 'react-router-dom';
import { Badge } from '../common/Badge';
import { PriceText } from '../common/PriceText';
import { ProgressBar } from '../common/ProgressBar';
import type { Deal, Offer } from '../../types';

interface DealCardProps {
  deal: Deal;
  lowestOffer?: Offer | null;
}

export const DealCard: React.FC<DealCardProps> = ({ deal, lowestOffer }) => {
  const navigate = useNavigate();
  const savingPct = deal.anchor_price && lowestOffer
    ? Math.round(((deal.anchor_price - lowestOffer.price) / deal.anchor_price) * 100)
    : null;
  const achieveRate = lowestOffer
    ? Math.round((deal.desired_price / lowestOffer.price) * 100)
    : null;

  return (
    <div
      onClick={() => navigate(`/deal/${deal.id}`)}
      role="button"
      aria-label={`${deal.product_name} 딜 상세 보기`}
      style={{
        padding: '16px',
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        cursor: 'pointer',
        transition: 'background 0.2s ease, border-color 0.2s ease, transform 0.15s ease',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-elevated)'; e.currentTarget.style.transform = 'scale(1.015)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = 'var(--bg-secondary)'; e.currentTarget.style.transform = 'none'; }}
      onMouseDown={e => { e.currentTarget.style.transform = 'scale(0.98)'; }}
      onMouseUp={e => { e.currentTarget.style.transform = 'scale(1.015)'; }}
    >
      {/* 헤더 행 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            {deal.status === 'OPEN' ? (
              <Badge variant="live">
                <span style={{ display: 'inline-block', width: 5, height: 5, borderRadius: '50%', background: 'var(--accent-green)', marginRight: 3 }} />
                LIVE
              </Badge>
            ) : (
              <Badge variant="closed">마감</Badge>
            )}
            <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--accent-blue)', background: 'rgba(0,176,255,0.08)', padding: '1px 6px', borderRadius: 4 }}>
              #{deal.id}
            </span>
          </div>
          <h3 style={{
            fontSize: 15, fontWeight: 700, color: 'var(--text-primary)',
            lineHeight: 1.3, overflow: 'hidden',
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          }}>
            {deal.product_name}
          </h3>
          {deal.brand && (
            <span style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2, display: 'block' }}>
              {deal.brand}
            </span>
          )}
        </div>
      </div>

      {/* 가격 행: 목표가 + 시장가 → 최저 오퍼 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
        {deal.desired_price > 0 && (
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            목표 <span style={{ fontWeight: 700 }}>{deal.desired_price.toLocaleString('ko-KR')}원</span>
          </span>
        )}
        {(deal.anchor_price ?? 0) > 0 && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            시장 <PriceText amount={deal.anchor_price!} size="body-md" color="var(--text-muted)" strikethrough />
          </span>
        )}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        {lowestOffer && (
          <>
            <span style={{ fontSize: 16, marginRight: 2 }}>⚡</span>
            <PriceText amount={lowestOffer.price} size="heading-lg" color="var(--accent-green)" />
          </>
        )}
        {savingPct != null && savingPct > 0 && (
          <span style={{
            fontSize: 11, fontWeight: 700,
            color: 'var(--accent-green)', background: 'var(--accent-green-bg)',
            padding: '2px 6px', borderRadius: 4,
          }}>
            -{savingPct}%
          </span>
        )}
      </div>

      {/* 통계 행 */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>참여 {deal.participants_count}명</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>·</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>오퍼 {deal.offer_count ?? 0}개</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>·</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>👀 {deal.spectator_count}명 관전</span>
      </div>

      {/* 목표 달성률 프로그레스바 */}
      {achieveRate != null && (
        <ProgressBar value={achieveRate} showLabel height={5} />
      )}

      {/* 생성일 */}
      {deal.created_at && (
        <div style={{ fontSize: 11, color: 'var(--text-disabled)', marginTop: 8, textAlign: 'right' }}>
          {deal.created_at.split('T')[0]?.replace(/-/g, '.')}
        </div>
      )}
    </div>
  );
};
