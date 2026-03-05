import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
};

interface Buyer {
  id: number;
  name?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  level?: number;
  points?: number;
  trust_tier?: string;
  created_at?: string;
}

export default function AdminBuyersPage() {
  const [buyers, setBuyers] = useState<Buyer[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.get(API.BUYERS.LIST);
        setBuyers(Array.isArray(res.data) ? res.data : []);
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, []);

  return (
    <div style={{ padding: '24px 16px', maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>
        구매자 관리
      </h1>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 20 }}>
        총 {buyers.length}명
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>로딩 중...</div>
      ) : buyers.length === 0 ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>구매자가 없습니다.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {buyers.map(b => (
            <div key={b.id} style={{
              background: C.card, border: `1px solid ${C.border}`, borderRadius: 14,
              padding: '16px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 4 }}>
                  #{b.id} {b.name || b.nickname || '(이름 없음)'}
                  {b.nickname && <span style={{ fontSize: 12, color: C.textSec, marginLeft: 6 }}>@{b.nickname}</span>}
                </div>
                <div style={{ fontSize: 12, color: C.textSec }}>
                  {b.email} · {b.phone || '-'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                <span style={{
                  padding: '4px 10px', borderRadius: 8, fontSize: 11, fontWeight: 700,
                  background: 'rgba(0,176,255,0.08)', color: '#00b0ff',
                }}>Lv.{b.level ?? 1}</span>
                <span style={{
                  padding: '4px 10px', borderRadius: 8, fontSize: 11, fontWeight: 700,
                  background: 'rgba(0,230,118,0.08)', color: '#00e676',
                }}>{(b.points ?? 0).toLocaleString()}P</span>
                <span style={{
                  padding: '4px 10px', borderRadius: 8, fontSize: 11, fontWeight: 700,
                  background: 'rgba(192,192,192,0.08)', color: '#c0c0c0',
                }}>{b.trust_tier || 'Bronze'}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
