import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminNotificationsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [targetRole, setTargetRole] = useState('all');
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState('');

  const load = async () => {
    try { const r = await apiClient.get(API.ADMIN.NOTIFICATIONS_ALL, { params: { limit: 100 } }); setItems(r.data?.items || []); } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const send = async () => {
    if (!title || !message) return;
    setSending(true); setResult('');
    try {
      const r = await apiClient.post(API.ADMIN.NOTIFICATIONS_BROADCAST, { title, message, target_role: targetRole });
      setResult(`${r.data?.sent || 0}명에게 발송 완료`);
      setTitle(''); setMessage('');
      load();
    } catch {
      setResult('발송 실패');
    }
    setSending(false);
  };

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>알림 관리</h1>

      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16, marginBottom: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>공지 알림 발송</h3>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="제목" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }} />
          <select value={targetRole} onChange={e => setTargetRole(e.target.value)} style={{ padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }}>
            <option value="all">전체</option>
            <option value="buyer">구매자</option>
            <option value="seller">판매자</option>
            <option value="admin">관리자</option>
          </select>
        </div>
        <textarea value={message} onChange={e => setMessage(e.target.value)} placeholder="내용" style={{ width: '100%', minHeight: 60, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical', marginBottom: 8 }} />
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button onClick={send} disabled={sending || !title || !message} style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>{sending ? '발송 중...' : '발송'}</button>
          {result && <span style={{ fontSize: 13, color: result.includes('실패') ? C.red : C.green }}>{result}</span>}
        </div>
      </div>

      <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>전체 알림 목록</h3>
      {loading ? <div style={{ padding: 20, color: C.textSec }}>로딩 중...</div> : (
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['ID', '사용자', '유형', '제목', '읽음', '시간'].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map(n => (
                <tr key={n.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={{ padding: '10px 8px', color: C.cyan }}>{n.id}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>#{n.user_id}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{n.type}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{n.title}</td>
                  <td style={{ padding: '10px 8px' }}><span style={{ color: n.is_read ? C.green : C.textSec }}>{n.is_read ? 'Y' : 'N'}</span></td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{n.created_at ? new Date(n.created_at).toLocaleString('ko-KR') : '-'}</td>
                </tr>
              ))}
              {!items.length && <tr><td colSpan={6} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>알림 없음</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
