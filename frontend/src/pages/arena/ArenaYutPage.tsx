// 윷놀이 (Yut Nori)
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import apiClient from '../../api/client';

const YUT_COLORS: Record<string, string> = { 도: '#888', 개: '#4488FF', 걸: '#44BB44', 윷: '#FFD700', 모: '#FF4444' };
const YUT_DESC: Record<string, string> = { 도: '1칸', 개: '2칸', 걸: '3칸', 윷: '4칸 🎉', 모: '5칸 🔥' };

export default function ArenaYutPage() {
  const { isLoggedIn } = useAuth();
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<any[]>([]);

  const throwYut = async () => {
    setLoading(true);
    try {
      const res = await apiClient.post('/arena/play', { game_type: 'yut', data: {} });
      setResult(res.data);
      setHistory(h => [res.data, ...h].slice(0, 10));
    } catch (e: any) {
      if (e.response?.status === 401) {
        const sticks: number[] = Array.from({ length: 4 }, () => Math.random() > 0.5 ? 1 : 0);
        const backs = sticks.reduce((a: number, b: number) => a + b, 0);
        const names = ['모', '도', '개', '걸', '윷'];
        setResult({ result: names[backs], sticks, move: backs === 0 ? 5 : backs, points: backs === 0 ? 5 : backs, bonus_throw: backs === 0 || backs === 4 });
      }
    }
    setLoading(false);
  };

  return (
    <div style={{ padding: 20, maxWidth: 500, margin: '0 auto', textAlign: 'center' }}>
      <Link to="/arena" style={{ color: '#888', textDecoration: 'none' }}>← 아레나</Link>
      <motion.h1 initial={{ scale: 0.5 }} animate={{ scale: 1 }} style={{ fontSize: 36, color: '#44BB44', margin: '20px 0' }}>
        🎯 윷놀이
      </motion.h1>
      {!isLoggedIn && <p style={{ color: '#FF8800', fontSize: 13 }}>🔥 로그인하면 기록이 저장됩니다!</p>}

      <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.85 }} onClick={throwYut} disabled={loading}
        style={{ fontSize: 24, padding: '16px 48px', borderRadius: 16, background: 'linear-gradient(135deg, #44BB44, #228B22)', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 700, marginTop: 20 }}>
        {loading ? '던지는 중...' : '🪵 윷 던지기!'}
      </motion.button>

      <AnimatePresence>
        {result && (
          <motion.div initial={{ opacity: 0, scale: 0.5, rotate: -10 }} animate={{ opacity: 1, scale: 1, rotate: 0 }} transition={{ type: 'spring' }}
            style={{ background: '#1a1a2e', borderRadius: 16, padding: 24, marginTop: 24 }}>
            {/* 윷 시각화 */}
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginBottom: 16 }}>
              {(result.sticks || result.detail?.sticks || [0,0,0,0]).map((s: number, i: number) => (
                <motion.div key={i} initial={{ rotateX: 180 }} animate={{ rotateX: 0 }} transition={{ delay: i * 0.15 }}
                  style={{ width: 40, height: 80, borderRadius: 8, background: s === 0 ? '#FFD700' : '#8B4513', border: '2px solid #555', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20 }}>
                  {s === 0 ? '⭐' : '🪵'}
                </motion.div>
              ))}
            </div>
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.6, type: 'spring', bounce: 0.6 }}
              style={{ fontSize: 48, fontWeight: 700, color: YUT_COLORS[result.result] || '#fff' }}>
              {result.result}
            </motion.div>
            <div style={{ color: '#aaa', marginTop: 4 }}>{YUT_DESC[result.result] || ''}</div>
            {result.bonus_throw && <div style={{ color: '#FF4444', fontWeight: 700, marginTop: 8 }}>🎉 한번 더!</div>}
            {result.points > 0 && <div style={{ color: '#FFD700', marginTop: 8 }}>+{result.points} pts</div>}
          </motion.div>
        )}
      </AnimatePresence>

      {/* 히스토리 */}
      {history.length > 1 && (
        <div style={{ marginTop: 24, textAlign: 'left' }}>
          <h4 style={{ color: '#888' }}>최근 결과</h4>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {history.map((h, i) => (
              <span key={i} style={{ padding: '4px 12px', borderRadius: 8, background: '#16213e', color: YUT_COLORS[h.result] || '#fff', fontSize: 14 }}>
                {h.result}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
