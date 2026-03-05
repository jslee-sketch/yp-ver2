import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  green: '#00e676', orange: '#ff9100', red: '#ff5252',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
};

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  ACTIVE:    { bg: 'rgba(0,230,118,0.1)',  color: C.green },
  SUSPENDED: { bg: 'rgba(255,145,0,0.1)',  color: C.orange },
  CLOSED:    { bg: 'rgba(255,82,82,0.1)',  color: C.red },
};

interface Actuator {
  id: number;
  name?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  status?: string;
  is_business?: boolean;
  business_name?: string;
  business_number?: string;
  created_at?: string;
}

export default function AdminActuatorsPage() {
  const [actuators, setActuators] = useState<Actuator[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.get(API.ACTUATORS.LIST);
        setActuators(Array.isArray(res.data) ? res.data : []);
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, []);

  return (
    <div style={{ padding: '24px 16px', maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>
        액츄에이터 관리
      </h1>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 20 }}>
        총 {actuators.length}명
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>로딩 중...</div>
      ) : actuators.length === 0 ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>액츄에이터가 없습니다.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {actuators.map(a => {
            const st = STATUS_STYLE[a.status || 'ACTIVE'] || STATUS_STYLE.ACTIVE;
            return (
              <div key={a.id} style={{
                background: C.card, border: `1px solid ${C.border}`, borderRadius: 14,
                padding: '16px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 4 }}>
                    #{a.id} {a.name || a.nickname || '(이름 없음)'}
                    {a.is_business && (
                      <span style={{ fontSize: 11, color: C.orange, marginLeft: 8 }}>사업자</span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: C.textSec }}>
                    {a.email} · {a.phone || '-'}
                    {a.business_name && ` · ${a.business_name}`}
                    {a.business_number && ` (${a.business_number})`}
                  </div>
                  <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                    가입: {a.created_at ? new Date(a.created_at).toLocaleDateString('ko-KR') : '-'}
                  </div>
                </div>
                <span style={{
                  padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                  background: st.bg, color: st.color, flexShrink: 0,
                }}>
                  {a.status || 'ACTIVE'}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
