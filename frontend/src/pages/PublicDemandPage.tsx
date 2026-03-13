// 공개 수요 대시보드 — /demand (로그인 불필요)
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import apiClient from '../api/client';

export default function PublicDemandPage() {
  const [data, setData] = useState<any>(null);
  const [filter, setFilter] = useState('');

  const load = () => {
    apiClient.get('/public/demand').then(r => setData(r.data)).catch(() => {});
  };

  useEffect(() => {
    // SEO 메타
    document.title = '지금 사람들이 찾는 것들 — 역핑 공동구매';
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', '에어팟, 갤럭시, 다이슨 등 실시간 공동구매 수요. 역핑에서 원하는 가격에 찾아드려요.');

    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  if (!data) return <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>로딩 중...</div>;

  const filtered = filter
    ? data.top_demands.filter((d: any) => d.category === filter)
    : data.top_demands;

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 20 }}>
      {/* 타이틀 */}
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
        style={{ textAlign: 'center', marginBottom: 32 }}>
        <h1 style={{ color: '#f472b6', fontSize: 32, marginBottom: 8 }}>
          지금 사람들이 찾는 것들
        </h1>
        <p style={{ color: '#888', fontSize: 16 }}>
          역핑에서 구매자들이 실시간으로 찾고 있는 상품들
        </p>
      </motion.div>

      {/* 통계 카드 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
        {[
          { val: data.stats.total_active_deals, label: '활성 수요', color: '#f472b6' },
          { val: `${data.stats.total_buyers_30d}명`, label: '이번 달 구매자', color: '#4ade80' },
          { val: `${data.stats.total_completed}건`, label: '거래 성사', color: '#60a5fa' },
        ].map((s, i) => (
          <motion.div key={i} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.1 }}
            style={{ background: '#1a1a2e', borderRadius: 12, padding: 20, textAlign: 'center' }}>
            <div style={{ color: s.color, fontSize: 28, fontWeight: 'bold' }}>{s.val}</div>
            <div style={{ color: '#888', fontSize: 13 }}>{s.label}</div>
          </motion.div>
        ))}
      </div>

      {/* 판매자 CTA 배너 */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}
        style={{
          background: 'linear-gradient(135deg, #f472b620, #4ade8020)',
          border: '1px solid #f472b650', borderRadius: 16, padding: 24, marginBottom: 24, textAlign: 'center',
        }}>
        <div style={{ fontSize: 20, fontWeight: 'bold', color: '#e0e0e0', marginBottom: 8 }}>
          이 수요, 당신이 채울 수 있어요!
        </div>
        <div style={{ color: '#888', fontSize: 14, marginBottom: 16 }}>
          입점 수수료 0원 (3개월) · 구매자가 먼저 기다리고 있어요
        </div>
        <a href="/register?role=seller" style={{
          display: 'inline-block', padding: '14px 32px', borderRadius: 12,
          background: '#f472b6', color: '#fff', textDecoration: 'none', fontWeight: 'bold', fontSize: 16,
        }}>판매자로 시작하기 →</a>
      </motion.div>

      {/* 카테고리 필터 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <button onClick={() => setFilter('')}
          style={{
            padding: '6px 14px', borderRadius: 20,
            background: !filter ? '#f472b620' : '#1a1a2e',
            border: `1px solid ${!filter ? '#f472b6' : '#2a2a4a'}`,
            color: !filter ? '#f472b6' : '#888', cursor: 'pointer', fontSize: 13,
          }}>전체</button>
        {(data.categories || []).map((c: any) => (
          <button key={c.category} onClick={() => setFilter(c.category)}
            style={{
              padding: '6px 14px', borderRadius: 20,
              background: filter === c.category ? '#f472b620' : '#1a1a2e',
              border: `1px solid ${filter === c.category ? '#f472b6' : '#2a2a4a'}`,
              color: filter === c.category ? '#f472b6' : '#888', cursor: 'pointer', fontSize: 13,
            }}>
            {c.category} ({c.count})
          </button>
        ))}
      </div>

      {/* 수요 목록 */}
      {filtered.length === 0 && (
        <div style={{ textAlign: 'center', padding: 40, color: '#666' }}>아직 수요가 없습니다. 첫 번째 딜을 만들어보세요!</div>
      )}
      {filtered.map((d: any, i: number) => (
        <motion.div key={d.id} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
          style={{
            background: '#1a1a2e', borderRadius: 12, padding: 16, marginBottom: 8,
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%', flexShrink: 0,
            background: i === 0 ? '#f59e0b' : i === 1 ? '#94a3b8' : i === 2 ? '#cd7f32' : '#2a2a4a',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: i < 3 ? '#000' : '#888', fontWeight: 'bold', fontSize: 14,
          }}>{i + 1}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ color: '#e0e0e0', fontWeight: 'bold', marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {d.title}
            </div>
            <div style={{ color: '#888', fontSize: 12 }}>
              {d.brand && `${d.brand} · `}{d.category} · {d.days_ago === 0 ? '오늘' : `${d.days_ago}일 전`}
            </div>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            <div style={{ color: '#f472b6', fontWeight: 'bold', fontSize: 16 }}>{d.demand_count}명</div>
            {d.target_price > 0 && (
              <div style={{ color: '#888', fontSize: 12 }}>
                목표 {d.target_price >= 10000 ? `${(d.target_price / 10000).toFixed(0)}만원` : `${d.target_price.toLocaleString()}원`}
              </div>
            )}
          </div>
        </motion.div>
      ))}

      {/* 최근 성사 사례 */}
      {data.recent_successes.length > 0 && (
        <div style={{ marginTop: 32 }}>
          <h2 style={{ color: '#e0e0e0', fontSize: 18, marginBottom: 12 }}>최근 거래 성사</h2>
          {data.recent_successes.map((s: any, i: number) => (
            <div key={i} style={{
              background: '#4ade8010', borderRadius: 8, padding: 12, marginBottom: 4,
              display: 'flex', justifyContent: 'space-between',
            }}>
              <span style={{ color: '#e0e0e0' }}>{s.title}</span>
              <span style={{ color: '#4ade80', fontWeight: 'bold' }}>
                {s.savings_pct && s.savings_pct > 0 ? `${s.savings_pct}% 절약!` : '성사'}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 하단 CTA */}
      <div style={{ marginTop: 32, padding: 24, textAlign: 'center', background: '#1a1a2e', borderRadius: 16 }}>
        <div style={{ color: '#888', marginBottom: 12 }}>구매자라면? 원하는 가격에 찾아드려요!</div>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'center', flexWrap: 'wrap' }}>
          <a href="/register?role=buyer" style={{
            padding: '12px 24px', borderRadius: 10, background: '#4ade80', color: '#000',
            textDecoration: 'none', fontWeight: 'bold',
          }}>구매자로 가입</a>
          <a href="/register?role=seller" style={{
            padding: '12px 24px', borderRadius: 10, background: '#f472b6', color: '#fff',
            textDecoration: 'none', fontWeight: 'bold',
          }}>판매자로 입점</a>
        </div>
      </div>

      {/* SEO 푸터 */}
      <div style={{ marginTop: 24, color: '#555', fontSize: 11, textAlign: 'center', lineHeight: 1.8 }}>
        역핑 | 공동구매 플랫폼 | AI 기반 가격 매칭<br />
        에어팟 공동구매 · 갤럭시 공동구매 · 아이폰 공동구매 · 다이슨 공동구매<br />
        © 2026 (주)텔러스테크
      </div>
    </div>
  );
}
