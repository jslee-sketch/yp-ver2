import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';
import { addParticipant } from '../api/dealApi';
import { FEATURES } from '../config';

// ── Mock 딜 정보 ────────────────────────────────────────

const MOCK_DEALS: Record<number, {
  product_name: string; brand: string; target_price: number;
  participant_count: number; target_participants: number; days_left: number;
  options: { title: string; value: string }[];
  ship_fee: string; warranty: string;
}> = {
  15: {
    product_name: '에어팟 프로 2세대 (USB-C)',
    brand: 'Apple',
    target_price: 279000,
    participant_count: 32,
    target_participants: 100,
    days_left: 2,
    options: [{ title: '색상', value: '블랙' }, { title: '타입', value: 'USB-C' }],
    ship_fee: '무료',
    warranty: '6개월',
  },
  16: {
    product_name: '종가집 포기김치 5kg',
    brand: '종가집',
    target_price: 28000,
    participant_count: 15,
    target_participants: 50,
    days_left: 5,
    options: [{ title: '중량', value: '5kg' }],
    ship_fee: '무료',
    warranty: '없음',
  },
};

// ── 색상 ─────────────────────────────────────────────

const C = {
  bgDeep: '#0a0e1a', bgCard: '#111827', bgSurface: '#1a2236', bgInput: '#0f1625',
  cyan: '#00f0ff', green: '#39ff14', yellow: '#ffe156', orange: '#ff8c42',
  textPri: '#f0f4ff', textSec: '#8892a8', textDim: '#4a5568',
  border: 'rgba(0,240,255,0.12)',
};

const variants = {
  enter:  (d: number) => ({ x: d > 0 ? '60%' : '-60%', opacity: 0 }),
  center: { x: 0, opacity: 1, transition: { type: 'spring' as const, damping: 28, stiffness: 300 } },
  exit:   (d: number) => ({ x: d > 0 ? '-60%' : '60%', opacity: 0, transition: { duration: 0.18 } }),
};

// ── 공용 컴포넌트 ────────────────────────────────────

function ReadonlyRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
      <span style={{ fontSize: 13, color: C.textSec }}>{label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.textPri }}>{value}</span>
        <span style={{ fontSize: 11, color: C.textDim }}>🔒</span>
      </div>
    </div>
  );
}

// ── 메인 ─────────────────────────────────────────────

export default function DealJoinPage() {
  const { id: dealId } = useParams<{ id: string }>();
  const navigate       = useNavigate();
  const { user }       = useAuth();

  const deal = MOCK_DEALS[Number(dealId)];

  const [step, setStep] = useState(1);
  const [dir,  setDir]  = useState(1);
  const [qty,  setQty]  = useState(1);
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  const goTo = (n: number) => { setDir(n > step ? 1 : -1); setStep(n); };

  if (!deal) {
    return (
      <div style={{ minHeight: '100dvh', background: C.bgDeep, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16 }}>
        <div style={{ fontSize: 40 }}>🔍</div>
        <div style={{ color: C.textSec, fontSize: 14 }}>딜을 찾을 수 없어요</div>
        <button onClick={() => navigate(-1)} style={{ padding: '10px 20px', borderRadius: 10, background: `${C.green}18`, border: `1px solid ${C.green}44`, color: C.green, fontSize: 13, fontWeight: 700, cursor: 'pointer' }}>돌아가기</button>
      </div>
    );
  }

  if (done) {
    return (
      <div style={{ minHeight: '100dvh', background: C.bgDeep, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 24px' }}>
        <style>{`@keyframes popIn { 0%{transform:scale(0.5);opacity:0} 70%{transform:scale(1.1)} 100%{transform:scale(1);opacity:1} }`}</style>
        <motion.div
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', damping: 24 }}
          style={{ width: '100%', maxWidth: 400, textAlign: 'center' }}
        >
          <div style={{ fontSize: 64, marginBottom: 20, animation: 'popIn 0.6s cubic-bezier(.175,.885,.32,1.275) both' }}>🎉</div>
          <div style={{ fontSize: 24, fontWeight: 900, color: C.textPri, marginBottom: 8 }}>딜에 참여했어요!</div>
          <div style={{ fontSize: 14, color: C.textSec, marginBottom: 32 }}>
            {deal.product_name} · {qty}개
          </div>

          <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: '20px', marginBottom: 24, textAlign: 'left' }}>
            <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.7 }}>
              딜방에서 다른 참여자들과<br />소통해보세요! 함께 더 좋은 가격을<br />만들어갈 수 있어요 🤝
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <button
              onClick={() => navigate(`/deal/${dealId ?? ''}`)}
              style={{ padding: '15px', borderRadius: 14, fontSize: 15, fontWeight: 800, background: `linear-gradient(135deg, ${C.cyan}, ${C.green})`, color: '#0a0e1a', cursor: 'pointer' }}
            >딜 페이지로 이동</button>
            <button
              onClick={() => navigate('/my-orders')}
              style={{ padding: '14px', borderRadius: 14, fontSize: 14, fontWeight: 600, background: 'transparent', border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}
            >참여/결제/배송 보기</button>
          </div>
        </motion.div>
      </div>
    );
  }

  const handleJoin = async () => {
    if (FEATURES.USE_API_DEALS) {
      if (!user) { navigate('/login'); return; }
      setLoading(true);
      try {
        await addParticipant(Number(dealId), user.id, qty);
        setDone(true);
      } catch (err: unknown) {
        const e = err as { response?: { data?: { detail?: unknown } } };
        const detail = e.response?.data?.detail;
        alert(typeof detail === 'string' ? detail : '딜 참여에 실패했어요. 다시 시도해주세요.');
      } finally {
        setLoading(false);
      }
    } else {
      setLoading(true);
      await new Promise(r => setTimeout(r, 1000));
      setLoading(false);
      setDone(true);
    }
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bgDeep, overflow: 'hidden' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* TopBar */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 20px', zIndex: 10,
        background: 'rgba(10,14,26,0.92)', backdropFilter: 'blur(10px)',
        borderBottom: `1px solid ${C.border}`,
      }}>
        <button
          onClick={() => { if (step === 1) navigate(-1); else goTo(1); }}
          style={{ fontSize: 13, color: C.textSec, cursor: 'pointer' }}
        >← {step === 1 ? '뒤로' : '이전'}</button>
        <div style={{ fontSize: 13, fontWeight: 700 }}>
          <span style={{ color: C.cyan }}>{step}</span>
          <span style={{ color: C.textSec }}>/2</span>
        </div>
        <div style={{ width: 48 }} />
      </div>

      {/* 진행 바 */}
      <div style={{ position: 'fixed', top: 56, left: 0, right: 0, height: 3, zIndex: 10, background: C.border }}>
        <div style={{ height: '100%', width: `${(step / 2) * 100}%`, background: `linear-gradient(90deg, ${C.cyan}, ${C.green})`, transition: 'width 0.35s ease' }} />
      </div>

      {/* 콘텐츠 */}
      <div style={{ paddingTop: 60, minHeight: '100dvh' }}>
        <AnimatePresence mode="wait" custom={dir}>
          <motion.div
            key={step} custom={dir} variants={variants}
            initial="enter" animate="center" exit="exit"
            style={{ width: '100%', maxWidth: 500, margin: '0 auto', padding: '24px 20px 100px' }}
          >

            {/* ══ Step 1: 딜 정보 확인 + 수량 ══ */}
            {step === 1 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {/* 딜 정보 헤더 */}
                <div>
                  <div style={{ fontSize: 13, color: C.textSec, marginBottom: 4 }}>딜 참여하기</div>
                  <div style={{ fontSize: 17, fontWeight: 800, color: C.textPri, marginBottom: 4 }}>
                    📦 {deal.product_name}
                  </div>
                  <div style={{ fontSize: 12, color: C.textSec }}>{deal.brand} · {deal.options.map(o => `${o.title}: ${o.value}`).join(' · ')}</div>
                </div>

                {/* 요약 통계 */}
                <div style={{ display: 'flex', gap: 8 }}>
                  {[
                    { label: '목표가', value: `₩${deal.target_price.toLocaleString()}`, color: C.green },
                    { label: '현재 참여', value: `${deal.participant_count}/${deal.target_participants}명`, color: C.yellow },
                    { label: '남은 기간', value: `${deal.days_left}일`, color: C.orange },
                  ].map(item => (
                    <div key={item.label} style={{ flex: 1, textAlign: 'center', padding: '10px 4px', background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 10 }}>
                      <div style={{ fontSize: 10, color: C.textDim, marginBottom: 4 }}>{item.label}</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: item.color }}>{item.value}</div>
                    </div>
                  ))}
                </div>

                {/* 딜 정보 (변경 불가) */}
                <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14, padding: '14px 16px' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 12 }}>딜 정보 (변경 불가)</div>
                  <ReadonlyRow label="상품" value={deal.product_name} />
                  <ReadonlyRow label="목표가" value={`₩${deal.target_price.toLocaleString()}`} />
                  {deal.options.map(o => <ReadonlyRow key={o.title} label={o.title} value={o.value} />)}
                  <ReadonlyRow label="배송비" value={deal.ship_fee} />
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 8 }}>
                    <span style={{ fontSize: 13, color: C.textSec }}>보증</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: C.textPri }}>{deal.warranty}</span>
                      <span style={{ fontSize: 11, color: C.textDim }}>🔒</span>
                    </div>
                  </div>
                </div>

                {/* 참여 수량 */}
                <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14, padding: '16px' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 14, letterSpacing: 1 }}>참여 수량</div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 24 }}>
                    <button
                      onClick={() => setQty(q => Math.max(1, q - 1))}
                      style={{ width: 40, height: 40, borderRadius: 10, fontSize: 20, fontWeight: 700, background: C.bgSurface, border: `1px solid ${C.border}`, color: C.textPri, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >−</button>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 28, fontWeight: 900, color: C.cyan, lineHeight: 1 }}>{qty}</div>
                      <div style={{ fontSize: 11, color: C.textDim, marginTop: 4 }}>개</div>
                    </div>
                    <button
                      onClick={() => setQty(q => Math.min(99, q + 1))}
                      style={{ width: 40, height: 40, borderRadius: 10, fontSize: 20, fontWeight: 700, background: C.bgSurface, border: `1px solid ${C.border}`, color: C.textPri, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                    >+</button>
                  </div>
                  <div style={{ textAlign: 'center', fontSize: 11, color: C.textDim, marginTop: 10 }}>
                    최소 1개 ~ 최대 99개
                  </div>
                </div>

                <button
                  onClick={() => goTo(2)}
                  style={{ width: '100%', padding: '15px', borderRadius: 14, fontSize: 15, fontWeight: 800, background: `linear-gradient(135deg, ${C.cyan}, ${C.green})`, color: '#0a0e1a', cursor: 'pointer' }}
                >다음 →</button>
              </div>
            )}

            {/* ══ Step 2: 확인 ══ */}
            {step === 2 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ fontSize: 20, fontWeight: 800, color: C.textPri }}>참여 확인</div>

                {/* 참여 요약 */}
                <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: '20px' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 14 }}>참여 요약</div>
                  {[
                    { icon: '📦', label: '상품',    value: deal.product_name },
                    { icon: '🎯', label: '목표가',  value: `₩${deal.target_price.toLocaleString()}` },
                    { icon: '📊', label: '참여 수량', value: `${qty}개` },
                    { icon: '💰', label: '예상 금액', value: `₩${(deal.target_price * qty).toLocaleString()}` },
                  ].map(row => (
                    <div key={row.label} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
                      <span style={{ fontSize: 16, flexShrink: 0 }}>{row.icon}</span>
                      <span style={{ fontSize: 13, color: C.textSec, flex: 1 }}>{row.label}</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: C.textPri }}>{row.value}</span>
                    </div>
                  ))}
                  <div style={{ fontSize: 11, color: C.textDim, marginTop: 10, lineHeight: 1.6 }}>
                    ⚠️ 실제 결제 금액은 오퍼 확정 후 결정됩니다.
                  </div>
                </div>

                {/* 핑퐁이 안내 */}
                <div style={{ background: 'rgba(0,240,255,0.04)', border: `1px solid rgba(0,240,255,0.2)`, borderRadius: 14, padding: '14px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    <span style={{ fontSize: 20 }}>🤖</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: C.cyan }}>핑퐁이 안내</span>
                  </div>
                  <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.7 }}>
                    참여하시면 딜방 채팅에 참여할 수 있어요!<br />
                    다른 참여자들과 소통하며 더 좋은 가격을 만들어보세요.
                  </div>
                </div>

                <button
                  onClick={handleJoin}
                  disabled={loading}
                  style={{
                    width: '100%', padding: '15px', borderRadius: 14, fontSize: 15, fontWeight: 800,
                    background: loading ? `${C.green}40` : `linear-gradient(135deg, ${C.cyan}, ${C.green})`,
                    color: '#0a0e1a', cursor: loading ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  }}
                >
                  {loading && <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid rgba(0,0,0,0.3)', borderTopColor: '#0a0e1a', animation: 'spin 0.8s linear infinite' }} />}
                  🤝 딜 참여하기
                </button>

                <div style={{ textAlign: 'center', fontSize: 12, color: C.textDim }}>
                  ⚠️ 참여 후에도 취소 가능해요
                </div>
              </div>
            )}

          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
