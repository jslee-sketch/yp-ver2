import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

/* ── 타입 ── */
interface ReturnItem {
  id: number;
  order_number: string;
  request_type: 'exchange' | 'return' | 'partial_refund';
  reason: string;
  status: string;
  requested_resolution: string;
  detail?: string;
  created_at: string;
  updated_at?: string;
  dispute_id?: number;
}

/* ── 상수 ── */
const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

const STATUS_MAP: Record<string, { label: string; color: string; icon: string }> = {
  PENDING:       { label: '접수 대기', color: '#e040fb', icon: '🟣' },
  IN_REVIEW:     { label: '검토 중', color: '#ff8c42', icon: '🔶' },
  APPROVED:      { label: '승인', color: '#00e676', icon: '✅' },
  REJECTED:      { label: '거절', color: '#ff5252', icon: '❌' },
  COMPLETED:     { label: '처리 완료', color: '#00e676', icon: '✅' },
  DISPUTE_OPEN:  { label: '중재 진행', color: '#a78bfa', icon: '⚖️' },
  CANCELLED:     { label: '취소', color: '#757575', icon: '⚫' },
};

const TYPE_MAP: Record<string, { label: string; icon: string }> = {
  exchange:       { label: '교환', icon: '🔄' },
  return:         { label: '반품', icon: '📦' },
  partial_refund: { label: '부분 환불', icon: '💸' },
};

const TABS = ['처리중', '완료'] as const;
const ACTIVE_STATUSES = ['PENDING', 'IN_REVIEW', 'DISPUTE_OPEN'];
const DONE_STATUSES = ['APPROVED', 'REJECTED', 'COMPLETED', 'CANCELLED'];

function fmtDate(s: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

export default function MyReturnsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [items, setItems] = useState<ReturnItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<typeof TABS[number]>('처리중');

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    (async () => {
      setLoading(true);
      try {
        const res = await apiClient.get('/v3/returns/my', { params: { buyer_id: user.id } });
        const data = Array.isArray(res.data) ? res.data : (res.data?.items ?? []);
        setItems(data as ReturnItem[]);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  const filtered = items.filter(item => {
    if (tab === '처리중') return ACTIVE_STATUSES.includes(item.status);
    return DONE_STATUSES.includes(item.status);
  });

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      {/* Header */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', background: 'none', border: 'none' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>교환/반품 내역</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* Tabs */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              flex: 1, padding: '8px 0', borderRadius: 10, fontSize: 13, fontWeight: tab === t ? 700 : 400,
              cursor: 'pointer',
              background: tab === t ? `${C.green}22` : C.bgEl,
              border: `1px solid ${tab === t ? C.green : C.border}`,
              color: tab === t ? C.green : C.textSec,
            }}>{t}</button>
          ))}
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>결과 {filtered.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim, fontSize: 13 }}>불러오는 중...</div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>📭</div>
            <div style={{ fontSize: 13 }}>교환/반품 내역이 없습니다</div>
          </div>
        ) : filtered.map(item => {
          const st = STATUS_MAP[item.status] || { label: item.status, color: '#757575', icon: '❓' };
          const tp = TYPE_MAP[item.request_type] || { label: item.request_type, icon: '📋' };
          return (
            <div key={item.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${st.color}`,
              borderRadius: 14, padding: '13px 14px', marginBottom: 8,
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  {/* Type + Icon */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <span style={{ fontSize: 18 }}>{tp.icon}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{tp.label} 요청</span>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 8,
                      background: `${st.color}22`, color: st.color, border: `1px solid ${st.color}44`,
                    }}>
                      {st.icon} {st.label}
                    </span>
                  </div>

                  {/* Order number */}
                  <div style={{ fontSize: 11, color: 'var(--accent-blue)', fontWeight: 600, marginBottom: 4 }}>
                    주문번호 {item.order_number}
                  </div>

                  {/* Reason */}
                  <div style={{ fontSize: 12, color: C.textSec, marginBottom: 4 }}>
                    사유: {item.reason}
                  </div>

                  {/* Requested resolution */}
                  <div style={{ fontSize: 11, color: C.textDim }}>
                    희망 처리: {item.requested_resolution}
                  </div>
                </div>

                <div style={{ fontSize: 10, color: C.textDim, flexShrink: 0, textAlign: 'right' }}>
                  {fmtDate(item.created_at)}
                </div>
              </div>

              {/* Actions */}
              <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
                <button
                  onClick={() => navigate(`/my-returns/${item.id}`)}
                  style={{
                    padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                    background: 'rgba(0,176,255,0.1)', border: '1px solid rgba(0,176,255,0.3)',
                    color: '#00b0ff', cursor: 'pointer',
                  }}
                >
                  상세보기
                </button>
                {item.dispute_id && (
                  <button
                    onClick={() => navigate(`/disputes/${item.dispute_id}`)}
                    style={{
                      padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                      background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.3)',
                      color: '#a78bfa', cursor: 'pointer',
                    }}
                  >
                    중재 상세 보기
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
