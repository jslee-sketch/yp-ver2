import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

/* ── 타입 ── */
interface DisputeListItem {
  id: number;
  order_number?: string;
  reservation_id?: number;
  status: string;
  category?: string;
  title?: string;
  days_remaining?: number;
  current_round?: number;
  created_at: string;
}

/* ── 상수 ── */
const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

const STATUS_MAP: Record<string, { label: string; color: string; icon: string }> = {
  ROUND1_RESPONSE: { label: 'Round 1 변론 대기', color: '#ff8c42', icon: '🔶' },
  ROUND1_AI:       { label: 'AI 분석 중', color: '#a78bfa', icon: '🤖' },
  ROUND1_REVIEW:   { label: '합의 검토', color: '#00e5ff', icon: '🔍' },
  ROUND2_RESPONSE: { label: 'Round 2 변론 대기', color: '#fbbf24', icon: '🔶' },
  ROUND2_AI:       { label: 'AI 2차 분석 중', color: '#a78bfa', icon: '🤖' },
  ROUND2_REVIEW:   { label: 'Round 2 합의 검토', color: '#f472b6', icon: '🔍' },
  ACCEPTED:        { label: '합의 완료', color: '#00e676', icon: '🎉' },
  REJECTED:        { label: '결렬', color: '#ff5252', icon: '⚖️' },
  AUTO_CLOSED:     { label: '자동 종결', color: '#757575', icon: '⏰' },
  ADMIN_DECIDED:   { label: '관리자 판정', color: '#e040fb', icon: '👨‍⚖️' },
};

const TABS = ['진행중', '완료'] as const;
const ACTIVE_STATUSES = ['ROUND1_RESPONSE', 'ROUND1_AI', 'ROUND1_REVIEW', 'ROUND2_RESPONSE', 'ROUND2_AI', 'ROUND2_REVIEW'];
const DONE_STATUSES = ['ACCEPTED', 'REJECTED', 'AUTO_CLOSED', 'ADMIN_DECIDED'];

function fmtDate(s: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

export default function MyDisputesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const [items, setItems] = useState<DisputeListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<typeof TABS[number]>('진행중');

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    (async () => {
      setLoading(true);
      try {
        const res = await apiClient.get('/v3/disputes/my', { params: { user_id: user.id } });
        const data = Array.isArray(res.data) ? res.data : (res.data?.items ?? []);
        setItems(data as DisputeListItem[]);
      } catch {
        // silent
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  const filtered = items.filter(item => {
    if (tab === '진행중') return ACTIVE_STATUSES.includes(item.status);
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
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>중재</span>
        <button
          onClick={() => navigate('/my-disputes/new')}
          style={{
            fontSize: 12, fontWeight: 700, padding: '5px 10px', borderRadius: 8,
            background: 'rgba(0,230,118,0.12)', border: '1px solid rgba(0,230,118,0.3)',
            color: '#00e676', cursor: 'pointer',
          }}
        >
          + 중재 신청하기
        </button>
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
            <div style={{ fontSize: 40, marginBottom: 8 }}>⚖️</div>
            <div style={{ fontSize: 13 }}>진행 중인 중재가 없습니다</div>
          </div>
        ) : filtered.map(item => {
          const st = STATUS_MAP[item.status] || { label: item.status, color: '#757575', icon: '❓' };
          return (
            <div key={item.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${st.color}`,
              borderRadius: 14, padding: '13px 14px', marginBottom: 8,
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  {/* Dispute ID */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <span style={{ fontSize: 14, fontWeight: 800, color: C.text }}>D-{item.id}</span>
                    <span style={{
                      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 8,
                      background: `${st.color}22`, color: st.color, border: `1px solid ${st.color}44`,
                    }}>
                      {st.icon} {st.label}
                    </span>
                  </div>

                  {/* Order number */}
                  {item.order_number && (
                    <div style={{ fontSize: 11, color: 'var(--accent-blue)', fontWeight: 600, marginBottom: 4 }}>
                      주문번호 {item.order_number}
                    </div>
                  )}
                  {!item.order_number && item.reservation_id && (
                    <div style={{ fontSize: 11, color: C.textSec, marginBottom: 4 }}>
                      예약 #{item.reservation_id}
                    </div>
                  )}

                  {/* Days remaining countdown */}
                  {item.days_remaining != null && !DONE_STATUSES.includes(item.status) && (
                    <div style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4,
                      padding: '3px 8px', borderRadius: 6, marginTop: 2,
                      background: item.days_remaining <= 1 ? 'rgba(255,82,82,0.1)' : 'rgba(255,140,66,0.08)',
                      border: `1px solid ${item.days_remaining <= 1 ? 'rgba(255,82,82,0.2)' : 'rgba(255,140,66,0.15)'}`,
                    }}>
                      <span style={{ fontSize: 12 }}>⏰</span>
                      <span style={{
                        fontSize: 11, fontWeight: 700,
                        color: item.days_remaining <= 1 ? '#ff5252' : '#ff8c42',
                      }}>
                        {item.days_remaining}영업일 남음
                      </span>
                    </div>
                  )}
                </div>

                <div style={{ fontSize: 10, color: C.textDim, flexShrink: 0, textAlign: 'right' }}>
                  {fmtDate(item.created_at)}
                </div>
              </div>

              {/* Actions */}
              <div style={{ marginTop: 8 }}>
                <button
                  onClick={() => navigate(`/disputes/${item.id}`)}
                  style={{
                    padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                    background: 'rgba(0,176,255,0.1)', border: '1px solid rgba(0,176,255,0.3)',
                    color: '#00b0ff', cursor: 'pointer',
                  }}
                >
                  상세보기
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
