import React from 'react';
import type { PredictionBucket } from '../../types';

interface BarChartProps {
  buckets: PredictionBucket[];
  avgPrice?: number | null;
  myPrediction?: number | null;
  height?: number;
}

export const BarChart: React.FC<BarChartProps> = ({
  buckets,
  avgPrice,
  myPrediction,
  height = 60,
}) => {
  if (!buckets.length) return null;
  const maxPct = Math.max(...buckets.map(b => b.pct));

  return (
    <div style={{ width: '100%' }}>
      {/* 막대 그래프 */}
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height, marginBottom: 6 }}>
        {buckets.map((bucket, i) => {
          const barH = maxPct > 0 ? (bucket.pct / maxPct) * height : 0;
          const isMax = bucket.pct === maxPct;
          const isMyRange = myPrediction != null
            && myPrediction >= bucket.min && myPrediction < bucket.max;

          return (
            <div
              key={i}
              title={`${bucket.label}: ${bucket.pct}%`}
              style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 2,
              }}
            >
              <span style={{ fontSize: 9, color: 'var(--text-muted)', lineHeight: 1 }}>
                {bucket.pct}%
              </span>
              <div
                className="bar-animate"
                style={{
                  width: '100%',
                  height: barH,
                  borderRadius: '4px 4px 0 0',
                  background: isMyRange
                    ? 'var(--accent-blue)'
                    : isMax
                      ? 'var(--accent-green)'
                      : 'var(--bg-elevated)',
                  border: isMax ? '1px solid rgba(0,230,118,0.4)' : 'none',
                  position: 'relative',
                  transition: 'height 0.5s ease-out',
                }}
              />
            </div>
          );
        })}
      </div>

      {/* 라벨 */}
      <div style={{ display: 'flex', gap: 3 }}>
        {buckets.map((bucket, i) => (
          <div key={i} style={{ flex: 1, textAlign: 'center' }}>
            <span style={{ fontSize: 9, color: 'var(--text-muted)', lineHeight: 1.2 }}>
              {bucket.label}
            </span>
          </div>
        ))}
      </div>

      {/* 평균 / 내 예측 */}
      <div style={{ display: 'flex', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>
        {avgPrice != null && (
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            평균 예측가:&nbsp;
            <strong style={{ color: 'var(--text-primary)' }}>
              {avgPrice.toLocaleString('ko-KR')}원
            </strong>
          </span>
        )}
        {myPrediction != null && (
          <span style={{ fontSize: 12, color: 'var(--accent-blue)' }}>
            내 예측: <strong>{myPrediction.toLocaleString('ko-KR')}원</strong>
          </span>
        )}
      </div>
    </div>
  );
};
