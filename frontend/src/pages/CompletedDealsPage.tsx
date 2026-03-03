import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchDeals } from '../api/dealApi';
import { useApiData } from '../api/hooks';
import type { DealResponse } from '../api/types';
import LoadingSkeleton from '../components/common/LoadingSkeleton';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';

// ── 타입 ────────────────────────────────────────────

interface CompletedDeal {
  id: number;
  product_name: string;
  brand: string;
  category: string;
  avg_price: number;
  total_sold_qty: number;
  deal_start: string;
  deal_end: string;
  original_target: number;
}

const POPULAR_BRANDS = ['Apple', 'Samsung', 'Nike', 'Dyson', 'Sony', 'LG', '종가집'];
const CATEGORIES = [
  { emoji: '📱', label: '전자기기' },
  { emoji: '👗', label: '패션' },
  { emoji: '🏠', label: '생활' },
  { emoji: '🍔', label: '식품' },
];

type SortKey = 'qty' | 'recent' | 'price';

// ── 색상 ─────────────────────────────────────────────

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', cyan: '#00e5ff', orange: 'var(--accent-orange)',
};

function fmtP(n: number) { return '₩' + n.toLocaleString('ko-KR'); }
function fmtDate(s: string) { return (s ?? '').slice(5, 10).replace('-', '.'); }

// ── 메인 ─────────────────────────────────────────────

export default function CompletedDealsPage() {
  const navigate = useNavigate();

  const { data: allDeals, loading, error, refetch } = useApiData<CompletedDeal[]>(async () => {
    const raw = await fetchDeals(0, 500);
    if (!raw) return [];
    return (raw as DealResponse[])
      .filter(d => d.status === 'closed' || d.status === 'archived')
      .map(d => ({
        id:              d.id,
        product_name:    d.product_name,
        brand:           d.brand ?? '',
        category:        d.extra_conditions ?? '',
        avg_price:       d.current_avg_price ?? d.target_price ?? 0,
        total_sold_qty:  d.current_qty ?? 0,
        deal_start:      d.created_at?.split('T')[0] ?? '',
        deal_end:        d.deadline_at?.split('T')[0] ?? '',
        original_target: d.target_price ?? d.max_budget ?? 0,
      }));
  }, []);

  const [searchQuery,     setSearchQuery]     = useState('');
  const [selectedBrands,  setSelectedBrands]  = useState<string[]>([]);
  const [selectedCat,     setSelectedCat]     = useState('');
  const [sortBy,          setSortBy]          = useState<SortKey>('qty');

  const toggleBrand = (b: string) =>
    setSelectedBrands(prev => prev.includes(b) ? prev.filter(x => x !== b) : [...prev, b]);

  const getFiltered = () => {
    let deals = [...(allDeals ?? [])];
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      deals = deals.filter(d => d.product_name.toLowerCase().includes(q) || d.brand.toLowerCase().includes(q));
    }
    if (selectedBrands.length > 0) deals = deals.filter(d => selectedBrands.includes(d.brand));
    if (selectedCat) deals = deals.filter(d => d.category === selectedCat);
    if (sortBy === 'qty')    deals.sort((a, b) => b.total_sold_qty - a.total_sold_qty);
    if (sortBy === 'recent') deals.sort((a, b) => b.deal_end.localeCompare(a.deal_end));
    if (sortBy === 'price')  deals.sort((a, b) => a.avg_price - b.avg_price);
    return deals;
  };

  const filtered = getFiltered();

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      {/* TopBar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>지난딜 가격조회</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>

        {/* 검색 입력 */}
        <div style={{ position: 'relative', marginBottom: 14 }}>
          <input
            type="text" value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="브랜드, 상품명 검색..."
            style={{
              width: '100%', padding: '10px 12px 10px 36px', fontSize: 13,
              borderRadius: 12, background: C.bgCard, border: `1px solid ${C.border}`,
              color: C.text, boxSizing: 'border-box' as const,
            }}
          />
        </div>

        {/* 인기 브랜드 */}
        <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 8 }}>인기 브랜드</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
          {POPULAR_BRANDS.map(b => {
            const on = selectedBrands.includes(b);
            return (
              <button key={b} onClick={() => toggleBrand(b)} style={{
                padding: '5px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
                background: on ? `${C.green}22` : C.bgEl,
                border: `1px solid ${on ? C.green : C.border}`,
                color: on ? C.green : C.textSec, fontWeight: on ? 700 : 400,
              }}>{b}{on ? ' ✓' : ''}</button>
            );
          })}
        </div>

        {/* 카테고리 */}
        <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 8 }}>카테고리</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
          {CATEGORIES.map(cat => {
            const on = selectedCat === cat.label;
            return (
              <button key={cat.label} onClick={() => setSelectedCat(on ? '' : cat.label)} style={{
                padding: '6px 14px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
                background: on ? `${C.green}22` : C.bgEl,
                border: `1px solid ${on ? C.green : C.border}`,
                color: on ? C.green : C.textSec, fontWeight: on ? 700 : 400,
              }}>{cat.emoji} {cat.label}</button>
            );
          })}
        </div>

        {/* 정렬 + 결과 수 */}
        {loading && <LoadingSkeleton variant="cards" count={3} />}
        {!loading && error && <ErrorMessage message={error} onRetry={refetch} />}

        {!loading && !error && (<>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <span style={{ fontSize: 12, color: C.textDim }}>
            거래 완료 딜 {filtered.length}건
          </span>
          <div style={{ display: 'flex', gap: 6 }}>
            {(['qty', 'recent', 'price'] as SortKey[]).map(k => {
              const labels: Record<SortKey, string> = { qty: '거래량순', recent: '최신순', price: '가격순' };
              const on = sortBy === k;
              return (
                <button key={k} onClick={() => setSortBy(k)} style={{
                  padding: '4px 10px', borderRadius: 12, fontSize: 11, cursor: 'pointer',
                  background: on ? `${C.cyan}22` : C.bgEl,
                  border: `1px solid ${on ? C.cyan : C.border}`,
                  color: on ? C.cyan : C.textSec, fontWeight: on ? 700 : 400,
                }}>{labels[k]}{on ? ' ✓' : ''}</button>
              );
            })}
          </div>
        </div>

        {/* 딜 카드 목록 */}
        {!loading && filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim, fontSize: 13 }}>검색 결과가 없어요</div>
        ) : filtered.map(deal => {
          const diff = deal.original_target > 0 ? ((deal.avg_price - deal.original_target) / deal.original_target * 100).toFixed(1) : '0.0';
          const isBelow = deal.avg_price < deal.original_target;
          return (
            <div
              key={deal.id}
              onClick={() => navigate(`/completed-deals/${deal.id}`)}
              style={{
                background: C.bgCard, border: `1px solid ${C.border}`,
                borderLeft: `3px solid ${C.green}`,
                borderRadius: 14, padding: '14px 14px 12px', marginBottom: 8,
                cursor: 'pointer', transition: 'transform 0.15s',
              }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translateX(2px)'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'none'; }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 2 }}>
                    {deal.product_name}
                  </div>
                  <div style={{ fontSize: 11, color: C.textSec, marginBottom: 8 }}>
                    {deal.brand}{deal.category ? ` · ${deal.category}` : ''}
                  </div>

                  <div style={{ fontSize: 12, color: C.text, marginBottom: 4 }}>
                    평균 체결가 {fmtP(deal.avg_price)}
                  </div>

                  <div style={{ display: 'flex', gap: 12, fontSize: 11, color: C.textSec, marginBottom: 4 }}>
                    <span>{deal.total_sold_qty}개</span>
                    <span>{fmtDate(deal.deal_start)} ~ {fmtDate(deal.deal_end)}</span>
                  </div>

                  {deal.original_target > 0 && (
                    <div style={{ fontSize: 11 }}>
                      <span style={{ color: isBelow ? C.green : C.orange }}>
                        목표가 대비 {isBelow ? '' : '+'}{diff}%
                      </span>
                    </div>
                  )}
                </div>
                <button
                  onClick={e => { e.stopPropagation(); navigate(`/completed-deals/${deal.id}`); }}
                  style={{
                    padding: '6px 10px', borderRadius: 8, fontSize: 10, fontWeight: 700, flexShrink: 0,
                    background: `${C.green}22`, border: `1px solid ${C.green}66`, color: C.green, cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >상세 ›</button>
              </div>
            </div>
          );
        })}
        </>)}
      </div>
    </div>
  );
}
