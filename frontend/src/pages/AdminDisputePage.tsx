import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };

export default function AdminDisputePage() {
  const [items, setItems] = useState<any[]>([]);
  const [closed, setClosed] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState<'open' | 'closed'>('open');
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<any>(null);
  const [resolution, setResolution] = useState('');
  const [refundAction, setRefundAction] = useState('no_refund');

  const load = async () => {
    try {
      const [openR, closedR] = await Promise.allSettled([
        apiClient.get(API.ADMIN.RESERVATIONS, { params: { is_disputed: true, limit: 200 } }),
        apiClient.get(API.ADMIN.RESERVATIONS, { params: { is_disputed: false, limit: 200 } }),
      ]);
      setItems(openR.status === 'fulfilled' ? (openR.value.data?.items || []) : []);
      // closed disputes = those with dispute_closed_at set
      const allNonDisputed = closedR.status === 'fulfilled' ? (closedR.value.data?.items || []) : [];
      setClosed(allNonDisputed.filter((r: any) => r.dispute_closed_at));
    } catch {}
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const closeDispute = async () => {
    if (!modal) return;
    try {
      await apiClient.post(API.RESERVATIONS_V36.DISPUTE_CLOSE(modal.id), {
        resolution,
        refund_action: refundAction,
      });
      setModal(null);
      setResolution('');
      setRefundAction('no_refund');
      load();
    } catch {}
  };

  const list = tab === 'open' ? items : closed;
  const filtered = list.filter(r => {
    const q = search.toLowerCase();
    return !q || [String(r.id), String(r.deal_id), r.buyer_name, r.seller_name, r.dispute_reason].some(v => v && String(v).toLowerCase().includes(q));
  });

  const formatDate = (d: string | null) => d ? new Date(d).toLocaleString('ko-KR') : '-';

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>분쟁 관리</h1>

      {/* 탭 */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        {(['open', 'closed'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '6px 16px', borderRadius: 6, border: 'none', fontSize: 13, cursor: 'pointer',
            background: tab === t ? (t === 'open' ? C.red : C.green) : 'transparent',
            color: tab === t ? '#fff' : C.textSec, fontWeight: tab === t ? 700 : 400,
          }}>
            {t === 'open' ? `진행 중 (${items.length})` : `종료됨 (${closed.length})`}
          </button>
        ))}
      </div>

      {/* 검색 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="R-#/D-#/구매자/판매자/사유 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
      </div>

      {/* 테이블 */}
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 900 }}>
          <thead style={stickyHead}>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['R-#', 'D-#', '구매자', '판매자', '금액', '사유', tab === 'open' ? '접수일' : '종료일', '상태', ''].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer' }} onClick={() => { setModal(r); setResolution(r.dispute_resolution || ''); }}>
                <td style={{ padding: '10px 8px', color: C.red, fontWeight: 600 }}>R-{r.id}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>D-{r.deal_id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{r.buyer_name || `B-${r.buyer_id}`}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{r.seller_name || `S-${r.seller_id}`}</td>
                <td style={{ padding: '10px 8px', color: C.orange }}>{(r.amount || 0).toLocaleString()}</td>
                <td style={{ padding: '10px 8px', color: C.text, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.dispute_reason || '-'}</td>
                <td style={{ padding: '10px 8px', color: C.textSec, fontSize: 12 }}>{formatDate(tab === 'open' ? r.dispute_opened_at : r.dispute_closed_at)}</td>
                <td style={{ padding: '10px 8px' }}>
                  <span style={{ color: r.is_disputed ? C.red : C.green, fontWeight: 600 }}>{r.is_disputed ? '분쟁 중' : '종료'}</span>
                </td>
                <td style={{ padding: '10px 8px' }}>
                  {r.is_disputed && (
                    <button onClick={e => { e.stopPropagation(); setModal(r); setResolution(''); }} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,230,118,0.15)', color: C.green }}>처리</button>
                  )}
                </td>
              </tr>
            ))}
            {!filtered.length && <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>{tab === 'open' ? '진행 중인 분쟁 없음' : '종료된 분쟁 없음'}</td></tr>}
          </tbody>
        </table>
        </div>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{filtered.length}건</div>

      {/* 상세/처리 모달 */}
      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 500, maxWidth: 600, border: `1px solid ${C.border}`, maxHeight: '85vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: C.red, marginBottom: 16 }}>
              분쟁 상세 R-{modal.id} {modal.is_disputed ? '(진행 중)' : '(종료됨)'}
            </h3>

            {/* 정보 */}
            {Object.entries({
              딜: `D-${modal.deal_id}`,
              오퍼: `O-${modal.offer_id || '-'}`,
              구매자: modal.buyer_name || `B-${modal.buyer_id}`,
              판매자: modal.seller_name || `S-${modal.seller_id}`,
              금액: `${(modal.amount || 0).toLocaleString()}원`,
              예약상태: modal.status,
              '분쟁 사유': modal.dispute_reason || '-',
              '접수일': formatDate(modal.dispute_opened_at),
              '종료일': formatDate(modal.dispute_closed_at),
            }).map(([k, v]) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${C.border}`, fontSize: 13 }}>
                <span style={{ color: C.textSec }}>{k}</span>
                <span style={{ color: C.text, maxWidth: '60%', textAlign: 'right', wordBreak: 'break-all' }}>{String(v)}</span>
              </div>
            ))}

            {/* 종료된 경우 resolution 표시 */}
            {modal.dispute_resolution && (
              <div style={{ marginTop: 12, padding: 12, background: 'rgba(0,230,118,0.06)', borderRadius: 8, border: `1px solid rgba(0,230,118,0.15)` }}>
                <div style={{ fontSize: 12, color: C.green, fontWeight: 600, marginBottom: 4 }}>처리 결과</div>
                <div style={{ fontSize: 13, color: C.text }}>{modal.dispute_resolution}</div>
              </div>
            )}

            {/* 진행 중인 경우: 처리 폼 */}
            {modal.is_disputed && (
              <div style={{ marginTop: 16, padding: 16, background: 'rgba(255,82,82,0.04)', borderRadius: 8, border: `1px solid rgba(255,82,82,0.1)` }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 8 }}>분쟁 처리</div>
                <textarea value={resolution} onChange={e => setResolution(e.target.value)} placeholder="처리 결과를 입력하세요" style={{ width: '100%', minHeight: 80, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical', marginBottom: 8 }} />
                <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                  <select value={refundAction} onChange={e => setRefundAction(e.target.value)} style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }}>
                    <option value="no_refund">환불 없음</option>
                    <option value="full_refund">전액 환불</option>
                    <option value="partial_refund">부분 환불</option>
                  </select>
                </div>
                <button onClick={closeDispute} disabled={!resolution} style={{ width: '100%', padding: '10px', borderRadius: 8, border: 'none', background: resolution ? C.green : 'rgba(0,230,118,0.2)', color: resolution ? '#000' : C.textSec, fontWeight: 600, cursor: resolution ? 'pointer' : 'default', fontSize: 13 }}>
                  분쟁 종료 처리
                </button>
              </div>
            )}

            <button onClick={() => setModal(null)} style={{ marginTop: 12, width: '100%', padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>닫기</button>
          </div>
        </div>
      )}
    </div>
  );
}
