import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminDeliveryPage() {
  const [items, setItems] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await apiClient.get(API.ADMIN.RESERVATIONS, { params: { shipped: true, limit: 200 } });
        setItems(r.data?.items || []);
      } catch {}
      setLoading(false);
    };
    load();
  }, []);

  const daysSince = (dateStr: string | null) => {
    if (!dateStr) return null;
    const diff = (Date.now() - new Date(dateStr).getTime()) / (1000 * 60 * 60 * 24);
    return Math.floor(diff);
  };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>배송 관리</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="R-#/판매자/구매자/운송장 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 700 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['R-#', '판매자', '구매자', '택배사', '운송장', '상태', '소요일'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.filter(r => { const q = search.toLowerCase(); return !q || [String(r.id), r.seller_name, r.buyer_name, r.tracking_number, r.carrier].some(v => v && String(v).toLowerCase().includes(q)); }).map(r => {
              const days = daysSince(r.shipped_at);
              const overdue = days !== null && days > 3 && !['ARRIVED', 'CONFIRMED'].includes(r.status);
              return (
                <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}`, background: overdue ? 'rgba(255,82,82,0.05)' : undefined }}>
                  <td style={{ padding: '10px 8px', color: C.cyan }}>R-{r.id}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{r.seller_name || `S-${r.seller_id}`}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{r.buyer_name || `B-${r.buyer_id}`}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{r.carrier || '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{r.tracking_number || '-'}</td>
                  <td style={{ padding: '10px 8px' }}><span style={{ fontWeight: 600, color: r.status === 'ARRIVED' || r.status === 'CONFIRMED' ? C.green : C.orange }}>{r.status}</span></td>
                  <td style={{ padding: '10px 8px', color: overdue ? C.red : C.textSec, fontWeight: overdue ? 700 : 400 }}>{days !== null ? `${days}일` : '-'}</td>
                </tr>
              );
            })}
            {!items.length && <tr><td colSpan={7} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>배송 데이터 없음</td></tr>}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{items.length}건</div>
    </div>
  );
}
