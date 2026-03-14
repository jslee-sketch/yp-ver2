import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { refundPreview, refundReservation } from '../api/reservationApi';
import { showToast } from '../components/common/Toast';
import { trackBehavior } from '../utils/behaviorTracker';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

function fmtP(n: number) { return '₩' + (n ?? 0).toLocaleString('ko-KR'); }
function fmtDate(s?: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

interface RefundReservation {
  id: number;
  deal_id: number;
  offer_id: number;
  buyer_id: number;
  qty: number;
  amount_total: number;
  status: string;
  refunded_qty?: number;
  refunded_amount_total?: number;
  is_disputed?: boolean;
  created_at: string;
  cancelled_at?: string;
  reason?: string;
  refund_reason?: string;
  order_number?: string;
  deal?: { product_name?: string };
  buyer?: { nickname?: string; name?: string };
}

type ViewFilter = '전체' | '환불요청' | '완료' | '분쟁중';

export default function SellerRefundsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [items, setItems] = useState<RefundReservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<ViewFilter>('전체');

  // Refund agree modal
  const [agreeTarget, setAgreeTarget] = useState<RefundReservation | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [refundLoading, setRefundLoading] = useState(false);

  // Disagree modal
  const [disagreeTarget, setDisagreeTarget] = useState<RefundReservation | null>(null);
  const [disagreeReason, setDisagreeReason] = useState('');
  const [disputeLoading, setDisputeLoading] = useState(false);

  const sellerId = user?.seller?.id ?? user?.id ?? 0;

  // ── 행동 수집: SELLER_VIEW_REFUND ──
  useEffect(() => {
    trackBehavior('SELLER_VIEW_REFUND', { meta: { page: 'refunds' } });
  }, []);

  useEffect(() => {
    if (!sellerId) return;
    (async () => {
      try {
        const res = await apiClient.get(API.RESERVATIONS.LIST_SELLER(sellerId));
        const all: RefundReservation[] = Array.isArray(res.data) ? res.data : [];
        // Filter: cancelled (refunded) OR disputed OR has refunded amounts
        const refundRelated = all.filter(r =>
          r.status === 'CANCELLED' || r.is_disputed || (r.refunded_qty && r.refunded_qty > 0)
        );
        setItems(refundRelated);
      } catch (err) {
        console.error('환불 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [sellerId]);

  const getRefundStatus = (r: RefundReservation) => {
    if (r.is_disputed) return '분쟁중';
    if (r.status === 'CANCELLED') return '완료';
    if (r.refunded_qty && r.refunded_qty > 0) return '완료';
    return '환불요청';
  };

  const filtered = filter === '전체' ? items : items.filter(r => getRefundStatus(r) === filter);

  const handleAgreeOpen = async (r: RefundReservation) => {
    setAgreeTarget(r);
    setPreviewLoading(true);
    try {
      const data = await refundPreview(r.id, 'buyer_cancel');
      setPreview(data as Record<string, unknown>);
    } catch {
      setPreview(null);
    }
    setPreviewLoading(false);
  };

  const handleAgreeConfirm = async () => {
    if (!agreeTarget) return;
    setRefundLoading(true);
    try {
      await refundReservation(agreeTarget.id, '판매자 동의 환불', 'SELLER');
      setItems(prev => prev.map(r => r.id === agreeTarget.id ? { ...r, status: 'CANCELLED' } : r));
      setAgreeTarget(null);
      showToast('환불 처리 완료', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '환불 처리 실패', 'error');
    }
    setRefundLoading(false);
  };

  const handleDisagreeSubmit = async () => {
    if (!disagreeTarget || !disagreeReason.trim()) return;
    setDisputeLoading(true);
    try {
      await apiClient.post(API.RESERVATIONS_V36.DISPUTE_OPEN(disagreeTarget.id), {
        reason: disagreeReason,
      });
      setItems(prev => prev.map(r => r.id === disagreeTarget.id ? { ...r, is_disputed: true } : r));
      setDisagreeTarget(null);
      setDisagreeReason('');
      showToast('분쟁으로 전환되었습니다', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '분쟁 전환 실패', 'error');
    }
    setDisputeLoading(false);
  };

  const statusColor: Record<string, string> = {
    '환불요청': '#ff9100',
    '완료': '#78909c',
    '분쟁중': '#ff5252',
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>환불 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 필터 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {(['전체', '환불요청', '완료', '분쟁중'] as ViewFilter[]).map(s => (
            <button key={s} onClick={() => setFilter(s)} style={{
              padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: filter === s ? `${C.green}22` : C.bgEl,
              border: `1px solid ${filter === s ? C.green : C.border}`,
              color: filter === s ? C.green : C.textSec,
              fontWeight: filter === s ? 700 : 400,
            }}>{s}</button>
          ))}
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>{filtered.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>↩️</div>
            <div style={{ fontSize: 13 }}>환불 내역이 없어요</div>
          </div>
        ) : filtered.map(r => {
          const st = getRefundStatus(r);
          const clr = statusColor[st] ?? C.textDim;
          return (
            <div key={r.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${clr}`,
              borderRadius: 14, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: C.textSec }}>
                  주문 {r.order_number || `#${r.id}`} · 딜 #{r.deal_id}
                </span>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                  background: `${clr}22`, color: clr,
                }}>{st}</span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 4 }}>
                {r.deal?.product_name ?? `주문 ${r.order_number || '#' + r.id}`}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 6 }}>
                <div><div style={{ fontSize: 10, color: C.textDim }}>결제액</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{fmtP(r.amount_total)}</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>환불액</div><div style={{ fontSize: 12, fontWeight: 700, color: '#ff5252' }}>{fmtP(r.refunded_amount_total ?? 0)}</div></div>
              </div>
              <div style={{ fontSize: 10, color: C.textDim, marginBottom: 6 }}>
                구매자 #{r.buyer_id}{r.buyer?.nickname ? ` (${r.buyer.nickname})` : ''} · {fmtDate(r.created_at)}
              </div>

              {(r.reason || r.refund_reason) && (
                <div style={{
                  borderLeft: '3px solid #ff9100',
                  background: 'rgba(255,145,0,0.06)',
                  borderRadius: '0 8px 8px 0',
                  padding: '8px 12px',
                  marginBottom: 6,
                }}>
                  <div style={{ fontSize: 10, color: C.textDim, marginBottom: 2 }}>환불 사유</div>
                  <div style={{ fontSize: 12, color: C.text, fontStyle: 'italic', lineHeight: 1.5 }}>
                    {r.reason ?? r.refund_reason}
                  </div>
                </div>
              )}

              {st === '환불요청' && (
                <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
                  <button onClick={() => void handleAgreeOpen(r)}
                    style={{ flex: 1, padding: '7px 0', borderRadius: 8, fontSize: 12, fontWeight: 700, background: `${C.green}18`, border: `1px solid ${C.green}44`, color: C.green, cursor: 'pointer' }}>
                    동의
                  </button>
                  <button onClick={() => { setDisagreeTarget(r); setDisagreeReason(''); }}
                    style={{ flex: 1, padding: '7px 0', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', color: '#ff5252', cursor: 'pointer' }}>
                    미동의
                  </button>
                </div>
              )}

              {st === '분쟁중' && (
                <div style={{ fontSize: 11, color: '#ff5252', marginTop: 6 }}>
                  관리자 처리 대기 중
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 동의 모달 */}
      {agreeTarget && (
        <>
          <div onClick={() => setAgreeTarget(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000 }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: '92%', maxWidth: 400, background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 20, padding: '24px 20px', zIndex: 3001 }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 4 }}>환불 동의</div>
            <div style={{ fontSize: 12, color: C.textSec, marginBottom: 16 }}>주문 {agreeTarget.order_number || `#${agreeTarget.id}`}</div>
            {previewLoading ? (
              <div style={{ textAlign: 'center', padding: '20px 0', color: C.textDim }}>미리보기 로딩...</div>
            ) : preview ? (
              <div style={{ background: C.bgEl, border: `1px solid ${C.border}`, borderRadius: 12, padding: 14, marginBottom: 16 }}>
                <div style={{ fontSize: 12, color: C.textDim, marginBottom: 8 }}>환불 프리뷰</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
                  결제액: {fmtP(agreeTarget.amount_total)}
                </div>
              </div>
            ) : null}
            <div style={{ fontSize: 13, color: C.textSec, marginBottom: 16 }}>
              환불에 동의하시겠어요? 정산에서 차감됩니다.
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setAgreeTarget(null)} style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>취소</button>
              <button disabled={refundLoading} onClick={() => void handleAgreeConfirm()}
                style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: refundLoading ? `${C.green}55` : C.green, border: 'none', color: '#0a0a0f', cursor: refundLoading ? 'not-allowed' : 'pointer' }}>
                {refundLoading ? '처리 중...' : '동의'}
              </button>
            </div>
          </div>
        </>
      )}

      {/* 미동의 모달 */}
      {disagreeTarget && (
        <>
          <div onClick={() => setDisagreeTarget(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000 }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: '92%', maxWidth: 400, background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 20, padding: '24px 20px', zIndex: 3001 }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 4 }}>환불 미동의</div>
            <div style={{ fontSize: 12, color: C.textSec, marginBottom: 16 }}>주문 {disagreeTarget.order_number || `#${disagreeTarget.id}`}</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>미동의 사유</div>
            <textarea
              value={disagreeReason} onChange={e => setDisagreeReason(e.target.value)}
              placeholder="미동의 사유를 입력해주세요"
              rows={3}
              style={{ width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: 10, fontSize: 13, background: C.bgEl, border: `1px solid ${C.border}`, color: C.text, resize: 'none', marginBottom: 12 }}
            />
            <div style={{ fontSize: 11, color: '#ff9100', marginBottom: 16, lineHeight: 1.5 }}>
              분쟁으로 전환됩니다. 관리자가 중재합니다.
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setDisagreeTarget(null)} style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>취소</button>
              <button disabled={disputeLoading || !disagreeReason.trim()} onClick={() => void handleDisagreeSubmit()}
                style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: disputeLoading ? 'rgba(255,82,82,0.3)' : '#ff5252', border: 'none', color: '#fff', cursor: disputeLoading || !disagreeReason.trim() ? 'not-allowed' : 'pointer' }}>
                {disputeLoading ? '처리 중...' : '분쟁 전환'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
