import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchDeal } from '../api/dealApi';
import { fetchChatMessages, sendChatMessage } from '../api/chatApi';
import { submitPrediction } from '../api/spectatorApi';
import { createReservation } from '../api/reservationApi';
import { showToast } from '../components/common/Toast';
import { FEATURES } from '../config';
import { BarChart, Bar, XAxis, YAxis, Cell, ResponsiveContainer } from 'recharts';
import { PriceFaceSection }   from '../components/journey/PriceFaceSection';
import { OfferListSection }   from '../components/journey/OfferListSection';
import { GroupCurveSection }  from '../components/journey/GroupCurveSection';
import { OfferDetailSheet }   from '../components/journey/OfferDetailSheet';
import { T }                  from '../components/journey/journeyTokens';
import type { JourneyOffer }  from '../components/journey/types';

// ── 가격 상수 ───────────────────────────────────────────
const P_ANCHOR  = 349000;
const P_TARGET  = 279000;
const CURRENT_Q = 32;
const Q_TARGET  = 100;

// ── 딜 방장/단계 Mock ──────────────────────────────────
const MOCK_DEAL_EXTENDED = {
  creator_id: 1,
  phase: 'RECRUITING' as 'RECRUITING' | 'OFFER_PHASE',
  target_price_reason: '',
  target_price_images: [] as string[],
};
const CURRENT_USER_ID = 1;

// ── Mock 오퍼 데이터 ────────────────────────────────────
const MOCK_OFFERS: JourneyOffer[] = [
  {
    id: 1, seller: '디지텍', icon: '⛵',
    rawPrice: 305000, adjPrice: 286500,
    offerIndexPct: 109,
    totalQty: 20, remainQty: 14,
    shipDays: 2, shipFee: '3,000원', refund: '보통', asGrade: '보통',
    sellerTier: '프로', sellerScore: 82, sellerDeals: 47, sellerRate: '96%',
    condTags: [
      { text: '배송 2일',   type: 'good' },
      { text: '배송비 별도', type: 'neutral' },
      { text: '환불 보통',  type: 'neutral' },
      { text: '정품 보장',  type: 'good' },
    ],
    group: 'BELOW',
    groupAdj: -12200, groupResult: 292800,
    condAdj: -6300, condResult: 286500,
    condDetail: '배송 빠름 +3.2% · 배송비 별도 −2.1% · 환불 보통 −0.1% · 신뢰도 높음 +1.8%',
    verdictType: 'good', verdictEmoji: '🎯', verdictTitle: '목표가에 거의 도달!',
    verdictDesc: '액면가로는 <strong>26,000원 차이</strong>지만 동일 기준 보정 후 <strong style="color:#39ff14">7,500원 차이</strong>예요.',
  },
  {
    id: 2, seller: '테크마트', icon: '🚤',
    rawPrice: 319000, adjPrice: 289100,
    offerIndexPct: 114,
    totalQty: 30, remainQty: 22,
    shipDays: 3, shipFee: '무료', refund: '우수', asGrade: '우수',
    sellerTier: '마스터', sellerScore: 91, sellerDeals: 123, sellerRate: '98%',
    condTags: [
      { text: '배송 3일', type: 'good' },
      { text: '무료배송', type: 'good' },
      { text: '환불 우수', type: 'good' },
      { text: 'AS 우수',  type: 'good' },
    ],
    group: 'BELOW',
    groupAdj: -19100, groupResult: 299900,
    condAdj: -10800, condResult: 289100,
    condDetail: '배송 보통 +0.5% · 무료배송 +2.1% · 환불 우수 +2.3% · 신뢰도 매우 높음 +3.1%',
    verdictType: 'good', verdictEmoji: '✨', verdictTitle: '조건이 뛰어난 오퍼',
    verdictDesc: '액면가는 높지만 <strong>모든 조건이 우수</strong>해서 보정 후 <strong style="color:#39ff14">10,100원 차이</strong>예요.',
  },
  {
    id: 3, seller: '옥션셀러', icon: '🛶',
    rawPrice: 298000, adjPrice: 302500,
    offerIndexPct: 107,
    totalQty: 15, remainQty: 15,
    shipDays: 5, shipFee: '무료', refund: '보통', asGrade: '기본',
    sellerTier: '루키', sellerScore: 58, sellerDeals: 8, sellerRate: '88%',
    condTags: [
      { text: '배송 5일', type: 'bad' },
      { text: '무료배송', type: 'good' },
      { text: '환불 보통', type: 'neutral' },
      { text: 'AS 기본',  type: 'bad' },
    ],
    group: 'BELOW',
    groupAdj: -6800, groupResult: 291200,
    condAdj: 11300, condResult: 302500,
    condDetail: '배송 느림 −2.8% · 무료배송 +2.1% · 환불 보통 −0.1% · 신뢰도 낮음 −3.2%',
    verdictType: 'close', verdictEmoji: '⚠️', verdictTitle: '조건 보정 시 불리',
    verdictDesc: '액면가는 싸 보이지만 <strong>배송 느리고 신뢰도 낮아서</strong> 보정 후 <strong style="color:#ff8c42">23,500원 차이</strong>예요.',
  },
  {
    id: 4, seller: '디지털프라자', icon: '🚢',
    rawPrice: 295000, adjPrice: 315800,
    offerIndexPct: 106,
    totalQty: 10, remainQty: 10,
    shipDays: 7, shipFee: '5,000원', refund: '불가', asGrade: '없음',
    sellerTier: '신규', sellerScore: 42, sellerDeals: 3, sellerRate: '67%',
    condTags: [
      { text: '배송 7일',       type: 'bad' },
      { text: '배송비 5,000원', type: 'bad' },
      { text: '환불 불가',      type: 'bad' },
      { text: 'AS 없음',        type: 'bad' },
    ],
    group: 'BELOW',
    groupAdj: -3200, groupResult: 291800,
    condAdj: 24000, condResult: 315800,
    condDetail: '배송 매우 느림 −4.1% · 배송비 높음 −3.5% · 환불 불가 −5.2% · 신뢰도 매우 낮음 −4.8%',
    verdictType: 'far', verdictEmoji: '🚫', verdictTitle: '조건이 많이 불리',
    verdictDesc: '액면가 최저지만 <strong>조건이 나빠서</strong> 보정 후 <strong style="color:#ff2d78">36,800원 차이</strong>.',
  },
  {
    id: 5, seller: '스마트딜', icon: '🎯',
    rawPrice: 275000, adjPrice: 272000,
    offerIndexPct: 99,
    totalQty: 5, remainQty: 2,
    shipDays: 1, shipFee: '무료', refund: '우수', asGrade: '우수',
    sellerTier: '마스터', sellerScore: 95, sellerDeals: 201, sellerRate: '99%',
    condTags: [
      { text: '배송 1일', type: 'good' },
      { text: '무료배송', type: 'good' },
      { text: '환불 우수', type: 'good' },
      { text: 'AS 우수',  type: 'good' },
    ],
    group: 'PREMIUM',
    groupAdj: -1500, groupResult: 273500,
    condAdj: -1500, condResult: 272000,
    condDetail: '배송 매우 빠름 +4.2% · 무료배송 +2.1% · 환불 우수 +2.3% · 신뢰도 최상 +3.5%',
    verdictType: 'good', verdictEmoji: '🏆', verdictTitle: '목표가 이하! 최고 오퍼',
    verdictDesc: '<strong style="color:#39ff14">목표가보다 7,000원 저렴</strong>하고 모든 조건이 최상급!',
    detail: '정품 Apple AirPods Pro 2세대 (USB-C) 미개봉 새제품입니다.\n\n■ 구성품\n- AirPods Pro 본체\n- MagSafe 충전 케이스 (USB-C)\n- 이어팁 4사이즈 (XS/S/M/L)\n- USB-C 케이블\n- 설명서\n\n■ 보증\n- Apple 공식 1년 보증\n- 구매일 기준 AppleCare+ 가입 가능\n\n■ 기타\n- 정식 수입 정품 (KOR 버전)\n- 시리얼 번호 확인 가능\n- 재고 보유 중 (즉시 발송 가능)',
    images: [],
  },
  {
    id: 6, seller: '가전천국', icon: '🏪',
    rawPrice: 279000, adjPrice: 278500,
    offerIndexPct: 100,
    totalQty: 25, remainQty: 18,
    shipDays: 2, shipFee: '무료', refund: '우수', asGrade: '보통',
    sellerTier: '프로', sellerScore: 85, sellerDeals: 67, sellerRate: '95%',
    condTags: [
      { text: '배송 2일', type: 'good' },
      { text: '무료배송', type: 'good' },
      { text: '환불 우수', type: 'good' },
      { text: 'AS 보통',  type: 'neutral' },
    ],
    group: 'MATCHING',
    groupAdj: -8200, groupResult: 270800,
    condAdj: 7700, condResult: 278500,
    condDetail: '배송 빠름 +3.2% · 무료배송 +2.1% · 환불 우수 +2.3% · 신뢰도 높음 +1.8%',
    verdictType: 'good', verdictEmoji: '✅', verdictTitle: '목표가에 부합!',
    verdictDesc: '보정 후에도 <strong style="color:#39ff14">목표가와 거의 동일</strong>한 수준이에요.',
  },
  {
    id: 7, seller: 'IT마켓', icon: '💻',
    rawPrice: 312000, adjPrice: 294000,
    offerIndexPct: Math.round(312000 / P_TARGET * 1000) / 10,
    totalQty: 40, remainQty: 35,
    shipDays: 2, shipFee: '무료', refund: '우수', asGrade: '우수',
    sellerTier: '마스터', sellerScore: 88, sellerDeals: 89, sellerRate: '97%',
    condTags: [
      { text: '배송 2일',   type: 'good' },
      { text: '무료배송',   type: 'good' },
      { text: '환불 우수',  type: 'good' },
      { text: '대량 가능',  type: 'good' },
    ],
    group: 'BELOW',
    groupAdj: -14000, groupResult: 298000,
    condAdj: -4000, condResult: 294000,
    condDetail: '배송 빠름 +3.2% · 무료배송 +2.1% · 환불 우수 +2.3% · 신뢰도 높음 +2.4%',
    verdictType: 'good', verdictEmoji: '📦', verdictTitle: '대량 참여에 유리',
    verdictDesc: '수량이 <strong>40개로 가장 많고</strong> 조건도 우수. 보정 후 <strong style="color:#39ff14">15,000원 차이</strong>.',
  },
  {
    id: 8, seller: '할인왕', icon: '👑',
    rawPrice: 308000, adjPrice: 299000,
    offerIndexPct: Math.round(308000 / P_TARGET * 1000) / 10,
    totalQty: 15, remainQty: 8,
    shipDays: 3, shipFee: '2,500원', refund: '보통', asGrade: '보통',
    sellerTier: '프로', sellerScore: 76, sellerDeals: 34, sellerRate: '94%',
    condTags: [
      { text: '배송 3일',      type: 'good' },
      { text: '배송비 2,500원', type: 'neutral' },
      { text: '환불 보통',     type: 'neutral' },
    ],
    group: 'BELOW',
    groupAdj: -8000, groupResult: 300000,
    condAdj: -1000, condResult: 299000,
    condDetail: '배송 보통 +0.5% · 배송비 소폭 −0.8% · 환불 보통 −0.1% · 신뢰도 보통 +0.7%',
    verdictType: 'close', verdictEmoji: '🤏', verdictTitle: '아쉽게 근접',
    verdictDesc: '보정 후 <strong style="color:#ffe156">20,000원 차이</strong>. 조건이 조금 더 좋으면 근접할 수 있어요.',
  },
  {
    id: 9, seller: '베스트일렉', icon: '⚡',
    rawPrice: 325000, adjPrice: 298500,
    offerIndexPct: Math.round(325000 / P_TARGET * 1000) / 10,
    totalQty: 50, remainQty: 45,
    shipDays: 1, shipFee: '무료', refund: '우수', asGrade: '우수',
    sellerTier: '마스터', sellerScore: 93, sellerDeals: 156, sellerRate: '99%',
    condTags: [
      { text: '당일배송',  type: 'good' },
      { text: '무료배송',  type: 'good' },
      { text: '환불 우수', type: 'good' },
      { text: 'AS 우수',   type: 'good' },
    ],
    group: 'BELOW',
    groupAdj: -22000, groupResult: 303000,
    condAdj: -4500, condResult: 298500,
    condDetail: '배송 매우 빠름 +4.2% · 무료배송 +2.1% · 환불 우수 +2.3% · 신뢰도 최상 +3.5%',
    verdictType: 'close', verdictEmoji: '⚡', verdictTitle: '최다 수량 + 최상 조건',
    verdictDesc: '수량 <strong>50개 최다</strong>, 조건 최상급이지만 액면가가 높아 보정 후 <strong style="color:#ffe156">19,500원 차이</strong>.',
  },
  {
    id: 10, seller: '굿프라이스', icon: '🎪',
    rawPrice: 310000, adjPrice: 305000,
    offerIndexPct: Math.round(310000 / P_TARGET * 1000) / 10,
    totalQty: 12, remainQty: 7,
    shipDays: 4, shipFee: '무료', refund: '보통', asGrade: '기본',
    sellerTier: '루키', sellerScore: 62, sellerDeals: 11, sellerRate: '91%',
    condTags: [
      { text: '배송 4일',  type: 'neutral' },
      { text: '무료배송',  type: 'good' },
      { text: '환불 보통', type: 'neutral' },
    ],
    group: 'BELOW',
    groupAdj: -5000, groupResult: 305000,
    condAdj: 0, condResult: 305000,
    condDetail: '배송 약간 느림 −1.2% · 무료배송 +2.1% · 환불 보통 −0.1% · 신뢰도 보통 −0.8%',
    verdictType: 'close', verdictEmoji: '😐', verdictTitle: '보통 수준',
    verdictDesc: '보정 후에도 <strong style="color:#ffe156">26,000원 차이</strong>로 크게 달라지지 않아요.',
  },
  {
    id: 11, seller: '다이렉트몰', icon: '🏬',
    rawPrice: 335000, adjPrice: 310000,
    offerIndexPct: Math.round(335000 / P_TARGET * 1000) / 10,
    totalQty: 20, remainQty: 20,
    shipDays: 3, shipFee: '무료', refund: '우수', asGrade: '우수',
    sellerTier: '프로', sellerScore: 80, sellerDeals: 52, sellerRate: '96%',
    condTags: [
      { text: '배송 3일',  type: 'good' },
      { text: '무료배송',  type: 'good' },
      { text: '환불 우수', type: 'good' },
    ],
    group: 'BELOW',
    groupAdj: -13000, groupResult: 322000,
    condAdj: -12000, condResult: 310000,
    condDetail: '배송 보통 +0.5% · 무료배송 +2.1% · 환불 우수 +2.3% · 신뢰도 높음 +1.8%',
    verdictType: 'close', verdictEmoji: '📉', verdictTitle: '액면가 대비 보정 효과 큼',
    verdictDesc: '보정으로 <strong>25,000원 절약</strong>되지만 여전히 <strong style="color:#ffe156">31,000원 차이</strong>.',
  },
  {
    id: 12, seller: '테크아울렛', icon: '🔧',
    rawPrice: 342000, adjPrice: 325000,
    offerIndexPct: Math.round(342000 / P_TARGET * 1000) / 10,
    totalQty: 8, remainQty: 8,
    shipDays: 5, shipFee: '4,000원', refund: '기본', asGrade: '없음',
    sellerTier: '신규', sellerScore: 38, sellerDeals: 2, sellerRate: '50%',
    condTags: [
      { text: '배송 5일',      type: 'bad' },
      { text: '배송비 4,000원', type: 'bad' },
      { text: '환불 기본',     type: 'bad' },
      { text: 'AS 없음',      type: 'bad' },
    ],
    group: 'BELOW',
    groupAdj: -2000, groupResult: 340000,
    condAdj: -15000, condResult: 325000,
    condDetail: '배송 느림 −2.8% · 배송비 높음 −2.8% · 환불 기본 −2.5% · 신뢰도 매우 낮음 −5.2%',
    verdictType: 'far', verdictEmoji: '🚫', verdictTitle: '조건이 전반적으로 불리',
    verdictDesc: '액면가도 높고 조건도 나빠서 보정 후 <strong style="color:#ff2d78">46,000원 차이</strong>.',
  },
];

const LOWEST_BELOW = [...MOCK_OFFERS]
  .filter(o => o.group === 'BELOW')
  .sort((a, b) => a.adjPrice - b.adjPrice)[0];

// ── 딜 단계 ───────────────────────────────────────────────
const STAGES = ['딜모집', '오퍼경쟁', '성사', '결제', '배송', '완료'];
const STAGE_CURRENT = 1;

// ── 마감 타이머 (모듈 로드 시점 기준) ────────────────────
const DEADLINE_MS = Date.now() + (23 * 3600 + 14 * 60) * 1000;

function getCountdownColor(diff: number): string {
  if (diff < 10 * 60 * 1000)  return '#ff2d78';
  if (diff < 60 * 60 * 1000)  return '#ff2d78';
  if (diff < 3 * 60 * 60 * 1000)  return '#ff8c42';
  if (diff < 12 * 60 * 60 * 1000) return '#ffe156';
  return '#e8eaed';
}

// ── 관전자 예측 데이터 ────────────────────────────────────
const PREDICTION_BUCKETS = [
  { range: '85-88만', count: 12 },
  { range: '88-91만', count: 35 },
  { range: '91-94만', count: 28 },
  { range: '94-97만', count: 18 },
  { range: '97-100만', count: 7 },
];
const PRED_MAX = Math.max(...PREDICTION_BUCKETS.map(b => b.count));
const AVG_PREDICTION = 920000;

// ── 채팅 ──────────────────────────────────────────────────
interface ChatMsg { id: number; user: string; msg: string; time: string; isMe?: boolean; }
const INIT_CHAT: ChatMsg[] = [
  { id: 1, user: '구매왕',    msg: '이 딜 실제로 성사 가능성 있나요? 🤔', time: '14:23' },
  { id: 2, user: '핑퐁이',    msg: '현재 오퍼가 12건이고, 목표가 대비 6,000원 저렴한 오퍼도 있어요! 성사 가능성 높습니다 😊', time: '14:24' },
  { id: 3, user: '테크러버',  msg: '에어팟 프로 2 USB-C 정품 맞죠?', time: '14:31' },
  { id: 4, user: '스마트딜',  msg: '안녕하세요! 저희 오퍼는 100% 정품 보장입니다 🏆', time: '14:32' },
  { id: 5, user: '알뜰구매자', msg: '배송비 포함 가격으로 비교하면 어디가 제일 좋아요?', time: '15:02' },
];

// ── 페이지 ───────────────────────────────────────────────
export default function PriceJourneyPage() {
  const { id: dealId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const [selectedOffer, setSelectedOffer] = useState<JourneyOffer | null>(null);
  const [apiDeal, setApiDeal] = useState<Record<string, unknown> | null>(null);
  const [offers, setOffers] = useState<JourneyOffer[]>(MOCK_OFFERS);

  // ── 방장 목표가 수정 상태 ──
  const isCreator      = MOCK_DEAL_EXTENDED.creator_id === CURRENT_USER_ID;
  const canEditTarget  = isCreator && MOCK_DEAL_EXTENDED.phase === 'RECRUITING';
  const [currentTargetReason, setCurrentTargetReason] = useState(MOCK_DEAL_EXTENDED.target_price_reason);
  const [currentTargetImages, setCurrentTargetImages] = useState<string[]>(MOCK_DEAL_EXTENDED.target_price_images);
  const [showTargetEditModal, setShowTargetEditModal] = useState(false);
  const [newTargetPrice, setNewTargetPrice]           = useState(P_TARGET);
  const [targetReason, setTargetReason]               = useState('');
  const [targetImages, setTargetImages]               = useState<string[]>([]);
  const [targetSubmitting, setTargetSubmitting]       = useState(false);
  const [currentDisplayPrice, setCurrentDisplayPrice] = useState(P_TARGET);
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
      offerIndexPct: Math.round(newPrice / P_TARGET * 1000) / 10,
      totalQty: newQty, remainQty: newQty,
      shipDays: 2, shipFee: shipFeeText, refund: '우수', asGrade: '우수',
      sellerTier: '신규', sellerScore: 0, sellerDeals: 0, sellerRate: '-',
      condTags: [],
      group: newPrice < P_TARGET ? 'PREMIUM' : newPrice === P_TARGET ? 'MATCHING' : 'BELOW',
      groupAdj: 0, groupResult: newPrice,
      condAdj: Math.round(newPrice * -0.02), condResult: Math.round(newPrice * 0.98),
      condDetail: '내가 등록한 오퍼',
      verdictType: newPrice <= P_TARGET ? 'good' : newPrice <= P_TARGET * 1.1 ? 'close' : 'far',
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
  const timerRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  useEffect(() => {
    const tick = () => {
      const diff = DEADLINE_MS - Date.now();
      if (diff <= 0) { setCountdown('마감'); clearInterval(timerRef.current); return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setCountdown(`${h}시간 ${String(m).padStart(2,'0')}분 ${String(s).padStart(2,'0')}초`);
    };
    tick();
    timerRef.current = setInterval(tick, 1000);
    return () => clearInterval(timerRef.current);
  }, []);

  const countdownDiff = DEADLINE_MS - Date.now();
  const countdownColor = getCountdownColor(countdownDiff);
  const isBlinking = countdownDiff < 10 * 60 * 1000;

  // ── API: 딜 메타 + 채팅 로드 ──
  useEffect(() => {
    if (!FEATURES.USE_API_DEALS) return;
    const numId = Number(dealId);
    if (!numId) return;
    fetchDeal(numId).then(d => { if (d) setApiDeal(d as Record<string, unknown>); }).catch(() => {});
  }, [dealId]);

  useEffect(() => {
    if (!FEATURES.USE_API_DEALS) return;
    const numId = Number(dealId);
    if (!numId) return;
    const buyerId = user?.id ?? CURRENT_USER_ID;
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
  }, [dealId, user]);

  // ── 채팅 ──
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>(INIT_CHAT);
  const [chatInput, setChatInput] = useState('');
  const [chatExpanded, setChatExpanded] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const nextChatId = useRef(INIT_CHAT.length + 1);

  const sendChat = () => {
    const txt = chatInput.trim();
    if (!txt) return;
    const now = new Date();
    const time = `${now.getHours()}:${String(now.getMinutes()).padStart(2,'0')}`;
    setChatMessages(prev => [...prev, { id: nextChatId.current++, user: '나', msg: txt, time, isMe: true }]);
    setChatInput('');
    if (FEATURES.USE_API_DEALS) {
      const numId = Number(dealId);
      const userId = user?.id ?? CURRENT_USER_ID;
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
          👥 현재 {apiDeal ? Number(apiDeal.current_qty ?? CURRENT_Q) : CURRENT_Q}명 참여 · 목표 {apiDeal ? Number(apiDeal.desired_qty ?? Q_TARGET) : Q_TARGET}명 · 🏷️ 오퍼 {offers.length}건 · ⏰ 2일 남음
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
                    background: i <= STAGE_CURRENT
                      ? `linear-gradient(90deg, ${T.green}, ${i === STAGE_CURRENT ? T.green + '88' : T.green})`
                      : T.border,
                  }} />
                )}
                {/* 원 */}
                <div style={{
                  width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 700,
                  ...(i < STAGE_CURRENT
                    ? { background: T.green, color: T.bgDeep }
                    : i === STAGE_CURRENT
                    ? { background: T.green, color: T.bgDeep, animation: 'stagePulse 2s infinite' }
                    : { background: T.bgDeep, border: `1px solid ${T.border}`, color: T.textSec }
                  ),
                }}>
                  {i < STAGE_CURRENT ? '✓' : i + 1}
                </div>
                {/* 마지막 원 이후 빈 공간 */}
                {i < STAGES.length - 1 && (
                  <div style={{
                    flex: 1, height: 2,
                    background: i < STAGE_CURRENT ? T.green : T.border,
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
                fontSize: 10, fontWeight: i === STAGE_CURRENT ? 700 : 400,
                color: i <= STAGE_CURRENT ? T.text : T.textSec,
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
              <span style={{ fontSize: 12, color: T.green, fontWeight: 700 }}>현재: {STAGES[STAGE_CURRENT]}</span>
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
        anchor={P_ANCHOR}
        target={currentDisplayPrice}
        lowestPrice={LOWEST_BELOW.rawPrice}
        lowestSeller={LOWEST_BELOW.seller}
        lowestQty={LOWEST_BELOW.totalQty}
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
        target={P_TARGET}
        onSelectOffer={setSelectedOffer}
      />

      {/* ── ③ 공동구매 기대가격 곡선 ── */}
      <GroupCurveSection
        anchor={P_ANCHOR}
        target={P_TARGET}
        currentQ={CURRENT_Q}
        qTarget={Q_TARGET}
        lowestOfferPrice={LOWEST_BELOW.rawPrice}
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
              {AVG_PREDICTION.toLocaleString()}원
            </span>
          </div>

          {/* 바 차트 (div-based for design consistency) */}
          <div style={{ height: 140 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={PREDICTION_BUCKETS} margin={{ top: 4, right: 4, left: -20, bottom: 0 }} barCategoryGap="20%">
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
                  {PREDICTION_BUCKETS.map((b, i) => (
                    <Cell
                      key={i}
                      fill={b.count === PRED_MAX ? T.green : 'rgba(0,230,118,0.25)'}
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
              목표가보다 <span style={{ color: T.green, fontWeight: 700 }}>6,000원 더 저렴한 오퍼</span>가 있어요! 🎉
              <br />PREMIUM 오퍼가 2개나 경쟁 중이에요. 마감 전 참여하면 좋을 것 같아요.
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
            <span style={{ fontSize: 12, color: T.textSec, transition: 'transform 0.2s', display: 'inline-block', transform: chatExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span>
          </div>

          {/* 메시지 영역 */}
          {chatExpanded ? (
            <div>
              {/* 전체 메시지 스크롤 */}
              <div style={{
                maxHeight: 260, overflowY: 'auto', padding: '0 16px 12px',
                display: 'flex', flexDirection: 'column', gap: 10,
              }}>
                {chatMessages.map(m => (
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
                        background: m.isMe
                          ? 'rgba(0,230,118,0.12)'
                          : m.user === '핑퐁이'
                          ? 'rgba(0,229,255,0.08)'
                          : 'rgba(255,255,255,0.06)',
                        border: `1px solid ${m.isMe ? 'rgba(0,230,118,0.25)' : m.user === '핑퐁이' ? 'rgba(0,229,255,0.2)' : T.border}`,
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
        target={P_TARGET}
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
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 500, display: 'flex', alignItems: 'flex-end' }}
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
