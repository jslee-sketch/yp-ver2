import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchDeals } from '../api/dealApi';
import { useApiData } from '../api/hooks';
import type { DealResponse } from '../api/types';
import LoadingSkeleton from '../components/common/LoadingSkeleton';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';

// ── 타입 ────────────────────────────────────────────

interface MyCreatedDeal {
  id: number;
  product_name: string;
  target_price: number;
  current_qty: number;
  desired_qty: number;
  offer_count: number;
  status: 'open' | 'closed' | 'archived';
  created_at: string;
  deadline_at: string;
  participant_count: number;
}

const STATUS_FILTERS = ['전체', '진행중', '마감', '종료'];

const STATUS_STYLE: Record<MyCreatedDeal['status'], { color: string; label: string }> = {
  open:     { color: '#00e676', label: '진행중' },
  closed:   { color: '#ff9100', label: '마감'   },
  archived: { color: '#757575', label: '종료'   },
};

const ITEMS_PER_PAGE = 10;

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

function fmtDate(s: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }
function fmtP(n: number) { return '₩' + n.toLocaleString('ko-KR'); }
function daysLeft(deadline: string): number {
  if (!deadline) return 0;
  return Math.max(0, Math.ceil((new Date(deadline).getTime() - Date.now()) / 86400000));
}

export default function MyDealsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const { data: allDeals, loading, error, refetch } = useApiData<MyCreatedDeal[]>(async () => {
    const raw = await fetchDeals(0, 500);
    if (!raw) return [];
    const mapped = (raw as DealResponse[])
      .filter(d => d.creator_id === user?.id)
      .map(d => ({
        id:                d.id,
        product_name:      d.product_name,
        target_price:      d.target_price ?? d.max_budget ?? 0,
        current_qty:       d.current_qty ?? 0,
        desired_qty:       d.desired_qty ?? 1,
        offer_count:       0,
        status:            d.status as MyCreatedDeal['status'],
        created_at:        d.created_at?.split('T')[0] ?? '',
        deadline_at:       d.deadline_at ?? '',
        participant_count: d.current_qty ?? 0,
      }));
    return mapped;
  }, [user?.id]);

  const [statusFilter, setStatusFilter] = useState('전체');
  const [dateFrom, setDateFrom]         = useState('2025-01-01');
  const [dateTo, setDateTo]             = useState('2026-12-31');
  const [keyword, setKeyword]           = useState('');
  const [applied, setApplied]           = useState({ status: '전체', from: '2025-01-01', to: '2026-12-31', kw: '' });
  const [page, setPage]                 = useState(1);

  const filtered = (() => {
    let items = allDeals ?? [];
    if (applied.status !== '전체') {
      const statusMap: Record<string, MyCreatedDeal['status'][]> = {
        '진행중': ['open'],
        '마감':   ['closed'],
        '종료':   ['archived'],
      };
      const allowed = statusMap[applied.status] ?? [];
      items = items.filter(i => allowed.includes(i.status));
    }
    items = items.filter(i => (i.created_at ?? '') >= applied.from && (i.created_at ?? '') <= applied.to);
    if (applied.kw.trim()) {
      const kw = applied.kw.toLowerCase();
      items = items.filter(i => i.product_name.toLowerCase().includes(kw));
    }
    return items;
  })();

  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
  const paged      = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  const doSearch = () => { setApplied({ status: statusFilter, from: dateFrom, to: dateTo, kw: keyword }); setPage(1); };
  const doReset  = () => {
    setStatusFilter('전체'); setDateFrom('2025-01-01'); setDateTo('2026-12-31'); setKeyword('');
    setApplied({ status: '전체', from: '2025-01-01', to: '2026-12-31', kw: '' }); setPage(1);
  };

  const inputSt: React.CSSProperties = {
    padding: '7px 10px', borderRadius: 8, fontSize: 13,
    background: C.bgCard, border: `1px solid ${C.border}`,
    color: C.text, colorScheme: 'dark' as React.CSSProperties['colorScheme'],
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>내딜 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 필터 */}
        <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14, padding: '14px 16px', marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: C.textDim, marginBottom: 8 }}>상태</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
            {STATUS_FILTERS.map(s => (
              <button key={s} onClick={() => setStatusFilter(s)} style={{
                padding: '5px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
                background: statusFilter === s ? `${C.green}22` : C.bgEl,
                border: `1px solid ${statusFilter === s ? C.green : C.border}`,
                color: statusFilter === s ? C.green : C.textSec,
                fontWeight: statusFilter === s ? 700 : 400,
              }}>{s}</button>
            ))}
          </div>

          <div style={{ fontSize: 11, color: C.textDim, marginBottom: 6 }}>기간</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} style={inputSt} />
            <span style={{ color: C.textDim, fontSize: 12 }}>~</span>
            <input type="date" value={dateTo}   onChange={e => setDateTo(e.target.value)}   style={inputSt} />
          </div>

          <div style={{ fontSize: 11, color: C.textDim, marginBottom: 6 }}>키워드</div>
          <input
            type="text" value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') doSearch(); }}
            placeholder="상품명으로 검색..."
            style={{ ...inputSt, width: '100%', boxSizing: 'border-box' as const, marginBottom: 12 }}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={doSearch} style={{ flex: 1, padding: '9px 0', borderRadius: 10, fontSize: 13, fontWeight: 700, background: `${C.green}22`, border: `1px solid ${C.green}66`, color: C.green, cursor: 'pointer' }}>검색</button>
            <button onClick={doReset}  style={{ flex: 1, padding: '9px 0', borderRadius: 10, fontSize: 13, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>초기화</button>
          </div>
        </div>

        {loading && <LoadingSkeleton variant="cards" count={3} />}
        {!loading && error && <ErrorMessage message={error} onRetry={refetch} />}

        {!loading && !error && (
          <>
            <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>
              생성한 딜 {filtered.length}건
            </div>

            {paged.length === 0 ? (
              <EmptyState
                icon="🎧"
                message="아직 생성한 딜이 없어요"
                actionLabel="딜 만들기 →"
                onAction={() => navigate('/deal/create')}
              />
            ) : paged.map(deal => {
          const st      = STATUS_STYLE[deal.status] ?? STATUS_STYLE.open;
          const pct     = deal.desired_qty > 0 ? Math.round((deal.current_qty / deal.desired_qty) * 100) : 0;
          const days    = daysLeft(deal.deadline_at);
          const barFill = Math.min(100, pct);
          return (
            <div key={deal.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${st.color}`,
              borderRadius: 14, padding: '14px', marginBottom: 10,
            }}>
              {/* 헤더 */}
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, marginBottom: 10 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{deal.product_name}</span>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 6,
                      background: 'rgba(255,152,0,0.2)', color: '#ff9800', flexShrink: 0,
                    }}>방장</span>
                  </div>
                  <div style={{ fontSize: 11, color: C.textSec }}>
                    {fmtP(deal.target_price)} · 오퍼 {deal.offer_count}건
                  </div>
                  <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                    참여자 {deal.participant_count}명
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 6, background: `${st.color}22`, color: st.color }}>
                    {st.label}
                  </span>
                  {deal.status === 'open' && days > 0 && (
                    <span style={{ fontSize: 10, color: C.textDim }}>⏰ {days}일 남음</span>
                  )}
                </div>
              </div>

              {/* 진행 바 */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: C.textDim, marginBottom: 4 }}>
                  <span>참여 현황</span>
                  <span>{deal.current_qty}/{deal.desired_qty}명 ({pct}%)</span>
                </div>
                <div style={{ height: 6, borderRadius: 3, background: C.bgEl, overflow: 'hidden' }}>
                  <div style={{
                    height: '100%', width: `${barFill}%`, borderRadius: 3,
                    background: pct >= 100
                      ? `linear-gradient(90deg, ${C.green}, #39ff14)`
                      : pct >= 50
                      ? `linear-gradient(90deg, ${C.green}88, ${C.green})`
                      : `linear-gradient(90deg, #448aff88, #448aff)`,
                    transition: 'width 0.5s ease',
                  }} />
                </div>
              </div>

              {/* 하단 */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 10, color: C.textDim }}>
                  {fmtDate(deal.created_at)} 생성{deal.deadline_at ? ` · ${fmtDate(deal.deadline_at)} 마감` : ''}
                </span>
                <button
                  onClick={() => navigate(`/deal/${deal.id}`)}
                  style={{ padding: '5px 12px', borderRadius: 8, fontSize: 11, fontWeight: 700, background: `${C.green}22`, border: `1px solid ${C.green}66`, color: C.green, cursor: 'pointer' }}
                >딜 관리 ›</button>
              </div>
            </div>
          );
        })}

        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 20, padding: '20px 0' }}>
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, opacity: page <= 1 ? 0.3 : 1, cursor: page <= 1 ? 'default' : 'pointer' }}>‹ 이전</button>
            <span style={{ fontSize: 13, color: C.textSec }}>{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, opacity: page >= totalPages ? 0.3 : 1, cursor: page >= totalPages ? 'default' : 'pointer' }}>다음 ›</button>
          </div>
        )}
          </>
        )}
      </div>
    </div>
  );
}
