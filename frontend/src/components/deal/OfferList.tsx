import React from 'react';
import { OfferCard } from './OfferCard';
import type { Offer } from '../../types';

interface OfferListProps {
  offers: Offer[];
  onSelect?: (offer: Offer) => void;
}

const TIER_LABEL: Record<string, string> = {
  PREMIUM: '⭐ PREMIUM',
  MATCHING: 'MATCHING',
  BELOW: 'BELOW',
};

export const OfferList: React.FC<OfferListProps> = ({ offers, onSelect }) => {
  const tiers = ['PREMIUM', 'MATCHING', 'BELOW'] as const;
  const byTier = Object.fromEntries(
    tiers.map(t => [t, offers.filter(o => o.tier === t)])
  );

  return (
    <div style={{ padding: '0 16px 16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)' }}>
          🏷️ 오퍼 {offers.length}개 경쟁 중
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {tiers.map(tier => {
          const group = byTier[tier];
          if (!group.length) return null;
          return (
            <div key={tier}>
              {/* 티어 구분선 */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 6,
                marginTop: tier !== 'PREMIUM' ? 8 : 0,
              }}>
                <span style={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: '1px',
                  color: tier === 'PREMIUM' ? 'var(--accent-green)'
                       : tier === 'MATCHING' ? 'var(--accent-blue)'
                       : 'var(--text-muted)',
                  textTransform: 'uppercase',
                }}>
                  {TIER_LABEL[tier]}
                </span>
                <div style={{ flex: 1, height: 1, background: 'var(--border-subtle)' }} />
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {group.map((offer, i) => (
                  <div key={offer.id} className="slide-in" style={{ animationDelay: `${i * 0.05}s` }}>
                    <OfferCard offer={offer} onSelect={onSelect} />
                  </div>
                ))}
              </div>
            </div>
          );
        })}

        {offers.length === 0 && (
          <div style={{
            padding: '32px 16px',
            textAlign: 'center',
            color: 'var(--text-muted)',
            fontSize: 13,
          }}>
            아직 오퍼가 없어요.<br />판매자들이 준비 중이에요! ⏳
          </div>
        )}
      </div>
    </div>
  );
};
