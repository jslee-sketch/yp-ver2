import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminActuatorsPage() {
  const [actuators, setActuators] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [commissions, setCommissions] = useState<Record<number, any>>({});

  useEffect(() => {
    const load = async () => {
      try {
        const r = await apiClient.get(API.ACTUATORS.LIST);
        const list = Array.isArray(r.data) ? r.data : [];
        setActuators(list);
        const cMap: Record<number, any> = {};
        await Promise.allSettled(list.map(async (a: any) => {
          try { const cr = await apiClient.get(API.ACTUATORS.COMMISSIONS_SUMMARY(a.id)); cMap[a.id] = cr.data; } catch {}
        }));
        setCommissions(cMap);
      } catch {}
      setLoading(false);
    };
    load();
  }, []);

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>액추에이터 관리</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="이름/이메일/전화 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 700 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['ID', '이름', '이메일', '전화', '연결판매자', '커미션합계', '상태'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {actuators.filter(a => { const q = search.toLowerCase(); return !q || [a.name, a.nickname, a.email, a.phone, String(a.id)].some(v => v && String(v).toLowerCase().includes(q)); }).map(a => (
              <tr key={a.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={{ padding: '10px 8px', color: C.cyan }}>A-{a.id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{a.name || a.nickname || '-'}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{a.email}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>{a.phone || '-'}</td>
                <td style={{ padding: '10px 8px', color: C.orange }}>{commissions[a.id]?.seller_count ?? '-'}</td>
                <td style={{ padding: '10px 8px', color: C.green }}>{(commissions[a.id]?.total_commission || 0).toLocaleString()}원</td>
                <td style={{ padding: '10px 8px' }}><span style={{ color: a.is_active === false ? C.red : C.green, fontWeight: 600 }}>{a.is_active === false ? '비활성' : '활성'}</span></td>
              </tr>
            ))}
            {!actuators.length && <tr><td colSpan={7} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>액추에이터 없음</td></tr>}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{actuators.length}명</div>
    </div>
  );
}
