import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  cyan: '#00e5ff', green: '#00e676', magenta: '#e040fb', orange: '#ff9100',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
};

interface Stats {
  buyers: number;
  sellers: number;
  deals: number;
  offers: number;
  pendingSellers: number;
}

export default function AdminDashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats>({ buyers: 0, sellers: 0, deals: 0, offers: 0, pendingSellers: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [buyersRes, sellersRes, dealsRes, offersRes] = await Promise.allSettled([
          apiClient.get(API.BUYERS.LIST),
          apiClient.get(API.SELLERS.LIST),
          apiClient.get(API.DEALS.LIST),
          apiClient.get(API.OFFERS.LIST),
        ]);

        const buyers = buyersRes.status === 'fulfilled' ? buyersRes.value.data : [];
        const sellers = sellersRes.status === 'fulfilled' ? sellersRes.value.data : [];
        const deals = dealsRes.status === 'fulfilled' ? dealsRes.value.data : [];
        const offers = offersRes.status === 'fulfilled' ? offersRes.value.data : [];

        const pendingSellers = Array.isArray(sellers)
          ? sellers.filter((s: { verified_at?: string | null }) => !s.verified_at).length
          : 0;

        setStats({
          buyers: Array.isArray(buyers) ? buyers.length : 0,
          sellers: Array.isArray(sellers) ? sellers.length : 0,
          deals: Array.isArray(deals) ? deals.length : 0,
          offers: Array.isArray(offers) ? offers.length : 0,
          pendingSellers,
        });
      } catch {
        /* ignore */
      }
      setLoading(false);
    };
    load();
  }, []);

  const cards = [
    { label: '총 구매자', value: stats.buyers, color: C.green, icon: '👤' },
    { label: '총 판매자', value: stats.sellers, color: C.cyan, icon: '👥' },
    { label: '총 딜', value: stats.deals, color: C.magenta, icon: '🔥' },
    { label: '총 오퍼', value: stats.offers, color: C.orange, icon: '📝' },
  ];

  return (
    <div style={{ padding: '24px 16px', maxWidth: 800, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 24 }}>
        관리자 대시보드
      </h1>

      {loading ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>로딩 중...</div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 24 }}>
            {cards.map(c => (
              <div key={c.label} style={{
                background: C.card, border: `1px solid ${C.border}`, borderRadius: 16,
                padding: '20px 16px', textAlign: 'center',
              }}>
                <div style={{ fontSize: 28, marginBottom: 6 }}>{c.icon}</div>
                <div style={{ fontSize: 28, fontWeight: 800, color: c.color }}>{c.value}</div>
                <div style={{ fontSize: 13, color: C.textSec, marginTop: 4 }}>{c.label}</div>
              </div>
            ))}
          </div>

          {stats.pendingSellers > 0 && (
            <button
              onClick={() => navigate('/admin/sellers')}
              style={{
                width: '100%', padding: '16px', borderRadius: 14,
                background: 'rgba(255,145,0,0.1)', border: `1px solid rgba(255,145,0,0.3)`,
                color: C.orange, fontSize: 15, fontWeight: 700, cursor: 'pointer',
                textAlign: 'center',
              }}
            >
              승인 대기 판매자: {stats.pendingSellers}명 →
            </button>
          )}
        </>
      )}
    </div>
  );
}
