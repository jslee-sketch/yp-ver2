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
      const [buyersR, sellersR, dealsR, offersR, settR, anomR, recentR, reportsR] = await Promise.allSettled([
        apiClient.get(API.BUYERS.LIST),
        apiClient.get(API.SELLERS.LIST),
        apiClient.get(API.DEALS.LIST),
        apiClient.get(API.OFFERS.LIST),
        apiClient.get(API.SETTLEMENTS.ADMIN_LIST),
        apiClient.get(API.ADMIN.ANOMALY_DETECT, { params: { lookback_hours: 24 } }),
        apiClient.get(API.ACTIVITY.LIST, { params: { limit: 10 } }),
        apiClient.get(API.ADMIN.REPORTS),
      ]);

      const arr = (r: any) => (r.status === 'fulfilled' && Array.isArray(r.value.data)) ? r.value.data : (r.status === 'fulfilled' && r.value.data?.items) ? r.value.data.items : [];
      const buyers = arr(buyersR); const sellers = arr(sellersR);
      const deals = arr(dealsR); const offers = arr(offersR);
      const setts = arr(settR); const anoms = arr(anomR);
      const reps = arr(reportsR);

      const pendingSellers = sellers.filter((s: any) => !s.verified_at).length;
      const pendingSett = setts.filter((s: any) => s.status === 'READY' || s.status === 'HOLD').length;
      const disputes = setts.filter((s: any) => s.is_disputed).length;
      const openReports = reps.filter((r: any) => r.status === 'OPEN').length;

      setStats({ buyers: buyers.length, sellers: sellers.length, deals: deals.length, offers: offers.length, pendingSellers, pendingSett });
      setAlerts({ pendingSellers, pendingSett, disputes, anomalies: anoms.length, openReports });
      setRecent(recentR.status === 'fulfilled' ? (Array.isArray(recentR.value.data) ? recentR.value.data.slice(0, 8) : []) : []);
      setLoading(false);
    };
    load();
  }, []);

  const kpi = [
    { label: '구매자', value: stats.buyers || 0, color: C.green },
    { label: '판매자', value: stats.sellers || 0, color: C.cyan },
    { label: '딜', value: stats.deals || 0, color: '#e040fb' },
    { label: '오퍼', value: stats.offers || 0, color: C.orange },
    { label: '승인대기', value: stats.pendingSellers || 0, color: C.red },
    { label: '정산대기', value: stats.pendingSett || 0, color: '#ffab40' },
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

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginBottom: 24 }}>
        {kpi.map(k => (
          <div key={k.label} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: '16px 12px', textAlign: 'center' }}>
            <div style={{ fontSize: 24, fontWeight: 800, color: k.color }}>{k.value}</div>
            <div style={{ fontSize: 12, color: C.textSec, marginTop: 4 }}>{k.label}</div>
          </div>
        ))}
      </div>

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
