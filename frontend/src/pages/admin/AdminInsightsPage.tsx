import { useState, useEffect } from 'react';

const BASE = import.meta.env.VITE_API_BASE || '';

interface Trends {
  categories: { category: string; count: number }[];
  brands: { brand: string; count: number; avg_target: number }[];
  price_ranges: { label: string; count: number }[];
  hot_keywords: { word: string; count: number }[];
}

export default function AdminInsightsPage() {
  const [data, setData] = useState<Trends | null>(null);

  useEffect(() => {
    fetch(`${BASE}/v3_6/admin/insights/trends`)
      .then(r => r.json())
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) return <div style={{ padding: 40, color: '#888' }}>로딩 중...</div>;

  const maxCat = Math.max(...data.categories.map(c => c.count), 1);
  const maxBrand = Math.max(...data.brands.map(b => b.count), 1);

  return (
    <div style={{ padding: 20 }}>
      <h2 style={{ color: '#e0e0e0', fontSize: 20, marginBottom: 20 }}>금맥 인사이트</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        {/* Categories */}
        <div style={{ background: '#1a1a2e', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#f472b6', marginBottom: 12 }}>
            카테고리별 딜 수
          </div>
          {data.categories.map(c => (
            <div key={c.category} style={{ marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#ccc' }}>
                <span>{c.category}</span><span>{c.count}</span>
              </div>
              <div style={{ height: 6, background: '#333', borderRadius: 3, marginTop: 2 }}>
                <div style={{
                  height: '100%', borderRadius: 3, background: '#f472b6',
                  width: `${(c.count / maxCat) * 100}%`,
                }} />
              </div>
            </div>
          ))}
        </div>

        {/* Brands */}
        <div style={{ background: '#1a1a2e', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#4ade80', marginBottom: 12 }}>
            인기 브랜드 TOP 10
          </div>
          {data.brands.map(b => (
            <div key={b.brand} style={{ marginBottom: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#ccc' }}>
                <span>{b.brand}</span>
                <span>{b.count}건 | 평균 {b.avg_target.toLocaleString()}원</span>
              </div>
              <div style={{ height: 6, background: '#333', borderRadius: 3, marginTop: 2 }}>
                <div style={{
                  height: '100%', borderRadius: 3, background: '#4ade80',
                  width: `${(b.count / maxBrand) * 100}%`,
                }} />
              </div>
            </div>
          ))}
          {data.brands.length === 0 && <div style={{ fontSize: 12, color: '#666' }}>데이터 없음</div>}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Price Ranges */}
        <div style={{ background: '#1a1a2e', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#60a5fa', marginBottom: 12 }}>
            가격대별 분포
          </div>
          {data.price_ranges.map(p => (
            <div key={p.label} style={{
              display: 'flex', justifyContent: 'space-between',
              padding: '6px 0', borderBottom: '1px solid #222', fontSize: 13, color: '#ccc',
            }}>
              <span>{p.label}</span><span style={{ color: '#60a5fa' }}>{p.count}건</span>
            </div>
          ))}
        </div>

        {/* Hot Keywords */}
        <div style={{ background: '#1a1a2e', borderRadius: 12, padding: 16 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#f59e0b', marginBottom: 12 }}>
            핫 키워드 (최근 7일)
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {data.hot_keywords.map(k => (
              <span key={k.word} style={{
                padding: '4px 10px', borderRadius: 12,
                background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)',
                color: '#f59e0b', fontSize: Math.min(16, 10 + k.count * 2),
              }}>{k.word} ({k.count})</span>
            ))}
            {data.hot_keywords.length === 0 && <div style={{ fontSize: 12, color: '#666' }}>데이터 없음</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
