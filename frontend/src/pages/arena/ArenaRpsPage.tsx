// 가위바위보 (Rock Paper Scissors)
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import apiClient from '../../api/client';

const CHOICES = [
  { id: 'rock', emoji: '✊', name: '바위' },
  { id: 'paper', emoji: '✋', name: '보' },
  { id: 'scissors', emoji: '✌️', name: '가위' },
];

const RESULT_COLORS: Record<string, string> = { win: '#44BB44', lose: '#FF4444', draw: '#FFD700' };
const RESULT_TEXT: Record<string, string> = { win: '승리! 🎉', lose: '패배 💀', draw: '무승부 🤝' };

export default function ArenaRpsPage() {
  const { isLoggedIn } = useAuth();
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [streak, setStreak] = useState(0);

  const play = async (choice: string) => {
    setLoading(true);
    setResult(null);
    try {
      const res = await apiClient.post('/arena/play', { game_type: 'rps', data: { choice } });
      setResult(res.data);
      if (res.data.result === 'win') setStreak(s => s + 1);
      else setStreak(0);
    } catch (e: any) {
      if (e.response?.status === 429) {
        setResult({ result: 'limit', message: '오늘의 게임 한도를 초과했습니다!' });
      } else if (e.response?.status === 401) {
        // 비로그인: 로컬 게임
        const cpu = CHOICES[Math.floor(Math.random() * 3)].id;
        const diff = (['rock', 'paper', 'scissors'].indexOf(choice) - ['rock', 'paper', 'scissors'].indexOf(cpu) + 3) % 3;
        const r = diff === 0 ? 'draw' : diff === 1 ? 'win' : 'lose';
        setResult({ result: r, player_choice: choice, cpu_choice: cpu, points: 0, total_points: 0, arena_level: 'guest' });
        if (r === 'win') setStreak(s => s + 1); else setStreak(0);
      }
    }
    setLoading(false);
  };

  return (
    <div style={{ padding: 20, maxWidth: 500, margin: '0 auto', textAlign: 'center' }}>
      <Link to="/arena" style={{ color: '#888', textDecoration: 'none' }}>← 아레나</Link>
      <motion.h1 initial={{ scale: 0.5 }} animate={{ scale: 1 }} style={{ fontSize: 36, color: '#FFD700', margin: '20px 0' }}>
        ✊ 가위바위보
      </motion.h1>
      {!isLoggedIn && <p style={{ color: '#FF8800', fontSize: 13 }}>🔥 로그인하면 기록이 저장됩니다!</p>}
      {streak > 0 && <div style={{ color: '#FF4444', fontWeight: 700, fontSize: 20 }}>🔥 {streak} 연승!</div>}

      <div style={{ display: 'flex', gap: 20, justifyContent: 'center', margin: '30px 0' }}>
        {CHOICES.map(c => (
          <motion.button key={c.id} whileHover={{ scale: 1.15 }} whileTap={{ scale: 0.9 }}
            onClick={() => play(c.id)} disabled={loading}
            style={{ fontSize: 64, background: 'none', border: '3px solid #333', borderRadius: 20, padding: '20px 24px', cursor: 'pointer', transition: 'border-color 0.2s' }}
            onMouseEnter={e => (e.currentTarget.style.borderColor = '#FFD700')}
            onMouseLeave={e => (e.currentTarget.style.borderColor = '#333')}>
            {c.emoji}
            <div style={{ fontSize: 14, color: '#aaa' }}>{c.name}</div>
          </motion.button>
        ))}
      </div>

      <AnimatePresence>
        {result && result.result !== 'limit' && (
          <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            style={{ background: '#1a1a2e', borderRadius: 16, padding: 24, marginTop: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 40, alignItems: 'center', fontSize: 48, marginBottom: 16 }}>
              <div>{CHOICES.find(c => c.id === result.player_choice)?.emoji}<div style={{ fontSize: 12, color: '#aaa' }}>나</div></div>
              <div style={{ fontSize: 24, color: '#666' }}>VS</div>
              <div>{CHOICES.find(c => c.id === result.cpu_choice)?.emoji}<div style={{ fontSize: 12, color: '#aaa' }}>CPU</div></div>
            </div>
            <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', bounce: 0.5 }}
              style={{ fontSize: 28, fontWeight: 700, color: RESULT_COLORS[result.result] || '#fff' }}>
              {RESULT_TEXT[result.result] || result.result}
            </motion.div>
            {result.points > 0 && <div style={{ color: '#FFD700', marginTop: 8 }}>+{result.points} pts</div>}
            {result.total_points !== undefined && <div style={{ color: '#888', fontSize: 12, marginTop: 4 }}>총 {result.total_points}점 | {result.arena_level}</div>}
          </motion.div>
        )}
        {result?.result === 'limit' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ color: '#FF4444', fontSize: 18, marginTop: 20 }}>
            ⏰ {result.message}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
