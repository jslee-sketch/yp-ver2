import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

function fmtWon(n: number) {
  if (n >= 10000) return (n / 10000).toFixed(0) + '만';
  return n.toLocaleString('ko-KR');
}

interface OfferItem {
  id: number;
  deal_id: number;
  is_active: boolean;
  is_confirmed: boolean;
  sold_qty: number;
  reserved_qty: number;
  price: number;
  total_available_qty: number;
}

interface Reservation {
  id: number;
  amount_total: number;
  status: string;
  paid_at?: string;
}

interface ReviewSummary {
  count: number;
  raw_avg: number;
  adjusted_rating: number;
}

export default function SellerStatsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const sellerId = user?.seller?.id ?? user?.id ?? 0;

  const [offers, setOffers] = useState<OfferItem[]>([]);
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sellerId) return;
    (async () => {
      try {
        const [offersRes, resvRes, reviewRes] = await Promise.all([
          apiClient.get(API.OFFERS_V36.LIST, { params: { seller_id: sellerId } }).catch(() => ({ data: [] })),
          apiClient.get(API.RESERVATIONS.LIST_SELLER(sellerId)).catch(() => ({ data: [] })),
          apiClient.get(API.REVIEWS.SUMMARY(sellerId)).catch(() => ({ data: null })),
        ]);
        setOffers(Array.isArray(offersRes.data) ? offersRes.data : []);
        setReservations(Array.isArray(resvRes.data) ? resvRes.data : []);
        setReviewSummary(reviewRes.data ?? null);
      } catch (err) {
        console.error('통계 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [sellerId]);

  const totalOffers = offers.length;
  const confirmedOffers = offers.filter(o => o.is_confirmed).length;
  const winRate = totalOffers > 0 ? ((confirmedOffers / totalOffers) * 100).toFixed(1) : '0';
  const totalRevenue = reservations.filter(r => r.status === 'PAID').reduce((a, r) => a + r.amount_total, 0);
  const paidOrders = reservations.filter(r => r.paid_at).length;
  const avgRating = reviewSummary?.adjusted_rating ?? reviewSummary?.raw_avg ?? 0;
  const reviewCount = reviewSummary?.count ?? 0;

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>판매 통계</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : (
          <>
            {/* 핵심 지표 */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
              {[
                { label: '총 오퍼', value: `${totalOffers}건`, color: '#00b0ff' },
                { label: '낙찰', value: `${confirmedOffers}건`, color: C.green },
                { label: '총 매출', value: `₩${fmtWon(totalRevenue)}`, color: C.orange },
                { label: '평균 평점', value: avgRating > 0 ? `${avgRating.toFixed(1)}` : '-', color: '#ffe156' },
              ].map(card => (
                <div key={card.label} style={{
                  textAlign: 'center', padding: 16, background: C.bgCard,
                  border: `1px solid ${C.border}`, borderRadius: 14,
                }}>
                  <div style={{ fontSize: 10, color: C.textDim, marginBottom: 4 }}>{card.label}</div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: card.color }}>{card.value}</div>
                </div>
              ))}
            </div>

            {/* 낙찰률 */}
            <div style={{
              background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
              padding: 16, marginBottom: 16,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>낙찰률</span>
                <span style={{ fontSize: 15, fontWeight: 800, color: C.green }}>{winRate}%</span>
              </div>
              <div style={{ height: 10, borderRadius: 5, background: C.bgEl, overflow: 'hidden' }}>
                <div style={{
                  height: '100%', borderRadius: 5, background: `linear-gradient(90deg, ${C.green}, #00b0ff)`,
                  width: `${Math.min(100, parseFloat(winRate))}%`,
                  transition: 'width 0.5s ease',
                }} />
              </div>
              <div style={{ fontSize: 10, color: C.textDim, marginTop: 6 }}>
                {confirmedOffers}건 낙찰 / {totalOffers}건 제출
              </div>
            </div>

            {/* 주문 요약 */}
            <div style={{
              background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
              padding: 16, marginBottom: 16,
            }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>주문 현황</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 10, color: C.textDim }}>결제완료</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: C.text }}>{paidOrders}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 10, color: C.textDim }}>총 예약</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: C.text }}>{reservations.length}</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 10, color: C.textDim }}>리뷰</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: '#ffe156' }}>{reviewCount}건</div>
                </div>
              </div>
            </div>

            {/* 오퍼 현황 바 */}
            <div style={{
              background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
              padding: 16, marginBottom: 16,
            }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>오퍼 상태 분포</div>
              {(() => {
                const active = offers.filter(o => o.is_active && !o.is_confirmed).length;
                const confirmed = confirmedOffers;
                const inactive = offers.filter(o => !o.is_active && !o.is_confirmed).length;
                const total = Math.max(1, totalOffers);
                return (
                  <>
                    <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden', marginBottom: 8 }}>
                      {confirmed > 0 && <div style={{ width: `${(confirmed / total) * 100}%`, background: C.green }} />}
                      {active > 0 && <div style={{ width: `${(active / total) * 100}%`, background: '#00b0ff' }} />}
                      {inactive > 0 && <div style={{ width: `${(inactive / total) * 100}%`, background: '#757575' }} />}
                    </div>
                    <div style={{ display: 'flex', gap: 16, fontSize: 11 }}>
                      <span style={{ color: C.green }}>확정 {confirmed}</span>
                      <span style={{ color: '#00b0ff' }}>활성 {active}</span>
                      <span style={{ color: '#757575' }}>만료 {inactive}</span>
                    </div>
                  </>
                );
              })()}
            </div>

            {/* 월별 매출 테이블 (최근 6개월) */}
            <div style={{
              background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
              padding: 16,
            }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>월별 매출 현황</div>
              {(() => {
                const now = new Date();
                const months: { key: string; label: string; revenue: number; count: number }[] = [];
                for (let i = 0; i < 6; i++) {
                  const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
                  const key = d.toISOString().slice(0, 7); // YYYY-MM
                  const label = `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, '0')}`;
                  const monthResvs = reservations.filter(r => r.paid_at && r.paid_at.startsWith(key));
                  const revenue = monthResvs.reduce((a, r) => a + r.amount_total, 0);
                  months.push({ key, label, revenue, count: monthResvs.length });
                }
                return (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead>
                      <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                        <th style={{ padding: '8px 4px', textAlign: 'left', color: C.textDim }}>월</th>
                        <th style={{ padding: '8px 4px', textAlign: 'right', color: C.textDim }}>거래</th>
                        <th style={{ padding: '8px 4px', textAlign: 'right', color: C.textDim }}>매출</th>
                      </tr>
                    </thead>
                    <tbody>
                      {months.map(m => (
                        <tr key={m.key} style={{ borderBottom: `1px solid ${C.border}` }}>
                          <td style={{ padding: '8px 4px', color: C.text }}>{m.label}</td>
                          <td style={{ padding: '8px 4px', textAlign: 'right', color: C.textSec }}>{m.count}건</td>
                          <td style={{ padding: '8px 4px', textAlign: 'right', fontWeight: 700, color: C.green }}>₩{fmtWon(m.revenue)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                );
              })()}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
