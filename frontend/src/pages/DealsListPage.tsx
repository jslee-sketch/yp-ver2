import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { DealCard } from '../components/deal/DealCard';
import { fetchDeals, mapDealResponseToDisplay } from '../api/dealApi';
import { useApiData } from '../api/hooks';
import type { DealResponse } from '../api/types';
import type { Deal } from '../types';
import LoadingSkeleton from '../components/common/LoadingSkeleton';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';

const CATEGORIES = ['전체', '전자기기', '패션', '식품', '생활용품', '뷰티', '스포츠', '가전'];
const STATUS_FILTERS = [
  { key: 'all', label: '전체' },
  { key: 'open', label: '모집중' },
  { key: 'offer', label: '오퍼경쟁' },
  { key: 'closed', label: '마감' },
  { key: 'completed', label: '완료' },
];
const SORT_OPTIONS = [
  { key: 'latest', label: '최신순' },
  { key: 'popular', label: '인기순' },
  { key: 'saving', label: '절약률순' },
  { key: 'closing', label: '마감순' },
];

export default function DealsListPage() {
  const navigate = useNavigate();
  const [activeCategory, setActiveCategory] = useState('전체');
  const [activeStatus, setActiveStatus] = useState('all');
  const [activeSort, setActiveSort] = useState('latest');

  const { data: deals, loading, error, refetch } = useApiData<Deal[]>(async () => {
    const raw = await fetchDeals(1, 200);
    if (!raw) return [];
    return (raw as DealResponse[]).map(mapDealResponseToDisplay);
  }, []);

  const allDeals = deals ?? [];

  // Status filter
  const statusFiltered = activeStatus === 'all' ? allDeals : allDeals.filter(d => {
    const s = (d.status ?? '').toLowerCase();
    if (activeStatus === 'open') return s === 'open' && (d.participants_count ?? 0) === 0;
    if (activeStatus === 'offer') return s === 'open' && (d.participants_count ?? 0) > 0;
    if (activeStatus === 'closed') return s === 'closed';
    if (activeStatus === 'completed') return s === 'completed' || s === 'archived';
    return true;
  });

  const filteredDeals = activeCategory === '전체'
    ? statusFiltered
    : statusFiltered.filter(d => d.category === activeCategory);

  const sortedDeals = [...filteredDeals].sort((a, b) => {
    if (activeSort === 'popular') return (b.participants_count ?? 0) - (a.participants_count ?? 0);
    if (activeSort === 'saving') return (b.anchor_price ? (b.anchor_price - (b.desired_price ?? 0)) / b.anchor_price : 0) - (a.anchor_price ? (a.anchor_price - (a.desired_price ?? 0)) / a.anchor_price : 0);
    if (activeSort === 'closing') return (a.deadline_at ?? '').localeCompare(b.deadline_at ?? '');
    return (b.created_at ?? '').localeCompare(a.created_at ?? '');
  });

  return (
    <div style={{ minHeight: '100dvh', paddingBottom: 32 }}>
      {/* 상단 헤더 */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        background: 'var(--bg-primary)',
        borderBottom: '1px solid var(--border-subtle)',
        padding: '0 16px',
        height: 48,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <button
          onClick={() => navigate(-1)}
          style={{ padding: '6px 8px', color: 'var(--text-primary)', fontSize: 20, cursor: 'pointer' }}
        >
          ←
        </button>
        <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
          딜 목록
        </span>
        <span style={{
          fontSize: 11, fontWeight: 700, padding: '3px 8px',
          background: 'rgba(0,230,118,0.12)', color: 'var(--accent-green)',
          borderRadius: 20, border: '1px solid rgba(0,230,118,0.2)',
        }}>
          {sortedDeals.length}개
        </span>
      </div>

      <div className="page-enter">
        {/* 상태 필터 */}
        <div style={{ display: 'flex', gap: 6, overflowX: 'auto', padding: '12px 16px 0' }}>
          {STATUS_FILTERS.map(sf => (
            <button
              key={sf.key}
              onClick={() => setActiveStatus(sf.key)}
              style={{
                flexShrink: 0, padding: '6px 14px',
                borderRadius: 'var(--radius-full)',
                border: `1px solid ${activeStatus === sf.key ? 'var(--accent-green)' : 'var(--border-subtle)'}`,
                background: activeStatus === sf.key ? 'var(--accent-green-bg)' : 'var(--bg-tertiary)',
                color: activeStatus === sf.key ? 'var(--accent-green)' : 'var(--text-muted)',
                fontSize: 13, fontWeight: activeStatus === sf.key ? 700 : 400,
                cursor: 'pointer',
              }}
            >
              {sf.label}
            </button>
          ))}
        </div>

        {/* 카테고리 필터 */}
        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', padding: '8px 16px 0' }}>
          {CATEGORIES.map(cat => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              style={{
                flexShrink: 0, padding: '6px 14px',
                borderRadius: 'var(--radius-full)',
                border: `1px solid ${activeCategory === cat ? 'var(--accent-green)' : 'var(--border-subtle)'}`,
                background: activeCategory === cat ? 'var(--accent-green-bg)' : 'var(--bg-tertiary)',
                color: activeCategory === cat ? 'var(--accent-green)' : 'var(--text-muted)',
                fontSize: 13, fontWeight: activeCategory === cat ? 700 : 400,
                cursor: 'pointer',
              }}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* 정렬 탭 */}
        <div style={{ padding: '10px 16px 12px', display: 'flex', gap: 6 }}>
          {SORT_OPTIONS.map(opt => (
            <button
              key={opt.key}
              onClick={() => setActiveSort(opt.key)}
              style={{
                padding: '4px 12px',
                borderRadius: 'var(--radius-sm)',
                background: activeSort === opt.key ? 'var(--bg-elevated)' : 'transparent',
                color: activeSort === opt.key ? 'var(--text-primary)' : 'var(--text-muted)',
                fontSize: 12, fontWeight: activeSort === opt.key ? 700 : 400,
                border: activeSort === opt.key ? '1px solid var(--border-subtle)' : 'none',
                cursor: 'pointer',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* 딜 카드 피드 */}
        <div style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          {loading && <LoadingSkeleton variant="cards" count={4} />}
          {!loading && error && <ErrorMessage message={error} onRetry={refetch} />}
          {!loading && !error && sortedDeals.map((deal, i) => (
            <div key={deal.id} className="slide-in" style={{ animationDelay: `${i * 0.04}s` }}>
              <DealCard deal={deal} />
            </div>
          ))}
          {!loading && !error && sortedDeals.length === 0 && (
            <EmptyState icon="🛒" message="해당 카테고리에 진행 중인 딜이 없어요." />
          )}
        </div>
      </div>
    </div>
  );
}
