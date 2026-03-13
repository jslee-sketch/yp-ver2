import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';

const BASE = import.meta.env.VITE_API_BASE || '';

interface DisputeData {
  id: number;
  status: string;
  current_round: number;
  category: string;
  title: string;
  initiator: { id: number; role: string };
  respondent: { id: number };
  description: string;
  evidence: { type: string; url: string; description: string }[];
  requested_resolution: string;
  requested_amount: number;
  round1: {
    response: string;
    response_evidence: any[];
    proposal_type: string;
    proposal_amount: number;
    deadline: string;
    ai_opinion: string;
    ai_recommendation: string;
    ai_amount: number;
    ai_explanation: { to_initiator?: string; to_respondent?: string; reasoning?: string };
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
    initiator_decision: string;
    respondent_decision: string;
  } | null;
  resolution: string;
  resolution_amount: number;
  closed_at: string;
  closed_reason: string;
  legal_guidance_sent: boolean;
  current_deadline: string;
  days_remaining: number;
}

const statusLabels: Record<string, string> = {
  ROUND1_RESPONSE: '반론 대기',
  ROUND1_AI: 'AI 분석 중',
  ROUND1_REVIEW: '검토 대기',
  ROUND2_RESPONSE: '재반론 대기',
  ROUND2_AI: 'AI 2차 분석 중',
  ROUND2_REVIEW: '최종 검토 대기',
  ACCEPTED: '합의 완료',
  REJECTED: '미합의 (법적 안내)',
  AUTO_CLOSED: '자동 종결',
};

export default function DisputeDetailPage() {
  const { id } = useParams();
  const [dispute, setDispute] = useState<DisputeData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BASE}/v3_6/disputes/${id}`)
      .then(r => r.json())
      .then(setDispute)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div style={{ padding: 40, textAlign: 'center', color: '#888' }}>로딩 중...</div>;
  if (!dispute) return <div style={{ padding: 40, textAlign: 'center', color: '#888' }}>분쟁을 찾을 수 없습니다</div>;

  const isClosed = ['ACCEPTED', 'REJECTED', 'AUTO_CLOSED'].includes(dispute.status);

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 20 }}>
      <h2 style={{ color: '#e0e0e0', fontSize: 18, marginBottom: 16 }}>
        분쟁 #{dispute.id}: {dispute.title}
      </h2>

      {/* Status Badge */}
      <div style={{
        display: 'inline-block', padding: '4px 12px', borderRadius: 8, marginBottom: 16,
        background: isClosed ? (dispute.status === 'ACCEPTED' ? 'rgba(74,222,128,0.15)' : 'rgba(239,68,68,0.15)')
          : 'rgba(96,165,250,0.15)',
        color: isClosed ? (dispute.status === 'ACCEPTED' ? '#4ade80' : '#ef4444') : '#60a5fa',
        fontSize: 13, fontWeight: 600,
      }}>
        {statusLabels[dispute.status] || dispute.status}
        {dispute.days_remaining != null && !isClosed && ` (${dispute.days_remaining}영업일 남음)`}
      </div>

      {/* Round 1 Timeline */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#f472b6', marginBottom: 8 }}>
          Round 1
        </div>

        {/* Filing */}
        <TimelineStep icon="📝" title="분쟁 신청" done>
          <div style={{ fontSize: 12, color: '#aaa' }}>
            카테고리: {dispute.category} | 희망: {dispute.requested_resolution} ({dispute.requested_amount?.toLocaleString()}원)
          </div>
          <div style={{ fontSize: 12, color: '#ccc', marginTop: 4 }}>{dispute.description}</div>
          {dispute.evidence.length > 0 && (
            <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
              증거 {dispute.evidence.length}건 첨부
            </div>
          )}
        </TimelineStep>

        {/* Response */}
        <TimelineStep icon="💬" title="반론+제안" done={!!dispute.round1.response}>
          {dispute.round1.response ? (
            <>
              <div style={{ fontSize: 12, color: '#ccc' }}>{dispute.round1.response}</div>
              <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                제안: {dispute.round1.proposal_type} / {dispute.round1.proposal_amount?.toLocaleString()}원
              </div>
            </>
          ) : (
            <div style={{ fontSize: 12, color: '#666' }}>
              {dispute.round1.deadline && `마감: ${new Date(dispute.round1.deadline).toLocaleDateString('ko-KR')}`}
            </div>
          )}
        </TimelineStep>

        {/* AI Mediation */}
        <TimelineStep icon="🤖" title="AI 1차 중재" done={!!dispute.round1.ai_opinion}>
          {dispute.round1.ai_opinion && (
            <>
              <div style={{ fontSize: 12, color: '#ccc' }}>{dispute.round1.ai_opinion}</div>
              <div style={{ fontSize: 12, color: '#4ade80', marginTop: 4 }}>
                추천 금액: {dispute.round1.ai_amount?.toLocaleString()}원
              </div>
            </>
          )}
        </TimelineStep>

        {/* Decisions */}
        <TimelineStep icon={dispute.round1.initiator_decision === 'accept' ? '✅' : dispute.round1.initiator_decision === 'reject' ? '❌' : '⏳'}
          title={`신청인: ${dispute.round1.initiator_decision || '대기'} | 상대방: ${dispute.round1.respondent_decision || '대기'}`}
          done={!!(dispute.round1.initiator_decision && dispute.round1.respondent_decision)}
        />
      </div>

      {/* Round 2 */}
      {dispute.round2 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: '#f59e0b', marginBottom: 8 }}>
            Round 2
          </div>

          <TimelineStep icon="💬" title="재반론+제안" done={!!(dispute.round2.initiator_rebuttal || dispute.round2.respondent_rebuttal)}>
            {dispute.round2.initiator_rebuttal && (
              <div style={{ fontSize: 12, color: '#ccc' }}>신청인: {dispute.round2.initiator_rebuttal}</div>
            )}
            {dispute.round2.respondent_rebuttal && (
              <div style={{ fontSize: 12, color: '#ccc' }}>상대방: {dispute.round2.respondent_rebuttal}</div>
            )}
          </TimelineStep>

          <TimelineStep icon="🤖" title="AI 2차 중재" done={!!dispute.round2.ai_opinion}>
            {dispute.round2.ai_opinion && (
              <>
                <div style={{ fontSize: 12, color: '#ccc' }}>{dispute.round2.ai_opinion}</div>
                <div style={{ fontSize: 12, color: '#4ade80', marginTop: 4 }}>
                  최종 추천 금액: {dispute.round2.ai_amount?.toLocaleString()}원
                </div>
              </>
            )}
          </TimelineStep>

          <TimelineStep icon={dispute.round2.initiator_decision === 'accept' ? '✅' : dispute.round2.initiator_decision === 'reject' ? '❌' : '⏳'}
            title={`신청인: ${dispute.round2.initiator_decision || '대기'} | 상대방: ${dispute.round2.respondent_decision || '대기'}`}
            done={!!(dispute.round2.initiator_decision && dispute.round2.respondent_decision)}
          />
        </div>
      )}

      {/* Resolution */}
      {isClosed && (
        <div style={{
          padding: 16, borderRadius: 12, marginTop: 16,
          background: dispute.status === 'ACCEPTED' ? 'rgba(74,222,128,0.08)' : 'rgba(239,68,68,0.08)',
          border: `1px solid ${dispute.status === 'ACCEPTED' ? 'rgba(74,222,128,0.2)' : 'rgba(239,68,68,0.2)'}`,
        }}>
          {dispute.status === 'ACCEPTED' && (
            <>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#4ade80' }}>합의 완료</div>
              <div style={{ fontSize: 13, color: '#ccc', marginTop: 4 }}>
                합의 금액: {dispute.resolution_amount?.toLocaleString()}원
              </div>
            </>
          )}
          {dispute.status === 'REJECTED' && (
            <>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#ef4444' }}>미합의 — 법적 안내</div>
              <div style={{ fontSize: 12, color: '#aaa', marginTop: 8, lineHeight: 1.6 }}>
                소액사건심판 (2,000만원 이하) → 법원<br />
                소비자원 중재 → 1372.go.kr<br />
                변호인 연결 가능 → 고객센터 문의
              </div>
            </>
          )}
          {dispute.status === 'AUTO_CLOSED' && (
            <>
              <div style={{ fontSize: 15, fontWeight: 700, color: '#888' }}>자동 종결</div>
              <div style={{ fontSize: 12, color: '#aaa', marginTop: 4 }}>
                기한 내 답변이 없어 자동 종결되었습니다.<br />
                이후 분쟁은 시스템 외에서 1:1로 진행하셔야 합니다.
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function TimelineStep({ icon, title, done, children }: {
  icon: string; title: string; done?: boolean; children?: React.ReactNode;
}) {
  return (
    <div style={{
      display: 'flex', gap: 10, marginBottom: 12, padding: 10,
      background: '#1a1a2e', borderRadius: 10,
      borderLeft: `3px solid ${done ? '#4ade80' : '#333'}`,
    }}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: done ? '#e0e0e0' : '#666' }}>{title}</div>
        {children}
      </div>
    </div>
  );
}
