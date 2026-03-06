import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminReportsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<any>(null);
  const [resolution, setResolution] = useState('');

  const load = async () => {
    try {
      const params: any = {};
      if (statusFilter) params.status = statusFilter;
      const r = await apiClient.get(API.ADMIN.REPORTS, { params });
      setItems(Array.isArray(r.data) ? r.data : r.data?.items || []);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, [statusFilter]);

  const resolve = async () => {
    if (!modal || !resolution) return;
    try {
      await apiClient.post(API.ADMIN.REPORT_RESOLVE(modal.id), { resolution, action_taken: 'admin_resolved' });
      setModal(null); setResolution(''); load();
    } catch {}
  };

  const statusColor: Record<string, string> = { OPEN: C.orange, IN_REVIEW: C.cyan, RESOLVED: C.green, DISMISSED: C.textSec };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>신고 관리</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }}>
          <option value="">전체 상태</option>
          {['OPEN', 'IN_REVIEW', 'RESOLVED', 'DISMISSED'].map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['#', '신고자', '대상', '카테고리', '설명', '상태', ''].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(r => (
              <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={{ padding: '10px 8px', color: C.cyan }}>{r.id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{r.reporter_type} #{r.reporter_id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{r.target_type} #{r.target_id}</td>
                <td style={{ padding: '10px 8px', color: C.orange }}>{r.category}</td>
                <td style={{ padding: '10px 8px', color: C.textSec, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.description || '-'}</td>
                <td style={{ padding: '10px 8px' }}><span style={{ color: statusColor[r.status] || C.textSec, fontWeight: 600 }}>{r.status}</span></td>
                <td style={{ padding: '10px 8px' }}>
                  {r.status === 'OPEN' && <button onClick={() => { setModal(r); setResolution(''); }} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,229,255,0.15)', color: C.cyan }}>처리</button>}
                </td>
              </tr>
            ))}
            {!items.length && <tr><td colSpan={7} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>신고 없음</td></tr>}
          </tbody>
        </table>
      </div>

      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 400, border: `1px solid ${C.border}` }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 12 }}>신고 처리 #{modal.id}</h3>
            <div style={{ fontSize: 13, color: C.textSec, marginBottom: 12 }}>{modal.description}</div>
            <textarea value={resolution} onChange={e => setResolution(e.target.value)} placeholder="처리 내용 입력" style={{ width: '100%', minHeight: 80, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical' }} />
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button onClick={resolve} style={{ flex: 1, padding: '10px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer' }}>처리 완료</button>
              <button onClick={() => setModal(null)} style={{ flex: 1, padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>취소</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
