import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

const TABS = ['전체', '제안', '승인', '적용', '거부'] as const;
const TAB_STATUS: Record<string, string> = { '제안': 'PROPOSED', '승인': 'APPROVED', '적용': 'APPLIED', '거부': 'REJECTED' };

export default function AdminPolicyProposalsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [tab, setTab] = useState<string>('전체');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setError('');
    try {
      const params: any = {};
      if (TAB_STATUS[tab]) params.status = TAB_STATUS[tab];
      const r = await apiClient.get(API.ADMIN.POLICY_PROPOSALS, { params });
      const data = r.data;
      const list = Array.isArray(data) ? data : (data?.items || data?.results || []);
      setItems(list);
    } catch (e: any) {
      console.error('PolicyProposals load error:', e);
      setError(e?.message || 'API 오류');
      setItems([]);
    }
    setLoading(false);
  };
  useEffect(() => { setLoading(true); load(); }, [tab]);

  const action = async (id: number, act: string) => {
    try { await apiClient.post(API.ADMIN.POLICY_PROPOSAL(id) + `/${act}`); load(); } catch {}
  };

  const statusColor: Record<string, string> = { PROPOSED: C.orange, APPROVED: C.cyan, APPLIED: C.green, REJECTED: C.red };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>핑퐁이 정책 제안</h1>
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '6px 14px', borderRadius: 6, border: 'none', fontSize: 13, cursor: 'pointer',
            background: tab === t ? C.cyan : 'transparent', color: tab === t ? '#000' : C.textSec, fontWeight: tab === t ? 700 : 400,
          }}>{t}</button>
        ))}
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 800 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['#', '제목', '유형', '파라미터', '현재값', '제안값', '상태', ''].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(p => (
              <tr key={p.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={{ padding: '10px 8px', color: C.cyan }}>{p.id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{p.title || '-'}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>{p.proposal_type || '-'}</td>
                <td style={{ padding: '10px 8px', color: C.textSec, fontFamily: 'monospace' }}>{p.param_key || '-'}</td>
                <td style={{ padding: '10px 8px', color: C.orange }}>{p.current_value != null ? String(p.current_value) : '-'}</td>
                <td style={{ padding: '10px 8px', color: C.green }}>{p.proposed_value != null ? String(p.proposed_value) : '-'}</td>
                <td style={{ padding: '10px 8px' }}><span style={{ color: statusColor[p.status] || C.textSec, fontWeight: 600 }}>{p.status}</span></td>
                <td style={{ padding: '10px 8px', display: 'flex', gap: 4 }}>
                  {p.status === 'PROPOSED' && <>
                    <button onClick={() => action(p.id, 'approve')} style={{ padding: '4px 8px', fontSize: 11, borderRadius: 5, border: 'none', cursor: 'pointer', background: 'rgba(0,229,255,0.15)', color: C.cyan }}>승인</button>
                    <button onClick={() => action(p.id, 'reject')} style={{ padding: '4px 8px', fontSize: 11, borderRadius: 5, border: 'none', cursor: 'pointer', background: 'rgba(255,82,82,0.15)', color: C.red }}>거부</button>
                  </>}
                  {p.status === 'APPROVED' && <button onClick={() => action(p.id, 'apply')} style={{ padding: '4px 8px', fontSize: 11, borderRadius: 5, border: 'none', cursor: 'pointer', background: 'rgba(0,230,118,0.15)', color: C.green }}>적용</button>}
                  {p.status === 'APPLIED' && <button onClick={() => action(p.id, 'rollback')} style={{ padding: '4px 8px', fontSize: 11, borderRadius: 5, border: 'none', cursor: 'pointer', background: 'rgba(255,145,0,0.15)', color: C.orange }}>롤백</button>}
                </td>
              </tr>
            ))}
            {!items.length && <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>{error ? `오류: ${error}` : '제안 없음'}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
