import React, { useState } from 'react';
import { BarChart } from '../common/BarChart';
import type { SpectatorStats } from '../../types';

interface SpectatorPanelProps {
  stats: SpectatorStats;
  onPredict?: (price: number) => void;
}

function buildBuckets(avgPrice: number, count: number) {
  if (!avgPrice) return [];
  const base = Math.round(avgPrice / 1000) * 1000;
  const step = 3000;
  const centers = [base - 2 * step, base - step, base, base + step, base + 2 * step];
  const pcts = [12, 35, 28, 18, 7];
  return centers.map((c, i) => ({
    label: `${Math.round((c - step / 2) / 1000)}K+`,
    min: c - step / 2,
    max: c + step / 2,
    count: Math.round((count * pcts[i]) / 100),
    pct: pcts[i],
  }));
}

export const SpectatorPanel: React.FC<SpectatorPanelProps> = ({ stats, onPredict }) => {
  const [showInput, setShowInput] = useState(false);
  const [inputPrice, setInputPrice] = useState('');
  const hasMyPrediction = stats.my_prediction != null;

  const buckets = stats.buckets.length > 0
    ? stats.buckets
    : stats.avg_predicted_price
      ? buildBuckets(stats.avg_predicted_price, stats.total_count)
      : [];

  const handleSubmit = () => {
    const p = parseInt(inputPrice.replace(/,/g, ''), 10);
    if (p > 0 && onPredict) {
      onPredict(p);
      setShowInput(false);
    }
  };

  return (
    <div style={{
      margin: '0 16px 16px',
      padding: 16,
      background: 'var(--bg-tertiary)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-lg)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)' }}>
          🎯 관전자 예측 분포
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {stats.total_count}명
        </span>
      </div>

      {buckets.length > 0 ? (
        <BarChart
          buckets={buckets}
          avgPrice={stats.avg_predicted_price}
          myPrediction={stats.my_prediction}
        />
      ) : (
        <div style={{ textAlign: 'center', padding: '16px 0', color: 'var(--text-muted)', fontSize: 13 }}>
          아직 예측 데이터가 없어요
        </div>
      )}

      {/* 예측 입력/상태 */}
      <div style={{ marginTop: 14 }}>
        {hasMyPrediction ? (
          <div style={{
            padding: '8px 12px',
            background: 'rgba(0,176,255,0.08)',
            border: '1px solid rgba(0,176,255,0.2)',
            borderRadius: 'var(--radius-sm)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}>
            <span style={{ fontSize: 16 }}>✅</span>
            <span style={{ fontSize: 13, color: 'var(--accent-blue)' }}>
              내 예측: <strong>{stats.my_prediction!.toLocaleString('ko-KR')}원</strong>
            </span>
          </div>
        ) : showInput ? (
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              value={inputPrice}
              onChange={e => setInputPrice(e.target.value)}
              placeholder="예측가 입력 (원)"
              style={{
                flex: 1,
                padding: '10px 12px',
                fontSize: 14,
                background: 'var(--bg-elevated)',
                border: '1px solid var(--accent-blue)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
              }}
            />
            <button
              onClick={handleSubmit}
              style={{
                padding: '10px 16px',
                background: 'var(--accent-green)',
                color: '#0a0a0f',
                borderRadius: 'var(--radius-sm)',
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              제출
            </button>
            <button
              onClick={() => setShowInput(false)}
              style={{
                padding: '10px 12px',
                background: 'var(--bg-elevated)',
                color: 'var(--text-muted)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 13,
              }}
            >
              취소
            </button>
          </div>
        ) : (
          <button
            onClick={() => setShowInput(true)}
            style={{
              width: '100%',
              padding: '11px',
              background: 'rgba(0,230,118,0.08)',
              border: '1px solid rgba(0,230,118,0.2)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--accent-green)',
              fontSize: 13,
              fontWeight: 700,
            }}
          >
            🎯 나도 예측하기
          </button>
        )}
      </div>
    </div>
  );
};
