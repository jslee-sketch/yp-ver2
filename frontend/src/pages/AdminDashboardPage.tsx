import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
};
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };

export default function AdminDashboardPage() {
  const navigate = useNavigate();
  const [counts, setCounts] = useState<any>(null);
  const [alerts, setAlerts] = useState<any>({});
  const [recent, setRecent] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rawJson, setRawJson] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError(''); setRawJson('');
    try {
      // 1) /admin/stats/counts — 전용 카운트 API (가장 확실)
      const r = await apiClient.get(API.ADMIN.STATS_COUNTS);
      const d = r.data;
      setRawJson(JSON.stringify(d, null, 2));
      setCounts(d);

      // 2) 보조 데이터 (실패해도 무시)
      const [anomR, recentR, reportsR] = await Promise.allSettled([
        apiClient.get(API.ADMIN.ANOMALY_DETECT, { params: { lookback_hours: 24 } }),
        apiClient.get(API.ACTIVITY.LIST, { params: { limit: 10 } }),
        apiClient.get(API.ADMIN.REPORTS),
      ]);
      const anoms = anomR.status === 'fulfilled' && Array.isArray(anomR.value.data) ? anomR.value.data : [];
      const reps = reportsR.status === 'fulfilled' ? (Array.isArray(reportsR.value.data) ? reportsR.value.data : reportsR.value.data?.items || []) : [];
      setAlerts({
        pendingSellers: d.pending_sellers ?? 0,
        pendingSett: d.pending_settlement ?? 0,
        disputes: d.disputed ?? 0,
        anomalies: anoms.length,
        openReports: reps.filter((r: any) => r.status === 'OPEN').length,
      });
      const rd = recentR.status === 'fulfilled' ? recentR.value.data : [];
      setRecent(Array.isArray(rd) ? rd.slice(0, 8) : []);
    } catch (e: any) {
      console.error('Dashboard load error:', e);
      setError(e?.response?.data?.detail || e?.message || '데이터 로딩 실패');
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;
  if (error) return (
    <div style={{ padding: 40 }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16, paddingLeft: 48 }}>대시보드</h1>
      <div style={{ padding: 16, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', borderRadius: 8, color: C.red, fontSize: 14, marginBottom: 16 }}>{error}</div>
      <button onClick={load} style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer' }}>다시 시도</button>
    </div>
  );
  if (!counts) return <div style={{ padding: 40, color: C.textSec }}>데이터 없음</div>;

  const kpi = [
    { label: '구매자', value: counts.buyers ?? 0, color: C.green, path: '/admin/buyers' },
    { label: '판매자', value: counts.sellers ?? 0, color: C.cyan, path: '/admin/sellers' },
    { label: '딜', value: counts.deals ?? 0, color: '#e040fb', path: '/admin/deals' },
    { label: '오퍼', value: counts.offers ?? 0, color: C.orange, path: '/admin/offers' },
    { label: '예약/주문', value: counts.reservations ?? 0, color: '#4fc3f7', path: '/admin/reservations' },
    { label: '액추에이터', value: counts.actuators ?? 0, color: '#ba68c8', path: '/admin/actuators' },
    { label: '승인대기', value: counts.pending_sellers ?? 0, color: C.red, path: '/admin/sellers' },
    { label: '정산대기', value: counts.pending_settlement ?? 0, color: '#ffab40', path: '/admin/settlements' },
    { label: '분쟁', value: counts.disputed ?? 0, color: C.red, path: '/admin/disputes' },
  ];

  const statCards = [
    { label: 'GMV', value: `${(counts.gmv ?? 0).toLocaleString()}원`, color: C.green },
    { label: 'AOV', value: `${(counts.aov ?? 0).toLocaleString()}원`, color: C.cyan },
  ];

  const alertItems = [
    { label: '승인대기 판매자', count: alerts.pendingSellers, path: '/admin/sellers' },
    { label: '미처리 분쟁', count: alerts.disputes, path: '/admin/disputes' },
    { label: '정산 대기', count: alerts.pendingSett, path: '/admin/settlements' },
    { label: '이상 탐지', count: alerts.anomalies, path: '/admin/anomalies' },
    { label: '미답변 신고', count: alerts.openReports, path: '/admin/reports' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, paddingLeft: 48 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text }}>대시보드</h1>
        <button onClick={load} style={{ padding: '6px 16px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.cyan, cursor: 'pointer', fontSize: 12 }}>새로고침</button>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 24 }}>
        {kpi.map(k => (
          <div key={k.label} onClick={() => navigate(k.path)} style={{
            background: C.card, border: `1px solid ${C.border}`, borderRadius: 12,
            padding: '16px 12px', textAlign: 'center', cursor: 'pointer',
            transition: 'border-color 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = k.color)}
          onMouseLeave={e => (e.currentTarget.style.borderColor = '')}
          >
            <div style={{ fontSize: 28, fontWeight: 800, color: k.color }}>{typeof k.value === 'number' ? k.value.toLocaleString() : k.value}</div>
            <div style={{ fontSize: 12, color: C.textSec, marginTop: 4 }}>{k.label}</div>
          </div>
        ))}
      </div>

      {/* GMV / AOV */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 24 }}>
        {statCards.map(s => (
          <div key={s.label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: '14px 12px', textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 11, color: C.textSec, marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Settlement summary */}
      {counts.settlement_summary && Object.keys(counts.settlement_summary).length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
          {['HOLD', 'READY', 'APPROVED', 'PAID'].map(s => (
            <div key={s} onClick={() => navigate('/admin/settlements')} style={{
              background: C.card, border: `1px solid ${C.border}`, borderRadius: 12,
              padding: '12px', textAlign: 'center', cursor: 'pointer',
            }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: s === 'HOLD' ? C.orange : s === 'READY' ? C.cyan : s === 'APPROVED' ? '#4fc3f7' : C.green }}>
                {(counts.settlement_summary[s] ?? 0).toLocaleString()}
              </div>
              <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>정산 {s}</div>
            </div>
          ))}
        </div>
      )}

      {/* Alert panel */}
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16, marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: C.orange, marginBottom: 12 }}>주의 필요</h3>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {alertItems.filter(a => a.count > 0).map(a => (
            <div key={a.label} onClick={() => navigate(a.path)} style={{
              padding: '8px 16px', background: 'rgba(255,145,0,0.08)', border: '1px solid rgba(255,145,0,0.2)',
              borderRadius: 8, cursor: 'pointer', fontSize: 13, color: C.orange,
            }}>
              {a.label}: <b>{a.count}</b>
            </div>
          ))}
          {alertItems.every(a => !a.count) && <span style={{ color: C.textSec, fontSize: 13 }}>모든 항목 정상</span>}
        </div>
      </div>

      {/* Reservation status breakdown */}
      {counts.reservation_status && Object.keys(counts.reservation_status).length > 0 && (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16, marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>예약 상태 분포</h3>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {Object.entries(counts.reservation_status).map(([status, count]: [string, any]) => (
              <div key={status} onClick={() => navigate('/admin/reservations')} style={{
                padding: '8px 16px', background: 'rgba(0,229,255,0.06)', border: `1px solid ${C.border}`,
                borderRadius: 8, cursor: 'pointer', fontSize: 13, color: C.text,
              }}>
                {status}: <b style={{ color: C.cyan }}>{count}</b>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent activity */}
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>최근 활동</h3>
        <div style={{ maxHeight: '50vh', overflowY: 'auto', overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 500 }}>
          <thead style={stickyHead}>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              <th style={{ textAlign: 'left', padding: '8px 6px', color: C.textSec }}>이벤트</th>
              <th style={{ textAlign: 'left', padding: '8px 6px', color: C.textSec }}>액터</th>
              <th style={{ textAlign: 'left', padding: '8px 6px', color: C.textSec }}>시간</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((r: any, i: number) => (
              <tr key={i} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={{ padding: '8px 6px', color: C.text }}>{r.event_type || r.type || '-'}</td>
                <td style={{ padding: '8px 6px', color: C.textSec }}>{r.actor_type || '-'} #{r.actor_id || ''}</td>
                <td style={{ padding: '8px 6px', color: C.textSec }}>{r.created_at ? new Date(r.created_at).toLocaleString('ko-KR') : '-'}</td>
              </tr>
            ))}
            {!recent.length && <tr><td colSpan={3} style={{ padding: 16, textAlign: 'center', color: C.textSec }}>활동 없음</td></tr>}
          </tbody>
        </table>
        </div>
      </div>

      {/* Debug: raw API response */}
      {rawJson && (
        <details style={{ marginTop: 16 }}>
          <summary style={{ cursor: 'pointer', color: C.textSec, fontSize: 11 }}>API 응답 원본 (디버그)</summary>
          <pre style={{ background: '#0a0a1a', padding: 12, borderRadius: 8, fontSize: 11, color: '#888', overflow: 'auto', maxHeight: 200, marginTop: 8 }}>{rawJson}</pre>
        </details>
      )}
    </div>
  );
}
