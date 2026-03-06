import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminAnnouncementsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<any>(null);
  const [form, setForm] = useState({ title: '', content: '', category: 'general', target_role: 'all', is_pinned: false, is_published: false });

  const load = async () => {
    try { const r = await apiClient.get(API.ADMIN.ANNOUNCEMENTS); setItems(r.data?.items || []); } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const openNew = () => {
    setForm({ title: '', content: '', category: 'general', target_role: 'all', is_pinned: false, is_published: false });
    setModal({ mode: 'create' });
  };
  const openEdit = (a: any) => {
    setForm({ title: a.title, content: a.content || '', category: a.category || 'general', target_role: a.target_role || 'all', is_pinned: a.is_pinned, is_published: a.is_published });
    setModal({ mode: 'edit', id: a.id });
  };
  const save = async () => {
    try {
      if (modal.mode === 'create') await apiClient.post(API.ADMIN.ANNOUNCEMENTS, form);
      else await apiClient.put(API.ADMIN.ANNOUNCEMENT(modal.id), form);
      setModal(null); load();
    } catch {}
  };
  const del = async (id: number) => {
    try { await apiClient.delete(API.ADMIN.ANNOUNCEMENT(id)); load(); } catch {}
  };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text }}>공지사항</h1>
        <button onClick={openNew} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>새 공지</button>
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 800 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['#', '제목', '카테고리', '대상', '고정', '공개', '작성일', ''].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map(a => (
              <tr key={a.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                <td style={{ padding: '10px 8px', color: C.cyan }}>{a.id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{a.title}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>{a.category}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>{a.target_role}</td>
                <td style={{ padding: '10px 8px', color: a.is_pinned ? C.orange : C.textSec }}>{a.is_pinned ? 'Y' : '-'}</td>
                <td style={{ padding: '10px 8px', color: a.is_published ? C.green : C.red }}>{a.is_published ? '공개' : '비공개'}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>{a.created_at ? new Date(a.created_at).toLocaleDateString('ko-KR') : '-'}</td>
                <td style={{ padding: '10px 8px', display: 'flex', gap: 4 }}>
                  <button onClick={() => openEdit(a)} style={{ padding: '4px 8px', fontSize: 11, borderRadius: 5, border: 'none', cursor: 'pointer', background: 'rgba(0,229,255,0.15)', color: C.cyan }}>수정</button>
                  <button onClick={() => del(a.id)} style={{ padding: '4px 8px', fontSize: 11, borderRadius: 5, border: 'none', cursor: 'pointer', background: 'rgba(255,82,82,0.15)', color: C.red }}>삭제</button>
                </td>
              </tr>
            ))}
            {!items.length && <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>공지 없음</td></tr>}
          </tbody>
        </table>
      </div>

      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 480, border: `1px solid ${C.border}` }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 16 }}>{modal.mode === 'create' ? '새 공지' : '공지 수정'}</h3>
            <input value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} placeholder="제목" style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, marginBottom: 8 }} />
            <textarea value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} placeholder="내용" style={{ width: '100%', minHeight: 120, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical', marginBottom: 8 }} />
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })} style={{ flex: 1, padding: '8px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }}>
                {['general', 'notice', 'event', 'maintenance'].map(c => <option key={c} value={c}>{c}</option>)}
              </select>
              <select value={form.target_role} onChange={e => setForm({ ...form, target_role: e.target.value })} style={{ flex: 1, padding: '8px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }}>
                {['all', 'buyer', 'seller', 'admin'].map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div style={{ display: 'flex', gap: 16, marginBottom: 16 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, color: C.text }}>
                <input type="checkbox" checked={form.is_pinned} onChange={e => setForm({ ...form, is_pinned: e.target.checked })} /> 고정
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 13, color: C.text }}>
                <input type="checkbox" checked={form.is_published} onChange={e => setForm({ ...form, is_published: e.target.checked })} /> 공개
              </label>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={save} style={{ flex: 1, padding: '10px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer' }}>저장</button>
              <button onClick={() => setModal(null)} style={{ flex: 1, padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>취소</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
