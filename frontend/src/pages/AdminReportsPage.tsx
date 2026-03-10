import { useState, useEffect, useRef } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import DateRangeFilter from '../components/common/DateRangeFilter';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };

export default function AdminReportsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<any>(null);
  const [resolution, setResolution] = useState('');
  const [actionPlan, setActionPlan] = useState('');
  const [error, setError] = useState('');

  const dateRef = useRef({ from: '', to: '' });

  const load = async () => {
    setError('');
    try {
      const params: any = {};
      if (statusFilter) params.status = statusFilter;
      if (dateRef.current.from) params.date_from = dateRef.current.from;
      if (dateRef.current.to) params.date_to = dateRef.current.to;
      const r = await apiClient.get(API.ADMIN.REPORTS, { params });
      const data = r.data;
      const list = Array.isArray(data) ? data : (data?.items || data?.results || []);
      setItems(list);
    } catch (e: any) {
      console.error('Reports load error:', e);
      setError(e?.message || 'API 오류');
      setItems([]);
    }
    setLoading(false);
  };
  useEffect(() => { load(); }, [statusFilter]);

  const resolve = async () => {
    if (!modal || !resolution) return;
    try {
      await apiClient.post(API.ADMIN.REPORT_RESOLVE(modal.id), { resolution, action_taken: 'admin_resolved' });
      setModal(null); setResolution(''); setActionPlan(''); load();
    } catch {}
  };

  const statusColor: Record<string, string> = { OPEN: C.orange, IN_REVIEW: C.cyan, RESOLVED: C.green, DISMISSED: C.textSec };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>신고 관리</h1>
      <DateRangeFilter onFilter={(f, t) => { dateRef.current = { from: f, to: t }; load(); }} style={{ marginBottom: 12 }} />
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: '#1a1a2e', color: '#e0e0e0', fontSize: 13 }}>
          <option value="">전체 상태</option>
          <option value="OPEN">OPEN : 접수됨</option>
          <option value="IN_REVIEW">IN_REVIEW : 검토 중</option>
          <option value="RESOLVED">RESOLVED : 처리 완료</option>
          <option value="DISMISSED">DISMISSED : 기각</option>
        </select>
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 800 }}>
            <thead style={stickyHead}>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['식별번호', '신고자', '대상', '카테고리', '설명', '접수일', '처리상태', ''].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((r, i) => (
                <tr key={r.id || i} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer' }} onClick={() => { setModal(r); setResolution(''); setActionPlan(''); }}>
                  <td style={{ padding: '10px 8px', color: '#4ade80', textDecoration: 'underline' }}>RPT-{String(r.id || i + 1).padStart(3, '0')}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{r.reporter_type} #{r.reporter_id}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{r.target_type} #{r.target_id}</td>
                  <td style={{ padding: '10px 8px', color: C.orange }}>{r.category}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.description || '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec, fontSize: 12 }}>{r.created_at ? r.created_at.split('T')[0]?.replace(/-/g, '.') : '-'}</td>
                  <td style={{ padding: '10px 8px' }}><span style={{ color: statusColor[r.status] || C.textSec, fontWeight: 600 }}>{r.status}</span></td>
                  <td style={{ padding: '10px 8px' }}>
                    {r.status === 'OPEN' && <button onClick={e => { e.stopPropagation(); setModal(r); setResolution(''); }} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,229,255,0.15)', color: C.cyan }}>처리</button>}
                  </td>
                </tr>
              ))}
              {!items.length && <tr><td colSpan={7} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>{error ? `오류: ${error}` : '신고 없음'}</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{items.length}건</div>

      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 500, maxWidth: 600, border: `1px solid ${C.border}`, maxHeight: '85vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 16 }}>
              신고 상세 — RPT-{String(modal.id).padStart(3, '0')}
            </h3>
            {Object.entries({
              '접수일': modal.created_at ? new Date(modal.created_at).toLocaleString('ko-KR') : '-',
              '신고자': `${modal.reporter_type} #${modal.reporter_id}`,
              '대상': `${modal.target_type} #${modal.target_id}`,
              '카테고리': modal.category || '-',
              '상태': modal.status || '-',
            }).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${C.border}`, fontSize: 13 }}>
                <span style={{ color: C.textSec }}>{k}</span><span style={{ color: C.text }}>{String(v)}</span>
              </div>
            ))}
            <div style={{ marginTop: 12, padding: 12, background: 'rgba(0,0,0,0.1)', borderRadius: 8, fontSize: 13, color: C.text }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>신고 내용</div>
              {modal.description || '-'}
            </div>

            {modal.status === 'OPEN' && (
              <div style={{ marginTop: 16, padding: 16, background: 'rgba(0,229,255,0.04)', borderRadius: 8, border: `1px solid rgba(0,229,255,0.1)` }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 8 }}>신고 처리</div>
                <label style={{ fontSize: 12, color: C.textSec }}>처리 방향:</label>
                <textarea value={actionPlan} onChange={e => setActionPlan(e.target.value)} placeholder="처리 방향을 입력하세요" style={{ width: '100%', minHeight: 60, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical', marginTop: 4, marginBottom: 8 }} />
                <label style={{ fontSize: 12, color: C.textSec }}>처리 결과:</label>
                <textarea value={resolution} onChange={e => setResolution(e.target.value)} placeholder="처리 결과를 입력하세요" style={{ width: '100%', minHeight: 60, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical', marginTop: 4, marginBottom: 8 }} />
                <button onClick={resolve} disabled={!resolution} style={{ width: '100%', padding: '10px', borderRadius: 8, border: 'none', background: resolution ? C.green : 'rgba(0,230,118,0.2)', color: resolution ? '#000' : C.textSec, fontWeight: 600, cursor: resolution ? 'pointer' : 'default', fontSize: 13 }}>처리 완료</button>
              </div>
            )}

            {modal.resolution && (
              <div style={{ marginTop: 12, padding: 12, background: 'rgba(0,230,118,0.06)', borderRadius: 8, border: `1px solid rgba(0,230,118,0.15)` }}>
                <div style={{ fontSize: 12, color: C.green, fontWeight: 600, marginBottom: 4 }}>처리 결과</div>
                <div style={{ fontSize: 13, color: C.text }}>{modal.resolution}</div>
              </div>
            )}

            <button onClick={() => setModal(null)} style={{ marginTop: 12, width: '100%', padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>닫기</button>
          </div>
        </div>
      )}
    </div>
  );
}
