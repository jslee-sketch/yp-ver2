import { useState, useEffect } from 'react';
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
  const [stats, setStats] = useState<any>({});
  const [alerts, setAlerts] = useState<any>({});
  const [recent, setRecent] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      // Use /admin/stats for accurate DB counts (single query, no pagination issues)
      const [statsR, anomR, recentR, reportsR] = await Promise.allSettled([
        apiClient.get(API.ADMIN.STATS),
        apiClient.get(API.ADMIN.ANOMALY_DETECT, { params: { lookback_hours: 24 } }),
        apiClient.get(API.ACTIVITY.LIST, { params: { limit: 10 } }),
        apiClient.get(API.ADMIN.REPORTS),
      ]);

      const statsData = statsR.status === 'fulfilled' ? statsR.value.data : {};
      const anoms = anomR.status === 'fulfilled' ? (Array.isArray(anomR.value.data) ? anomR.value.data : []) : [];
      const reps = reportsR.status === 'fulfilled' ? (Array.isArray(reportsR.value.data) ? reportsR.value.data : reportsR.value.data?.items || []) : [];

      const openReports = reps.filter((r: any) => r.status === 'OPEN').length;

      setStats({
        buyers: statsData.buyer_count || 0,
        sellers: statsData.seller_count || 0,
        deals: statsData.deal_count || 0,
        offers: statsData.offer_count || 0,
        reservations: statsData.total_reservations || 0,
        actuators: statsData.actuator_count || 0,
        pendingSellers: statsData.pending_sellers || 0,
        pendingSett: statsData.pending_settlement || 0,
        gmv: statsData.gmv || 0,
        aov: statsData.aov || 0,
        refundRate: statsData.refund_rate || 0,
        takeRate: statsData.take_rate || 0,
        dealSuccessRate: statsData.deal_success_rate || 0,
        settlementSummary: statsData.settlement_summary || {},
        reservationStatus: statsData.reservation_status || {},
        disputed: statsData.disputed_count || 0,
      });

      setAlerts({
        pendingSellers: statsData.pending_sellers || 0,
        pendingSett: statsData.pending_settlement || 0,
        disputes: statsData.disputed_count || 0,
        anomalies: anoms.length,
        openReports,
      });

      setRecent(recentR.status === 'fulfilled' ? (Array.isArray(recentR.value.data) ? recentR.value.data.slice(0, 8) : []) : []);
      setLoading(false);
    };
    load();
  }, []);

  const kpi = [
    { label: '구매자', value: stats.buyers || 0, color: C.green, path: '/admin/buyers' },
    { label: '판매자', value: stats.sellers || 0, color: C.cyan, path: '/admin/sellers' },
    { label: '딜', value: stats.deals || 0, color: '#e040fb', path: '/admin/deals' },
    { label: '오퍼', value: stats.offers || 0, color: C.orange, path: '/admin/offers' },
    { label: '예약/주문', value: stats.reservations || 0, color: '#4fc3f7', path: '/admin/reservations' },
    { label: '승인대기', value: stats.pendingSellers || 0, color: C.red, path: '/admin/sellers' },
    { label: '정산대기', value: stats.pendingSett || 0, color: '#ffab40', path: '/admin/settlements' },
    { label: '분쟁', value: stats.disputed || 0, color: C.red, path: '/admin/disputes' },
  ];

  const statCards = [
    { label: 'GMV', value: `${(stats.gmv || 0).toLocaleString()}원`, color: C.green },
    { label: 'AOV', value: `${(stats.aov || 0).toLocaleString()}원`, color: C.cyan },
    { label: '환불률', value: `${stats.refundRate || 0}%`, color: stats.refundRate > 10 ? C.red : C.green },
    { label: 'Take Rate', value: `${stats.takeRate || 0}%`, color: C.cyan },
    { label: '딜 성사율', value: `${stats.dealSuccessRate || 0}%`, color: C.green },
  ];

  const alertItems = [
    { label: '승인대기 판매자', count: alerts.pendingSellers, path: '/admin/sellers' },
    { label: '미처리 분쟁', count: alerts.disputes, path: '/admin/disputes' },
    { label: '정산 대기', count: alerts.pendingSett, path: '/admin/settlements' },
    { label: '이상 탐지', count: alerts.anomalies, path: '/admin/anomalies' },
    { label: '미답변 신고', count: alerts.openReports, path: '/admin/reports' },
  ];

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 20 }}>대시보드</h1>

      {/* KPI Cards - clickable */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
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

      {/* Stat summary row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 24 }}>
        {statCards.map(s => (
          <div key={s.label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: '14px 12px', textAlign: 'center' }}>
            <div style={{ fontSize: 18, fontWeight: 700, color: s.color }}>{s.value}</div>
            <div style={{ fontSize: 11, color: C.textSec, marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Settlement status summary */}
      {stats.settlementSummary && Object.keys(stats.settlementSummary).length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 24 }}>
          {['HOLD', 'READY', 'APPROVED', 'PAID'].map(s => (
            <div key={s} onClick={() => navigate('/admin/settlements')} style={{
              background: C.card, border: `1px solid ${C.border}`, borderRadius: 12,
              padding: '12px', textAlign: 'center', cursor: 'pointer',
            }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: s === 'HOLD' ? C.orange : s === 'READY' ? C.cyan : s === 'APPROVED' ? '#4fc3f7' : C.green }}>
                {(stats.settlementSummary[s] || 0).toLocaleString()}
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
      {stats.reservationStatus && Object.keys(stats.reservationStatus).length > 0 && (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16, marginBottom: 24 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>예약 상태 분포</h3>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {Object.entries(stats.reservationStatus).map(([status, count]: [string, any]) => (
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
    </div>
  );
}
