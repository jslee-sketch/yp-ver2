import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminReservationsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<any>(null);

  const load = async () => {
    try {
      const params: any = { limit: 200 };
      if (statusFilter) params.status = statusFilter;
      const r = await apiClient.get(API.ADMIN.RESERVATIONS, { params });
      setItems(r.data?.items || []);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const filtered = items.filter(r => {
    const q = search.toLowerCase();
    return !q || [String(r.id), String(r.deal_id), r.buyer_name, r.seller_name].some(v => v && String(v).toLowerCase().includes(q));
  });

  const cancel = async (id: number) => { try { await apiClient.post(API.RESERVATIONS_V36.ADMIN_CANCEL(id)); load(); } catch {} };

  const statusColor: Record<string, string> = { PAID: C.cyan, SHIPPED: C.orange, ARRIVED: '#4fc3f7', CONFIRMED: C.green, CANCELLED: C.red, REFUNDED: C.red, PENDING: C.textSec };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>예약/주문 관리</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="R-#/D-#/구매자/판매자 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); }} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }}>
          <option value="">전체 상태</option>
          {['PENDING', 'PAID', 'SHIPPED', 'ARRIVED', 'CONFIRMED', 'CANCELLED', 'REFUNDED'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 900 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['R-#', 'D-#', 'O-#', '구매자', '판매자', '금액', '상태', '분쟁', ''].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer' }} onClick={() => setModal(r)}>
                <td style={{ padding: '10px 8px', color: C.cyan }}>R-{r.id}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>D-{r.deal_id}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>O-{r.offer_id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{r.buyer_name || `B-${r.buyer_id}`}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{r.seller_name || `S-${r.seller_id}`}</td>
                <td style={{ padding: '10px 8px', color: C.orange }}>{(r.amount || 0).toLocaleString()}</td>
                <td style={{ padding: '10px 8px' }}><span style={{ color: statusColor[r.status] || C.textSec, fontWeight: 600 }}>{r.status}</span></td>
                <td style={{ padding: '10px 8px' }}>{r.is_disputed && <span style={{ color: C.red, fontWeight: 600 }}>Y</span>}</td>
                <td style={{ padding: '10px 8px' }}>
                  {!['CANCELLED', 'REFUNDED'].includes(r.status) && <button onClick={e => { e.stopPropagation(); cancel(r.id); }} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(255,82,82,0.15)', color: C.red }}>강제취소</button>}
                </td>
              </tr>
            ))}
            {!filtered.length && <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>예약 없음</td></tr>}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{filtered.length}건</div>

      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 440, border: `1px solid ${C.border}`, maxHeight: '80vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 16 }}>예약 상세 R-{modal.id}</h3>
            {Object.entries({ 딜: `D-${modal.deal_id}`, 오퍼: `O-${modal.offer_id}`, 구매자: modal.buyer_name, 판매자: modal.seller_name, 금액: modal.amount, 상태: modal.status, 분쟁: modal.is_disputed ? 'Y' : 'N', 택배: modal.carrier, 운송장: modal.tracking_number, 배송일: modal.shipped_at, 생성일: modal.created_at }).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${C.border}`, fontSize: 13 }}>
                <span style={{ color: C.textSec }}>{k}</span><span style={{ color: C.text }}>{String(v ?? '-')}</span>
              </div>
            ))}
            <button onClick={() => setModal(null)} style={{ marginTop: 16, width: '100%', padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>닫기</button>
          </div>
        </div>
      )}
    </div>
  );
}
