import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

interface SellerSummary {
  seller_id: number;
  name?: string;
  business_name?: string;
  total_offers: number;
  confirmed_offers: number;
  active_offers: number;
  total_sold_qty: number;
  verified_at?: string;
  // from /me/sellers extended response
  offers?: unknown[];
}

function fmtNum(n: number) {
  if (n >= 10000) return (n / 10000).toFixed(0) + '만';
  return n.toLocaleString('ko-KR');
}

export default function ActuatorSellersPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [sellers, setSellers] = useState<SellerSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (!user) return;
    const actuatorId = user.id;
    (async () => {
      try {
        const res = await apiClient.get(`/actuators/${actuatorId}/sellers`);
        const data = res.data;
        setSellers(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error('판매자 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [user]);

  const filtered = sellers.filter(s => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      String(s.seller_id).includes(q) ||
      (s.business_name ?? '').toLowerCase().includes(q) ||
      (s.name ?? '').toLowerCase().includes(q)
    );
  });

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      {/* 헤더 */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>내 판매자 관리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 검색 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <input
            value={search} onChange={e => setSearch(e.target.value)}
            placeholder="ID / 회사명 / 대표자이름 검색"
            style={{
              flex: 1, padding: '10px 14px', borderRadius: 10, fontSize: 13,
              background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
              boxSizing: 'border-box',
            }}
          />
        </div>

        {/* 요약 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>내 판매자</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.green }}>{sellers.length}명</div>
          </div>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>총 오퍼</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.text }}>{sellers.reduce((a, s) => a + s.total_offers, 0)}건</div>
          </div>
          <div style={{ flex: 1, textAlign: 'center', padding: 12, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 12 }}>
            <div style={{ fontSize: 10, color: C.textDim }}>총 낙찰</div>
            <div style={{ fontSize: 18, fontWeight: 700, color: C.orange }}>{sellers.reduce((a, s) => a + s.confirmed_offers, 0)}건</div>
          </div>
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>{filtered.length}명</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>👥</div>
            <div style={{ fontSize: 13 }}>{search ? '검색 결과가 없어요' : '아직 담당 판매자가 없어요'}</div>
          </div>
        ) : filtered.map(s => (
          <button key={s.seller_id} onClick={() => navigate(`/actuator/sellers/${s.seller_id}/offers`)}
            style={{
              width: '100%', textAlign: 'left', cursor: 'pointer',
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${s.verified_at ? C.green : C.orange}`,
              borderRadius: 14, padding: 14, marginBottom: 8,
            }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 2 }}>
                  {s.business_name || s.name || `판매자 #${s.seller_id}`}
                </div>
                <div style={{ fontSize: 11, color: C.textSec }}>
                  {s.name ? `${s.name} · ` : ''}ID #{s.seller_id}
                </div>
              </div>
              <span style={{
                fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6, height: 'fit-content',
                background: s.verified_at ? `${C.green}22` : `${C.orange}22`,
                color: s.verified_at ? C.green : C.orange,
              }}>
                {s.verified_at ? '승인' : '대기'}
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 6 }}>
              <div><div style={{ fontSize: 10, color: C.textDim }}>오퍼수</div><div style={{ fontSize: 12, fontWeight: 700, color: C.text }}>{s.total_offers}</div></div>
              <div><div style={{ fontSize: 10, color: C.textDim }}>낙찰</div><div style={{ fontSize: 12, fontWeight: 700, color: C.green }}>{s.confirmed_offers}</div></div>
              <div><div style={{ fontSize: 10, color: C.textDim }}>활성</div><div style={{ fontSize: 12, fontWeight: 700, color: '#00b0ff' }}>{s.active_offers}</div></div>
              <div><div style={{ fontSize: 10, color: C.textDim }}>판매</div><div style={{ fontSize: 12, fontWeight: 700, color: C.orange }}>{fmtNum(s.total_sold_qty)}개</div></div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
