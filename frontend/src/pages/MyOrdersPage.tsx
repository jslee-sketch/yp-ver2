import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { fetchMyReservations, cancelReservation, confirmArrival, payReservation } from '../api/reservationApi';
import { showToast } from '../components/common/Toast';

// ── 타입 & Mock ───────────────────────────────────────

type ActivityStatus =
  | 'RECRUITING' | 'OFFER_PHASE' | 'PENDING_PAY'
  | 'PAID' | 'SHIPPED' | 'DELIVERED' | 'CANCELLED';

interface MyDealActivity {
  id: number;
  product_name: string;
  seller_name?: string;
  price?: number;
  qty: number;
  role: 'creator' | 'participant';
  status: ActivityStatus;
  created_at: string;
  tracking_number?: string;
}

// Dynamic date helpers
const _today = () => new Date().toISOString().split('T')[0];
const _monthsAgo = (n: number) => {
  const d = new Date();
  d.setMonth(d.getMonth() - n);
  return d.toISOString().split('T')[0];
};

const STATUS_MAP: Record<ActivityStatus, { color: string; label: string; emoji: string }> = {
  RECRUITING:  { color: '#ffd600', label: '모집중',  emoji: '🟡' },
  OFFER_PHASE: { color: '#ff9100', label: '오퍼경쟁', emoji: '🟠' },
  PENDING_PAY: { color: '#e040fb', label: '결제대기', emoji: '🟣' },
  PAID:        { color: '#448aff', label: '결제완료', emoji: '🔵' },
  SHIPPED:     { color: '#ff6d00', label: '배송중',  emoji: '📦' },
  DELIVERED:   { color: '#00e676', label: '완료',    emoji: '🟢' },
  CANCELLED:   { color: '#757575', label: '취소',    emoji: '⚫' },
};

const STATUS_FILTER_MAP: Record<string, ActivityStatus[]> = {
  '전체':   ['RECRUITING', 'OFFER_PHASE', 'PENDING_PAY', 'PAID', 'SHIPPED', 'DELIVERED', 'CANCELLED'],
  '모집중':  ['RECRUITING'],
  '오퍼경쟁': ['OFFER_PHASE'],
  '결제대기': ['PENDING_PAY'],
  '결제완료': ['PAID'],
  '배송중':  ['SHIPPED'],
  '완료':   ['DELIVERED', 'CANCELLED'],
};
const STATUS_FILTERS = ['전체', '모집중', '오퍼경쟁', '결제대기', '결제완료', '배송중', '완료'];
const ITEMS_PER_PAGE = 10;

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

function fmtDate(s: string) { return s.replace(/-/g, '.'); }
function fmtPrice(n: number) { return '₩' + n.toLocaleString('ko-KR'); }

function mapReservationStatus(status: string, r: Record<string, unknown>): ActivityStatus {
  if (status === 'CANCELLED' || status === 'EXPIRED') return 'CANCELLED';
  if (status === 'PENDING')  return 'PENDING_PAY';
  if (status === 'PAID') {
    if (r.shipped_at)   return 'SHIPPED';
    if (r.delivered_at) return 'DELIVERED';
    return 'PAID';
  }
  if (status === 'SHIPPED')   return 'SHIPPED';
  if (status === 'DELIVERED') return 'DELIVERED';
  if (status === 'RECRUITING')  return 'RECRUITING';
  if (status === 'OFFER_PHASE') return 'OFFER_PHASE';
  return 'PAID';
}

export default function MyOrdersPage() {
  const navigate = useNavigate();
  const { user }  = useAuth();

  const [activities, setActivities] = useState<MyDealActivity[]>([]);
  const [loading, setLoading]             = useState(true);
  const [statusFilter, setStatusFilter] = useState('전체');
  const [dateFrom, setDateFrom]         = useState(_monthsAgo(3));
  const [dateTo, setDateTo]             = useState(_today());
  const [keyword, setKeyword]           = useState('');
  const [applied, setApplied]           = useState({ status: '전체', from: _monthsAgo(3), to: _today(), kw: '' });
  const [page, setPage]                 = useState(1);

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    const load = async () => {
      setLoading(true);
      try {
        const apiData = await fetchMyReservations();
        if (apiData && Array.isArray(apiData)) {
          const mapped: MyDealActivity[] = (apiData as Record<string, unknown>[]).map(r => {
            const deal   = r.deal   as Record<string, unknown> | undefined;
            const offer  = r.offer  as Record<string, unknown> | undefined;
            const seller = offer?.seller as Record<string, unknown> | undefined;
            return {
              id:             typeof r.id === 'number' ? r.id : 0,
              product_name:   String(deal?.product_name ?? offer?.comment ?? `예약 #${r.id}`),
              seller_name:    typeof seller?.nickname === 'string' ? seller.nickname
                            : typeof seller?.business_name === 'string' ? seller.business_name
                            : undefined,
              price:          typeof r.amount_total === 'number' ? r.amount_total
                            : typeof r.amount_goods === 'number' ? r.amount_goods
                            : undefined,
              qty:            typeof r.qty === 'number' ? r.qty : 1,
              role:           deal?.creator_id === user.id ? 'creator' : 'participant',
              status:         mapReservationStatus(String(r.status ?? ''), r),
              created_at:     typeof r.created_at === 'string' ? r.created_at.split('T')[0] : '',
              tracking_number: typeof r.tracking_number === 'string' ? r.tracking_number : undefined,
            };
          });
          setActivities(mapped);
        }
      } catch (err) {
        console.error('예약 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [user]);

  const updateStatus = (id: number, status: ActivityStatus) =>
    setActivities(prev => prev.map(a => a.id === id ? { ...a, status } : a));

  const handleConfirmArrival = async (id: number) => {
    if (!window.confirm('상품을 받으셨나요?')) return;
    try {
      const result = await confirmArrival(id);
      if (result) {
        updateStatus(id, 'DELIVERED');
        showToast('수령 확인 완료!', 'success');
      } else {
        updateStatus(id, 'DELIVERED');
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e.response?.data?.detail;
      alert(typeof detail === 'string' ? detail : '수령 확인에 실패했어요');
    }
  };

  const handlePay = async (id: number) => {
    if (!window.confirm('결제를 진행하시겠어요?\n(테스트 환경: 즉시 결제 처리됩니다)')) return;
    try {
      const result = await payReservation(id);
      if (result) {
        updateStatus(id, 'PAID');
        showToast('결제가 완료되었어요!', 'success');
      } else {
        // Mock 모드: API 비활성화 시 UI만 변경
        updateStatus(id, 'PAID');
        showToast('결제가 완료되었어요! (Mock)', 'success');
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e.response?.data?.detail;
      alert(typeof detail === 'string' ? detail : '결제 처리에 실패했어요');
    }
  };

  const handleCancel = async (id: number) => {
    if (!window.confirm('정말 취소하시겠어요?')) return;
    try {
      const result = await cancelReservation(id);
      if (result) {
        updateStatus(id, 'CANCELLED');
        showToast('취소되었어요', 'info');
      } else {
        updateStatus(id, 'CANCELLED');
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e.response?.data?.detail;
      alert(typeof detail === 'string' ? detail : '취소에 실패했어요');
    }
  };

  const filtered = (() => {
    let items = activities;
    if (applied.status !== '전체') {
      const allow = STATUS_FILTER_MAP[applied.status] ?? [];
      items = items.filter(i => allow.includes(i.status));
    }
    items = items.filter(i => i.created_at >= applied.from && i.created_at <= applied.to);
    if (applied.kw.trim()) {
      const kw = applied.kw.toLowerCase();
      items = items.filter(i => i.product_name.toLowerCase().includes(kw) || (i.seller_name ?? '').toLowerCase().includes(kw));
    }
    return items;
  })();

  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
  const paged      = filtered.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE);

  const doSearch = () => { setApplied({ status: statusFilter, from: dateFrom, to: dateTo, kw: keyword }); setPage(1); };
  const doReset  = () => {
    setStatusFilter('전체'); setDateFrom(_monthsAgo(3)); setDateTo(_today()); setKeyword('');
    setApplied({ status: '전체', from: _monthsAgo(3), to: _today(), kw: '' }); setPage(1);
  };

  const inputSt: React.CSSProperties = {
    padding: '7px 10px', borderRadius: 8, fontSize: 13,
    background: C.bgCard, border: `1px solid ${C.border}`,
    color: C.text, colorScheme: 'dark' as React.CSSProperties['colorScheme'],
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>참여/결제/배송</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 필터 */}
        <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14, padding: '14px 16px', marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: C.textDim, marginBottom: 8 }}>진행현황</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
            {STATUS_FILTERS.map(s => (
              <button key={s} onClick={() => setStatusFilter(s)} style={{
                padding: '5px 10px', borderRadius: 20, fontSize: 11, cursor: 'pointer',
                background: statusFilter === s ? `${C.green}22` : C.bgEl,
                border: `1px solid ${statusFilter === s ? C.green : C.border}`,
                color: statusFilter === s ? C.green : C.textSec,
                fontWeight: statusFilter === s ? 700 : 400,
              }}>{s}</button>
            ))}
          </div>

          <div style={{ fontSize: 11, color: C.textDim, marginBottom: 6 }}>기간</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} style={inputSt} />
            <span style={{ color: C.textDim, fontSize: 12 }}>~</span>
            <input type="date" value={dateTo}   onChange={e => setDateTo(e.target.value)}   style={inputSt} />
          </div>

          <div style={{ fontSize: 11, color: C.textDim, marginBottom: 6 }}>키워드</div>
          <input
            type="text" value={keyword}
            onChange={e => setKeyword(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') doSearch(); }}
            placeholder="🔍 상품명으로 검색..."
            style={{ ...inputSt, width: '100%', boxSizing: 'border-box' as const, marginBottom: 12 }}
          />
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={doSearch} style={{ flex: 1, padding: '9px 0', borderRadius: 10, fontSize: 13, fontWeight: 700, background: `${C.green}22`, border: `1px solid ${C.green}66`, color: C.green, cursor: 'pointer' }}>검색</button>
            <button onClick={doReset}  style={{ flex: 1, padding: '9px 0', borderRadius: 10, fontSize: 13, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>초기화</button>
          </div>
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>결과 {filtered.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim, fontSize: 13 }}>불러오는 중...</div>
        ) : paged.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim, fontSize: 13 }}>조건에 맞는 내역이 없어요</div>
        ) : paged.map(item => {
          const st = STATUS_MAP[item.status];
          return (
            <div key={item.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${st.color}`,
              borderRadius: 14, padding: '13px 14px', marginBottom: 8,
              opacity: item.status === 'CANCELLED' ? 0.6 : 1,
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  {/* 상품명 + 역할 배지 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4, flexWrap: 'wrap' }}>
                    <span style={{
                      fontSize: 13, fontWeight: 700, color: C.text,
                      textDecoration: item.status === 'CANCELLED' ? 'line-through' : 'none',
                    }}>
                      📦 {item.product_name}
                    </span>
                    {item.role === 'creator' && (
                      <span style={{ padding: '2px 7px', borderRadius: 6, background: 'rgba(255,152,0,0.2)', color: '#ff9800', fontSize: 10, fontWeight: 700, flexShrink: 0 }}>
                        방장
                      </span>
                    )}
                    {item.role === 'participant' && (
                      <span style={{ padding: '2px 7px', borderRadius: 6, background: 'rgba(0,176,255,0.2)', color: '#00b0ff', fontSize: 10, fontWeight: 700, flexShrink: 0 }}>
                        참여
                      </span>
                    )}
                  </div>

                  {/* 셀러 & 가격 */}
                  {item.seller_name && (
                    <div style={{ fontSize: 11, color: C.textSec, marginBottom: 4 }}>
                      {item.seller_name}
                      {item.price && ` · ${fmtPrice(item.price)}`}
                      {` · ${item.qty}개`}
                    </div>
                  )}
                  {!item.seller_name && (
                    <div style={{ fontSize: 11, color: C.textSec, marginBottom: 4 }}>{item.qty}개 · 셀러 미확정</div>
                  )}

                  {/* 상태 배지 */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 8, background: `${st.color}22`, color: st.color, border: `1px solid ${st.color}44` }}>
                      {st.emoji} {st.label}
                    </span>
                    {item.tracking_number && (
                      <span style={{ fontSize: 10, color: 'var(--accent-orange)' }}>🚚 {item.tracking_number}</span>
                    )}
                  </div>
                </div>

                <div style={{ fontSize: 10, color: C.textDim, flexShrink: 0 }}>{fmtDate(item.created_at)}</div>
              </div>

              {/* 결제대기 안내 */}
              {item.status === 'PENDING_PAY' && (
                <div style={{ marginTop: 8, padding: '8px 10px', background: 'rgba(224,64,251,0.1)', border: '1px solid rgba(224,64,251,0.3)', borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: '#e040fb', fontWeight: 700 }}>⚠️ 결제 마감 5분 전! 지금 바로 결제하세요</div>
                  <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                    <button onClick={() => void handlePay(item.id)} style={{ flex: 1, padding: '5px 0', borderRadius: 7, fontSize: 11, fontWeight: 700, background: '#e040fb22', border: '1px solid #e040fb66', color: '#e040fb', cursor: 'pointer' }}>
                      💳 결제하기
                    </button>
                    <button onClick={() => void handleCancel(item.id)} style={{ padding: '5px 10px', borderRadius: 7, fontSize: 11, fontWeight: 700, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', color: '#ff5252', cursor: 'pointer' }}>
                      ❌ 취소
                    </button>
                  </div>
                </div>
              )}

              {/* 배송중 — 수령 확인 */}
              {item.status === 'SHIPPED' && (
                <div style={{ marginTop: 8 }}>
                  <button
                    onClick={() => void handleConfirmArrival(item.id)}
                    style={{ padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(0,230,118,0.12)', border: '1px solid rgba(0,230,118,0.35)', color: '#00e676', cursor: 'pointer' }}
                  >📦 수령 확인</button>
                </div>
              )}

              {/* 완료 — 리뷰 쓰기 */}
              {item.status === 'DELIVERED' && (
                <div style={{ marginTop: 8 }}>
                  <button
                    onClick={() => navigate(`/review/write/${item.id}`)}
                    style={{ padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,214,0,0.1)', border: '1px solid rgba(255,214,0,0.35)', color: '#ffd600', cursor: 'pointer' }}
                  >⭐ 리뷰 쓰기</button>
                </div>
              )}

              {/* 모집중/오퍼경쟁 — 참여 취소 */}
              {(item.status === 'RECRUITING' || item.status === 'OFFER_PHASE') && (
                <div style={{ marginTop: 8 }}>
                  <button
                    onClick={() => void handleCancel(item.id)}
                    style={{ padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,82,82,0.08)', border: '1px solid rgba(255,82,82,0.3)', color: '#ff5252', cursor: 'pointer' }}
                  >❌ 참여 취소</button>
                </div>
              )}

              {/* 결제완료 — 환불 정책 안내 + 취소 */}
              {item.status === 'PAID' && (
                <div style={{ marginTop: 8, padding: '8px 10px', background: 'rgba(255,152,0,0.08)', border: '1px solid rgba(255,152,0,0.2)', borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: 'var(--accent-orange)', marginBottom: 6 }}>⚠️ 결제 후 취소는 환불 정책에 따릅니다</div>
                  <button
                    onClick={() => void handleCancel(item.id)}
                    style={{ padding: '5px 12px', borderRadius: 7, fontSize: 11, fontWeight: 700, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', color: '#ff5252', cursor: 'pointer' }}
                  >❌ 취소 신청</button>
                </div>
              )}
            </div>
          );
        })}

        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 20, padding: '20px 0' }}>
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, opacity: page <= 1 ? 0.3 : 1, cursor: page <= 1 ? 'default' : 'pointer' }}>‹ 이전</button>
            <span style={{ fontSize: 13, color: C.textSec }}>{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 600, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, opacity: page >= totalPages ? 0.3 : 1, cursor: page >= totalPages ? 'default' : 'pointer' }}>다음 ›</button>
          </div>
        )}
      </div>
    </div>
  );
}
