import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { showToast } from '../components/common/Toast';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

interface DisputeReservation {
  id: number;
  deal_id: number;
  buyer_id: number;
  offer_id: number;
  qty: number;
  amount_total: number;
  status: string;
  is_disputed: boolean;
  dispute_reason?: string;
  created_at: string;
  deal?: { product_name?: string };
  buyer?: { nickname?: string; name?: string };
}

function fmtP(n: number) { return '₩' + (n ?? 0).toLocaleString('ko-KR'); }
function fmtDate(s?: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

export default function AdminDisputePage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<DisputeReservation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.get(API.RESERVATIONS_SEARCH.SEARCH, { params: { is_disputed: true, limit: 200 } });
        const data = res.data?.items ?? res.data ?? [];
        setItems(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error('분쟁 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleClose = async (id: number) => {
    if (!confirm('이 분쟁을 종료하시겠습니까?')) return;
    try {
      await apiClient.post(API.RESERVATIONS_V36.DISPUTE_CLOSE(id));
      setItems(prev => prev.filter(r => r.id !== id));
      showToast('분쟁 종료 완료', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '분쟁 종료 실패', 'error');
    }
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>분쟁 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>분쟁 중 {items.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : items.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>✅</div>
            <div style={{ fontSize: 13 }}>진행 중인 분쟁이 없어요</div>
          </div>
        ) : items.map(r => (
          <div key={r.id} style={{
            background: C.bgCard, border: `1px solid ${C.border}`,
            borderLeft: '3px solid #ff5252',
            borderRadius: 14, padding: 14, marginBottom: 8,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 12, color: C.textSec }}>
                예약 #{r.id} · 딜 #{r.deal_id}
              </span>
              <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6, background: 'rgba(255,82,82,0.15)', color: '#ff5252' }}>
                분쟁중
              </span>
            </div>
            <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 4 }}>
              {r.deal?.product_name ?? `예약 #${r.id}`}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 6 }}>
              <div><div style={{ fontSize: 10, color: C.textDim }}>결제액</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{fmtP(r.amount_total)}</div></div>
              <div><div style={{ fontSize: 10, color: C.textDim }}>수량</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{r.qty}개</div></div>
            </div>
            <div style={{ fontSize: 10, color: C.textDim, marginBottom: 6 }}>
              구매자 #{r.buyer_id}{r.buyer?.nickname ? ` (${r.buyer.nickname})` : ''} · {fmtDate(r.created_at)}
            </div>
            {r.dispute_reason && (
              <div style={{ fontSize: 11, color: '#ff9100', marginBottom: 6 }}>사유: {r.dispute_reason}</div>
            )}
            <button onClick={() => void handleClose(r.id)}
              style={{ marginTop: 4, padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,82,82,0.12)', border: '1px solid rgba(255,82,82,0.35)', color: '#ff5252', cursor: 'pointer' }}>
              분쟁 종료
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
