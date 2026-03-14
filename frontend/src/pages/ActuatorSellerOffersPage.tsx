import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

function fmtP(n: number) { return (n ?? 0).toLocaleString('ko-KR') + '원'; }
function fmtDate(s?: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

interface SellerInfo {
  id: number;
  name?: string;
  business_name?: string;
  verified_at?: string;
}

interface OfferItem {
  id: number;
  deal_id: number;
  price: number;
  shipping_cost: number;
  total_available_qty: number;
  reserved_qty: number;
  sold_qty: number;
  is_active: boolean;
  is_confirmed: boolean;
  created_at: string;
  deadline_at?: string;
  deal?: { product_name?: string; status?: string };
}

type FilterKey = '전체' | '활성' | '확정' | '비활성';

export default function ActuatorSellerOffersPage() {
  const navigate = useNavigate();
  const { sellerId } = useParams<{ sellerId: string }>();
  const [seller, setSeller] = useState<SellerInfo | null>(null);
  const [offers, setOffers] = useState<OfferItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterKey>('전체');

  useEffect(() => {
    if (!sellerId) return;
    (async () => {
      try {
        const [sellerRes, offersRes] = await Promise.all([
          apiClient.get(API.SELLERS.DETAIL(Number(sellerId))).catch(() => null),
          apiClient.get(API.OFFERS_V36.LIST, { params: { seller_id: sellerId } }),
        ]);
        if (sellerRes?.data) setSeller(sellerRes.data);
        const data = offersRes.data;
        setOffers(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error('오퍼 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [sellerId]);

  const filtered = filter === '전체' ? offers : offers.filter(o => {
    if (filter === '활성') return o.is_active && !o.is_confirmed;
    if (filter === '확정') return o.is_confirmed;
    if (filter === '비활성') return !o.is_active;
    return true;
  });

  const activeCount = offers.filter(o => o.is_active).length;
  const confirmedCount = offers.filter(o => o.is_confirmed).length;

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>판매자 오퍼 현황</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 판매자 정보 헤더 */}
        {seller && (
          <div style={{
            background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
            padding: 14, marginBottom: 14,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 15, fontWeight: 800, color: C.text }}>
                {seller.business_name || seller.name || `판매자 #${seller.id}`}
              </span>
              <span style={{
                fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                background: seller.verified_at ? `${C.green}22` : `${C.orange}22`,
                color: seller.verified_at ? C.green : C.orange,
              }}>
                {seller.verified_at ? '승인완료' : '승인대기'}
              </span>
            </div>
            {seller.name && seller.business_name && (
              <div style={{ fontSize: 11, color: C.textSec, marginBottom: 6 }}>{seller.name}</div>
            )}
            <div style={{ fontSize: 12, color: C.textDim }}>
              총 오퍼: {offers.length}건 | 낙찰: {confirmedCount}건 | 활성: {activeCount}건
            </div>
          </div>
        )}

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
            <div key={o.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${statusColor}`,
              borderRadius: 14, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
                  {o.deal?.product_name ?? `딜 #${o.deal_id}`}
                </span>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                  background: `${statusColor}22`, color: statusColor,
                }}>{statusLabel}</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 6 }}>
                <div><div style={{ fontSize: 10, color: C.textDim }}>제안가</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{fmtP(o.price)}</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>배송비</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{o.shipping_cost ? fmtP(o.shipping_cost) : '무료'}</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>수량</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{o.sold_qty + o.reserved_qty}/{o.total_available_qty}</div></div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
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
