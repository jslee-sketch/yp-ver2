import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMyPredictions, fetchRankings } from '../api/spectatorApi';
import { useApiData } from '../api/hooks';
import type { SpectatorPrediction } from '../api/types';
import LoadingSkeleton from '../components/common/LoadingSkeleton';
import EmptyState from '../components/common/EmptyState';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
  cyan: '#00e5ff', yellow: '#ffe156',
};

const TIER_COLORS: Record<string, string> = {
  PERFECT: '#ffd600', EXCELLENT: '#00e676', GOOD: '#00b0ff', FAIR: '#ff9100', MISS: '#757575',
};

function fmtP(n: number) { return n.toLocaleString('ko-KR') + '원'; }
function fmtDate(s: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

interface RankEntry {
  rank: number;
  buyer_id: number;
  nickname: string;
  total_points: number;
  hits_count: number;
  predictions_count: number;
  hit_rate: number;
  badge?: string;
}

export default function SpectatingPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<'predictions' | 'rankings'>('predictions');

  const { data: predictions, loading: loadingP } = useApiData<SpectatorPrediction[]>(
    () => fetchMyPredictions(),
    [],
  );

  const { data: rankings, loading: loadingR } = useApiData<RankEntry[]>(
    () => fetchRankings() as Promise<RankEntry[]>,
    [],
  );

  const myPreds = predictions ?? [];
  const rankList = rankings ?? [];

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>관전 모드</span>
        <div style={{ width: 24 }} />
      </div>

      {/* 탭 */}
      <div style={{ display: 'flex', borderBottom: `1px solid ${C.border}` }}>
        {([['predictions', '내 예측'], ['rankings', '랭킹']] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              flex: 1, padding: '12px 0', fontSize: 13, fontWeight: tab === key ? 700 : 400,
              color: tab === key ? C.cyan : C.textDim,
              borderBottom: tab === key ? `2px solid ${C.cyan}` : '2px solid transparent',
              background: 'none', cursor: 'pointer',
            }}
          >{label}</button>
        ))}
      </div>

      <div style={{ padding: '14px 16px 0' }}>

        {/* 내 예측 탭 */}
        {tab === 'predictions' && (
          <>
            {loadingP && <LoadingSkeleton variant="cards" count={3} />}

            {!loadingP && (
              <>
                <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>
                  예측 {myPreds.length}건
                </div>

                {myPreds.length === 0 && (
                  <EmptyState
                    icon="👀"
                    message="아직 예측이 없어요"
                    sub="딜 상세에서 가격을 예측해보세요!"
                    actionLabel="딜 둘러보기 →"
                    onAction={() => navigate('/deals')}
                  />
                )}

            {myPreds.map(p => {
              const tierColor = TIER_COLORS[p.tier_name ?? ''] ?? C.textDim;
              return (
                <div
                  key={p.id}
                  onClick={() => navigate(`/deal/${p.deal_id}`)}
                  style={{
                    background: C.bgCard, border: `1px solid ${C.border}`,
                    borderLeft: `3px solid ${tierColor}`,
                    borderRadius: 14, padding: 14, marginBottom: 8, cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>딜 #{p.deal_id}</span>
                    {p.tier_label && (
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                        background: `${tierColor}22`, color: tierColor,
                      }}>{p.tier_label}</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontSize: 12, color: C.textSec }}>예측가</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{fmtP(p.predicted_price)}</span>
                  </div>
                  {p.settled_price != null && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <span style={{ fontSize: 12, color: C.textSec }}>실제가</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: C.green }}>{fmtP(p.settled_price)}</span>
                    </div>
                  )}
                  {p.error_pct != null && (
                    <div style={{ fontSize: 11, color: C.textDim }}>
                      오차: {p.error_pct.toFixed(1)}%
                      {p.points_earned ? ` · +${p.points_earned}P` : ''}
                    </div>
                  )}
                  <div style={{ fontSize: 10, color: C.textDim, marginTop: 4 }}>{fmtDate(p.created_at)}</div>
                </div>
              );
            })}
          </>
        )}
          </>
        )}

        {/* 랭킹 탭 */}
        {tab === 'rankings' && (
          <>
            {loadingR && <LoadingSkeleton variant="list" count={5} />}

            {!loadingR && rankList.length === 0 && (
              <EmptyState icon="🏆" message="아직 랭킹 데이터가 없어요" />
            )}

            {!loadingR && rankList.length > 0 && (
              <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>
                관전왕 랭킹
              </div>
            )}

            {rankList.map(r => {
              const medal = r.rank <= 3 ? ['🥇', '🥈', '🥉'][r.rank - 1] : `${r.rank}`;
              return (
                <div key={r.rank} style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  background: C.bgCard, border: `1px solid ${C.border}`,
                  borderRadius: 14, padding: '12px 14px', marginBottom: 8,
                }}>
                  <span style={{ fontSize: r.rank <= 3 ? 22 : 14, fontWeight: 800, width: 30, textAlign: 'center', color: r.rank <= 3 ? C.yellow : C.textDim }}>
                    {medal}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
                      {r.nickname || `유저#${r.buyer_id}`}
                      {r.badge && <span style={{ marginLeft: 6, fontSize: 11, color: C.yellow }}>{r.badge}</span>}
                    </div>
                    <div style={{ fontSize: 11, color: C.textSec }}>
                      적중 {r.hits_count}/{r.predictions_count} ({(r.hit_rate * 100).toFixed(0)}%)
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: C.green }}>{r.total_points.toLocaleString()}P</div>
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>
    </div>
  );
}
