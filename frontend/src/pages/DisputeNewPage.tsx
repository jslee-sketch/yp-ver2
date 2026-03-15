import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import { showToast } from '../components/common/Toast';

/* ── 타입 ── */
interface OrderInfo {
  order_number: string;
  reservation_id: number;
  product_name: string;
  seller_id: number;
  seller_name: string;
  amount_total: number;
  status: string;
}

interface RejectedCSRequest {
  id: number;
  request_type: string;
  reason: string;
  status: string;
  created_at: string;
}

/* ── 상수 ── */
const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: '#00e676', red: '#ff5252', orange: '#ff8c42',
};

const RESOLUTION_OPTIONS = [
  { value: 'refund', label: '전액 환불' },
  { value: 'partial_refund', label: '부분 환불' },
  { value: 'exchange', label: '교환' },
] as const;

const TOTAL_STEPS = 6;

function fmtPrice(n: number) { return n.toLocaleString('ko-KR') + '원'; }

/** F-019 sequential highlight helper */
function stepStyle(currentStep: number, thisStep: number): React.CSSProperties {
  if (thisStep < currentStep) {
    // completed
    return { opacity: 1 };
  }
  if (thisStep === currentStep) {
    // active
    return { opacity: 1 };
  }
  // future
  return { opacity: 0.4, pointerEvents: 'none' as const };
}

function stepBorder(currentStep: number, thisStep: number): string {
  // Container never gets green border — only input elements get green glow via CSS class
  if (thisStep < currentStep) return `1px solid ${C.border}`;
  return `1px solid ${C.border}`;
}

function StepLabel({ step, currentStep, label }: { step: number; currentStep: number; label: string }) {
  const done = step < currentStep;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <span style={{
        width: 22, height: 22, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 11, fontWeight: 700,
        background: done ? 'rgba(0,230,118,0.15)' : step === currentStep ? 'rgba(0,230,118,0.1)' : 'rgba(255,255,255,0.04)',
        color: done ? C.green : step === currentStep ? C.green : C.textDim,
        border: done ? `1px solid ${C.green}44` : step === currentStep ? `1px solid ${C.green}66` : `1px solid ${C.border}`,
      }}>
        {done ? '✓' : step + 1}
      </span>
      <span style={{ fontSize: 13, fontWeight: 700, color: done ? C.green : step === currentStep ? C.text : C.textDim }}>
        {label} {done && '✅'}
      </span>
    </div>
  );
}

export default function DisputeNewPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  // Step tracking
  const [currentStep, setCurrentStep] = useState(0);
  const fieldCls = (step: number) =>
    step < currentStep ? 'field-completed' : step === currentStep ? 'field-active' : 'field-pending';

  // Step 0: Order search
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [orderInfo, setOrderInfo] = useState<OrderInfo | null>(null);
  const [rejectedRequests, setRejectedRequests] = useState<RejectedCSRequest[]>([]);
  const [searchError, setSearchError] = useState('');

  // Step 2: Claim
  const [claimText, setClaimText] = useState('');

  // Step 3: Evidence
  const [evidenceUrl, setEvidenceUrl] = useState('');

  // Step 4: Compensation
  const [compensationType, setCompensationType] = useState<'fixed' | 'percentage'>('fixed');
  const [compensationAmount, setCompensationAmount] = useState('');
  const compensationValue = compensationType === 'percentage' && orderInfo
    ? Math.round((orderInfo.amount_total * (parseFloat(compensationAmount) || 0)) / 100)
    : parseFloat(compensationAmount) || 0;

  // Step 5: Resolution
  const [resolution, setResolution] = useState('');

  // Submit
  const [submitting, setSubmitting] = useState(false);

  /* ── 주문 검색 ── */
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchError('');
    setOrderInfo(null);
    setRejectedRequests([]);
    try {
      const res = await apiClient.get('/v3/orders/search', { params: { order_number: searchQuery.trim(), buyer_id: user?.id } });
      const data = res.data as Record<string, unknown>;
      if (!data || !data.order_number) {
        setSearchError('주문을 찾을 수 없습니다');
        return;
      }
      setOrderInfo({
        order_number: String(data.order_number),
        reservation_id: data.reservation_id as number,
        product_name: String(data.product_name ?? ''),
        seller_id: data.seller_id as number,
        seller_name: String(data.seller_name ?? ''),
        amount_total: (data.amount_total as number) || 0,
        status: String(data.status ?? ''),
      });
      const rejected = (data.rejected_cs_requests as RejectedCSRequest[]) ?? [];
      setRejectedRequests(rejected);
      if (rejected.length === 0) {
        setSearchError('이 주문에 거절된 CS 요청이 없습니다. 중재를 신청하려면 먼저 교환/반품 요청이 거절되어야 합니다.');
        return;
      }
      setCurrentStep(1);
    } catch {
      setSearchError('주문 검색에 실패했습니다');
    } finally {
      setSearching(false);
    }
  };

  /* ── 제출 ── */
  const handleSubmit = async () => {
    if (!user || !orderInfo) return;
    if (!claimText.trim()) { showToast('변론 내용을 입력해주세요', 'error'); return; }
    if (!compensationAmount || compensationValue <= 0) { showToast('보상 금액을 입력해주세요', 'error'); return; }
    if (!resolution) { showToast('희망 처리 방법을 선택해주세요', 'error'); return; }

    setSubmitting(true);
    try {
      const body = {
        initiator_id: user.id,
        initiator_role: 'buyer',
        reservation_id: orderInfo.reservation_id,
        order_number: orderInfo.order_number,
        respondent_id: orderInfo.seller_id,
        category: 'buyer_change_mind',
        description: claimText.trim(),
        evidence: evidenceUrl.trim() ? [{ type: 'url', url: evidenceUrl.trim(), description: '' }] : [],
        requested_resolution: resolution,
        requested_amount: compensationValue,
        initiator_amount_type: compensationType,
        initiator_amount_value: parseFloat(compensationAmount) || 0,
      };
      const res = await apiClient.post('/v3/disputes', body);
      const created = res.data as Record<string, unknown>;
      showToast('중재가 신청되었습니다', 'success');
      navigate(`/disputes/${created.id}`);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '중재 신청 실패', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // Determine effective step based on filled data
  const canProceedStep1 = !!orderInfo && rejectedRequests.length > 0;
  const canProceedStep2 = canProceedStep1 && claimText.trim().length > 0;
  const canProceedStep3 = canProceedStep2; // evidence is optional
  const canProceedStep4 = canProceedStep3 && compensationAmount !== '' && compensationValue > 0;
  const canProceedStep5 = canProceedStep4 && !!resolution;

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      {/* Header */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', background: 'none', border: 'none' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>중재 신청</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ maxWidth: 600, margin: '0 auto', padding: '16px 16px 40px' }}>

        {/* Progress */}
        <div style={{ display: 'flex', gap: 4, marginBottom: 20 }}>
          {Array.from({ length: TOTAL_STEPS }, (_, i) => (
            <div key={i} style={{
              flex: 1, height: 3, borderRadius: 2,
              background: i <= currentStep ? C.green : 'rgba(255,255,255,0.08)',
              transition: 'background 0.3s',
            }} />
          ))}
        </div>

        {/* ── Step 0: Order Search ── */}
        <div style={{ ...stepStyle(currentStep, 0), marginBottom: 16 }}>
          <div style={{
            background: C.bgCard, borderRadius: 14, padding: '16px 14px',
            border: stepBorder(currentStep, 0),
            transition: 'border 0.3s, opacity 0.3s',
          }}>
            <StepLabel step={0} currentStep={currentStep} label="주문번호 검색" />
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className={fieldCls(0)}
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') void handleSearch(); }}
                placeholder="주문번호를 입력하세요"
                style={{
                  flex: 1, padding: '10px 14px', borderRadius: 10, fontSize: 13,
                  background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
                }}
              />
              <button
                onClick={() => void handleSearch()}
                disabled={searching || !searchQuery.trim()}
                style={{
                  padding: '10px 16px', borderRadius: 10, fontSize: 13, fontWeight: 700,
                  background: searching ? 'rgba(0,230,118,0.05)' : 'rgba(0,230,118,0.12)',
                  border: `1px solid ${C.green}44`, color: C.green, cursor: 'pointer',
                }}
              >
                {searching ? '검색 중...' : '검색'}
              </button>
            </div>
            {searchError && (
              <div style={{ fontSize: 12, color: C.red, marginTop: 8 }}>{searchError}</div>
            )}
          </div>
        </div>

        {/* ── Step 1: Search Result ── */}
        {canProceedStep1 && (
          <div style={{ ...stepStyle(currentStep, 1), marginBottom: 16 }}>
            <div style={{
              background: C.bgCard, borderRadius: 14, padding: '16px 14px',
              border: stepBorder(currentStep, 1),
              transition: 'border 0.3s, opacity 0.3s',
            }}>
              <StepLabel step={1} currentStep={currentStep} label="주문 정보 확인" />

              {/* Order info card */}
              <div style={{
                background: C.bgEl, borderRadius: 10, padding: '12px 14px', marginBottom: 12,
                border: `1px solid ${C.border}`,
              }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 4 }}>
                  {orderInfo!.product_name}
                </div>
                <div style={{ fontSize: 11, color: C.textSec }}>
                  주문번호: {orderInfo!.order_number} · {orderInfo!.seller_name} · {fmtPrice(orderInfo!.amount_total)}
                </div>
              </div>

              {/* Rejected CS requests */}
              <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>거절된 CS 요청</div>
              {rejectedRequests.map(req => (
                <div key={req.id} style={{
                  padding: '8px 10px', borderRadius: 8, marginBottom: 4,
                  background: 'rgba(255,82,82,0.05)', border: '1px solid rgba(255,82,82,0.15)',
                }}>
                  <div style={{ fontSize: 12, color: C.text }}>
                    {req.request_type === 'exchange' ? '교환' : req.request_type === 'return' ? '반품' : req.request_type} — {req.reason}
                  </div>
                  <div style={{ fontSize: 10, color: C.red }}>거절됨 · {req.created_at?.split('T')[0]}</div>
                </div>
              ))}

              {currentStep === 1 && (
                <button
                  onClick={() => setCurrentStep(2)}
                  style={{
                    marginTop: 8, padding: '8px 16px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                    background: 'rgba(0,230,118,0.12)', border: `1px solid ${C.green}44`,
                    color: C.green, cursor: 'pointer',
                  }}
                >
                  확인 → 다음
                </button>
              )}
            </div>
          </div>
        )}

        {/* ── Step 2: Claim ── */}
        {canProceedStep1 && (
          <div style={{ ...stepStyle(currentStep, 2), marginBottom: 16 }}>
            <div style={{
              background: C.bgCard, borderRadius: 14, padding: '16px 14px',
              border: stepBorder(currentStep, 2),
              transition: 'border 0.3s, opacity 0.3s',
            }}>
              <StepLabel step={2} currentStep={currentStep} label="변론 내용" />
              <textarea
                className={fieldCls(2)}
                value={claimText}
                onChange={e => {
                  if (e.target.value.length <= 2000) setClaimText(e.target.value);
                }}
                onBlur={() => { if (claimText.trim() && currentStep === 2) setCurrentStep(3); }}
                placeholder="분쟁 사유를 상세히 작성해주세요 (최대 2000자)"
                style={{
                  width: '100%', boxSizing: 'border-box', minHeight: 100, padding: '10px 14px',
                  borderRadius: 10, fontSize: 13, background: C.bgEl,
                  border: `1px solid ${C.border}`, color: C.text, resize: 'vertical',
                }}
              />
              <div style={{ fontSize: 10, color: C.textDim, textAlign: 'right', marginTop: 4 }}>
                {claimText.length} / 2000
              </div>
            </div>
          </div>
        )}

        {/* ── Step 3: Evidence ── */}
        {canProceedStep2 && (
          <div style={{ ...stepStyle(currentStep, 3), marginBottom: 16 }}>
            <div style={{
              background: C.bgCard, borderRadius: 14, padding: '16px 14px',
              border: stepBorder(currentStep, 3),
              transition: 'border 0.3s, opacity 0.3s',
            }}>
              <StepLabel step={3} currentStep={currentStep} label="증거 자료 (선택)" />
              <input
                className={fieldCls(3)}
                value={evidenceUrl}
                onChange={e => setEvidenceUrl(e.target.value)}
                onBlur={() => { if (currentStep === 3) setCurrentStep(4); }}
                placeholder="증거 파일 URL을 입력하세요 (이미지/문서 링크)"
                style={{
                  width: '100%', boxSizing: 'border-box', padding: '10px 14px',
                  borderRadius: 10, fontSize: 13, background: C.bgEl,
                  border: `1px solid ${C.border}`, color: C.text,
                }}
              />
              <div style={{ fontSize: 10, color: C.textDim, marginTop: 4 }}>
                선택사항입니다. 건너뛰려면 다음 단계로 이동하세요.
              </div>
              {currentStep === 3 && (
                <button
                  onClick={() => setCurrentStep(4)}
                  style={{
                    marginTop: 8, padding: '8px 16px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                    background: 'rgba(0,230,118,0.12)', border: `1px solid ${C.green}44`,
                    color: C.green, cursor: 'pointer',
                  }}
                >
                  다음 →
                </button>
              )}
            </div>
          </div>
        )}

        {/* ── Step 4: Compensation ── */}
        {canProceedStep3 && (
          <div style={{ ...stepStyle(currentStep, 4), marginBottom: 16 }}>
            <div style={{
              background: C.bgCard, borderRadius: 14, padding: '16px 14px',
              border: stepBorder(currentStep, 4),
              transition: 'border 0.3s, opacity 0.3s',
            }}>
              <StepLabel step={4} currentStep={currentStep} label="요구 보상 금액" />

              {/* Type radio */}
              <div style={{ display: 'flex', gap: 6, marginBottom: 10 }}>
                {([['fixed', '정액'], ['percentage', '비율(%)']] as const).map(([val, label]) => (
                  <button key={val} onClick={() => { setCompensationType(val); setCompensationAmount(''); }} style={{
                    flex: 1, padding: '8px 0', borderRadius: 8, fontSize: 12, fontWeight: compensationType === val ? 700 : 400,
                    cursor: 'pointer',
                    background: compensationType === val ? 'rgba(0,230,118,0.1)' : C.bgEl,
                    border: `1px solid ${compensationType === val ? C.green : C.border}`,
                    color: compensationType === val ? C.green : C.textSec,
                  }}>{label}</button>
                ))}
              </div>

              <input
                className={fieldCls(4)}
                type="number"
                value={compensationAmount}
                onChange={e => {
                  setCompensationAmount(e.target.value);
                  if (e.target.value && parseFloat(e.target.value) > 0 && currentStep === 4) {
                    setCurrentStep(5);
                  }
                }}
                placeholder={compensationType === 'fixed' ? '금액 (원)' : '비율 (%)'}
                style={{
                  width: '100%', boxSizing: 'border-box', padding: '10px 14px',
                  borderRadius: 10, fontSize: 13, background: C.bgEl,
                  border: `1px solid ${C.border}`, color: C.text,
                }}
              />

              {compensationType === 'percentage' && compensationAmount && orderInfo && (
                <div style={{
                  marginTop: 6, padding: '6px 10px', borderRadius: 8,
                  background: 'rgba(0,230,118,0.06)', fontSize: 12, color: C.green,
                }}>
                  계산 금액: {fmtPrice(compensationValue)} ({orderInfo.amount_total.toLocaleString('ko-KR')}원의 {compensationAmount}%)
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Step 5: Resolution ── */}
        {canProceedStep4 && (
          <div style={{ ...stepStyle(currentStep, 5), marginBottom: 16 }}>
            <div style={{
              background: C.bgCard, borderRadius: 14, padding: '16px 14px',
              border: stepBorder(currentStep, 5),
              transition: 'border 0.3s, opacity 0.3s',
            }}>
              <StepLabel step={5} currentStep={currentStep} label="희망 처리 방법" />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {RESOLUTION_OPTIONS.map(opt => (
                  <button key={opt.value} onClick={() => setResolution(opt.value)} style={{
                    padding: '10px 14px', borderRadius: 10, fontSize: 13, textAlign: 'left',
                    cursor: 'pointer',
                    background: resolution === opt.value ? 'rgba(0,230,118,0.08)' : C.bgEl,
                    border: `1px solid ${resolution === opt.value ? C.green : C.border}`,
                    color: resolution === opt.value ? C.green : C.textSec,
                    fontWeight: resolution === opt.value ? 700 : 400,
                  }}>{opt.label}</button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Submit ── */}
        <button
          onClick={() => void handleSubmit()}
          disabled={!canProceedStep5 || submitting}
          style={{
            width: '100%', padding: '14px', borderRadius: 12, fontSize: 15, fontWeight: 800,
            cursor: canProceedStep5 && !submitting ? 'pointer' : 'not-allowed',
            background: canProceedStep5 ? C.green : 'rgba(255,255,255,0.06)',
            border: 'none',
            color: canProceedStep5 ? '#0a0a0f' : C.textDim,
            opacity: canProceedStep5 ? 1 : 0.4,
            transition: 'all 0.3s',
          }}
        >
          {submitting ? '제출 중...' : '중재 신청하기'}
        </button>
      </div>
    </div>
  );
}
