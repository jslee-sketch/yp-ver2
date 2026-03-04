import { useRef, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { DealHeader } from '../components/deal/DealHeader';
import { DealStageProgress } from '../components/deal/DealStageProgress';
import { PriceDashboard } from '../components/deal/PriceDashboard';
import { SpectatorPanel } from '../components/deal/SpectatorPanel';
import { OfferList } from '../components/deal/OfferList';
import { PingpongCard } from '../components/common/PingpongCard';
import { BottomSheet } from '../components/common/BottomSheet';
import { ProductDetailSheet } from '../components/deal/ProductDetailSheet';
import { fetchDeal } from '../api/dealApi';
import type { Deal, Offer, SpectatorStats, DealStage } from '../types';

// ── Mock 데이터 (API 실패 시 fallback) ──────────────
function makeMockDeal(id: number): Deal & { current_stage: string; stage_deadline_at: string; stages: DealStage[] } {
  return {
    id,
    product_name: '(로딩 실패)',
    brand: '',
    category: '',
    desired_price: 0,
    anchor_price: 0,
    status: 'OPEN',
    deadline_at: new Date(Date.now() + 23 * 3600000).toISOString(),
    participants_count: 0,
    spectator_count: 0,
    offer_count: 0,
    avg_prediction: 0,
    created_at: new Date().toISOString(),
    current_stage: 'deal_open',
    stage_deadline_at: new Date(Date.now() + 23 * 3600000).toISOString(),
    stages: [
      { key: 'deal_open',       label: '딜 모집',   completed: true },
      { key: 'offer_competing', label: '오퍼 경쟁', completed: false },
      { key: 'deal_closed',     label: '성사',       completed: false },
      { key: 'payment',         label: '결제',       completed: false },
      { key: 'shipping',        label: '배송',       completed: false },
      { key: 'completed',       label: '완료',       completed: false },
    ],
  };
}

const OFFERS: Offer[] = [
  { id: 1, seller_name: '디지털플러스', price: 89000, tier: 'PREMIUM',  rating: 4.8, review_count: 342, shipping_fee: 0,    delivery_days: 2, warranty_months: 12 },
  { id: 2, seller_name: '테크마켓',     price: 91000, tier: 'PREMIUM',  rating: 4.6, review_count: 215, shipping_fee: 0,    delivery_days: 3, warranty_months: 6  },
  { id: 3, seller_name: '애플매니아',   price: 93500, tier: 'MATCHING', rating: 4.9, review_count: 891, shipping_fee: 0,    delivery_days: 1, warranty_months: 12 },
  { id: 4, seller_name: '전자왕',       price: 96000, tier: 'BELOW',    rating: 4.2, review_count: 67,  shipping_fee: 3000, delivery_days: 4, warranty_months: 0  },
];

const SPECTATOR_STATS: SpectatorStats = {
  deal_id: 15,
  total_count: 87,
  avg_predicted_price: 92000,
  median_predicted_price: 91000,
  buckets: [
    { label: '85-88K', min: 85000, max: 88000, count: 10, pct: 12 },
    { label: '88-91K', min: 88000, max: 91000, count: 30, pct: 35 },
    { label: '91-94K', min: 91000, max: 94000, count: 24, pct: 28 },
    { label: '94-97K', min: 94000, max: 97000, count: 16, pct: 18 },
    { label: '97-100K', min: 97000, max: 100000, count: 7, pct: 7 },
  ],
  my_prediction: null,
};

const PRODUCT_DETAIL = {
  options: [
    { title: '색상', selected_value: '블랙', values: ['화이트', '블랙'] },
    { title: '용량', selected_value: '256GB', values: ['128GB', '256GB', '512GB'] },
  ],
  conditions: {
    shipping_fee_krw: 0, warranty_months: 12, delivery_days: 2,
    return_policy: '7일 이내 무료 반품', condition_grade: '미개봉',
  },
  naver_lowest_price: 103900,
  naver_product_name: 'Apple 에어팟 프로 2세대 (USB-C)',
  ai_analyzed_at: new Date(Date.now() - 3600000).toISOString(),
};

const MOCK_CHAT = [
  { id: 1, user: '가격파괴자',  msg: '무료배송 아닌 오퍼도 있나요?',              time: '13:41' },
  { id: 2, user: '사냥꾼87',   msg: '디지털플러스 1년보증 괜찮은듯',              time: '13:43' },
  { id: 3, user: '가격파괴자',  msg: 'ㅇㅇ 그거 선택하려구',                      time: '13:44' },
  { id: 4, user: '절약왕_kim', msg: '배송 2일이면 충분히 빠른 거 아닌가요?',     time: '13:45' },
  { id: 5, user: '사냥꾼87',   msg: '맞아요, 1년보증까지 있으니 좋은 것 같아요', time: '13:47' },
];

function getPingpongMessage(deal: Deal, offers: Offer[]): string {
  if (!offers.length) return '아직 오퍼가 없어요. 판매자들이 준비 중이에요 — 조금만 기다려주세요! ⏳';
  const lowest = offers[0];
  const premiumCount = offers.filter(o => o.tier === 'PREMIUM').length;
  const saving = deal.anchor_price ? deal.anchor_price - lowest.price : 0;
  const savingPct = deal.anchor_price ? Math.round((saving / deal.anchor_price) * 100) : 0;
  if (lowest.price <= deal.desired_price) {
    return `목표가보다 ${(deal.desired_price - lowest.price).toLocaleString('ko-KR')}원 더 저렴한 오퍼가 있어요! 🎉 PREMIUM 오퍼가 ${premiumCount}개나 경쟁 중이에요.`;
  }
  return `현재 최저 오퍼가 시장가보다 ${savingPct}% 저렴해요. 관전자 ${deal.spectator_count}명의 평균 예측가는 ${(deal.avg_prediction ?? 0).toLocaleString('ko-KR')}원이에요. 👍`;
}

// ── 페이지 ───────────────────────────────────────────
export default function DealDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const dealId = Number(id) || 0;

  const [deal, setDeal] = useState<Deal & { current_stage: string; stage_deadline_at: string; stages: DealStage[] }>(makeMockDeal(dealId));
  const [loading, setLoading] = useState(true);
  const [spectatorStats, setSpectatorStats] = useState<SpectatorStats>(SPECTATOR_STATS);
  const [chatSheetOpen, setChatSheetOpen]   = useState(false);
  const [productSheetOpen, setProductSheetOpen] = useState(false);
  const [chatMsg, setChatMsg] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);

  // ── 딜 데이터 페칭 ──
  useEffect(() => {
    if (!dealId) return;
    setLoading(true);
    fetchDeal(dealId).then(raw => {
      if (raw && typeof raw === 'object') {
        const d = raw as Record<string, unknown>;
        setDeal({
          id: dealId,
          product_name: (d.product_name as string) || `딜 #${dealId}`,
          brand: (d.brand as string) || '',
          category: (d.category as string) || '',
          desired_price: (d.target_price as number) ?? (d.max_budget as number) ?? 0,
          anchor_price: (d.anchor_price as number) ?? 0,
          status: d.status === 'open' ? 'OPEN' : d.status === 'closed' ? 'CLOSED' : 'OPEN',
          deadline_at: (d.deadline_at as string) || new Date(Date.now() + 72 * 3600000).toISOString(),
          participants_count: (d.current_qty as number) ?? 0,
          spectator_count: 0,
          offer_count: 0,
          avg_prediction: 0,
          created_at: (d.created_at as string) || new Date().toISOString(),
          current_stage: d.status === 'closed' ? 'deal_closed' : 'offer_competing',
          stage_deadline_at: (d.deadline_at as string) || new Date(Date.now() + 72 * 3600000).toISOString(),
          stages: [
            { key: 'deal_open',       label: '딜 모집',   completed: true },
            { key: 'offer_competing', label: '오퍼 경쟁', completed: d.status !== 'open', deadline_at: (d.deadline_at as string) || undefined },
            { key: 'deal_closed',     label: '성사',       completed: d.status === 'closed' || d.status === 'archived' },
            { key: 'payment',         label: '결제',       completed: false },
            { key: 'shipping',        label: '배송',       completed: false },
            { key: 'completed',       label: '완료',       completed: d.status === 'archived' },
          ],
        });
      }
    }).finally(() => setLoading(false));
  }, [dealId]);

  useEffect(() => {
    if (chatSheetOpen) {
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 300);
    }
  }, [chatSheetOpen]);

  const lowestOffer = OFFERS[0];
  const pingpongMsg = getPingpongMessage(deal, OFFERS);

  if (loading) {
    return (
      <div style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🔄</div>
          <div style={{ fontSize: 14, color: 'var(--text-secondary)' }}>딜 정보를 불러오는 중...</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100dvh', paddingBottom: 32 }}>
      {/* 미니 헤더: 뒤로가기 + 알림 */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 48,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px',
        background: 'var(--bg-primary)',
        borderBottom: '1px solid var(--border-subtle)',
      }}>
        <button
          onClick={() => navigate(-1)}
          style={{ padding: '6px 8px', color: 'var(--text-primary)', fontSize: 20, cursor: 'pointer' }}
        >←</button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <button
            onClick={() => navigate(`/deal/${deal.id}/journey`)}
            style={{
              padding: '4px 10px', borderRadius: 8, fontSize: 11, fontWeight: 700,
              background: 'rgba(0,230,118,0.1)', border: '1px solid rgba(0,230,118,0.2)',
              color: 'var(--accent-green)', cursor: 'pointer',
            }}
          >
            📊 가격 여정
          </button>
          <button style={{ padding: '6px 8px', color: 'var(--text-muted)', fontSize: 18, cursor: 'pointer' }}>🔔</button>
        </div>
      </div>

      <div className="page-enter">
        {/* 딜 헤더 (상품명 탭 → 상품 상세 시트) */}
        <div onClick={() => setProductSheetOpen(true)} style={{ cursor: 'pointer' }}>
          <DealHeader deal={deal} />
        </div>

        {/* 딜 단계 프로그레스 + 카운트다운 */}
        <DealStageProgress
          stages={deal.stages}
          currentStageKey={deal.current_stage}
          deadlineAt={deal.stage_deadline_at}
        />

        <div style={{ height: 1, background: 'var(--border-subtle)', margin: '0 16px 16px' }} />

        {/* 가격 대시보드 */}
        <PriceDashboard
          anchorPrice={deal.anchor_price}
          desiredPrice={deal.desired_price}
          lowestOfferPrice={lowestOffer?.price ?? null}
        />

        {/* 관전자 예측 분포 */}
        <SpectatorPanel
          stats={spectatorStats}
          onPredict={price => setSpectatorStats(prev => ({ ...prev, my_prediction: price }))}
        />

        {/* 오퍼 목록 */}
        <OfferList offers={OFFERS} />

        {/* 핑퐁이 인사이트 */}
        <div style={{ margin: '0 16px 16px' }}>
          <PingpongCard message={pingpongMsg} />
        </div>

        {/* 딜방 채팅 미리보기 */}
        <div style={{
          margin: '0 16px 32px',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-lg)',
          overflow: 'hidden',
        }}>
          <button
            onClick={() => setChatSheetOpen(true)}
            style={{
              width: '100%', padding: '13px 16px',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              background: 'var(--bg-tertiary)',
              color: 'var(--text-secondary)', fontSize: 13, fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <span>💬 딜방 채팅 ({MOCK_CHAT.length})</span>
            <span style={{ fontSize: 12, color: 'var(--accent-blue)' }}>펼치기 ↑</span>
          </button>
          <div style={{ background: 'var(--bg-secondary)', padding: '10px 16px' }}>
            {MOCK_CHAT.slice(-3).map((c, i, arr) => (
              <div key={c.id} style={{
                display: 'flex', gap: 8, padding: '5px 0', alignItems: 'flex-start',
                borderBottom: i < arr.length - 1 ? '1px solid var(--border-subtle)' : 'none',
              }}>
                <span style={{ fontSize: 11, color: 'var(--accent-blue)', fontWeight: 600, flexShrink: 0, minWidth: 60 }}>
                  {c.user}
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.msg}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 바텀 시트: 딜방 채팅 */}
      <BottomSheet isOpen={chatSheetOpen} onClose={() => setChatSheetOpen(false)} title="💬 딜방 채팅" height="70vh">
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px' }}>
            {MOCK_CHAT.map(c => (
              <div key={c.id} style={{ marginBottom: 14 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'baseline', marginBottom: 3 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent-blue)' }}>{c.user}</span>
                  <span style={{ fontSize: 10, color: 'var(--text-disabled)' }}>{c.time}</span>
                </div>
                <div style={{
                  display: 'inline-block', padding: '8px 12px',
                  background: 'var(--bg-elevated)',
                  borderRadius: '4px 12px 12px 12px',
                  fontSize: 13, color: 'var(--text-primary)', maxWidth: '80%', lineHeight: 1.5,
                }}>
                  {c.msg}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          <div style={{
            padding: '12px 16px', borderTop: '1px solid var(--border-subtle)',
            background: 'var(--bg-secondary)', display: 'flex', gap: 8,
          }}>
            <input
              value={chatMsg}
              onChange={e => setChatMsg(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && chatMsg.trim()) setChatMsg(''); }}
              type="text" placeholder="메시지 입력..."
              style={{
                flex: 1, padding: '10px 14px', fontSize: 13,
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)',
              }}
            />
            <button
              onClick={() => setChatMsg('')}
              style={{
                padding: '10px 16px', background: 'var(--accent-green)',
                color: '#0a0a0f', borderRadius: 'var(--radius-sm)',
                fontSize: 13, fontWeight: 700, cursor: 'pointer',
              }}
            >전송</button>
          </div>
        </div>
      </BottomSheet>

      {/* 바텀 시트: 상품 상세 */}
      <ProductDetailSheet
        isOpen={productSheetOpen}
        onClose={() => setProductSheetOpen(false)}
        productName={deal.product_name}
        brand={deal.brand}
        canonicalName="Apple AirPods Pro 2nd Gen USB-C"
        options={PRODUCT_DETAIL.options}
        conditions={PRODUCT_DETAIL.conditions}
        naverLowestPrice={PRODUCT_DETAIL.naver_lowest_price}
        naverProductName={PRODUCT_DETAIL.naver_product_name}
        aiAnalyzedAt={PRODUCT_DETAIL.ai_analyzed_at}
      />
    </div>
  );
}
