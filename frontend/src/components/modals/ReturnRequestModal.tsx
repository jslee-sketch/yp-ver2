import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import apiClient from '../../api/client';
import { showToast } from '../common/Toast';

/* ── 타입 ── */
interface OrderData {
  order_number: string;
  items?: string;
  amount: number;
  reservation_id: number;
  seller_id: number;
}

interface ReturnRequestModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: OrderData;
}

/* ── 상수 ── */
const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: '#00e676',
};

const REQUEST_TYPES = [
  { value: 'same_exchange', label: '같은 제품 교환' },
  { value: 'diff_exchange', label: '다른 제품 교환' },
  { value: 'full_refund', label: '반품 후 전액 환불' },
  { value: 'partial_refund', label: '일부 금액 환불' },
] as const;

const REASONS = [
  { value: 'change_mind', label: '단순변심' },
  { value: 'size_color', label: '사이즈·색상 불일치' },
  { value: 'defective', label: '제품불량' },
  { value: 'wrong_delivery', label: '오배송' },
  { value: 'other', label: '기타' },
] as const;

const TOTAL_STEPS = 4;

function stepBorder(currentStep: number, thisStep: number): string {
  if (thisStep === currentStep) return `2px solid ${C.green}`;
  if (thisStep < currentStep) return `1px solid ${C.border}`;
  return `1px solid ${C.border}`;
}

function stepOpacity(currentStep: number, thisStep: number): number {
  if (thisStep < currentStep) return 1;
  if (thisStep === currentStep) return 1;
  return 0.4;
}

function StepLabel({ step, currentStep, label }: { step: number; currentStep: number; label: string }) {
  const done = step < currentStep;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <span style={{
        width: 20, height: 20, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 10, fontWeight: 700,
        background: done ? 'rgba(0,230,118,0.15)' : step === currentStep ? 'rgba(0,230,118,0.1)' : 'rgba(255,255,255,0.04)',
        color: done ? C.green : step === currentStep ? C.green : C.textDim,
        border: done ? `1px solid ${C.green}44` : step === currentStep ? `1px solid ${C.green}66` : `1px solid ${C.border}`,
      }}>
        {done ? '✓' : step + 1}
      </span>
      <span style={{ fontSize: 12, fontWeight: 700, color: done ? C.green : step === currentStep ? C.text : C.textDim }}>
        {label} {done && '✅'}
      </span>
    </div>
  );
}

export default function ReturnRequestModal({ isOpen, onClose, order }: ReturnRequestModalProps) {
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);

  const [requestType, setRequestType] = useState('');
  const [reason, setReason] = useState('');
  const [detail, setDetail] = useState('');
  const [evidenceUrl, setEvidenceUrl] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!user) return;
    if (!requestType) { showToast('요청 유형을 선택해주세요', 'error'); return; }
    if (!reason) { showToast('사유를 선택해주세요', 'error'); return; }

    setSubmitting(true);
    try {
      await apiClient.post(`/v3/orders/${order.order_number}/return-request`, {
        buyer_id: user.id,
        reservation_id: order.reservation_id,
        seller_id: order.seller_id,
        request_type: requestType,
        reason,
        detail: detail.trim(),
        evidence_url: evidenceUrl.trim() || undefined,
      });
      showToast('교환/반품 요청이 접수되었습니다', 'success');
      onClose();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '요청 실패', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = !!requestType && !!reason;

  return (
    <>
      {/* Overlay */}
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000 }} />

      {/* Modal */}
      <div style={{
        position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: '92%', maxWidth: 420, background: '#1a1a2e', border: `1px solid ${C.border}`,
        borderRadius: 20, padding: '24px 20px', zIndex: 3001, maxHeight: '85vh', overflowY: 'auto',
      }}>
        <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 4 }}>교환/반품 요청</div>
        <div style={{ fontSize: 12, color: C.textSec, marginBottom: 16 }}>
          주문번호 {order.order_number} · {order.amount.toLocaleString('ko-KR')}원
        </div>

        {/* Progress */}
        <div style={{ display: 'flex', gap: 3, marginBottom: 16 }}>
          {Array.from({ length: TOTAL_STEPS }, (_, i) => (
            <div key={i} style={{
              flex: 1, height: 3, borderRadius: 2,
              background: i <= currentStep ? C.green : 'rgba(255,255,255,0.08)',
            }} />
          ))}
        </div>

        {/* Step 0: Request Type */}
        <div style={{
          marginBottom: 12, padding: '12px', borderRadius: 12,
          border: stepBorder(currentStep, 0),
          opacity: stepOpacity(currentStep, 0),
          pointerEvents: currentStep < 0 ? 'none' as const : 'auto' as const,
          transition: 'all 0.3s',
        }}>
          <StepLabel step={0} currentStep={currentStep} label="요청 유형" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {REQUEST_TYPES.map(t => (
              <button key={t.value} onClick={() => {
                setRequestType(t.value);
                if (currentStep === 0) setCurrentStep(1);
              }} style={{
                padding: '9px 12px', borderRadius: 8, fontSize: 12, textAlign: 'left', cursor: 'pointer',
                background: requestType === t.value ? 'rgba(0,230,118,0.08)' : C.bgEl,
                border: `1px solid ${requestType === t.value ? C.green : C.border}`,
                color: requestType === t.value ? C.green : C.textSec,
                fontWeight: requestType === t.value ? 700 : 400,
              }}>{t.label}</button>
            ))}
          </div>
        </div>

        {/* Step 1: Reason */}
        <div style={{
          marginBottom: 12, padding: '12px', borderRadius: 12,
          border: stepBorder(currentStep, 1),
          opacity: stepOpacity(currentStep, 1),
          pointerEvents: currentStep < 1 ? 'none' as const : 'auto' as const,
          transition: 'all 0.3s',
        }}>
          <StepLabel step={1} currentStep={currentStep} label="사유 선택" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {REASONS.map(r => (
              <button key={r.value} onClick={() => {
                setReason(r.value);
                if (currentStep === 1) setCurrentStep(2);
              }} style={{
                padding: '9px 12px', borderRadius: 8, fontSize: 12, textAlign: 'left', cursor: 'pointer',
                background: reason === r.value ? 'rgba(0,230,118,0.08)' : C.bgEl,
                border: `1px solid ${reason === r.value ? C.green : C.border}`,
                color: reason === r.value ? C.green : C.textSec,
                fontWeight: reason === r.value ? 700 : 400,
              }}>{r.label}</button>
            ))}
          </div>
        </div>

        {/* Step 2: Detail */}
        <div style={{
          marginBottom: 12, padding: '12px', borderRadius: 12,
          border: stepBorder(currentStep, 2),
          opacity: stepOpacity(currentStep, 2),
          pointerEvents: currentStep < 2 ? 'none' as const : 'auto' as const,
          transition: 'all 0.3s',
        }}>
          <StepLabel step={2} currentStep={currentStep} label="상세 설명" />
          <textarea
            value={detail}
            onChange={e => setDetail(e.target.value)}
            onBlur={() => { if (currentStep === 2) setCurrentStep(3); }}
            placeholder="상세한 사유를 입력해주세요 (선택)"
            style={{
              width: '100%', boxSizing: 'border-box', minHeight: 70, padding: '10px 12px',
              borderRadius: 8, fontSize: 12, background: C.bgEl,
              border: `1px solid ${C.border}`, color: C.text, resize: 'vertical',
            }}
          />
          {currentStep === 2 && (
            <button onClick={() => setCurrentStep(3)} style={{
              marginTop: 6, padding: '6px 12px', borderRadius: 6, fontSize: 11, fontWeight: 700,
              background: 'rgba(0,230,118,0.12)', border: `1px solid ${C.green}44`,
              color: C.green, cursor: 'pointer',
            }}>다음 →</button>
          )}
        </div>

        {/* Step 3: Evidence URL */}
        <div style={{
          marginBottom: 16, padding: '12px', borderRadius: 12,
          border: stepBorder(currentStep, 3),
          opacity: stepOpacity(currentStep, 3),
          pointerEvents: currentStep < 3 ? 'none' as const : 'auto' as const,
          transition: 'all 0.3s',
        }}>
          <StepLabel step={3} currentStep={currentStep} label="증거 자료 (선택)" />
          <input
            value={evidenceUrl}
            onChange={e => setEvidenceUrl(e.target.value)}
            placeholder="증거 이미지/문서 URL"
            style={{
              width: '100%', boxSizing: 'border-box', padding: '10px 12px',
              borderRadius: 8, fontSize: 12, background: C.bgEl,
              border: `1px solid ${C.border}`, color: C.text,
            }}
          />
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={onClose} style={{
            flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700,
            background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer',
          }}>닫기</button>
          <button
            onClick={() => void handleSubmit()}
            disabled={!canSubmit || submitting}
            style={{
              flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700,
              background: canSubmit && !submitting ? C.green : 'rgba(0,230,118,0.2)',
              border: 'none', color: canSubmit ? '#0a0a0f' : C.textDim,
              cursor: canSubmit && !submitting ? 'pointer' : 'not-allowed',
            }}
          >{submitting ? '처리 중...' : '요청하기'}</button>
        </div>
      </div>
    </>
  );
}
