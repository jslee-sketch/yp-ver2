import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };

export default function AdminSellersPage() {
  const [sellers, setSellers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<any>(null);

  const load = async () => {
    try {
      const r = await apiClient.get(API.SELLERS.LIST, { params: { limit: 500 } });
      const data = r.data;
      setSellers(Array.isArray(data) ? data : data?.items || []);
    } catch (e) { console.error('Sellers load:', e); }
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const filtered = sellers.filter(s => {
    const q = search.toLowerCase();
    return !q || [s.business_name, s.email, s.business_number, String(s.id)].some(v => v && String(v).toLowerCase().includes(q));
  });

  const approve = async (id: number) => { try { await apiClient.patch(API.SELLERS.VERIFY(id)); load(); } catch {} };
  const toggleBan = async (s: any) => {
    try {
      if (s.is_banned) await apiClient.post(API.ADMIN.USERS_UNBAN, { user_id: s.id, user_type: 'seller' });
      else await apiClient.post(API.ADMIN.USERS_BAN, { user_id: s.id, user_type: 'seller', reason: '관리자 정지' });
      load();
    } catch {}
  };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>판매자 관리</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="상호/이메일/사업자번호 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
      </div>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 850 }}>
            <thead style={stickyHead}>
              <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                {['ID', '상호명', '이메일', '사업자번호', '액추에이터', '레벨', '총판매액', '상태', ''].map(h => (
                  <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(s => (
                <tr key={s.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={{ padding: '10px 8px', color: '#4ade80', cursor: 'pointer', textDecoration: 'underline' }} onClick={() => setModal(s)}>S-{s.id}</td>
                  <td style={{ padding: '10px 8px', color: C.text, cursor: 'pointer' }} onClick={() => setModal(s)}>{s.business_name || '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{s.email}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{s.business_number || '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.cyan }}>{s.actuator_id ? `ACT-${String(s.actuator_id).padStart(5, '0')}` : '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.orange }}>{s.level ?? '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.orange }}>{(s.total_sales || 0).toLocaleString()}원</td>
                  <td style={{ padding: '10px 8px' }}>
                    {!s.verified_at ? <span style={{ color: C.orange, fontWeight: 600 }}>미승인</span> : s.is_banned ? <span style={{ color: C.red, fontWeight: 600 }}>정지</span> : <span style={{ color: C.green, fontWeight: 600 }}>활성</span>}
                  </td>
                  <td style={{ padding: '10px 8px', display: 'flex', gap: 4 }}>
                    {!s.verified_at && <button onClick={e => { e.stopPropagation(); approve(s.id); }} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,229,255,0.15)', color: C.cyan }}>승인</button>}
                    <button onClick={e => { e.stopPropagation(); toggleBan(s); }} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: s.is_banned ? 'rgba(0,230,118,0.15)' : 'rgba(255,82,82,0.15)', color: s.is_banned ? C.green : C.red }}>{s.is_banned ? '해제' : '정지'}</button>
                  </td>
                </tr>
              ))}
              {!filtered.length && <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>판매자 없음</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{filtered.length}명</div>

      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 400, maxWidth: 520, border: `1px solid ${C.border}`, maxHeight: '80vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 16 }}>판매자 상세 S-{modal.id}</h3>
            <div style={{ display: 'inline-block', padding: '4px 12px', borderRadius: 12, fontSize: 12, fontWeight: 700, marginBottom: 12, background: !modal.verified_at ? 'rgba(255,145,0,0.15)' : modal.is_banned ? 'rgba(255,82,82,0.15)' : 'rgba(0,230,118,0.15)', color: !modal.verified_at ? C.orange : modal.is_banned ? C.red : C.green }}>
              {!modal.verified_at ? '미승인' : modal.is_banned ? '정지' : '활성'}
            </div>
            {Object.entries({ 상호명: modal.business_name, 이메일: modal.email, 사업자번호: modal.business_number, 닉네임: modal.nickname, 레벨: modal.level, 대표자: modal.representative_name, 전화: modal.phone, 주소: modal.address, 포인트: modal.points != null ? `${Number(modal.points).toLocaleString()}P` : '-', 총판매액: modal.total_sales != null ? `${Number(modal.total_sales).toLocaleString()}원` : '-', 액추에이터: modal.actuator_id ? `ACT-${String(modal.actuator_id).padStart(5,'0')}` : '-', 가입일: modal.created_at ? new Date(modal.created_at).toLocaleDateString('ko-KR') : '-', 승인일: modal.verified_at ? new Date(modal.verified_at).toLocaleDateString('ko-KR') : '미승인' }).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${C.border}`, fontSize: 13 }}>
                <span style={{ color: C.textSec }}>{k}</span><span style={{ color: C.text }}>{String(v ?? '-')}</span>
              </div>
            ))}
            {modal.business_license_image && <div style={{ marginTop: 12 }}><div style={{ fontSize: 12, color: C.textSec, marginBottom: 4 }}>사업자등록증</div><img src={modal.business_license_image} alt="" style={{ maxWidth: '100%', borderRadius: 8 }} /></div>}

            {/* 액션 버튼 */}
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              {!modal.verified_at && (
                <button onClick={() => { approve(modal.id); setModal(null); }} style={{ flex: 1, padding: '10px', borderRadius: 8, border: 'none', cursor: 'pointer', background: C.cyan, color: '#000', fontWeight: 700, fontSize: 14 }}>판매자 승인</button>
              )}
              <button onClick={() => { toggleBan(modal); setModal(null); }} style={{ flex: 1, padding: '10px', borderRadius: 8, border: 'none', cursor: 'pointer', background: modal.is_banned ? 'rgba(0,230,118,0.2)' : 'rgba(255,82,82,0.2)', color: modal.is_banned ? C.green : C.red, fontWeight: 700, fontSize: 14 }}>{modal.is_banned ? '정지 해제' : '계정 정지'}</button>
            </div>
            <div style={{ marginTop: 4, fontSize: 11, color: C.textSec, textAlign: 'center' }}>
              {!modal.verified_at ? '미승인 판매자입니다. 정보를 확인 후 승인해주세요.' : modal.is_banned ? '정지된 계정입니다.' : '활성 판매자입니다.'}
            </div>

            <button onClick={() => setModal(null)} style={{ marginTop: 12, width: '100%', padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>닫기</button>
          </div>
        </div>
      )}
    </div>
  );
}
