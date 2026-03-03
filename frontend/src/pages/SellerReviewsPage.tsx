import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchReviewsBySeller, fetchSellerReviewSummary } from '../api/reviewApi';
import { useApiData } from '../api/hooks';
import type { Review } from '../api/types';
import type { SellerReviewSummary } from '../api/reviewApi';
import LoadingSkeleton from '../components/common/LoadingSkeleton';
import ErrorMessage from '../components/common/ErrorMessage';
import EmptyState from '../components/common/EmptyState';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
  yellow: '#ffe156',
};

function fmtDate(s: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

export default function SellerReviewsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const sellerId = user?.seller?.id ?? user?.id ?? 0;

  const { data: reviews, loading, error, refetch } = useApiData<Review[]>(
    () => fetchReviewsBySeller(sellerId),
    [sellerId],
  );

  const { data: summary } = useApiData<SellerReviewSummary | null>(
    () => fetchSellerReviewSummary(sellerId),
    [sellerId],
  );

  const items = reviews ?? [];

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>리뷰 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 요약 카드 */}
        {summary && (
          <div style={{
            background: C.bgCard, border: `1px solid ${C.border}`, borderTop: `3px solid ${C.yellow}`,
            borderRadius: 16, padding: 16, marginBottom: 16,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 32, fontWeight: 800, color: C.yellow }}>
                  {summary.avg_rating.toFixed(1)}
                </div>
                <div style={{ fontSize: 11, color: C.textDim }}>평균 평점</div>
              </div>
              <div style={{ flex: 1 }}>
                {[5, 4, 3, 2, 1].map(star => {
                  const count = summary.rating_distribution?.[star] ?? 0;
                  const pct = summary.total_count > 0 ? (count / summary.total_count * 100) : 0;
                  return (
                    <div key={star} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                      <span style={{ fontSize: 11, color: C.textDim, width: 16 }}>{star}</span>
                      <div style={{ flex: 1, height: 4, borderRadius: 2, background: C.bgEl, overflow: 'hidden' }}>
                        <div style={{ width: `${pct}%`, height: '100%', background: C.yellow, borderRadius: 2 }} />
                      </div>
                      <span style={{ fontSize: 10, color: C.textDim, width: 20, textAlign: 'right' }}>{count}</span>
                    </div>
                  );
                })}
              </div>
            </div>
            <div style={{ textAlign: 'center', fontSize: 11, color: C.textDim, marginTop: 8 }}>
              총 {summary.total_count}개 리뷰
            </div>
          </div>
        )}

        {loading && <LoadingSkeleton variant="cards" count={3} />}
        {!loading && error && <ErrorMessage message={error} onRetry={refetch} />}

        {!loading && !error && (
          <>
            <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>
              리뷰 {items.length}건
            </div>

            {items.length === 0 && (
              <EmptyState icon="⭐" message="아직 받은 리뷰가 없어요" />
            )}

        {items.map(review => (
          <div key={review.id} style={{
            background: C.bgCard, border: `1px solid ${C.border}`,
            borderRadius: 14, padding: 14, marginBottom: 8,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <div style={{ display: 'flex', gap: 2 }}>
                {[1, 2, 3, 4, 5].map(s => (
                  <span key={s} style={{ fontSize: 14, color: s <= review.rating ? C.yellow : C.bgEl }}>
                    ★
                  </span>
                ))}
              </div>
              <span style={{ fontSize: 10, color: C.textDim }}>{fmtDate(review.created_at)}</span>
            </div>
            {review.comment && (
              <div style={{ fontSize: 13, color: C.text, lineHeight: 1.5 }}>{review.comment}</div>
            )}
            <div style={{ fontSize: 11, color: C.textDim, marginTop: 6 }}>
              구매자 #{review.buyer_id} · 예약 #{review.reservation_id}
            </div>
          </div>
        ))}
          </>
        )}
      </div>
    </div>
  );
}
