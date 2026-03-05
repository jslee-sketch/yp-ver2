import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

function fmtP(n: number) { return '₩' + (n ?? 0).toLocaleString('ko-KR'); }
function fmtDate(s?: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

interface OfferItem {
  offer_id: number;
  deal_id: number;
  seller_id: number;
  seller_name?: string;
  price: number;
  total_available_qty: number;
  reserved_qty: number;
  sold_qty: number;
  is_active: boolean;
  is_confirmed: boolean;
  created_at: string;
}

interface SellerWithOffers {
  seller_id: number;
  name?: string;
  business_name?: string;
  offers?: OfferItem[];
}

type FilterKey = '전체' | '활성' | '확정' | '비활성';

export default function ActuatorOffersPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [allOffers, setAllOffers] = useState<OfferItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterKey>('전체');

  useEffect(() => {
    if (!user) return;
    const actuatorId = user.id;
    (async () => {
      try {
        // Use /actuators/me/sellers which returns sellers with nested offers
        const res = await apiClient.get('/actuators/me/sellers', { params: { actuator_id: actuatorId } });
        const data: SellerWithOffers[] = Array.isArray(res.data) ? res.data : [];
        const offers: OfferItem[] = [];
        for (const s of data) {
          if (Array.isArray(s.offers)) {
            for (const o of s.offers) {
              offers.push({
                ...o,
                seller_id: s.seller_id,
                seller_name: s.business_name || s.name || `#${s.seller_id}`,
              } as OfferItem);
            }
          }
        }
        setAllOffers(offers);
      } catch (err) {
        console.error('오퍼 현황 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  const filtered = filter === '전체' ? allOffers : allOffers.filter(o => {
    if (filter === '활성') return o.is_active && !o.is_confirmed;
    if (filter === '확정') return o.is_confirmed;
    if (filter === '비활성') return !o.is_active;
    return true;
  });

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>오퍼 현황</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 요약 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>전체</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.text }}>{allOffers.length}</div>
          </div>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>활성</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#00b0ff' }}>{allOffers.filter(o => o.is_active).length}</div>
          </div>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>확정</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.green }}>{allOffers.filter(o => o.is_confirmed).length}</div>
          </div>
        </div>

        {/* 필터 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {(['전체', '활성', '확정', '비활성'] as FilterKey[]).map(s => (
            <button key={s} onClick={() => setFilter(s)} style={{
              padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: filter === s ? `${C.green}22` : C.bgEl,
              border: `1px solid ${filter === s ? C.green : C.border}`,
              color: filter === s ? C.green : C.textSec,
              fontWeight: filter === s ? 700 : 400,
            }}>{s}</button>
          ))}
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>{filtered.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>📋</div>
            <div style={{ fontSize: 13 }}>오퍼가 없어요</div>
          </div>
        ) : filtered.map(o => {
          const statusColor = o.is_confirmed ? C.green : o.is_active ? '#00b0ff' : '#757575';
          const statusLabel = o.is_confirmed ? '확정' : o.is_active ? '대기중' : '만료';
          return (
            <div key={o.offer_id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${statusColor}`,
              borderRadius: 14, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <div>
                  <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>딜 #{o.deal_id}</span>
                  <span style={{ fontSize: 11, color: C.textDim, marginLeft: 8 }}>{o.seller_name}</span>
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                  background: `${statusColor}22`, color: statusColor,
                }}>{statusLabel}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 6 }}>
                <div><div style={{ fontSize: 10, color: C.textDim }}>제안가</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{fmtP(o.price)}</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>수량</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{(o.sold_qty ?? 0) + (o.reserved_qty ?? 0)}/{o.total_available_qty}</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>판매</div><div style={{ fontSize: 12, fontWeight: 700, color: C.orange }}>{o.sold_qty ?? 0}개</div></div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: 10, color: C.textDim }}>{fmtDate(o.created_at)}</span>
                <button onClick={() => navigate(`/deal/${o.deal_id}`)}
                  style={{ fontSize: 11, fontWeight: 700, color: C.green, cursor: 'pointer', background: 'none', border: 'none', padding: 0 }}>
                  딜 보기 ›
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
