import { useNavigate, useParams } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { fetchDeal } from '../api/dealApi';
import { fetchOffersByDeal } from '../api/offerApi';
import { useApiData } from '../api/hooks';
import type { DealResponse, OfferResponse } from '../api/types';
import LoadingSkeleton from '../components/common/LoadingSkeleton';
import EmptyState from '../components/common/EmptyState';

// ── 색상 ─────────────────────────────────────────────

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)', blue: 'var(--accent-blue)',
};

const TIER_META = {
  PREMIUM:  { label: 'PREMIUM',  color: '#ffd600', bg: '#ffd60022', desc: '목표가 이상' },
  MATCHING: { label: 'MATCHING', color: '#00e676', bg: '#00e67622', desc: '목표가 근접' },
  BELOW:    { label: 'BELOW',    color: '#00b0ff', bg: '#00b0ff22', desc: '목표가 이하' },
};

function fmtP(n: number) { return n.toLocaleString('ko-KR') + '원'; }
function fmtK(n: number) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000)    return Math.round(n / 1000) + 'K';
  return String(n);
}
function fmtDate(s: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

function getTier(price: number, avg: number, spread: number): keyof typeof TIER_META {
  if (price < avg - spread * 0.1) return 'BELOW';
  if (price > avg + spread * 0.1) return 'PREMIUM';
  return 'MATCHING';
}

// ── 커스텀 툴팁 ──────────────────────────────────────

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: { value: number }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: C.bgEl, border: `1px solid ${C.border}`, borderRadius: 8, padding: '8px 12px', fontSize: 12 }}>
      <div style={{ color: C.textDim, marginBottom: 2 }}>가격대: {label}</div>
      <div style={{ color: C.green, fontWeight: 700 }}>{payload[0].value}건</div>
    </div>
  );
}

// ── 메인 ─────────────────────────────────────────────

export default function CompletedDealDetailPage() {
  const { id }   = useParams<{ id: string }>();
  const navigate = useNavigate();
  const dealId   = Number(id);

  const { data: deal, loading: loadingDeal } = useApiData<DealResponse>(async () => {
    const res = await fetchDeal(dealId);
    return res as DealResponse | null;
  }, [dealId]);

  const { data: offers } = useApiData<OfferResponse[]>(async () => {
    const res = await fetchOffersByDeal(dealId);
    return (res ?? []) as OfferResponse[];
  }, [dealId]);

  if (loadingDeal) {
    return (
      <div style={{ minHeight: '100dvh', background: C.bg }}>
        <LoadingSkeleton variant="detail" />
      </div>
    );
  }

  if (!deal) {
    return (
      <div style={{ minHeight: '100dvh', background: C.bg }}>
        <EmptyState
          icon="🔍"
          message="딜을 찾을 수 없어요"
          actionLabel="목록으로"
          onAction={() => navigate('/completed-deals')}
        />
      </div>
    );
  }

  const allOffers = offers ?? [];
  const prices = allOffers.map(o => o.price).filter(p => p > 0);
  const minPrice = prices.length > 0 ? Math.min(...prices) : deal.current_avg_price;
  const maxPrice = prices.length > 0 ? Math.max(...prices) : deal.current_avg_price;
  const avgPrice = deal.current_avg_price || (prices.length > 0 ? prices.reduce((a, b) => a + b, 0) / prices.length : 0);
  const targetPrice = deal.target_price ?? deal.max_budget ?? 0;
  const spread = maxPrice - minPrice || 1;

  const diff = targetPrice > 0 ? ((avgPrice - targetPrice) / targetPrice * 100) : 0;
  const isBelow = diff < 0;

  // 가격 분포 생성
  const distrib = (() => {
    if (prices.length === 0) return [];
    const buckets = 5;
    const step = spread / buckets;
    return Array.from({ length: buckets }, (_, i) => {
      const lo = Math.round(minPrice + step * i);
      const hi = Math.round(minPrice + step * (i + 1));
      const count = prices.filter(p => p >= lo && (i === buckets - 1 ? p <= hi : p < hi)).length;
      return { range: `${fmtK(lo)}~${fmtK(hi)}`, count, lo, hi, avg: avgPrice };
    });
  })();

  // 오퍼 매핑
  const offerEntries = allOffers.map(o => ({
    seller: `셀러#${o.seller_id}`,
    price: o.price,
    qty: o.total_available_qty - o.reserved_qty,
    tier: getTier(o.price, avgPrice, spread),
    condition: o.shipping_mode ?? (o.delivery_days ? `${o.delivery_days}일 배송` : '기본 배송'),
  })).sort((a, b) => a.price - b.price);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      {/* TopBar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 14, fontWeight: 700, color: C.text, flex: 1, textAlign: 'center', marginRight: 24 }} className="truncate">
          {deal.product_name}
        </span>
      </div>

      <div style={{ padding: '14px 16px 0' }}>

        {/* 딜 요약 카드 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderTop: `3px solid ${C.green}`,
          borderRadius: 16, padding: '16px', marginBottom: 12,
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 4 }}>
            {deal.product_name}
          </div>
          <div style={{ fontSize: 11, color: C.textSec, marginBottom: 14 }}>
            {deal.brand ?? ''}{deal.extra_conditions ? ` · ${deal.extra_conditions}` : ''} · {fmtDate(deal.created_at)} ~ {fmtDate(deal.deadline_at ?? '')}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 10 }}>
            {[
              { label: '목표가',     value: fmtP(targetPrice), color: C.textSec },
              { label: '평균체결가', value: fmtP(Math.round(avgPrice)), color: C.text },
              { label: '목표대비',   value: targetPrice > 0 ? `${isBelow ? '' : '+'}${diff.toFixed(1)}%` : '-', color: isBelow ? C.green : C.orange },
            ].map(item => (
              <div key={item.label} style={{ textAlign: 'center', padding: '10px 6px', background: C.bgEl, borderRadius: 10 }}>
                <div style={{ fontSize: 10, color: C.textDim, marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: 12, fontWeight: 700, color: item.color }}>{item.value}</div>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            {[
              { label: '최저가',   value: fmtP(minPrice) },
              { label: '최고가',   value: fmtP(maxPrice) },
              { label: '거래량',   value: `${deal.current_qty ?? 0}개` },
            ].map(item => (
              <div key={item.label} style={{ textAlign: 'center', padding: '10px 6px', background: C.bgEl, borderRadius: 10 }}>
                <div style={{ fontSize: 10, color: C.textDim, marginBottom: 4 }}>{item.label}</div>
                <div style={{ fontSize: 11, fontWeight: 600, color: C.text }}>{item.value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* 가격 분포 차트 */}
        {distrib.length > 0 && (
          <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: '16px', marginBottom: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 12 }}>가격 분포</div>
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={distrib} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                <XAxis dataKey="range" tick={{ fontSize: 9, fill: '#607d8b' }} />
                <YAxis tick={{ fontSize: 9, fill: '#607d8b' }} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {distrib.map((entry, i) => (
                    <Cell
                      key={i}
                      fill={entry.lo <= avgPrice && entry.hi >= avgPrice
                        ? 'var(--accent-green)'
                        : 'rgba(0,230,118,0.3)'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: 'var(--accent-green)' }} />
              <span style={{ fontSize: 10, color: C.textDim }}>평균 체결 구간</span>
            </div>
          </div>
        )}

        {/* 오퍼 목록 */}
        {offerEntries.length > 0 && (
          <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: '16px', marginBottom: 12 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 12 }}>
              오퍼 목록 ({offerEntries.length}건)
            </div>

            {offerEntries.map((offer, i) => {
              const tm = TIER_META[offer.tier];
              return (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '10px 0',
                  borderBottom: i < offerEntries.length - 1 ? `1px solid ${C.border}` : 'none',
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
                      <span style={{
                        fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
                        background: tm.bg, color: tm.color, border: `1px solid ${tm.color}44`,
                        letterSpacing: 0.5,
                      }}>{tm.label}</span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{offer.seller}</span>
                    </div>
                    <div style={{ fontSize: 11, color: C.textSec }}>{offer.condition}</div>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{fmtP(offer.price)}</div>
                    <div style={{ fontSize: 10, color: C.textDim }}>{offer.qty}개 가능</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* 핑퐁이 분석 */}
        <div style={{
          background: C.bgCard, border: `1px solid rgba(255,183,77,0.25)`,
          borderLeft: '3px solid var(--accent-orange)',
          borderRadius: 16, padding: '14px 16px', marginBottom: 12,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <span style={{ fontSize: 20 }}>🤖</span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-orange)' }}>핑퐁이 분석</div>
              <div style={{ fontSize: 10, color: C.textDim }}>AI 가격 인사이트</div>
            </div>
          </div>
          <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.6 }}>
            {isBelow
              ? `이 딜은 목표가보다 ${Math.abs(diff).toFixed(1)}% 저렴하게 체결됐어요! 셀러 경쟁이 활발해서 구매자에게 유리한 결과가 나왔어요.`
              : targetPrice > 0
              ? `이 딜은 목표가보다 ${diff.toFixed(1)}% 높게 체결됐어요. 다음 딜에서는 더 낮은 가격을 목표로 설정해보세요.`
              : '이 딜의 가격 데이터를 분석 중입니다.'}
          </div>
        </div>

        {/* 비슷한 딜 더보기 */}
        <button
          onClick={() => navigate('/completed-deals')}
          style={{
            width: '100%', padding: '14px 0', borderRadius: 14,
            background: `${C.green}15`, border: `1px solid ${C.green}44`,
            color: C.green, fontSize: 14, fontWeight: 700, cursor: 'pointer',
            marginBottom: 8,
          }}
        >
          비슷한 딜 더보기 →
        </button>
      </div>
    </div>
  );
}
