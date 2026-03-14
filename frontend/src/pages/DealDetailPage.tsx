import { useRef, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { DealHeader } from '../components/deal/DealHeader';
import { DealStageProgress } from '../components/deal/DealStageProgress';
import DealTimeline, { mapDealToTimelineStage } from '../components/DealTimeline';
import { PriceDashboard } from '../components/deal/PriceDashboard';
import { SpectatorPanel } from '../components/deal/SpectatorPanel';
import { OfferList } from '../components/deal/OfferList';
import { PingpongCard } from '../components/common/PingpongCard';
import { BottomSheet } from '../components/common/BottomSheet';
import { ProductDetailSheet } from '../components/deal/ProductDetailSheet';
import { fetchDeal } from '../api/dealApi';
import { fetchOffersByDeal } from '../api/offerApi';
import { fetchChatMessages, sendChatMessage } from '../api/chatApi';
import { useAuth } from '../contexts/AuthContext';
import { trackBehavior } from '../utils/behaviorTracker';
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

// ── 백엔드 오퍼 → 프론트 Offer 매핑 ──
function mapOffer(raw: Record<string, unknown>, idx: number): Offer {
  const price = (raw.price as number) ?? 0;
  return {
    id: (raw.id as number) ?? idx,
    seller_name: (raw.seller_nickname as string) || (raw.business_name as string) || `셀러 #${raw.seller_id ?? idx}`,
    price,
    tier: (raw.tier as Offer['tier']) || 'MATCHING',
    rating: (raw.rating as number) ?? 0,
    review_count: (raw.review_count as number) ?? 0,
    shipping_fee: (raw.shipping_fee_per_reservation as number) ?? (raw.shipping_fee as number) ?? 0,
    delivery_days: (raw.delivery_days as number) ?? 0,
    warranty_months: (raw.warranty_months as number) ?? 0,
  };
}

// ── 백엔드 채팅 → 표시용 매핑 ──
interface ChatMsg { id: number; user: string; msg: string; time: string }
function mapChat(raw: Record<string, unknown>): ChatMsg {
  const d = raw.created_at ? new Date(raw.created_at as string) : new Date();
  return {
    id: (raw.id as number) ?? 0,
    user: (raw.sender_nickname as string) || `유저 ${raw.buyer_id ?? ''}`,
    msg: (raw.text as string) || '',
    time: `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`,
  };
}

// ── 딜 데이터에서 상품 상세 추출 ──
function buildProductDetail(d: Record<string, unknown>) {
  let options: { title: string; selected_value: string; values: string[] }[] = [];
  try {
    const raw = d.options;
    if (typeof raw === 'string' && raw.startsWith('[')) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        options = parsed.map((g: Record<string, unknown>) => ({
          title: (g.title as string) || '',
          selected_value: (g.selected_value as string) || ((g.values as string[])?.[0] ?? ''),
          values: Array.isArray(g.values) ? g.values as string[] : [],
        }));
      }
    }
  } catch { /* ignore parse errors */ }

  return {
    options,
    conditions: {
      shipping_fee_krw: 0,
      warranty_months: 0,
      delivery_days: 0,
      return_policy: '',
      condition_grade: (d.condition as string) || '신품',
    },
    naver_lowest_price: (d.anchor_price as number) ?? null,
    naver_product_name: (d.product_detail as string) || (d.product_name as string) || '',
    ai_analyzed_at: (d.created_at as string) || null,
  };
}

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
  const { user } = useAuth();
  const buyerId = user?.id ?? null;

  const [deal, setDeal] = useState<Deal & { current_stage: string; stage_deadline_at: string; stages: DealStage[] }>(makeMockDeal(dealId));
  const [loading, setLoading] = useState(true);
  const [offers, setOffers] = useState<Offer[]>([]);
  const [spectatorStats, setSpectatorStats] = useState<SpectatorStats>({
    deal_id: dealId, total_count: 0, avg_predicted_price: null, median_predicted_price: null, buckets: [], my_prediction: null,
  });
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [productDetail, setProductDetail] = useState<ReturnType<typeof buildProductDetail> | null>(null);
  const [chatSheetOpen, setChatSheetOpen]   = useState(false);
  const [productSheetOpen, setProductSheetOpen] = useState(false);
  const [chatMsg, setChatMsg] = useState('');
  const chatEndRef = useRef<HTMLDivElement>(null);
  const rawDealRef = useRef<Record<string, unknown>>({});

  // ── 타임라인 배너 tracking ──
  const timelineStage = mapDealToTimelineStage(rawDealRef.current);
  const [shownStages, setShownStages] = useState<string[]>(() => {
    const saved = localStorage.getItem(`deal_${dealId}_shown_stages`);
    return saved ? JSON.parse(saved) : [];
  });
  const shouldShowBanner = !shownStages.includes(timelineStage);

  useEffect(() => {
    if (shouldShowBanner && timelineStage) {
      const updated = [...shownStages, timelineStage];
      setShownStages(updated);
      localStorage.setItem(`deal_${dealId}_shown_stages`, JSON.stringify(updated));
    }
  }, [timelineStage]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 딜 + 오퍼 + 채팅 데이터 페칭 ──
  useEffect(() => {
    if (!dealId) return;
    setLoading(true);

    const fetchAll = async () => {
      // 딜 데이터
      const raw = await fetchDeal(dealId);
      if (raw && typeof raw === 'object') {
        const d = raw as Record<string, unknown>;
        rawDealRef.current = d;
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
        setProductDetail(buildProductDetail(d));
      }

      // 오퍼 데이터
      const offersRaw = await fetchOffersByDeal(dealId);
      if (Array.isArray(offersRaw)) {
        const mapped = offersRaw.map((o: Record<string, unknown>, i: number) => mapOffer(o, i));
        mapped.sort((a, b) => a.price - b.price);
        setOffers(mapped);
      } else if (offersRaw && typeof offersRaw === 'object' && Array.isArray((offersRaw as Record<string, unknown>).items)) {
        const items = (offersRaw as Record<string, unknown>).items as Record<string, unknown>[];
        const mapped = items.map((o, i) => mapOffer(o, i));
        mapped.sort((a, b) => a.price - b.price);
        setOffers(mapped);
      }

      // 채팅 데이터
      if (buyerId) {
        const chatRaw = await fetchChatMessages(dealId, buyerId);
        if (Array.isArray(chatRaw)) {
          setChatMessages(chatRaw.map((m: Record<string, unknown>) => mapChat(m)));
        }
      }
    };

    fetchAll().finally(() => setLoading(false));
  }, [dealId, buyerId]);

  // ── 행동 수집: VIEW_DEAL / SELLER_VIEW_DEAL_DETAIL ──
  useEffect(() => {
    if (!dealId || loading) return;
    const isSeller = !!user?.seller;
    trackBehavior(isSeller ? 'SELLER_VIEW_DEAL_DETAIL' : 'VIEW_DEAL', {
      target_type: 'deal',
      target_id: dealId,
      target_name: deal.product_name,
      meta: { category: deal.category, price: deal.desired_price },
    });
  }, [dealId, loading]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (chatSheetOpen) {
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 300);
    }
  }, [chatSheetOpen]);

  const lowestOffer = offers[0] ?? null;
  const pingpongMsg = getPingpongMessage(deal, offers);

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

        {/* 딜 단계 프로그레스 (4단계 타임라인) */}
        <div style={{ margin: '0 16px 8px' }}>
          <DealTimeline currentStage={mapDealToTimelineStage(rawDealRef.current)} showBanner={shouldShowBanner} />
        </div>
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

        {/* 요청 옵션 표시 */}
        {productDetail && productDetail.options.length > 0 && (
          <div style={{ margin: '0 16px 16px' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8 }}>📦 요청 옵션</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {productDetail.options.map((opt, i) => (
                <span key={i} style={{
                  padding: '4px 10px', borderRadius: 20, fontSize: 12,
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)',
                }}>
                  {opt.title}: {opt.selected_value || opt.values[0] || ''}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* 오퍼 목록 */}
        <OfferList offers={offers} />

        {/* 판매자 전용: 오퍼 제출 버튼 */}
        {user?.role === 'seller' && (
          <div style={{ margin: '0 16px 16px' }}>
            <button
              onClick={() => navigate(`/deal/${dealId}/offer/create`)}
              style={{
                width: '100%', padding: '16px', borderRadius: 14,
                fontSize: 16, fontWeight: 800, cursor: 'pointer',
                background: 'linear-gradient(135deg, #ff2d78, #ff6a99)',
                color: '#fff', border: 'none',
                boxShadow: '0 4px 16px rgba(255,45,120,0.25)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              }}
            >
              📋 이 딜에 오퍼 제출하기
            </button>
          </div>
        )}

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
            <span>💬 딜방 채팅 ({chatMessages.length})</span>
            <span style={{ fontSize: 12, color: 'var(--accent-blue)' }}>펼치기 ↑</span>
          </button>
          <div style={{ background: 'var(--bg-secondary)', padding: '10px 16px' }}>
            {chatMessages.slice(-3).map((c, i, arr) => (
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
            {chatMessages.map(c => (
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
              onKeyDown={e => {
                if (e.key === 'Enter' && chatMsg.trim() && buyerId) {
                  const msg = chatMsg.trim();
                  setChatMsg('');
                  sendChatMessage(dealId, msg, buyerId).then(() => {
                    fetchChatMessages(dealId, buyerId).then(raw => {
                      if (Array.isArray(raw)) setChatMessages(raw.map((m: Record<string, unknown>) => mapChat(m)));
                    });
                  });
                }
              }}
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
              onClick={() => {
                if (chatMsg.trim() && buyerId) {
                  const msg = chatMsg.trim();
                  setChatMsg('');
                  sendChatMessage(dealId, msg, buyerId).then(() => {
                    fetchChatMessages(dealId, buyerId).then(raw => {
                      if (Array.isArray(raw)) setChatMessages(raw.map((m: Record<string, unknown>) => mapChat(m)));
                    });
                  });
                }
              }}
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
        canonicalName={(rawDealRef.current.product_detail as string) || deal.product_name}
        options={productDetail?.options ?? []}
        conditions={productDetail?.conditions ?? { shipping_fee_krw: 0, warranty_months: 0, delivery_days: 0, return_policy: '', condition_grade: '신품' }}
        naverLowestPrice={productDetail?.naver_lowest_price ?? null}
        naverProductName={productDetail?.naver_product_name ?? ''}
        aiAnalyzedAt={productDetail?.ai_analyzed_at ?? null}
      />
    </div>
  );
}
