import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };
const gradeColor: Record<string, string> = { HIGH: '#ff5252', MEDIUM: '#ff9100', LOW: '#448aff' };

export default function AdminAnomaliesPage() {
  const [items, setItems] = useState<any[]>([]);
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [modal, setModal] = useState<any>(null);
  const [actionPlan, setActionPlan] = useState('');
  const [actionResult, setActionResult] = useState('');
  const [anomalyStatuses, setAnomalyStatuses] = useState<Record<number, string>>({});

  const load = async () => {
    setLoading(true);
    try {
      const r = await apiClient.get(API.ADMIN.ANOMALY_DETECT, { params: { lookback_hours: hours } });
      setItems(Array.isArray(r.data) ? r.data : r.data?.items || []);
    } catch (e) { console.error('Anomalies load:', e); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const getStatus = (a: any, i: number) => anomalyStatuses[a.id || i] || 'Open';
  const setStatus = (a: any, i: number, s: string) => setAnomalyStatuses({ ...anomalyStatuses, [a.id || i]: s });

  const filtered = items.filter(a => {
    if (statusFilter && getStatus(a, items.indexOf(a)) !== statusFilter) return false;
    return true;
  });

  const openModal = (a: any, i: number) => {
    setModal({ ...a, _idx: i });
    setActionPlan('');
    setActionResult('');
  };

  const handleComplete = () => {
    if (!modal) return;
    setStatus(modal, modal._idx, 'Closed');
    setModal(null);
  };

  const handleProcessing = () => {
    if (!modal) return;
    setStatus(modal, modal._idx, 'Processing');
  };

  const statusBadge = (s: string) => {
    const colors: Record<string, string> = { Open: C.orange, Processing: C.cyan, Closed: C.green };
    return <span style={{ color: colors[s] || C.textSec, fontWeight: 600 }}>{s === 'Open' ? 'Open : 미처리' : s === 'Processing' ? 'Processing : 처리 중' : 'Closed : 완료'}</span>;
  };

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>이상 감지</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <input type="number" value={hours} onChange={e => setHours(Number(e.target.value))} min={1} max={720} style={{ width: 100, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <span style={{ alignSelf: 'center', color: C.textSec, fontSize: 13 }}>시간 이내</span>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: '#1a1a2e', color: '#e0e0e0', fontSize: 13 }}>
          <option value="">전체 처리상태</option>
          <option value="Open">Open : 미처리</option>
          <option value="Processing">Processing : 처리 중</option>
          <option value="Closed">Closed : 완료</option>
        </select>
        <button onClick={load} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>탐지</button>
      </div>
      {loading ? <div style={{ padding: 40, color: C.textSec }}>분석 중...</div> : (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 850 }}>
              <thead style={stickyHead}>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  {['식별번호', '등급', '유형', '대상', '관련번호', '설명', '처리상태', '시각'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((a, i) => {
                  const idx = items.indexOf(a);
                  const st = getStatus(a, idx);
                  const targetDisplay = a.buyer_id ? `B-${a.buyer_id}` : a.seller_id ? `S-${a.seller_id}` : a.target || a.entity || '-';
                  const relatedDisplay = a.deal_id ? `D-${a.deal_id}` : a.reservation_id ? `R-${a.reservation_id}` : '-';
                  return (
                    <tr key={a.id || i} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer' }} onClick={() => openModal(a, idx)}>
                      <td style={{ padding: '10px 8px', color: '#4ade80', textDecoration: 'underline' }}>ANO-{String(a.id || i + 1).padStart(3, '0')}</td>
                      <td style={{ padding: '10px 8px' }}><span style={{ color: gradeColor[a.grade || a.severity] || C.textSec, fontWeight: 700 }}>{a.grade || a.severity || '-'}</span></td>
                      <td style={{ padding: '10px 8px', color: C.text }}>{a.type || a.anomaly_type || '-'}</td>
                      <td style={{ padding: '10px 8px', color: C.cyan }}>{targetDisplay}</td>
                      <td style={{ padding: '10px 8px', color: C.textSec }}>{relatedDisplay}</td>
                      <td style={{ padding: '10px 8px', color: C.text, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.description || a.message || '-'}</td>
                      <td style={{ padding: '10px 8px' }}>{statusBadge(st)}</td>
                      <td style={{ padding: '10px 8px', color: C.textSec, fontSize: 12 }}>{a.detected_at || a.timestamp ? new Date(a.detected_at || a.timestamp).toLocaleString('ko-KR') : '-'}</td>
                    </tr>
                  );
                })}
                {!filtered.length && <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>이상 없음</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 500, maxWidth: 600, border: `1px solid ${C.border}`, maxHeight: '85vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 16 }}>
              이상 감지 상세 — ANO-{String(modal.id || (modal._idx + 1)).padStart(3, '0')}
            </h3>
            {Object.entries({
              '발생일자': modal.detected_at || modal.timestamp ? new Date(modal.detected_at || modal.timestamp).toLocaleString('ko-KR') : '-',
              '등급': modal.grade || modal.severity || '-',
              '유형': modal.type || modal.anomaly_type || '-',
              '대상': modal.buyer_id ? `B-${modal.buyer_id}` : modal.seller_id ? `S-${modal.seller_id}` : modal.target || '-',
              '관련 딜': modal.deal_id ? `D-${modal.deal_id}` : '-',
              '관련 예약': modal.reservation_id ? `R-${modal.reservation_id}` : '-',
              '처리상태': getStatus(modal, modal._idx),
            }).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${C.border}`, fontSize: 13 }}>
                <span style={{ color: C.textSec }}>{k}</span><span style={{ color: C.text }}>{String(v)}</span>
              </div>
            ))}
            <div style={{ marginTop: 12, padding: 12, background: 'rgba(0,0,0,0.1)', borderRadius: 8, fontSize: 13, color: C.text }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>내용</div>
              {modal.description || modal.message || '-'}
            </div>
            {modal.evidence && (
              <div style={{ marginTop: 8, padding: 12, background: 'rgba(0,0,0,0.1)', borderRadius: 8 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 4 }}>Evidence</div>
                <pre style={{ fontSize: 11, color: C.textSec, whiteSpace: 'pre-wrap', margin: 0 }}>{typeof modal.evidence === 'string' ? modal.evidence : JSON.stringify(modal.evidence, null, 2)}</pre>
              </div>
            )}
            <div style={{ marginTop: 16 }}>
              <label style={{ fontSize: 13, color: C.textSec, fontWeight: 600 }}>처리 방향:</label>
              <textarea value={actionPlan} onChange={e => setActionPlan(e.target.value)} placeholder="처리 방향을 입력하세요" style={{ width: '100%', minHeight: 60, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical', marginTop: 4 }} />
              {actionPlan && getStatus(modal, modal._idx) === 'Open' && (
                <button onClick={handleProcessing} style={{ marginTop: 8, padding: '8px 16px', borderRadius: 8, border: 'none', background: 'rgba(0,229,255,0.15)', color: C.cyan, fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>처리 중으로 변경</button>
              )}
            </div>
            <div style={{ marginTop: 12 }}>
              <label style={{ fontSize: 13, color: C.textSec, fontWeight: 600 }}>처리 결과:</label>
              <textarea value={actionResult} onChange={e => setActionResult(e.target.value)} placeholder="처리 결과를 입력하세요" style={{ width: '100%', minHeight: 60, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical', marginTop: 4 }} />
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              <button onClick={handleComplete} disabled={!actionResult} style={{ flex: 1, padding: '10px', borderRadius: 8, border: 'none', background: actionResult ? C.green : 'rgba(0,230,118,0.2)', color: actionResult ? '#000' : C.textSec, fontWeight: 600, cursor: actionResult ? 'pointer' : 'default', fontSize: 13 }}>완료</button>
              <button onClick={() => setModal(null)} style={{ flex: 1, padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>닫기</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
