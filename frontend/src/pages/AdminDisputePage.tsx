import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminDisputePage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const r = await apiClient.get(API.ADMIN.RESERVATIONS, { params: { is_disputed: true, limit: 200 } });
      setItems(r.data?.items || []);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const closeDispute = async (id: number) => {
    try { await apiClient.post(API.RESERVATIONS_V36.DISPUTE_CLOSE(id)); load(); } catch {}
  };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>분쟁 관리</h1>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['예약ID', '딜ID', '구매자', '판매자', '금액', '상태', ''].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(r => (
              <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={{ padding: '10px 8px', color: C.red }}>R-{r.id}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>D-{r.deal_id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{r.buyer_name || `B-${r.buyer_id}`}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{r.seller_name || `S-${r.seller_id}`}</td>
                <td style={{ padding: '10px 8px', color: C.orange }}>{(r.amount || 0).toLocaleString()}</td>
                <td style={{ padding: '10px 8px', color: C.red, fontWeight: 600 }}>{r.status}</td>
                <td style={{ padding: '10px 8px' }}>
                  <button onClick={() => closeDispute(r.id)} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,230,118,0.15)', color: C.green }}>분쟁종료</button>
                </td>
              </tr>
            ))}
            {!items.length && <tr><td colSpan={7} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>분쟁 없음</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
