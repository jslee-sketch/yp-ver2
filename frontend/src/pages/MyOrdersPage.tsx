import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchMyReservations, cancelReservation, confirmArrival, payReservation, refundPreview, refundReservation } from '../api/reservationApi';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { showToast } from '../components/common/Toast';

type ActivityStatus = 'PENDING_PAY' | 'PAID' | 'SHIPPED' | 'DELIVERED' | 'CANCELLED';

interface MyOrder {
  id: number;
  deal_id?: number;
  offer_id?: number;
  product_name: string;
  seller_name?: string;
  price?: number;
  qty: number;
  amount_total: number;
  status: ActivityStatus;
  created_at: string;
  paid_at?: string;
  tracking_number?: string;
  shipping_carrier?: string;
  is_disputed?: boolean;
}

const STATUS_MAP: Record<ActivityStatus, { color: string; label: string; emoji: string }> = {
  PENDING_PAY: { color: '#e040fb', label: '결제대기', emoji: '🟣' },
  PAID:        { color: '#448aff', label: '결제완료', emoji: '🔵' },
  SHIPPED:     { color: '#ff6d00', label: '배송중',  emoji: '📦' },
  DELIVERED:   { color: '#00e676', label: '배송완료', emoji: '🟢' },
  CANCELLED:   { color: '#757575', label: '취소/환불', emoji: '⚫' },
};

const STATUS_FILTERS = ['전체', '결제대기', '결제완료', '배송중', '배송완료', '취소/환불'];
const STATUS_FILTER_MAP: Record<string, ActivityStatus[]> = {
  '전체':     ['PENDING_PAY', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED'],
  '결제대기': ['PENDING_PAY'],
  '결제완료': ['PAID'],
  '배송중':   ['SHIPPED'],
  '배송완료': ['DELIVERED'],
  '취소/환불': ['CANCELLED'],
};
const ITEMS_PER_PAGE = 10;

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

function fmtDate(s: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }
function fmtPrice(n: number) { return n.toLocaleString('ko-KR') + '원'; }

function mapStatus(status: string, r: Record<string, unknown>): ActivityStatus {
  if (status === 'CANCELLED' || status === 'EXPIRED') return 'CANCELLED';
  if (status === 'PENDING') return 'PENDING_PAY';
  if (status === 'PAID') {
    if (r.arrival_confirmed_at || r.delivered_at) return 'DELIVERED';
    if (r.shipped_at) return 'SHIPPED';
    return 'PAID';
  }
  return 'PAID';
}

const REFUND_REASONS = ['단순 변심', '상품 불량/하자', '상품 미수령', '오배송', '기타'];

export default function MyOrdersPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [orders, setOrders] = useState<MyOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('전체');
  const [page, setPage] = useState(1);

  // Refund modal
  const [refundTarget, setRefundTarget] = useState<MyOrder | null>(null);
  const [refundReason, setRefundReason] = useState(REFUND_REASONS[0]);
  const [refundReasonOther, setRefundReasonOther] = useState('');
  const [refundType, setRefundType] = useState<'refund' | 'return' | 'exchange'>('refund');
  const [refundPreviewData, setRefundPreviewData] = useState<Record<string, unknown> | null>(null);
  const [refundLoading, setRefundLoading] = useState(false);

  // Delivery tracking
  const [trackingInfo, setTrackingInfo] = useState<Record<string, unknown> | null>(null);
  const [trackingOrderId, setTrackingOrderId] = useState<number | null>(null);
  const [trackingLoading, setTrackingLoading] = useState(false);

  const handleTrackDelivery = async (orderId: number) => {
    if (trackingOrderId === orderId && trackingInfo) {
      setTrackingOrderId(null);
      setTrackingInfo(null);
      return;
    }
    setTrackingLoading(true);
    setTrackingOrderId(orderId);
    try {
      const resp = await apiClient.get(`/delivery/track/${orderId}`);
      setTrackingInfo(resp.data as Record<string, unknown>);
    } catch {
      setTrackingInfo({ success: false, error: '조회 실패' });
    }
    setTrackingLoading(false);
  };

  // Dispute modal
  const [disputeTarget, setDisputeTarget] = useState<MyOrder | null>(null);
  const [disputeReason, setDisputeReason] = useState('');
  const [disputeLoading, setDisputeLoading] = useState(false);

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    (async () => {
      setLoading(true);
      try {
        const data = await fetchMyReservations(user.id);
        if (data && Array.isArray(data)) {
          setOrders((data as Record<string, unknown>[]).map(r => {
            const deal = r.deal as Record<string, unknown> | undefined;
            const offer = r.offer as Record<string, unknown> | undefined;
            const seller = offer?.seller as Record<string, unknown> | undefined;
            return {
              id: r.id as number,
              deal_id: (r.deal_id as number) || (deal?.id as number) || undefined,
              offer_id: (r.offer_id as number) || undefined,
              product_name: String(deal?.product_name ?? offer?.comment ?? `예약 #${r.id}`),
              seller_name: String(seller?.business_name ?? seller?.nickname ?? ''),
              price: (r.amount_goods as number) || undefined,
              qty: (r.qty as number) || 1,
              amount_total: (r.amount_total as number) || 0,
              status: mapStatus(String(r.status ?? ''), r),
              created_at: String(r.created_at ?? '').split('T')[0],
              paid_at: (r.paid_at as string) || undefined,
              tracking_number: (r.tracking_number as string) || undefined,
              shipping_carrier: (r.shipping_carrier as string) || undefined,
              is_disputed: r.is_disputed === true,
            };
          }));
        }
      } catch (err) {
        console.error('주문 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  const updateStatus = (id: number, status: ActivityStatus) =>
    setOrders(prev => prev.map(o => o.id === id ? { ...o, status } : o));

  const handlePay = async (order: MyOrder) => {
    if (!user) return;
    if (!window.confirm('결제를 진행하시겠어요?\n(테스트 환경: 즉시 결제 처리됩니다)')) return;
    try {
      await payReservation(order.id, user.id, order.amount_total);
      updateStatus(order.id, 'PAID');
      showToast('결제가 완료되었어요!', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '결제 실패', 'error');
    }
  };

  const handleCancel = async (id: number) => {
    if (!window.confirm('정말 취소하시겠어요?')) return;
    try {
      await cancelReservation(id, user!.id);
      updateStatus(id, 'CANCELLED');
      showToast('취소되었어요', 'info');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '취소 실패', 'error');
    }
  };

  const handleConfirmArrival = async (id: number) => {
    if (!window.confirm('상품을 받으셨나요?')) return;
    try {
      await confirmArrival(id, user?.id);
      updateStatus(id, 'DELIVERED');
      showToast('수령 확인 완료!', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '수령확인 실패', 'error');
    }
  };

  const openRefundModal = async (order: MyOrder) => {
    setRefundTarget(order);
    setRefundReason(REFUND_REASONS[0]);
    setRefundReasonOther('');
    setRefundType('refund');
    setRefundPreviewData(null);
    setRefundLoading(true);
    try {
      const preview = await refundPreview(order.id);
      setRefundPreviewData(preview as Record<string, unknown>);
    } catch {
      // preview might fail but we still show the modal
    }
    setRefundLoading(false);
  };

  const handleRefundSubmit = async () => {
    if (!refundTarget) return;
    const reason = refundReason === '기타' ? refundReasonOther : refundReason;
    if (!reason.trim()) { showToast('환불 사유를 입력해주세요', 'error'); return; }
    setRefundLoading(true);
    try {
      await refundReservation(refundTarget.id, reason, 'BUYER', refundType);
      updateStatus(refundTarget.id, 'CANCELLED');
      setRefundTarget(null);
      showToast('환불이 요청되었습니다', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '환불 요청 실패', 'error');
    }
    setRefundLoading(false);
  };

  const handleDisputeOpen = async () => {
    if (!disputeTarget || !user) return;
    if (!disputeReason.trim()) { showToast('분쟁 사유를 입력해주세요', 'error'); return; }
    setDisputeLoading(true);
    try {
      await apiClient.post(API.RESERVATIONS_V36.DISPUTE_OPEN(disputeTarget.id), {
        buyer_id: user.id,
        reason: disputeReason.trim(),
      });
      setOrders(prev => prev.map(o => o.id === disputeTarget.id ? { ...o, is_disputed: true } : o));
      setDisputeTarget(null);
      setDisputeReason('');
      showToast('분쟁이 접수되었습니다', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '분쟁 접수 실패', 'error');
    }
    setDisputeLoading(false);
  };

  const filtered = orders.filter(o => {
    const allow = STATUS_FILTER_MAP[statusFilter] ?? [];
    return allow.includes(o.status);
  });
  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
  const paged = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>내 주문</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 상태 필터 */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
          {STATUS_FILTERS.map(s => (
            <button key={s} onClick={() => { setStatusFilter(s); setPage(1); }} style={{
              padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: statusFilter === s ? `${C.green}22` : C.bgEl,
              border: `1px solid ${statusFilter === s ? C.green : C.border}`,
              color: statusFilter === s ? C.green : C.textSec,
              fontWeight: statusFilter === s ? 700 : 400,
            }}>{s}</button>
          ))}
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>결과 {filtered.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim, fontSize: 13 }}>불러오는 중...</div>
        ) : paged.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>📭</div>
            <div style={{ fontSize: 13 }}>주문 내역이 없어요</div>
          </div>
        ) : paged.map(item => {
          const st = STATUS_MAP[item.status];
          return (
            <div key={item.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${st.color}`,
              borderRadius: 14, padding: '13px 14px', marginBottom: 8,
              opacity: item.status === 'CANCELLED' ? 0.6 : 1,
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  {/* 예약번호 + 연결 번호 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
                    <span
                      onClick={e => { e.stopPropagation(); if (item.deal_id) navigate(`/deal/${item.deal_id}`); }}
                      style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-blue)', background: 'rgba(0,176,255,0.08)', padding: '1px 6px', borderRadius: 4, cursor: 'pointer', textDecoration: 'underline' }}
                    >
                      예약 #{item.id}
                    </span>
                    {item.deal_id && (
                      <span
                        onClick={e => { e.stopPropagation(); navigate(`/deal/${item.deal_id}`); }}
                        style={{ fontSize: 10, fontWeight: 600, color: 'var(--accent-blue)', cursor: 'pointer', textDecoration: 'underline' }}
                      >
                        딜 #{item.deal_id}
                      </span>
                    )}
                    {item.offer_id && (
                      <span
                        onClick={e => { e.stopPropagation(); if (item.deal_id) navigate(`/deal/${item.deal_id}`); }}
                        style={{ fontSize: 10, color: 'var(--accent-blue)', cursor: 'pointer', textDecoration: 'underline' }}
                      >
                        오퍼 #{item.offer_id}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 4 }}>📦 {item.product_name}</div>
                  <div style={{ fontSize: 11, color: C.textSec, marginBottom: 4 }}>
                    {item.seller_name ? `${item.seller_name} · ` : ''}{item.qty}개{item.amount_total > 0 ? ` · ${fmtPrice(item.amount_total)}` : ''}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 8, background: `${st.color}22`, color: st.color, border: `1px solid ${st.color}44` }}>
                      {st.emoji} {st.label}
                    </span>
                    {item.tracking_number && (
                      <span style={{ fontSize: 10, color: 'var(--accent-orange)' }}>🚚 {item.shipping_carrier ? `${item.shipping_carrier} ` : ''}{item.tracking_number}</span>
                    )}
                    {item.is_disputed && (
                      <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 6, background: 'rgba(255,82,82,0.12)', color: '#ff5252', fontWeight: 700 }}>분쟁중</span>
                    )}
                  </div>
                </div>
                <div style={{ fontSize: 10, color: C.textDim, flexShrink: 0, textAlign: 'right' }}>
                  <div>{fmtDate(item.created_at)}</div>
                  {item.paid_at && <div style={{ color: C.green, marginTop: 2 }}>결제 {fmtDate(item.paid_at)}</div>}
                </div>
              </div>

              {/* 결제대기 */}
              {item.status === 'PENDING_PAY' && (
                <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
                  <button onClick={() => void handlePay(item)} style={{ flex: 1, padding: '7px 0', borderRadius: 8, fontSize: 12, fontWeight: 700, background: '#e040fb22', border: '1px solid #e040fb66', color: '#e040fb', cursor: 'pointer' }}>
                    💳 결제하기
                  </button>
                  <button onClick={() => void handleCancel(item.id)} style={{ padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', color: '#ff5252', cursor: 'pointer' }}>
                    취소
                  </button>
                </div>
              )}

              {/* 결제완료 (배송 전) */}
              {item.status === 'PAID' && (
                <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
                  <button onClick={() => void openRefundModal(item)} style={{ padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,152,0,0.1)', border: '1px solid rgba(255,152,0,0.3)', color: '#ff9100', cursor: 'pointer' }}>
                    환불요청
                  </button>
                  {!item.is_disputed && (
                    <button onClick={() => { setDisputeTarget(item); setDisputeReason(''); }} style={{ padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', color: '#ff5252', cursor: 'pointer' }}>
                      ⚠️ 분쟁 신청
                    </button>
                  )}
                </div>
              )}

              {/* 배송중 */}
              {item.status === 'SHIPPED' && (
                <div style={{ marginTop: 8 }}>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {item.tracking_number && (
                      <button onClick={() => void handleTrackDelivery(item.id)} style={{ padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.35)', color: '#3b82f6', cursor: 'pointer' }}>
                        {trackingLoading && trackingOrderId === item.id ? '조회중...' : '🚚 배송 조회'}
                      </button>
                    )}
                    <button onClick={() => void handleConfirmArrival(item.id)} style={{ padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(0,230,118,0.12)', border: '1px solid rgba(0,230,118,0.35)', color: '#00e676', cursor: 'pointer' }}>
                      📦 수령 확인
                    </button>
                    <button onClick={() => void openRefundModal(item)} style={{ padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,152,0,0.1)', border: '1px solid rgba(255,152,0,0.3)', color: '#ff9100', cursor: 'pointer' }}>
                      환불요청
                    </button>
                    {!item.is_disputed && (
                      <button onClick={() => { setDisputeTarget(item); setDisputeReason(''); }} style={{ padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', color: '#ff5252', cursor: 'pointer' }}>
                        ⚠️ 분쟁 신청
                      </button>
                    )}
                  </div>

                  {/* 배송 추적 결과 */}
                  {trackingOrderId === item.id && trackingInfo && (
                    <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 12, padding: 14, marginTop: 8, border: '1px solid rgba(255,255,255,0.08)' }}>
                      {trackingInfo.success ? (
                        <>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                            <span style={{ fontSize: 13, fontWeight: 700, color: '#4ade80' }}>{String(trackingInfo.status_label)}</span>
                            <span style={{ fontSize: 11, color: '#888' }}>{String(trackingInfo.carrier ?? '')} {String(trackingInfo.tracking_number ?? '')}</span>
                          </div>
                          <div style={{ borderLeft: '2px solid rgba(255,255,255,0.15)', paddingLeft: 14, marginLeft: 4 }}>
                            {(trackingInfo.details as Array<Record<string, string>> || []).slice().reverse().map((d, i) => (
                              <div key={i} style={{ position: 'relative', paddingBottom: 10, color: i === 0 ? '#4ade80' : '#888', fontSize: 12 }}>
                                <div style={{ position: 'absolute', left: -19, top: 4, width: 8, height: 8, borderRadius: '50%', background: i === 0 ? '#4ade80' : '#444' }} />
                                <div style={{ fontWeight: i === 0 ? 700 : 400 }}>{d.kind}</div>
                                <div style={{ fontSize: 10, color: '#666', marginTop: 1 }}>{d.time} · {d.where}</div>
                              </div>
                            ))}
                          </div>
                          {trackingInfo.status === 'DELIVERED' && (
                            <div style={{ marginTop: 8, textAlign: 'center' }}>
                              <div style={{ color: '#f59e0b', fontSize: 12, marginBottom: 6 }}>배달 완료! 3일 내 수취 확인하지 않으면 자동 구매확정됩니다.</div>
                              <button onClick={() => void handleConfirmArrival(item.id)} style={{ background: '#4ade80', color: '#000', padding: '8px 20px', borderRadius: 8, border: 'none', cursor: 'pointer', fontWeight: 700, fontSize: 12 }}>
                                수취 확인
                              </button>
                            </div>
                          )}
                        </>
                      ) : (
                        <div style={{ fontSize: 12, color: '#ff5252' }}>{String(trackingInfo.error || trackingInfo.message || '조회 실패')}</div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* 배송완료 */}
              {item.status === 'DELIVERED' && (
                <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
                  <button onClick={() => navigate(`/review/write/${item.id}`)} style={{ padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,214,0,0.1)', border: '1px solid rgba(255,214,0,0.35)', color: '#ffd600', cursor: 'pointer' }}>
                    ⭐ 리뷰 쓰기
                  </button>
                  <button onClick={() => void openRefundModal(item)} style={{ padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,152,0,0.1)', border: '1px solid rgba(255,152,0,0.3)', color: '#ff9100', cursor: 'pointer' }}>
                    환불요청
                  </button>
                </div>
              )}
            </div>
          );
        })}

        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 20, padding: '20px 0' }}>
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, opacity: page <= 1 ? 0.3 : 1, cursor: page <= 1 ? 'default' : 'pointer' }}>‹ 이전</button>
            <span style={{ fontSize: 13, color: C.textSec }}>{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, opacity: page >= totalPages ? 0.3 : 1, cursor: page >= totalPages ? 'default' : 'pointer' }}>다음 ›</button>
          </div>
        )}
      </div>

      {/* 환불 요청 모달 */}
      {refundTarget && (
        <>
          <div onClick={() => setRefundTarget(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000 }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: '92%', maxWidth: 400, background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 20, padding: '24px 20px', zIndex: 3001, maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 4 }}>환불 요청</div>
            <div style={{ fontSize: 12, color: C.textSec, marginBottom: 16 }}>예약 #{refundTarget.id} · {refundTarget.product_name}</div>

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 8 }}>처리 유형</div>
            <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
              {([['refund', '환불'], ['return', '반품'], ['exchange', '교환']] as const).map(([val, label]) => (
                <button key={val} onClick={() => setRefundType(val)} style={{
                  flex: 1, padding: '8px 0', borderRadius: 10, fontSize: 12, fontWeight: refundType === val ? 700 : 400, cursor: 'pointer',
                  background: refundType === val ? 'rgba(0,176,255,0.1)' : C.bgEl,
                  border: `1px solid ${refundType === val ? '#00b0ff' : C.border}`,
                  color: refundType === val ? '#00b0ff' : C.textSec,
                }}>{label}</button>
              ))}
            </div>

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 8 }}>환불 사유</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
              {REFUND_REASONS.map(r => (
                <button key={r} onClick={() => setRefundReason(r)} style={{
                  padding: '10px 14px', borderRadius: 10, fontSize: 13, textAlign: 'left', cursor: 'pointer',
                  background: refundReason === r ? 'rgba(0,230,118,0.08)' : C.bgEl,
                  border: `1px solid ${refundReason === r ? C.green : C.border}`,
                  color: refundReason === r ? C.green : C.textSec,
                  fontWeight: refundReason === r ? 700 : 400,
                }}>{r}</button>
              ))}
            </div>

            {refundReason === '기타' && (
              <input
                value={refundReasonOther}
                onChange={e => setRefundReasonOther(e.target.value)}
                placeholder="사유를 입력해주세요"
                style={{ width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: 10, fontSize: 13, background: C.bgEl, border: `1px solid ${C.border}`, color: C.text, marginBottom: 12 }}
              />
            )}

            {/* 환불 프리뷰 */}
            {refundPreviewData && (
              <div style={{ background: C.bgEl, border: `1px solid ${C.border}`, borderRadius: 12, padding: 14, marginBottom: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, marginBottom: 8 }}>환불 금액 미리보기</div>
                {(() => {
                  const decision = (refundPreviewData.decision ?? refundPreviewData) as Record<string, unknown>;
                  return (
                    <>
                      {decision.amount_goods != null && <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: C.textSec, padding: '3px 0' }}><span>상품 환불</span><span>{fmtPrice(decision.amount_goods as number)}</span></div>}
                      {decision.amount_shipping != null && <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: C.textSec, padding: '3px 0' }}><span>배송비 환불</span><span>{fmtPrice(decision.amount_shipping as number)}</span></div>}
                      {decision.amount_total != null && (
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, fontWeight: 700, color: C.green, padding: '6px 0 0', borderTop: `1px solid ${C.border}`, marginTop: 4 }}>
                          <span>예상 환불 금액</span><span>{fmtPrice(decision.amount_total as number)}</span>
                        </div>
                      )}
                      {decision.note && <div style={{ fontSize: 11, color: C.textDim, marginTop: 6 }}>{String(decision.note)}</div>}
                    </>
                  );
                })()}
              </div>
            )}

            <div style={{ fontSize: 11, color: C.textDim, marginBottom: 16, lineHeight: 1.6 }}>
              환불 금액은 환불 정책에 따라 달라질 수 있습니다.
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setRefundTarget(null)} style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>닫기</button>
              <button
                disabled={refundLoading}
                onClick={handleRefundSubmit}
                style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: refundLoading ? '#ff910055' : '#ff9100', border: 'none', color: '#0a0a0f', cursor: refundLoading ? 'not-allowed' : 'pointer' }}
              >{refundLoading ? '처리 중...' : '환불 요청하기'}</button>
            </div>
          </div>
        </>
      )}

      {/* 분쟁 신청 모달 */}
      {disputeTarget && (
        <>
          <div onClick={() => setDisputeTarget(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000 }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: '92%', maxWidth: 400, background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 20, padding: '24px 20px', zIndex: 3001 }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: '#ff5252', marginBottom: 4 }}>⚠️ 분쟁 신청</div>
            <div style={{ fontSize: 12, color: C.textSec, marginBottom: 16 }}>예약 #{disputeTarget.id} · {disputeTarget.product_name}</div>

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 8 }}>분쟁 사유</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 12 }}>
              {['상품 미배송', '상품 불량/하자', '설명과 다른 상품', '오배송', '기타'].map(r => (
                <button key={r} onClick={() => setDisputeReason(r === '기타' ? '' : r)} style={{
                  padding: '10px 14px', borderRadius: 10, fontSize: 13, textAlign: 'left', cursor: 'pointer',
                  background: disputeReason === r ? 'rgba(255,82,82,0.08)' : C.bgEl,
                  border: `1px solid ${disputeReason === r ? '#ff5252' : C.border}`,
                  color: disputeReason === r ? '#ff5252' : C.textSec,
                  fontWeight: disputeReason === r ? 700 : 400,
                }}>{r}</button>
              ))}
            </div>

            <textarea
              value={disputeReason}
              onChange={e => setDisputeReason(e.target.value)}
              placeholder="분쟁 사유를 상세히 입력해주세요"
              style={{ width: '100%', boxSizing: 'border-box', minHeight: 80, padding: '10px 14px', borderRadius: 10, fontSize: 13, background: C.bgEl, border: `1px solid ${C.border}`, color: C.text, resize: 'vertical', marginBottom: 16 }}
            />

            <div style={{ fontSize: 11, color: C.textDim, marginBottom: 16, lineHeight: 1.6 }}>
              분쟁 접수 시 해당 거래의 정산이 자동 보류됩니다. 관리자가 양측 의견을 확인한 후 처리합니다.
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setDisputeTarget(null)} style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>취소</button>
              <button
                disabled={disputeLoading || !disputeReason.trim()}
                onClick={() => void handleDisputeOpen()}
                style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: disputeLoading || !disputeReason.trim() ? '#ff525555' : '#ff5252', border: 'none', color: '#fff', cursor: disputeLoading || !disputeReason.trim() ? 'not-allowed' : 'pointer' }}
              >{disputeLoading ? '처리 중...' : '분쟁 접수하기'}</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
