import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };

export default function AdminLogsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await apiClient.get(API.ACTIVITY.LIST, { params: { limit: 500 } });
      const data = r.data;
      setItems(Array.isArray(data) ? data : data?.items || data?.logs || []);
    } catch (e) { console.error('Logs load:', e); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const filtered = items.filter(l => {
    const q = search.toLowerCase();
    return !q || [l.event_type, l.actor_type, String(l.actor_id), String(l.entity_id), l.type].some(v => v && String(v).toLowerCase().includes(q));
  });

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>활동 로그</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="이벤트/액터/엔티티 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <button onClick={load} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>새로고침</button>
      </div>
      {loading ? <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div> : (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 700 }}>
              <thead style={stickyHead}>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {['ID', '이벤트', '액터', '대상', '금액', '시간'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((l, i) => (
                  <tr key={l.id || i} style={{ borderBottom: `1px solid ${C.border}`, cursor: l.meta ? 'pointer' : undefined }} onClick={() => l.meta && setExpanded(expanded === i ? null : i)}>
                    <td style={{ padding: '10px 8px', color: C.cyan }}>{l.id || i + 1}</td>
                    <td style={{ padding: '10px 8px', color: C.text }}>{l.event_type || l.type || '-'}</td>
                    <td style={{ padding: '10px 8px', color: C.textSec }}>{l.actor_type || '-'} #{l.actor_id || ''}</td>
                    <td style={{ padding: '10px 8px', color: C.textSec }}>{l.entity_type || ''} #{l.entity_id || ''}</td>
                    <td style={{ padding: '10px 8px', color: C.orange }}>{l.amount ? Number(l.amount).toLocaleString() : '-'}</td>
                    <td style={{ padding: '10px 8px', color: C.textSec }}>{l.created_at ? new Date(l.created_at).toLocaleString('ko-KR') : '-'}</td>
                  </tr>
                ))}
                {filtered.map((l, i) => expanded === i && l.meta ? (
                  <tr key={`${l.id || i}-m`}><td colSpan={6} style={{ padding: '8px 16px', background: 'rgba(0,0,0,0.15)' }}><pre style={{ fontSize: 11, color: C.textSec, whiteSpace: 'pre-wrap', margin: 0 }}>{typeof l.meta === 'string' ? l.meta : JSON.stringify(l.meta, null, 2)}</pre></td></tr>
                ) : null)}
                {!filtered.length && <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>로그 없음</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{filtered.length}건</div>
    </div>
  );
}
