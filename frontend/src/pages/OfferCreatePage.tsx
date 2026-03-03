import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';
import { createOffer } from '../api/offerApi';
import { showToast } from '../components/common/Toast';

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

// ── Mock 딜 정보 ─────────────────────────────────────────
const MOCK_DEAL = {
  id: 15,
  product_name: '에어팟 프로 2세대 (USB-C)',
  brand: 'Apple',
  target_price: 279000,
  anchor_price: 349000,
  current_orders: 32,
  target_orders: 100,
  deadline_at: new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString(),
  options: [
    { title: '색상', value: '블랙' },
    { title: '용량', value: '256GB' },
  ],
  lowest_offer: 275000,
  offer_count: 12,
};

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
];

const DELIVERY_CHIPS = [1, 2, 3] as const;

// ── 헬퍼 ─────────────────────────────────────────────────
const fmtPrice  = (n: number) => n > 0 ? n.toLocaleString('ko-KR') : '';
const parseNum  = (s: string) => parseInt(s.replace(/[^\d]/g, ''), 10) || 0;

const getTier = (p: number): 'PREMIUM' | 'MATCHING' | 'BELOW' => {
  if (p < MOCK_DEAL.target_price)  return 'PREMIUM';
  if (p === MOCK_DEAL.target_price) return 'MATCHING';
  return 'BELOW';
};

const getSavingsPct = (p: number): string => {
  if (p <= 0) return '';
  const diff = MOCK_DEAL.target_price - p;
  const pct  = Math.abs((diff / MOCK_DEAL.target_price) * 100).toFixed(1);
  return diff > 0 ? `-${pct}%` : `+${pct}%`;
};

const getRank = (p: number): number => {
  if (p <= 0) return 0;
  if (p <= MOCK_DEAL.lowest_offer) return 1;
  return Math.min(13, Math.floor((p - MOCK_DEAL.lowest_offer) / 5000) + 2);
};

const tierBadge = (tier: ReturnType<typeof getTier>) => {
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

  const [step, setStep] = useState(1);
  const [dir,  setDir]  = useState(1);

  // Step 1: 가격 & 수량
  const [priceStr,  setPriceStr]  = useState('');
  const [totalQty,  setTotalQty]  = useState(20);
  const [comment,   setComment]   = useState('');
  const [detail,    setDetail]    = useState('');
  const [images,    setImages]    = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 2: 배송 & 정책
  const [shippingMode,      setShippingMode]      = useState<'INCLUDED' | 'PER_RESERVATION' | 'PER_QTY'>('INCLUDED');
  const [feePerReservation, setFeePerReservation] = useState(3000);
  const [feePerQty,         setFeePerQty]         = useState(1000);
  const [deliveryDays,      setDeliveryDays]      = useState(2);
  const [showCustomDel,     setShowCustomDel]     = useState(false);
  const [warrantyMonths,    setWarrantyMonths]    = useState(0);
  const [cancelRule,        setCancelRule]        = useState<CancelRule>('A1');
  const [cancelWithinDays,  setCancelWithinDays]  = useState(7);
  const [extraText,         setExtraText]         = useState('');

  // 제출
  const [submitting, setSubmitting] = useState(false);
  const [submitted,  setSubmitted]  = useState(false);

  // ── 파생 값 ──────────────────────────────────────────
  const price       = parseNum(priceStr);
  const tier        = price > 0 ? getTier(price) : null;
  const rank        = getRank(price);
  const badge       = tier ? tierBadge(tier) : null;

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
    if (!tier) return '';

    if (tier === 'PREMIUM') {
      parts.push('이 조건이면 PREMIUM 등급이에요! 🎉');
    } else if (tier === 'MATCHING') {
      parts.push('목표가에 딱 맞는 MATCHING 오퍼에요.');
    } else {
      parts.push('목표가보다 높지만, 좋은 조건이면 선택될 수 있어요.');
    }
    if (shippingMode === 'INCLUDED') parts.push('무료배송으로 구매자 선택 확률이 높아요!');
    if (warrantyMonths >= 12) parts.push('12개월 보증으로 신뢰도 최고!');
    else if (warrantyMonths >= 6) parts.push('6개월 보증이면 충분히 경쟁력 있어요.');
    if (cancelRule === 'A1') parts.push('환불 정책이 구매자 친화적이에요.');
    if (rank > 0) parts.push(`현재 ${MOCK_DEAL.offer_count}건의 오퍼 중 ${rank}위 가격!`);

    return parts.join(' ');
  };

  // ── 배송비 표시 텍스트 ──────────────────────────────────
  const getShippingDisplay = (): string => {
    if (shippingMode === 'INCLUDED')        return '무료배송 (상품가 포함)';
    if (shippingMode === 'PER_RESERVATION') return `참여당 ₩${feePerReservation.toLocaleString()}`;
    return `개당 ₩${feePerQty.toLocaleString()} (${totalQty}개 = ₩${(feePerQty * totalQty).toLocaleString()})`;
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
  const handleSubmit = async () => {
    setSubmitting(true);
    const numPrice = parseInt(priceStr.replace(/[^\d]/g, ''), 10) || 0;
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
            <span style={{ fontWeight: 800, color: C.green, fontSize: 15 }}>₩{fmtPrice(price)}</span>
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
          <span style={{ color: C.textSec }}>/3</span>
        </div>
        <div style={{ width: 64 }} />
      </div>

      {/* ── 진행 바 ── */}
      <div style={{ position: 'fixed', top: 56, left: 0, right: 0, height: 3, zIndex: 10, background: C.border }}>
        <div style={{
          height: '100%', width: `${(step / 3) * 100}%`,
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

            {/* ══ Step 1: 가격 & 수량 ══ */}
            {step === 1 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                {/* 딜 정보 헤더 */}
                <div>
                  <div style={{ fontSize: 13, color: C.textSec, marginBottom: 4 }}>오퍼 제출 대상 딜</div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: C.textPri, marginBottom: 4 }}>
                    📦 {MOCK_DEAL.product_name}
                  </div>
                  <div style={{ fontSize: 12, color: C.textSec }}>
                    {MOCK_DEAL.brand}
                    {MOCK_DEAL.options.map(o => ` · ${o.title}: ${o.value}`).join('')}
                  </div>
                </div>

                {/* 딜 정보 카드 */}
                <div style={{ ...cardStyle }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {[
                      { icon: '🎯', label: '목표가',    value: `₩${fmtPrice(MOCK_DEAL.target_price)}`, color: C.green },
                      { icon: '📊', label: '시장가',    value: `₩${fmtPrice(MOCK_DEAL.anchor_price)}`, color: C.yellow },
                      { icon: '⚡', label: '현재 최저',  value: `₩${fmtPrice(MOCK_DEAL.lowest_offer)}`, color: C.cyan },
                      { icon: '📦', label: '현재 오퍼',  value: `${MOCK_DEAL.offer_count}건`, color: C.textSec },
                      { icon: '👥', label: '참여수',    value: `${MOCK_DEAL.current_orders}/${MOCK_DEAL.target_orders}명`, color: C.textSec },
                    ].map(({ icon, label, value, color }) => (
                      <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 13, color: C.textSec }}>{icon} {label}</span>
                        <span style={{ fontSize: 13, fontWeight: 700, color }}>{value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 구매자 목표가 근거 */}
                <div style={{ ...cardStyle, borderColor: 'rgba(255,225,86,0.25)', background: 'rgba(255,225,86,0.04)' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#ffe156', marginBottom: 10 }}>💡 구매자 목표가 근거</div>
                  <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.65, marginBottom: 10 }}>
                    "네이버 쇼핑에서 해당 모델이 265,000원에 판매되는 것을 확인했습니다. 해당 가격이 충분히 현실적인 목표가라고 판단합니다."
                  </div>
                  <button
                    onClick={() => showToast('이미지 미리보기 준비 중입니다', 'info')}
                    style={{ fontSize: 12, color: C.textSec, background: C.bgSurface, border: `1px solid ${C.border}`, borderRadius: 8, padding: '5px 12px', cursor: 'pointer' }}
                  >📷 증빙 이미지 2장 보기</button>
                </div>

                {/* 가격 입력 */}
                <div>
                  <Label required>내 오퍼 가격</Label>
                  <div style={{ position: 'relative' }}>
                    <span style={{
                      position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)',
                      fontSize: 14, color: C.textSec, pointerEvents: 'none',
                    }}>₩</span>
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
                      {rank > 1 && <span style={{ color: C.textSec }}>현재 {MOCK_DEAL.offer_count}건 중 {rank}위 가격 · 목표가 대비 {getSavingsPct(price)}</span>}
                    </div>
                  )}
                </div>

                {/* 핑퐁이 가격 가이드 */}
                <div style={{ ...cardStyle, borderColor: 'rgba(0,240,255,0.25)', background: 'rgba(0,240,255,0.04)' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.cyan, marginBottom: 10 }}>💡 핑퐁이 가격 가이드</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                    {[
                      { cond: '미만',   label: `₩${fmtPrice(MOCK_DEAL.target_price)} 미만`, tier: 'PREMIUM' as const, badge: tierBadge('PREMIUM') },
                      { cond: '동일',   label: `₩${fmtPrice(MOCK_DEAL.target_price)} 동일`, tier: 'MATCHING' as const, badge: tierBadge('MATCHING') },
                      { cond: '초과',   label: `₩${fmtPrice(MOCK_DEAL.target_price)} 초과`, tier: 'BELOW' as const, badge: tierBadge('BELOW') },
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
                  {price > 0 && price < MOCK_DEAL.lowest_offer && (
                    <div style={{ marginTop: 10, fontSize: 12, color: C.green, fontWeight: 700 }}>
                      🔥 현재 최저가 ₩{fmtPrice(MOCK_DEAL.lowest_offer)}보다 낮게 설정하면 1위 오퍼!
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

                {/* 제품 상세 설명 */}
                <div>
                  <Label>📝 제품 상세 설명 (선택)</Label>
                  <textarea
                    value={detail}
                    onChange={e => setDetail(e.target.value.slice(0, 5000))}
                    placeholder="제품 상태, 구성품, 특이사항 등 상세하게 적어주세요"
                    rows={6}
                    className="oc-input"
                    style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.6 }}
                  />
                  <div style={{ fontSize: 11, color: C.textDim, textAlign: 'right', marginTop: 4 }}>{detail.length}/5,000</div>
                </div>

                {/* 제품 이미지 */}
                <div>
                  <Label>📸 제품 이미지 (최대 10장, 선택)</Label>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={handleImageAdd}
                    style={{ display: 'none' }}
                  />
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
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        style={{
                          width: 72, height: 72, borderRadius: 10, flexShrink: 0,
                          background: C.bgSurface, border: `1.5px dashed ${C.border}`,
                          color: C.textSec, fontSize: 22, cursor: 'pointer',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}
                      >+</button>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: C.textDim, marginTop: 6 }}>
                    {images.length}/10장 등록됨
                  </div>
                </div>

                {ctaBtn('다음 →', () => goTo(2), price <= 0)}
              </div>
            )}

            {/* ══ Step 2: 배송 & 정책 ══ */}
            {step === 2 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 900, color: C.textPri, lineHeight: 1.3, marginBottom: 6 }}>
                    🚚 배송 & 정책
                  </div>
                  <div style={{ fontSize: 13, color: C.textSec }}>구매자에게 보여줄 배송 및 취소 정책을 설정하세요.</div>
                </div>

                {/* Phase 2 안내 */}
                <div style={{
                  padding: '12px 14px',
                  background: 'rgba(0,240,255,0.06)',
                  border: '1px solid rgba(0,240,255,0.18)',
                  borderRadius: 12,
                  fontSize: 13, color: C.cyan, lineHeight: 1.6,
                }}>
                  💡 판매자 프로필에서 기본 배송·환불 조건을 설정하면, 오퍼 생성 시 자동으로 채워집니다.
                  <span style={{ color: C.textDim }}> (Phase 2 오픈 예정)</span>
                </div>

                {/* 배송비 — 3가지 모드 */}
                <div>
                  <Label>배송비</Label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

                    {/* INCLUDED */}
                    <div
                      onClick={() => setShippingMode('INCLUDED')}
                      style={{ display: 'flex', alignItems: 'flex-start', gap: 12, cursor: 'pointer', padding: '12px 14px', borderRadius: 12, background: shippingMode === 'INCLUDED' ? `${C.green}10` : C.bgSurface, border: `1px solid ${shippingMode === 'INCLUDED' ? C.green + '50' : C.border}`, transition: 'all 0.15s' }}
                    >
                      <div style={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0, marginTop: 2, border: `2px solid ${shippingMode === 'INCLUDED' ? C.green : C.textDim}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {shippingMode === 'INCLUDED' && <div style={{ width: 9, height: 9, borderRadius: '50%', background: C.green }} />}
                      </div>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: C.textPri }}>무료배송 (상품가 포함)</div>
                        <div style={{ fontSize: 12, color: C.textSec }}>추가 배송비 없이 상품가에 포함</div>
                      </div>
                    </div>

                    {/* PER_RESERVATION */}
                    <div
                      onClick={() => setShippingMode('PER_RESERVATION')}
                      style={{ display: 'flex', alignItems: 'flex-start', gap: 12, cursor: 'pointer', padding: '12px 14px', borderRadius: 12, background: shippingMode === 'PER_RESERVATION' ? `${C.green}10` : C.bgSurface, border: `1px solid ${shippingMode === 'PER_RESERVATION' ? C.green + '50' : C.border}`, transition: 'all 0.15s' }}
                    >
                      <div style={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0, marginTop: 2, border: `2px solid ${shippingMode === 'PER_RESERVATION' ? C.green : C.textDim}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {shippingMode === 'PER_RESERVATION' && <div style={{ width: 9, height: 9, borderRadius: '50%', background: C.green }} />}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 14, fontWeight: 600, color: C.textPri }}>참여당 고정 배송비</div>
                        <div style={{ fontSize: 12, color: C.textSec }}>참여 1건당 동일한 배송비</div>
                        {shippingMode === 'PER_RESERVATION' && (
                          <div style={{ marginTop: 8, position: 'relative' }}>
                            <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.textSec, fontSize: 14, pointerEvents: 'none' }}>₩</span>
                            <input
                              type="number" min={0}
                              value={feePerReservation}
                              onChange={e => setFeePerReservation(Math.max(0, parseInt(e.target.value) || 0))}
                              onClick={e => e.stopPropagation()}
                              className="oc-input"
                              style={{ ...inputStyle, paddingLeft: 30 }}
                            />
                          </div>
                        )}
                      </div>
                    </div>

                    {/* PER_QTY */}
                    <div
                      onClick={() => setShippingMode('PER_QTY')}
                      style={{ display: 'flex', alignItems: 'flex-start', gap: 12, cursor: 'pointer', padding: '12px 14px', borderRadius: 12, background: shippingMode === 'PER_QTY' ? `${C.green}10` : C.bgSurface, border: `1px solid ${shippingMode === 'PER_QTY' ? C.green + '50' : C.border}`, transition: 'all 0.15s' }}
                    >
                      <div style={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0, marginTop: 2, border: `2px solid ${shippingMode === 'PER_QTY' ? C.green : C.textDim}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {shippingMode === 'PER_QTY' && <div style={{ width: 9, height: 9, borderRadius: '50%', background: C.green }} />}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 14, fontWeight: 600, color: C.textPri }}>수량별 배송비</div>
                        <div style={{ fontSize: 12, color: C.textSec }}>구매 수량 1개당 배송비 부과</div>
                        {shippingMode === 'PER_QTY' && (
                          <>
                            <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                              <div style={{ flex: 1, position: 'relative' }}>
                                <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.textSec, fontSize: 14, pointerEvents: 'none' }}>₩</span>
                                <input
                                  type="number" min={0}
                                  value={feePerQty}
                                  onChange={e => setFeePerQty(Math.max(0, parseInt(e.target.value) || 0))}
                                  onClick={e => e.stopPropagation()}
                                  className="oc-input"
                                  style={{ ...inputStyle, paddingLeft: 30 }}
                                />
                              </div>
                              <span style={{ fontSize: 13, color: C.textSec, flexShrink: 0 }}>/ 개</span>
                            </div>
                            <div style={{ marginTop: 6, fontSize: 12, color: C.cyan }}>
                              💡 {totalQty}개 참여 시 배송비: ₩{(feePerQty * totalQty).toLocaleString()}
                            </div>
                          </>
                        )}
                      </div>
                    </div>

                  </div>
                </div>

                {/* 배송 소요일 */}
                <div>
                  <Label>배송 소요일</Label>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {DELIVERY_CHIPS.map(d => (
                      <Chip key={d} active={deliveryDays === d && !showCustomDel} onClick={() => { setDeliveryDays(d); setShowCustomDel(false); }}>
                        {d}일
                      </Chip>
                    ))}
                    <Chip active={showCustomDel} onClick={() => { setShowCustomDel(true); if (!showCustomDel && deliveryDays < 5) setDeliveryDays(5); }}>
                      5일+
                    </Chip>
                  </div>
                  {showCustomDel && (
                    <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10 }}>
                      <input
                        type="number"
                        min={5} max={14}
                        value={deliveryDays}
                        onChange={e => setDeliveryDays(Math.max(5, Math.min(14, parseInt(e.target.value) || 5)))}
                        className="oc-input"
                        style={{ ...inputStyle, width: 90, textAlign: 'center' }}
                      />
                      <span style={{ fontSize: 13, color: C.textSec }}>일 이내 (최대 14일)</span>
                    </div>
                  )}
                </div>

                {/* 보증 기간 */}
                <div>
                  <Label>보증 기간</Label>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {WARRANTY_OPTIONS.map(opt => (
                      <Chip key={opt.months} active={warrantyMonths === opt.months} onClick={() => setWarrantyMonths(opt.months)}>
                        {opt.label}
                      </Chip>
                    ))}
                  </div>
                </div>

                {/* 환불/취소 정책 */}
                <div>
                  <Label>환불/취소 정책</Label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {CANCEL_RULES.map(rule => (
                      <div key={rule.id}>
                        <label
                          style={{
                            display: 'flex', alignItems: 'flex-start', gap: 12, cursor: 'pointer',
                            padding: '12px 14px', borderRadius: 12,
                            background: cancelRule === rule.id ? `${C.green}10` : C.bgSurface,
                            border: `1px solid ${cancelRule === rule.id ? C.green + '50' : C.border}`,
                            transition: 'all 0.15s',
                          }}
                          onClick={() => setCancelRule(rule.id)}
                        >
                          <div style={{
                            width: 18, height: 18, borderRadius: '50%', flexShrink: 0, marginTop: 1,
                            border: `2px solid ${cancelRule === rule.id ? C.green : C.textDim}`,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                          }}>
                            {cancelRule === rule.id && (
                              <div style={{ width: 9, height: 9, borderRadius: '50%', background: C.green }} />
                            )}
                          </div>
                          <div>
                            <div style={{ fontSize: 14, fontWeight: 600, color: C.textPri, marginBottom: 2 }}>
                              {rule.id}: {rule.label}
                            </div>
                            <div style={{ fontSize: 12, color: C.textSec }}>{rule.desc}</div>
                          </div>
                        </label>
                        {rule.id === 'A3' && cancelRule === 'A3' && (
                          <div style={{ marginTop: 8, marginLeft: 30, display: 'flex', alignItems: 'center', gap: 10 }}>
                            <input
                              type="number"
                              min={1} max={30}
                              value={cancelWithinDays}
                              onChange={e => setCancelWithinDays(Math.max(1, Math.min(30, parseInt(e.target.value) || 7)))}
                              className="oc-input"
                              style={{ ...inputStyle, width: 80, textAlign: 'center' }}
                            />
                            <span style={{ fontSize: 13, color: C.textSec }}>일 이내 (1~30일)</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* 추가 안내 */}
                <div>
                  <Label>추가 안내 (선택)</Label>
                  <textarea
                    value={extraText}
                    onChange={e => setExtraText(e.target.value.slice(0, 1000))}
                    placeholder="구매자에게 알리고 싶은 추가 정보를 적어주세요"
                    rows={4}
                    className="oc-input"
                    style={{ ...inputStyle, resize: 'none', lineHeight: 1.55 }}
                  />
                  <div style={{ fontSize: 11, color: C.textDim, textAlign: 'right', marginTop: 4 }}>{extraText.length}/1000</div>
                </div>

                {ctaBtn('다음 →', () => goTo(3))}
              </div>
            )}

            {/* ══ Step 3: 확인 & 제출 ══ */}
            {step === 3 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                <div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: C.textPri, marginBottom: 4 }}>📋 오퍼 확인</div>
                  <div style={{ fontSize: 13, color: C.textSec }}>제출 전에 내용을 확인해주세요.</div>
                </div>

                {/* 딜 명 */}
                <div style={{ fontSize: 14, fontWeight: 600, color: C.textSec }}>
                  📦 {MOCK_DEAL.product_name}
                </div>

                {/* 오퍼 요약 카드 */}
                <div style={{ ...cardStyle }}>
                  {/* 가격 */}
                  <div style={{ paddingBottom: 14, marginBottom: 14, borderBottom: `1px solid ${C.border}` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                      <span style={{ fontSize: 24, fontWeight: 900, color: C.textPri }}>₩{fmtPrice(price)}</span>
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
                      목표가 대비 {getSavingsPct(price)} · {MOCK_DEAL.offer_count}건 중 {rank}위
                    </div>
                  </div>

                  {/* 상세 목록 */}
                  {[
                    { icon: '📦', label: '판매 수량',  value: `${totalQty}개` },
                    ...(comment ? [{ icon: '💬', label: '코멘트', value: comment.length > 28 ? comment.slice(0, 28) + '…' : comment }] : []),
                    { icon: '🚚', label: '배송비',    value: getShippingDisplay() },
                    { icon: '📅', label: '배송일',    value: showCustomDel ? `${deliveryDays}일 이내` : `${deliveryDays}일 이내` },
                    { icon: '🛡️', label: '보증',      value: warrantyMonths === 0 ? '없음' : `${warrantyMonths}개월` },
                    { icon: '↩️', label: '환불정책',  value: cancelRuleLabels[cancelRule] },
                    ...(extraText ? [{ icon: '📝', label: '추가안내', value: extraText.length > 24 ? extraText.slice(0, 24) + '…' : extraText }] : []),
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
                      {detail.length > 100 ? detail.slice(0, 100) + '…' : detail}
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

                {ctaBtn('오퍼 제출하기 🚀', handleSubmit, false, submitting)}
              </div>
            )}

          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
