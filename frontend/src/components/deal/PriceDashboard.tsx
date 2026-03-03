import React from 'react';
import { PriceText } from '../common/PriceText';
import { ProgressBar } from '../common/ProgressBar';

interface PriceDashboardProps {
  anchorPrice: number | null;
  desiredPrice: number;
  lowestOfferPrice: number | null;
}

export const PriceDashboard: React.FC<PriceDashboardProps> = ({
  anchorPrice,
  desiredPrice,
  lowestOfferPrice,
}) => {
  const saving = anchorPrice && lowestOfferPrice ? anchorPrice - lowestOfferPrice : null;
  const savingPct = anchorPrice && saving ? Math.round((saving / anchorPrice) * 100) : null;
  const achieveRate = lowestOfferPrice
    ? Math.round((desiredPrice / lowestOfferPrice) * 100)
    : null;

  return (
    <div style={{
      margin: '0 16px 16px',
      padding: '16px',
      background: 'var(--gradient-price)',
      border: '1px solid var(--border-accent)',
      borderRadius: 'var(--radius-lg)',
    }}>
      {/* 3-column price row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
        {/* 시장가 */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4, fontWeight: 700 }}>
            📊 시장가
          </div>
          {anchorPrice != null ? (
            <PriceText amount={anchorPrice} size="heading-lg" color="var(--text-secondary)" />
          ) : (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>분석 중...</span>
          )}
        </div>

        {/* 목표가 */}
        <div style={{ textAlign: 'center', borderLeft: '1px solid var(--border-subtle)', borderRight: '1px solid var(--border-subtle)' }}>
          <div style={{ fontSize: 10, color: 'var(--accent-blue)', marginBottom: 4, fontWeight: 700 }}>
            🎯 목표가
          </div>
          <PriceText amount={desiredPrice} size="heading-lg" color="var(--accent-blue)" />
        </div>

        {/* 최저 오퍼 */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 10, color: 'var(--accent-green)', marginBottom: 4, fontWeight: 700 }}>
            ⚡ 최저 오퍼
          </div>
          {lowestOfferPrice != null ? (
            <PriceText amount={lowestOfferPrice} size="heading-lg" color="var(--accent-green)" />
          ) : (
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>없음</span>
          )}
        </div>
      </div>

      {/* 절약 배지 */}
      {saving != null && savingPct != null && saving > 0 && (
        <div style={{
          padding: '8px 12px',
          background: 'rgba(0,230,118,0.08)',
          border: '1px solid rgba(0,230,118,0.15)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: 12,
          textAlign: 'center',
        }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-green)' }}>
            🔥 시장가 대비 {saving.toLocaleString('ko-KR')}원 절약 ({savingPct}%↓)
          </span>
        </div>
      )}

      {/* 진행률 바 */}
      {achieveRate != null && (
        <ProgressBar
          value={achieveRate}
          label="목표 달성률"
          showLabel={true}
        />
      )}
    </div>
  );
};
