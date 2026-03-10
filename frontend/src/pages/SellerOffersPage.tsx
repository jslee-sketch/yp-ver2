import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { trackBehavior } from '../utils/behaviorTracker';
import { useAuth } from '../contexts/AuthContext';
import { useApiData } from '../api/hooks';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import type { OfferResponse } from '../api/types';
import { showToast } from '../components/common/Toast';
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

function getOfferStatus(o: OfferResponse): string {
  if (o.is_confirmed) return '확정';
  if (o.is_active) return '대기중';
  // Check if deadline passed
  if (o.deadline_at && new Date(o.deadline_at) < new Date()) return '만료';
  return '만료';
}

const STATUS_COLOR: Record<string, string> = {
  '대기중': '#00b0ff',
  '확정': '#00e676',
  '만료': '#757575',
};

type FilterKey = '전체' | '대기중' | '확정' | '만료';

export default function SellerOffersPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [filter, setFilter] = useState<FilterKey>('전체');

  // Edit modal
  const [editTarget, setEditTarget] = useState<OfferResponse | null>(null);
  const [editPrice, setEditPrice] = useState('');
  const [editShipping, setEditShipping] = useState('');
  const [editDeliveryDays, setEditDeliveryDays] = useState('');
  const [editSaving, setEditSaving] = useState(false);

  const sellerId = user?.seller?.id ?? user?.id;
  const { data: offers, loading, error, refetch } = useApiData<OfferResponse[]>(async () => {
    if (!sellerId) return [];
    try {
      const res = await apiClient.get(API.OFFERS.LIST, { params: { seller_id: sellerId, limit: 100 } });
      const raw = res.data;
      // API 응답이 배열이 아닐 수 있음 (paginated object 등)
      if (Array.isArray(raw)) return raw as OfferResponse[];
      if (raw && typeof raw === 'object') {
        const arr = (raw as Record<string, unknown>).items
          ?? (raw as Record<string, unknown>).results
          ?? (raw as Record<string, unknown>).offers;
        if (Array.isArray(arr)) return arr as OfferResponse[];
      }
      return [];
    } catch { return []; }
  }, [sellerId]);

  const items = Array.isArray(offers) ? offers : [];
  const filtered = filter === '전체' ? items : items.filter(o => getOfferStatus(o) === filter);

  const activeCount = items.filter(o => o.is_active && !o.is_confirmed).length;
  const confirmedCount = items.filter(o => o.is_confirmed).length;
  const expiredCount = items.filter(o => !o.is_active && !o.is_confirmed).length;

  const openEdit = (o: OfferResponse) => {
    setEditTarget(o);
    setEditPrice(String(o.price));
    setEditShipping(String(o.shipping_fee_per_reservation ?? 0));
    setEditDeliveryDays(String(o.delivery_days ?? ''));
  };

  const handleEditSave = async () => {
    if (!editTarget) return;
    setEditSaving(true);
    try {
      await apiClient.patch(API.OFFERS.UPDATE(editTarget.id), {
        price: Number(editPrice),
        shipping_fee_per_reservation: Number(editShipping),
        delivery_days: editDeliveryDays ? Number(editDeliveryDays) : null,
      });
      trackBehavior('SELLER_EDIT_OFFER', {
        target_type: 'offer',
        target_id: editTarget.id,
        meta: { old_price: editTarget.price, new_price: Number(editPrice), direction: Number(editPrice) > editTarget.price ? 'up' : 'down' },
      });
      showToast('오퍼 수정 완료', 'success');
      setEditTarget(null);
      refetch();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      showToast(typeof e.response?.data?.detail === 'string' ? e.response.data.detail as string : '수정 실패 — 수정 가능 기간이 지났을 수 있습니다', 'error');
    }
    setEditSaving(false);
  };

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
        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>대기중</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: '#00b0ff' }}>{activeCount}</div>
          </div>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>확정</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.green }}>{confirmedCount}</div>
          </div>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>만료</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.textSec }}>{expiredCount}</div>
          </div>
        </div>

        {/* 필터 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {(['전체', '대기중', '확정', '만료'] as FilterKey[]).map(s => (
            <button key={s} onClick={() => setFilter(s)} style={{
              padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: filter === s ? `${C.green}22` : C.bgEl,
              border: `1px solid ${filter === s ? C.green : C.border}`,
              color: filter === s ? C.green : C.textSec,
              fontWeight: filter === s ? 700 : 400,
            }}>{s}</button>
          ))}
        </div>

        {loading && <LoadingSkeleton variant="cards" count={3} />}
        {!loading && error && <ErrorMessage message={error} onRetry={refetch} />}

        {!loading && !error && (
          <>
            <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>{filtered.length}건</div>
            {filtered.length === 0 && <EmptyState icon="📋" message="해당 오퍼가 없어요" />}

            {filtered.map(offer => {
              const status = getOfferStatus(offer);
              const clr = STATUS_COLOR[status] ?? '#757575';
              const canEdit = offer.is_active && !offer.is_confirmed;
              return (
                <div key={offer.id} style={{
                  background: C.bgCard, border: `1px solid ${C.border}`,
                  borderLeft: `3px solid ${clr}`,
                  borderRadius: 14, padding: 14, marginBottom: 8,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>
                      <span style={{ color: C.green, cursor: 'pointer', textDecoration: 'underline' }} onClick={() => navigate(`/deal/${offer.deal_id}`)}>O-{String(offer.id).padStart(6,'0')}</span>
                      {' · '}
                      <span style={{ color: '#00b0ff', cursor: 'pointer', textDecoration: 'underline' }} onClick={() => navigate(`/deal/${offer.deal_id}`)}>D-{String(offer.deal_id).padStart(6,'0')}</span>
                    </span>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                      background: `${clr}22`, color: clr,
                    }}>{status}</span>
                  </div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 6 }}>
                    {(offer as Record<string, unknown>).product_name
                      ?? ((offer as Record<string, unknown>).deal as Record<string, unknown> | undefined)?.product_name
                      ?? `딜 #${offer.deal_id}`}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 6 }}>
                    <div><div style={{ fontSize: 10, color: C.textDim }}>제안가</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{fmtP(offer.price)}</div></div>
                    <div><div style={{ fontSize: 10, color: C.textDim }}>배송비</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{offer.shipping_fee_per_reservation ? fmtP(offer.shipping_fee_per_reservation) : '무료'}</div></div>
                    <div><div style={{ fontSize: 10, color: C.textDim }}>수량</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{offer.sold_qty + offer.reserved_qty}/{offer.total_available_qty}</div></div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 10, color: C.textDim }}>{fmtDate(offer.created_at)}</span>
                    <div style={{ display: 'flex', gap: 8 }}>
                      {canEdit && (
                        <button onClick={() => openEdit(offer)}
                          style={{ fontSize: 11, fontWeight: 700, color: C.orange, cursor: 'pointer', background: 'none', border: 'none', padding: 0 }}>
                          수정
                        </button>
                      )}
                      <button onClick={() => navigate(`/deal/${offer.deal_id}`)}
                        style={{ fontSize: 11, fontWeight: 700, color: C.green, cursor: 'pointer', background: 'none', border: 'none', padding: 0 }}>
                        상세 ›
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>

      {/* 수정 모달 */}
      {editTarget && (
        <>
          <div onClick={() => setEditTarget(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000 }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: '92%', maxWidth: 400, background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 20, padding: '24px 20px', zIndex: 3001 }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 4 }}>오퍼 수정</div>
            <div style={{ fontSize: 12, color: C.textSec, marginBottom: 16 }}>오퍼 #{editTarget.id} · 딜 #{editTarget.deal_id}</div>

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>제안가 (원)</div>
            <input value={editPrice} onChange={e => setEditPrice(e.target.value)} type="number"
              style={{ width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: 10, fontSize: 13, background: C.bgEl, border: `1px solid ${C.border}`, color: C.text, marginBottom: 12 }} />

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>배송비 (원)</div>
            <input value={editShipping} onChange={e => setEditShipping(e.target.value)} type="number"
              style={{ width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: 10, fontSize: 13, background: C.bgEl, border: `1px solid ${C.border}`, color: C.text, marginBottom: 12 }} />

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>리드타임 (일)</div>
            <input value={editDeliveryDays} onChange={e => setEditDeliveryDays(e.target.value)} type="number" placeholder="선택"
              style={{ width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: 10, fontSize: 13, background: C.bgEl, border: `1px solid ${C.border}`, color: C.text, marginBottom: 16 }} />

            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setEditTarget(null)} style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>취소</button>
              <button disabled={editSaving} onClick={() => void handleEditSave()}
                style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: editSaving ? `${C.green}55` : C.green, border: 'none', color: '#0a0a0f', cursor: editSaving ? 'not-allowed' : 'pointer' }}>
                {editSaving ? '저장 중...' : '저장'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
