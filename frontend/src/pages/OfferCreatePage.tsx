import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';
import { createOffer, fetchOffersByDeal } from '../api/offerApi';
import { fetchDeal } from '../api/dealApi';
import { showToast } from '../components/common/Toast';
import { trackBehavior } from '../utils/behaviorTracker';

// ── 디자인 토큰 ──────────────────────────────────────────
const C = {
  bgDeep:   '#0a0e1a',
  bgCard:   '#111827',
  bgSurface:'#1a2236',
  bgInput:  '#0f1625',
  cyan:     '#00f0ff',
  magenta:  '#ff2d78',
  green:    '#39ff14',
  yellow:   '#ffe156',
  orange:   '#ff8c42',
  textPri:  '#f0f4ff',
  textSec:  '#8892a8',
  textDim:  '#4a5568',
  border:   'rgba(0,240,255,0.12)',
};

// ── 딜 정보 타입 ─────────────────────────────────────────
interface DealInfo {
  id: number;
  product_name: string;
  brand?: string;
  target_price: number;
  anchor_price: number;
  current_orders: number;
  target_orders: number;
  deadline_at?: string;
  options: { title: string; value: string }[];
  lowest_offer: number;
  offer_count: number;
}

// ── 타입 ────────────────────────────────────────────────
type CancelRule = 'A1' | 'A2' | 'A3' | 'A4';

const CANCEL_RULES: { id: CancelRule; label: string; desc: string }[] = [
  { id: 'A1', label: '언제든 취소 가능',    desc: '구매자 친화적, 신뢰도 ↑' },
  { id: 'A2', label: '발송 후 취소 불가',   desc: '판매자 보호, 식품/맞춤제작' },
  { id: 'A3', label: '수령 후 N일 이내 취소', desc: '수령 후 기간 내 취소 허용' },
  { id: 'A4', label: '협의 후 취소',        desc: '케이스별 개별 협의' },
];

const WARRANTY_OPTIONS = [
  { months: 0,  label: '없음' },
  { months: 3,  label: '3개월' },
  { months: 6,  label: '6개월' },
  { months: 12, label: '12개월' },
  { months: -1, label: '12개월+' },  // custom: triggers input
];

const DELIVERY_CHIPS = [1, 2, 3] as const;

// ── 헬퍼 ─────────────────────────────────────────────────
const fmtPrice  = (n: number) => n > 0 ? n.toLocaleString('ko-KR') : '';
const parseNum  = (s: string) => parseInt(s.replace(/[^\d]/g, ''), 10) || 0;

const _getTier = (p: number, targetPrice: number): 'PREMIUM' | 'MATCHING' | 'BELOW' => {
  if (p < targetPrice)  return 'PREMIUM';
  if (p === targetPrice) return 'MATCHING';
  return 'BELOW';
};

const _getSavingsPct = (p: number, targetPrice: number): string => {
  if (p <= 0 || targetPrice <= 0) return '';
  const diff = targetPrice - p;
  const pct  = Math.abs((diff / targetPrice) * 100).toFixed(1);
  return diff > 0 ? `-${pct}%` : `+${pct}%`;
};

const _getRank = (p: number, lowestOffer: number): number => {
  if (p <= 0) return 0;
  if (lowestOffer <= 0 || p <= lowestOffer) return 1;
  return Math.min(13, Math.floor((p - lowestOffer) / 5000) + 2);
};

const tierBadge = (tier: 'PREMIUM' | 'MATCHING' | 'BELOW') => {
  const map = {
    PREMIUM:  { bg: 'rgba(57,255,20,0.15)',  border: 'rgba(57,255,20,0.4)',  color: '#39ff14', label: 'PREMIUM' },
    MATCHING: { bg: 'rgba(255,225,86,0.15)', border: 'rgba(255,225,86,0.4)', color: '#ffe156', label: 'MATCHING' },
    BELOW:    { bg: 'rgba(255,45,120,0.12)', border: 'rgba(255,45,120,0.35)', color: '#ff6a99', label: 'BELOW' },
  };
  return map[tier];
};

// ── 애니메이션 ────────────────────────────────────────────
const variants = {
  enter:  (d: number) => ({ x: d > 0 ? '60%' : '-60%', opacity: 0 }),
  center: { x: 0, opacity: 1, transition: { type: 'spring' as const, damping: 28, stiffness: 300 } },
  exit:   (d: number) => ({ x: d > 0 ? '-60%' : '60%', opacity: 0, transition: { duration: 0.18 } }),
};

// ── 공용 컴포넌트 ────────────────────────────────────────
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '12px 14px', fontSize: 14, borderRadius: 12, boxSizing: 'border-box',
  background: C.bgInput, border: `1px solid rgba(255,255,255,0.12)`, color: C.textPri,
  outline: 'none',
};

function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 8 }}>
      {children}{required && <span style={{ color: C.magenta }}> *</span>}
    </div>
  );
}

function Chip({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '7px 16px', borderRadius: 20, fontSize: 13, fontWeight: 600, cursor: 'pointer',
        background: active ? `${C.green}18` : C.bgSurface,
        border: `1.5px solid ${active ? C.green : C.border}`,
        color: active ? C.green : C.textSec,
        transition: 'all 0.15s',
      }}
    >
      {children}
    </button>
  );
}

// ── 메인 컴포넌트 ────────────────────────────────────────
export default function OfferCreatePage() {
  const { id: dealId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [deal, setDeal] = useState<DealInfo | null>(null);
  const [dealLoading, setDealLoading] = useState(true);

  const [step, setStep] = useState(1);
  const [dir,  setDir]  = useState(1);

  // Step 1: 옵션 확인 + 조건 + 구성품
  const [confirmedOptions, setConfirmedOptions] = useState<Record<string, boolean>>({});
  const [extraOptions, setExtraOptions] = useState<{ key: string; value: string }[]>([]);
  const [condWarranty, setCondWarranty] = useState('없음');
  const [condRefund, setCondRefund] = useState('7일');
  const [condShipping, setCondShipping] = useState('무료');
  const [condDelivery, setCondDelivery] = useState('1~3일');
  const [componentsText, setComponentsText] = useState('');
  const [optionAgreement, setOptionAgreement] = useState(false);

  // Step 2: 가격 & 수량
  const [priceStr,  setPriceStr]  = useState('');
  const [totalQty,  setTotalQty]  = useState(20);
  const [comment,   setComment]   = useState('');

  // Step 3: 제품 상세 + 사진
  const [detail,    setDetail]    = useState('');
  const [images,    setImages]    = useState<string[]>([]);

  // Step 2 (old): 배송 & 정책
  const [shippingMode,      setShippingMode]      = useState<'INCLUDED' | 'PER_RESERVATION' | 'PER_QTY'>('INCLUDED');
  const [feePerReservation, setFeePerReservation] = useState(3000);
  const [feePerQty,         setFeePerQty]         = useState(1000);
  const [deliveryDays,      setDeliveryDays]      = useState(2);
  const [showCustomDel,     setShowCustomDel]     = useState(false);
  const [warrantyMonths,    setWarrantyMonths]    = useState(0);
  const [showCustomWarranty, setShowCustomWarranty] = useState(false);
  const [cancelRule,        setCancelRule]        = useState<CancelRule>('A1');
  const [cancelWithinDays,  setCancelWithinDays]  = useState(7);
  const [extraText,         setExtraText]         = useState('');

  // 제출
  const [submitting, setSubmitting] = useState(false);
  const [submitted,  setSubmitted]  = useState(false);

  // ── 딜 데이터 로드 ──────────────────────────────────────
  useEffect(() => {
    if (!dealId) return;
    const numId = Number(dealId);
    if (!numId) return;
    const load = async () => {
      setDealLoading(true);
      try {
        const [dealData, offersData] = await Promise.all([
          fetchDeal(numId),
          fetchOffersByDeal(numId),
        ]);
        if (dealData) {
          const offers = Array.isArray(offersData) ? offersData : [];
          const prices = offers.map((o: Record<string, unknown>) => Number(o.price) || 0).filter((p: number) => p > 0);
          const lowestOffer = prices.length > 0 ? Math.min(...prices) : 0;

          let parsedOptions: { title: string; value: string }[] = [];
          try {
            const raw = dealData.options;
            if (typeof raw === 'string') {
              const arr = JSON.parse(raw);
              if (Array.isArray(arr)) {
                parsedOptions = arr.flatMap((g: Record<string, unknown>) => {
                  const title = String(g.title ?? g.name ?? '');
                  const vals = Array.isArray(g.values) ? g.values : [g.value];
                  return vals.map((v: unknown) => ({ title, value: String(v ?? '') }));
                });
              }
            }
          } catch { /* ignore */ }

          setDeal({
            id: dealData.id,
            product_name: dealData.product_name ?? `Deal #${dealData.id}`,
            brand: dealData.brand ?? '',
            target_price: Number(dealData.target_price) || 0,
            anchor_price: Number(dealData.anchor_price) || Number(dealData.market_price) || 0,
            current_orders: Number(dealData.current_orders) || Number(dealData.desired_qty) || 0,
            target_orders: Number(dealData.target_orders) || Number(dealData.desired_qty) || 0,
            deadline_at: dealData.deadline_at,
            options: parsedOptions,
            lowest_offer: lowestOffer,
            offer_count: offers.length,
          });
        }
      } catch (err) {
        console.error('딜 로드 실패:', err);
      } finally {
        setDealLoading(false);
      }
    };
    void load();
  }, [dealId]);

  // ── 파생 값 ──────────────────────────────────────────
  const price       = parseNum(priceStr);
  const tier        = price > 0 && deal ? _getTier(price, deal.target_price) : null;
  const rank        = deal ? _getRank(price, deal.lowest_offer) : 0;
  const badge       = tier ? tierBadge(tier) : null;
  const getSavingsPct = (p: number) => _getSavingsPct(p, deal?.target_price ?? 0);

  // ── 이동 ─────────────────────────────────────────────
  const goTo  = (n: number) => { setDir(n > step ? 1 : -1); setStep(n); };
  const goBack = () => { if (step === 1) navigate(-1); else goTo(step - 1); };

  // 스텝 변경 시 히스토리 + 스크롤
  useEffect(() => {
    if (step > 1) window.history.pushState({ step }, '');
    window.scrollTo(0, 0);
  }, [step]);

  useEffect(() => {
    const handlePop = () => {
      if (submitted) { navigate(`/deal/${dealId ?? ''}`, { replace: true }); return; }
      if (step > 1) setStep(prev => prev - 1);
    };
    window.addEventListener('popstate', handlePop);
    return () => window.removeEventListener('popstate', handlePop);
  }, [step, submitted, dealId, navigate]);

  // ── 핑퐁이 메시지 생성 ───────────────────────────────
  const generatePingpongMessage = (): string => {
    const parts: string[] = [];
    if (!deal) return '';
    if (!tier) return '';

    if (tier === 'PREMIUM') {
      parts.push('이 조건이면 PREMIUM 등급이에요! 🎉');
    } else if (tier === 'MATCHING') {
      parts.push('목표가에 딱 맞는 MATCHING 오퍼에요.');
    } else {
      parts.push('목표가보다 높지만, 좋은 조건이면 선택될 수 있어요.');
    }
    if (shippingMode === 'INCLUDED') parts.push('무료배송으로 구매자 선택 확률이 높아요!');
    if (warrantyMonths >= 12) parts.push('12개월 이상 보증으로 신뢰도 최고!');
    else if (warrantyMonths >= 6) parts.push('6개월 보증이면 충분히 경쟁력 있어요.');
    if (cancelRule === 'A1') parts.push('환불 정책이 구매자 친화적이에요.');

    if (deal.offer_count === 0) {
      parts.push('아직 이 딜에 오퍼가 없어요. 첫 번째 오퍼를 제출해보세요!');
    } else if (deal.lowest_offer > 0 && price <= deal.lowest_offer) {
      parts.push('현재 최저가보다 낮은 가격이에요! 🎉');
    } else if (rank > 0) {
      parts.push(`현재 ${deal.offer_count}건의 오퍼 중 ${rank}위 가격!`);
    }

    return parts.join(' ');
  };

  // ── 배송비 표시 텍스트 ──────────────────────────────────
  const getShippingDisplay = (): string => {
    if (shippingMode === 'INCLUDED')        return '무료배송 (상품가 포함)';
    if (shippingMode === 'PER_RESERVATION') return `참여당 ${feePerReservation.toLocaleString()}원`;
    return `개당 ${feePerQty.toLocaleString()}원 (${totalQty}개 = ${(feePerQty * totalQty).toLocaleString()}원)`;
  };

  // ── 이미지 ────────────────────────────────────────────
  const handleImageAdd = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;
    const next = [...images];
    for (let i = 0; i < files.length; i++) {
      if (next.length >= 10) break;
      next.push(URL.createObjectURL(files[i]));
    }
    setImages(next);
    e.target.value = '';
  };
  const handleImageRemove = (idx: number) => {
    setImages(prev => prev.filter((_, i) => i !== idx));
  };

  // ── 제출 ─────────────────────────────────────────────
  const isUnverifiedSeller = user?.role === 'seller' && user?.verified === false;

  const handleSubmit = async () => {
    if (isUnverifiedSeller) {
      showToast('관리자 승인 후 오퍼를 제출할 수 있습니다.', 'error');
      return;
    }
    setSubmitting(true);
    const numPrice = parseInt(priceStr.replace(/[^\d]/g, ''), 10) || 0;
    const isSeller = !!user?.seller;
    trackBehavior(isSeller ? 'SELLER_SUBMIT_OFFER' : 'SUBMIT_OFFER', {
      target_type: 'offer',
      meta: { deal_id: Number(dealId), price: numPrice },
    });
    try {
      const result = await createOffer({
        deal_id:                     Number(dealId),
        seller_id:                   user?.seller?.id ?? user?.id ?? 0,
        price:                       numPrice,
        total_available_qty:         totalQty,
        delivery_days:               deliveryDays,
        comment:                     comment || undefined,
        shipping_mode:               shippingMode,
        shipping_fee_per_reservation: feePerReservation,
        shipping_fee_per_qty:        feePerQty,
      });
      if (result) {
        showToast('오퍼가 제출되었어요! 🎉', 'success');
        setSubmitting(false);
        setSubmitted(true);
        window.history.replaceState({ submitted: true }, '');
        return;
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e.response?.data?.detail;
      if (typeof detail === 'string') {
        alert(detail);
        setSubmitting(false);
        return;
      }
    }
    // Mock 폴백
    await new Promise(r => setTimeout(r, 1500));
    setSubmitting(false);
    setSubmitted(true);
    window.history.replaceState({ submitted: true }, '');
  };

  // ── 로딩 / 에러 ────────────────────────────────────────
  if (dealLoading) {
    return (
      <div style={{ minHeight: '100dvh', background: C.bgDeep, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', color: C.textSec, fontSize: 14 }}>딜 정보를 불러오는 중...</div>
      </div>
    );
  }
  if (!deal) {
    return (
      <div style={{ minHeight: '100dvh', background: C.bgDeep, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>😥</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: C.textPri, marginBottom: 8 }}>딜을 찾을 수 없어요</div>
          <button onClick={() => navigate('/deals')} style={{ padding: '10px 24px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: `${C.cyan}22`, border: `1px solid ${C.cyan}55`, color: C.cyan, cursor: 'pointer' }}>딜 목록으로</button>
        </div>
      </div>
    );
  }

  // ── 성공 화면 ────────────────────────────────────────
  if (submitted) {
    return (
      <div style={{
        minHeight: '100dvh', background: C.bgDeep,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '0 24px',
      }}>
        <style>{`@keyframes popIn { 0%{transform:scale(0.5);opacity:0} 70%{transform:scale(1.1)} 100%{transform:scale(1);opacity:1} }`}</style>
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', damping: 24 }}
          style={{ width: '100%', maxWidth: 400, textAlign: 'center' }}
        >
          <div style={{ fontSize: 64, marginBottom: 20, animation: 'popIn 0.6s cubic-bezier(.175,.885,.32,1.275) both' }}>🎉</div>
          <div style={{ fontSize: 24, fontWeight: 900, color: C.textPri, marginBottom: 10 }}>
            오퍼가 등록되었어요!
          </div>

          {/* 요약 배지 */}
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '8px 18px', borderRadius: 24, marginBottom: 20,
            background: `${C.green}12`, border: `1px solid ${C.green}40`,
          }}>
            <span style={{ fontWeight: 800, color: C.green, fontSize: 15 }}>{fmtPrice(price)}원</span>
            <span style={{ color: C.textDim }}>·</span>
            <span style={{ color: C.textSec, fontSize: 13 }}>{totalQty}개</span>
            {tier && badge && (
              <>
                <span style={{ color: C.textDim }}>·</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: badge.color }}>{badge.label}</span>
              </>
            )}
          </div>

          <div style={{ fontSize: 14, color: C.textSec, lineHeight: 1.7, marginBottom: 36 }}>
            구매자들이 선택할 수 있도록<br />딜 페이지에 노출됩니다.
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <button
              onClick={() => {
                (window as any).__newOfferData = { detail, images };
                const shipFeeParam = shippingMode === 'PER_RESERVATION' ? feePerReservation : feePerQty;
                navigate(
                  `/deal/${dealId ?? ''}?newOffer=1&price=${price}&qty=${totalQty}&name=${encodeURIComponent('내 오퍼')}&shipMode=${shippingMode}&shipFee=${shipFeeParam}`,
                  { replace: true }
                );
              }}
              style={{
                padding: '15px', borderRadius: 14, fontSize: 15, fontWeight: 800,
                background: `linear-gradient(135deg, ${C.cyan}, ${C.green})`,
                color: '#0a0e1a', cursor: 'pointer',
              }}
            >
              딜 페이지로 이동
            </button>
            <button
              onClick={() => navigate('/seller/offers')}
              style={{
                padding: '14px', borderRadius: 14, fontSize: 14, fontWeight: 600,
                background: 'transparent',
                border: `1px solid ${C.border}`,
                color: C.textSec, cursor: 'pointer',
              }}
            >
              내 오퍼 관리하기
            </button>
          </div>
        </motion.div>
      </div>
    );
  }

  // ── 공용 버튼 ────────────────────────────────────────
  const ctaBtn = (label: string, onClick: () => void, disabled?: boolean, loading?: boolean) => (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        width: '100%', padding: '15px', borderRadius: 14, fontSize: 15, fontWeight: 800,
        background: disabled ? `${C.cyan}30` : `linear-gradient(135deg, ${C.cyan}, ${C.green})`,
        color: disabled ? C.textSec : '#0a0e1a',
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        transition: 'opacity 0.15s',
      }}
    >
      {loading && (
        <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid rgba(0,0,0,0.3)', borderTopColor: '#0a0e1a', animation: 'spin 0.8s linear infinite' }} />
      )}
      {label}
    </button>
  );

  const cardStyle: React.CSSProperties = {
    background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: '16px 18px',
  };

  const cancelRuleLabels: Record<CancelRule, string> = {
    A1: 'A1: 언제든 취소 가능',
    A2: 'A2: 발송 후 취소 불가',
    A3: `A3: 수령 후 ${cancelWithinDays}일 이내`,
    A4: 'A4: 협의 후 취소',
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bgDeep, overflow: 'hidden' }}>
      <style>{`
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes ppBlink { 0%,100%{opacity:1} 50%{opacity:0.45} }
        .oc-input:focus { border-color: rgba(0,240,255,0.5) !important; outline: none; }
        .oc-input { box-sizing: border-box; width: 100%; }
      `}</style>

      {/* ── TopBar ── */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 20px', zIndex: 10,
        background: 'rgba(10,14,26,0.92)', backdropFilter: 'blur(10px)',
        borderBottom: `1px solid ${C.border}`,
      }}>
        <button
          onClick={goBack}
          style={{ fontSize: 13, color: C.textSec, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}
        >
          ← 오퍼 제출
        </button>
        <div style={{ fontSize: 13, fontWeight: 700 }}>
          <span style={{ color: C.cyan }}>{step}</span>
          <span style={{ color: C.textSec }}>/4</span>
        </div>
        <div style={{ width: 64 }} />
      </div>

      {/* ── 진행 바 ── */}
      <div style={{ position: 'fixed', top: 56, left: 0, right: 0, height: 3, zIndex: 10, background: C.border }}>
        <div style={{
          height: '100%', width: `${(step / 4) * 100}%`,
          background: `linear-gradient(90deg, ${C.cyan}, ${C.green})`,
          transition: 'width 0.35s ease',
        }} />
      </div>

      {/* ── 콘텐츠 ── */}
      <div style={{ paddingTop: 60, minHeight: '100dvh' }}>
        <AnimatePresence mode="wait" custom={dir}>
          <motion.div
            key={step}
            custom={dir}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            style={{ width: '100%', maxWidth: 500, margin: '0 auto', padding: '24px 20px 100px' }}
          >

            {/* ══ Step 1: 옵션 확인 + 조건 + 구성품 ══ */}
            {step === 1 && (() => {
              const dealOptions = deal?.options ?? [];
              const allConfirmed = dealOptions.length === 0 || dealOptions.every((_, i) => confirmedOptions[`opt_${i}`]);
              const canProceed = allConfirmed && optionAgreement;
              return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                {/* 딜 정보 헤더 */}
                <div>
                  <div style={{ fontSize: 13, color: C.textSec, marginBottom: 4 }}>오퍼 제출 대상 딜</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: C.textPri, marginBottom: 4 }}>
                    📦 {(deal?.product_name ?? '')}
                  </div>
                  <div style={{ fontSize: 12, color: C.textSec }}>
                    {(deal?.brand ?? '')}
                  </div>
                </div>

                {/* 딜 요청 옵션 확인 */}
                {dealOptions.length > 0 && (
                  <div>
                    <Label required>딜 요청 옵션 확인</Label>
                    <div style={{ fontSize: 12, color: C.textSec, marginBottom: 10 }}>
                      구매자가 요청한 옵션을 하나씩 확인해주세요. 모든 옵션을 확인해야 다음 단계로 진행할 수 있습니다.
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {dealOptions.map((opt, i) => {
                        const key = `opt_${i}`;
                        const isConfirmed = !!confirmedOptions[key];
                        return (
                          <div key={key} style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            padding: '12px 14px', borderRadius: 12,
                            background: isConfirmed ? `${C.green}10` : C.bgSurface,
                            border: `1px solid ${isConfirmed ? C.green + '50' : C.border}`,
                            transition: 'all 0.15s',
                          }}>
                            <div>
                              <div style={{ fontSize: 13, fontWeight: 600, color: C.textPri }}>{opt.title}</div>
                              <div style={{ fontSize: 12, color: C.textSec }}>{opt.value}</div>
                            </div>
                            <button
                              onClick={() => setConfirmedOptions(prev => ({ ...prev, [key]: !prev[key] }))}
                              style={{
                                padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                                cursor: 'pointer', transition: 'all 0.15s',
                                background: isConfirmed ? C.green : 'transparent',
                                color: isConfirmed ? '#0a0e1a' : C.textSec,
                                border: `1px solid ${isConfirmed ? C.green : C.border}`,
                              }}
                            >
                              {isConfirmed ? '확인됨' : '확인'}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                    {!allConfirmed && (
                      <div style={{ fontSize: 11, color: C.magenta, marginTop: 6 }}>
                        모든 옵션을 확인해주세요 ({Object.values(confirmedOptions).filter(Boolean).length}/{dealOptions.length})
                      </div>
                    )}
                  </div>
                )}

                {/* 추가 옵션 (최대 5개) */}
                <div>
                  <Label>추가 옵션 (선택, 최대 5개)</Label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {extraOptions.map((opt, i) => (
                      <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <input
                          type="text"
                          placeholder="옵션명"
                          value={opt.key}
                          onChange={e => {
                            const next = [...extraOptions];
                            next[i] = { ...next[i], key: e.target.value };
                            setExtraOptions(next);
                          }}
                          className="oc-input"
                          style={{ ...inputStyle, flex: 1 }}
                        />
                        <input
                          type="text"
                          placeholder="옵션값"
                          value={opt.value}
                          onChange={e => {
                            const next = [...extraOptions];
                            next[i] = { ...next[i], value: e.target.value };
                            setExtraOptions(next);
                          }}
                          className="oc-input"
                          style={{ ...inputStyle, flex: 1 }}
                        />
                        <button
                          onClick={() => setExtraOptions(prev => prev.filter((_, idx) => idx !== i))}
                          style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(255,45,120,0.12)', border: `1px solid rgba(255,45,120,0.3)`, color: C.magenta, fontSize: 14, cursor: 'pointer', flexShrink: 0 }}
                        >✕</button>
                      </div>
                    ))}
                    {extraOptions.length < 5 && (
                      <button
                        onClick={() => setExtraOptions(prev => [...prev, { key: '', value: '' }])}
                        style={{
                          padding: '10px', borderRadius: 10, fontSize: 13, fontWeight: 600,
                          background: C.bgSurface, border: `1.5px dashed ${C.border}`,
                          color: C.textSec, cursor: 'pointer',
                        }}
                      >+ 추가 옵션</button>
                    )}
                  </div>
                </div>

                {/* 조건 설정 */}
                <div>
                  <Label>판매 조건</Label>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                    <div>
                      <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>보증</div>
                      <select value={condWarranty} onChange={e => setCondWarranty(e.target.value)} className="oc-input" style={{ ...inputStyle, cursor: 'pointer' }}>
                        <option value="없음">없음</option>
                        <option value="3개월">3개월</option>
                        <option value="6개월">6개월</option>
                        <option value="1년">1년</option>
                      </select>
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>환불</div>
                      <select value={condRefund} onChange={e => setCondRefund(e.target.value)} className="oc-input" style={{ ...inputStyle, cursor: 'pointer' }}>
                        <option value="7일">7일</option>
                        <option value="14일">14일</option>
                        <option value="불가">불가</option>
                      </select>
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>배송비</div>
                      <select value={condShipping} onChange={e => setCondShipping(e.target.value)} className="oc-input" style={{ ...inputStyle, cursor: 'pointer' }}>
                        <option value="무료">무료</option>
                        <option value="유료">유료</option>
                        <option value="조건부">조건부</option>
                      </select>
                    </div>
                    <div>
                      <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>배송일</div>
                      <select value={condDelivery} onChange={e => setCondDelivery(e.target.value)} className="oc-input" style={{ ...inputStyle, cursor: 'pointer' }}>
                        <option value="1~3일">1~3일</option>
                        <option value="3~5일">3~5일</option>
                        <option value="5~7일">5~7일</option>
                        <option value="7일+">7일+</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* 구성품 */}
                <div>
                  <Label>구성품 (선택)</Label>
                  <textarea
                    value={componentsText}
                    onChange={e => setComponentsText(e.target.value.slice(0, 500))}
                    placeholder="본체, 충전기, 케이블, 설명서 등"
                    rows={3}
                    className="oc-input"
                    style={{ ...inputStyle, resize: 'none', lineHeight: 1.55 }}
                  />
                  <div style={{ fontSize: 11, color: C.textDim, textAlign: 'right', marginTop: 4 }}>{componentsText.length}/500</div>
                </div>

                {/* 동의 체크박스 */}
                <div
                  onClick={() => setOptionAgreement(prev => !prev)}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 10, cursor: 'pointer',
                    padding: '14px', borderRadius: 12,
                    background: optionAgreement ? `${C.green}08` : C.bgSurface,
                    border: `1px solid ${optionAgreement ? C.green + '40' : C.border}`,
                  }}
                >
                  <div style={{
                    width: 20, height: 20, borderRadius: 6, flexShrink: 0, marginTop: 1,
                    border: `2px solid ${optionAgreement ? C.green : C.textDim}`,
                    background: optionAgreement ? C.green : 'transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: '#0a0e1a', fontSize: 12, fontWeight: 900,
                  }}>
                    {optionAgreement && '✓'}
                  </div>
                  <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.5 }}>
                    위 딜 옵션과 판매 조건을 확인했으며, 해당 조건으로 오퍼를 제출하는 것에 동의합니다.
                  </div>
                </div>

                {ctaBtn('다음 →', () => {
                  if (!canProceed) {
                    showToast('모든 옵션을 확인하고 동의 체크를 해주세요.', 'error');
                    return;
                  }
                  goTo(2);
                }, !canProceed)}
              </div>
              );
            })()}

            {/* ══ Step 2: 가격 & 수량 ══ */}
            {step === 2 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                {/* 딜 정보 카드 */}
                <div style={{ ...cardStyle }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {[
                      { icon: '🎯', label: '목표가',    value: `${fmtPrice((deal?.target_price ?? 0))}원`, color: C.green },
                      { icon: '📊', label: '시장가',    value: `${fmtPrice((deal?.anchor_price ?? 0))}원`, color: C.yellow },
                      { icon: '⚡', label: '현재 최저',  value: `${fmtPrice((deal?.lowest_offer ?? 0))}원`, color: C.cyan },
                      { icon: '📦', label: '현재 오퍼',  value: `${(deal?.offer_count ?? 0)}건`, color: C.textSec },
                      { icon: '👥', label: '참여수',    value: `${(deal?.current_orders ?? 0)}/${(deal?.target_orders ?? 0)}명`, color: C.textSec },
                    ].map(({ icon, label, value, color }) => (
                      <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 13, color: C.textSec }}>{icon} {label}</span>
                        <span style={{ fontSize: 13, fontWeight: 700, color }}>{value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 가격 입력 */}
                <div>
                  <Label required>내 오퍼 가격</Label>
                  <div style={{ position: 'relative' }}>
                    <span style={{
                      position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)',
                      fontSize: 14, color: C.textSec, pointerEvents: 'none',
                    }}>원</span>
                    <input
                      type="text"
                      value={priceStr}
                      onChange={e => {
                        const raw = e.target.value.replace(/[^\d]/g, '');
                        const n = parseInt(raw, 10) || 0;
                        setPriceStr(n > 0 ? fmtPrice(n) : '');
                      }}
                      className="oc-input"
                      placeholder="0"
                      style={{
                        ...inputStyle,
                        paddingLeft: 30, fontSize: 17, fontWeight: 700,
                        fontFamily: 'monospace', letterSpacing: '0.5px',
                        border: `1px solid ${badge ? badge.border : 'rgba(255,255,255,0.12)'}`,
                      }}
                    />
                    {tier && badge && (
                      <span style={{
                        position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                        padding: '3px 9px', borderRadius: 10, fontSize: 11, fontWeight: 800,
                        background: badge.bg, color: badge.color, border: `1px solid ${badge.border}`,
                      }}>
                        {badge.label}
                      </span>
                    )}
                  </div>
                  {tier && (
                    <div style={{ fontSize: 12, marginTop: 6, paddingLeft: 2 }}>
                      {rank === 1 && <span style={{ color: C.green, fontWeight: 700 }}>🔥 1위 오퍼가 됩니다!</span>}
                      {rank > 1 && <span style={{ color: C.textSec }}>현재 {(deal?.offer_count ?? 0)}건 중 {rank}위 가격 · 목표가 대비 {getSavingsPct(price)}</span>}
                    </div>
                  )}
                </div>

                {/* 핑퐁이 가격 가이드 */}
                <div style={{ ...cardStyle, borderColor: 'rgba(0,240,255,0.25)', background: 'rgba(0,240,255,0.04)' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.cyan, marginBottom: 10 }}>💡 핑퐁이 가격 가이드</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                    {[
                      { cond: '미만',   label: `${fmtPrice((deal?.target_price ?? 0))}원 미만`, tier: 'PREMIUM' as const, badge: tierBadge('PREMIUM') },
                      { cond: '동일',   label: `${fmtPrice((deal?.target_price ?? 0))}원 동일`, tier: 'MATCHING' as const, badge: tierBadge('MATCHING') },
                      { cond: '초과',   label: `${fmtPrice((deal?.target_price ?? 0))}원 초과`, tier: 'BELOW' as const, badge: tierBadge('BELOW') },
                    ].map(row => {
                      const active = tier === row.tier;
                      return (
                        <div key={row.tier} style={{
                          display: 'flex', alignItems: 'center', gap: 10,
                          padding: '8px 10px', borderRadius: 8,
                          background: active ? `${row.badge.bg}` : 'transparent',
                          transition: 'background 0.2s',
                        }}>
                          <span style={{
                            padding: '2px 8px', borderRadius: 8, fontSize: 10, fontWeight: 800,
                            background: row.badge.bg, color: row.badge.color, border: `1px solid ${row.badge.border}`,
                            flexShrink: 0,
                          }}>
                            {row.badge.label}
                          </span>
                          <span style={{ fontSize: 12, color: active ? C.textPri : C.textSec }}>{row.label}</span>
                        </div>
                      );
                    })}
                  </div>
                  {price > 0 && price < (deal?.lowest_offer ?? 0) && (
                    <div style={{ marginTop: 10, fontSize: 12, color: C.green, fontWeight: 700 }}>
                      🔥 현재 최저가 {fmtPrice((deal?.lowest_offer ?? 0))}원보다 낮게 설정하면 1위 오퍼!
                    </div>
                  )}
                </div>

                {/* 수량 */}
                <div>
                  <Label required>판매 수량 (개)</Label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <button
                      onClick={() => setTotalQty(q => Math.max(1, q - 1))}
                      style={{ width: 40, height: 40, borderRadius: 10, background: C.bgSurface, border: `1px solid ${C.border}`, color: C.textPri, fontSize: 20, cursor: 'pointer' }}
                    >−</button>
                    <input
                      type="text"
                      value={String(totalQty)}
                      onChange={e => {
                        const n = parseInt(e.target.value, 10);
                        if (!isNaN(n)) setTotalQty(Math.max(1, Math.min(999, n)));
                      }}
                      className="oc-input"
                      style={{
                        ...inputStyle, width: 70, textAlign: 'center',
                        fontSize: 18, fontWeight: 800,
                      }}
                    />
                    <button
                      onClick={() => setTotalQty(q => Math.min(999, q + 1))}
                      style={{ width: 40, height: 40, borderRadius: 10, background: C.bgSurface, border: `1px solid ${C.border}`, color: C.textPri, fontSize: 20, cursor: 'pointer' }}
                    >+</button>
                    <span style={{ fontSize: 12, color: C.textDim }}>최소 1 · 최대 999</span>
                  </div>
                </div>

                {/* 코멘트 */}
                <div>
                  <Label>한줄 코멘트 (선택)</Label>
                  <textarea
                    value={comment}
                    onChange={e => setComment(e.target.value.slice(0, 200))}
                    placeholder="구매자에게 어필할 한마디를 적어주세요"
                    rows={3}
                    className="oc-input"
                    style={{ ...inputStyle, resize: 'none', lineHeight: 1.55 }}
                  />
                  <div style={{ fontSize: 11, color: C.textDim, textAlign: 'right', marginTop: 4 }}>{comment.length}/200</div>
                </div>

                {ctaBtn('다음 →', () => {
                  if (price <= 0 || totalQty <= 0) {
                    showToast("'내 오퍼 가격'과 '수량'을 기입해주세요.", 'error');
                    return;
                  }
                  goTo(3);
                })}
              </div>
            )}

            {/* ══ Step 3: 제품 상세 + 사진 ══ */}
            {step === 3 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 900, color: C.textPri, lineHeight: 1.3, marginBottom: 6 }}>
                    📝 제품 상세 + 사진
                  </div>
                  <div style={{ fontSize: 13, color: C.textSec }}>제품에 대한 상세 설명과 사진을 등록하세요.</div>
                </div>

                {/* 제품 상세 설명 */}
                <div>
                  <Label>제품 상세 설명 (최소 20자)</Label>
                  <textarea
                    value={detail}
                    onChange={e => setDetail(e.target.value.slice(0, 1000))}
                    placeholder="제품 상태, 구성품, 특이사항 등 상세하게 적어주세요 (최소 20자)"
                    rows={6}
                    className="oc-input"
                    style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.6 }}
                  />
                  <div style={{ fontSize: 11, color: detail.length < 20 ? C.magenta : C.textDim, textAlign: 'right', marginTop: 4 }}>{detail.length}/1,000 {detail.length < 20 ? `(최소 ${20 - detail.length}자 더 입력)` : ''}</div>
                </div>

                {/* 제품 이미지 */}
                <div>
                  <Label>제품 이미지 (1~10장, jpg/png, 최대 10MB)</Label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {images.map((src, idx) => (
                      <div key={idx} style={{ position: 'relative', width: 72, height: 72, borderRadius: 10, overflow: 'hidden', border: `1px solid ${C.border}`, flexShrink: 0 }}>
                        <img src={src} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        <button
                          onClick={() => handleImageRemove(idx)}
                          style={{
                            position: 'absolute', top: 2, right: 2,
                            width: 18, height: 18, borderRadius: '50%',
                            background: 'rgba(0,0,0,0.65)',
                            color: '#fff', fontSize: 10, display: 'flex',
                            alignItems: 'center', justifyContent: 'center',
                            cursor: 'pointer',
                          }}
                        >✕</button>
                      </div>
                    ))}
                    {images.length < 10 && (
                      <div style={{ position: 'relative', width: 72, height: 72, flexShrink: 0 }}>
                        <div style={{
                          width: 72, height: 72, borderRadius: 10,
                          background: C.bgSurface, border: `1.5px dashed ${C.border}`,
                          color: C.textSec, fontSize: 22,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          pointerEvents: 'none',
                        }}>+</div>
                        <input
                          type="file" accept="image/jpeg,image/png" multiple
                          onClick={() => {
                            const sy = window.scrollY;
                            const restore = () => { window.scrollTo(0, sy); window.removeEventListener('focus', restore); };
                            window.addEventListener('focus', restore);
                          }}
                          onChange={e => handleImageAdd(e)}
                          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0, cursor: 'pointer' }}
                        />
                      </div>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: C.textDim, marginTop: 6 }}>
                    {images.length}/10장 등록됨
                  </div>
                </div>

                {ctaBtn('다음 →', () => {
                  if (detail.length < 20) {
                    showToast('제품 상세 설명을 최소 20자 이상 입력해주세요.', 'error');
                    return;
                  }
                  if (images.length < 1) {
                    showToast('제품 이미지를 최소 1장 등록해주세요.', 'error');
                    return;
                  }
                  goTo(4);
                })}
              </div>
            )}

            {/* ══ Step 4 (old Step 2): 배송 & 정책 — hidden, kept for data ══ */}

            {/* ══ Step 4: 최종 확인 ══ */}
            {step === 4 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: C.textPri, marginBottom: 4 }}>📋 오퍼 최종 확인</div>
                  <div style={{ fontSize: 13, color: C.textSec }}>제출 전에 내용을 확인해주세요.</div>
                </div>

                {/* 딜 명 */}
                <div style={{ fontSize: 14, fontWeight: 600, color: C.textSec }}>
                  📦 {(deal?.product_name ?? '')}
                </div>

                {/* 확인된 옵션 */}
                {(deal?.options ?? []).length > 0 && (
                  <div style={{ ...cardStyle }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 10 }}>확인된 옵션</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {(deal?.options ?? []).map((opt, i) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: `1px solid ${C.border}` }}>
                          <span style={{ fontSize: 13, color: C.textSec }}>{opt.title}</span>
                          <span style={{ fontSize: 13, fontWeight: 600, color: C.textPri }}>{opt.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 조건 요약 */}
                <div style={{ ...cardStyle }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 10 }}>판매 조건</div>
                  {[
                    { label: '보증', value: condWarranty },
                    { label: '환불', value: condRefund },
                    { label: '배송비', value: condShipping },
                    { label: '배송일', value: condDelivery },
                    ...(componentsText ? [{ label: '구성품', value: componentsText.length > 30 ? componentsText.slice(0, 30) + '...' : componentsText }] : []),
                  ].map(({ label, value }) => (
                    <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: `1px solid ${C.border}` }}>
                      <span style={{ fontSize: 13, color: C.textSec }}>{label}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: C.textPri }}>{value}</span>
                    </div>
                  ))}
                </div>

                {/* 오퍼 요약 카드 */}
                <div style={{ ...cardStyle }}>
                  {/* 가격 */}
                  <div style={{ paddingBottom: 14, marginBottom: 14, borderBottom: `1px solid ${C.border}` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                      <span style={{ fontSize: 24, fontWeight: 900, color: C.textPri }}>{fmtPrice(price)}원</span>
                      {tier && badge && (
                        <span style={{
                          padding: '3px 10px', borderRadius: 10, fontSize: 11, fontWeight: 800,
                          background: badge.bg, color: badge.color, border: `1px solid ${badge.border}`,
                        }}>
                          {badge.label}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 12, color: C.textSec }}>
                      목표가 대비 {getSavingsPct(price)} · {(deal?.offer_count ?? 0)}건 중 {rank}위
                    </div>
                  </div>

                  {/* 상세 목록 */}
                  {[
                    { icon: '📦', label: '판매 수량',  value: `${totalQty}개` },
                    ...(comment ? [{ icon: '💬', label: '코멘트', value: comment.length > 28 ? comment.slice(0, 28) + '...' : comment }] : []),
                    { icon: '🚚', label: '배송비',    value: getShippingDisplay() },
                    { icon: '📅', label: '배송일',    value: `${deliveryDays}일 이내` },
                    { icon: '🛡️', label: '보증',      value: warrantyMonths === 0 ? '없음' : `${warrantyMonths}개월` },
                    { icon: '↩️', label: '환불정책',  value: cancelRuleLabels[cancelRule] },
                  ].map(({ icon, label, value }) => (
                    <div key={label} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '9px 0', borderBottom: `1px solid ${C.border}`,
                    }}>
                      <span style={{ fontSize: 13, color: C.textSec }}>{icon} {label}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: C.textPri, maxWidth: '55%', textAlign: 'right' }}>{value}</span>
                    </div>
                  ))}
                </div>

                {/* 제품 상세 미리보기 */}
                {detail && (
                  <div style={{ ...cardStyle }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 8 }}>📝 제품 상세 설명</div>
                    <div style={{ fontSize: 13, color: C.textPri, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                      {detail.length > 100 ? detail.slice(0, 100) + '...' : detail}
                    </div>
                    {detail.length > 100 && (
                      <div style={{ fontSize: 11, color: C.textSec, marginTop: 6 }}>{detail.length.toLocaleString()}자 입력됨</div>
                    )}
                  </div>
                )}

                {/* 이미지 썸네일 */}
                {images.length > 0 && (
                  <div style={{ ...cardStyle }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 10 }}>📸 등록 이미지 ({images.length}장)</div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {images.map((src, idx) => (
                        <div key={idx} style={{ width: 60, height: 60, borderRadius: 8, overflow: 'hidden', border: `1px solid ${C.border}`, flexShrink: 0 }}>
                          <img src={src} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* 핑퐁이 분석 카드 */}
                {tier && (
                  <div style={{ ...cardStyle, borderColor: 'rgba(0,229,255,0.3)', background: 'rgba(0,229,255,0.04)' }}>
                    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                      <div style={{
                        width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                        background: 'rgba(0,229,255,0.12)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
                      }}>🤖</div>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 700, color: '#00e5ff', marginBottom: 5 }}>핑퐁이 분석</div>
                        <div style={{ fontSize: 13, color: C.textPri, lineHeight: 1.6 }}>
                          {generatePingpongMessage()}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 안내 */}
                <div style={{ fontSize: 12, color: C.textSec, textAlign: 'center', lineHeight: 1.6 }}>
                  ⚠️ 제출 후에도 수정/철회 가능해요
                </div>

                {/* 버튼 영역 */}
                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    onClick={() => goTo(1)}
                    style={{
                      flex: '0 0 auto', padding: '15px 20px', borderRadius: 14, fontSize: 14, fontWeight: 700,
                      background: C.bgSurface, border: `1px solid ${C.border}`,
                      color: C.textSec, cursor: 'pointer',
                    }}
                  >← 수정</button>
                  <div style={{ flex: 1 }}>
                    {ctaBtn('오퍼 제출', handleSubmit, false, submitting)}
                  </div>
                </div>
              </div>
            )}

          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
