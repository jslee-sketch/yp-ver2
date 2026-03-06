import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

export default function AdminBuyersPage() {
  const [buyers, setBuyers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<any>(null);

  const load = async () => {
    try { const r = await apiClient.get(API.BUYERS.LIST); setBuyers(Array.isArray(r.data) ? r.data : []); } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const filtered = buyers.filter(b => {
    const s = search.toLowerCase();
    return !s || [b.email, b.nickname, b.phone, String(b.id)].some(v => v && String(v).toLowerCase().includes(s));
  });

  const toggleBan = async (buyer: any) => {
    try {
      if (buyer.is_banned) await apiClient.post(API.ADMIN.USERS_UNBAN, { user_id: buyer.id, user_type: 'buyer' });
      else await apiClient.post(API.ADMIN.USERS_BAN, { user_id: buyer.id, user_type: 'buyer', reason: '관리자 정지' });
      load();
    } catch {}
  };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>구매자 관리</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="ID/닉네임/이메일/전화 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['ID', '닉네임', '이메일', '전화', '포인트', '상태', '가입일', ''].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(b => (
              <tr key={b.id} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer' }} onClick={() => setModal(b)}>
                <td style={{ padding: '10px 8px', color: C.cyan }}>B-{b.id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{b.nickname || '-'}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{b.email}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>{b.phone || '-'}</td>
                <td style={{ padding: '10px 8px', color: C.green }}>{(b.points || 0).toLocaleString()}</td>
                <td style={{ padding: '10px 8px' }}><span style={{ color: b.is_banned ? C.red : C.green, fontWeight: 600 }}>{b.is_banned ? '정지' : '활성'}</span></td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>{b.created_at ? new Date(b.created_at).toLocaleDateString('ko-KR') : '-'}</td>
                <td style={{ padding: '10px 8px' }}>
                  <button onClick={e => { e.stopPropagation(); toggleBan(b); }} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: b.is_banned ? 'rgba(0,230,118,0.15)' : 'rgba(255,82,82,0.15)', color: b.is_banned ? C.green : C.red }}>
                    {b.is_banned ? '해제' : '정지'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{filtered.length}명</div>

      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 400, maxWidth: 500, border: `1px solid ${C.border}` }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 16 }}>구매자 상세 B-{modal.id}</h3>
            {Object.entries({ 닉네임: modal.nickname, 이메일: modal.email, 전화: modal.phone, 포인트: modal.points, 레벨: modal.level, 신뢰등급: modal.trust_tier, 가입일: modal.created_at }).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${C.border}`, fontSize: 13 }}>
                <span style={{ color: C.textSec }}>{k}</span><span style={{ color: C.text }}>{String(v ?? '-')}</span>
              </div>
            ))}
            <button onClick={() => setModal(null)} style={{ marginTop: 16, width: '100%', padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>닫기</button>
          </div>
        </div>
      )}
    </div>
  );
}
