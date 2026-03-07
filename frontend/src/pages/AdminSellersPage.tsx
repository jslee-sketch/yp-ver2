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
  const [actionMsg, setActionMsg] = useState('');
  const [acting, setActing] = useState(false);

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

  const approve = async (id: number) => {
    setActing(true); setActionMsg('');
    try {
      await apiClient.patch(API.SELLERS.VERIFY(id));
      setActionMsg('승인 완료');
      await load();
      // 모달 데이터 갱신
      const updated = sellers.find(s => s.id === id);
      if (updated) setModal({ ...updated });
      else {
        // load 후 sellers state가 아직 반영 안 됐을 수 있으므로 API에서 직접 조회
        try {
          const r = await apiClient.get(API.SELLERS.DETAIL(id));
          setModal(r.data);
        } catch { setModal(null); }
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '승인 실패';
      setActionMsg(`오류: ${typeof msg === 'string' ? msg : JSON.stringify(msg)}`);
    }
    setActing(false);
  };

  const toggleBan = async (s: any) => {
    setActing(true); setActionMsg('');
    try {
      if (s.is_banned) {
        await apiClient.post(API.ADMIN.USERS_UNBAN, { user_id: s.user_id || s.id, user_type: 'seller' });
        setActionMsg('정지 해제 완료');
      } else {
        await apiClient.post(API.ADMIN.USERS_BAN, { user_id: s.user_id || s.id, user_type: 'seller', reason: '관리자 정지' });
        setActionMsg('계정 정지 완료');
      }
      await load();
      try {
        const r = await apiClient.get(API.SELLERS.DETAIL(s.id));
        setModal(r.data);
      } catch { setModal(null); }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '처리 실패';
      setActionMsg(`오류: ${typeof msg === 'string' ? msg : JSON.stringify(msg)}`);
    }
    setActing(false);
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
                <tr key={s.id} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer' }}
                  onClick={() => { setModal(s); setActionMsg(''); }}>
                  <td style={{ padding: '10px 8px', color: '#4ade80', textDecoration: 'underline' }}>S-{s.id}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{s.business_name || '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.text }}>{s.email}</td>
                  <td style={{ padding: '10px 8px', color: C.textSec }}>{s.business_number || '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.cyan }}>{s.actuator_id ? `ACT-${String(s.actuator_id).padStart(5, '0')}` : '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.orange }}>{s.level ?? '-'}</td>
                  <td style={{ padding: '10px 8px', color: C.orange }}>{(s.total_sales || 0).toLocaleString()}원</td>
                  <td style={{ padding: '10px 8px' }}>
                    {!s.verified_at ? <span style={{ color: C.orange, fontWeight: 600 }}>미승인</span> : s.is_banned ? <span style={{ color: C.red, fontWeight: 600 }}>정지</span> : <span style={{ color: C.green, fontWeight: 600 }}>활성</span>}
                  </td>
                  <td style={{ padding: '10px 8px' }}>
                    {!s.verified_at && <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: C.orange, marginRight: 4 }} title="승인 필요" />}
                  </td>
                </tr>
              ))}
              {!filtered.length && <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>판매자 없음</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>
        {filtered.length}명 (미승인: {filtered.filter(s => !s.verified_at).length}명)
      </div>

      {/* ─── 상세 모달 ─── */}
      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 420, maxWidth: 540, border: `1px solid ${C.border}`, maxHeight: '85vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, color: C.text, margin: 0 }}>판매자 상세 S-{modal.id}</h3>
              <div style={{ display: 'inline-block', padding: '4px 12px', borderRadius: 12, fontSize: 12, fontWeight: 700, background: !modal.verified_at ? 'rgba(255,145,0,0.15)' : modal.is_banned ? 'rgba(255,82,82,0.15)' : 'rgba(0,230,118,0.15)', color: !modal.verified_at ? C.orange : modal.is_banned ? C.red : C.green }}>
                {!modal.verified_at ? '미승인' : modal.is_banned ? '정지' : '활성'}
              </div>
            </div>

            {Object.entries({
              상호명: modal.business_name,
              이메일: modal.email,
              사업자번호: modal.business_number,
              닉네임: modal.nickname,
              레벨: modal.level,
              대표자: modal.representative_name,
              전화: modal.phone,
              주소: modal.address,
              포인트: modal.points != null ? `${Number(modal.points).toLocaleString()}P` : '-',
              총판매액: modal.total_sales != null ? `${Number(modal.total_sales).toLocaleString()}원` : '-',
              액추에이터: modal.actuator_id ? `ACT-${String(modal.actuator_id).padStart(5, '0')}` : '-',
              가입일: modal.created_at ? new Date(modal.created_at).toLocaleDateString('ko-KR') : '-',
              승인일: modal.verified_at ? new Date(modal.verified_at).toLocaleDateString('ko-KR') : '미승인',
            }).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${C.border}`, fontSize: 13 }}>
                <span style={{ color: C.textSec }}>{k}</span>
                <span style={{ color: k === '승인일' && v === '미승인' ? C.orange : C.text, fontWeight: k === '승인일' && v === '미승인' ? 600 : 400 }}>{String(v ?? '-')}</span>
              </div>
            ))}

            {modal.business_license_image && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 12, color: C.textSec, marginBottom: 4 }}>사업자등록증</div>
                <img src={modal.business_license_image} alt="" style={{ maxWidth: '100%', borderRadius: 8 }} />
              </div>
            )}

            {/* 결과 메시지 */}
            {actionMsg && (
              <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: actionMsg.startsWith('오류') ? 'rgba(255,82,82,0.1)' : 'rgba(0,230,118,0.1)', color: actionMsg.startsWith('오류') ? C.red : C.green }}>
                {actionMsg}
              </div>
            )}

            {/* 액션 버튼 */}
            <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
              {!modal.verified_at && (
                <button disabled={acting} onClick={() => approve(modal.id)}
                  style={{ flex: 1, padding: '10px', borderRadius: 8, border: 'none', cursor: acting ? 'wait' : 'pointer', background: C.cyan, color: '#000', fontWeight: 700, fontSize: 14, opacity: acting ? 0.5 : 1 }}>
                  {acting ? '처리 중...' : '판매자 승인'}
                </button>
              )}
              <button disabled={acting} onClick={() => toggleBan(modal)}
                style={{ flex: 1, padding: '10px', borderRadius: 8, border: 'none', cursor: acting ? 'wait' : 'pointer', background: modal.is_banned ? 'rgba(0,230,118,0.2)' : 'rgba(255,82,82,0.2)', color: modal.is_banned ? C.green : C.red, fontWeight: 700, fontSize: 14, opacity: acting ? 0.5 : 1 }}>
                {acting ? '처리 중...' : modal.is_banned ? '정지 해제' : '계정 정지'}
              </button>
            </div>

            {!modal.verified_at && !actionMsg && (
              <div style={{ marginTop: 6, fontSize: 11, color: C.orange, textAlign: 'center' }}>
                미승인 판매자입니다. 정보를 확인 후 승인해주세요.
              </div>
            )}

            <button onClick={() => setModal(null)} style={{ marginTop: 12, width: '100%', padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>닫기</button>
          </div>
        </div>
      )}
    </div>
  );
}
