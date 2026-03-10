import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchMySettlements } from '../api/settlementApi';
import { useApiData } from '../api/hooks';
import type { Settlement } from '../api/types';
import LoadingSkeleton from '../components/common/LoadingSkeleton';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
  blue: 'var(--accent-blue)', yellow: '#ffe156',
};

const STATUS_META: Record<string, { label: string; color: string }> = {
  HOLD:     { label: '보류',   color: '#ff9100' },
  READY:    { label: '정산가능', color: '#00b0ff' },
  APPROVED: { label: '승인',   color: '#00e676' },
  PAID:     { label: '지급완료', color: '#78909c' },
};

function fmtP(n: number) { return n.toLocaleString('ko-KR') + '원'; }
function fmtDate(s: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

export default function SettlementsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const { data: settlements, loading, error, refetch } = useApiData<Settlement[]>(
    () => fetchMySettlements(user?.seller?.id),
    [user?.seller?.id],
  );

  const items = settlements ?? [];

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>정산내역</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 요약 카드 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`, borderTop: `3px solid ${C.green}`,
          borderRadius: 16, padding: 16, marginBottom: 16,
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div style={{ textAlign: 'center', padding: '10px 6px', background: C.bgEl, borderRadius: 10 }}>
              <div style={{ fontSize: 10, color: C.textDim, marginBottom: 4 }}>총 정산액</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: C.green }}>
                {fmtP(items.reduce((s, i) => s + i.net_amount, 0))}
              </div>
            </div>
            <div style={{ textAlign: 'center', padding: '10px 6px', background: C.bgEl, borderRadius: 10 }}>
              <div style={{ fontSize: 10, color: C.textDim, marginBottom: 4 }}>건수</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>{items.length}건</div>
            </div>
          </div>
        </div>

        {loading && <LoadingSkeleton variant="list" count={4} />}
        {!loading && error && <ErrorMessage message={error} onRetry={refetch} />}

        {!loading && !error && (
          <>
            <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>
              정산 {items.length}건
            </div>

            {items.length === 0 && (
              <EmptyState icon="💰" message="아직 정산 내역이 없어요" />
            )}

        {items.map(s => {
          const meta = STATUS_META[s.status] ?? STATUS_META.HOLD;
          return (
            <div key={s.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${meta.color}`,
              borderRadius: 14, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: C.blue, background: 'rgba(0,176,255,0.08)', padding: '1px 6px', borderRadius: 4 }}>
                    S-{s.id}
                  </span>
                  <span
                    onClick={() => navigate(`/my-orders`)}
                    style={{ fontSize: 11, color: C.blue, cursor: 'pointer', textDecoration: 'underline' }}
                  >예약 #{s.reservation_id}</span>
                  {s.deal_id && (
                    <span
                      onClick={() => navigate(`/deal/${s.deal_id}`)}
                      style={{ fontSize: 11, color: C.blue, cursor: 'pointer', textDecoration: 'underline' }}
                    >딜 #{s.deal_id}</span>
                  )}
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                  background: `${meta.color}22`, color: meta.color,
                }}>{meta.label}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 6 }}>
                <div>
                  <div style={{ fontSize: 10, color: C.textDim }}>총액</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{fmtP(s.gross_amount)}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: C.textDim }}>수수료</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.orange }}>{fmtP(s.platform_fee)}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: C.textDim }}>정산액</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.green }}>{fmtP(s.net_amount)}</div>
                </div>
              </div>
              <div style={{ fontSize: 10, color: C.textDim }}>
                생성: {fmtDate(s.created_at)}
                {s.paid_at ? ` · 지급: ${fmtDate(s.paid_at)}` : ''}
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
