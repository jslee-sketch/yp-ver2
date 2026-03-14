import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminPolicyParamsPage() {
  const [yaml, setYaml] = useState('');
  const [original, setOriginal] = useState('');
  const [history, setHistory] = useState<any[]>([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    const load = async () => {
      try { const r = await apiClient.get(API.ADMIN.POLICY_YAML); setYaml(r.data.content || ''); setOriginal(r.data.content || ''); } catch {}
      try { const r = await apiClient.get(API.ADMIN.POLICY_YAML_HISTORY); setHistory(Array.isArray(r.data) ? r.data : []); } catch {}
    };
    load();
  }, []);

  const save = async () => {
    setSaving(true); setMsg('');
    try {
      await apiClient.put(API.ADMIN.POLICY_YAML, { content: yaml });
      setOriginal(yaml); setMsg('저장 완료');
      const r = await apiClient.get(API.ADMIN.POLICY_YAML_HISTORY);
      setHistory(Array.isArray(r.data) ? r.data : []);
    } catch (e: any) {
      setMsg(e.response?.data?.detail || '저장 실패');
    }
    setSaving(false);
  };

  const revert = () => { setYaml(original); setMsg(''); };
  const changed = yaml !== original;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>정책 파라미터</h1>
      <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 120px)', minHeight: 500 }}>
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <button onClick={save} disabled={saving || !changed} style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: changed ? C.cyan : 'rgba(0,229,255,0.2)', color: changed ? '#000' : C.textSec, fontWeight: 600, cursor: changed ? 'pointer' : 'default', fontSize: 13 }}>
              {saving ? '저장 중...' : '저장'}
            </button>
            <button onClick={revert} disabled={!changed} style={{ padding: '8px 20px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: changed ? 'pointer' : 'default', fontSize: 13 }}>되돌리기</button>
            {msg && <span style={{ fontSize: 13, color: msg.includes('실패') || msg.includes('error') ? C.red : C.green, alignSelf: 'center' }}>{msg}</span>}
          </div>
          <textarea value={yaml} onChange={e => setYaml(e.target.value)} style={{ flex: 1, fontFamily: 'monospace', fontSize: 13, padding: 12, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, resize: 'vertical', lineHeight: 1.6, overflowY: 'auto', minHeight: 400 }} />
        </div>
        <div style={{ width: 280 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: C.textSec, marginBottom: 8 }}>변경 이력</h3>
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 8, maxHeight: 500, overflowY: 'auto' }}>
            {history.map((h, i) => (
              <div key={i} style={{ padding: '6px 8px', borderBottom: `1px solid ${C.border}`, fontSize: 12 }}>
                <div style={{ color: C.text }}>{h.filename}</div>
                <div style={{ color: C.textSec }}>{h.modified_at ? new Date(h.modified_at).toLocaleString('ko-KR') : ''} ({h.size}B)</div>
              </div>
            ))}
            {!history.length && <div style={{ padding: 12, textAlign: 'center', color: C.textSec, fontSize: 12 }}>이력 없음</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
