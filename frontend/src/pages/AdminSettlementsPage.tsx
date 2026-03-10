import { useState, useEffect, useRef } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import DateRangeFilter from '../components/common/DateRangeFilter';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };

export default function AdminSettlementsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const dateRef = useRef({ from: '', to: '' });

  const load = async () => {
    try {
      await apiClient.post('/settlements/refresh-ready').catch(() => {});
      const params: any = {};
      if (dateRef.current.from) params.date_from = dateRef.current.from;
      if (dateRef.current.to) params.date_to = dateRef.current.to;
      const r = await apiClient.get(API.SETTLEMENTS.ADMIN_LIST, { params });
      const data = r.data;
      setItems(Array.isArray(data) ? data : data?.items || []);
    } catch (e) { console.error('Settlements load:', e); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const filtered = items.filter(s => {
    const q = search.toLowerCase();
    const matchQ = !q || [String(s.id), String(s.reservation_id), s.seller_name, s.seller_business_name, s.product_name].some(v => v && String(v).toLowerCase().includes(q));
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
      <DateRangeFilter onFilter={(f, t) => { dateRef.current = { from: f, to: t }; load(); }} style={{ marginBottom: 12 }} />
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="정산ID/예약ID/판매자/품목명 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: '#1a1a2e', color: '#e0e0e0', fontSize: 13 }}>
          <option value="">전체 상태</option>
          {['HOLD', 'READY', 'APPROVED', 'PAID'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button onClick={load} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>새로고침</button>
        <button onClick={async () => { const ready = filtered.filter(s => s.status === 'READY'); if (!ready.length) return alert('READY 상태 정산이 없습니다.'); if (!confirm(`${ready.length}건을 일괄 승인하시겠습니까?`)) return; for (const s of ready) { await approve(s.id); } }} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: C.green, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>일괄 승인</button>
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 900 }}>
            <thead style={stickyHead}>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['정산ID', '예약ID', '품목명', '수량', '판매자', '결제금액', 'PG수수료', '플랫폼수수료', '정산금액', '상태', '생성일', ''].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(s => (
                <tr key={s.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={{ padding: '10px 8px', color: C.cyan, cursor: 'pointer', textDecoration: 'underline' }} onClick={() => { if (s.deal_id) window.open(`/deal/${s.deal_id}`, '_blank'); }}>S-{s.id}</td>
                  <td style={{ padding: '10px 8px', color: '#60a5fa', cursor: 'pointer', textDecoration: 'underline' }} onClick={() => { if (s.deal_id) window.open(`/deal/${s.deal_id}`, '_blank'); }}>R-{s.reservation_id}</td>
                  <td style={{ padding: '10px 8px', color: C.text, maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={s.product_name || ''}>{s.product_name || '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{s.quantity ?? '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{s.seller_business_name || s.seller_name || `S-${s.seller_id}`}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{(s.total_amount || 0).toLocaleString()}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{(s.pg_fee || 0).toLocaleString()}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{(s.platform_fee || 0).toLocaleString()}</td>
                  <td style={{ padding: '10px 8px', color: C.green, fontWeight: 600 }}>{(s.payout_amount || s.settlement_amount || 0).toLocaleString()}</td>
                  <td style={{ padding: '10px 8px' }}><span style={{ color: statusColor[s.status] || C.textSec, fontWeight: 600 }}>{s.status}</span>{s.is_disputed && <span style={{ marginLeft: 6, padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 700, background: 'rgba(255,82,82,0.15)', color: C.red }}>분쟁</span>}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec, fontSize: 12 }}>{s.created_at ? new Date(s.created_at).toLocaleDateString('ko-KR') : '-'}</td>
                  <td style={{ padding: '10px 8px' }}>
                    {(s.status === 'READY' || s.status === 'HOLD') && <button onClick={() => approve(s.id)} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,229,255,0.15)', color: C.cyan }}>승인</button>}
                  </td>
                </tr>
              ))}
              {!filtered.length && <tr><td colSpan={12} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>정산 없음</td></tr>}
              {filtered.length > 0 && (
                <tr style={{ borderTop: `2px solid ${C.border}`, fontWeight: 700 }}>
                  <td colSpan={8} style={{ padding: '10px 8px', color: C.textSec }}>합계</td>
                  <td style={{ padding: '10px 8px', color: C.green }}>{totalAmount.toLocaleString()}</td>
                  <td colSpan={3} />
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{filtered.length}건</div>
    </div>
  );
}
