import { useState, useEffect, useCallback } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { showToast } from '../components/common/Toast';

const C = {
  green: '#00e676', orange: '#ff9100', red: '#ff5252',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
};

interface Seller {
  id: number;
  name?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  business_name?: string;
  business_number?: string;
  verified_at?: string | null;
  status?: string;
  created_at?: string;
}

export default function AdminSellersPage() {
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'pending' | 'all'>('pending');
  const [approvingId, setApprovingId] = useState<number | null>(null);

  const fetchSellers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get(API.SELLERS.LIST);
      setSellers(Array.isArray(res.data) ? res.data : []);
    } catch {
      showToast('판매자 목록 로드 실패', 'error');
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchSellers(); }, [fetchSellers]);

  const handleApprove = async (id: number) => {
    setApprovingId(id);
    try {
      await apiClient.post(API.SELLERS.VERIFY(id));
      showToast('판매자 승인 완료', 'success');
      fetchSellers();
    } catch {
      showToast('승인 실패', 'error');
    }
    setApprovingId(null);
  };

  const filtered = tab === 'pending'
    ? sellers.filter(s => !s.verified_at)
    : sellers;

  return (
    <div style={{ padding: '24px 16px', maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>
        판매자 관리
      </h1>

      {/* 탭 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {(['pending', 'all'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '8px 20px', borderRadius: 10, fontSize: 13, fontWeight: 700,
              cursor: 'pointer',
              background: tab === t ? C.green : 'var(--bg-elevated)',
              color: tab === t ? '#0a0a0f' : C.textSec,
              border: `1px solid ${tab === t ? C.green : C.border}`,
            }}
          >
            {t === 'pending' ? `승인 대기 (${sellers.filter(s => !s.verified_at).length})` : `전체 (${sellers.length})`}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>로딩 중...</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>
          {tab === 'pending' ? '승인 대기 중인 판매자가 없습니다.' : '판매자가 없습니다.'}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(s => (
            <div key={s.id} style={{
              background: C.card, border: `1px solid ${C.border}`, borderRadius: 14,
              padding: '16px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 4 }}>
                  #{s.id} {s.business_name || s.name || s.nickname || '(이름 없음)'}
                </div>
                <div style={{ fontSize: 12, color: C.textSec }}>
                  {s.email} · {s.phone || '-'} · 사업자번호: {s.business_number || '-'}
                </div>
                <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                  가입: {s.created_at ? new Date(s.created_at).toLocaleDateString('ko-KR') : '-'}
                  {s.verified_at && ` · 승인: ${new Date(s.verified_at).toLocaleDateString('ko-KR')}`}
                </div>
              </div>
              <div style={{ flexShrink: 0, marginLeft: 12 }}>
                {s.verified_at ? (
                  <span style={{
                    padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                    background: 'rgba(0,230,118,0.1)', color: C.green,
                  }}>승인됨</span>
                ) : (
                  <button
                    onClick={() => handleApprove(s.id)}
                    disabled={approvingId === s.id}
                    style={{
                      padding: '8px 18px', borderRadius: 10, fontSize: 13, fontWeight: 700,
                      background: approvingId === s.id ? `${C.orange}55` : C.orange,
                      color: '#0a0a0f', cursor: approvingId === s.id ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {approvingId === s.id ? '처리중...' : '승인'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
