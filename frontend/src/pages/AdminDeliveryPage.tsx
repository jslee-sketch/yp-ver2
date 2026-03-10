import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { showToast } from '../components/common/Toast';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', blue: '#3b82f6', purple: '#8b5cf6', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };

const cleanStatus = (s: string) => s?.replace(/^ReservationStatus\./i, '').replace(/^Reservation/i, '') || '-';

const getDeliveryStage = (r: any) => {
  const ds = r.delivery_status;
  if (ds) {
    const map: Record<string, string> = {
      READY: '📦 준비', COLLECTING: '📥 집하', IN_TRANSIT: '🚚 이동중',
      OUT_FOR_DELIVERY: '🛵 배달중', DELIVERED: '✅ 완료',
    };
    return map[ds] || `📦 ${ds}`;
  }
  const st = cleanStatus(String(r.status || ''));
  if (!r.shipped_at) return '📦 배송준비';
  if (st === 'ARRIVAL_CONFIRMED' || st === 'CONFIRMED') return '🎉 수취완료';
  if (st === 'DELIVERED') return '✅ 배송완료';
  return '🚚 배송중';
};

const deliveryStatusOptions = [
  { value: '', label: '전체 상태' },
  { value: 'PAID', label: 'PAID : 발송 대기' },
  { value: 'SHIPPED', label: 'SHIPPED : 배송 중' },
  { value: 'DELIVERED', label: 'DELIVERED : 배달 완료' },
  { value: 'ARRIVAL_CONFIRMED', label: 'ARRIVAL_CONFIRMED : 수취 확인' },
];

interface DeliverySummary {
  total_shipped: number;
  READY: number;
  COLLECTING: number;
  IN_TRANSIT: number;
  OUT_FOR_DELIVERY: number;
  DELIVERED: number;
  NOT_TRACKED: number;
  awaiting_confirm: number;
  auto_confirm_pending: number;
}

function SummaryCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div style={{
      background: C.card, border: `1px solid ${C.border}`, borderRadius: 12,
      padding: '12px 16px', minWidth: 100, textAlign: 'center',
    }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: color || C.text }}>{value}</div>
      <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>{label}</div>
    </div>
  );
}

export default function AdminDeliveryPage() {
  const [items, setItems] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState<DeliverySummary | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [autoLoading, setAutoLoading] = useState(false);

  const load = async () => {
    try {
      const params: any = { limit: 300 };
      if (statusFilter) params.status = statusFilter;
      else params.shipped = true;
      const r = await apiClient.get(API.ADMIN.RESERVATIONS, { params });
      setItems(r.data?.items || []);
    } catch {}
    setLoading(false);
  };

  const loadSummary = async () => {
    try {
      const r = await apiClient.get('/delivery/status-summary');
      setSummary(r.data as DeliverySummary);
    } catch {}
  };

  useEffect(() => { load(); loadSummary(); }, [statusFilter]);

  const handleBatchCheck = async () => {
    setBatchLoading(true);
    try {
      const r = await apiClient.post('/delivery/batch-check');
      const d = r.data as Record<string, number>;
      showToast(`일괄 조회 완료: ${d.checked}건 조회, ${d.updated}건 갱신, ${d.delivered}건 배달완료`, 'success');
      loadSummary();
      load();
    } catch {
      showToast('일괄 조회 실패', 'error');
    }
    setBatchLoading(false);
  };

  const handleAutoConfirm = async () => {
    setAutoLoading(true);
    try {
      const r = await apiClient.post('/delivery/auto-confirm');
      const d = r.data as { auto_confirmed: number };
      showToast(`자동 구매확정: ${d.auto_confirmed}건 처리`, 'success');
      loadSummary();
      load();
    } catch {
      showToast('자동 구매확정 실패', 'error');
    }
    setAutoLoading(false);
  };

  const daysSince = (dateStr: string | null) => {
    if (!dateStr) return null;
    const diff = (Date.now() - new Date(dateStr).getTime()) / (1000 * 60 * 60 * 24);
    return Math.floor(diff);
  };

  const displayCarrier = (carrier: string) => {
    if (!carrier) return '-';
    const parts = carrier.split(',').map(s => s.trim());
    return parts.length === 1 ? parts[0] : `${parts[0]} 외 ${parts.length - 1}건`;
  };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>배송 관리</h1>

      {/* 배송 상태 요약 */}
      {summary && (
        <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
          <SummaryCard label="전체 발송" value={summary.total_shipped} />
          <SummaryCard label="집하" value={summary.COLLECTING} color={C.orange} />
          <SummaryCard label="이동중" value={summary.IN_TRANSIT} color={C.blue} />
          <SummaryCard label="배달중" value={summary.OUT_FOR_DELIVERY} color={C.purple} />
          <SummaryCard label="배달완료" value={summary.DELIVERED} color={C.green} />
          <SummaryCard label="수취대기" value={summary.awaiting_confirm} color={C.orange} />
          <SummaryCard label="자동확정대기" value={summary.auto_confirm_pending} color={C.red} />
          <SummaryCard label="미추적" value={summary.NOT_TRACKED} />
        </div>
      )}

      {/* 액션 버튼 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button onClick={handleBatchCheck} disabled={batchLoading} style={{
          padding: '8px 16px', borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: batchLoading ? 'not-allowed' : 'pointer',
          background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.35)', color: C.blue,
        }}>
          {batchLoading ? '조회중...' : '🔍 일괄 배송 조회'}
        </button>
        <button onClick={handleAutoConfirm} disabled={autoLoading} style={{
          padding: '8px 16px', borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: autoLoading ? 'not-allowed' : 'pointer',
          background: 'rgba(0,230,118,0.12)', border: '1px solid rgba(0,230,118,0.35)', color: C.green,
        }}>
          {autoLoading ? '처리중...' : '✅ 자동 구매확정 실행'}
        </button>
      </div>

      {/* 검색 & 필터 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="R-#/판매자/구매자/운송장 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: '#1a1a2e', color: '#e0e0e0', fontSize: 13 }}>
          {deliveryStatusOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      {/* 테이블 */}
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 800 }}>
            <thead style={stickyHead}>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['R-#', '판매자', '구매자', '택배사', '운송장', '배송단계', '상태', '소요일'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.filter(r => { const q = search.toLowerCase(); return !q || [String(r.id), r.seller_name, r.buyer_name, r.tracking_number, r.carrier].some(v => v && String(v).toLowerCase().includes(q)); }).map(r => {
                const days = daysSince(r.shipped_at);
                const st = cleanStatus(String(r.status || ''));
                const overdue = days !== null && days > 3 && !['ARRIVED', 'CONFIRMED', 'ARRIVAL_CONFIRMED', 'DELIVERED'].includes(st);
                return (
                  <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}`, background: overdue ? 'rgba(255,82,82,0.05)' : undefined }}>
                    <td style={{ padding: '10px 8px', color: C.cyan, cursor: 'pointer', textDecoration: 'underline' }} onClick={() => window.open(`/reservation/${r.id}`, '_blank')}>R-{r.id}</td>
                    <td style={{ padding: '10px 8px', color: C.text }}>{r.seller_name || `S-${r.seller_id}`}</td>
                    <td style={{ padding: '10px 8px', color: C.text }}>{r.buyer_name || `B-${r.buyer_id}`}</td>
                    <td style={{ padding: '10px 8px', color: C.textSec }}>{displayCarrier(r.carrier)}</td>
                    <td style={{ padding: '10px 8px', color: C.textSec }}>{r.tracking_number || '-'}</td>
                    <td style={{ padding: '10px 8px', color: C.text }}>{getDeliveryStage(r)}</td>
                    <td style={{ padding: '10px 8px' }}><span style={{ fontWeight: 600, color: ['ARRIVED', 'CONFIRMED', 'ARRIVAL_CONFIRMED'].includes(st) ? C.green : C.orange }}>{st}</span></td>
                    <td style={{ padding: '10px 8px', color: overdue ? C.red : C.textSec, fontWeight: overdue ? 700 : 400 }}>{days !== null ? `${days}일` : '-'}</td>
                  </tr>
                );
              })}
              {!items.length && <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>배송 데이터 없음</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{items.length}건</div>
    </div>
  );
}
