import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

const gradeColor: Record<string, string> = { HIGH: '#ff5252', MEDIUM: '#ff9100', LOW: '#448aff' };

export default function AdminAnomaliesPage() {
  const [items, setItems] = useState<any[]>([]);
  const [hours, setHours] = useState(24);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await apiClient.get(API.ADMIN.ANOMALY_DETECT, { params: { lookback_hours: hours } });
      setItems(Array.isArray(r.data) ? r.data : []);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>이상 감지</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input type="number" value={hours} onChange={e => setHours(Number(e.target.value))} min={1} max={720} style={{ width: 100, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
        <span style={{ alignSelf: 'center', color: C.textSec, fontSize: 13 }}>시간 이내</span>
        <button onClick={load} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>탐지</button>
      </div>
      {loading ? <div style={{ padding: 40, color: C.textSec }}>분석 중...</div> : (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 650 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['등급', '유형', '대상', '설명', '시각'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((a, i) => (
                <>
                  <tr key={i} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer' }} onClick={() => setExpanded(expanded === i ? null : i)}>
                    <td style={{ padding: '10px 8px' }}><span style={{ color: gradeColor[a.grade || a.severity] || C.textSec, fontWeight: 700 }}>{a.grade || a.severity || '-'}</span></td>
                    <td style={{ padding: '10px 8px', color: C.text }}>{a.type || a.anomaly_type || '-'}</td>
                    <td style={{ padding: '10px 8px', color: C.cyan }}>{a.target || a.entity || '-'}</td>
                    <td style={{ padding: '10px 8px', color: C.text }}>{a.description || a.message || '-'}</td>
                    <td style={{ padding: '10px 8px', color: C.textSec }}>{a.detected_at || a.timestamp ? new Date(a.detected_at || a.timestamp).toLocaleString('ko-KR') : '-'}</td>
                  </tr>
                  {expanded === i && a.evidence && (
                    <tr key={`${i}-ev`}><td colSpan={5} style={{ padding: '8px 16px', background: 'rgba(0,0,0,0.1)' }}><pre style={{ fontSize: 11, color: C.textSec, whiteSpace: 'pre-wrap', margin: 0 }}>{typeof a.evidence === 'string' ? a.evidence : JSON.stringify(a.evidence, null, 2)}</pre></td></tr>
                  )}
                </>
              ))}
              {!items.length && <tr><td colSpan={5} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>이상 없음</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
