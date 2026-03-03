import { AnimatePresence, motion } from 'framer-motion';
import { T, groupColor, groupBg, groupBorder } from './journeyTokens';
import type { JourneyOffer, VerdictType } from './types';

const VERDICT_STYLE: Record<VerdictType, { bg: string; border: string; color: string }> = {
  good:  { bg: 'rgba(57,255,20,0.06)',  border: 'rgba(57,255,20,0.2)',  color: T.green   },
  close: { bg: 'rgba(255,225,86,0.06)', border: 'rgba(255,225,86,0.2)', color: T.yellow  },
  far:   { bg: 'rgba(255,45,120,0.06)', border: 'rgba(255,45,120,0.2)', color: T.magenta },
};

const COND_TAG_STYLE = {
  good:    { bg: 'rgba(57,255,20,0.08)',  border: 'rgba(57,255,20,0.2)',  color: T.green   },
  neutral: { bg: 'rgba(255,225,86,0.08)', border: 'rgba(255,225,86,0.2)', color: T.yellow  },
  bad:     { bg: 'rgba(255,45,120,0.08)', border: 'rgba(255,45,120,0.2)', color: T.magenta },
};

interface Props {
  offer:   JourneyOffer | null;
  target:  number;
  onClose: () => void;
  onBuy?:  (offer: JourneyOffer) => void;
}

export function OfferDetailSheet({ offer, target, onClose, onBuy }: Props) {
  return (
    <AnimatePresence>
      {offer && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 200 }}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 280 }}
            style={{
              position: 'fixed', bottom: 0, left: 0, right: 0,
              maxWidth: 480, margin: '0 auto',
              maxHeight: '92dvh', background: T.bgDeep,
              borderRadius: '20px 20px 0 0',
              overflowY: 'auto', zIndex: 201,
            }}
          >
            {/* Handle */}
            <div style={{ display: 'flex', justifyContent: 'center', padding: '12px 0 4px', position: 'sticky', top: 0, background: T.bgDeep, zIndex: 5 }}>
              <div style={{ width: 36, height: 4, borderRadius: 2, background: T.textDim }} />
            </div>

            {/* Close */}
            <button
              onClick={onClose}
              style={{
                position: 'absolute', top: 12, right: 16,
                width: 32, height: 32, borderRadius: '50%',
                background: T.bgSurface, border: `1px solid ${T.border}`,
                color: T.textSec, fontSize: 16, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                zIndex: 6,
              }}
            >✕</button>

            <DetailContent offer={offer} target={target} onClose={onClose} />
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function DetailContent({ offer, target }: { offer: JourneyOffer; target: number; onClose: () => void }) {
  const gap = offer.adjPrice - target;
  const gc  = groupColor[offer.group];
  const gb  = groupBg[offer.group];
  const gbr = groupBorder[offer.group];
  const vs  = VERDICT_STYLE[offer.verdictType];

  return (
    <div style={{ padding: '0 20px 36px' }}>
      {/* ── Seller header ── */}
      <div style={{ padding: '8px 0 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12, flexShrink: 0,
            background: T.bgSurface, border: `1px solid ${T.border}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22,
          }}>
            {offer.icon}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 16, fontWeight: 700, color: T.text }}>{offer.seller}</span>
              <span style={{ padding: '2px 7px', background: gb, border: `1px solid ${gbr}`, borderRadius: 5, fontSize: 9, fontWeight: 700, color: gc, fontFamily: "'Space Mono', monospace" }}>
                {offer.group}
              </span>
            </div>
            <div style={{ fontSize: 11, color: T.textSec, marginTop: 3 }}>
              {offer.sellerTier} · {offer.sellerScore}점 · {offer.sellerDeals}건 · {offer.sellerRate}
            </div>
          </div>
        </div>

        {/* Two price boxes */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
          <div style={{ flex: 1, borderRadius: 12, padding: '12px', textAlign: 'center', background: T.bgSurface, border: `1px solid ${T.border}` }}>
            <div style={{ fontSize: 9, fontWeight: 600, color: T.textSec, marginBottom: 4, fontFamily: "'Space Mono', monospace", textTransform: 'uppercase', letterSpacing: 0.5 }}>오퍼 액면가</div>
            <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: 20, fontWeight: 800, color: T.text }}>₩{offer.rawPrice.toLocaleString('ko-KR')}</div>
            <div style={{ fontSize: 9, marginTop: 4, color: T.textSec }}>{offer.totalQty}개 기준</div>
          </div>
          <div style={{ flex: 1, borderRadius: 12, padding: '12px', textAlign: 'center', background: 'rgba(57,255,20,0.06)', border: '1px solid rgba(57,255,20,0.2)' }}>
            <div style={{ fontSize: 9, fontWeight: 600, color: T.green, marginBottom: 4, fontFamily: "'Space Mono', monospace", textTransform: 'uppercase', letterSpacing: 0.5 }}>보정가</div>
            <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: 20, fontWeight: 800, color: T.green }}>₩{offer.adjPrice.toLocaleString('ko-KR')}</div>
            <div style={{ fontSize: 9, marginTop: 4, color: 'rgba(57,255,20,0.5)' }}>
              목표가 대비 {gap > 0 ? `+${gap.toLocaleString('ko-KR')}` : gap.toLocaleString('ko-KR')}원
            </div>
          </div>
        </div>

        {/* ── Qty 3-box ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
          <QtyBox label="전체 수량"  value={offer.totalQty}                      color={T.text} />
          <QtyBox label="판매 완료"  value={offer.totalQty - offer.remainQty}    color={T.green} />
          <QtyBox label="남은 수량"  value={offer.remainQty}                     color={T.yellow} />
        </div>

        {/* Seller stats 2×2 */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
          <SgItem label="판매자 등급" value={offer.sellerTier} valueColor={T.text} />
          <SgItem label="신뢰 점수"  value={`${offer.sellerScore}/100`}
            valueColor={offer.sellerScore >= 80 ? T.green : offer.sellerScore >= 60 ? T.yellow : T.magenta} />
          <SgItem label="총 거래"    value={`${offer.sellerDeals}건`}  valueColor={T.text} />
          <SgItem label="성사율"     value={offer.sellerRate}          valueColor={T.text} />
        </div>

        {/* Condition tags */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {offer.condTags.map((tag, i) => {
            const s = COND_TAG_STYLE[tag.type];
            return (
              <div key={i} style={{ padding: '5px 10px', borderRadius: 8, fontSize: 11, fontWeight: 500, background: s.bg, border: `1px solid ${s.border}`, color: s.color }}>
                {tag.text}
              </div>
            );
          })}
        </div>
      </div>

      <Divider />

      {/* ── Waterfall ── */}
      <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
        🔍 같은 기준으로 비교하면?
      </div>

      <div style={{ marginBottom: 16 }}>
        {/* Step 0 */}
        <WFStep
          dotColor={T.textSec} lineColor={T.textDim} titleColor={T.textSec}
          title="오퍼 액면가"
          desc={`${offer.seller} 님이 제시한 가격`}
          result={`₩${offer.rawPrice.toLocaleString('ko-KR')}`}
          resultSub={`(${offer.totalQty}개 기준 · 배송비 ${offer.shipFee})`}
          resultBg="rgba(136,146,168,0.1)" resultColor={T.textSec}
        />
        {/* Step 1 */}
        <WFStep
          dotColor={T.orange} lineColor={T.orange} titleColor={T.orange}
          title="👥 Step 1 · 수량 보정"
          desc={`목표가는 100개 기준인데 이 오퍼는 ${offer.totalQty}개 기준이에요. 같은 수량으로 환산합니다.`}
          result={`₩${offer.rawPrice.toLocaleString('ko-KR')} → ₩${offer.groupResult.toLocaleString('ko-KR')}`}
          resultSub={`(${offer.groupAdj > 0 ? '+' : ''}${offer.groupAdj.toLocaleString('ko-KR')}원)`}
          resultBg="rgba(255,140,66,0.08)" resultColor={T.orange}
        />
        {/* Step 2 */}
        <WFStep
          dotColor={T.yellow} lineColor={T.yellow} titleColor={T.yellow}
          title="⚖️ Step 2 · 조건 보정 (수량보정가 기준)"
          desc={`수량보정된 ₩${offer.groupResult.toLocaleString('ko-KR')} 위에서 조건 차이를 반영`}
          descSub={offer.condDetail}
          result={`₩${offer.groupResult.toLocaleString('ko-KR')} → ₩${offer.condResult.toLocaleString('ko-KR')}`}
          resultSub={`(${offer.condAdj > 0 ? '+' : ''}${offer.condAdj.toLocaleString('ko-KR')}원)`}
          resultBg="rgba(255,225,86,0.08)" resultColor={T.yellow}
          isLast={false}
        />
        {/* Final */}
        <div style={{ display: 'flex', alignItems: 'stretch' }}>
          <div style={{ width: 32, display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', border: `2px solid ${T.green}`, background: T.green, flexShrink: 0, zIndex: 2 }} />
          </div>
          <div style={{ flex: 1, paddingLeft: 8, paddingBottom: 4 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: T.green, marginBottom: 4 }}>✅ 동일 기준 비교가</div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '5px 12px', borderRadius: 8, background: 'rgba(57,255,20,0.1)',
              fontFamily: "'Space Mono', monospace", fontWeight: 700, fontSize: 14, color: T.green,
            }}>
              ₩{offer.adjPrice.toLocaleString('ko-KR')}
            </div>
          </div>
        </div>
      </div>

      {/* Verdict */}
      <div style={{ padding: 14, borderRadius: 14, textAlign: 'center', background: vs.bg, border: `1px solid ${vs.border}`, marginBottom: 16 }}>
        <div style={{ fontSize: 24, marginBottom: 6 }}>{offer.verdictEmoji}</div>
        <div style={{ fontSize: 14, fontWeight: 700, color: vs.color, marginBottom: 4 }}>{offer.verdictTitle}</div>
        <div
          style={{ fontSize: 11, color: T.textSec, lineHeight: 1.7 }}
          dangerouslySetInnerHTML={{ __html: offer.verdictDesc }}
        />
      </div>

      {/* Product images */}
      {offer.images && offer.images.length > 0 && (
        <>
          <Divider />
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 12 }}>📸 제품 이미지</div>
            <div style={{
              display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4,
              scrollbarWidth: 'none',
            } as React.CSSProperties}>
              {offer.images.map((src, i) => (
                <img
                  key={i}
                  src={src}
                  alt={`제품 ${i + 1}`}
                  style={{
                    width: 120, height: 120, objectFit: 'cover',
                    borderRadius: 12, flexShrink: 0,
                    border: `1px solid ${T.border}`,
                  }}
                />
              ))}
            </div>
          </div>
        </>
      )}

      {/* Product detail text */}
      {offer.detail && (
        <>
          <Divider />
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.text, marginBottom: 10 }}>📝 제품 상세 설명</div>
            <div style={{
              padding: '12px 14px',
              background: 'rgba(255,255,255,0.03)',
              borderRadius: 12,
              border: `1px solid ${T.border}`,
              fontSize: 13, lineHeight: 1.7,
              color: T.textSec,
              whiteSpace: 'pre-wrap',
              maxHeight: 300,
              overflowY: 'auto',
            }}>
              {offer.detail}
            </div>
          </div>
        </>
      )}

      {/* CTA */}
      <button
        onClick={() => {
          if (onBuy && offer) {
            onBuy(offer);
          } else if (offer) {
            window.confirm('이 오퍼로 구매하시겠어요?');
          }
        }}
        style={{
          width: '100%', padding: 14, borderRadius: 14, cursor: 'pointer',
          background: 'linear-gradient(135deg,rgba(57,255,20,0.12),rgba(0,240,255,0.08))',
          border: '1px solid rgba(57,255,20,0.2)',
          transition: 'background 0.2s',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'linear-gradient(135deg,rgba(57,255,20,0.2),rgba(0,240,255,0.14))'; }}
        onMouseLeave={e => { e.currentTarget.style.background = 'linear-gradient(135deg,rgba(57,255,20,0.12),rgba(0,240,255,0.08))'; }}
      >
        <div style={{ fontSize: 14, fontWeight: 700, color: T.green }}>이 오퍼로 구매하기</div>
        <div style={{ fontSize: 11, color: T.textSec, marginTop: 4 }}>
          ₩{offer.rawPrice.toLocaleString('ko-KR')} · {offer.seller} · 잔여 {offer.remainQty}개
        </div>
      </button>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────

function QtyBox({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{ background: T.bgSurface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '10px 8px', textAlign: 'center' }}>
      <div style={{ fontSize: 10, color: T.textSec, marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: 18, fontWeight: 800, color }}>{value}</div>
      <div style={{ fontSize: 9, color: T.textDim, marginTop: 2 }}>개</div>
    </div>
  );
}

function SgItem({ label, value, valueColor }: { label: string; value: string; valueColor: string }) {
  return (
    <div style={{ background: T.bgSurface, border: `1px solid ${T.border}`, borderRadius: 10, padding: '10px 12px' }}>
      <div style={{ fontSize: 10, color: T.textSec, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: valueColor }}>{value}</div>
    </div>
  );
}

function Divider() {
  return <div style={{ height: 1, background: T.border, margin: '16px 0' }} />;
}

interface WFStepProps {
  dotColor:   string; lineColor: string; titleColor: string;
  title:      string; desc: string; descSub?: string;
  result:     string; resultSub?: string;
  resultBg:   string; resultColor: string;
  isLast?:    boolean;
}

function WFStep({ dotColor, lineColor, titleColor, title, desc, descSub, result, resultSub, resultBg, resultColor, isLast }: WFStepProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'stretch' }}>
      <div style={{ width: 32, display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <div style={{ width: 10, height: 10, borderRadius: '50%', border: `2px solid ${dotColor}`, background: '#0a0e1a', flexShrink: 0, zIndex: 2 }} />
        {isLast !== true && (
          <div style={{ width: 2, flex: 1, minHeight: 16, background: lineColor, marginTop: 2 }} />
        )}
      </div>
      <div style={{ flex: 1, paddingLeft: 8, paddingBottom: 18 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: titleColor, marginBottom: 4 }}>{title}</div>
        <div style={{ fontSize: 11, color: T.textSec, lineHeight: 1.6, marginBottom: 4 }}>{desc}</div>
        {descSub && (
          <div style={{ fontSize: 10, color: T.yellow, lineHeight: 1.5, marginBottom: 4 }}>{descSub}</div>
        )}
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '4px 10px', borderRadius: 8,
          background: resultBg, fontFamily: "'Space Mono', monospace",
          fontWeight: 700, fontSize: 11, color: resultColor,
        }}>
          {result}
          {resultSub && <span style={{ fontSize: 9, opacity: 0.7, fontWeight: 400 }}>{resultSub}</span>}
        </div>
      </div>
    </div>
  );
}
