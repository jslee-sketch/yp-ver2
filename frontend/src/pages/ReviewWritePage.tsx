import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { useAuth } from '../contexts/AuthContext';

interface OrderInfo {
  product_name: string;
  seller_name: string;
  price: number;
  qty: number;
}

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

function fmtPrice(n: number) { return n.toLocaleString('ko-KR') + '원'; }

export default function ReviewWritePage() {
  const navigate = useNavigate();
  const { reservationId } = useParams<{ reservationId: string }>();
  const { user } = useAuth();

  const [order, setOrder] = useState<OrderInfo | null>(null);

  useEffect(() => {
    if (!reservationId) return;
    const load = async () => {
      try {
        const res = await apiClient.get(API.RESERVATIONS.DETAIL(Number(reservationId)));
        const r = res.data as Record<string, unknown>;
        setOrder({
          product_name: String(r.product_name ?? r.deal_title ?? `예약 #${reservationId}`),
          seller_name: String(r.seller_name ?? r.seller_business_name ?? '판매자'),
          price: Number(r.amount_total ?? r.price ?? 0),
          qty: Number(r.qty ?? 1),
        });
      } catch {
        // API 실패 시 기본값
        setOrder(null);
      }
    };
    void load();
  }, [reservationId]);

  const [rating, setRating]   = useState(0);
  const [hover, setHover]     = useState(0);
  const [comment, setComment] = useState('');

  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (rating === 0) { alert('별점을 선택해주세요!'); return; }
    if (submitting) return;
    setSubmitting(true);
    try {
      await apiClient.post(API.REVIEWS.CREATE, {
        reservation_id: Number(reservationId),
        buyer_id: user?.id,
        rating,
        comment: comment.trim() || undefined,
      });
      alert('리뷰가 등록되었어요! ⭐');
      navigate(-1);
    } catch {
      alert('리뷰 등록에 실패했어요. 다시 시도해주세요.');
      setSubmitting(false);
    }
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 40 }}>
      {/* TopBar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>리뷰 작성</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '20px 16px 0' }}>
        {/* 주문 정보 */}
        {order ? (
          <div style={{
            background: C.bgCard, border: `1px solid ${C.border}`,
            borderRadius: 14, padding: '14px 16px', marginBottom: 24,
          }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 6 }}>📦 {order.product_name}</div>
            <div style={{ fontSize: 12, color: C.textSec }}>
              {order.seller_name} · {fmtPrice(order.price)} · {order.qty}개
            </div>
          </div>
        ) : (
          <div style={{
            background: C.bgCard, border: `1px solid ${C.border}`,
            borderRadius: 14, padding: '14px 16px', marginBottom: 24,
          }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>📦 예약 #{reservationId}</div>
          </div>
        )}

        {/* 별점 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 14, padding: '18px 16px', marginBottom: 16,
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 16 }}>별점</div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10 }}>
            {[1, 2, 3, 4, 5].map(s => (
              <button
                key={s}
                onClick={() => setRating(s)}
                onMouseEnter={() => setHover(s)}
                onMouseLeave={() => setHover(0)}
                style={{ fontSize: 36, background: 'none', border: 'none', cursor: 'pointer', lineHeight: 1, transition: 'transform 0.1s' }}
              >
                {s <= (hover || rating) ? '⭐' : '☆'}
              </button>
            ))}
          </div>
          {rating > 0 && (
            <div style={{ textAlign: 'center', marginTop: 10, fontSize: 13, color: C.textSec }}>
              {['', '별로였어요', '그저 그래요', '괜찮아요', '좋아요', '최고예요!'][rating]}
            </div>
          )}
          {rating === 0 && (
            <div style={{ textAlign: 'center', marginTop: 10, fontSize: 12, color: C.textDim }}>별을 터치해주세요</div>
          )}
        </div>

        {/* 한줄 리뷰 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 14, padding: '16px', marginBottom: 24,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, letterSpacing: 1 }}>한줄 리뷰</div>
            <div style={{ fontSize: 11, color: C.textDim }}>{comment.length}/200</div>
          </div>
          <textarea
            value={comment}
            onChange={e => { if (e.target.value.length <= 200) setComment(e.target.value); }}
            placeholder="리뷰를 입력해주세요 (선택)"
            rows={4}
            style={{
              width: '100%', boxSizing: 'border-box' as const,
              background: 'var(--bg-elevated)', border: `1px solid ${C.border}`,
              borderRadius: 10, padding: '10px 12px',
              fontSize: 13, color: C.text, resize: 'none',
              colorScheme: 'dark' as React.CSSProperties['colorScheme'],
            }}
          />
        </div>

        {/* 등록 버튼 */}
        <button
          onClick={handleSubmit}
          style={{
            width: '100%', padding: '15px', borderRadius: 14,
            background: rating > 0 ? `${C.green}22` : C.bgCard,
            border: `1px solid ${rating > 0 ? C.green : C.border}`,
            color: rating > 0 ? C.green : C.textDim,
            fontSize: 15, fontWeight: 800, cursor: rating > 0 ? 'pointer' : 'default',
            transition: 'all 0.2s',
          }}
        >
          ⭐ 리뷰 등록하기
        </button>
      </div>
    </div>
  );
}
