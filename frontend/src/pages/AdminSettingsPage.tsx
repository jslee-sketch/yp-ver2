import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminSettingsPage() {
  const [health, setHealth] = useState<any>(null);
  const [policy, setPolicy] = useState<any>(null);

  useEffect(() => {
    const load = async () => {
      try { const r = await apiClient.get(API.SYSTEM.HEALTH); setHealth(r.data); } catch {}
      try { const r = await apiClient.get(API.ADMIN.POLICY_STATUS); setPolicy(r.data); } catch {}
    };
    load();
  }, []);

  const infoRows = [
    { label: '서버 상태', value: health?.ok ? 'OK' : 'Unknown' },
    { label: 'API URL', value: (apiClient.defaults?.baseURL || window.location.origin) },
    { label: 'DB 타입', value: policy?.db_type || '-' },
    { label: 'TIME_POLICY', value: policy?.time_policy ? JSON.stringify(policy.time_policy) : '-' },
    { label: 'DEAD_TIME_POLICY', value: policy?.dead_time_policy ? JSON.stringify(policy.dead_time_policy) : '-' },
    { label: 'Platform Fee Rate', value: policy?.platform_fee_rate != null ? `${policy.platform_fee_rate * 100}%` : '-' },
    { label: 'Cooling Days', value: policy?.cooling_days ?? '-' },
    { label: 'Payment Timeout', value: policy?.payment_timeout ? `${policy.payment_timeout}초` : '-' },
  ];

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>시스템 설정</h1>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16 }}>
        <div style={{ fontSize: 12, color: C.orange, marginBottom: 12 }}>읽기 전용 — 정책 변경은 정책 파라미터 메뉴를 이용하세요</div>
        {infoRows.map(r => (
          <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: `1px solid ${C.border}`, fontSize: 13 }}>
            <span style={{ color: C.textSec, fontWeight: 600 }}>{r.label}</span>
            <span style={{ color: C.text, fontFamily: 'monospace', maxWidth: '60%', textAlign: 'right', wordBreak: 'break-all' }}>{r.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
