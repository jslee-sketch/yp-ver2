import { useState, useRef } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import DateRangeFilter from '../components/common/DateRangeFilter';

const C = {
  cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252',
  purple: '#7c4dff', blue: '#60a5fa',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
};

const CATEGORIES = [
  { key: '', label: '전체' },
  { key: 'deals', label: '딜' },
  { key: 'offers', label: '오퍼' },
  { key: 'reservations', label: '예약' },
  { key: 'settlements', label: '정산' },
  { key: 'users', label: '사용자' },
];

const stickyHead = { position: 'sticky' as const, top: 0, backgroundColor: '#1a1a2e', zIndex: 10 };

export default function AdminUnifiedSearchPage() {
  const [keyword, setKeyword] = useState('');
  const [category, setCategory] = useState('');
  const [results, setResults] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const dateRef = useRef({ from: '', to: '' });

  const search = async () => {
    if (!keyword.trim() && !dateRef.current.from) return;
    setLoading(true);
    try {
      const params: any = { keyword: keyword.trim(), limit: 50 };
      if (category) params.category = category;
      if (dateRef.current.from) params.date_from = dateRef.current.from;
      if (dateRef.current.to) params.date_to = dateRef.current.to;
      const r = await apiClient.get(API.ADMIN.UNIFIED_SEARCH, { params });
      setResults(r.data || {});
    } catch (e) {
      console.error('Search error:', e);
      setResults({});
    }
    setLoading(false);
    setSearched(true);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') search();
  };

  const totalCount = Object.values(results).reduce((a, arr) => a + (arr?.length || 0), 0);

  const navigate = (path: string) => window.open(path, '_blank');

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>통합 검색</h1>

      {/* Search bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="품목명, ID, 판매자명, 닉네임 등 검색..."
          style={{
            flex: 1, padding: '10px 14px', borderRadius: 10,
            border: `1px solid ${C.border}`, background: C.card,
            color: C.text, fontSize: 14,
          }}
          autoFocus
        />
        <button
          onClick={search}
          disabled={loading}
          style={{
            padding: '10px 24px', borderRadius: 10, border: 'none',
            background: C.cyan, color: '#000', fontWeight: 700,
            cursor: loading ? 'not-allowed' : 'pointer', fontSize: 14,
          }}
        >
          {loading ? '검색중...' : '검색'}
        </button>
      </div>

      {/* Category toggles */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
        {CATEGORIES.map(c => (
          <button
            key={c.key}
            onClick={() => setCategory(c.key)}
            style={{
              padding: '5px 14px', borderRadius: 16, border: 'none',
              cursor: 'pointer', fontSize: 12, fontWeight: 600,
              background: category === c.key ? C.cyan : C.card,
              color: category === c.key ? '#000' : C.textSec,
            }}
          >
            {c.label}
          </button>
        ))}
      </div>

      {/* Date range */}
      <DateRangeFilter onFilter={(f, t) => { dateRef.current = { from: f, to: t }; }} style={{ marginBottom: 16 }} />

      {/* Results */}
      {searched && (
        <div style={{ fontSize: 13, color: C.textSec, marginBottom: 12 }}>
          검색 결과: {totalCount}건
        </div>
      )}

      {/* Deals */}
      {results.deals?.length > 0 && (
        <ResultSection title="딜" color={C.cyan} count={results.deals.length}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: '#1a1a2e' }}>
              {['D-#', '품목명', '목표가', '시장가', '상태', '생성일'].map(h => (
                <th key={h} style={{ padding: '8px', color: C.textSec, textAlign: 'left', fontWeight: 600 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {results.deals.map((d: any) => (
                <tr key={d.id} style={{ borderTop: `1px solid ${C.border}`, cursor: 'pointer' }} onClick={() => navigate(`/deal/${d.id}/journey`)}>
                  <td style={{ padding: 8, color: C.cyan }}>D-{d.id}</td>
                  <td style={{ padding: 8, color: C.text }}>{d.product_name || '-'}</td>
                  <td style={{ padding: 8, color: C.orange }}>{d.target_price?.toLocaleString() || '-'}</td>
                  <td style={{ padding: 8, color: C.textSec }}>{d.market_price?.toLocaleString() || '-'}</td>
                  <td style={{ padding: 8 }}><StatusBadge status={d.status} /></td>
                  <td style={{ padding: 8, color: C.textSec, fontSize: 12 }}>{d.created_at?.split('T')[0]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ResultSection>
      )}

      {/* Offers */}
      {results.offers?.length > 0 && (
        <ResultSection title="오퍼" color={C.green} count={results.offers.length}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: '#1a1a2e' }}>
              {['O-#', 'D-#', '품목명', '가격', '수량', '상태', '생성일'].map(h => (
                <th key={h} style={{ padding: 8, color: C.textSec, textAlign: 'left', fontWeight: 600 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {results.offers.map((o: any) => (
                <tr key={o.id} style={{ borderTop: `1px solid ${C.border}` }}>
                  <td style={{ padding: 8, color: C.green }}>O-{o.id}</td>
                  <td style={{ padding: 8, color: C.cyan, cursor: 'pointer', textDecoration: 'underline' }} onClick={() => navigate(`/deal/${o.deal_id}/journey`)}>D-{o.deal_id}</td>
                  <td style={{ padding: 8, color: C.text }}>{o.product_name || '-'}</td>
                  <td style={{ padding: 8, color: C.orange }}>{o.price?.toLocaleString() || '-'}</td>
                  <td style={{ padding: 8, color: C.textSec }}>{o.quantity ?? '-'}</td>
                  <td style={{ padding: 8 }}><StatusBadge status={o.status} /></td>
                  <td style={{ padding: 8, color: C.textSec, fontSize: 12 }}>{o.created_at?.split('T')[0]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ResultSection>
      )}

      {/* Reservations */}
      {results.reservations?.length > 0 && (
        <ResultSection title="예약" color={C.orange} count={results.reservations.length}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: '#1a1a2e' }}>
              {['R-#', 'D-#', '품목명', '수량', '금액', '상태', '생성일'].map(h => (
                <th key={h} style={{ padding: 8, color: C.textSec, textAlign: 'left', fontWeight: 600 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {results.reservations.map((r: any) => (
                <tr key={r.id} style={{ borderTop: `1px solid ${C.border}` }}>
                  <td style={{ padding: 8, color: C.orange }}>R-{r.id}</td>
                  <td style={{ padding: 8, color: C.cyan, cursor: 'pointer', textDecoration: 'underline' }} onClick={() => navigate(`/deal/${r.deal_id}/journey`)}>D-{r.deal_id}</td>
                  <td style={{ padding: 8, color: C.text }}>{r.product_name || '-'}</td>
                  <td style={{ padding: 8, color: C.textSec }}>{r.quantity ?? '-'}</td>
                  <td style={{ padding: 8, color: C.orange }}>{r.amount?.toLocaleString() || '-'}</td>
                  <td style={{ padding: 8 }}><StatusBadge status={r.status} /></td>
                  <td style={{ padding: 8, color: C.textSec, fontSize: 12 }}>{r.created_at?.split('T')[0]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ResultSection>
      )}

      {/* Settlements */}
      {results.settlements?.length > 0 && (
        <ResultSection title="정산" color={C.purple} count={results.settlements.length}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: '#1a1a2e' }}>
              {['S-#', 'R-#', '품목명', '정산액', '상태', '생성일'].map(h => (
                <th key={h} style={{ padding: 8, color: C.textSec, textAlign: 'left', fontWeight: 600 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {results.settlements.map((s: any) => (
                <tr key={s.id} style={{ borderTop: `1px solid ${C.border}` }}>
                  <td style={{ padding: 8, color: C.purple }}>S-{s.id}</td>
                  <td style={{ padding: 8, color: C.orange }}>R-{s.reservation_id}</td>
                  <td style={{ padding: 8, color: C.text }}>{s.product_name || '-'}</td>
                  <td style={{ padding: 8, color: C.green }}>{s.payout_amount?.toLocaleString() || '-'}</td>
                  <td style={{ padding: 8 }}><StatusBadge status={s.status} /></td>
                  <td style={{ padding: 8, color: C.textSec, fontSize: 12 }}>{s.created_at?.split('T')[0]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ResultSection>
      )}

      {/* Users */}
      {results.users?.length > 0 && (
        <ResultSection title="사용자" color={C.blue} count={results.users.length}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead><tr style={{ background: '#1a1a2e' }}>
              {['ID', '유형', '닉네임', '상호명/이메일'].map(h => (
                <th key={h} style={{ padding: 8, color: C.textSec, textAlign: 'left', fontWeight: 600 }}>{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {results.users.map((u: any, i: number) => (
                <tr key={`${u.type}-${u.id}-${i}`} style={{ borderTop: `1px solid ${C.border}` }}>
                  <td style={{ padding: 8, color: C.blue }}>{u.type === 'buyer' ? 'B' : 'S'}-{u.id}</td>
                  <td style={{ padding: 8 }}><span style={{ padding: '2px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600, background: u.type === 'buyer' ? 'rgba(96,165,250,0.15)' : 'rgba(0,230,118,0.15)', color: u.type === 'buyer' ? C.blue : C.green }}>{u.type === 'buyer' ? '구매자' : '판매자'}</span></td>
                  <td style={{ padding: 8, color: C.text }}>{u.nickname || '-'}</td>
                  <td style={{ padding: 8, color: C.textSec }}>{u.business_name || u.email || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ResultSection>
      )}

      {searched && totalCount === 0 && !loading && (
        <div style={{ padding: 60, textAlign: 'center', color: C.textSec }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>&#128269;</div>
          <div style={{ fontSize: 15 }}>검색 결과가 없습니다</div>
          <div style={{ fontSize: 12, marginTop: 4 }}>다른 키워드로 검색해 보세요</div>
        </div>
      )}
    </div>
  );
}

function ResultSection({ title, color, count, children }: { title: string; color: string; count: number; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 15, fontWeight: 700, color }}>{title}</span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', background: 'var(--bg-elevated)', padding: '2px 8px', borderRadius: 10 }}>{count}건</span>
      </div>
      <div style={{ borderRadius: 12, border: '1px solid var(--border-subtle)', overflow: 'hidden' }}>
        {children}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    open: '#00e5ff', OPEN: '#00e5ff', closed: '#78909c', CLOSED: '#78909c',
    PAID: '#00e5ff', SHIPPED: '#ff9100', CONFIRMED: '#00e676', CANCELLED: '#ff5252',
    HOLD: '#ff9100', READY: '#00e5ff', APPROVED: '#4fc3f7',
    active: '#00e676', ACTIVE: '#00e676', expired: '#ff5252',
  };
  return (
    <span style={{
      padding: '2px 8px', borderRadius: 8, fontSize: 11, fontWeight: 600,
      background: `${colors[status] || '#78909c'}22`,
      color: colors[status] || '#78909c',
    }}>
      {status || '-'}
    </span>
  );
}
