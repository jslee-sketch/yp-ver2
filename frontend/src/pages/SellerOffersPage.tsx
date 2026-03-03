import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useApiData } from '../api/hooks';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import type { OfferResponse } from '../api/types';
import LoadingSkeleton from '../components/common/LoadingSkeleton';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

function fmtP(n: number) { return '₩' + n.toLocaleString('ko-KR'); }
function fmtDate(s: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

export default function SellerOffersPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const { data: offers, loading, error, refetch } = useApiData<OfferResponse[]>(async () => {
    try {
      const res = await apiClient.get(API.OFFERS.LIST, { params: { seller_id: user?.seller?.id ?? user?.id } });
      return (res.data ?? []) as OfferResponse[];
    } catch { return []; }
  }, [user?.id]);

  const items = offers ?? [];
  const active = items.filter(o => o.is_active);
  const inactive = items.filter(o => !o.is_active);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>오퍼 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 요약 */}
        <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>활성 오퍼</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.green }}>{active.length}</div>
          </div>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>비활성</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.textSec }}>{inactive.length}</div>
          </div>
        </div>

        {loading && <LoadingSkeleton variant="cards" count={3} />}
        {!loading && error && <ErrorMessage message={error} onRetry={refetch} />}

        {!loading && !error && (
          <>
            <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>
              전체 {items.length}건
            </div>

            {items.length === 0 && (
              <EmptyState icon="📋" message="아직 제출한 오퍼가 없어요" />
            )}

        {items.map(offer => (
          <div key={offer.id} style={{

            background: C.bgCard, border: `1px solid ${C.border}`,
            borderLeft: `3px solid ${offer.is_active ? C.green : '#757575'}`,
            borderRadius: 14, padding: 14, marginBottom: 8,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>딜 #{offer.deal_id}</span>
              <span style={{
                fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                background: offer.is_active ? `${C.green}22` : 'rgba(117,117,117,0.2)',
                color: offer.is_active ? C.green : '#757575',
              }}>{offer.is_active ? '활성' : '비활성'}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: C.textSec }}>가격</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{fmtP(offer.price)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
              <span style={{ fontSize: 12, color: C.textSec }}>수량</span>
              <span style={{ fontSize: 12, color: C.text }}>
                {offer.sold_qty + offer.reserved_qty}/{offer.total_available_qty}개 (예약 {offer.reserved_qty})
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 10, color: C.textDim }}>{fmtDate(offer.created_at)}</span>
              <button
                onClick={() => navigate(`/deal/${offer.deal_id}`)}
                style={{ fontSize: 11, fontWeight: 700, color: C.green, cursor: 'pointer', background: 'none', border: 'none', padding: 0 }}
              >딜 보기 ›</button>
            </div>
          </div>
        ))}
          </>
        )}
      </div>
    </div>
  );
}
