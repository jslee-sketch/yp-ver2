import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const BASE = import.meta.env.VITE_API_BASE || '';

/* ── 타입 ── */
interface DisputeData {
  id: number;
  status: string;
  current_round: number;
  category: string;
  title: string;
  initiator: { id: number; role: string; name: string };
  respondent: { id: number; name: string };
  reservation_id: number;
  order_number?: string;
  reservation_amount: number;
  description: string;
  evidence: { type: string; url: string; description: string }[];
  requested_resolution: string;
  requested_amount: number;
  initiator_amount_type?: string;
  initiator_amount_value?: number;
  initiator_shipping_burden?: string;
  initiator_return_required?: boolean;
  round1: {
    response: string;
    response_evidence: unknown[];
    proposal_type: string;
    proposal_amount: number;
    deadline: string;
    ai_opinion: string;
    ai_recommendation: string;
    ai_amount: number;
    ai_explanation: { to_initiator?: string; to_respondent?: string; reasoning?: string };
    respondent_amount_type?: string;
    respondent_shipping_burden?: string;
    respondent_return_required?: boolean;
    ai_amount_type?: string;
    ai_shipping_burden?: string;
    ai_return_required?: boolean;
    ai_legal_basis?: string;
    ai_nudge_buyer?: string;
    ai_nudge_seller?: string;
    initiator_decision: string;
    respondent_decision: string;
  };
  round2: {
    rebuttal_by: string;
    initiator_rebuttal: string;
    respondent_rebuttal: string;
    deadline: string;
    ai_opinion: string;
    ai_recommendation: string;
    ai_amount: number;
    ai_explanation: { to_initiator?: string; to_respondent?: string; reasoning?: string };
    ai_legal_basis?: string;
    ai_nudge_buyer?: string;
    ai_nudge_seller?: string;
    initiator_decision: string;
    respondent_decision: string;
  } | null;
  accepted_proposal_source?: string;
  accepted_proposal_type?: string;
  accepted_amount?: number;
  accepted_shipping_burden?: string;
  accepted_return_required?: boolean;
  resolution: string;
  resolution_amount: number;
  closed_at: string;
  closed_reason: string;
  legal_guidance_sent: boolean;
  current_deadline: string;
  days_remaining: number;
  created_at: string;
}

/* ── 상수 ── */
const C = {
  bg: '#0d0d1a', card: '#141428', cardAlt: '#1a1a2e', border: '#2a2a4a',
  text: '#e0e0e0', textSec: '#9ca3af', textDim: '#666',
  green: '#00e676', orange: '#ff8c42', cyan: '#00e5ff', red: '#ff5252',
  pink: '#f472b6', yellow: '#fbbf24', purple: '#a78bfa',
};

const statusLabels: Record<string, { label: string; color: string; icon: string }> = {
  ROUND1_RESPONSE: { label: 'Round 1 반론 대기', color: C.orange, icon: '🔶' },
  ROUND1_AI:       { label: 'AI 분석 중', color: C.purple, icon: '🤖' },
  ROUND1_REVIEW:   { label: 'Round 1 검토 대기', color: C.cyan, icon: '🔍' },
  ROUND2_RESPONSE: { label: 'Round 2 재반론 대기', color: C.yellow, icon: '🔶' },
  ROUND2_AI:       { label: 'AI 2차 분석 중', color: C.purple, icon: '🤖' },
  ROUND2_REVIEW:   { label: 'Round 2 최종 검토', color: C.pink, icon: '🔍' },
  ACCEPTED:        { label: '합의 완료', color: C.green, icon: '🎉' },
  REJECTED:        { label: '미합의 (법적 안내)', color: C.red, icon: '⚖️' },
  AUTO_CLOSED:     { label: '자동 종결', color: C.textDim, icon: '⏰' },
};

const categoryLabels: Record<string, string> = {
  defective: '품질 불량', wrong_item: '오배송', damaged: '파손',
  not_delivered: '미배송', description_mismatch: '설명 불일치',
  quantity_shortage: '수량 부족', buyer_change_mind: '단순 변심', '기타': '기타',
};

const resolutionLabels: Record<string, string> = {
  FULL_REFUND: '전액 환불', PARTIAL_REFUND: '부분 환불', EXCHANGE: '교환',
  COMPENSATION: '보상금', NO_ACTION: '조치 없음',
  full_refund: '전액 환불', partial_refund: '부분 환불', exchange: '교환',
  compensation: '보상금', no_action: '조치 없음',
};

const fmt = (n?: number) => (n ?? 0).toLocaleString('ko-KR');
const fmtDate = (s?: string) => {
  if (!s) return '';
  const d = new Date(s);
  return d.toLocaleString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
};

/* ── 카운트다운 훅 ── */
function useCountdown(deadline?: string) {
  const [remaining, setRemaining] = useState('');
  useEffect(() => {
    if (!deadline) return;
    const tick = () => {
      const diff = new Date(deadline).getTime() - Date.now();
      if (diff <= 0) { setRemaining('기한 만료'); return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setRemaining(`${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`);
    };
    tick();
    const iv = setInterval(tick, 1000);
    return () => clearInterval(iv);
  }, [deadline]);
  return remaining;
}

/* ── 메인 컴포넌트 ── */
export default function DisputeDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const userId = user?.id ?? 0;

  const [dispute, setDispute] = useState<DisputeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Action form states
  const [showResponseForm, setShowResponseForm] = useState(false);
  const [responseText, setResponseText] = useState('');
  const [proposalType, setProposalType] = useState('partial_refund');
  const [proposalAmount, setProposalAmount] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [actionMsg, setActionMsg] = useState('');

  const load = useCallback(() => {
    fetch(`${BASE}/v3_6/disputes/${id}`)
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(setDispute)
      .catch(() => setError('분쟁 정보를 불러오지 못했습니다.'))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const countdown = useCountdown(dispute?.current_deadline);

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: C.textSec }}>로딩 중...</div>;
  if (error || !dispute) return (
    <div style={{ padding: 40, textAlign: 'center', color: C.textSec }}>
      <div style={{ fontSize: 48, marginBottom: 12 }}>⚖️</div>
      <div style={{ fontSize: 14, marginBottom: 16 }}>{error || '분쟁을 찾을 수 없습니다'}</div>
      <button onClick={() => navigate(-1)} style={btnStyle(C.textDim)}>뒤로가기</button>
    </div>
  );

  const isClosed = ['ACCEPTED', 'REJECTED', 'AUTO_CLOSED'].includes(dispute.status);
  const isInitiator = userId === dispute.initiator.id;
  const isRespondent = userId === dispute.respondent.id;
  const isParty = isInitiator || isRespondent;
  const st = statusLabels[dispute.status] || { label: dispute.status, color: C.textDim, icon: '❓' };

  const myRole = isInitiator ? 'initiator' : isRespondent ? 'respondent' : 'observer';
  const myLabel = isInitiator ? '신청자(나)' : isRespondent ? '상대방(나)' : '관리자';

  /* ── 액션: 반론 제출 ── */
  const handleResponse = async () => {
    setSubmitting(true);
    setActionMsg('');
    try {
      const endpoint = dispute.status === 'ROUND1_RESPONSE'
        ? `${BASE}/v3_6/disputes/${id}/round1-response`
        : `${BASE}/v3_6/disputes/${id}/round2-rebuttal`;
      const body = dispute.status === 'ROUND1_RESPONSE'
        ? { respondent_id: userId, reply: responseText, proposal_type: proposalType, proposal_amount: proposalAmount }
        : { user_id: userId, rebuttal: responseText, proposal_type: proposalType, proposal_amount: proposalAmount };
      const method = dispute.status === 'ROUND1_RESPONSE' ? 'PUT' : 'PUT';
      const res = await fetch(endpoint, {
        method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || '제출 실패'); }
      setActionMsg('제출 완료!');
      setShowResponseForm(false);
      setResponseText('');
      load();
    } catch (e: unknown) {
      setActionMsg(e instanceof Error ? e.message : '오류 발생');
    } finally {
      setSubmitting(false);
    }
  };

  /* ── 액션: 동의/거절 ── */
  const handleDecision = async (decision: string) => {
    setSubmitting(true);
    setActionMsg('');
    try {
      const res = await fetch(`${BASE}/v3_6/disputes/${id}/decision`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, decision }),
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || '실패'); }
      setActionMsg(decision === 'accept' ? '동의 완료' : '거절 완료');
      load();
    } catch (e: unknown) {
      setActionMsg(e instanceof Error ? e.message : '오류 발생');
    } finally {
      setSubmitting(false);
    }
  };

  /* ── 현재 상태에서 가능한 액션 ── */
  const canRespond = isRespondent && dispute.status === 'ROUND1_RESPONSE';
  const canRebuttal = isParty && dispute.status === 'ROUND2_RESPONSE';
  const canDecideR1 = isParty && dispute.status === 'ROUND1_REVIEW';
  const canDecideR2 = isParty && dispute.status === 'ROUND2_REVIEW';

  // 내가 이미 결정했는지
  const myR1Decision = isInitiator ? dispute.round1.initiator_decision : dispute.round1.respondent_decision;
  const myR2Decision = dispute.round2 ? (isInitiator ? dispute.round2.initiator_decision : dispute.round2.respondent_decision) : null;

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      {/* Header */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', background: 'none', border: 'none' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>분쟁 상세</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '16px 16px 40px' }}>

        {/* ── 분쟁 헤더 카드 ── */}
        <div style={{
          background: C.card, border: `1px solid ${C.border}`, borderRadius: 16,
          padding: '18px 16px', marginBottom: 16,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 22 }}>{st.icon}</span>
            <div>
              <div style={{ fontSize: 16, fontWeight: 800, color: C.text }}>분쟁 #{dispute.id}</div>
              <div style={{ fontSize: 11, color: C.textSec }}>
                {dispute.order_number ? `주문번호: ${dispute.order_number}` : `예약 #${dispute.reservation_id}`}
                {dispute.created_at && ` · ${fmtDate(dispute.created_at)}`}
              </div>
            </div>
          </div>

          {/* 상태 뱃지 */}
          <div style={{
            display: 'inline-block', padding: '5px 14px', borderRadius: 20, marginBottom: 12,
            background: `${st.color}15`, border: `1px solid ${st.color}30`,
            color: st.color, fontSize: 13, fontWeight: 700,
          }}>
            {st.label}
            {dispute.days_remaining != null && !isClosed && ` (${dispute.days_remaining}영업일 남음)`}
          </div>

          {/* 당사자 정보 */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
            <PartyBadge label="신청자" name={dispute.initiator.name} role={dispute.initiator.role} color={C.cyan} isMe={isInitiator} />
            <span style={{ color: C.textDim, fontSize: 16 }}>→</span>
            <PartyBadge label="상대방" name={dispute.respondent.name} role={dispute.initiator.role === 'buyer' ? 'seller' : 'buyer'} color={C.orange} isMe={isRespondent} />
          </div>

          {/* 카운트다운 */}
          {!isClosed && countdown && (
            <div style={{
              marginTop: 8, padding: '8px 12px', borderRadius: 10,
              background: 'rgba(255,140,66,0.08)', border: '1px solid rgba(255,140,66,0.15)',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <span style={{ fontSize: 14 }}>⏰</span>
              <span style={{ fontFamily: "'Courier New', monospace", fontSize: 18, fontWeight: 700, color: countdown === '기한 만료' ? C.red : C.orange }}>
                {countdown}
              </span>
              <span style={{ fontSize: 11, color: C.textSec }}>
                {dispute.status === 'ROUND1_RESPONSE' ? '1차 반론 마감' :
                 dispute.status === 'ROUND1_REVIEW' ? '1차 검토 마감' :
                 dispute.status === 'ROUND2_RESPONSE' ? '2차 반론 마감' :
                 dispute.status === 'ROUND2_REVIEW' ? '2차 검토 마감' : '마감'}
              </span>
            </div>
          )}

          {/* 내 역할 안내 */}
          {isParty && !isClosed && (
            <div style={{ marginTop: 8, fontSize: 11, color: C.cyan }}>
              나는 이 분쟁의 <strong>{myLabel}</strong>입니다
            </div>
          )}
        </div>

        {/* ━━ ROUND 1 타임라인 ━━ */}
        <SectionDivider label="Round 1" color={C.pink} />

        {/* 분쟁 신청 */}
        <TimelineStep icon="📌" title="분쟁 신청" subtitle={fmtDate(dispute.created_at)} done>
          <InfoRow label="카테고리" value={categoryLabels[dispute.category] || dispute.category} />
          <InfoRow label="희망 처리" value={`${resolutionLabels[dispute.requested_resolution] || dispute.requested_resolution} (${fmt(dispute.requested_amount)}원)`} />
          {dispute.initiator_shipping_burden && (
            <InfoRow label="배송비 부담" value={dispute.initiator_shipping_burden === 'seller' ? '판매자' : dispute.initiator_shipping_burden === 'buyer' ? '구매자' : '분담'} />
          )}
          <div style={{ fontSize: 12, color: C.text, marginTop: 6, lineHeight: 1.6, padding: '8px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
            {dispute.description}
          </div>
          {dispute.evidence.length > 0 && (
            <div style={{ fontSize: 11, color: C.cyan, marginTop: 4 }}>
              📷 증거 {dispute.evidence.length}건 첨부
            </div>
          )}
        </TimelineStep>

        {/* 1차 반론 + 제안 */}
        <TimelineStep icon="💬" title="1차 반론 + 제안" subtitle={dispute.round1.response ? '' : (dispute.round1.deadline ? `마감: ${fmtDate(dispute.round1.deadline)}` : '')} done={!!dispute.round1.response}>
          {dispute.round1.response ? (
            <>
              <div style={{ fontSize: 12, color: C.text, lineHeight: 1.6, padding: '8px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
                {dispute.round1.response}
              </div>
              <div style={{ fontSize: 11, color: C.orange, marginTop: 6 }}>
                제안: {resolutionLabels[dispute.round1.proposal_type] || dispute.round1.proposal_type} / {fmt(dispute.round1.proposal_amount)}원
                {dispute.round1.respondent_shipping_burden && ` · 배송비: ${dispute.round1.respondent_shipping_burden === 'seller' ? '판매자' : '구매자'}`}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 12, color: C.textDim }}>반론 대기 중</div>
          )}
        </TimelineStep>

        {/* 반론 제출 폼 */}
        {canRespond && (
          <ActionCard>
            {!showResponseForm ? (
              <button onClick={() => setShowResponseForm(true)} style={actionBtnStyle(C.orange)}>
                💬 반론 + 제안 제출하기
              </button>
            ) : (
              <ResponseForm
                text={responseText} setText={setResponseText}
                proposalType={proposalType} setProposalType={setProposalType}
                proposalAmount={proposalAmount} setProposalAmount={setProposalAmount}
                onSubmit={handleResponse} onCancel={() => setShowResponseForm(false)}
                submitting={submitting} label="1차 반론"
              />
            )}
          </ActionCard>
        )}

        {/* AI 1차 중재 */}
        <TimelineStep icon="🤖" title="AI 1차 중재 의견" done={!!dispute.round1.ai_opinion}>
          {dispute.round1.ai_opinion ? (
            <AIMediation
              opinion={dispute.round1.ai_opinion}
              recommendation={dispute.round1.ai_recommendation}
              amount={dispute.round1.ai_amount}
              explanation={dispute.round1.ai_explanation}
              legalBasis={dispute.round1.ai_legal_basis}
              nudgeBuyer={dispute.round1.ai_nudge_buyer}
              nudgeSeller={dispute.round1.ai_nudge_seller}
              shippingBurden={dispute.round1.ai_shipping_burden}
              returnRequired={dispute.round1.ai_return_required}
              myRole={myRole}
            />
          ) : (
            <div style={{ fontSize: 12, color: C.textDim }}>
              {dispute.status === 'ROUND1_AI' ? 'AI가 분석 중입니다...' : '반론 제출 후 진행됩니다'}
            </div>
          )}
        </TimelineStep>

        {/* 1차 동의/거절 */}
        <TimelineStep
          icon={dispute.round1.initiator_decision === 'accept' && dispute.round1.respondent_decision === 'accept' ? '✅' :
                dispute.round1.initiator_decision === 'reject' || dispute.round1.respondent_decision === 'reject' ? '❌' : '⏳'}
          title="1차 동의 결정"
          done={!!(dispute.round1.initiator_decision && dispute.round1.respondent_decision)}
        >
          <DecisionDisplay label="신청자" decision={dispute.round1.initiator_decision} />
          <DecisionDisplay label="상대방" decision={dispute.round1.respondent_decision} />
        </TimelineStep>

        {/* 1차 동의/거절 액션 */}
        {canDecideR1 && !myR1Decision && (
          <ActionCard>
            <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>
              AI 중재안에 동의하시겠습니까?
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => handleDecision('accept')} disabled={submitting} style={actionBtnStyle(C.green)}>
                ✅ 동의
              </button>
              <button onClick={() => handleDecision('reject')} disabled={submitting} style={actionBtnStyle(C.red)}>
                ❌ 거절
              </button>
            </div>
          </ActionCard>
        )}

        {/* ━━ ROUND 2 ━━ */}
        {(dispute.round2 || dispute.status === 'ROUND2_RESPONSE') && (
          <>
            <SectionDivider label="Round 2" color={C.yellow} />

            {/* 재반론 */}
            <TimelineStep icon="💬" title="2차 재반론" done={!!(dispute.round2?.initiator_rebuttal || dispute.round2?.respondent_rebuttal)}>
              {dispute.round2?.initiator_rebuttal && (
                <div style={{ marginBottom: 6 }}>
                  <div style={{ fontSize: 11, color: C.cyan, marginBottom: 2 }}>신청자 재반론:</div>
                  <div style={{ fontSize: 12, color: C.text, padding: '6px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
                    {dispute.round2.initiator_rebuttal}
                  </div>
                </div>
              )}
              {dispute.round2?.respondent_rebuttal && (
                <div>
                  <div style={{ fontSize: 11, color: C.orange, marginBottom: 2 }}>상대방 재반론:</div>
                  <div style={{ fontSize: 12, color: C.text, padding: '6px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: 8 }}>
                    {dispute.round2.respondent_rebuttal}
                  </div>
                </div>
              )}
              {!dispute.round2?.initiator_rebuttal && !dispute.round2?.respondent_rebuttal && (
                <div style={{ fontSize: 12, color: C.textDim }}>재반론 대기 중</div>
              )}
            </TimelineStep>

            {/* R2 반론 제출 폼 */}
            {canRebuttal && (
              <ActionCard>
                {!showResponseForm ? (
                  <button onClick={() => setShowResponseForm(true)} style={actionBtnStyle(C.yellow)}>
                    💬 2차 반론 제출하기
                  </button>
                ) : (
                  <ResponseForm
                    text={responseText} setText={setResponseText}
                    proposalType={proposalType} setProposalType={setProposalType}
                    proposalAmount={proposalAmount} setProposalAmount={setProposalAmount}
                    onSubmit={handleResponse} onCancel={() => setShowResponseForm(false)}
                    submitting={submitting} label="2차 반론"
                  />
                )}
              </ActionCard>
            )}

            {/* AI 2차 중재 */}
            {dispute.round2 && (
              <TimelineStep icon="🤖" title="AI 2차 중재 의견" done={!!dispute.round2.ai_opinion}>
                {dispute.round2.ai_opinion ? (
                  <AIMediation
                    opinion={dispute.round2.ai_opinion}
                    recommendation={dispute.round2.ai_recommendation}
                    amount={dispute.round2.ai_amount}
                    explanation={dispute.round2.ai_explanation}
                    legalBasis={dispute.round2.ai_legal_basis}
                    nudgeBuyer={dispute.round2.ai_nudge_buyer}
                    nudgeSeller={dispute.round2.ai_nudge_seller}
                    myRole={myRole}
                  />
                ) : (
                  <div style={{ fontSize: 12, color: C.textDim }}>
                    {dispute.status === 'ROUND2_AI' ? 'AI 2차 분석 중...' : '재반론 제출 후 진행됩니다'}
                  </div>
                )}
              </TimelineStep>
            )}

            {/* 2차 결정 */}
            {dispute.round2 && (dispute.round2.ai_opinion || dispute.status === 'ROUND2_REVIEW') && (
              <TimelineStep
                icon={dispute.round2.initiator_decision === 'accept' && dispute.round2.respondent_decision === 'accept' ? '✅' :
                      dispute.round2.initiator_decision === 'reject' || dispute.round2.respondent_decision === 'reject' ? '❌' : '⏳'}
                title="2차 동의 결정"
                done={!!(dispute.round2.initiator_decision && dispute.round2.respondent_decision)}
              >
                <DecisionDisplay label="신청자" decision={dispute.round2.initiator_decision} />
                <DecisionDisplay label="상대방" decision={dispute.round2.respondent_decision} />
              </TimelineStep>
            )}

            {/* 2차 동의/거절 액션 */}
            {canDecideR2 && !myR2Decision && (
              <ActionCard>
                <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>
                  AI 2차 중재안에 동의하시겠습니까?
                </div>
                <div style={{ fontSize: 11, color: C.red, marginBottom: 10 }}>
                  2차 거절 시 법적 절차 안내로 전환됩니다
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => handleDecision('accept')} disabled={submitting} style={actionBtnStyle(C.green)}>
                    ✅ 동의
                  </button>
                  <button onClick={() => handleDecision('reject')} disabled={submitting} style={actionBtnStyle(C.red)}>
                    ❌ 거절
                  </button>
                </div>
              </ActionCard>
            )}
          </>
        )}

        {/* ━━ 결과 ━━ */}
        {isClosed && (
          <>
            <SectionDivider label="결과" color={dispute.status === 'ACCEPTED' ? C.green : C.red} />

            {dispute.status === 'ACCEPTED' && (
              <div style={{
                padding: 18, borderRadius: 14,
                background: 'rgba(0,230,118,0.06)', border: '1px solid rgba(0,230,118,0.2)',
              }}>
                <div style={{ fontSize: 22, marginBottom: 6 }}>🎉</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: C.green, marginBottom: 8 }}>합의 완료!</div>
                {dispute.accepted_proposal_source && (
                  <InfoRow label="채택안"
                    value={dispute.accepted_proposal_source === 'ai' ? 'AI 추천안' :
                           dispute.accepted_proposal_source === 'respondent' ? '상대방 제안' : '신청자 제안'} />
                )}
                <InfoRow label="합의 유형" value={resolutionLabels[dispute.accepted_proposal_type || ''] || dispute.accepted_proposal_type || ''} />
                <div style={{ fontSize: 18, fontWeight: 800, color: C.green, margin: '8px 0' }}>
                  합의 금액: {fmt(dispute.accepted_amount ?? dispute.resolution_amount)}원
                </div>
                {dispute.accepted_shipping_burden && (
                  <InfoRow label="배송비" value={dispute.accepted_shipping_burden === 'seller' ? '판매자 부담' : dispute.accepted_shipping_burden === 'buyer' ? '구매자 부담' : '분담'} />
                )}
                {dispute.accepted_return_required != null && (
                  <InfoRow label="반품" value={dispute.accepted_return_required ? '필요' : '불필요'} />
                )}
                <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 8, background: 'rgba(0,230,118,0.08)', fontSize: 11, color: C.green }}>
                  후속 처리(환불/정산 재계산)가 자동으로 진행됩니다.
                </div>
              </div>
            )}

            {dispute.status === 'REJECTED' && (
              <div style={{
                padding: 18, borderRadius: 14,
                background: 'rgba(255,82,82,0.06)', border: '1px solid rgba(255,82,82,0.2)',
              }}>
                <div style={{ fontSize: 22, marginBottom: 6 }}>⚖️</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: C.red, marginBottom: 12 }}>미합의 — 법적 안내</div>
                <div style={{ fontSize: 13, color: C.text, lineHeight: 1.8 }}>
                  양측 합의에 이르지 못했습니다. 아래 외부 기관을 통해 해결하실 수 있습니다:
                </div>
                <div style={{ marginTop: 10, padding: '10px 14px', borderRadius: 10, background: 'rgba(255,255,255,0.03)', fontSize: 12, color: C.textSec, lineHeight: 1.8 }}>
                  <strong style={{ color: C.text }}>1. 소비자원 중재</strong><br />
                  1372.go.kr 또는 1372 전화<br /><br />
                  <strong style={{ color: C.text }}>2. 소액사건심판</strong> (2,000만원 이하)<br />
                  관할 법원에 소액심판 청구<br /><br />
                  <strong style={{ color: C.text }}>3. 변호사 연결</strong><br />
                  고객센터 문의 → 법률 전문가 연결 가능
                </div>
                <div style={{ marginTop: 10, fontSize: 11, color: C.textDim }}>
                  정산은 계속 보류 상태입니다. 외부 해결 후 관리자에게 연락해주세요.
                </div>
              </div>
            )}

            {dispute.status === 'AUTO_CLOSED' && (
              <div style={{
                padding: 18, borderRadius: 14,
                background: 'rgba(102,102,102,0.06)', border: `1px solid ${C.border}`,
              }}>
                <div style={{ fontSize: 22, marginBottom: 6 }}>⏰</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: C.textDim, marginBottom: 8 }}>자동 종결</div>
                <div style={{ fontSize: 12, color: C.textSec, lineHeight: 1.6 }}>
                  기한 내 답변이 없어 자동 종결되었습니다.<br />
                  사유: {dispute.closed_reason}<br />
                  종결 시각: {fmtDate(dispute.closed_at)}
                </div>
              </div>
            )}
          </>
        )}

        {/* 액션 메시지 */}
        {actionMsg && (
          <div style={{
            position: 'fixed', bottom: 80, left: '50%', transform: 'translateX(-50%)',
            padding: '10px 20px', borderRadius: 12, background: C.card, border: `1px solid ${C.border}`,
            color: C.text, fontSize: 13, fontWeight: 600, zIndex: 200,
          }}>
            {actionMsg}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── 하위 컴포넌트 ── */

function PartyBadge({ label, name, role, color, isMe }: { label: string; name: string; role: string; color: string; isMe: boolean }) {
  return (
    <div style={{
      flex: 1, padding: '8px 10px', borderRadius: 10,
      background: isMe ? `${color}10` : 'rgba(255,255,255,0.02)',
      border: `1px solid ${isMe ? `${color}30` : C.border}`,
    }}>
      <div style={{ fontSize: 10, color: isMe ? color : C.textDim, fontWeight: 700, marginBottom: 2 }}>
        {label} {isMe && '(나)'}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{name}</div>
      <div style={{ fontSize: 10, color: C.textSec }}>{role === 'buyer' ? '구매자' : '판매자'}</div>
    </div>
  );
}

function SectionDivider({ label, color }: { label: string; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '20px 0 12px' }}>
      <div style={{ flex: 1, height: 1, background: `${color}30` }} />
      <span style={{ fontSize: 13, fontWeight: 800, color, letterSpacing: 1 }}>{label}</span>
      <div style={{ flex: 1, height: 1, background: `${color}30` }} />
    </div>
  );
}

function TimelineStep({ icon, title, subtitle, done, children }: {
  icon: string; title: string; subtitle?: string; done?: boolean; children?: React.ReactNode;
}) {
  return (
    <div style={{
      display: 'flex', gap: 10, marginBottom: 10, padding: '12px 14px',
      background: C.card, borderRadius: 12,
      borderLeft: `3px solid ${done ? C.green : '#333'}`,
    }}>
      <span style={{ fontSize: 18, flexShrink: 0, lineHeight: 1 }}>{icon}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: children ? 6 : 0 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: done ? C.text : C.textDim }}>{title}</span>
          {subtitle && <span style={{ fontSize: 10, color: C.textDim }}>{subtitle}</span>}
        </div>
        {children}
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 12 }}>
      <span style={{ color: C.textSec }}>{label}</span>
      <span style={{ color: C.text, fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function DecisionDisplay({ label, decision }: { label: string; decision: string }) {
  const map: Record<string, { text: string; color: string }> = {
    accept: { text: '동의', color: C.green },
    reject: { text: '거절', color: C.red },
    ACCEPT: { text: '동의', color: C.green },
    REJECT: { text: '거절', color: C.red },
  };
  const d = map[decision] || { text: decision || '대기', color: C.textDim };
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, marginBottom: 2 }}>
      <span style={{ color: C.textSec }}>{label}:</span>
      <span style={{ color: d.color, fontWeight: 700 }}>{d.text === '동의' ? '✅ ' : d.text === '거절' ? '❌ ' : '⏳ '}{d.text}</span>
    </div>
  );
}

function ActionCard({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      margin: '0 0 10px', padding: '14px 16px', borderRadius: 12,
      background: 'rgba(255,140,66,0.04)', border: '1px solid rgba(255,140,66,0.15)',
    }}>
      {children}
    </div>
  );
}

function AIMediation({ opinion, recommendation, amount, explanation, legalBasis, nudgeBuyer, nudgeSeller, shippingBurden, returnRequired, myRole }: {
  opinion: string; recommendation: string; amount: number;
  explanation: { to_initiator?: string; to_respondent?: string; reasoning?: string };
  legalBasis?: string; nudgeBuyer?: string; nudgeSeller?: string;
  shippingBurden?: string; returnRequired?: boolean; myRole: string;
}) {
  const fmt2 = (n: number) => n.toLocaleString('ko-KR');
  return (
    <>
      <div style={{ fontSize: 12, color: C.text, lineHeight: 1.6, marginBottom: 8 }}>{opinion}</div>
      <div style={{
        padding: '8px 12px', borderRadius: 8, background: 'rgba(0,230,118,0.06)',
        border: '1px solid rgba(0,230,118,0.15)', marginBottom: 8,
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: C.green }}>
          추천: {resolutionLabels[recommendation] || recommendation} / {fmt2(amount)}원
        </div>
        {shippingBurden && (
          <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
            배송비: {shippingBurden === 'seller' ? '판매자 부담' : shippingBurden === 'buyer' ? '구매자 부담' : '분담'}
            {returnRequired != null && ` · 반품: ${returnRequired ? '필요' : '불필요'}`}
          </div>
        )}
      </div>
      {legalBasis && (
        <div style={{ fontSize: 11, color: '#60a5fa', marginBottom: 6 }}>
          📌 법적 근거: {legalBasis}
        </div>
      )}
      {explanation.reasoning && (
        <div style={{ fontSize: 11, color: C.textSec, marginBottom: 6, lineHeight: 1.5 }}>
          {explanation.reasoning}
        </div>
      )}
      {/* 넛지 - 역할별 표시 */}
      {(myRole === 'initiator' || myRole === 'observer') && nudgeBuyer && (
        <div style={{ padding: '6px 10px', borderRadius: 8, background: 'rgba(96,165,250,0.08)', border: '1px solid rgba(96,165,250,0.12)', fontSize: 11, color: '#93c5fd', marginBottom: 4 }}>
          💡 {nudgeBuyer}
        </div>
      )}
      {(myRole === 'respondent' || myRole === 'observer') && nudgeSeller && (
        <div style={{ padding: '6px 10px', borderRadius: 8, background: 'rgba(255,140,66,0.08)', border: '1px solid rgba(255,140,66,0.12)', fontSize: 11, color: '#fbbf24', marginBottom: 4 }}>
          💡 {nudgeSeller}
        </div>
      )}
      {/* 개별 설명 */}
      {myRole === 'initiator' && explanation.to_initiator && (
        <div style={{ fontSize: 11, color: C.cyan, marginTop: 4 }}>{explanation.to_initiator}</div>
      )}
      {myRole === 'respondent' && explanation.to_respondent && (
        <div style={{ fontSize: 11, color: C.orange, marginTop: 4 }}>{explanation.to_respondent}</div>
      )}
      {myRole === 'observer' && (
        <>
          {explanation.to_initiator && <div style={{ fontSize: 11, color: C.cyan, marginTop: 4 }}>신청자에게: {explanation.to_initiator}</div>}
          {explanation.to_respondent && <div style={{ fontSize: 11, color: C.orange, marginTop: 2 }}>상대방에게: {explanation.to_respondent}</div>}
        </>
      )}
    </>
  );
}

function ResponseForm({ text, setText, proposalType, setProposalType, proposalAmount, setProposalAmount, onSubmit, onCancel, submitting, label }: {
  text: string; setText: (v: string) => void;
  proposalType: string; setProposalType: (v: string) => void;
  proposalAmount: number; setProposalAmount: (v: number) => void;
  onSubmit: () => void; onCancel: () => void;
  submitting: boolean; label: string;
}) {
  const proposals = [
    { value: 'full_refund', label: '전액 환불' },
    { value: 'partial_refund', label: '부분 환불' },
    { value: 'exchange', label: '교환' },
    { value: 'compensation', label: '보상금' },
    { value: 'no_action', label: '조치 불필요' },
  ];
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 8 }}>{label} 제출</div>
      <textarea value={text} onChange={e => setText(e.target.value)} placeholder={`${label} 내용을 작성하세요`}
        style={{ width: '100%', minHeight: 80, padding: 10, borderRadius: 8, border: `1px solid ${C.border}`, background: C.bg, color: C.text, fontSize: 13, resize: 'vertical', marginBottom: 8 }} />
      <div style={{ fontSize: 12, color: C.textSec, marginBottom: 6 }}>제안</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
        {proposals.map(p => (
          <button key={p.value} onClick={() => setProposalType(p.value)} style={{
            padding: '5px 10px', borderRadius: 6, fontSize: 11, cursor: 'pointer',
            background: proposalType === p.value ? 'rgba(255,140,66,0.15)' : 'transparent',
            border: `1px solid ${proposalType === p.value ? C.orange : C.border}`,
            color: proposalType === p.value ? C.orange : C.textSec,
          }}>{p.label}</button>
        ))}
      </div>
      {proposalType !== 'no_action' && proposalType !== 'exchange' && (
        <input type="number" value={proposalAmount} onChange={e => setProposalAmount(+e.target.value)} placeholder="금액 (원)"
          style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.bg, color: C.text, fontSize: 13, marginBottom: 8 }} />
      )}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={onCancel} style={btnStyle(C.textDim)}>취소</button>
        <button onClick={onSubmit} disabled={submitting || !text.trim()} style={actionBtnStyle(C.orange)}>
          {submitting ? '제출 중...' : '제출'}
        </button>
      </div>
    </div>
  );
}

function btnStyle(color: string): React.CSSProperties {
  return { flex: 1, padding: '10px', borderRadius: 10, fontSize: 13, fontWeight: 600, cursor: 'pointer', background: 'transparent', border: `1px solid ${C.border}`, color };
}

function actionBtnStyle(color: string): React.CSSProperties {
  return { flex: 1, padding: '10px', borderRadius: 10, fontSize: 13, fontWeight: 700, cursor: 'pointer', background: `${color}15`, border: `1px solid ${color}30`, color };
}
