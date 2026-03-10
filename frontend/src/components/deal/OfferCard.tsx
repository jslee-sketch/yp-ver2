import React from 'react';
import { Badge } from '../common/Badge';
import { PriceText } from '../common/PriceText';
import type { Offer } from '../../types';

interface OfferCardProps {
  offer: Offer;
  onSelect?: (offer: Offer) => void;
}

export const OfferCard: React.FC<OfferCardProps> = ({ offer, onSelect }) => {
  const isPremium = offer.tier === 'PREMIUM';
  const isBelow = offer.tier === 'BELOW';

  return (
    <div
      style={{
        padding: '14px 16px',
        background: isPremium
          ? 'rgba(0,230,118,0.04)'
          : 'var(--bg-tertiary)',
        border: `1px solid ${isPremium ? 'rgba(0,230,118,0.2)' : 'var(--border-subtle)'}`,
        borderRadius: 'var(--radius-md)',
        opacity: isBelow ? 0.75 : 1,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        {/* 왼쪽: 배지 + 오퍼번호 + 셀러명 */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
            {isPremium && (
              <Badge variant="premium" className="slide-in" style={{ display: 'inline-block' }}>
                PREMIUM
              </Badge>
            )}
            {offer.tier === 'MATCHING' && (
              <Badge variant="matching" style={{ display: 'inline-block' }}>
                MATCHING
              </Badge>
            )}
            <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-muted)', background: 'var(--bg-elevated)', padding: '1px 5px', borderRadius: 3 }}>
              Offer #{offer.id}
            </span>
          </div>
          <div style={{
            fontSize: 14,
            fontWeight: 700,
            color: isBelow ? 'var(--text-muted)' : 'var(--text-primary)',
          }}>
            {offer.seller_name}
          </div>
        </div>

        {/* 오른쪽: 가격 + 버튼 */}
        <div style={{ textAlign: 'right' }}>
          <PriceText
            amount={offer.price}
            size="display-sm"
            color={isPremium ? 'var(--accent-green)' : isBelow ? 'var(--text-muted)' : 'var(--text-primary)'}
          />
          <div style={{ marginTop: 6 }}>
            <button
              onClick={() => onSelect?.(offer)}
              style={{
                padding: '6px 14px',
                background: isPremium ? 'var(--accent-green)' : 'var(--bg-elevated)',
                color: isPremium ? '#0a0a0f' : 'var(--text-primary)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              선택하기
            </button>
          </div>
        </div>
      </div>

      {/* 조건 정보 */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          ⭐ {offer.rating} ({offer.review_count.toLocaleString('ko-KR')})
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>·</span>
        <span style={{ fontSize: 11, color: offer.shipping_fee === 0 ? 'var(--accent-green)' : 'var(--text-muted)' }}>
          📦 {offer.shipping_fee === 0 ? '무료배송' : `${offer.shipping_fee.toLocaleString('ko-KR')}원`}
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>·</span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {offer.delivery_days}일
        </span>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>·</span>
        <span style={{ fontSize: 11, color: offer.warranty_months > 0 ? 'var(--text-muted)' : 'var(--text-disabled)' }}>
          {offer.warranty_months > 0 ? `${offer.warranty_months}개월 보증` : '보증없음'}
        </span>
      </div>
    </div>
  );
};
