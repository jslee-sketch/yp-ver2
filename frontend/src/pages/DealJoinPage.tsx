import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';
import { fetchDeal } from '../api/dealApi';
import { fetchOffersByDeal, createReservation, payReservation } from '../api/reservationApi';
import { showToast } from '../components/common/Toast';
import { trackBehavior } from '../utils/behaviorTracker';

const C = {
  bgDeep: '#0a0e1a', bgCard: '#111827', bgSurface: '#1a2236', bgInput: '#0f1625',
  cyan: '#00f0ff', green: '#39ff14', yellow: '#ffe156', orange: '#ff8c42',
  textPri: '#f0f4ff', textSec: '#8892a8', textDim: '#4a5568',
  border: 'rgba(0,240,255,0.12)',
};

const fmtP = (n: number) => '₩' + n.toLocaleString('ko-KR');

interface OfferItem {
  id: number;
  seller_id: number;
  seller_name: string;
  price: number;
  total_available_qty: number;
  sold_qty: number;
  reserved_qty: number;
  shipping_mode: string;
  shipping_fee_per_reservation: number;
  shipping_fee_per_qty: number;
  delivery_days: number;
  comment: string;
  is_active: boolean;
}

interface DealInfo {
  product_name: string;
  brand: string;
  target_price: number;
  market_price: number | null;
}

export default function DealJoinPage() {
  const { id: dealId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [deal, setDeal] = useState<DealInfo | null>(null);
  const [offers, setOffers] = useState<OfferItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState(false);

  // Flow: 'offers' → 'confirm' → 'checkout' → 'done'
  const [step, setStep] = useState<'offers' | 'confirm' | 'checkout' | 'done'>('offers');
  const [selectedOffer, setSelectedOffer] = useState<OfferItem | null>(null);
  const [qty, setQty] = useState(1);
  const [reservationData, setReservationData] = useState<Record<string, unknown> | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!dealId) { setLoadErr(true); return; }
    (async () => {
      try {
        const [rawDeal, rawOffers] = await Promise.all([
          fetchDeal(Number(dealId)),
          fetchOffersByDeal(Number(dealId)),
        ]);
        if (!rawDeal) { setLoadErr(true); return; }
        const d = rawDeal as Record<string, unknown>;
        setDeal({
          product_name: String(d.product_name ?? ''),
          brand: String(d.brand ?? ''),
          target_price: (d.target_price as number) || 0,
          market_price: (d.market_price as number) ?? null,
        });
        if (rawOffers && Array.isArray(rawOffers)) {
          setOffers(rawOffers.map((o: Record<string, unknown>) => {
            const seller = o.seller as Record<string, unknown> | undefined;
            return {
              id: o.id as number,
              seller_id: o.seller_id as number,
              seller_name: String(seller?.business_name ?? seller?.nickname ?? `판매자#${o.seller_id}`),
              price: (o.price as number) || 0,
              total_available_qty: (o.total_available_qty as number) || 0,
              sold_qty: (o.sold_qty as number) || 0,
              reserved_qty: (o.reserved_qty as number) || 0,
              shipping_mode: String(o.shipping_mode ?? 'FLAT'),
              shipping_fee_per_reservation: (o.shipping_fee_per_reservation as number) || 0,
              shipping_fee_per_qty: (o.shipping_fee_per_qty as number) || 0,
              delivery_days: (o.delivery_days as number) || 7,
              comment: String(o.comment ?? ''),
              is_active: o.is_active !== false,
            };
          }).filter(o => o.is_active));
        }
      } catch {
        setLoadErr(true);
      } finally {
        setLoading(false);
      }
    })();
  }, [dealId]);

  const calcShipping = (offer: OfferItem, q: number) => {
    if (offer.shipping_mode === 'FREE') return 0;
    if (offer.shipping_mode === 'PER_ITEM') return offer.shipping_fee_per_qty * q;
    return offer.shipping_fee_per_reservation;
  };

  const handleSelectOffer = (offer: OfferItem) => {
    setSelectedOffer(offer);
    setQty(1);
    setStep('confirm');
  };

  const handleReserve = async () => {
    if (!user || !selectedOffer) return;
    trackBehavior('JOIN_DEAL', {
      target_type: 'offer',
      target_id: selectedOffer.id,
      meta: { deal_id: Number(dealId), price: selectedOffer.price },
    });
    setSubmitting(true);
    try {
      const result = await createReservation({
        deal_id: Number(dealId),
        offer_id: selectedOffer.id,
        buyer_id: user.id,
        qty,
      });
      setReservationData(result as Record<string, unknown>);
      setStep('checkout');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e.response?.data?.detail;
      showToast(typeof detail === 'string' ? detail : '예약 생성에 실패했어요', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  const handlePay = async () => {
    if (!user || !reservationData || !selectedOffer) return;
    setSubmitting(true);
    try {
      const resId = reservationData.id as number;
      const total = (reservationData.amount_total as number) || selectedOffer.price * qty + calcShipping(selectedOffer, qty);
      await payReservation(resId, user.id, total);
      setStep('done');
      showToast('결제가 완료되었어요!', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e.response?.data?.detail;
      showToast(typeof detail === 'string' ? detail : '결제 처리에 실패했어요', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100dvh', background: C.bgDeep, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ fontSize: 14, color: C.textSec }}>불러오는 중...</div>
      </div>
    );
  }

  if (loadErr || !deal) {
    return (
      <div style={{ minHeight: '100dvh', background: C.bgDeep, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <div style={{ fontSize: 40 }}>🔍</div>
        <div style={{ color: C.textSec, fontSize: 14 }}>딜을 찾을 수 없어요</div>
        <button onClick={() => navigate(-1)} style={{ padding: '10px 20px', borderRadius: 10, background: `${C.green}18`, border: `1px solid ${C.green}44`, color: C.green, fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>돌아가기</button>
      </div>
    );
  }

  // Done state
  if (step === 'done') {
    return (
      <div style={{ minHeight: '100dvh', background: C.bgDeep, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px' }}>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} style={{ width: '100%', maxWidth: 400, textAlign: 'center' }}>
          <div style={{ fontSize: 64, marginBottom: 20 }}>🎉</div>
          <div style={{ fontSize: 24, fontWeight: 900, color: C.textPri, marginBottom: 8 }}>결제가 완료되었어요!</div>
          <div style={{ fontSize: 14, color: C.textSec, marginBottom: 32 }}>판매자가 상품을 준비합니다.</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <button onClick={() => navigate('/my-orders')} style={{ padding: '15px', borderRadius: 14, fontSize: 15, fontWeight: 800, background: `linear-gradient(135deg, ${C.cyan}, ${C.green})`, color: '#0a0e1a', cursor: 'pointer' }}>
              내 주문 확인하기
            </button>
            <button onClick={() => navigate(`/deal/${dealId ?? ''}`)} style={{ padding: '14px', borderRadius: 14, fontSize: 14, fontWeight: 600, background: 'transparent', border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>
              딜 페이지로 이동
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  const stepLabel = step === 'offers' ? '오퍼 선택' : step === 'confirm' ? '예약 확인' : '결제';
  const stepNum = step === 'offers' ? 1 : step === 'confirm' ? 2 : 3;

  return (
    <div style={{ minHeight: '100dvh', background: C.bgDeep }}>
      {/* TopBar */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 20px', zIndex: 10, background: 'rgba(10,14,26,0.92)', backdropFilter: 'blur(10px)', borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => {
          if (step === 'offers') navigate(-1);
          else if (step === 'confirm') setStep('offers');
          else setStep('confirm');
        }} style={{ fontSize: 13, color: C.textSec, cursor: 'pointer' }}>← {step === 'offers' ? '뒤로' : '이전'}</button>
        <div style={{ fontSize: 13, fontWeight: 700 }}>
          <span style={{ color: C.cyan }}>{stepLabel}</span>
          <span style={{ color: C.textDim }}> ({stepNum}/3)</span>
        </div>
        <div style={{ width: 48 }} />
      </div>

      <div style={{ position: 'fixed', top: 56, left: 0, right: 0, height: 3, zIndex: 10, background: C.border }}>
        <div style={{ height: '100%', width: `${(stepNum / 3) * 100}%`, background: `linear-gradient(90deg, ${C.cyan}, ${C.green})`, transition: 'width 0.35s' }} />
      </div>

      <div style={{ paddingTop: 64, maxWidth: 500, margin: '0 auto', padding: '64px 20px 100px' }}>
        <AnimatePresence mode="wait">
          {/* Step 1: 오퍼 목록 */}
          {step === 'offers' && (
            <motion.div key="offers" initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -40 }}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: C.textPri, marginBottom: 4 }}>📦 {deal.product_name}</div>
                <div style={{ fontSize: 12, color: C.textSec }}>{[deal.brand, deal.target_price ? `목표가 ${fmtP(deal.target_price)}` : ''].filter(Boolean).join(' · ')}</div>
              </div>

              {offers.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '60px 0', color: C.textDim }}>
                  <div style={{ fontSize: 40, marginBottom: 12 }}>📭</div>
                  <div style={{ fontSize: 14 }}>아직 오퍼가 없어요</div>
                  <div style={{ fontSize: 12, marginTop: 6 }}>판매자의 오퍼를 기다려주세요!</div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {offers.map(offer => {
                    const avail = offer.total_available_qty - offer.sold_qty - offer.reserved_qty;
                    const shippingLabel = offer.shipping_mode === 'FREE' ? '무료배송' : `배송비 ${fmtP(offer.shipping_fee_per_reservation || offer.shipping_fee_per_qty)}`;
                    return (
                      <div key={offer.id} style={{
                        background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: 16, cursor: avail > 0 ? 'pointer' : 'default',
                        opacity: avail > 0 ? 1 : 0.5, transition: 'border-color 0.15s',
                      }}
                        onClick={() => avail > 0 && handleSelectOffer(offer)}
                        onMouseEnter={e => { if (avail > 0) e.currentTarget.style.borderColor = C.cyan; }}
                        onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(0,240,255,0.12)'; }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
                          <div>
                            <div style={{ fontSize: 14, fontWeight: 700, color: C.textPri, marginBottom: 2 }}>{offer.seller_name}</div>
                            {offer.comment && <div style={{ fontSize: 11, color: C.textDim }}>{offer.comment}</div>}
                          </div>
                          <div style={{ textAlign: 'right' }}>
                            <div style={{ fontSize: 18, fontWeight: 900, color: C.green }}>{fmtP(offer.price)}</div>
                            <div style={{ fontSize: 10, color: C.textDim }}>개당</div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 10, padding: '3px 8px', borderRadius: 6, background: 'rgba(0,240,255,0.08)', color: C.cyan }}>{shippingLabel}</span>
                          <span style={{ fontSize: 10, padding: '3px 8px', borderRadius: 6, background: 'rgba(255,225,86,0.08)', color: C.yellow }}>리드타임 {offer.delivery_days}일</span>
                          <span style={{ fontSize: 10, padding: '3px 8px', borderRadius: 6, background: avail > 0 ? 'rgba(57,255,20,0.08)' : 'rgba(255,82,82,0.08)', color: avail > 0 ? C.green : '#ff5252' }}>
                            {avail > 0 ? `잔여 ${avail}개` : '품절'}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </motion.div>
          )}

          {/* Step 2: 예약 확인 */}
          {step === 'confirm' && selectedOffer && (
            <motion.div key="confirm" initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -40 }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: C.textPri, marginBottom: 16 }}>예약 확인</div>

              <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: 16, marginBottom: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 12 }}>오퍼 정보</div>
                {[
                  { icon: '📦', label: '상품', value: deal.product_name },
                  { icon: '🏪', label: '판매자', value: selectedOffer.seller_name },
                  { icon: '💰', label: '단가', value: fmtP(selectedOffer.price) },
                  { icon: '🚚', label: '배송', value: selectedOffer.shipping_mode === 'FREE' ? '무료' : fmtP(calcShipping(selectedOffer, qty)) },
                ].map(r => (
                  <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: `1px solid ${C.border}` }}>
                    <span style={{ fontSize: 13, color: C.textSec }}>{r.icon} {r.label}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: C.textPri }}>{r.value}</span>
                  </div>
                ))}
              </div>

              {/* 수량 선택 */}
              <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: 16, marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 14, letterSpacing: 1 }}>수량</div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 24 }}>
                  <button onClick={() => setQty(q => Math.max(1, q - 1))}
                    style={{ width: 40, height: 40, borderRadius: 10, fontSize: 20, fontWeight: 700, background: C.bgSurface, border: `1px solid ${C.border}`, color: C.textPri, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>−</button>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 28, fontWeight: 900, color: C.cyan }}>{qty}</div>
                    <div style={{ fontSize: 11, color: C.textDim, marginTop: 2 }}>개</div>
                  </div>
                  <button onClick={() => {
                    const avail = selectedOffer.total_available_qty - selectedOffer.sold_qty - selectedOffer.reserved_qty;
                    setQty(q => Math.min(avail, q + 1));
                  }}
                    style={{ width: 40, height: 40, borderRadius: 10, fontSize: 20, fontWeight: 700, background: C.bgSurface, border: `1px solid ${C.border}`, color: C.textPri, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>+</button>
                </div>
              </div>

              {/* 금액 요약 */}
              <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderTop: `3px solid ${C.green}`, borderRadius: 16, padding: 16, marginBottom: 20 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0' }}>
                  <span style={{ fontSize: 13, color: C.textSec }}>상품 금액</span>
                  <span style={{ fontSize: 13, color: C.textPri }}>{fmtP(selectedOffer.price * qty)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${C.border}` }}>
                  <span style={{ fontSize: 13, color: C.textSec }}>배송비</span>
                  <span style={{ fontSize: 13, color: C.textPri }}>{calcShipping(selectedOffer, qty) === 0 ? '무료' : fmtP(calcShipping(selectedOffer, qty))}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0 0' }}>
                  <span style={{ fontSize: 15, fontWeight: 800, color: C.textPri }}>총 결제 예상 금액</span>
                  <span style={{ fontSize: 18, fontWeight: 900, color: C.green }}>{fmtP(selectedOffer.price * qty + calcShipping(selectedOffer, qty))}</span>
                </div>
              </div>

              <button
                onClick={handleReserve}
                disabled={submitting}
                style={{
                  width: '100%', padding: '15px', borderRadius: 14, fontSize: 15, fontWeight: 800,
                  background: submitting ? `${C.green}40` : `linear-gradient(135deg, ${C.cyan}, ${C.green})`,
                  color: '#0a0e1a', cursor: submitting ? 'not-allowed' : 'pointer',
                }}
              >{submitting ? '예약 중...' : '🛒 예약하기'}</button>
              <div style={{ textAlign: 'center', fontSize: 11, color: C.textDim, marginTop: 8 }}>예약 후 결제를 진행합니다</div>
            </motion.div>
          )}

          {/* Step 3: 결제 */}
          {step === 'checkout' && reservationData && selectedOffer && (
            <motion.div key="checkout" initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -40 }}>
              <div style={{ fontSize: 20, fontWeight: 800, color: C.textPri, marginBottom: 16 }}>결제</div>

              <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: 16, marginBottom: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 12 }}>결제 정보</div>
                {[
                  { label: '예약 번호', value: `#${reservationData.id}` },
                  { label: '상품', value: deal.product_name },
                  { label: '판매자', value: selectedOffer.seller_name },
                  { label: '수량', value: `${reservationData.qty ?? qty}개` },
                  { label: '상품 금액', value: fmtP((reservationData.amount_goods as number) || selectedOffer.price * qty) },
                  { label: '배송비', value: (reservationData.amount_shipping as number) ? fmtP(reservationData.amount_shipping as number) : '무료' },
                ].map(r => (
                  <div key={r.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: `1px solid ${C.border}` }}>
                    <span style={{ fontSize: 13, color: C.textSec }}>{r.label}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: C.textPri }}>{r.value}</span>
                  </div>
                ))}
                <div style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0 0' }}>
                  <span style={{ fontSize: 16, fontWeight: 800, color: C.textPri }}>총 결제 금액</span>
                  <span style={{ fontSize: 20, fontWeight: 900, color: C.green }}>{fmtP((reservationData.amount_total as number) || 0)}</span>
                </div>
              </div>

              <div style={{ background: 'rgba(0,240,255,0.04)', border: `1px solid rgba(0,240,255,0.15)`, borderRadius: 14, padding: '14px 16px', marginBottom: 20 }}>
                <div style={{ fontSize: 12, color: C.cyan, fontWeight: 700, marginBottom: 4 }}>테스트 결제 안내</div>
                <div style={{ fontSize: 12, color: C.textSec, lineHeight: 1.6 }}>
                  실제 PG 결제는 준비 중입니다.<br />테스트 결제로 즉시 처리됩니다.
                </div>
              </div>

              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  onClick={() => { setStep('confirm'); }}
                  style={{ flex: 1, padding: '15px', borderRadius: 14, fontSize: 14, fontWeight: 700, background: C.bgCard, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}
                >취소</button>
                <button
                  onClick={handlePay}
                  disabled={submitting}
                  style={{
                    flex: 2, padding: '15px', borderRadius: 14, fontSize: 15, fontWeight: 800,
                    background: submitting ? `${C.green}40` : `linear-gradient(135deg, ${C.cyan}, ${C.green})`,
                    color: '#0a0e1a', cursor: submitting ? 'not-allowed' : 'pointer',
                  }}
                >{submitting ? '처리 중...' : '💳 결제하기'}</button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
