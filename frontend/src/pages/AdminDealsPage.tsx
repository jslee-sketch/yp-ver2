import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };

export default function AdminDealsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try {
      const params: any = { limit: 200 };
      if (search) params.keyword = search;
      if (statusFilter) params.status = statusFilter;
      const r = await apiClient.get(API.ADMIN.DEALS, { params });
      setItems(r.data?.items || []);
      setTotal(r.data?.total || 0);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const doSearch = () => { setLoading(true); load(); };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>딜 관리</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="상품명/D-# 검색" onKeyDown={e => e.key === 'Enter' && doSearch()} style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: '#1a1a2e', color: '#e0e0e0', fontSize: 13 }}>
          <option value="">전체 상태</option>
          {['OPEN', 'CLOSED', 'EXPIRED', 'CANCELLED'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button onClick={doSearch} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>검색</button>
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 850 }}>
            <thead style={stickyHead}>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['ID', '상품명', '생성자', '목표가', '시장가', '오퍼수', '상태', '생성일'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(d => (
                <tr key={d.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={{ padding: '10px 8px', color: '#4ade80', cursor: 'pointer', textDecoration: 'underline' }} onClick={() => window.open(`/deal/${d.id}`, '_blank')}>D-{d.id}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{d.product_name || '-'}</td>
                  <td style={{ padding: '10px 8px', color: '#60a5fa', cursor: 'pointer', textDecoration: 'underline' }} onClick={() => window.open(`/mypage?user_id=${d.creator_id}`, '_blank')}>{d.buyer_nickname || `B-${d.creator_id}`}</td>
                  <td style={{ padding: '10px 8px', color: C.orange }}>{d.target_price ? d.target_price.toLocaleString() + '원' : '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{d.market_price ? d.market_price.toLocaleString() + '원' : '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{d.offer_count}</td>
                  <td style={{ padding: '10px 8px' }}><span style={{ color: d.status === 'OPEN' ? C.green : d.status === 'CLOSED' ? C.cyan : C.textSec, fontWeight: 600 }}>{d.status}</span></td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{d.created_at ? new Date(d.created_at).toLocaleDateString('ko-KR') : '-'}</td>
                </tr>
              ))}
              {!items.length && <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>딜 없음</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>전체 {total}건</div>
    </div>
  );
}
