import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', cyan: '#00e5ff',
  orange: '#ff8c42', red: '#ff4444', purple: '#a855f7',
};

interface Stats {
  total_logs: number;
  total_profiles: number;
  today_logs: number;
  keywords: { keyword: string; count: number }[];
  actions: { action: string; count: number }[];
  categories: { category: string; count: number }[];
}

interface Profile {
  id: number;
  user_type: string;
  user_id: number;
  profile: Record<string, unknown>;
  analyzed_at: string | null;
  behavior_count: number;
}

interface HesitatingBuyer {
  user_id: number;
  view_count: number;
  interests: { name: string; count: number }[];
  last_activity: string | null;
}

interface SkipPattern {
  reason: string;
  count: number;
  insight: string;
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 style={{
      fontSize: 14, fontWeight: 700, color: C.cyan, margin: '24px 0 12px',
      display: 'flex', alignItems: 'center', gap: 8,
    }}>
      {children}
      <div style={{ flex: 1, height: 1, background: C.border }} />
    </h3>
  );
}

function StatCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{
      background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12,
      padding: '16px 14px', textAlign: 'center', minWidth: 0,
    }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: color || C.cyan, fontFamily: "'Space Mono', monospace" }}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      <div style={{ fontSize: 11, color: C.textDim, marginTop: 4 }}>{label}</div>
    </div>
  );
}

function ActionButton({ label, onClick, loading, color }: {
  label: string; onClick: () => void; loading?: boolean; color?: string;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      style={{
        padding: '8px 18px', borderRadius: 10, fontSize: 12, fontWeight: 700,
        background: `${color || C.cyan}22`, border: `1px solid ${color || C.cyan}66`,
        color: color || C.cyan, cursor: loading ? 'wait' : 'pointer',
        opacity: loading ? 0.6 : 1,
      }}
    >
      {loading ? '...' : label}
    </button>
  );
}

export default function AdminMinorityReportPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [buyerProfiles, setBuyerProfiles] = useState<Profile[]>([]);
  const [sellerProfiles, setSellerProfiles] = useState<Profile[]>([]);
  const [hesitating, setHesitating] = useState<HesitatingBuyer[]>([]);
  const [skipPatterns, setSkipPatterns] = useState<{ total_skips: number; patterns: SkipPattern[] }>({ total_skips: 0, patterns: [] });
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [matching, setMatching] = useState(false);
  const [matchingSellers, setMatchingSellers] = useState(false);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [statsRes, buyerRes, sellerRes, hesRes, skipRes] = await Promise.all([
        apiClient.get(API.BEHAVIOR.STATS).catch(() => ({ data: null })),
        apiClient.get(API.BEHAVIOR.PROFILES, { params: { user_type: 'BUYER', limit: 10 } }).catch(() => ({ data: [] })),
        apiClient.get(API.BEHAVIOR.PROFILES, { params: { user_type: 'SELLER', limit: 10 } }).catch(() => ({ data: [] })),
        apiClient.get(API.BEHAVIOR.HESITATING).catch(() => ({ data: [] })),
        apiClient.get(API.BEHAVIOR.SELLER_SKIP_PATTERNS).catch(() => ({ data: { total_skips: 0, patterns: [] } })),
      ]);
      if (statsRes.data) setStats(statsRes.data);
      setBuyerProfiles(Array.isArray(buyerRes.data) ? buyerRes.data : []);
      setSellerProfiles(Array.isArray(sellerRes.data) ? sellerRes.data : []);
      setHesitating(Array.isArray(hesRes.data) ? hesRes.data : []);
      setSkipPatterns(skipRes.data || { total_skips: 0, patterns: [] });
    } catch (err) {
      console.error('Minority report load failed:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const handleAnalyzeAll = async () => {
    setAnalyzing(true);
    try {
      await apiClient.post(API.BEHAVIOR.ANALYZE_ALL);
      await fetchAll();
    } catch { /* */ }
    setAnalyzing(false);
  };

  const handleMatchBuyers = async () => {
    setMatching(true);
    try {
      const res = await apiClient.post(API.BEHAVIOR.MATCH_DEALS);
      alert(`매칭 완료: ${res.data?.matched ?? 0}건, 알림 ${res.data?.notifications_sent ?? 0}건`);
    } catch { /* */ }
    setMatching(false);
  };

  const handleMatchSellers = async () => {
    setMatchingSellers(true);
    try {
      const res = await apiClient.post(API.BEHAVIOR.MATCH_SELLERS);
      alert(`판매자 매칭: ${res.data?.matched ?? 0}건, 알림 ${res.data?.notifications_sent ?? 0}건`);
    } catch { /* */ }
    setMatchingSellers(false);
  };

  if (loading) {
    return (
      <div style={{ padding: 32, textAlign: 'center', color: C.textDim }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>...</div>
        <div>마이너리티 리포트를 불러오는 중...</div>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px 24px', maxWidth: 1000, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 22, fontWeight: 800, color: C.text, margin: 0 }}>
          마이너리티 리포트
        </h2>
        <p style={{ fontSize: 12, color: C.textDim, margin: '4px 0 0' }}>
          구매 전 예측 &middot; 행동 분석 &middot; 자동 매칭
        </p>
      </div>

      {/* Action buttons */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        <ActionButton label="전체 분석 실행" onClick={handleAnalyzeAll} loading={analyzing} color={C.purple} />
        <ActionButton label="구매자 매칭 알림" onClick={handleMatchBuyers} loading={matching} color={C.green} />
        <ActionButton label="판매자 매칭 알림" onClick={handleMatchSellers} loading={matchingSellers} color={C.orange} />
        <ActionButton label="새로고침" onClick={fetchAll} color={C.cyan} />
      </div>

      {/* 1. Summary stats */}
      <SectionTitle>전체 요약</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10 }}>
        <StatCard label="총 행동 로그" value={stats?.total_logs ?? 0} />
        <StatCard label="AI 프로파일" value={stats?.total_profiles ?? 0} color={C.purple} />
        <StatCard label="오늘 수집" value={stats?.today_logs ?? 0} color={C.green} />
        <StatCard label="검색 키워드" value={stats?.keywords?.length ?? 0} color={C.orange} />
      </div>

      {/* 2. Popular keywords */}
      <SectionTitle>인기 검색 키워드</SectionTitle>
      {stats?.keywords && stats.keywords.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {stats.keywords.slice(0, 15).map((kw, i) => (
            <span key={i} style={{
              padding: '5px 12px', borderRadius: 20, fontSize: 12, fontWeight: i < 3 ? 700 : 400,
              background: i < 3 ? `${C.cyan}22` : C.bgEl,
              border: `1px solid ${i < 3 ? C.cyan + '66' : C.border}`,
              color: i < 3 ? C.cyan : C.textSec,
            }}>
              {kw.keyword} <span style={{ color: C.textDim, fontSize: 10 }}>({kw.count})</span>
            </span>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: C.textDim, padding: '8px 0' }}>
          아직 검색 데이터가 없습니다.
        </div>
      )}

      {/* 3. Category distribution */}
      <SectionTitle>인기 카테고리</SectionTitle>
      {stats?.categories && stats.categories.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {stats.categories.slice(0, 8).map((cat, i) => {
            const maxCount = stats.categories[0]?.count || 1;
            return (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ width: 80, fontSize: 12, color: C.textSec, textAlign: 'right', flexShrink: 0 }}>
                  {cat.category}
                </span>
                <div style={{ flex: 1, height: 18, background: C.bgEl, borderRadius: 4, overflow: 'hidden' }}>
                  <div style={{
                    width: `${Math.round((cat.count / maxCount) * 100)}%`, height: '100%',
                    background: `linear-gradient(90deg, ${C.cyan}88, ${C.green}88)`, borderRadius: 4,
                    display: 'flex', alignItems: 'center', paddingLeft: 6,
                  }}>
                    <span style={{ fontSize: 10, color: '#fff', fontWeight: 700 }}>{cat.count}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: C.textDim, padding: '8px 0' }}>카테고리 데이터 없음</div>
      )}

      {/* 4. Hesitating buyers */}
      <SectionTitle>망설이는 구매자</SectionTitle>
      {hesitating.length > 0 ? (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['구매자', '관심 상품', '조회수', '마지막 활동'].map(h => (
                  <th key={h} style={{ padding: '8px 6px', textAlign: 'left', color: C.textDim, fontWeight: 600, fontSize: 11 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {hesitating.slice(0, 15).map(b => (
                <tr key={b.user_id} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={{ padding: '8px 6px', color: C.cyan, fontWeight: 700 }}>B-{b.user_id}</td>
                  <td style={{ padding: '8px 6px', color: C.textSec }}>
                    {b.interests.map(i => i.name).join(', ') || '-'}
                  </td>
                  <td style={{ padding: '8px 6px', color: C.orange, fontWeight: 700 }}>{b.view_count}</td>
                  <td style={{ padding: '8px 6px', color: C.textDim, fontSize: 11 }}>
                    {b.last_activity ? new Date(b.last_activity).toLocaleDateString('ko-KR') : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: C.textDim, padding: '8px 0' }}>아직 망설이는 구매자 데이터가 없습니다.</div>
      )}

      {/* 5. Buyer profiles TOP 10 */}
      <SectionTitle>구매자 프로파일 TOP 10</SectionTitle>
      {buyerProfiles.length > 0 ? (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['구매자', '유형', '관심사', '가격대', '구매의지', '로그수'].map(h => (
                  <th key={h} style={{ padding: '8px 6px', textAlign: 'left', color: C.textDim, fontWeight: 600, fontSize: 11 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {buyerProfiles.map(p => {
                const pr = p.profile as Record<string, unknown>;
                return (
                  <tr key={p.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: '8px 6px', color: C.cyan, fontWeight: 700 }}>B-{p.user_id}</td>
                    <td style={{ padding: '8px 6px', color: C.textSec }}>{String(pr.type || '-')}</td>
                    <td style={{ padding: '8px 6px', color: C.textSec, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {Array.isArray(pr.interests) ? (pr.interests as string[]).join(', ') : '-'}
                    </td>
                    <td style={{ padding: '8px 6px', color: C.textSec }}>{String(pr.price_range || '-')}</td>
                    <td style={{ padding: '8px 6px', color: pr.purchase_intent === '높음' ? C.green : C.textDim, fontWeight: 700 }}>
                      {String(pr.purchase_intent || '-')}
                    </td>
                    <td style={{ padding: '8px 6px', color: C.textDim }}>{p.behavior_count}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: C.textDim, padding: '8px 0' }}>구매자 프로파일이 없습니다. [전체 분석 실행]을 눌러주세요.</div>
      )}

      {/* 6. Seller profiles TOP 10 */}
      <SectionTitle>판매자 프로파일 TOP 10</SectionTitle>
      {sellerProfiles.length > 0 ? (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['판매자', '패턴', '강점 분야', '낙찰률', '발송속도', '위험도', '성장'].map(h => (
                  <th key={h} style={{ padding: '8px 6px', textAlign: 'left', color: C.textDim, fontWeight: 600, fontSize: 11 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sellerProfiles.map(p => {
                const pr = p.profile as Record<string, unknown>;
                return (
                  <tr key={p.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: '8px 6px', color: C.orange, fontWeight: 700 }}>S-{p.user_id}</td>
                    <td style={{ padding: '8px 6px', color: C.textSec }}>{String(pr.pattern || '-')}</td>
                    <td style={{ padding: '8px 6px', color: C.textSec, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {Array.isArray(pr.strength_areas) ? (pr.strength_areas as string[]).join(', ') : '-'}
                    </td>
                    <td style={{ padding: '8px 6px', color: C.textSec }}>{String(pr.win_rate_estimate || '-')}</td>
                    <td style={{ padding: '8px 6px', color: C.textSec }}>{String(pr.shipping_speed || '-')}</td>
                    <td style={{ padding: '8px 6px', color: pr.risk_level === '높음' ? C.red : C.textDim, fontWeight: 700 }}>
                      {String(pr.risk_level || '-')}
                    </td>
                    <td style={{ padding: '8px 6px', color: pr.growth_potential === '높음' ? C.green : C.textDim }}>
                      {String(pr.growth_potential || '-')}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: C.textDim, padding: '8px 0' }}>판매자 프로파일이 없습니다.</div>
      )}

      {/* 7. Seller skip patterns */}
      <SectionTitle>판매자 스킵 패턴 분석</SectionTitle>
      {skipPatterns.patterns.length > 0 ? (
        <div>
          <div style={{ fontSize: 11, color: C.textDim, marginBottom: 8 }}>
            총 스킵: {skipPatterns.total_skips}건
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {['스킵 사유', '건수', '인사이트'].map(h => (
                    <th key={h} style={{ padding: '8px 6px', textAlign: 'left', color: C.textDim, fontWeight: 600, fontSize: 11 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {skipPatterns.patterns.map((p, i) => (
                  <tr key={i} style={{ borderBottom: `1px solid ${C.border}` }}>
                    <td style={{ padding: '8px 6px', color: C.textSec }}>{p.reason}</td>
                    <td style={{ padding: '8px 6px', color: C.orange, fontWeight: 700 }}>{p.count}</td>
                    <td style={{ padding: '8px 6px', color: C.textDim, fontSize: 11 }}>{p.insight}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: C.textDim, padding: '8px 0' }}>스킵 패턴 데이터 없음</div>
      )}

      {/* 8. Action distribution */}
      <SectionTitle>행동 분포</SectionTitle>
      {stats?.actions && stats.actions.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {stats.actions.map((a, i) => (
            <span key={i} style={{
              padding: '4px 10px', borderRadius: 16, fontSize: 11,
              background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec,
            }}>
              {a.action} <span style={{ color: C.cyan, fontWeight: 700 }}>({a.count})</span>
            </span>
          ))}
        </div>
      ) : (
        <div style={{ fontSize: 12, color: C.textDim, padding: '8px 0' }}>행동 데이터 없음</div>
      )}

      <div style={{ height: 60 }} />
    </div>
  );
}
