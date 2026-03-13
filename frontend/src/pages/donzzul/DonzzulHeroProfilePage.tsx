import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';

const BASE = import.meta.env.VITE_API_BASE || '';

interface HeroProfile {
  hero_id: number;
  user_id: number;
  hero_level: string;
  badge: string;
  title: string;
  total_stores: number;
  total_points: number;
  status: string;
  stores: { id: number; store_name: string; status: string; created_at: string }[];
}

export default function DonzzulHeroProfilePage() {
  const { heroId } = useParams();
  const [hero, setHero] = useState<HeroProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BASE}/donzzul/actuators/${heroId}/profile`)
      .then(r => r.json())
      .then(setHero)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [heroId]);

  if (loading) return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>로딩 중...</div>;
  if (!hero) return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>히어로를 찾을 수 없습니다</div>;

  return (
    <div style={{ maxWidth: 500, margin: '0 auto', padding: 20 }}>
      <Link to="/donzzul" style={{ color: '#888', textDecoration: 'none', fontSize: 13 }}>← 돈쭐 메인</Link>

      {/* Profile Card */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(244,114,182,0.1), rgba(74,222,128,0.1))',
        borderRadius: 16, padding: 24, textAlign: 'center', marginTop: 12, marginBottom: 20,
        border: '1px solid rgba(244,114,182,0.2)',
      }}>
        <div style={{ fontSize: 48, marginBottom: 8 }}>{hero.badge}</div>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#f472b6', marginBottom: 4 }}>
          {hero.title}
        </div>
        <div style={{ fontSize: 13, color: '#888' }}>
          Lv. {hero.hero_level}
        </div>

        <div style={{
          display: 'flex', justifyContent: 'center', gap: 24, marginTop: 16,
        }}>
          <div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#4ade80' }}>{hero.total_stores}</div>
            <div style={{ fontSize: 11, color: '#888' }}>추천 가게</div>
          </div>
          <div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#f59e0b' }}>{hero.total_points}</div>
            <div style={{ fontSize: 11, color: '#888' }}>포인트</div>
          </div>
        </div>
      </div>

      {/* Stores List */}
      <div style={{ fontSize: 15, fontWeight: 700, color: '#e0e0e0', marginBottom: 10 }}>
        추천한 가게 ({hero.stores.length})
      </div>
      {hero.stores.length === 0 && (
        <div style={{ padding: 20, textAlign: 'center', color: '#888', background: '#1a1a2e', borderRadius: 12 }}>
          아직 추천한 가게가 없습니다
        </div>
      )}
      {hero.stores.map(s => (
        <div key={s.id} style={{
          background: '#1a1a2e', borderRadius: 10, padding: 12, marginBottom: 6,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ fontSize: 14, color: '#e0e0e0' }}>{s.store_name}</div>
          <span style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 6,
            background: s.status === 'APPROVED' ? 'rgba(74,222,128,0.15)' : 'rgba(136,136,136,0.15)',
            color: s.status === 'APPROVED' ? '#4ade80' : '#888',
          }}>{s.status}</span>
        </div>
      ))}
    </div>
  );
}
