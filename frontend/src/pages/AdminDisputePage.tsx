import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };
const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.3)' };

export default function AdminDisputePage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<any[]>([]);
  const [closed, setClosed] = useState<any[]>([]);
  const [v3Disputes, setV3Disputes] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [tab, setTab] = useState<'v3' | 'open' | 'closed' | 'post_failure'>('v3');
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState<any>(null);
  const [resolution, setResolution] = useState('');
  const [refundAction, setRefundAction] = useState('no_refund');

  // 결렬 후속 modals
  const [forceCloseModal, setForceCloseModal] = useState<any>(null);
  const [forceCloseMode, setForceCloseMode] = useState<'ai' | 'manual'>('ai');
  const [fcCompType, setFcCompType] = useState('no_compensation');
  const [fcCompAmount, setFcCompAmount] = useState('');
  const [fcResolution, setFcResolution] = useState('');
  const [fcReason, setFcReason] = useState('');

  const [externalModal, setExternalModal] = useState<any>(null);
  const [extDescription, setExtDescription] = useState('');
  const [extDocUrl, setExtDocUrl] = useState('');
  const [extCompType, setExtCompType] = useState('no_compensation');
  const [extCompAmount, setExtCompAmount] = useState('');
  const [extResolution, setExtResolution] = useState('');

  const load = async () => {
    try {
      const [openR, closedR, v3R] = await Promise.allSettled([
        apiClient.get(API.ADMIN.RESERVATIONS, { params: { is_disputed: true, limit: 200 } }),
        apiClient.get(API.ADMIN.RESERVATIONS, { params: { is_disputed: false, limit: 200 } }),
        apiClient.get('/v3_6/disputes'),
      ]);
      setItems(openR.status === 'fulfilled' ? (openR.value.data?.items || []) : []);
      const allNonDisputed = closedR.status === 'fulfilled' ? (closedR.value.data?.items || []) : [];
      setClosed(allNonDisputed.filter((r: any) => r.dispute_closed_at));
      setV3Disputes(v3R.status === 'fulfilled' ? (Array.isArray(v3R.value.data) ? v3R.value.data : []) : []);
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

  const failedDisputes = v3Disputes.filter(d => d.status === 'FAILED');
  const graceDisputes = failedDisputes.filter(d => d.post_failure_status === 'GRACE_PERIOD');
  const externalDisputes = failedDisputes.filter(d => d.post_failure_status === 'EXTERNAL_FILED');
  const otherFailedDisputes = failedDisputes.filter(d => d.post_failure_status && d.post_failure_status !== 'GRACE_PERIOD' && d.post_failure_status !== 'EXTERNAL_FILED');

  const getDaysRemaining = (deadline: string | null) => {
    if (!deadline) return null;
    const diff = (new Date(deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24);
    return Math.ceil(diff);
  };

  const graceUrgent = graceDisputes.filter(d => {
    const days = getDaysRemaining(d.grace_deadline);
    return days !== null && days <= 3;
  });

  const submitForceClose = async () => {
    if (!forceCloseModal) return;
    try {
      const body: any = { mode: forceCloseMode };
      if (forceCloseMode === 'manual') {
        body.compensation_type = fcCompType;
        body.compensation_amount = fcCompAmount ? Number(fcCompAmount) : 0;
        body.resolution = fcResolution;
        body.reason = fcReason;
      }
      await apiClient.post(`/v3_6/admin/disputes/${forceCloseModal.id}/force-close`, body);
      setForceCloseModal(null);
      resetForceCloseForm();
      load();
    } catch {}
  };

  const resetForceCloseForm = () => {
    setForceCloseMode('ai');
    setFcCompType('no_compensation');
    setFcCompAmount('');
    setFcResolution('');
    setFcReason('');
  };

  const submitExternalResult = async () => {
    if (!externalModal) return;
    try {
      await apiClient.post(`/v3_6/admin/disputes/${externalModal.id}/external-result`, {
        result_description: extDescription,
        document_url: extDocUrl,
        compensation_type: extCompType,
        compensation_amount: extCompAmount ? Number(extCompAmount) : 0,
        resolution: extResolution,
      });
      setExternalModal(null);
      resetExternalForm();
      load();
    } catch {}
  };

  const resetExternalForm = () => {
    setExtDescription('');
    setExtDocUrl('');
    setExtCompType('no_compensation');
    setExtCompAmount('');
    setExtResolution('');
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
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>중재 관리</h1>

      {/* 탭 */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
        <button onClick={() => setTab('v3')} style={{
          padding: '6px 16px', borderRadius: 6, border: 'none', fontSize: 13, cursor: 'pointer',
          background: tab === 'v3' ? C.cyan : 'transparent',
          color: tab === 'v3' ? '#000' : C.textSec, fontWeight: tab === 'v3' ? 700 : 400,
        }}>
          AI 중재 ({v3Disputes.length})
        </button>
        <button onClick={() => setTab('post_failure')} style={{
          padding: '6px 16px', borderRadius: 6, border: 'none', fontSize: 13, cursor: 'pointer',
          background: tab === 'post_failure' ? C.orange : 'transparent',
          color: tab === 'post_failure' ? '#000' : C.textSec, fontWeight: tab === 'post_failure' ? 700 : 400,
        }}>
          결렬 후속 ({failedDisputes.length})
        </button>
        {(['open', 'closed'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '6px 16px', borderRadius: 6, border: 'none', fontSize: 13, cursor: 'pointer',
            background: tab === t ? (t === 'open' ? C.red : C.green) : 'transparent',
            color: tab === t ? '#fff' : C.textSec, fontWeight: tab === t ? 700 : 400,
          }}>
            {t === 'open' ? `구 중재 (${items.length})` : `종료됨 (${closed.length})`}
          </button>
        ))}
      </div>

      {/* 검색 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="중재 ID/카테고리 검색" style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 13 }} />
      </div>

      {/* V3 AI 중재 분쟁 목록 */}
      {tab === 'v3' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
          {v3Disputes.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: C.textSec }}>AI 중재 없음</div>
          ) : v3Disputes
            .filter(d => {
              const q = search.toLowerCase();
              return !q || [String(d.id), d.category, d.title, d.status].some(v => v && String(v).toLowerCase().includes(q));
            })
            .map((d: any) => {
              const stMap: Record<string,{label:string;color:string}> = {
                ROUND1_RESPONSE: { label: '1차 반론 대기', color: C.orange },
                ROUND1_AI: { label: 'AI 분석', color: '#a78bfa' },
                ROUND1_REVIEW: { label: '1차 검토', color: C.cyan },
                ROUND2_RESPONSE: { label: '2차 반론 대기', color: '#fbbf24' },
                ROUND2_AI: { label: 'AI 2차', color: '#a78bfa' },
                ROUND2_REVIEW: { label: '2차 검토', color: '#f472b6' },
                ACCEPTED: { label: '합의', color: C.green },
                REJECTED: { label: '미합의', color: C.red },
                AUTO_CLOSED: { label: '자동종결', color: '#78909c' },
              };
              const st = stMap[d.status] || { label: d.status, color: '#888' };
              return (
                <div key={d.id} onClick={() => navigate(`/disputes/${d.id}`)} style={{
                  background: C.card, border: `1px solid ${C.border}`, borderLeft: `3px solid ${st.color}`,
                  borderRadius: 12, padding: '12px 14px', cursor: 'pointer',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>중재 #{d.id}: {d.title || d.category}</div>
                      <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                        Round {d.current_round} · 신청자 #{d.initiator_id} → 상대방 #{d.respondent_id}
                        {d.created_at && ` · ${d.created_at.split('T')[0]}`}
                      </div>
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 6, background: `${st.color}22`, color: st.color }}>{st.label}</span>
                  </div>
                </div>
              );
            })
          }
        </div>
      )}

      {/* 결렬 후속 탭 */}
      {tab === 'post_failure' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 16 }}>
          {failedDisputes.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 0', color: C.textSec }}>결렬 후속 건 없음</div>
          ) : (
            <>
              {/* 유예 만료 임박 섹션 */}
              {graceUrgent.length > 0 && (
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: C.red, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                    유예 만료 임박 ({graceUrgent.length})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {graceUrgent.map((d: any) => {
                      const daysLeft = getDaysRemaining(d.grace_deadline);
                      return (
                        <div key={d.id} style={{
                          background: C.card, border: `1px solid ${C.border}`, borderLeft: `3px solid ${C.red}`,
                          borderRadius: 12, padding: '12px 14px',
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>중재 #{d.id}</div>
                              <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                                주문: {d.order_number || '-'} · 잔여 {daysLeft}일
                              </div>
                            </div>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button onClick={() => { setForceCloseModal(d); setForceCloseMode('ai'); }} style={{ padding: '4px 10px', fontSize: 11, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(167,139,250,0.15)', color: '#a78bfa', fontWeight: 600 }}>AI기준 자동종결</button>
                              <button onClick={() => { setForceCloseModal(d); setForceCloseMode('manual'); }} style={{ padding: '4px 10px', fontSize: 11, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,229,255,0.12)', color: C.cyan, fontWeight: 600 }}>수동 판정</button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* GRACE_PERIOD 전체 */}
              {graceDisputes.length > 0 && (
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: C.orange, marginBottom: 8 }}>
                    유예 기간 ({graceDisputes.length})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {graceDisputes.map((d: any) => {
                      const daysLeft = getDaysRemaining(d.grace_deadline);
                      return (
                        <div key={d.id} style={{
                          background: C.card, border: `1px solid ${C.border}`, borderLeft: `3px solid ${C.orange}`,
                          borderRadius: 12, padding: '12px 14px',
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>중재 #{d.id}</div>
                              <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                                주문: {d.order_number || '-'} · 잔여 {daysLeft !== null ? `${daysLeft}일` : '-'}
                                {d.created_at && ` · ${d.created_at.split('T')[0]}`}
                              </div>
                            </div>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button onClick={() => { setForceCloseModal(d); setForceCloseMode('ai'); }} style={{ padding: '4px 10px', fontSize: 11, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(167,139,250,0.15)', color: '#a78bfa', fontWeight: 600 }}>AI기준 자동종결</button>
                              <button onClick={() => { setForceCloseModal(d); setForceCloseMode('manual'); }} style={{ padding: '4px 10px', fontSize: 11, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,229,255,0.12)', color: C.cyan, fontWeight: 600 }}>수동 판정</button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 외부기관 결과 대기 섹션 */}
              {externalDisputes.length > 0 && (
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#a78bfa', marginBottom: 8 }}>
                    외부기관 결과 대기 ({externalDisputes.length})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {externalDisputes.map((d: any) => {
                      const daysLeft = getDaysRemaining(d.grace_deadline);
                      return (
                        <div key={d.id} style={{
                          background: C.card, border: `1px solid ${C.border}`, borderLeft: '3px solid #a78bfa',
                          borderRadius: 12, padding: '12px 14px',
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>중재 #{d.id}</div>
                              <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                                주문: {d.order_number || '-'} · 잔여 {daysLeft !== null ? `${daysLeft}일` : '-'}
                                {d.created_at && ` · ${d.created_at.split('T')[0]}`}
                              </div>
                            </div>
                            <div style={{ display: 'flex', gap: 6 }}>
                              <button onClick={() => { setExternalModal(d); resetExternalForm(); }} style={{ padding: '4px 10px', fontSize: 11, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(244,114,182,0.15)', color: '#f472b6', fontWeight: 600 }}>외부 결과 입력</button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* 기타 결렬 후속 */}
              {otherFailedDisputes.length > 0 && (
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: C.textSec, marginBottom: 8 }}>
                    기타 ({otherFailedDisputes.length})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {otherFailedDisputes.map((d: any) => (
                      <div key={d.id} style={{
                        background: C.card, border: `1px solid ${C.border}`, borderLeft: '3px solid #78909c',
                        borderRadius: 12, padding: '12px 14px',
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <div>
                            <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>중재 #{d.id}</div>
                            <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                              주문: {d.order_number || '-'} · 상태: {d.post_failure_status}
                              {d.created_at && ` · ${d.created_at.split('T')[0]}`}
                            </div>
                          </div>
                          <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 10px', borderRadius: 6, background: 'rgba(120,144,156,0.15)', color: '#78909c' }}>{d.post_failure_status}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* 구 분쟁 테이블 */}
      {tab !== 'v3' && tab !== 'post_failure' && <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ maxHeight: '70vh', overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, minWidth: 900 }}>
          <thead style={stickyHead}>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {['주문번호', 'D-#', '구매자', '판매자', '금액', '사유', tab === 'open' ? '접수일' : '종료일', '상태', ''].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 8px', color: C.textSec, fontWeight: 600, whiteSpace: 'nowrap' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(r => (
              <tr key={r.id} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer' }} onClick={() => { setModal(r); setResolution(r.dispute_resolution || ''); }}>
                <td style={{ padding: '10px 8px', color: C.red, fontWeight: 600 }}>{r.order_number || `R-${r.id}`}</td>
                <td style={{ padding: '10px 8px', color: C.textSec }}>D-{r.deal_id}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{r.buyer_name || `B-${r.buyer_id}`}</td>
                <td style={{ padding: '10px 8px', color: C.text }}>{r.seller_name || `S-${r.seller_id}`}</td>
                <td style={{ padding: '10px 8px', color: C.orange }}>{(r.amount || 0).toLocaleString()}</td>
                <td style={{ padding: '10px 8px', color: C.text, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.dispute_reason || '-'}</td>
                <td style={{ padding: '10px 8px', color: C.textSec, fontSize: 12 }}>{formatDate(tab === 'open' ? r.dispute_opened_at : r.dispute_closed_at)}</td>
                <td style={{ padding: '10px 8px' }}>
                  <span style={{ color: r.is_disputed ? C.red : C.green, fontWeight: 600 }}>{r.is_disputed ? '중재중' : '종료'}</span>
                </td>
                <td style={{ padding: '10px 8px' }}>
                  {r.is_disputed && (
                    <button onClick={e => { e.stopPropagation(); setModal(r); setResolution(''); }} style={{ padding: '4px 10px', fontSize: 12, borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(0,230,118,0.15)', color: C.green }}>처리</button>
                  )}
                </td>
              </tr>
            ))}
            {!filtered.length && <tr><td colSpan={9} style={{ padding: 24, textAlign: 'center', color: C.textSec }}>{tab === 'open' ? '진행 중인 중재 없음' : '종료된 중재 없음'}</td></tr>}
          </tbody>
        </table>
        </div>
      </div>}
      {tab !== 'v3' && tab !== 'post_failure' && <div style={{ marginTop: 8, fontSize: 12, color: C.textSec }}>{filtered.length}건</div>}

      {/* 상세/처리 모달 */}
      {modal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setModal(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 500, maxWidth: 600, border: `1px solid ${C.border}`, maxHeight: '85vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: C.red, marginBottom: 16 }}>
              중재 상세 {modal.order_number || `R-${modal.id}`} {modal.is_disputed ? '(진행 중)' : '(종료됨)'}
            </h3>

            {/* 정보 */}
            {Object.entries({
              딜: `D-${modal.deal_id}`,
              오퍼: `O-${modal.offer_id || '-'}`,
              구매자: modal.buyer_name || `B-${modal.buyer_id}`,
              판매자: modal.seller_name || `S-${modal.seller_id}`,
              금액: `${(modal.amount || 0).toLocaleString()}원`,
              예약상태: modal.status,
              '중재 사유': modal.dispute_reason || '-',
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
                <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 8 }}>중재 처리</div>
                <textarea value={resolution} onChange={e => setResolution(e.target.value)} placeholder="처리 결과를 입력하세요" style={{ width: '100%', minHeight: 80, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical', marginBottom: 8 }} />
                <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                  <select value={refundAction} onChange={e => setRefundAction(e.target.value)} style={{ flex: 1, padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }}>
                    <option value="no_refund">환불 없음</option>
                    <option value="full_refund">전액 환불</option>
                    <option value="partial_refund">부분 환불</option>
                  </select>
                </div>
                <button onClick={closeDispute} disabled={!resolution} style={{ width: '100%', padding: '10px', borderRadius: 8, border: 'none', background: resolution ? C.green : 'rgba(0,230,118,0.2)', color: resolution ? '#000' : C.textSec, fontWeight: 600, cursor: resolution ? 'pointer' : 'default', fontSize: 13 }}>
                  중재 종료 처리
                </button>
              </div>
            )}

            <button onClick={() => setModal(null)} style={{ marginTop: 12, width: '100%', padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>닫기</button>
          </div>
        </div>
      )}

      {/* Force Close 모달 (AI기준 자동종결 / 수동 판정) */}
      {forceCloseModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => { setForceCloseModal(null); resetForceCloseForm(); }}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 500, maxWidth: 600, border: `1px solid ${C.border}`, maxHeight: '85vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: forceCloseMode === 'ai' ? '#a78bfa' : C.cyan, marginBottom: 16 }}>
              {forceCloseMode === 'ai' ? 'AI기준 자동종결' : '수동 판정'} — 중재 #{forceCloseModal.id}
            </h3>

            {/* 모드 전환 */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
              {(['ai', 'manual'] as const).map(m => (
                <button key={m} onClick={() => setForceCloseMode(m)} style={{
                  padding: '5px 14px', borderRadius: 6, border: 'none', fontSize: 12, cursor: 'pointer',
                  background: forceCloseMode === m ? (m === 'ai' ? '#a78bfa' : C.cyan) : 'transparent',
                  color: forceCloseMode === m ? '#000' : C.textSec, fontWeight: forceCloseMode === m ? 700 : 400,
                }}>
                  {m === 'ai' ? 'AI 기준' : '수동'}
                </button>
              ))}
            </div>

            {forceCloseMode === 'ai' ? (
              <div>
                <div style={{ padding: 16, background: 'rgba(167,139,250,0.06)', borderRadius: 8, border: '1px solid rgba(167,139,250,0.15)', marginBottom: 16 }}>
                  <div style={{ fontSize: 12, color: '#a78bfa', fontWeight: 600, marginBottom: 8 }}>AI 제안</div>
                  <div style={{ fontSize: 13, color: C.text }}>
                    보상 금액: {forceCloseModal.ai_proposal_amount != null ? `${Number(forceCloseModal.ai_proposal_amount).toLocaleString()}원` : '미산정'}
                  </div>
                  {forceCloseModal.ai_proposal_summary && (
                    <div style={{ fontSize: 12, color: C.textSec, marginTop: 6 }}>{forceCloseModal.ai_proposal_summary}</div>
                  )}
                </div>
                <button onClick={submitForceClose} style={{ width: '100%', padding: '10px', borderRadius: 8, border: 'none', background: '#a78bfa', color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>
                  AI 기준으로 자동종결
                </button>
              </div>
            ) : (
              <div>
                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 12, color: C.textSec, marginBottom: 4, display: 'block' }}>보상 유형</label>
                  <select value={fcCompType} onChange={e => setFcCompType(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }}>
                    <option value="no_compensation">보상 없음</option>
                    <option value="full_refund">전액 환불</option>
                    <option value="partial_refund">부분 환불</option>
                    <option value="point_credit">포인트 보상</option>
                  </select>
                </div>
                {fcCompType !== 'no_compensation' && (
                  <div style={{ marginBottom: 12 }}>
                    <label style={{ fontSize: 12, color: C.textSec, marginBottom: 4, display: 'block' }}>보상 금액</label>
                    <input type="number" value={fcCompAmount} onChange={e => setFcCompAmount(e.target.value)} placeholder="금액 입력" style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }} />
                  </div>
                )}
                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 12, color: C.textSec, marginBottom: 4, display: 'block' }}>처리 결과</label>
                  <select value={fcResolution} onChange={e => setFcResolution(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }}>
                    <option value="">선택하세요</option>
                    <option value="buyer_win">구매자 승</option>
                    <option value="seller_win">판매자 승</option>
                    <option value="compromise">절충</option>
                    <option value="dismissed">기각</option>
                  </select>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <label style={{ fontSize: 12, color: C.textSec, marginBottom: 4, display: 'block' }}>판정 사유 (필수)</label>
                  <textarea value={fcReason} onChange={e => setFcReason(e.target.value)} placeholder="판정 사유를 입력하세요" style={{ width: '100%', minHeight: 80, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical' }} />
                </div>
                <button onClick={submitForceClose} disabled={!fcReason || !fcResolution} style={{ width: '100%', padding: '10px', borderRadius: 8, border: 'none', background: (fcReason && fcResolution) ? C.cyan : 'rgba(0,229,255,0.2)', color: (fcReason && fcResolution) ? '#000' : C.textSec, fontWeight: 600, cursor: (fcReason && fcResolution) ? 'pointer' : 'default', fontSize: 13 }}>
                  수동 판정 확정
                </button>
              </div>
            )}

            <button onClick={() => { setForceCloseModal(null); resetForceCloseForm(); }} style={{ marginTop: 12, width: '100%', padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>닫기</button>
          </div>
        </div>
      )}

      {/* External Result 모달 (외부 결과 입력) */}
      {externalModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => { setExternalModal(null); resetExternalForm(); }}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, minWidth: 500, maxWidth: 600, border: `1px solid ${C.border}`, maxHeight: '85vh', overflowY: 'auto' }} onClick={e => e.stopPropagation()}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: '#f472b6', marginBottom: 16 }}>
              외부 결과 입력 — 중재 #{externalModal.id}
            </h3>

            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: C.textSec, marginBottom: 4, display: 'block' }}>결과 설명</label>
              <textarea value={extDescription} onChange={e => setExtDescription(e.target.value)} placeholder="외부기관 결과를 입력하세요" style={{ width: '100%', minHeight: 80, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13, resize: 'vertical' }} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: C.textSec, marginBottom: 4, display: 'block' }}>문서 URL</label>
              <input type="url" value={extDocUrl} onChange={e => setExtDocUrl(e.target.value)} placeholder="https://..." style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: C.textSec, marginBottom: 4, display: 'block' }}>보상 유형</label>
              <select value={extCompType} onChange={e => setExtCompType(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }}>
                <option value="no_compensation">보상 없음</option>
                <option value="full_refund">전액 환불</option>
                <option value="partial_refund">부분 환불</option>
                <option value="point_credit">포인트 보상</option>
              </select>
            </div>
            {extCompType !== 'no_compensation' && (
              <div style={{ marginBottom: 12 }}>
                <label style={{ fontSize: 12, color: C.textSec, marginBottom: 4, display: 'block' }}>보상 금액</label>
                <input type="number" value={extCompAmount} onChange={e => setExtCompAmount(e.target.value)} placeholder="금액 입력" style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }} />
              </div>
            )}
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 12, color: C.textSec, marginBottom: 4, display: 'block' }}>처리 결과</label>
              <select value={extResolution} onChange={e => setExtResolution(e.target.value)} style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'var(--bg-primary)', color: C.text, fontSize: 13 }}>
                <option value="">선택하세요</option>
                <option value="buyer_win">구매자 승</option>
                <option value="seller_win">판매자 승</option>
                <option value="compromise">절충</option>
                <option value="dismissed">기각</option>
              </select>
            </div>

            <button onClick={submitExternalResult} disabled={!extDescription || !extResolution} style={{ width: '100%', padding: '10px', borderRadius: 8, border: 'none', background: (extDescription && extResolution) ? '#f472b6' : 'rgba(244,114,182,0.2)', color: (extDescription && extResolution) ? '#000' : C.textSec, fontWeight: 600, cursor: (extDescription && extResolution) ? 'pointer' : 'default', fontSize: 13 }}>
              외부 결과 반영
            </button>

            <button onClick={() => { setExternalModal(null); resetExternalForm(); }} style={{ marginTop: 12, width: '100%', padding: '10px', borderRadius: 8, border: `1px solid ${C.border}`, background: 'transparent', color: C.textSec, cursor: 'pointer' }}>닫기</button>
          </div>
        </div>
      )}
    </div>
  );
}
