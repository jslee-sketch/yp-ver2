import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import apiClient from '../../api/client';
import { showToast } from '../common/Toast';

/* ── 타입 ── */
interface OrderItem {
  id: number;
  name: string;
  qty: number;
  price: number;
}

interface OrderData {
  order_number: string;
  items?: OrderItem[];
  amount: number;
  reservation_id: number;
  seller_id?: number;
}

interface CancelOrderModalProps {
  isOpen: boolean;
  onClose: () => void;
  order: OrderData;
}

/* ── 상수 ── */
const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: '#00e676', red: '#ff5252',
};

const CANCEL_REASONS = [
  { value: 'change_mind', label: '단순변심' },
  { value: 'duplicate', label: '중복주문' },
  { value: 'other', label: '기타' },
] as const;

const TOTAL_STEPS = 3;

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

export default function CancelOrderModal({ isOpen, onClose, order }: CancelOrderModalProps) {
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);

  const [cancelType, setCancelType] = useState<'full' | 'partial'>('full');
  const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!isOpen) return null;

  const hasItems = order.items && order.items.length > 0;
  const isPartial = cancelType === 'partial';

  const toggleItem = (id: number) => {
    setSelectedItems(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSubmit = async () => {
    if (!user) return;
    if (!reason) { showToast('취소 사유를 선택해주세요', 'error'); return; }
    if (isPartial && hasItems && selectedItems.size === 0) {
      showToast('취소할 상품을 선택해주세요', 'error');
      return;
    }

    setSubmitting(true);
    try {
      await apiClient.post(`/v3/orders/${order.order_number}/cancel`, {
        buyer_id: user.id,
        reservation_id: order.reservation_id,
        cancel_type: cancelType,
        item_ids: isPartial ? Array.from(selectedItems) : undefined,
        reason,
      });
      showToast('취소 요청이 완료되었습니다', 'success');
      onClose();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '취소 요청 실패', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = !!reason && (cancelType === 'full' || !hasItems || selectedItems.size > 0);

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
        <div style={{ fontSize: 18, fontWeight: 800, color: C.red, marginBottom: 4 }}>주문 취소</div>
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

        {/* Step 0: Cancel Type */}
        <div style={{
          marginBottom: 12, padding: '12px', borderRadius: 12,
          border: stepBorder(currentStep, 0),
          opacity: stepOpacity(currentStep, 0),
          transition: 'all 0.3s',
        }}>
          <StepLabel step={0} currentStep={currentStep} label="취소 유형" />
          <div style={{ display: 'flex', gap: 6 }}>
            {([['full', '전체 취소'], ['partial', '부분 취소']] as const).map(([val, label]) => (
              <button key={val} onClick={() => {
                setCancelType(val);
                setSelectedItems(new Set());
                if (currentStep === 0) {
                  if (val === 'partial' && hasItems) setCurrentStep(1);
                  else setCurrentStep(2);
                }
              }} style={{
                flex: 1, padding: '9px 0', borderRadius: 8, fontSize: 12, fontWeight: cancelType === val ? 700 : 400,
                cursor: 'pointer',
                background: cancelType === val ? 'rgba(255,82,82,0.1)' : C.bgEl,
                border: `1px solid ${cancelType === val ? C.red : C.border}`,
                color: cancelType === val ? C.red : C.textSec,
              }}>{label}</button>
            ))}
          </div>
        </div>

        {/* Step 1: Item selection (partial only) */}
        {isPartial && hasItems && (
          <div style={{
            marginBottom: 12, padding: '12px', borderRadius: 12,
            border: stepBorder(currentStep, 1),
            opacity: stepOpacity(currentStep, 1),
            pointerEvents: currentStep < 1 ? 'none' as const : 'auto' as const,
            transition: 'all 0.3s',
          }}>
            <StepLabel step={1} currentStep={currentStep} label="취소할 상품 선택" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {order.items!.map(item => {
                const checked = selectedItems.has(item.id);
                return (
                  <button key={item.id} onClick={() => {
                    toggleItem(item.id);
                    if (currentStep === 1) setCurrentStep(2);
                  }} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '9px 12px', borderRadius: 8, fontSize: 12, cursor: 'pointer',
                    background: checked ? 'rgba(255,82,82,0.08)' : C.bgEl,
                    border: `1px solid ${checked ? C.red : C.border}`,
                    color: checked ? C.red : C.textSec,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{
                        width: 16, height: 16, borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center',
                        background: checked ? C.red : 'transparent', border: `1px solid ${checked ? C.red : C.border}`,
                        color: '#fff', fontSize: 10,
                      }}>
                        {checked && '✓'}
                      </span>
                      <span>{item.name} x{item.qty}</span>
                    </div>
                    <span style={{ fontWeight: 600 }}>{item.price.toLocaleString('ko-KR')}원</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Step 2: Reason */}
        <div style={{
          marginBottom: 16, padding: '12px', borderRadius: 12,
          border: stepBorder(currentStep, 2),
          opacity: stepOpacity(currentStep, 2),
          pointerEvents: currentStep < 2 ? 'none' as const : 'auto' as const,
          transition: 'all 0.3s',
        }}>
          <StepLabel step={2} currentStep={currentStep} label="취소 사유" />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {CANCEL_REASONS.map(r => (
              <button key={r.value} onClick={() => setReason(r.value)} style={{
                padding: '9px 12px', borderRadius: 8, fontSize: 12, textAlign: 'left', cursor: 'pointer',
                background: reason === r.value ? 'rgba(255,82,82,0.08)' : C.bgEl,
                border: `1px solid ${reason === r.value ? C.red : C.border}`,
                color: reason === r.value ? C.red : C.textSec,
                fontWeight: reason === r.value ? 700 : 400,
              }}>{r.label}</button>
            ))}
          </div>
        </div>

        {/* Warning */}
        <div style={{ fontSize: 11, color: C.textDim, marginBottom: 16, lineHeight: 1.6 }}>
          취소 요청 시 환불 정책에 따라 처리됩니다. 결제 수단에 따라 환불까지 3~5영업일이 소요될 수 있습니다.
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
              background: canSubmit && !submitting ? C.red : 'rgba(255,82,82,0.2)',
              border: 'none', color: canSubmit ? '#fff' : C.textDim,
              cursor: canSubmit && !submitting ? 'pointer' : 'not-allowed',
            }}
          >{submitting ? '처리 중...' : '취소 요청하기'}</button>
        </div>
      </div>
    </>
  );
}
