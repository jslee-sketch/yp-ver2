// 아레나 랭킹
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import apiClient from '../../api/client';

const GAME_TABS = [
  { id: 'all', name: '전체', color: '#FFD700' },
  { id: 'rps', name: '가위바위보', color: '#FFD700' },
  { id: 'mjb', name: '묵찌빠', color: '#FF4444' },
  { id: 'yut', name: '윷놀이', color: '#44BB44' },
  { id: 'math', name: '수학', color: '#4488FF' },
  { id: 'quiz', name: '퀴즈', color: '#AA44FF' },
  { id: 'reaction', name: '반응속도', color: '#FF8800' },
];

const LEVEL_COLORS: Record<string, string> = { legend: '#FFD700', champion: '#AA44FF', fighter: '#4488FF', rookie: '#888' };

export default function ArenaRankingsPage() {
  const [tab, setTab] = useState('all');
  const [rankings, setRankings] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    apiClient.get(`/arena/rankings?game_type=${tab}&limit=50`)
      .then(r => setRankings(r.data?.rankings || []))
      .catch(() => setRankings([]))
      .finally(() => setLoading(false));
  }, [tab]);

  const getStatValue = (p: any) => {
    switch (tab) {
      case 'rps': return `${p.rps_wins}W`;
      case 'mjb': return `${p.mjb_wins}W`;
      case 'yut': return `${p.yut_wins}W`;
      case 'math': return `Best: ${p.math_best_score}`;
      case 'quiz': return `Best: ${p.quiz_best_score}`;
      case 'reaction': return p.reaction_best_ms > 0 ? `${p.reaction_best_ms}ms` : '-';
      default: return `${p.total_points}pts`;
    }
  };

  return (
    <div style={{ padding: 20, maxWidth: 600, margin: '0 auto' }}>
      <Link to="/arena" style={{ color: '#888', textDecoration: 'none' }}>← 아레나</Link>
      <h1 style={{ textAlign: 'center', color: '#FFD700', margin: '20px 0' }}>🏆 랭킹</h1>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginBottom: 20 }}>
        {GAME_TABS.map(g => (
          <button key={g.id} onClick={() => setTab(g.id)}
            style={{ padding: '6px 14px', borderRadius: 16, border: tab === g.id ? `2px solid ${g.color}` : '1px solid #444', background: tab === g.id ? g.color + '22' : 'transparent', color: tab === g.id ? g.color : '#888', cursor: 'pointer', fontSize: 13 }}>
            {g.name}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', color: '#888', padding: 40 }}>로딩중...</div>
      ) : rankings.length === 0 ? (
        <div style={{ textAlign: 'center', color: '#666', padding: 40 }}>아직 데이터가 없습니다</div>
      ) : (
        <div>
          {rankings.map((p, i) => (
            <motion.div key={p.player_id} initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
              style={{ display: 'flex', alignItems: 'center', padding: '10px 16px', borderBottom: '1px solid #1a1a2e', gap: 12 }}>
              <span style={{ width: 32, fontWeight: 700, color: i < 3 ? '#FFD700' : '#666', fontSize: i < 3 ? 20 : 14 }}>
                {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `${i + 1}`}
              </span>
              <div style={{ flex: 1 }}>
                <span style={{ fontWeight: 600 }}>{p.nickname || `Player ${p.player_id}`}</span>
                <span style={{ marginLeft: 8, fontSize: 11, color: LEVEL_COLORS[p.arena_level] || '#888' }}>{p.arena_level?.toUpperCase()}</span>
              </div>
              <span style={{ color: '#aaa', fontSize: 12 }}>{p.country}</span>
              <span style={{ fontWeight: 700, color: GAME_TABS.find(g => g.id === tab)?.color || '#FFD700', minWidth: 80, textAlign: 'right' }}>
                {getStatValue(p)}
              </span>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
