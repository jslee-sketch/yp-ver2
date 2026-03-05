import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchDeal } from '../api/dealApi';
import { fetchOffersByDeal } from '../api/offerApi';
import { fetchChatMessages, sendChatMessage } from '../api/chatApi';
import { submitPrediction } from '../api/spectatorApi';
import { createReservation } from '../api/reservationApi';
import { showToast } from '../components/common/Toast';
import { BarChart, Bar, XAxis, YAxis, Cell, ResponsiveContainer } from 'recharts';
import { PriceFaceSection }   from '../components/journey/PriceFaceSection';
import { OfferListSection }   from '../components/journey/OfferListSection';
import { GroupCurveSection }  from '../components/journey/GroupCurveSection';
import { OfferDetailSheet }   from '../components/journey/OfferDetailSheet';
import { T }                  from '../components/journey/journeyTokens';
import type { JourneyOffer, OfferGroup, VerdictType }  from '../components/journey/types';

// ── 백엔드 오퍼 → JourneyOffer 매핑 ──
function mapApiOfferToJourney(raw: Record<string, unknown>, targetPrice: number, idx: number): JourneyOffer {
  const price = (raw.price as number) ?? 0;
  const sellerName = (raw.seller_nickname as string) || (raw.business_name as string) || `셀러 #${raw.seller_id ?? idx + 1}`;
  const icons = ['⛵','🚤','🛶','🚢','🎯','🏪','💻','👑','⚡','🎪','🏬','🔧'];
  const shipFeeNum = (raw.shipping_fee_per_reservation as number) ?? (raw.shipping_fee as number) ?? 0;
  const shipDays = (raw.delivery_days as number) ?? 3;
  const totalQty = (raw.total_available_qty as number) ?? 1;
  const remainQty = totalQty - ((raw.sold_qty as number) ?? 0) - ((raw.reserved_qty as number) ?? 0);

  const group: OfferGroup = price < targetPrice ? 'PREMIUM' : price <= targetPrice * 1.05 ? 'MATCHING' : 'BELOW';
  const priceDiff = price - targetPrice;
  const verdictType: VerdictType = priceDiff <= 0 ? 'good' : priceDiff <= targetPrice * 0.1 ? 'close' : 'far';

  return {
    id: (raw.id as number) ?? idx,
    seller: sellerName,
    icon: icons[idx % icons.length],
    rawPrice: price,
    adjPrice: price, // no backend pricing engine data — show raw price
    offerIndexPct: targetPrice > 0 ? Math.round(price / targetPrice * 1000) / 10 : 100,
    totalQty,
    remainQty: Math.max(0, remainQty),
    shipDays,
    shipFee: shipFeeNum === 0 ? '무료' : `${shipFeeNum.toLocaleString()}원`,
    refund: '보통',
    asGrade: '보통',
    sellerTier: '일반',
    sellerScore: 0,
    sellerDeals: 0,
    sellerRate: '-',
    condTags: [
      { text: `배송 ${shipDays}일`, type: shipDays <= 2 ? 'good' : shipDays <= 4 ? 'neutral' : 'bad' },
      { text: shipFeeNum === 0 ? '무료배송' : `배송비 ${shipFeeNum.toLocaleString()}원`, type: shipFeeNum === 0 ? 'good' : 'neutral' },
    ],
    group,
    groupAdj: 0,
    groupResult: price,
    condAdj: 0,
    condResult: price,
    condDetail: '',
    verdictType,
    verdictEmoji: verdictType === 'good' ? '🎯' : verdictType === 'close' ? '🤏' : '⚠️',
    verdictTitle: verdictType === 'good' ? '목표가 이하' : verdictType === 'close' ? '목표가 근접' : '목표가 초과',
    verdictDesc: priceDiff <= 0
      ? `목표가보다 <strong style="color:#39ff14">${Math.abs(priceDiff).toLocaleString()}원 저렴</strong>해요!`
      : `목표가보다 <strong style="color:#ff8c42">${priceDiff.toLocaleString()}원 비쌈</strong>`,
  };
}

// (Mock 오퍼 제거 — API 데이터 사용)

// ── 딜 단계 ───────────────────────────────────────────────
const STAGES = ['딜모집', '오퍼경쟁', '성사', '결제', '배송', '완료'];

function getCountdownColor(diff: number): string {
  if (diff < 10 * 60 * 1000)  return '#ff2d78';
  if (diff < 60 * 60 * 1000)  return '#ff2d78';
  if (diff < 3 * 60 * 60 * 1000)  return '#ff8c42';
  if (diff < 12 * 60 * 60 * 1000) return '#ffe156';
  return '#e8eaed';
}

// ── 채팅 ──────────────────────────────────────────────────
interface ChatMsg { id: number; user: string; msg: string; time: string; isMe?: boolean; }

// ── 페이지 ───────────────────────────────────────────────
export default function PriceJourneyPage() {
  const { id: dealId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const [selectedOffer, setSelectedOffer] = useState<JourneyOffer | null>(null);
  const [apiDeal, setApiDeal] = useState<Record<string, unknown> | null>(null);
  const [offers, setOffers] = useState<JourneyOffer[]>([]);

  // ── 딜 가격 상태 (API 로드 후 업데이트) ──
  const [pAnchor, setPAnchor] = useState(0);
  const [pTarget, setPTarget] = useState(0);
  const [currentQ, setCurrentQ] = useState(0);
  const [qTarget, setQTarget] = useState(0);
  const [dealCreatorId, setDealCreatorId] = useState<number | null>(null);
  const [dealPhase, setDealPhase] = useState<'RECRUITING' | 'OFFER_PHASE'>('RECRUITING');
  const [deadlineMs, setDeadlineMs] = useState(Date.now() + 72 * 3600000);
  const stageCurrent = dealPhase === 'RECRUITING' ? 1 : 2;
  const [predBuckets, _setPredBuckets] = useState<{range: string; count: number}[]>([]);
  const [avgPrediction, _setAvgPrediction] = useState(0);
  void _setPredBuckets; void _setAvgPrediction; // TODO: wire to spectator API
  const predMax = Math.max(1, ...predBuckets.map(b => b.count));
  const lowestOffer = offers.length > 0 ? [...offers].sort((a, b) => a.adjPrice - b.adjPrice)[0] : null;

  // ── 방장 목표가 수정 상태 ──
  const isCreator      = dealCreatorId != null && dealCreatorId === (user?.id ?? 0);
  const canEditTarget  = isCreator && dealPhase === 'RECRUITING';
  const [currentTargetReason, setCurrentTargetReason] = useState('');
  const [currentTargetImages, setCurrentTargetImages] = useState<string[]>([]);
  const [showTargetEditModal, setShowTargetEditModal] = useState(false);
  const [newTargetPrice, setNewTargetPrice]           = useState(0);
  const [targetReason, setTargetReason]               = useState('');
  const [targetImages, setTargetImages]               = useState<string[]>([]);
  const [targetSubmitting, setTargetSubmitting]       = useState(false);
  const [currentDisplayPrice, setCurrentDisplayPrice] = useState(0);
  const targetImgRef = useRef<HTMLInputElement>(null);

  // ── 예측 모달 ──
  const [showPredModal, setShowPredModal] = useState(false);
  const [predPrice, setPredPrice]         = useState('');
  const [predSubmitting, setPredSubmitting] = useState(false);
  const [predDone, setPredDone]           = useState(false);

  // ── 신규 오퍼 URL 파라미터 처리 (OfferCreatePage → redirect) ──
  useEffect(() => {
    if (searchParams.get('newOffer') !== '1') return;
    const newPrice = parseInt(searchParams.get('price') || '0', 10);
    const newQty   = parseInt(searchParams.get('qty')   || '1', 10);
    if (newPrice <= 0) return;
    const newOfferData = (window as any).__newOfferData ?? {};
    const shipMode   = searchParams.get('shipMode') || 'INCLUDED';
    const shipFeeNum = parseInt(searchParams.get('shipFee') || '0', 10);
    const shipFeeText =
      shipMode === 'INCLUDED'         ? '무료' :
      shipMode === 'PER_RESERVATION'  ? `${shipFeeNum.toLocaleString()}원` :
                                        `개당 ${shipFeeNum.toLocaleString()}원`;

    const myOffer: JourneyOffer = {
      id: 99, seller: '내 오퍼', icon: '🙋',
      rawPrice: newPrice, adjPrice: Math.round(newPrice * 0.98),
      offerIndexPct: pTarget > 0 ? Math.round(newPrice / pTarget * 1000) / 10 : 100,
      totalQty: newQty, remainQty: newQty,
      shipDays: 2, shipFee: shipFeeText, refund: '우수', asGrade: '우수',
      sellerTier: '신규', sellerScore: 0, sellerDeals: 0, sellerRate: '-',
      condTags: [],
      group: newPrice < pTarget ? 'PREMIUM' : newPrice <= pTarget * 1.05 ? 'MATCHING' : 'BELOW',
      groupAdj: 0, groupResult: newPrice,
      condAdj: Math.round(newPrice * -0.02), condResult: Math.round(newPrice * 0.98),
      condDetail: '내가 등록한 오퍼',
      verdictType: newPrice <= pTarget ? 'good' : newPrice <= pTarget * 1.1 ? 'close' : 'far',
      verdictEmoji: '🙋', verdictTitle: '내 오퍼',
      verdictDesc: '직접 등록한 오퍼입니다.',
      isMine: true,
      detail: newOfferData.detail || '',
      images: newOfferData.images || [],
    };
    setOffers(prev => {
      if (prev.some(o => o.id === 99)) return prev;
      return [...prev, myOffer].sort((a, b) => a.rawPrice - b.rawPrice);
    });
  }, [searchParams]);

  // ── 타이머 ──
  const [countdown, setCountdown] = useState('');
  const [countdownDiff, setCountdownDiff] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  useEffect(() => {
    const tick = () => {
      const diff = deadlineMs - Date.now();
      setCountdownDiff(diff);
      if (diff <= 0) { setCountdown('마감'); clearInterval(timerRef.current); return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setCountdown(`${h}시간 ${String(m).padStart(2,'0')}분 ${String(s).padStart(2,'0')}초`);
    };
    tick();
    timerRef.current = setInterval(tick, 1000);
    return () => clearInterval(timerRef.current);
  }, [deadlineMs]);

  const countdownColor = getCountdownColor(countdownDiff);
  const isBlinking = countdownDiff < 10 * 60 * 1000;

  // ── API: 딜 메타 + 오퍼 + 채팅 로드 ──
  useEffect(() => {
    const numId = Number(dealId);
    if (!numId) return;

    // 딜 메타
    fetchDeal(numId).then(d => {
      if (!d) return;
      const raw = d as Record<string, unknown>;
      setApiDeal(raw);
      const anchor = (raw.market_price as number) ?? (raw.anchor_price as number) ?? 0;
      const target = (raw.target_price as number) ?? (raw.max_budget as number) ?? 0;
      setPAnchor(anchor);
      setPTarget(target);
      setCurrentDisplayPrice(target);
      setNewTargetPrice(target);
      setCurrentQ((raw.current_qty as number) ?? 0);
      setQTarget((raw.desired_qty as number) ?? 100);
      setDealCreatorId((raw.creator_id as number) ?? null);
      setDealPhase(raw.status === 'open' ? 'RECRUITING' : 'OFFER_PHASE');
      if (raw.deadline_at) {
        setDeadlineMs(new Date(raw.deadline_at as string).getTime());
      }

      // 오퍼 (딜 로드 후 target 확정된 상태에서)
      fetchOffersByDeal(numId).then(offersRaw => {
        let items: Record<string, unknown>[] = [];
        if (Array.isArray(offersRaw)) items = offersRaw;
        else if (offersRaw && typeof offersRaw === 'object' && Array.isArray((offersRaw as Record<string, unknown>).items))
          items = (offersRaw as Record<string, unknown>).items as Record<string, unknown>[];
        if (items.length > 0) {
          const mapped = items.map((o, i) => mapApiOfferToJourney(o, target, i));
          mapped.sort((a, b) => a.rawPrice - b.rawPrice);
          setOffers(mapped);
        }
      }).catch(() => {});
    }).catch(() => {});

    // 채팅
    const buyerId = user?.id ?? 0;
    if (buyerId) {
      fetchChatMessages(numId, buyerId).then(msgs => {
        if (!msgs || !Array.isArray(msgs) || msgs.length === 0) return;
        setChatMessages(msgs.map((m: Record<string, unknown>, i: number) => ({
          id:   typeof m.id === 'number' ? m.id : i + 1,
          user: typeof m.sender_nickname === 'string' ? m.sender_nickname
              : typeof m.sender_name === 'string' ? m.sender_name : '익명',
          msg:  typeof m.text === 'string' ? m.text
              : typeof m.content === 'string' ? m.content : '',
          time: typeof m.created_at === 'string'
            ? new Date(m.created_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
            : '',
          isMe: typeof m.buyer_id === 'number' && m.buyer_id === buyerId,
        })));
      }).catch(() => {});
    }
  }, [dealId, user]);

  // ── 채팅 ──
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatExpanded, setChatExpanded] = useState(false);
  const [chatSearch, setChatSearch] = useState('');
  const [chatSearchOpen, setChatSearchOpen] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const nextChatId = useRef(1);

  const sendChat = () => {
    const txt = chatInput.trim();
    if (!txt) return;
    const now = new Date();
    const time = `${now.getHours()}:${String(now.getMinutes()).padStart(2,'0')}`;
    setChatMessages(prev => [...prev, { id: nextChatId.current++, user: '나', msg: txt, time, isMe: true }]);
    setChatInput('');
    const numId = Number(dealId);
    const userId = user?.id ?? 0;
    if (numId && userId) {
      sendChatMessage(numId, txt, userId, user?.role ?? 'buyer').catch(() => {});
    }
  };

  useEffect(() => {
    if (chatExpanded) chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, chatExpanded]);

  const previewMsgs = chatMessages.slice(-3);

  return (
    <div style={{ minHeight: '100dvh', background: T.bgDeep, paddingBottom: 64 }}>
      <style>{`
        @keyframes blink     { 0%,100%{opacity:1} 50%{opacity:0.3} }
        @keyframes blinkFast { 0%,100%{opacity:1} 25%{opacity:0.2} }
        @keyframes spin      { to { transform: rotate(360deg); } }
        @keyframes stagePulse {
          0%   { box-shadow: 0 0 0 0 rgba(0,230,118,0.5); }
          70%  { box-shadow: 0 0 0 6px rgba(0,230,118,0); }
          100% { box-shadow: 0 0 0 0 rgba(0,230,118,0); }
        }
      `}</style>

      {/* ── 헤더 ── */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 52, display: 'flex', alignItems: 'center', gap: 10,
        padding: '0 16px',
        background: T.bgDeep,
        borderBottom: `1px solid ${T.border}`,
      }}>
        <button
          onClick={() => navigate(-1)}
          style={{
            width: 32, height: 32, borderRadius: 8,
            background: T.bgSurface, border: `1px solid ${T.border}`,
            color: T.textSec, fontSize: 16, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >←</button>

        <span style={{ fontFamily: "'Outfit', sans-serif", fontSize: 17, fontWeight: 600, color: T.text, flex: 1 }}>
          가격 여정
        </span>

        {/* LIVE 배지 */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 5,
          padding: '3px 8px', borderRadius: 20,
          background: 'rgba(0,230,118,0.12)', border: '1px solid rgba(0,230,118,0.3)',
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%', background: T.green,
            display: 'inline-block', animation: 'blink 1.5s infinite',
          }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: T.green, letterSpacing: 1 }}>LIVE</span>
        </div>

        {/* 카운트다운 */}
        {countdown && (
          <span style={{
            fontSize: 12, fontWeight: 600, color: countdownColor,
            animation: isBlinking ? 'blinkFast 0.5s infinite' : undefined,
          }}>
            {countdown}
          </span>
        )}
      </div>

      {/* ── 딜 정보 스트립 ── */}
      <div style={{ padding: '12px 20px 14px', fontSize: 14, fontWeight: 500, color: T.text }}>
        🎧 {apiDeal ? String(apiDeal.product_name ?? '에어팟 프로 2 (USB-C)') : '에어팟 프로 2 (USB-C)'}
        <div style={{ fontSize: 12, color: T.textSec, marginTop: 4 }}>
          👥 현재 {currentQ}명 참여 · 목표 {qTarget}명 · 🏷️ 오퍼 {offers.length}건 · ⏰ {countdown || '로딩 중'}
        </div>
      </div>

      {/* ── 딜 단계 진행바 ── */}
      <div style={{ padding: '0 20px 20px' }}>
        <div style={{
          background: T.bgSurface, border: `1px solid ${T.border}`,
          borderRadius: 14, padding: '14px 16px',
        }}>
          {/* 스테이지 트랙 */}
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center', marginBottom: 10 }}>
            {STAGES.map((_, i) => (
              <div key={i} style={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                {/* 연결선 (첫 번째 제외) */}
                {i > 0 && (
                  <div style={{
                    flex: 1, height: 2,
                    background: i <= stageCurrent
                      ? `linear-gradient(90deg, ${T.green}, ${i === stageCurrent ? T.green + '88' : T.green})`
                      : T.border,
                  }} />
                )}
                {/* 원 */}
                <div style={{
                  width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 700,
                  ...(i < stageCurrent
                    ? { background: T.green, color: T.bgDeep }
                    : i === stageCurrent
                    ? { background: T.green, color: T.bgDeep, animation: 'stagePulse 2s infinite' }
                    : { background: T.bgDeep, border: `1px solid ${T.border}`, color: T.textSec }
                  ),
                }}>
                  {i < stageCurrent ? '✓' : i + 1}
                </div>
                {/* 마지막 원 이후 빈 공간 */}
                {i < STAGES.length - 1 && (
                  <div style={{
                    flex: 1, height: 2,
                    background: i < stageCurrent ? T.green : T.border,
                  }} />
                )}
              </div>
            ))}
          </div>
          {/* 스테이지 레이블 */}
          <div style={{ display: 'flex' }}>
            {STAGES.map((s, i) => (
              <div key={i} style={{
                flex: 1, textAlign: 'center',
                fontSize: 10, fontWeight: i === stageCurrent ? 700 : 400,
                color: i <= stageCurrent ? T.text : T.textSec,
                letterSpacing: '-0.2px',
              }}>
                {s}
              </div>
            ))}
          </div>
          {/* 현재 단계 설명 */}
          <div style={{
            marginTop: 10, paddingTop: 10, borderTop: `1px solid ${T.border}`,
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <div>
              <span style={{ fontSize: 12, color: T.green, fontWeight: 700 }}>현재: {STAGES[stageCurrent]}</span>
              <span style={{ fontSize: 11, color: T.textSec, marginLeft: 6 }}>— 셀러들이 오퍼를 제출 중이에요</span>
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, color: countdownColor }}>
              {countdown || '--'}
            </div>
          </div>
        </div>
      </div>

      {/* ── ① 전면: 목표가 vs 최저오퍼 ── */}
      <PriceFaceSection
        anchor={pAnchor}
        target={currentDisplayPrice}
        lowestPrice={lowestOffer?.rawPrice ?? 0}
        lowestSeller={lowestOffer?.seller ?? '-'}
        lowestQty={lowestOffer?.totalQty ?? 0}
        onEditTarget={canEditTarget ? () => {
          setNewTargetPrice(currentDisplayPrice);
          setTargetReason('');
          setTargetImages([]);
          setShowTargetEditModal(true);
        } : undefined}
      />


      {/* ── 목표가 근거 섹션 (근거 있을 때만) ── */}
      {currentTargetReason && (
        <div style={{ padding: '0 20px 8px' }}>
          <div style={{ background: T.bgSurface, border: `1px solid rgba(255,225,86,0.2)`, borderLeft: '3px solid #ffe156', borderRadius: 12, padding: '12px 14px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: '#ffe156', letterSpacing: 1, marginBottom: 8 }}>💡 목표가 근거 (방장 제시)</div>
            <div style={{ fontSize: 13, color: T.text, lineHeight: 1.6, marginBottom: currentTargetImages.length > 0 ? 10 : 0 }}>{currentTargetReason}</div>
            {currentTargetImages.length > 0 && (
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {currentTargetImages.map((src, i) => (
                  <img key={i} src={src} alt="" style={{ width: 70, height: 70, borderRadius: 8, objectFit: 'cover', border: `1px solid ${T.border}` }} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── ② 전체 오퍼 리스트 ── */}
      <OfferListSection
        offers={offers}
        target={pTarget}
        onSelectOffer={setSelectedOffer}
      />

      {/* ── ③ 공동구매 기대가격 곡선 ── */}
      <GroupCurveSection
        anchor={pAnchor}
        target={pTarget}
        currentQ={currentQ}
        qTarget={qTarget}
        lowestOfferPrice={lowestOffer?.rawPrice ?? 0}
      />

      {/* ── 딜 참여하기 플로팅 버튼 (fixed) ── */}
      <button
        onClick={() => navigate(`/deal/${dealId ?? ''}/join`)}
        style={{
          position: 'fixed',
          right: 20,
          bottom: 220,
          width: 86,
          height: 86,
          borderRadius: '50%',
          background: '#00c853',
          border: '2.5px solid rgba(0,255,136,0.6)',
          color: '#0a0e1a',
          fontSize: 11,
          fontWeight: 800,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          lineHeight: 1.3,
          textAlign: 'center' as const,
          boxShadow: '0 6px 28px rgba(0,200,83,0.55)',
          zIndex: 997,
        }}
      >
        <span style={{ fontSize: 20 }}>🤝</span>
        <span style={{ fontSize: 10 }}>이 딜</span>
        <span style={{ fontSize: 10 }}>참여하기</span>
      </button>

      {/* ── ④ 관전자 예측 분포 차트 ── */}
      <div style={{ padding: '24px 20px 0' }}>
        <div style={{
          background: T.bgSurface, border: `1px solid ${T.border}`,
          borderRadius: 14, padding: '16px',
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: T.text, marginBottom: 4 }}>
            👁️ 관전자 예측 분포
          </div>
          <div style={{ fontSize: 12, color: T.textSec, marginBottom: 14 }}>
            {chatMessages.length + 45}명이 예측에 참여했어요 · 평균 예측가:&nbsp;
            <span style={{ color: T.green, fontWeight: 700 }}>
              {avgPrediction.toLocaleString()}원
            </span>
          </div>

          {/* 바 차트 (div-based for design consistency) */}
          <div style={{ height: 140 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={predBuckets} margin={{ top: 4, right: 4, left: -20, bottom: 0 }} barCategoryGap="20%">
                <XAxis
                  dataKey="range"
                  tick={{ fill: T.textSec, fontSize: 10 }}
                  axisLine={{ stroke: T.border }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: T.textSec, fontSize: 9 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {predBuckets.map((b, i) => (
                    <Cell
                      key={i}
                      fill={b.count === predMax ? T.green : 'rgba(0,230,118,0.25)'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <button
            onClick={() => { if (predDone) return; setShowPredModal(true); }}
            disabled={predDone}
            style={{
              marginTop: 12, width: '100%',
              padding: '11px', borderRadius: 10,
              background: predDone ? 'rgba(0,230,118,0.05)' : 'rgba(0,230,118,0.1)',
              border: `1px solid rgba(0,230,118,0.3)`,
              color: T.green, fontSize: 13, fontWeight: 700,
              cursor: predDone ? 'default' : 'pointer',
              opacity: predDone ? 0.6 : 1,
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => { if (!predDone) e.currentTarget.style.background = 'rgba(0,230,118,0.18)'; }}
            onMouseLeave={e => { if (!predDone) e.currentTarget.style.background = 'rgba(0,230,118,0.1)'; }}
          >
            {predDone ? '예측 완료!' : '🎯 나도 예측하기'}
          </button>
        </div>
      </div>

      {/* ── ⑤ 핑퐁이 인사이트 카드 ── */}
      <div style={{ padding: '16px 20px 0' }}>
        <div style={{
          background: T.bgSurface,
          border: `1px solid rgba(0,229,255,0.3)`,
          borderRadius: 14, padding: '14px 16px',
          display: 'flex', gap: 12, alignItems: 'flex-start',
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10, flexShrink: 0,
            background: 'rgba(0,229,255,0.12)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 20,
          }}>🤖</div>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#00e5ff', marginBottom: 4 }}>
              핑퐁이 인사이트
            </div>
            <div style={{ fontSize: 13, color: T.text, lineHeight: 1.55 }}>
              {offers.length === 0 ? (
                <>아직 오퍼가 없어요. 판매자의 제안을 기다려주세요! ⏳</>
              ) : lowestOffer && pTarget > 0 && lowestOffer.rawPrice <= pTarget ? (
                <>목표가보다 <span style={{ color: T.green, fontWeight: 700 }}>{(pTarget - lowestOffer.rawPrice).toLocaleString()}원 더 저렴한 오퍼</span>가 있어요! 🎉
                <br />{offers.filter(o => o.rawPrice <= pTarget).length > 1 ? `PREMIUM 오퍼가 ${offers.filter(o => o.rawPrice <= pTarget).length}개나 경쟁 중이에요. ` : ''}마감 전 참여하면 좋을 것 같아요.</>
              ) : lowestOffer ? (
                <>아직 목표가에 도달한 오퍼가 없어요. 가장 가까운 오퍼는 <span style={{ color: '#ff8c42', fontWeight: 700 }}>{lowestOffer.rawPrice.toLocaleString()}원</span>이에요.</>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      {/* ── ⑥ 딜 채팅 ── */}
      <div style={{ padding: '16px 20px 0' }}>
        <div style={{
          background: T.bgSurface, border: `1px solid ${T.border}`,
          borderRadius: 14, overflow: 'hidden',
        }}>
          {/* 헤더 */}
          <div
            style={{
              padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              cursor: 'pointer', userSelect: 'none',
            }}
            onClick={() => setChatExpanded(v => !v)}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 700, color: T.text }}>💬 딜 채팅</span>
              <span style={{
                fontSize: 11, padding: '1px 7px', borderRadius: 10,
                background: 'rgba(0,229,255,0.12)', color: '#00e5ff',
              }}>{chatMessages.length}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {chatExpanded && (
                <button onClick={e => { e.stopPropagation(); setChatSearchOpen(v => !v); if (chatSearchOpen) setChatSearch(''); }} style={{ width: 24, height: 24, borderRadius: 6, background: chatSearchOpen ? 'rgba(0,229,255,0.15)' : 'transparent', border: 'none', color: chatSearchOpen ? '#00e5ff' : T.textSec, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>🔍</button>
              )}
              <span style={{ fontSize: 12, color: T.textSec, transition: 'transform 0.2s', display: 'inline-block', transform: chatExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span>
            </div>
          </div>

          {/* 검색바 */}
          {chatSearchOpen && (
            <div style={{ padding: '8px 12px', borderBottom: `1px solid ${T.border}`, display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ fontSize: 13, color: T.textSec }}>🔍</span>
              <input
                value={chatSearch}
                onChange={e => setChatSearch(e.target.value)}
                placeholder="채팅 검색..."
                autoFocus
                style={{
                  flex: 1, padding: '6px 10px', borderRadius: 8, fontSize: 12,
                  background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.border}`,
                  color: T.text, outline: 'none',
                }}
              />
              {chatSearch && (
                <button onClick={() => setChatSearch('')} style={{
                  width: 22, height: 22, borderRadius: 6, background: 'rgba(255,255,255,0.08)',
                  border: 'none', color: T.textSec, fontSize: 11, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>✕</button>
              )}
            </div>
          )}

          {/* 메시지 영역 */}
          {chatExpanded ? (
            <div>
              {/* 전체 메시지 스크롤 */}
              <div className="chat-scroll" style={{
                maxHeight: 260, overflowY: 'auto', padding: '0 16px 12px',
                display: 'flex', flexDirection: 'column', gap: 10,
              }}>
                {(chatSearch ? chatMessages.filter(m => m.msg.toLowerCase().includes(chatSearch.toLowerCase())) : chatMessages).map(m => (
                  <div key={m.id} style={{
                    display: 'flex', flexDirection: m.isMe ? 'row-reverse' : 'row',
                    alignItems: 'flex-start', gap: 8,
                  }}>
                    {!m.isMe && (
                      <div style={{
                        width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                        background: m.user === '핑퐁이' ? 'rgba(0,229,255,0.15)' : 'rgba(255,255,255,0.08)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 13,
                      }}>
                        {m.user === '핑퐁이' ? '🤖' : m.user[0]}
                      </div>
                    )}
                    <div style={{ maxWidth: '75%' }}>
                      {!m.isMe && (
                        <div style={{ fontSize: 10, color: T.textSec, marginBottom: 3, fontWeight: 600 }}>
                          {m.user}
                        </div>
                      )}
                      <div style={{
                        padding: '8px 11px', borderRadius: 10, fontSize: 13,
                        background: chatSearch && m.msg.toLowerCase().includes(chatSearch.toLowerCase())
                          ? 'rgba(255,235,59,0.18)'
                          : m.isMe
                          ? 'rgba(0,230,118,0.12)'
                          : m.user === '핑퐁이'
                          ? 'rgba(0,229,255,0.08)'
                          : 'rgba(255,255,255,0.06)',
                        border: `1px solid ${chatSearch && m.msg.toLowerCase().includes(chatSearch.toLowerCase()) ? 'rgba(255,235,59,0.4)' : m.isMe ? 'rgba(0,230,118,0.25)' : m.user === '핑퐁이' ? 'rgba(0,229,255,0.2)' : T.border}`,
                        color: T.text, lineHeight: 1.5,
                      }}>
                        {m.msg}
                      </div>
                      <div style={{ fontSize: 10, color: T.textSec, marginTop: 2, textAlign: m.isMe ? 'right' : 'left' }}>
                        {m.time}
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>

              {/* 입력창 */}
              <div style={{
                padding: '10px 12px',
                borderTop: `1px solid ${T.border}`,
                display: 'flex', gap: 8, alignItems: 'center',
              }}>
                <input
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); } }}
                  placeholder="메시지를 입력하세요..."
                  style={{
                    flex: 1, padding: '9px 12px', borderRadius: 10,
                    background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.border}`,
                    color: T.text, fontSize: 13, outline: 'none',
                  }}
                />
                <button
                  onClick={sendChat}
                  disabled={!chatInput.trim()}
                  style={{
                    width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                    background: chatInput.trim() ? T.green : 'rgba(255,255,255,0.08)',
                    border: 'none', cursor: chatInput.trim() ? 'pointer' : 'default',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 16, transition: 'background 0.15s',
                    color: chatInput.trim() ? T.bgDeep : T.textSec,
                  }}
                >↑</button>
              </div>
            </div>
          ) : (
            /* 미리보기 (접힌 상태) */
            <div style={{ padding: '0 16px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
              {previewMsgs.map(m => (
                <div key={m.id} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <div style={{
                    width: 22, height: 22, borderRadius: 6, flexShrink: 0,
                    background: m.user === '핑퐁이' ? 'rgba(0,229,255,0.15)' : 'rgba(255,255,255,0.08)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11,
                  }}>
                    {m.user === '핑퐁이' ? '🤖' : m.user[0]}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: T.textSec }}>{m.user}&nbsp;</span>
                    <span style={{ fontSize: 12, color: T.text }}
                      dangerouslySetInnerHTML={{ __html: m.msg.length > 40 ? m.msg.slice(0, 40) + '…' : m.msg }}
                    />
                  </div>
                  <span style={{ fontSize: 10, color: T.textSec, flexShrink: 0 }}>{m.time}</span>
                </div>
              ))}
              <div
                onClick={() => setChatExpanded(true)}
                style={{ fontSize: 11, color: T.textSec, textAlign: 'center', cursor: 'pointer', paddingTop: 4 }}
              >
                더보기 · 전체 {chatMessages.length}개 →
              </div>
            </div>
          )}
        </div>
      </div>

      <div style={{ height: 80 }} />

      {/* ── 오퍼 상세 시트 ── */}
      <OfferDetailSheet
        offer={selectedOffer}
        target={pTarget}
        onClose={() => setSelectedOffer(null)}
        onBuy={async (offer) => {
          if (!window.confirm('이 오퍼로 구매 예약을 진행하시겠어요?')) return;
          try {
            await createReservation({
              deal_id: Number(dealId),
              offer_id: offer.id,
              buyer_id: user?.id ?? 0,
              qty: 1,
            });
            showToast('구매 예약이 완료되었어요!', 'success');
            setSelectedOffer(null);
            navigate('/my-orders');
          } catch {
            showToast('구매 예약에 실패했어요. 다시 시도해주세요.', 'error');
          }
        }}
      />

      {/* ── 목표가 수정 모달 ── */}
      {showTargetEditModal && (
        <div
          onClick={() => setShowTargetEditModal(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 9990, display: 'flex', alignItems: 'flex-end' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{ width: '100%', maxHeight: '90dvh', background: T.bgSurface, borderRadius: '20px 20px 0 0', padding: '20px 20px 40px', overflowY: 'auto' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: T.text }}>목표가 변경</span>
              <button onClick={() => setShowTargetEditModal(false)} style={{ fontSize: 18, color: T.textSec, cursor: 'pointer' }}>✕</button>
            </div>

            <div style={{ fontSize: 13, color: T.textSec, marginBottom: 16 }}>현재 목표가: <strong style={{ color: T.green }}>₩{currentDisplayPrice.toLocaleString()}</strong></div>

            {/* 새 목표가 입력 */}
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.textSec, marginBottom: 8 }}>새 목표가</div>
              <div style={{ position: 'relative' }}>
                <span style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', fontSize: 14, color: T.textSec }}>₩</span>
                <input
                  type="text"
                  value={newTargetPrice > 0 ? newTargetPrice.toLocaleString() : ''}
                  onChange={e => { const n = parseInt(e.target.value.replace(/\D/g, ''), 10) || 0; setNewTargetPrice(n); }}
                  style={{ width: '100%', padding: '12px 14px 12px 30px', fontSize: 17, fontWeight: 700, borderRadius: 12, background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.border}`, color: T.text, boxSizing: 'border-box' as const }}
                />
              </div>
            </div>

            {/* 근거 텍스트 */}
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.textSec, marginBottom: 8 }}>변경 근거/이유 (필수, 최소 20자)</div>
              <textarea
                value={targetReason}
                onChange={e => setTargetReason(e.target.value)}
                placeholder="예: 네이버 쇼핑에서 해당 모델이 265,000원에 판매되는 것을 확인했습니다..."
                rows={5}
                style={{ width: '100%', padding: '12px 14px', fontSize: 13, borderRadius: 12, background: 'rgba(255,255,255,0.05)', border: `1px solid ${T.border}`, color: T.text, resize: 'none', boxSizing: 'border-box' as const }}
              />
              <div style={{ textAlign: 'right', fontSize: 11, color: targetReason.length >= 20 ? T.green : T.textSec, marginTop: 4 }}>
                {targetReason.length}/1000
              </div>
            </div>

            {/* 이미지 업로드 */}
            <div style={{ marginBottom: 18 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: T.textSec, marginBottom: 8 }}>증빙 이미지 (최대 2장)</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {targetImages.length < 2 && (
                  <button onClick={() => targetImgRef.current?.click()} style={{ width: 64, height: 64, borderRadius: 10, background: 'rgba(255,255,255,0.04)', border: `1px dashed ${T.border}`, cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2 }}>
                    <span style={{ fontSize: 20 }}>📷</span>
                    <span style={{ fontSize: 9, color: T.textSec }}>추가</span>
                  </button>
                )}
                {targetImages.map((src, i) => (
                  <div key={i} style={{ position: 'relative', width: 64, height: 64 }}>
                    <img src={src} alt="" style={{ width: 64, height: 64, borderRadius: 10, objectFit: 'cover', border: `1px solid ${T.border}` }} />
                    <button onClick={() => setTargetImages(prev => prev.filter((_, idx) => idx !== i))} style={{ position: 'absolute', top: -6, right: -6, width: 18, height: 18, borderRadius: '50%', background: '#ff5252', border: 'none', color: '#fff', fontSize: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>✕</button>
                  </div>
                ))}
              </div>
              <input
                ref={targetImgRef}
                type="file" accept="image/*" multiple
                style={{ display: 'none' }}
                onChange={e => {
                  const files = e.target.files;
                  if (!files) return;
                  const next = [...targetImages];
                  for (let i = 0; i < files.length; i++) {
                    if (next.length >= 2) break;
                    next.push(URL.createObjectURL(files[i]));
                  }
                  setTargetImages(next);
                  e.target.value = '';
                }}
              />
            </div>

            <div style={{ padding: '10px 12px', background: 'rgba(255,152,0,0.08)', border: '1px solid rgba(255,152,0,0.2)', borderRadius: 10, marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: '#ff9800' }}>⚠️ 변경 내용은 모든 참여자와 판매자에게 공개됩니다.</div>
            </div>

            <button
              disabled={targetReason.length < 20 || newTargetPrice <= 0 || targetSubmitting}
              onClick={async () => {
                setTargetSubmitting(true);
                await new Promise(r => setTimeout(r, 1000));
                setCurrentDisplayPrice(newTargetPrice);
                setCurrentTargetReason(targetReason);
                setCurrentTargetImages(targetImages);
                setTargetSubmitting(false);
                setShowTargetEditModal(false);
              }}
              style={{
                width: '100%', padding: '14px', borderRadius: 12, fontSize: 14, fontWeight: 800,
                background: targetReason.length >= 20 && newTargetPrice > 0 && !targetSubmitting
                  ? `linear-gradient(135deg, ${T.green}, #39ff14)` : 'rgba(0,230,118,0.2)',
                color: targetReason.length >= 20 ? '#0a0e1a' : T.textSec,
                cursor: targetReason.length >= 20 && newTargetPrice > 0 ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              }}
            >
              {targetSubmitting && <div style={{ width: 16, height: 16, borderRadius: '50%', border: '2px solid rgba(0,0,0,0.3)', borderTopColor: '#0a0e1a', animation: 'spin 0.8s linear infinite' }} />}
              목표가 변경하기
            </button>
          </div>
        </div>
      )}

      {/* ── 하단 고정 CTA (판매자용) ── */}
      <div style={{
        position: 'sticky', bottom: 70, left: 0, right: 0, zIndex: 996,
        padding: '12px 20px',
        paddingBottom: 'max(12px, env(safe-area-inset-bottom, 12px))',
        background: `linear-gradient(to bottom, transparent 0%, ${T.bgDeep} 35%)`,
      }}>
        <button
          onClick={() => navigate(`/deal/${dealId ?? ''}/offer/create`)}
          style={{
            width: '100%', padding: '16px',
            background: `linear-gradient(135deg, #00f0ff, #39ff14)`,
            color: '#0a0e1a', fontWeight: 800, fontSize: 16,
            border: 'none', borderRadius: 14,
            cursor: 'pointer',
            boxShadow: '0 4px 24px rgba(0,240,255,0.25)',
            transition: 'opacity 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.opacity = '0.88'; }}
          onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}
        >
          🏷️ 이 딜에 오퍼 제출하기
        </button>
      </div>

      {/* ── 예측 모달 ── */}
      {showPredModal && (
        <>
          <div onClick={() => setShowPredModal(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 9998 }} />
          <div style={{
            position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 9999,
            background: T.bgCard, borderRadius: '20px 20px 0 0', padding: '24px 20px 32px',
            boxShadow: '0 -8px 40px rgba(0,0,0,0.5)',
          }}>
            <div style={{ fontSize: 16, fontWeight: 800, color: T.text, marginBottom: 4 }}>🎯 가격 예측하기</div>
            <div style={{ fontSize: 12, color: T.textSec, marginBottom: 16 }}>이 딜의 최종 거래 가격을 예측해보세요!</div>
            <input
              type="number"
              value={predPrice}
              onChange={e => setPredPrice(e.target.value)}
              placeholder="예상 가격 (원)"
              style={{
                width: '100%', boxSizing: 'border-box', padding: '13px 14px',
                borderRadius: 12, fontSize: 16, fontWeight: 600,
                background: T.bgSurface, border: `1px solid ${T.border}`,
                color: T.text, marginBottom: 12,
              }}
            />
            {predPrice && Number(predPrice) > 0 && (
              <div style={{ fontSize: 12, color: T.textSec, marginBottom: 12 }}>
                예측가: ₩{Number(predPrice).toLocaleString('ko-KR')}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setShowPredModal(false)}
                style={{ flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 600, background: T.bgSurface, border: `1px solid ${T.border}`, color: T.textSec, cursor: 'pointer' }}
              >취소</button>
              <button
                disabled={predSubmitting || !predPrice || Number(predPrice) <= 0}
                onClick={async () => {
                  setPredSubmitting(true);
                  try {
                    await submitPrediction(Number(dealId), Number(predPrice));
                    setPredDone(true);
                    setShowPredModal(false);
                  } catch {
                    // API 실패해도 UI는 성공 처리 (mock 모드 대응)
                    setPredDone(true);
                    setShowPredModal(false);
                  }
                  setPredSubmitting(false);
                }}
                style={{
                  flex: 2, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  background: (!predPrice || Number(predPrice) <= 0) ? 'rgba(0,230,118,0.1)' : T.green,
                  color: (!predPrice || Number(predPrice) <= 0) ? T.green : '#0a0a0f',
                  cursor: predSubmitting ? 'wait' : 'pointer',
                  opacity: predSubmitting ? 0.6 : 1,
                }}
              >{predSubmitting ? '제출 중...' : '예측 제출'}</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
