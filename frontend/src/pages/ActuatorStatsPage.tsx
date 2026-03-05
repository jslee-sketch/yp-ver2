import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

interface SellerStat {
  seller_id: number;
  name?: string;
  business_name?: string;
  total_offers: number;
  confirmed_offers: number;
  active_offers: number;
  total_sold_qty: number;
}

interface CommSummary {
  pending_count: number;
  pending_total_amount: number;
  ready_count: number;
  ready_total_amount: number;
  paid_count: number;
  paid_total_amount: number;
}

function fmtWon(n: number) {
  if (n >= 10000) return (n / 10000).toFixed(0) + '만';
  return n.toLocaleString('ko-KR');
}

export default function ActuatorStatsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [sellers, setSellers] = useState<SellerStat[]>([]);
  const [commSummary, setCommSummary] = useState<CommSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    const actuatorId = user.id;
    (async () => {
      try {
        const [sellersRes, commRes] = await Promise.all([
          apiClient.get(`/actuators/${actuatorId}/sellers`),
          apiClient.get(`/actuators/${actuatorId}/commissions/summary`),
        ]);
        setSellers(Array.isArray(sellersRes.data) ? sellersRes.data : []);
        setCommSummary(commRes.data ?? null);
      } catch (err) {
        console.error('활동 현황 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  const totalOffers = sellers.reduce((a, s) => a + s.total_offers, 0);
  const totalConfirmed = sellers.reduce((a, s) => a + s.confirmed_offers, 0);
  const totalSold = sellers.reduce((a, s) => a + s.total_sold_qty, 0);
  const totalComm = commSummary
    ? commSummary.pending_total_amount + commSummary.ready_total_amount + commSummary.paid_total_amount
    : 0;

  // Find max offers for bar chart scaling
  const maxOffers = Math.max(1, ...sellers.map(s => s.total_offers));

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>활동 현황</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : (
          <>
            {/* 요약 카드 */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
              {[
                { label: '내 판매자', value: `${sellers.length}명`, color: C.green },
                { label: '총 오퍼', value: `${totalOffers}건`, color: '#00b0ff' },
                { label: '총 낙찰', value: `${totalConfirmed}건`, color: C.orange },
                { label: '총 커미션', value: `₩${fmtWon(totalComm)}`, color: '#e040fb' },
              ].map(card => (
                <div key={card.label} style={{
                  textAlign: 'center', padding: 14, background: C.bgCard,
                  border: `1px solid ${C.border}`, borderRadius: 14,
                }}>
                  <div style={{ fontSize: 10, color: C.textDim, marginBottom: 4 }}>{card.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: card.color }}>{card.value}</div>
                </div>
              ))}
            </div>

            {/* 커미션 상태 요약 */}
            {commSummary && (
              <div style={{
                background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
                padding: 14, marginBottom: 16,
              }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>커미션 현황</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 10, color: C.textDim }}>대기</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: C.orange }}>{commSummary.pending_count}건</div>
                    <div style={{ fontSize: 10, color: C.textDim }}>₩{fmtWon(commSummary.pending_total_amount)}</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 10, color: C.textDim }}>정산가능</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: '#00b0ff' }}>{commSummary.ready_count}건</div>
                    <div style={{ fontSize: 10, color: C.textDim }}>₩{fmtWon(commSummary.ready_total_amount)}</div>
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: 10, color: C.textDim }}>지급완료</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: C.green }}>{commSummary.paid_count}건</div>
                    <div style={{ fontSize: 10, color: C.textDim }}>₩{fmtWon(commSummary.paid_total_amount)}</div>
                  </div>
                </div>
              </div>
            )}

            {/* 판매자별 활동 차트 */}
            <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>판매자별 활동</div>
            {sellers.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '30px 0', color: C.textDim, fontSize: 13 }}>
                담당 판매자가 없어요
              </div>
            ) : sellers.map(s => (
              <button key={s.seller_id} onClick={() => navigate(`/actuator/sellers/${s.seller_id}/offers`)}
                style={{
                  width: '100%', textAlign: 'left', cursor: 'pointer',
                  background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12,
                  padding: '12px 14px', marginBottom: 6,
                }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: C.text }}>
                    {s.business_name || s.name || `#${s.seller_id}`}
                  </span>
                  <span style={{ fontSize: 11, color: C.textDim }}>
                    오퍼 {s.total_offers} · 낙찰 {s.confirmed_offers} · 판매 {totalSold > 0 ? fmtWon(s.total_sold_qty) + '개' : '0개'}
                  </span>
                </div>
                {/* 바 차트 */}
                <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                  <div style={{
                    height: 8, borderRadius: 4, background: C.green,
                    width: `${Math.max(4, (s.total_offers / maxOffers) * 100)}%`,
                    transition: 'width 0.3s ease',
                  }} />
                </div>
              </button>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
