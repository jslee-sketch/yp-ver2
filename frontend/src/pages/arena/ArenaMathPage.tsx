// 수학배틀 (Math Battle)
import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import apiClient from '../../api/client';

export default function ArenaMathPage() {
  useAuth(); // keep context active
  const [question, setQuestion] = useState<any>(null);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState<any>(null);
  const [difficulty, setDifficulty] = useState(1);
  const [score, setScore] = useState(0);
  const [startTime, setStartTime] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const newQuestion = async () => {
    setResult(null);
    setAnswer('');
    try {
      const res = await apiClient.post('/arena/play', { game_type: 'math', data: { action: 'new', difficulty } });
      setQuestion(res.data);
      setStartTime(Date.now());
      setTimeout(() => inputRef.current?.focus(), 100);
    } catch {
      // 비로그인: 로컬 문제
      const a = Math.floor(Math.random() * 20) + 1;
      const b = Math.floor(Math.random() * 20) + 1;
      const op = ['+', '-', '*'][Math.floor(Math.random() * (difficulty + 1))];
      setQuestion({ question: `${a} ${op} ${b} = ?`, detail: { a, b, op, answer: eval(`${a}${op}${b}`) } });
      setStartTime(Date.now());
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  };

  const submit = async () => {
    if (!question) return;
    const timeMs = Date.now() - startTime;
    const correctAnswer = question.detail?.answer;
    try {
      const res = await apiClient.post('/arena/play', {
        game_type: 'math',
        data: { action: 'answer', answer: parseInt(answer), correct_answer: correctAnswer, time_ms: timeMs }
      });
      setResult(res.data);
      if (res.data.result === 'correct') setScore(s => s + (res.data.points || 1));
    } catch {
      const correct = parseInt(answer) === correctAnswer;
      setResult({ result: correct ? 'correct' : 'wrong', points: correct ? Math.max(1, 10 - Math.floor(timeMs / 1000)) : 0, time_ms: timeMs });
      if (correct) setScore(s => s + 1);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') submit();
  };

  return (
    <div style={{ padding: 20, maxWidth: 500, margin: '0 auto', textAlign: 'center' }}>
      <Link to="/arena" style={{ color: '#888', textDecoration: 'none' }}>← 아레나</Link>
      <motion.h1 initial={{ scale: 0.5 }} animate={{ scale: 1 }} style={{ fontSize: 36, color: '#4488FF', margin: '20px 0' }}>
        🧮 수학배틀
      </motion.h1>
      <div style={{ color: '#FFD700', marginBottom: 12 }}>Score: {score}</div>

      {/* 난이도 */}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 20 }}>
        {[1, 2, 3].map(d => (
          <button key={d} onClick={() => setDifficulty(d)}
            style={{ padding: '6px 16px', borderRadius: 12, border: difficulty === d ? '2px solid #4488FF' : '1px solid #555', background: difficulty === d ? '#4488FF' : 'transparent', color: '#fff', cursor: 'pointer' }}>
            Lv.{d}
          </button>
        ))}
      </div>

      {!question && (
        <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }} onClick={newQuestion}
          style={{ fontSize: 20, padding: '14px 40px', borderRadius: 16, background: 'linear-gradient(135deg, #4488FF, #2255CC)', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 700 }}>
          🎮 시작!
        </motion.button>
      )}

      <AnimatePresence>
        {question && !result && (
          <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
            style={{ background: '#1a1a2e', borderRadius: 16, padding: 24, marginTop: 20 }}>
            <div style={{ fontSize: 36, fontWeight: 700, marginBottom: 20 }}>{question.question || question.detail?.question}</div>
            <input ref={inputRef} type="number" value={answer} onChange={e => setAnswer(e.target.value)} onKeyDown={handleKeyDown}
              style={{ fontSize: 24, padding: '10px 20px', borderRadius: 12, border: '2px solid #4488FF', background: '#0a0a1a', color: '#fff', textAlign: 'center', width: 120 }}
              autoFocus />
            <div style={{ marginTop: 16 }}>
              <motion.button whileHover={{ scale: 1.05 }} onClick={submit}
                style={{ padding: '10px 30px', borderRadius: 12, background: '#44BB44', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 16, fontWeight: 700 }}>
                제출
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {result && (
          <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
            style={{ background: '#1a1a2e', borderRadius: 16, padding: 24, marginTop: 20 }}>
            <div style={{ fontSize: 32, fontWeight: 700, color: result.result === 'correct' ? '#44BB44' : '#FF4444' }}>
              {result.result === 'correct' ? '정답! ✅' : '오답 ❌'}
            </div>
            <div style={{ color: '#888', marginTop: 8 }}>
              {result.time_ms && `${(result.time_ms / 1000).toFixed(1)}초`}
              {result.points > 0 && ` | +${result.points} pts`}
            </div>
            <motion.button whileHover={{ scale: 1.05 }} onClick={() => { setQuestion(null); newQuestion(); }}
              style={{ marginTop: 16, padding: '10px 30px', borderRadius: 12, background: '#4488FF', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 700 }}>
              다음 문제 →
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
