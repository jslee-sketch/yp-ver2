import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminOffersPage() {
  const [items, setItems] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const params: any = { limit: 200 };
      if (statusFilter) params.status = statusFilter;
      const r = await apiClient.get(API.ADMIN.OFFERS, { params });
      setItems(r.data?.items || []);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const filtered = items.filter(o => {
    const q = search.toLowerCase();
    return !q || [String(o.id), String(o.deal_id), o.product_name, o.business_name].some(v => v && String(v).toLowerCase().includes(q));
  });

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>오퍼 관리</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="O-#/D-#/판매자 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); }} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }}>
          <option value="">전체 상태</option>
          {['ACTIVE', 'INACTIVE', 'EXPIRED'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 800 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['O-#', 'D-#', '상품명', '판매자', '제안가', '배송비', '수량', '상태'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(o => (
              <tr key={o.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={{ padding: '10px 8px', color: C.cyan }}>O-{o.id}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>D-{o.deal_id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{o.product_name || '-'}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{o.business_name || `S-${o.seller_id}`}</td>
                <td style={{ padding: '10px 8px', color: C.orange }}>{o.price ? o.price.toLocaleString() : '-'}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>{o.shipping_fee != null ? o.shipping_fee.toLocaleString() : '-'}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{o.quantity ?? '-'}</td>
                <td style={{ padding: '10px 8px' }}><span style={{ color: o.status === 'ACTIVE' ? C.green : C.textSec, fontWeight: 600 }}>{o.status}</span></td>
              </tr>
            ))}
            {!filtered.length && <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>오퍼 없음</td></tr>}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{filtered.length}건</div>
    </div>
  );
}
