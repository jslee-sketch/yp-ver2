import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminPolicyDocsPage() {
  const [docs, setDocs] = useState<any[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState('');
  const [original, setOriginal] = useState('');
  const [saving, setSaving] = useState(false);
  const [newPath, setNewPath] = useState('');
  const [showNew, setShowNew] = useState(false);

  const loadList = async () => {
    try { const r = await apiClient.get(API.ADMIN.POLICY_DOCS); setDocs(Array.isArray(r.data) ? r.data : []); } catch {}
  };
  useEffect(() => { loadList(); }, []);

  const selectDoc = async (path: string) => {
    try {
      const r = await apiClient.get(API.ADMIN.POLICY_DOC(path));
      setContent(r.data.content || '');
      setOriginal(r.data.content || '');
      setSelected(path);
    } catch {}
  };

  const save = async () => {
    if (!selected) return;
    setSaving(true);
    try { await apiClient.put(API.ADMIN.POLICY_DOC(selected), { content }); setOriginal(content); } catch {}
    setSaving(false);
  };

  const createDoc = async () => {
    if (!newPath) return;
    try {
      await apiClient.post(API.ADMIN.POLICY_DOCS, { path: newPath, content: '# ' + newPath + '\n' });
      setShowNew(false); setNewPath(''); loadList();
    } catch {}
  };

  const changed = content !== original;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>정책 문서</h1>
      <div style={{ display: 'flex', gap: 16, minHeight: 500 }}>
        <div style={{ width: 260, flexShrink: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: C.textSec }}>문서 목록</span>
            <button onClick={() => setShowNew(true)} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,229,255,0.15)', color: C.cyan }}>새 문서</button>
          </div>
          {showNew && (
            <div style={{ display: 'flex', gap: 4, marginBottom: 8 }}>
              <input value={newPath} onChange={e => setNewPath(e.target.value)} placeholder="filename.md" style={{ flex: 1, padding: '6px 8px', fontSize: 12, borderRadius: 6, border: `1px solid ${C.border}`, background: C.card, color: C.text }} />
              <button onClick={createDoc} style={{ padding: '6px 10px', fontSize: 12, borderRadius: 6, border: 'none', background: C.cyan, color: '#000', cursor: 'pointer' }}>생성</button>
            </div>
          )}
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, overflow: 'auto', maxHeight: 460 }}>
            {docs.map(d => (
              <div key={d.path} onClick={() => selectDoc(d.path)} style={{
                padding: '8px 12px', borderBottom: `1px solid ${C.border}`, cursor: 'pointer', fontSize: 13,
                background: selected === d.path ? 'rgba(0,229,255,0.08)' : 'transparent', color: selected === d.path ? C.cyan : C.text,
              }}>
                <div>{d.path}</div>
                <div style={{ fontSize: 11, color: C.textSec }}>{d.size}B</div>
              </div>
            ))}
            {!docs.length && <div style={{ padding: 16, textAlign: 'center', color: C.textSec, fontSize: 12 }}>문서 없음</div>}
          </div>
        </div>

        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          {selected ? (
            <>
              <div style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'center' }}>
                <span style={{ fontSize: 14, fontWeight: 600, color: C.cyan }}>{selected}</span>
                <div style={{ flex: 1 }} />
                <button onClick={save} disabled={saving || !changed} style={{ padding: '6px 16px', borderRadius: 6, border: 'none', background: changed ? C.cyan : 'rgba(0,229,255,0.2)', color: changed ? '#000' : C.textSec, fontWeight: 600, cursor: changed ? 'pointer' : 'default', fontSize: 13 }}>
                  {saving ? '저장 중...' : '저장'}
                </button>
              </div>
              <textarea value={content} onChange={e => setContent(e.target.value)} style={{ flex: 1, fontFamily: 'monospace', fontSize: 13, padding: 12, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, resize: 'none', lineHeight: 1.6 }} />
            </>
          ) : (
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.textSec }}>좌측에서 문서를 선택하세요</div>
          )}
        </div>
      </div>
    </div>
  );
}
