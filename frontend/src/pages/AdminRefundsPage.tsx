import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };

const cleanStatus = (s: string) => s?.replace(/^ReservationStatus\./i, '').replace(/^Reservation/i, '') || '-';

export default function AdminRefundsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await apiClient.get(API.ADMIN.RESERVATIONS, { params: { refund: true, limit: 300 } });
        const data = r.data;
        setItems(Array.isArray(data) ? data : data?.items || []);
      } catch (e) { console.error('Refunds load:', e); }
      setLoading(false);
    };
    load();
  }, []);

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>환불 관리</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="R-#/구매자/판매자 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 800 }}>
            <thead style={stickyHead}>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['R-#', '구매자', '판매자', '원금액', '환불금액', '환불유형', '상태', '환불일'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.filter(r => { const q = search.toLowerCase(); return !q || [String(r.id), r.buyer_name, r.seller_name].some(v => v && String(v).toLowerCase().includes(q)); }).map(r => (
                <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={{ padding: '10px 8px', color: C.cyan }}>R-{r.id}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{r.buyer_name || `B-${r.buyer_id}`}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{r.seller_name || `S-${r.seller_id}`}</td>
                  <td style={{ padding: '10px 8px', color: C.orange }}>{(r.amount || 0).toLocaleString()}원</td>
                  <td style={{ padding: '10px 8px', color: C.red, fontWeight: 600 }}>{(r.refunded_amount_total || 0).toLocaleString()}원</td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{r.refund_type || '-'}</td>
                  <td style={{ padding: '10px 8px' }}><span style={{ color: C.red, fontWeight: 600 }}>{cleanStatus(String(r.status || ''))}</span></td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{r.refunded_at ? new Date(r.refunded_at).toLocaleDateString('ko-KR') : r.created_at ? new Date(r.created_at).toLocaleDateString('ko-KR') : '-'}</td>
                </tr>
              ))}
              {!items.length && <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>환불 없음</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{items.length}건</div>
    </div>
  );
}
