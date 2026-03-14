import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { trackBehavior } from '../utils/behaviorTracker';
import { useAuth } from '../contexts/AuthContext';
import { fetchReviewsBySeller, fetchSellerReviewSummary } from '../api/reviewApi';
import { useApiData } from '../api/hooks';
import type { Review } from '../api/types';
import type { SellerReviewSummary } from '../api/reviewApi';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { showToast } from '../components/common/Toast';
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

  // Reply modal
  const [replyTarget, setReplyTarget] = useState<Review | null>(null);
  const [replyText, setReplyText] = useState('');
  const [replySaving, setReplySaving] = useState(false);

  const { data: reviews, loading, error, refetch } = useApiData<Review[]>(
    () => fetchReviewsBySeller(sellerId),
    [sellerId],
  );

  const { data: summary } = useApiData<SellerReviewSummary | null>(
    () => fetchSellerReviewSummary(sellerId),
    [sellerId],
  );

  const items = reviews ?? [];

  // ── 행동 수집: SELLER_VIEW_REVIEW ──
  useEffect(() => {
    trackBehavior('SELLER_VIEW_REVIEW', { meta: { page: 'reviews' } });
  }, []);

  const handleReply = async () => {
    if (!replyTarget || !replyText.trim()) return;
    setReplySaving(true);
    try {
      await apiClient.post(API.REVIEWS.REPLY(replyTarget.id), {
        comment: replyText.trim(),
      });
      trackBehavior('SELLER_REPLY_REVIEW', { target_type: 'review', target_id: replyTarget.id });
      showToast('답글 등록 완료', 'success');
      setReplyTarget(null);
      setReplyText('');
      refetch();
    } catch {
      showToast('답글 기능이 준비 중입니다', 'error');
    }
    setReplySaving(false);
  };

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

            {items.length === 0 && !summary && (
              <div style={{
                background: C.bgCard, border: `1px solid ${C.border}`, borderTop: `3px solid ${C.yellow}`,
                borderRadius: 16, padding: 16, marginBottom: 16, textAlign: 'center',
              }}>
                <div style={{ fontSize: 32, fontWeight: 800, color: C.yellow }}>-</div>
                <div style={{ fontSize: 11, color: C.textDim }}>평균 평점</div>
                <div style={{ fontSize: 11, color: C.textDim, marginTop: 8 }}>아직 리뷰가 없습니다</div>
              </div>
            )}

            {items.length === 0 && (
              <EmptyState icon="⭐" message="아직 받은 리뷰가 없어요" sub="구매자가 리뷰를 남기면 여기에 표시됩니다" />
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
                  <div style={{ fontSize: 13, color: C.text, lineHeight: 1.5, marginBottom: 6 }}>{review.comment}</div>
                )}
                {review.seller_reply && (
                  <div style={{
                    background: `${C.green}08`, border: `1px solid ${C.green}22`, borderRadius: 10,
                    padding: '10px 12px', marginBottom: 6,
                  }}>
                    <div style={{ fontSize: 10, color: C.green, fontWeight: 700, marginBottom: 4 }}>내 답글</div>
                    <div style={{ fontSize: 12, color: C.text, lineHeight: 1.5 }}>{review.seller_reply}</div>
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 11, color: C.textDim }}>
                    구매자 #{review.buyer_id} · 주문번호 #{review.reservation_id}
                  </span>
                  <button
                    onClick={() => { setReplyTarget(review); setReplyText(''); }}
                    style={{ fontSize: 11, fontWeight: 700, color: C.green, cursor: 'pointer', background: 'none', border: 'none', padding: '4px 0' }}>
                    {review.seller_reply ? '답글 수정' : '답글'}
                  </button>
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      {/* 답글 모달 */}
      {replyTarget && (
        <>
          <div onClick={() => setReplyTarget(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000 }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: '92%', maxWidth: 400, background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 20, padding: '24px 20px', zIndex: 3001 }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 4 }}>답글 달기</div>
            <div style={{ fontSize: 12, color: C.textSec, marginBottom: 12 }}>
              구매자 #{replyTarget.buyer_id}님의 리뷰
            </div>
            {replyTarget.comment && (
              <div style={{
                background: C.bgEl, border: `1px solid ${C.border}`, borderRadius: 10,
                padding: 12, fontSize: 12, color: C.textSec, marginBottom: 14, lineHeight: 1.5,
              }}>
                "{replyTarget.comment}"
              </div>
            )}
            <textarea
              value={replyText} onChange={e => setReplyText(e.target.value)}
              placeholder="답글을 입력해주세요"
              rows={3}
              style={{ width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: 10, fontSize: 13, background: C.bgEl, border: `1px solid ${C.border}`, color: C.text, resize: 'none', marginBottom: 16 }}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setReplyTarget(null)} style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>취소</button>
              <button disabled={replySaving || !replyText.trim()} onClick={() => void handleReply()}
                style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: replySaving ? `${C.green}55` : C.green, border: 'none', color: '#0a0a0f', cursor: replySaving || !replyText.trim() ? 'not-allowed' : 'pointer' }}>
                {replySaving ? '등록 중...' : '등록'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
