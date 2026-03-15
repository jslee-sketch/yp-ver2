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

function fmtP(n: number) { return '₩' + (n ?? 0).toLocaleString('ko-KR'); }

// SSOT: app/policy/params/defaults.yaml → levels → platform_fee_rate
// Lv.1=최고등급(2.0%), Lv.6=기본등급(3.5%)
const COMMISSION_BY_LEVEL: Record<number, number> = {
  1: 2.0, 2: 2.5, 3: 2.7, 4: 2.8, 5: 3.0, 6: 3.5,
};

interface DashData {
  todayOrders: number;
  pendingShip: number;
  monthRevenue: number;
  avgRating: number;
  totalOffers: number;
  confirmedOffers: number;
  sellerLevel: number;
}

export default function SellerDashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const sellerId = user?.seller?.id ?? user?.id ?? 0;
  const [data, setData] = useState<DashData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sellerId) return;
    (async () => {
      try {
        const [resvRes, reviewRes, offerRes, sellerRes] = await Promise.all([
          apiClient.get(API.RESERVATIONS.LIST_SELLER(sellerId)).catch(() => ({ data: [] })),
          apiClient.get(API.REVIEWS.SUMMARY(sellerId)).catch(() => ({ data: null })),
          apiClient.get(API.OFFERS_V36.LIST, { params: { seller_id: sellerId } }).catch(() => ({ data: [] })),
          apiClient.get(`/sellers/me`).catch(() => ({ data: null })),
        ]);
        const resvs = Array.isArray(resvRes.data) ? resvRes.data : [];
        const offers = Array.isArray(offerRes.data) ? offerRes.data : [];
        const today = new Date().toISOString().split('T')[0];

        const todayOrders = resvs.filter((r: Record<string, unknown>) =>
          String(r.paid_at ?? '').startsWith(today)).length;
        const pendingShip = resvs.filter((r: Record<string, unknown>) =>
          r.status === 'PAID' && !r.shipped_at).length;

        const now = new Date();
        const monthStart = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
        const monthRevenue = resvs
          .filter((r: Record<string, unknown>) => r.status === 'PAID' && String(r.paid_at ?? '') >= monthStart)
          .reduce((a: number, r: Record<string, unknown>) => a + ((r.amount_total as number) || 0), 0);

        setData({
          todayOrders,
          pendingShip,
          monthRevenue,
          avgRating: reviewRes.data?.adjusted_rating ?? reviewRes.data?.raw_avg ?? 0,
          totalOffers: offers.length,
          confirmedOffers: offers.filter((o: Record<string, unknown>) => o.is_confirmed).length,
          sellerLevel: sellerRes.data?.level ?? 1,
        });
      } catch (err) {
        console.error('대시보드 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [sellerId]);

  const quickLinks = [
    { icon: '📝', label: '오퍼 관리', path: '/seller/offers' },
    { icon: '📦', label: '배송 관리', path: '/seller/delivery' },
    { icon: '💰', label: '정산 관리', path: '/seller/settlements' },
    { icon: '⭐', label: '리뷰 관리', path: '/seller/reviews' },
    { icon: '💬', label: '고객 문의', path: '/seller/inquiries' },
    { icon: '📊', label: '판매 통계', path: '/seller/stats' },
  ];

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>판매자 대시보드</span>
      </div>

      <div style={{ padding: '14px 16px 0', maxWidth: 1200, margin: '0 auto' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : !data ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 13, marginBottom: 8 }}>대시보드 데이터를 불러오지 못했습니다.</div>
            <button onClick={() => window.location.reload()} style={{
              padding: '8px 16px', borderRadius: 8, fontSize: 12, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer',
            }}>재시도</button>
          </div>
        ) : (
          <>
            {/* 판매자 레벨 & 수수료 */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14,
              background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14, padding: '12px 16px',
            }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10,
                background: 'linear-gradient(135deg, #00e676, #00b0ff)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 16, fontWeight: 900, color: '#0a0a0f',
              }}>
                Lv.{data.sellerLevel}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
                  판매자 등급 Lv.{data.sellerLevel}
                </div>
                <div style={{ fontSize: 11, color: C.textDim }}>
                  수수료율 <span style={{ fontWeight: 700, color: C.orange }}>{COMMISSION_BY_LEVEL[data.sellerLevel] ?? 3.5}%</span>
                </div>
              </div>
            </div>

            {/* 핵심 지표 카드 */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
              <div style={{ textAlign: 'center', padding: 16, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
                <div style={{ fontSize: 10, color: C.textDim }}>오늘 주문</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#00b0ff' }}>{data.todayOrders}</div>
              </div>
              <div style={{ textAlign: 'center', padding: 16, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
                <div style={{ fontSize: 10, color: C.textDim }}>발송대기</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: data.pendingShip > 0 ? C.orange : C.green }}>{data.pendingShip}</div>
              </div>
              <div style={{ textAlign: 'center', padding: 16, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
                <div style={{ fontSize: 10, color: C.textDim }}>이번달 매출</div>
                <div style={{ fontSize: 18, fontWeight: 800, color: C.green }}>{fmtP(data.monthRevenue)}</div>
              </div>
              <div style={{ textAlign: 'center', padding: 16, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
                <div style={{ fontSize: 10, color: C.textDim }}>평균 평점</div>
                <div style={{ fontSize: 24, fontWeight: 800, color: '#ffe156' }}>
                  {data.avgRating > 0 ? data.avgRating.toFixed(1) : '-'}
                </div>
              </div>
            </div>

            {/* 오퍼 요약 */}
            <div style={{
              background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
              padding: 16, marginBottom: 16,
            }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 8 }}>오퍼 현황</div>
              <div style={{ display: 'flex', gap: 16 }}>
                <div>
                  <div style={{ fontSize: 10, color: C.textDim }}>총 오퍼</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: C.text }}>{data.totalOffers}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: C.textDim }}>확정</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: C.green }}>{data.confirmedOffers}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: C.textDim }}>낙찰률</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: C.orange }}>
                    {data.totalOffers > 0 ? ((data.confirmedOffers / data.totalOffers) * 100).toFixed(0) : 0}%
                  </div>
                </div>
              </div>
            </div>

            {/* 바로가기 */}
            <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>바로가기</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
              {quickLinks.map(q => (
                <button key={q.path} onClick={() => navigate(q.path)} style={{
                  textAlign: 'center', padding: '14px 8px', background: C.bgCard,
                  border: `1px solid ${C.border}`, borderRadius: 12, cursor: 'pointer',
                }}>
                  <div style={{ fontSize: 22, marginBottom: 4 }}>{q.icon}</div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: C.text }}>{q.label}</div>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
