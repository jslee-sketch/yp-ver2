// 반응속도 (Reaction Speed Test)
import { useState, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import apiClient from '../../api/client';

type Phase = 'idle' | 'waiting' | 'ready' | 'result' | 'early';

export default function ArenaReactionPage() {
  useAuth(); // keep context active
  const [phase, setPhase] = useState<Phase>('idle');
  const [reactionMs, setReactionMs] = useState(0);
  const [bestMs, setBestMs] = useState(0);
  const [result, setResult] = useState<any>(null);
  const timerRef = useRef<any>(null);
  const startRef = useRef(0);

  const startGame = () => {
    setPhase('waiting');
    setResult(null);
    const delay = 1500 + Math.random() * 3500; // 1.5~5초 랜덤 대기
    timerRef.current = setTimeout(() => {
      setPhase('ready');
      startRef.current = Date.now();
    }, delay);
  };

  const handleClick = useCallback(async () => {
    if (phase === 'waiting') {
      clearTimeout(timerRef.current);
      setPhase('early');
      return;
    }
    if (phase === 'ready') {
      const ms = Date.now() - startRef.current;
      setReactionMs(ms);
      setPhase('result');
      if (bestMs === 0 || ms < bestMs) setBestMs(ms);

      try {
        const res = await apiClient.post('/arena/play', { game_type: 'reaction', data: { reaction_ms: ms } });
        setResult(res.data);
      } catch {
        setResult({ result: 'recorded', reaction_ms: ms, points: Math.max(1, 10 - Math.floor(ms / 100)) });
      }
    }
  }, [phase, bestMs]);

  const getColor = () => {
    switch (phase) {
      case 'waiting': return '#FF4444';
      case 'ready': return '#44BB44';
      case 'early': return '#FFD700';
      case 'result': return '#1a1a2e';
      default: return '#16213e';
    }
  };

  const getMessage = () => {
    switch (phase) {
      case 'idle': return '클릭해서 시작!';
      case 'waiting': return '초록색이 되면 클릭!';
      case 'ready': return '지금 클릭!';
      case 'early': return '너무 빨랐어요! 다시 시도';
      case 'result': return `${reactionMs}ms`;
      default: return '';
    }
  };

  return (
    <div style={{ padding: 20, maxWidth: 500, margin: '0 auto', textAlign: 'center' }}>
      <Link to="/arena" style={{ color: '#888', textDecoration: 'none' }}>← 아레나</Link>
      <motion.h1 initial={{ scale: 0.5 }} animate={{ scale: 1 }} style={{ fontSize: 36, color: '#FF8800', margin: '20px 0' }}>
        ⚡ 반응속도
      </motion.h1>
      {bestMs > 0 && <div style={{ color: '#FFD700', marginBottom: 12 }}>Best: {bestMs}ms</div>}

      <motion.div
        onClick={phase === 'idle' || phase === 'early' ? startGame : handleClick}
        whileTap={{ scale: 0.95 }}
        style={{
          width: '100%', height: 300, borderRadius: 24, display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', background: getColor(), transition: 'background 0.15s',
          flexDirection: 'column', userSelect: 'none',
        }}>
        <motion.div key={phase} initial={{ scale: 0.5, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
          style={{ fontSize: phase === 'result' ? 48 : 24, fontWeight: 700, color: phase === 'ready' ? '#000' : '#fff' }}>
          {getMessage()}
        </motion.div>
        {phase === 'result' && (
          <div style={{ fontSize: 14, color: '#888', marginTop: 8 }}>
            {reactionMs < 200 ? '⚡ 번개 반사신경!' : reactionMs < 300 ? '👍 빠르네요!' : reactionMs < 500 ? '🙂 평균' : '🐢 좀 더 연습!'}
          </div>
        )}
      </motion.div>

      <AnimatePresence>
        {result && phase === 'result' && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            style={{ marginTop: 20, display: 'flex', gap: 12, justifyContent: 'center' }}>
            {result.points > 0 && <span style={{ color: '#FFD700' }}>+{result.points} pts</span>}
            <motion.button whileHover={{ scale: 1.05 }} onClick={() => { setPhase('idle'); }}
              style={{ padding: '10px 24px', borderRadius: 12, background: '#FF8800', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 700 }}>
              다시 도전
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
