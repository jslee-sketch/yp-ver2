import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchDeals } from '../api/dealApi';
import type { DealResponse } from '../api/types';

// ── 타입 ──────────────────────────────────────────────

interface SearchDeal {
  id: number;
  product_name: string;
  brand?: string;
  target_price: number;
  current_qty: number;
  desired_qty: number;
  offer_count: number;
  status: 'open' | 'closed';
  deadline_at: string;
  category: string;
}

function mapToSearchDeal(d: DealResponse): SearchDeal {
  return {
    id:           d.id,
    product_name: d.product_name ?? '',
    brand:        d.brand ?? '',
    target_price: d.target_price ?? d.max_budget ?? 0,
    current_qty:  d.current_qty ?? 0,
    desired_qty:  d.desired_qty ?? 1,
    offer_count:  0,
    status:       (d.status ?? 'open') as 'open' | 'closed',
    deadline_at:  d.deadline_at ?? '',
    category:     d.extra_conditions ?? '',
  };
}

const POPULAR_KEYWORDS = [
  '에어팟 프로', '갤럭시 S25', '다이슨', '아이패드',
  '나이키', 'PS5', '김치', '맥북 에어',
];

const CATEGORIES = [
  { emoji: '📱', label: '전자기기' },
  { emoji: '👗', label: '패션' },
  { emoji: '🏠', label: '생활' },
  { emoji: '🍔', label: '식품' },
  { emoji: '💄', label: '뷰티' },
  { emoji: '⚽', label: '스포츠' },
];

// ── 유틸 ─────────────────────────────────────────────

function fmtPrice(n: number) { return '₩' + n.toLocaleString('ko-KR'); }

function daysLeft(deadline: string): number {
  const diff = new Date(deadline).getTime() - Date.now();
  return Math.max(0, Math.ceil(diff / 86400000));
}

// ── 색상 ─────────────────────────────────────────────

const C = {
  bg:      'var(--bg-primary)',
  bgCard:  'var(--bg-secondary)',
  bgEl:    'var(--bg-elevated)',
  text:    'var(--text-primary)',
  textSec: 'var(--text-secondary)',
  textDim: 'var(--text-muted)',
  border:  'var(--border-subtle)',
  green:   'var(--accent-green)',
  orange:  'var(--accent-orange)',
  cyan:    '#00e5ff',
};

// ── 프로그레스 바 ─────────────────────────────────────

function ProgressBar({ value, max }: { value: number; max: number }) {
  const pct = max === 0 ? 0 : Math.min(100, Math.round((value / max) * 100));
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 4, borderRadius: 2, background: C.bgEl, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%', borderRadius: 2,
          background: `linear-gradient(90deg, ${C.green}, ${C.cyan})`,
        }} />
      </div>
      <span style={{ fontSize: 10, color: C.textSec, flexShrink: 0 }}>{pct}%</span>
    </div>
  );
}

// ── 딜 카드 ──────────────────────────────────────────

function DealCard({ deal }: { deal: SearchDeal }) {
  const navigate = useNavigate();
  const days = daysLeft(deal.deadline_at);

  return (
    <div
      onClick={() => navigate(`/deal/${deal.id}`)}
      style={{
        background: C.bgCard,
        border: `1px solid ${C.border}`,
        borderLeft: `3px solid ${C.cyan}`,
        borderRadius: 14,
        padding: '14px 14px 12px',
        marginBottom: 8,
        cursor: 'pointer',
        transition: 'transform 0.15s',
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
            {deal.brand && `${deal.brand} · `}목표 {fmtPrice(deal.target_price)}
          </div>
          <ProgressBar value={deal.current_qty} max={deal.desired_qty} />
          <div style={{ display: 'flex', gap: 10, marginTop: 6, fontSize: 11, color: C.textDim }}>
            <span>{deal.current_qty}/{deal.desired_qty}개</span>
            <span>오퍼 {deal.offer_count}건</span>
            {deal.deadline_at && <span style={{ color: days <= 2 ? C.orange : C.textDim }}>⏰ {days}일 남음</span>}
          </div>
        </div>
        <button
          onClick={e => { e.stopPropagation(); navigate(`/deal/${deal.id}`); }}
          style={{
            padding: '6px 12px', borderRadius: 8, fontSize: 11, fontWeight: 700, flexShrink: 0,
            background: `${C.cyan}22`, border: `1px solid ${C.cyan}66`, color: C.cyan, cursor: 'pointer',
          }}
        >보기 ›</button>
      </div>
    </div>
  );
}

// ── 섹션 헤더 ─────────────────────────────────────────

function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontSize: 12, fontWeight: 700, color: C.textSec,
      letterSpacing: '0.5px', marginBottom: 10, marginTop: 20,
      display: 'flex', alignItems: 'center', gap: 6,
    }}>
      {children}
      <div style={{ flex: 1, height: 1, background: C.border }} />
    </div>
  );
}

// ── 메인 ─────────────────────────────────────────────

export default function SearchPage() {
  const navigate  = useNavigate();
  const [params]  = useSearchParams();
  const initialQ  = params.get('q') ?? '';

  const [query,        setQuery]        = useState(initialQ);
  const [isSearching,  setIsSearching]  = useState(!!initialQ.trim());
  const [results,      setResults]      = useState<SearchDeal[]>([]);
  const [allDeals,     setAllDeals]     = useState<SearchDeal[]>([]);
  const [selectedCat,  setSelectedCat]  = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef    = useRef<HTMLInputElement>(null);

  // 초기 로드: API에서 전체 딜 목록 가져오기 (인기 딜 표시용)
  useEffect(() => {
    void (async () => {
      const apiData = await fetchDeals(1, 200);
      if (apiData) {
        setAllDeals((apiData as DealResponse[]).map(mapToSearchDeal));
      }
    })();
  }, []);

  const doSearch = async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) { setIsSearching(false); setResults([]); setSelectedCat(null); return; }
    setIsSearching(true);

    // 서버 사이드 키워드 검색
    const apiData = await fetchDeals(1, 200, { keyword: trimmed });
    if (apiData) {
      setResults((apiData as DealResponse[]).map(mapToSearchDeal));
    } else {
      // API 실패 시 클라이언트 사이드 폴백
      const filterFn = (d: SearchDeal) =>
        d.product_name.toLowerCase().includes(trimmed.toLowerCase()) ||
        (d.brand && d.brand.toLowerCase().includes(trimmed.toLowerCase())) ||
        d.category.includes(trimmed);
      setResults(allDeals.filter(filterFn));
    }
  };

  const handleInput = (val: string) => {
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => { void doSearch(val); }, 300);
  };

  const handleEnter = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    void doSearch(query);
  };

  const handleKeyword = (kw: string) => { setQuery(kw); setSelectedCat(null); void doSearch(kw); };

  const handleCategory = (cat: string) => {
    const next = selectedCat === cat ? null : cat;
    setSelectedCat(next);
    if (next) { setQuery(next); void doSearch(next); }
    else { setQuery(''); setIsSearching(false); setResults([]); }
  };

  const clearSearch = () => {
    setQuery(''); setIsSearching(false); setResults([]); setSelectedCat(null);
    inputRef.current?.focus();
  };

  // 초기 URL 파라미터 동기화
  useEffect(() => { if (initialQ) void doSearch(initialQ); }, [allDeals]); // eslint-disable-line

  const hotDeals = [...allDeals].sort((a, b) => b.current_qty - a.current_qty).slice(0, 4);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 80 }}>

      {/* TopBar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56,
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '0 16px',
        background: C.bg,
        borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>

        <div style={{ flex: 1, position: 'relative' }}>
          <span style={{
            position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)',
            fontSize: 14, pointerEvents: 'none',
          }}>🔍</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => handleInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleEnter(); }}
            placeholder="상품명, 브랜드, 카테고리..."
            autoFocus
            style={{
              width: '100%', padding: '9px 36px 9px 36px', fontSize: 13,
              borderRadius: 12,
              background: C.bgEl,
              border: `1px solid ${C.border}`,
              color: C.text,
              boxSizing: 'border-box' as const,
            }}
          />
          {query && (
            <button
              onClick={clearSearch}
              style={{
                position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                fontSize: 14, color: C.textDim, cursor: 'pointer', lineHeight: 1,
              }}
            >✕</button>
          )}
        </div>
      </div>

      <div style={{ padding: '0 16px' }}>

        {/* 기본 화면 */}
        {!isSearching && (
          <>
            <SectionHeader>인기 검색어</SectionHeader>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0 }}>
              {POPULAR_KEYWORDS.map((kw, i) => (
                <button
                  key={kw}
                  onClick={() => handleKeyword(kw)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '9px 4px', background: 'none', border: 'none',
                    cursor: 'pointer', textAlign: 'left',
                    borderBottom: `1px solid ${C.border}`,
                  }}
                >
                  <span style={{
                    fontSize: 12, fontWeight: 800, width: 16, flexShrink: 0,
                    color: i < 3 ? C.green : C.textDim,
                    fontFamily: "'Space Mono', monospace",
                  }}>{i + 1}</span>
                  <span style={{ fontSize: 13, color: C.text }}>{kw}</span>
                </button>
              ))}
            </div>

            <SectionHeader>카테고리</SectionHeader>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 4 }}>
              {CATEGORIES.map(cat => {
                const active = selectedCat === cat.label;
                return (
                  <button
                    key={cat.label}
                    onClick={() => handleCategory(cat.label)}
                    style={{
                      padding: '7px 14px', borderRadius: 20, fontSize: 12,
                      background: active ? `${C.green}22` : C.bgEl,
                      border: `1px solid ${active ? C.green : C.border}`,
                      color: active ? C.green : C.textSec,
                      fontWeight: active ? 700 : 400,
                      cursor: 'pointer',
                    }}
                  >
                    {cat.emoji} {cat.label}
                  </button>
                );
              })}
            </div>

            <SectionHeader>지금 뜨는 딜</SectionHeader>
            {hotDeals.length === 0 && (
              <div style={{ textAlign: 'center', padding: '20px 0', color: C.textDim, fontSize: 13 }}>
                딜을 불러오는 중...
              </div>
            )}
            {hotDeals.map(deal => <DealCard key={deal.id} deal={deal} />)}
          </>
        )}

        {/* 검색 결과 */}
        {isSearching && (
          <>
            <div style={{ marginTop: 16, marginBottom: 10, fontSize: 12, color: C.textDim }}>
              "{query}" 검색 결과 · {results.length}건
            </div>
            {results.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 0' }}>
                <div style={{ fontSize: 36, marginBottom: 12 }}>😅</div>
                <p style={{ fontSize: 13, color: C.textDim, marginBottom: 16 }}>
                  검색 결과가 없어요<br />딜을 직접 만들어보세요!
                </p>
                <button
                  onClick={() => navigate('/deal/create')}
                  style={{
                    padding: '10px 20px', borderRadius: 12, fontSize: 13, fontWeight: 700,
                    background: `${C.green}22`, border: `1px solid ${C.green}66`, color: C.green, cursor: 'pointer',
                  }}
                >딜 만들기 →</button>
              </div>
            ) : (
              results.map(deal => <DealCard key={deal.id} deal={deal} />)
            )}
          </>
        )}
      </div>
    </div>
  );
}
