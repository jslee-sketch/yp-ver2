import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminStatsPage() {
  const [stats, setStats] = useState<any>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;
      const r = await apiClient.get(API.ADMIN.STATS, { params });
      setStats(r.data);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  const kpi = stats ? [
    { label: 'GMV', value: `${(stats.gmv || 0).toLocaleString()}원`, color: C.green },
    { label: 'Take Rate', value: `${stats.take_rate || 0}%`, color: C.cyan },
    { label: '거래건수', value: stats.total_reservations || 0, color: C.orange },
    { label: '딜 성사율', value: `${stats.deal_success_rate || 0}%`, color: '#e040fb' },
    { label: 'AOV', value: `${(stats.aov || 0).toLocaleString()}원`, color: '#4fc3f7' },
    { label: '환불률', value: `${stats.refund_rate || 0}%`, color: C.red },
  ] : [];

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>통계 / KPI</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <span style={{ alignSelf: 'center', color: C.textSec }}>~</span>
        <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <button onClick={load} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>조회</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
        {kpi.map(k => (
          <div key={k.label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: '16px 12px', textAlign: 'center' }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: k.color }}>{k.value}</div>
            <div style={{ fontSize: 12, color: C.textSec, marginTop: 4 }}>{k.label}</div>
          </div>
        ))}
      </div>

      {stats?.settlement_summary && (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16, marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>정산 상태 요약</h3>
          <div style={{ display: 'flex', gap: 16 }}>
            {Object.entries(stats.settlement_summary).map(([k, v]) => (
              <div key={k} style={{ fontSize: 13 }}>
                <span style={{ color: C.textSec }}>{k}: </span><span style={{ color: C.text, fontWeight: 600 }}>{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {stats?.reservation_status && (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>예약 상태 분포</h3>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {Object.entries(stats.reservation_status).map(([k, v]) => (
              <div key={k} style={{ fontSize: 13 }}>
                <span style={{ color: C.textSec }}>{k}: </span><span style={{ color: C.text, fontWeight: 600 }}>{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
