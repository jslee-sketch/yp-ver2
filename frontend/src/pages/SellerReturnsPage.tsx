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
function fmtId(prefix: string, id: number) { return `${prefix}-${String(id).padStart(6, '0')}`; }

interface ReturnItem {
  id: number;
  deal_id: number;
  offer_id: number;
  buyer_id: number;
  qty: number;
  amount_total: number;
  refunded_qty: number;
  refunded_amount_total: number;
  refund_type?: string;
  is_disputed?: boolean;
  created_at: string;
  deal?: { product_name?: string };
  buyer?: { nickname?: string; name?: string };
}

type FilterKey = '전체' | '반품요청' | '교환요청' | '처리완료';

export default function SellerReturnsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const sellerId = user?.seller?.id ?? user?.id ?? 0;
  const [items, setItems] = useState<ReturnItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterKey>('전체');

  useEffect(() => {
    if (!sellerId) return;
    (async () => {
      try {
        const res = await apiClient.get(`/reservations/seller/${sellerId}`);
        const all: ReturnItem[] = Array.isArray(res.data) ? res.data : [];
        const returnItems = all.filter(r =>
          r.refund_type === 'return' || r.refund_type === 'exchange' ||
          ((r.refunded_qty ?? 0) > 0 && r.refund_type !== 'refund')
        );
        setItems(returnItems);
      } catch (err) {
        console.error('반품/교환 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [sellerId]);

  const getStatus = (r: ReturnItem): string => {
    if (r.refund_type === 'exchange') return '교환요청';
    if (r.refund_type === 'return') return '반품요청';
    if ((r.refunded_qty ?? 0) > 0) return '처리완료';
    return '반품요청';
  };

  const filtered = filter === '전체' ? items : items.filter(r => getStatus(r) === filter);

  const statusColor: Record<string, string> = {
    '반품요청': '#ff9100',
    '교환요청': '#00b0ff',
    '처리완료': '#78909c',
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>반품/교환</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0', maxWidth: 1200, margin: '0 auto' }}>
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {(['전체', '반품요청', '교환요청', '처리완료'] as FilterKey[]).map(s => (
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
            <div style={{ fontSize: 40, marginBottom: 8 }}>↩️</div>
            <div style={{ fontSize: 13 }}>반품/교환 내역이 없어요</div>
          </div>
        ) : filtered.map(r => {
          const st = getStatus(r);
          const clr = statusColor[st] ?? C.textDim;
          return (
            <div key={r.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${clr}`,
              borderRadius: 14, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 12, color: C.textSec }}>
                  {fmtId('R', r.id)} · 딜 #{r.deal_id}
                </span>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                  background: `${clr}22`, color: clr,
                }}>{st}</span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 4 }}>
                {r.deal?.product_name ?? `예약 ${fmtId('R', r.id)}`}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 6 }}>
                <div><div style={{ fontSize: 10, color: C.textDim }}>수량</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{r.qty}개</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>결제액</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{fmtP(r.amount_total)}</div></div>
                <div><div style={{ fontSize: 10, color: C.textDim }}>환불액</div><div style={{ fontSize: 12, fontWeight: 700, color: '#ff5252' }}>{fmtP(r.refunded_amount_total ?? 0)}</div></div>
              </div>
              <div style={{ fontSize: 10, color: C.textDim }}>
                구매자 #{r.buyer_id}{r.buyer?.nickname ? ` (${r.buyer.nickname})` : ''} · {fmtDate(r.created_at)}
              </div>
              {r.is_disputed && (
                <div style={{ fontSize: 11, color: '#ff5252', marginTop: 6 }}>분쟁 접수됨</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
