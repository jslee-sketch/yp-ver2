import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminLogsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await apiClient.get(API.ACTIVITY.LIST, { params: { limit: 200 } });
      setItems(Array.isArray(r.data) ? r.data : []);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const filtered = items.filter(l => {
    const q = search.toLowerCase();
    return !q || [l.event_type, l.actor_type, String(l.actor_id), String(l.entity_id)].some(v => v && String(v).toLowerCase().includes(q));
  });

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>활동 로그</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="이벤트/액터/엔티티 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
      </div>
      {loading ? <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div> : (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 700 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['ID', '이벤트', '액터', '대상', '금액', '시간'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((l, i) => (
                <>
                  <tr key={i} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer' }} onClick={() => setExpanded(expanded === i ? null : i)}>
                    <td style={{ padding: '10px 8px', color: C.cyan }}>{l.id || i}</td>
                    <td style={{ padding: '10px 8px', color: C.text }}>{l.event_type || l.type || '-'}</td>
                    <td style={{ padding: '10px 8px', color: C.textSec }}>{l.actor_type || '-'} #{l.actor_id || ''}</td>
                    <td style={{ padding: '10px 8px', color: C.textSec }}>{l.entity_type || ''} #{l.entity_id || ''}</td>
                    <td style={{ padding: '10px 8px', color: C.orange }}>{l.amount ? Number(l.amount).toLocaleString() : '-'}</td>
                    <td style={{ padding: '10px 8px', color: C.textSec }}>{l.created_at ? new Date(l.created_at).toLocaleString('ko-KR') : '-'}</td>
                  </tr>
                  {expanded === i && l.meta && (
                    <tr key={`${i}-m`}><td colSpan={6} style={{ padding: '8px 16px', background: 'rgba(0,0,0,0.1)' }}><pre style={{ fontSize: 11, color: C.textSec, whiteSpace: 'pre-wrap', margin: 0 }}>{typeof l.meta === 'string' ? l.meta : JSON.stringify(l.meta, null, 2)}</pre></td></tr>
                  )}
                </>
              ))}
              {!filtered.length && <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>로그 없음</td></tr>}
            </tbody>
          </table>
        </div>
      )}
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{filtered.length}건</div>
    </div>
  );
}
