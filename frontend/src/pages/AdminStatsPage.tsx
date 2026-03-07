import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

function fmt(d: Date) { return d.toISOString().slice(0, 10); }
function daysAgo(n: number) { const d = new Date(); d.setDate(d.getDate() - n); return fmt(d); }
function monthStart() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`; }
function prevMonthRange(): [string, string] {
  const d = new Date(); d.setMonth(d.getMonth() - 1);
  const start = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`;
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0);
  return [start, fmt(end)];
}

export default function AdminStatsPage() {
  const [stats, setStats] = useState<any>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async (from?: string, to?: string) => {
    setLoading(true); setError('');
    const f = from ?? dateFrom;
    const t = to ?? dateTo;
    try {
      const params: any = {};
      if (f) params.date_from = f;
      if (t) params.date_to = t;
      const r = await apiClient.get(API.ADMIN.STATS, { params });
      setStats(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || '조회 실패');
    }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const applyPreset = (from: string, to: string) => {
    setDateFrom(from); setDateTo(to);
    load(from, to);
  };

  const presets = [
    { label: '전체', action: () => { setDateFrom(''); setDateTo(''); load('', ''); } },
    { label: '오늘', action: () => applyPreset(fmt(new Date()), fmt(new Date())) },
    { label: '7일', action: () => applyPreset(daysAgo(7), fmt(new Date())) },
    { label: '30일', action: () => applyPreset(daysAgo(30), fmt(new Date())) },
    { label: '이번 달', action: () => applyPreset(monthStart(), fmt(new Date())) },
    { label: '지난 달', action: () => { const [s, e] = prevMonthRange(); applyPreset(s, e); } },
    { label: '90일', action: () => applyPreset(daysAgo(90), fmt(new Date())) },
  ];

  const kpi = stats ? [
    { label: 'GMV (총거래액)', value: `${(stats.gmv || 0).toLocaleString()}원`, color: C.green },
    { label: 'Take Rate', value: `${stats.take_rate || 0}%`, color: C.cyan },
    { label: '총 거래건수', value: (stats.total_reservations || 0).toLocaleString(), color: C.orange },
    { label: '딜 성사율', value: `${stats.deal_success_rate || 0}%`, color: '#e040fb' },
    { label: 'AOV (평균 주문액)', value: `${(stats.aov || 0).toLocaleString()}원`, color: '#4fc3f7' },
    { label: '환불률', value: `${stats.refund_rate || 0}%`, color: (stats.refund_rate || 0) > 10 ? C.red : C.green },
  ] : [];

  const entityKpi = stats ? [
    { label: '구매자', value: stats.buyer_count || 0, color: C.green },
    { label: '판매자', value: stats.seller_count || 0, color: C.cyan },
    { label: '딜', value: stats.deal_count || 0, color: '#e040fb' },
    { label: '오퍼', value: stats.offer_count || 0, color: C.orange },
    { label: '액추에이터', value: stats.actuator_count || 0, color: '#4fc3f7' },
    { label: '승인대기', value: stats.pending_sellers || 0, color: C.red },
    { label: '정산대기', value: stats.pending_settlement || 0, color: '#ffab40' },
    { label: '분쟁중', value: stats.disputed_count || 0, color: C.red },
  ] : [];

  const inputStyle: React.CSSProperties = {
    padding: '8px 12px', borderRadius: 8,
    border: `1px solid ${C.border}`, background: '#1a1a2e', color: '#e0e0e0',
    fontSize: 13, colorScheme: 'dark',
  };

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>통계 / KPI</h1>

      {/* Quick presets */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
        {presets.map(p => (
          <button key={p.label} onClick={p.action} style={{
            padding: '6px 14px', borderRadius: 6, border: `1px solid ${C.border}`,
            background: 'rgba(0,229,255,0.08)', color: C.cyan, cursor: 'pointer', fontSize: 12, fontWeight: 600,
          }}>{p.label}</button>
        ))}
      </div>

      {/* Date range inputs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, alignItems: 'center' }}>
        <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} style={inputStyle} />
        <span style={{ color: C.textSec, fontSize: 14 }}>~</span>
        <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} style={inputStyle} />
        <button onClick={() => load()} style={{
          padding: '8px 20px', borderRadius: 8, border: 'none', background: C.cyan,
          color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13,
        }}>조회</button>
        {(dateFrom || dateTo) && (
          <span style={{ fontSize: 12, color: C.textSec }}>
            {dateFrom || '전체'} ~ {dateTo || '전체'}
          </span>
        )}
      </div>

      {error && <div style={{ padding: 12, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', borderRadius: 8, marginBottom: 16, color: C.red, fontSize: 13 }}>{error}</div>}
      {loading && <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>}

      {!loading && stats && (
        <>
          {/* Main KPI */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
            {kpi.map(k => (
              <div key={k.label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: '18px 12px', textAlign: 'center' }}>
                <div style={{ fontSize: 24, fontWeight: 800, color: k.color }}>{k.value}</div>
                <div style={{ fontSize: 12, color: C.textSec, marginTop: 4 }}>{k.label}</div>
              </div>
            ))}
          </div>

          {/* Entity counts */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
            {entityKpi.map(k => (
              <div key={k.label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: '14px 12px', textAlign: 'center' }}>
                <div style={{ fontSize: 20, fontWeight: 700, color: k.color }}>{typeof k.value === 'number' ? k.value.toLocaleString() : k.value}</div>
                <div style={{ fontSize: 11, color: C.textSec, marginTop: 4 }}>{k.label}</div>
              </div>
            ))}
          </div>

          {/* Settlement summary */}
          {stats.settlement_summary && Object.keys(stats.settlement_summary).length > 0 && (
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>정산 상태 요약</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {['HOLD', 'READY', 'APPROVED', 'PAID'].map(s => (
                  <div key={s} style={{ textAlign: 'center', padding: 8 }}>
                    <div style={{ fontSize: 18, fontWeight: 700, color: s === 'HOLD' ? C.orange : s === 'READY' ? C.cyan : s === 'APPROVED' ? '#4fc3f7' : C.green }}>
                      {(stats.settlement_summary[s] || 0).toLocaleString()}
                    </div>
                    <div style={{ fontSize: 11, color: C.textSec }}>{s}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Reservation status */}
          {stats.reservation_status && Object.keys(stats.reservation_status).length > 0 && (
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>예약 상태 분포</h3>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {Object.entries(stats.reservation_status).map(([k, v]) => (
                  <div key={k} style={{ padding: '8px 16px', background: 'rgba(0,229,255,0.06)', border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 13 }}>
                    <span style={{ color: C.textSec }}>{k}: </span><span style={{ color: C.cyan, fontWeight: 700 }}>{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
