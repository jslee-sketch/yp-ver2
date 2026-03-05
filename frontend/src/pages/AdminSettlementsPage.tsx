import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { showToast } from '../components/common/Toast';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

const STATUS_META: Record<string, { label: string; color: string }> = {
  PENDING:  { label: '대기',     color: '#78909c' },
  HOLD:     { label: '보류',     color: '#ff9100' },
  READY:    { label: '정산가능', color: '#00b0ff' },
  APPROVED: { label: '승인',     color: '#00e676' },
  PAID:     { label: '지급완료', color: '#78909c' },
};

interface SettlementItem {
  id: number;
  reservation_id: number;
  seller_id: number;
  buyer_paid_amount: number;
  platform_commission_amount: number;
  seller_payout_amount: number;
  status: string;
  block_reason?: string;
  ready_at?: string;
  approved_at?: string;
  paid_at?: string;
  created_at: string;
}

function fmtP(n: number) { return '₩' + (n ?? 0).toLocaleString('ko-KR'); }
function fmtDate(s?: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

export default function AdminSettlementsPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<SettlementItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('전체');

  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.get('/settlements/', { params: { limit: 200 } });
        setItems((res.data ?? []) as SettlementItem[]);
      } catch (err) {
        console.error('정산 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleApprove = async (id: number) => {
    try {
      await apiClient.post(`/settlements/${id}/approve`);
      setItems(prev => prev.map(s => s.id === id ? { ...s, status: 'APPROVED', approved_at: new Date().toISOString() } : s));
      showToast('승인 완료', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '승인 실패', 'error');
    }
  };

  const filtered = filter === '전체' ? items : items.filter(s => s.status === filter);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>정산 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
          {['전체', 'HOLD', 'READY', 'APPROVED', 'PAID'].map(s => (
            <button key={s} onClick={() => setFilter(s)} style={{
              padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: filter === s ? `${C.green}22` : C.bgEl,
              border: `1px solid ${filter === s ? C.green : C.border}`,
              color: filter === s ? C.green : C.textSec,
              fontWeight: filter === s ? 700 : 400,
            }}>{s === '전체' ? s : (STATUS_META[s]?.label ?? s)}</button>
          ))}
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>{filtered.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : filtered.map(s => {
          const meta = STATUS_META[s.status] ?? STATUS_META.HOLD;
          return (
            <div key={s.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${meta.color}`,
              borderRadius: 14, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: C.textSec }}>정산 #{s.id} (예약 #{s.reservation_id})</span>
                <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6, background: `${meta.color}22`, color: meta.color }}>{meta.label}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 6 }}>
                <div><div style={{ fontSize: 10, color: C.textDim }}>결제액</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{fmtP(s.buyer_paid_amount)}</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>수수료</div><div style={{ fontSize: 12, fontWeight: 700, color: C.orange }}>{fmtP(s.platform_commission_amount)}</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>정산액</div><div style={{ fontSize: 12, fontWeight: 700, color: C.green }}>{fmtP(s.seller_payout_amount)}</div></div>
              </div>
              <div style={{ fontSize: 10, color: C.textDim }}>
                판매자 #{s.seller_id} · 생성 {fmtDate(s.created_at)}
                {s.block_reason && <span style={{ color: '#ff5252' }}> · 차단: {s.block_reason}</span>}
              </div>
              {s.status === 'READY' && (
                <button onClick={() => void handleApprove(s.id)}
                  style={{ marginTop: 8, padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(0,230,118,0.12)', border: '1px solid rgba(0,230,118,0.35)', color: '#00e676', cursor: 'pointer' }}>
                  승인
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
