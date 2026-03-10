import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchSellerReservations, markShipped, fetchCarriers } from '../api/reservationApi';
import apiClient from '../api/client';
import { showToast } from '../components/common/Toast';
import { trackBehavior } from '../utils/behaviorTracker';

const DEFAULT_CARRIERS = ['CJ대한통운', '한진택배', '로젠택배', '우체국택배', 'CU편의점택배', '롯데택배'];

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

function fmtPrice(n: number) { return n.toLocaleString('ko-KR') + '원'; }
function fmtDate(s: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

type ShipStatus = 'PENDING_SHIP' | 'SHIPPED' | 'DELIVERED' | 'CONFIRMED';

interface SellerOrder {
  id: number;
  deal_id?: number;
  offer_id: number;
  product_name: string;
  buyer_name: string;
  qty: number;
  amount_total: number;
  status: ShipStatus;
  shipped_at?: string;
  tracking_number?: string;
  shipping_carrier?: string;
  created_at: string;
}

export default function SellerShipPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [orders, setOrders] = useState<SellerOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [carriers, setCarriers] = useState(DEFAULT_CARRIERS);
  const [filter, setFilter] = useState<'전체' | '발송대기' | '배송중' | '배송완료' | '구매확정'>('전체');

  // Ship modal
  const [shipTarget, setShipTarget] = useState<SellerOrder | null>(null);
  const [carrier, setCarrier] = useState(DEFAULT_CARRIERS[0]);
  const [tracking, setTracking] = useState('');
  const [shipLoading, setShipLoading] = useState(false);

  // Delivery tracking
  const [trackResult, setTrackResult] = useState<Record<string, unknown> | null>(null);
  const [trackOrderId, setTrackOrderId] = useState<number | null>(null);
  const [trackLoading, setTrackLoading] = useState(false);

  const handleTrack = async (orderId: number) => {
    if (trackOrderId === orderId) { setTrackOrderId(null); setTrackResult(null); return; }
    setTrackLoading(true);
    setTrackOrderId(orderId);
    try {
      const resp = await apiClient.get(`/delivery/track/${orderId}`);
      setTrackResult(resp.data as Record<string, unknown>);
    } catch { setTrackResult({ success: false, error: '조회 실패' }); }
    setTrackLoading(false);
  };

  const deliveryBadge = (status?: string) => {
    const map: Record<string, { label: string; color: string }> = {
      READY: { label: '준비', color: '#888' },
      COLLECTING: { label: '집하', color: '#f59e0b' },
      IN_TRANSIT: { label: '이동중', color: '#3b82f6' },
      OUT_FOR_DELIVERY: { label: '배달중', color: '#8b5cf6' },
      DELIVERED: { label: '완료', color: '#4ade80' },
    };
    const s = map[status || ''] || { label: status || '미확인', color: '#666' };
    return (
      <span style={{ background: s.color + '20', color: s.color, padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600 }}>{s.label}</span>
    );
  };

  useEffect(() => {
    fetchCarriers().then(data => {
      if (data && Array.isArray(data) && data.length > 0) {
        const names = data.map((c: Record<string, unknown>) => typeof c === 'string' ? c : String(c.name ?? c));
        setCarriers(names);
        setCarrier(names[0]);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    const sellerId = user.seller?.id || user.id;
    (async () => {
      setLoading(true);
      try {
        const data = await fetchSellerReservations(sellerId);
        if (data && Array.isArray(data)) {
          setOrders((data as Record<string, unknown>[]).map(r => {
            const deal = r.deal as Record<string, unknown> | undefined;
            const buyer = r.buyer as Record<string, unknown> | undefined;
            let status: ShipStatus = 'PENDING_SHIP';
            if (r.arrival_confirmed_at) status = 'CONFIRMED';
            else if (r.delivered_at) status = 'DELIVERED';
            else if (r.shipped_at) status = 'SHIPPED';
            return {
              id: r.id as number,
              deal_id: (r.deal_id as number) || (deal?.id as number) || undefined,
              offer_id: (r.offer_id as number) || 0,
              product_name: String(deal?.product_name ?? `예약 #${r.id}`),
              buyer_name: String(buyer?.nickname ?? buyer?.name ?? `구매자#${r.buyer_id}`),
              qty: (r.qty as number) || 1,
              amount_total: (r.amount_total as number) || 0,
              status,
              shipped_at: (r.shipped_at as string) || undefined,
              tracking_number: (r.tracking_number as string) || undefined,
              shipping_carrier: (r.shipping_carrier as string) || undefined,
              created_at: String(r.created_at ?? '').split('T')[0],
            };
          }));
        }
      } catch (err) {
        console.error('판매자 예약 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  const handleShip = async () => {
    if (!shipTarget || !tracking.trim()) {
      showToast('운송장 번호를 입력해주세요', 'error');
      return;
    }
    setShipLoading(true);
    try {
      await markShipped(shipTarget.id, tracking.trim(), carrier);
      setOrders(prev => prev.map(o => o.id === shipTarget.id ? { ...o, status: 'SHIPPED' as ShipStatus, tracking_number: tracking, shipping_carrier: carrier } : o));
      setShipTarget(null);
      setTracking('');
      trackBehavior('SELLER_SHIPPING', { target_type: 'reservation', target_id: shipTarget.id });
      showToast('발송 처리 완료!', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '발송 처리 실패', 'error');
    }
    setShipLoading(false);
  };

  const statusMeta: Record<ShipStatus, { label: string; color: string }> = {
    PENDING_SHIP: { label: '발송대기', color: '#ff9100' },
    SHIPPED:      { label: '배송중',   color: '#448aff' },
    DELIVERED:    { label: '배송완료', color: '#00e676' },
    CONFIRMED:    { label: '구매확정', color: '#78909c' },
  };

  const filtered = filter === '전체' ? orders : orders.filter(o => {
    if (filter === '발송대기') return o.status === 'PENDING_SHIP';
    if (filter === '배송중') return o.status === 'SHIPPED';
    if (filter === '배송완료') return o.status === 'DELIVERED';
    if (filter === '구매확정') return o.status === 'CONFIRMED';
    return true;
  });

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>배송 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 상태 필터 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {(['전체', '발송대기', '배송중', '배송완료', '구매확정'] as const).map(s => (
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
            <div style={{ fontSize: 40, marginBottom: 8 }}>📦</div>
            <div style={{ fontSize: 13 }}>해당 주문이 없어요</div>
          </div>
        ) : filtered.map(order => {
          const meta = statusMeta[order.status];
          return (
            <div key={order.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${meta.color}`,
              borderRadius: 14, padding: '13px 14px', marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 2 }}>📦 {order.product_name}</div>
                  <div style={{ fontSize: 11, color: C.textSec }}>
                    예약 <span style={{ fontWeight: 600, color: 'var(--accent-blue)' }}>#{order.id}</span>
                    {order.deal_id ? <> · <span onClick={e => { e.stopPropagation(); navigate(`/deal/${order.deal_id}`); }} style={{ cursor: 'pointer', color: 'var(--accent-blue)', textDecoration: 'underline' }}>딜 #{order.deal_id}</span></> : null}
                    {' · '}오퍼 #{order.offer_id} · {order.buyer_name}
                  </div>
                  <div style={{ fontSize: 11, color: C.textSec }}>{order.qty}개 · {fmtPrice(order.amount_total)}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6, background: `${meta.color}22`, color: meta.color }}>{meta.label}</span>
                  <div style={{ fontSize: 10, color: C.textDim, marginTop: 4 }}>{fmtDate(order.created_at)}</div>
                </div>
              </div>

              {order.status === 'PENDING_SHIP' && (
                <button onClick={() => { setShipTarget(order); setTracking(''); }}
                  style={{ marginTop: 6, padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(0,230,118,0.12)', border: '1px solid rgba(0,230,118,0.35)', color: '#00e676', cursor: 'pointer' }}>
                  📦 발송 처리
                </button>
              )}

              {order.tracking_number && (
                <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 11, color: C.orange }}>🚚 {order.shipping_carrier ? `${order.shipping_carrier} ` : ''}{order.tracking_number}</span>
                  {order.status === 'SHIPPED' && (
                    <button onClick={() => void handleTrack(order.id)} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 6, background: 'rgba(59,130,246,0.12)', border: '1px solid rgba(59,130,246,0.3)', color: '#3b82f6', cursor: 'pointer', fontWeight: 600 }}>
                      {trackLoading && trackOrderId === order.id ? '...' : '조회'}
                    </button>
                  )}
                </div>
              )}

              {/* 배송 추적 결과 */}
              {trackOrderId === order.id && trackResult && (
                <div style={{ marginTop: 6, padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)' }}>
                  {trackResult.success ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}>
                      {deliveryBadge(String(trackResult.status))}
                      <span style={{ color: '#888' }}>{String((trackResult.latest as Record<string, string>)?.kind ?? '')}</span>
                      <span style={{ color: '#666', fontSize: 11 }}>{String((trackResult.latest as Record<string, string>)?.time ?? '')}</span>
                    </div>
                  ) : (
                    <div style={{ fontSize: 11, color: '#ff5252' }}>{String(trackResult.error || '조회 실패')}</div>
                  )}
                </div>
              )}

              {order.status === 'CONFIRMED' && (
                <div style={{ marginTop: 6, fontSize: 11, color: '#78909c', fontWeight: 700 }}>
                  ✓ 구매확정 완료
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 발송 처리 모달 */}
      {shipTarget && (
        <>
          <div onClick={() => setShipTarget(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000 }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: '92%', maxWidth: 400, background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 20, padding: '24px 20px', zIndex: 3001 }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 4 }}>발송 처리</div>
            <div style={{ fontSize: 12, color: C.textSec, marginBottom: 16 }}>예약 #{shipTarget.id} · {shipTarget.product_name}</div>

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>택배사</div>
            <select value={carrier} onChange={e => setCarrier(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', borderRadius: 10, fontSize: 13, background: C.bgEl, border: `1px solid ${C.border}`, color: C.text, marginBottom: 12, appearance: 'auto' }}>
              {carriers.map(c => <option key={c} value={c}>{c}</option>)}
            </select>

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>운송장 번호</div>
            <input value={tracking} onChange={e => setTracking(e.target.value)} placeholder="운송장 번호 입력"
              style={{ width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: 10, fontSize: 13, background: C.bgEl, border: `1px solid ${C.border}`, color: C.text, marginBottom: 16 }} />

            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setShipTarget(null)} style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>취소</button>
              <button disabled={shipLoading || !tracking.trim()} onClick={handleShip}
                style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: shipLoading ? `${C.green}55` : C.green, border: 'none', color: '#0a0a0f', cursor: shipLoading || !tracking.trim() ? 'not-allowed' : 'pointer' }}>
                {shipLoading ? '처리 중...' : '발송 완료'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
