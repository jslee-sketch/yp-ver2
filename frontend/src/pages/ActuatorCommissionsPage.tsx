import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

interface CommissionItem {
  id: number;
  actuator_id: number;
  seller_id?: number;
  reservation_id?: number;
  gmv?: number;
  rate_percent?: number;
  amount: number;
  status: string;
  ready_at?: string;
  paid_at?: string;
  created_at: string;
}

interface CommSummary {
  pending_count: number;
  pending_total_amount: number;
  ready_count: number;
  ready_total_amount: number;
  paid_count: number;
  paid_total_amount: number;
}

function fmtP(n: number) { return '₩' + (n ?? 0).toLocaleString('ko-KR'); }
function fmtDate(s?: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

type FilterKey = '전체' | 'PENDING' | 'PAID';

export default function ActuatorCommissionsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [items, setItems] = useState<CommissionItem[]>([]);
  const [summary, setSummary] = useState<CommSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterKey>('전체');

  useEffect(() => {
    if (!user) return;
    const actuatorId = user.id;
    (async () => {
      try {
        const [commRes, summaryRes] = await Promise.all([
          apiClient.get(`/actuators/${actuatorId}/commissions`),
          apiClient.get(`/actuators/${actuatorId}/commissions/summary`),
        ]);
        setItems(Array.isArray(commRes.data) ? commRes.data : []);
        setSummary(summaryRes.data ?? null);
      } catch (err) {
        console.error('커미션 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  const filtered = filter === '전체' ? items : items.filter(c => c.status === filter);

  const statusMeta: Record<string, { label: string; color: string }> = {
    PENDING: { label: '대기', color: C.orange },
    PAID:    { label: '지급완료', color: C.green },
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>커미션 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 요약 */}
        {summary && (
          <div style={{
            background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
            padding: 14, marginBottom: 14,
          }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>커미션 요약</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div style={{ textAlign: 'center', padding: 10, background: `${C.orange}11`, borderRadius: 10 }}>
                <div style={{ fontSize: 10, color: C.textDim }}>정산 대기</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: C.orange }}>{fmtP(summary.pending_total_amount + summary.ready_total_amount)}</div>
                <div style={{ fontSize: 10, color: C.textDim }}>{summary.pending_count + summary.ready_count}건</div>
              </div>
              <div style={{ textAlign: 'center', padding: 10, background: `${C.green}11`, borderRadius: 10 }}>
                <div style={{ fontSize: 10, color: C.textDim }}>지급 완료</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: C.green }}>{fmtP(summary.paid_total_amount)}</div>
                <div style={{ fontSize: 10, color: C.textDim }}>{summary.paid_count}건</div>
              </div>
            </div>
          </div>
        )}

        {/* 필터 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {(['전체', 'PENDING', 'PAID'] as FilterKey[]).map(s => (
            <button key={s} onClick={() => setFilter(s)} style={{
              padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: filter === s ? `${C.green}22` : C.bgEl,
              border: `1px solid ${filter === s ? C.green : C.border}`,
              color: filter === s ? C.green : C.textSec,
              fontWeight: filter === s ? 700 : 400,
            }}>{s === '전체' ? s : (statusMeta[s]?.label ?? s)}</button>
          ))}
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>{filtered.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>💰</div>
            <div style={{ fontSize: 13 }}>커미션 내역이 없어요</div>
          </div>
        ) : filtered.map(c => {
          const meta = statusMeta[c.status] ?? statusMeta.PENDING;
          return (
            <div key={c.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${meta.color}`,
              borderRadius: 14, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: C.textSec }}>
                  커미션 #{c.id} · 예약 #{c.reservation_id ?? '-'}
                </span>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                  background: `${meta.color}22`, color: meta.color,
                }}>{meta.label}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 6 }}>
                <div>
                  <div style={{ fontSize: 10, color: C.textDim }}>거래액</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{fmtP(c.gmv ?? 0)}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: C.textDim }}>수수료율</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{c.rate_percent ?? '-'}%</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: C.textDim }}>커미션</div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.green }}>{fmtP(c.amount)}</div>
                </div>
              </div>
              <div style={{ fontSize: 10, color: C.textDim }}>
                판매자 #{c.seller_id ?? '-'} · {fmtDate(c.created_at)}
                {c.paid_at && <span style={{ color: C.green }}> · 지급 {fmtDate(c.paid_at)}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
