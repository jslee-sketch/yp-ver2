import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { trackBehavior } from '../utils/behaviorTracker';
import { useAuth } from '../contexts/AuthContext';
import { fetchMySettlements } from '../api/settlementApi';
import { useApiData } from '../api/hooks';
import type { Settlement } from '../api/types';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

const STATUS_META: Record<string, { label: string; color: string }> = {
  PENDING:  { label: '대기',     color: '#78909c' },
  HOLD:     { label: '보류',     color: '#ff9100' },
  READY:    { label: '정산예정', color: '#00b0ff' },
  APPROVED: { label: '승인',     color: '#00e676' },
  PAID:     { label: '정산완료', color: '#78909c' },
};

function fmtP(n: number) { return '₩' + (n ?? 0).toLocaleString('ko-KR'); }
function fmtDate(s?: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

// Normalize field names — backend may send either convention
function paid(s: Settlement) { return s.buyer_paid_amount ?? s.gross_amount ?? 0; }
function pgFee(s: Settlement) { return s.pg_fee_amount ?? 0; }
function platFee(s: Settlement) { return s.platform_commission_amount ?? s.platform_fee ?? 0; }
function payout(s: Settlement) { return s.seller_payout_amount ?? s.net_amount ?? 0; }

type FilterKey = '전체' | 'HOLD' | 'READY' | 'PAID';

export default function SellerSettlementsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const sellerId = user?.seller?.id ?? user?.id ?? 0;

  const [filter, setFilter] = useState<FilterKey>('전체');

  const { data: settlements, loading, error } = useApiData<Settlement[]>(
    () => fetchMySettlements(sellerId),
    [sellerId],
  );

  const items = settlements ?? [];

  // ── 행동 수집: SELLER_VIEW_SETTLEMENT ──
  useEffect(() => {
    trackBehavior('SELLER_VIEW_SETTLEMENT', { meta: { page: 'settlements' } });
  }, []);

  const filtered = filter === '전체' ? items : items.filter(s => {
    if (filter === 'HOLD') return s.status === 'HOLD' || s.status === 'PENDING';
    if (filter === 'READY') return s.status === 'READY' || s.status === 'APPROVED';
    return s.status === filter;
  });

  // Totals
  const totPaid = items.reduce((a, s) => a + paid(s), 0);
  const totPg = items.reduce((a, s) => a + pgFee(s), 0);
  const totPlat = items.reduce((a, s) => a + platFee(s), 0);
  const totPayout = items.filter(s => s.status === 'PAID').reduce((a, s) => a + payout(s), 0);
  const totPending = items.filter(s => s.status !== 'PAID').reduce((a, s) => a + payout(s), 0);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>정산 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 합계 카드 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`, borderTop: `3px solid ${C.green}`,
          borderRadius: 16, padding: 16, marginBottom: 14,
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 10 }}>
            <div style={{ textAlign: 'center', padding: 10, background: `${C.green}11`, borderRadius: 10 }}>
              <div style={{ fontSize: 10, color: C.textDim }}>정산완료</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: C.green }}>{fmtP(totPayout)}</div>
            </div>
            <div style={{ textAlign: 'center', padding: 10, background: `${C.orange}11`, borderRadius: 10 }}>
              <div style={{ fontSize: 10, color: C.textDim }}>대기중</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: C.orange }}>{fmtP(totPending)}</div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: C.textDim }}>총 결제액</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{fmtP(totPaid)}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: C.textDim }}>PG수수료</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#ff5252' }}>{fmtP(totPg)}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: C.textDim }}>역핑수수료</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.orange }}>{fmtP(totPlat)}</div>
            </div>
          </div>
        </div>

        {/* 필터 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {(['전체', 'HOLD', 'READY', 'PAID'] as FilterKey[]).map(s => (
            <button key={s} onClick={() => setFilter(s)} style={{
              padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: filter === s ? `${C.green}22` : C.bgEl,
              border: `1px solid ${filter === s ? C.green : C.border}`,
              color: filter === s ? C.green : C.textSec,
              fontWeight: filter === s ? 700 : 400,
            }}>{s === '전체' ? s : (STATUS_META[s]?.label ?? s)}</button>
          ))}
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>{filtered.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : error ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#ff5252' }}>{error}</div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>💰</div>
            <div style={{ fontSize: 13 }}>정산 내역이 없어요</div>
          </div>
        ) : filtered.map(s => {
          const meta = STATUS_META[s.status] ?? STATUS_META.HOLD;
          return (
            <div key={s.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${meta.color}`,
              borderRadius: 14, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: C.textSec }}>
                  정산 #{s.id}{s.deal_id ? ` · 딜 #${s.deal_id}` : ''}{s.offer_id ? ` · 오퍼 #${s.offer_id}` : ''}
                </span>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                  background: `${meta.color}22`, color: meta.color,
                }}>{meta.label}</span>
              </div>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 6 }}>
                예약 #{s.reservation_id} · {fmtDate(s.created_at)}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 6 }}>
                <div><div style={{ fontSize: 10, color: C.textDim }}>결제액</div><div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{fmtP(paid(s))}</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>정산액</div><div style={{ fontSize: 13, fontWeight: 700, color: C.green }}>{fmtP(payout(s))}</div></div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <div><div style={{ fontSize: 10, color: C.textDim }}>PG수수료</div><div style={{ fontSize: 11, fontWeight: 600, color: '#ff5252' }}>{fmtP(pgFee(s))}</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>역핑수수료</div><div style={{ fontSize: 11, fontWeight: 600, color: C.orange }}>{fmtP(platFee(s))}</div></div>
              </div>
              {s.paid_at && (
                <div style={{ fontSize: 10, color: C.green, marginTop: 6 }}>지급일: {fmtDate(s.paid_at)}</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
