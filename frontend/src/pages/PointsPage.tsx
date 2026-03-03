import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { useAuth } from '../contexts/AuthContext';

type TxType = 'earn' | 'spend';

interface PointTx {
  id: number;
  type: TxType;
  delta: number;
  label: string;
  date: string;
}

const MOCK_BALANCE = 1250;

const MOCK_TXS: PointTx[] = [
  { id: 1, type: 'earn',  delta: 20,   label: '에어팟 프로 구매 확정',      date: '2026.02.28' },
  { id: 2, type: 'earn',  delta: 20,   label: '다이슨 에어랩 구매 확정',     date: '2026.02.20' },
  { id: 3, type: 'earn',  delta: 80,   label: '나이키 에어포스 구매 확정',   date: '2026.02.27' },
  { id: 4, type: 'earn',  delta: 50,   label: '회원가입 보너스',             date: '2026.01.15' },
  { id: 5, type: 'earn',  delta: 1080, label: '기타 적립',                  date: '2026.01.14' },
];

type Filter = '전체' | '적립' | '사용';
const FILTERS: Filter[] = ['전체', '적립', '사용'];

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

export default function PointsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [filter, setFilter]   = useState<Filter>('전체');
  const [balance, setBalance] = useState(MOCK_BALANCE);
  const [txs, setTxs]         = useState<PointTx[]>(MOCK_TXS);

  useEffect(() => {
    if (!user) return;
    const load = async () => {
      try {
        const balRes = await apiClient.get(API.POINTS.BALANCE);
        if (balRes.data != null) setBalance(Number(balRes.data) || 0);
      } catch { /* Mock 유지 */ }
      try {
        const histRes = await apiClient.get(API.POINTS.HISTORY);
        if (histRes.data && Array.isArray(histRes.data) && histRes.data.length > 0) {
          setTxs(histRes.data.map((t: Record<string, unknown>, i: number) => ({
            id:    typeof t.id === 'number' ? t.id : i + 1,
            type:  Number(t.amount ?? 0) >= 0 ? 'earn' as const : 'spend' as const,
            delta: Math.abs(Number(t.amount ?? 0)),
            label: typeof t.description === 'string' ? t.description : typeof t.reason === 'string' ? t.reason : '포인트 변동',
            date:  typeof t.created_at === 'string' ? t.created_at.split('T')[0].replace(/-/g, '.') : '',
          })));
        }
      } catch { /* Mock 유지 */ }
    };
    void load();
  }, [user]);

  const monthEarn  = txs.filter(t => t.type === 'earn').reduce((s, t) => s + t.delta, 0);
  const monthSpend = txs.filter(t => t.type === 'spend').reduce((s, t) => s + t.delta, 0);

  const filtered = txs.filter(tx => {
    if (filter === '적립') return tx.type === 'earn';
    if (filter === '사용') return tx.type === 'spend';
    return true;
  });

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      {/* TopBar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>포인트 내역</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '16px 16px 0' }}>
        {/* 잔액 카드 */}
        <div style={{
          background: 'linear-gradient(135deg, rgba(0,230,118,0.12), rgba(0,176,255,0.1))',
          border: `1px solid rgba(0,230,118,0.3)`,
          borderRadius: 18, padding: '22px 20px', marginBottom: 16, textAlign: 'center',
        }}>
          <div style={{ fontSize: 12, color: C.textSec, marginBottom: 6 }}>보유 포인트</div>
          <div style={{ fontSize: 32, fontWeight: 900, color: '#ffe156', letterSpacing: -1 }}>
            💰 {balance.toLocaleString('ko-KR')} P
          </div>
          <div style={{ fontSize: 12, color: C.textSec, marginTop: 8 }}>
            이번 달 <span style={{ color: '#00e676', fontWeight: 700 }}>+{monthEarn}P</span>
            {monthSpend > 0 && <span style={{ color: '#ff5252', fontWeight: 700, marginLeft: 8 }}>-{monthSpend}P</span>}
          </div>
        </div>

        {/* 필터 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          {FILTERS.map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              style={{
                padding: '6px 16px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
                background: filter === f ? `${C.green}22` : C.bgEl,
                border: `1px solid ${filter === f ? C.green : C.border}`,
                color: filter === f ? C.green : C.textSec,
                fontWeight: filter === f ? 700 : 400,
              }}
            >{f}</button>
          ))}
        </div>

        {/* 내역 */}
        <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, overflow: 'hidden' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '32px 0', textAlign: 'center', color: C.textDim, fontSize: 13 }}>내역이 없어요</div>
          ) : filtered.map((tx, idx) => (
            <div
              key={tx.id}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '14px 16px',
                borderBottom: idx < filtered.length - 1 ? `1px solid ${C.border}` : 'none',
              }}
            >
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: C.text, marginBottom: 3 }}>{tx.label}</div>
                <div style={{ fontSize: 11, color: C.textDim }}>{tx.date}</div>
              </div>
              <div style={{
                fontSize: 15, fontWeight: 800,
                color: tx.type === 'earn' ? '#00e676' : '#ff5252',
              }}>
                {tx.type === 'earn' ? '+' : '-'}{tx.delta.toLocaleString('ko-KR')}P
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
