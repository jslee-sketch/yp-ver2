import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

function fmtDate(s?: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

interface Dispute {
  id: number;
  reservation_id: number;
  order_number?: string;
  status: string;
  category?: string;
  filed_by_role?: string;
  round1_deadline?: string;
  round2_deadline?: string;
  resolution?: string;
  created_at: string;
  product_name?: string;
}

type FilterKey = '전체' | '진행중' | '해결' | '거절';

const statusMeta: Record<string, { label: string; color: string }> = {
  ROUND1_RESPONSE:  { label: '1차 진행', color: '#ff9100' },
  ROUND2_RESPONSE:  { label: '2차 진행', color: '#ff6d00' },
  AI_MEDIATION:     { label: 'AI 중재',  color: '#7c4dff' },
  ACCEPTED:         { label: '합의 완료', color: '#00e676' },
  REJECTED:         { label: '거절',     color: '#ff5252' },
  CLOSED:           { label: '종결',     color: '#78909c' },
};

export default function SellerDisputesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const sellerId = user?.seller?.id ?? user?.id ?? 0;

  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<FilterKey>('전체');

  useEffect(() => {
    if (!sellerId) return;
    (async () => {
      try {
        const resp = await apiClient.get('/disputes', { params: { user_id: sellerId } });
        const data = Array.isArray(resp.data) ? resp.data : (resp.data?.items ?? []);
        setDisputes(data.map((d: Record<string, unknown>) => ({
          id: d.id as number,
          reservation_id: (d.reservation_id as number) || 0,
          order_number: (d.order_number as string) || undefined,
          status: (d.status as string) || 'ROUND1_RESPONSE',
          category: (d.category as string) || undefined,
          filed_by_role: (d.filed_by_role as string) || undefined,
          round1_deadline: (d.round1_deadline as string) || undefined,
          round2_deadline: (d.round2_deadline as string) || undefined,
          resolution: (d.resolution as string) || undefined,
          created_at: (d.created_at as string) || '',
          product_name: (d.product_name as string) || undefined,
        })));
      } catch {
        setError('중재 목록을 불러오지 못했습니다.');
      } finally {
        setLoading(false);
      }
    })();
  }, [sellerId]);

  const isActive = (s: string) => ['ROUND1_RESPONSE', 'ROUND2_RESPONSE', 'AI_MEDIATION'].includes(s);
  const isResolved = (s: string) => ['ACCEPTED', 'CLOSED'].includes(s);

  const filtered = filter === '전체' ? disputes : disputes.filter(d => {
    if (filter === '진행중') return isActive(d.status);
    if (filter === '해결') return isResolved(d.status);
    if (filter === '거절') return d.status === 'REJECTED';
    return true;
  });

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>중재 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 안내 */}
        <div style={{
          background: 'rgba(255,152,0,0.08)', border: '1px solid rgba(255,152,0,0.2)',
          borderRadius: 12, padding: '12px 14px', marginBottom: 14, fontSize: 12, color: C.orange, lineHeight: 1.6,
        }}>
          중재는 구매자 또는 판매자가 신청할 수 있습니다. 1차(3영업일) → AI 중재 → 2차(2영업일) 순으로 진행되며, 기한 내 미응답 시 자동 종결됩니다.
        </div>

        {/* 필터 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {(['전체', '진행중', '해결', '거절'] as FilterKey[]).map(s => (
            <button key={s} onClick={() => setFilter(s)} style={{
              padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: filter === s ? `${C.green}22` : C.bgEl,
              border: `1px solid ${filter === s ? C.green : C.border}`,
              color: filter === s ? C.green : C.textSec,
              fontWeight: filter === s ? 700 : 400,
            }}>{s}</button>
          ))}
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>{filtered.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff5252' }}>
            <div style={{ fontSize: 13, marginBottom: 8 }}>{error}</div>
            <button onClick={() => window.location.reload()} style={{
              padding: '8px 16px', borderRadius: 8, fontSize: 12, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer',
            }}>재시도</button>
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>⚖️</div>
            <div style={{ fontSize: 13 }}>중재 내역이 없습니다</div>
          </div>
        ) : filtered.map(d => {
          const meta = statusMeta[d.status] || { label: d.status, color: '#888' };
          return (
            <div key={d.id} onClick={() => navigate(`/disputes/${d.id}`)} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${meta.color}`,
              borderRadius: 14, padding: '13px 14px', marginBottom: 8, cursor: 'pointer',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
                    {d.product_name || `중재 #${d.id}`}
                  </div>
                  <div style={{ fontSize: 11, color: C.textSec }}>
                    주문 {d.order_number || `#${d.reservation_id}`}
                    {d.category && <> · {d.category}</>}
                    {d.filed_by_role && <> · {d.filed_by_role === 'seller' ? '내가 신청' : '구매자 신청'}</>}
                  </div>
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                  background: `${meta.color}22`, color: meta.color, height: 'fit-content',
                }}>{meta.label}</span>
              </div>

              {isActive(d.status) && d.round1_deadline && (
                <div style={{ fontSize: 11, color: '#ff9100' }}>
                  응답 기한: {fmtDate(d.round1_deadline)}
                </div>
              )}
              {d.resolution && (
                <div style={{ fontSize: 11, color: C.green, marginTop: 2 }}>
                  해결: {d.resolution}
                </div>
              )}
              <div style={{ fontSize: 10, color: C.textDim, marginTop: 4 }}>{fmtDate(d.created_at)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
