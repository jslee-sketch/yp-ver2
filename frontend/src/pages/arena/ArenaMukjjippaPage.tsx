// 묵찌빠 (Korean RPS Extended)
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import apiClient from '../../api/client';

const CHOICES = [
  { id: 'rock', emoji: '✊', name: '묵' },
  { id: 'scissors', emoji: '✌️', name: '찌' },
  { id: 'paper', emoji: '✋', name: '빠' },
];

export default function ArenaMukjjippaPage() {
  const { isLoggedIn } = useAuth();
  const [result, setResult] = useState<any>(null);
  const [isAttacker, setIsAttacker] = useState(false);
  const [loading, setLoading] = useState(false);
  const [round, setRound] = useState(1);

  const play = async (choice: string) => {
    setLoading(true);
    try {
      const res = await apiClient.post('/arena/play', { game_type: 'mjb', data: { choice, is_attacker: isAttacker } });
      setResult(res.data);
      if (res.data.result === 'attack') setIsAttacker(true);
      else if (res.data.result === 'defend') setIsAttacker(false);
      if (['win', 'lose'].includes(res.data.result)) {
        setRound(1);
        setIsAttacker(false);
      } else {
        setRound(r => r + 1);
      }
    } catch (e: any) {
      if (e.response?.status === 401) {
        const cpu = CHOICES[Math.floor(Math.random() * 3)].id;
        setResult({ result: choice === cpu ? (isAttacker ? 'win' : 'lose') : 'attack', player_choice: choice, cpu_choice: cpu, points: 0 });
      }
    }
    setLoading(false);
  };

  return (
    <div style={{ padding: 20, maxWidth: 500, margin: '0 auto', textAlign: 'center' }}>
      <Link to="/arena" style={{ color: '#888', textDecoration: 'none' }}>← 아레나</Link>
      <motion.h1 initial={{ scale: 0.5 }} animate={{ scale: 1 }} style={{ fontSize: 36, color: '#FF4444', margin: '20px 0' }}>
        👊 묵찌빠
      </motion.h1>
      {!isLoggedIn && <p style={{ color: '#FF8800', fontSize: 13 }}>🔥 로그인하면 기록이 저장됩니다!</p>}
      <div style={{ color: isAttacker ? '#FF4444' : '#4488FF', fontWeight: 700, fontSize: 18, marginBottom: 16 }}>
        {isAttacker ? '⚔️ 공격' : '🛡️ 수비'} | Round {round}
      </div>

      <div style={{ display: 'flex', gap: 20, justifyContent: 'center', margin: '30px 0' }}>
        {CHOICES.map(c => (
          <motion.button key={c.id} whileHover={{ scale: 1.15 }} whileTap={{ scale: 0.9 }}
            onClick={() => play(c.id)} disabled={loading}
            style={{ fontSize: 56, background: 'none', border: '3px solid #333', borderRadius: 20, padding: '16px 20px', cursor: 'pointer' }}>
            {c.emoji}
            <div style={{ fontSize: 14, color: '#aaa' }}>{c.name}</div>
          </motion.button>
        ))}
      </div>

      <AnimatePresence>
        {result && (
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            style={{ background: '#1a1a2e', borderRadius: 16, padding: 20, marginTop: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 30, fontSize: 40, marginBottom: 12 }}>
              <div>{CHOICES.find(c => c.id === result.player_choice)?.emoji}</div>
              <span style={{ color: '#666' }}>VS</span>
              <div>{CHOICES.find(c => c.id === result.cpu_choice)?.emoji}</div>
            </div>
            <div style={{ fontSize: 24, fontWeight: 700, color: result.result === 'win' ? '#44BB44' : result.result === 'lose' ? '#FF4444' : '#FFD700' }}>
              {result.result === 'win' ? '승리! 🎉' : result.result === 'lose' ? '패배 💀' : result.result === 'attack' ? '공격권 획득! ⚔️' : '수비 🛡️'}
            </div>
            {result.points > 0 && <div style={{ color: '#FFD700', marginTop: 8 }}>+{result.points} pts</div>}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
