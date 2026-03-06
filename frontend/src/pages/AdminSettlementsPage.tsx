import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminSettlementsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    try { const r = await apiClient.get(API.SETTLEMENTS.ADMIN_LIST); setItems(Array.isArray(r.data) ? r.data : r.data?.items || []); } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const filtered = items.filter(s => {
    const q = search.toLowerCase();
    const matchQ = !q || [String(s.id), String(s.reservation_id), s.seller_name, s.seller_business_name].some(v => v && String(v).toLowerCase().includes(q));
    const matchS = !statusFilter || s.status === statusFilter;
    return matchQ && matchS;
  });

  const totalAmount = filtered.reduce((a, s) => a + (s.payout_amount || s.settlement_amount || 0), 0);

  const approve = async (id: number) => { try { await apiClient.post(API.SETTLEMENTS.ADMIN_APPROVE(id)); load(); } catch {} };

  const statusColor: Record<string, string> = { HOLD: C.orange, READY: C.cyan, APPROVED: '#4fc3f7', PAID: C.green };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>정산 관리</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="정산ID/예약ID/판매자 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }}>
          <option value="">전체 상태</option>
          {['HOLD', 'READY', 'APPROVED', 'PAID'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 900 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['정산ID', '예약ID', '판매자', '결제금액', 'PG수수료', '플랫폼수수료', '정산금액', '상태', ''].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(s => (
              <tr key={s.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={{ padding: '10px 8px', color: C.cyan }}>S-{s.id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>R-{s.reservation_id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{s.seller_business_name || s.seller_name || `S-${s.seller_id}`}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{(s.total_amount || 0).toLocaleString()}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>{(s.pg_fee || 0).toLocaleString()}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>{(s.platform_fee || 0).toLocaleString()}</td>
                <td style={{ padding: '10px 8px', color: C.green, fontWeight: 600 }}>{(s.payout_amount || s.settlement_amount || 0).toLocaleString()}</td>
                <td style={{ padding: '10px 8px' }}><span style={{ color: statusColor[s.status] || C.textSec, fontWeight: 600 }}>{s.status}</span></td>
                <td style={{ padding: '10px 8px' }}>
                  {(s.status === 'READY' || s.status === 'HOLD') && <button onClick={() => approve(s.id)} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,229,255,0.15)', color: C.cyan }}>승인</button>}
                </td>
              </tr>
            ))}
            {!filtered.length && <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>정산 없음</td></tr>}
            {filtered.length > 0 && (
              <tr style={{ borderTop: `2px solid ${C.border}`, fontWeight: 700 }}>
                <td colSpan={6} style={{ padding: '10px 8px', color: C.textSec }}>합계</td>
                <td style={{ padding: '10px 8px', color: C.green }}>{totalAmount.toLocaleString()}</td>
                <td colSpan={2} />
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{filtered.length}건</div>
    </div>
  );
}
