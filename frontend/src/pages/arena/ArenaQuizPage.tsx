// 상식퀴즈 (Trivia Quiz)
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import apiClient from '../../api/client';

export default function ArenaQuizPage() {
  useAuth(); // keep context active
  const [question, setQuestion] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [score, setScore] = useState(0);
  const [count, setCount] = useState(0);
  const [lang, setLang] = useState('ko');

  const loadQuestion = async () => {
    setResult(null);
    try {
      const res = await apiClient.post('/arena/play', { game_type: 'quiz', data: { action: 'new', lang } });
      setQuestion(res.data);
    } catch {
      setQuestion({ question: '역핑은 어떤 플랫폼?', choices: ['공동구매 중개', 'SNS', '게임', '은행'], question_id: 0, detail: { question_id: 0 } });
    }
  };

  const submitAnswer = async (answerIdx: number) => {
    const qid = question?.question_id ?? question?.detail?.question_id ?? 0;
    try {
      const res = await apiClient.post('/arena/play', { game_type: 'quiz', data: { action: 'answer', question_id: qid, answer: answerIdx } });
      setResult(res.data);
      setCount(c => c + 1);
      if (res.data.result === 'correct') setScore(s => s + (res.data.points || 5));
    } catch {
      setResult({ result: answerIdx === 0 ? 'correct' : 'wrong', points: answerIdx === 0 ? 5 : 0 });
      setCount(c => c + 1);
    }
  };

  return (
    <div style={{ padding: 20, maxWidth: 500, margin: '0 auto', textAlign: 'center' }}>
      <Link to="/arena" style={{ color: '#888', textDecoration: 'none' }}>← 아레나</Link>
      <motion.h1 initial={{ scale: 0.5 }} animate={{ scale: 1 }} style={{ fontSize: 36, color: '#AA44FF', margin: '20px 0' }}>
        🧠 상식퀴즈
      </motion.h1>
      <div style={{ color: '#FFD700', marginBottom: 8 }}>Score: {score} | #{count + 1}</div>

      <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 20 }}>
        {['ko', 'en', 'ja', 'zh', 'es'].map(l => (
          <button key={l} onClick={() => setLang(l)}
            style={{ padding: '3px 10px', borderRadius: 8, border: lang === l ? '2px solid #AA44FF' : '1px solid #555', background: lang === l ? '#AA44FF' : 'transparent', color: '#fff', cursor: 'pointer', fontSize: 12 }}>
            {l.toUpperCase()}
          </button>
        ))}
      </div>

      {!question && (
        <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }} onClick={loadQuestion}
          style={{ fontSize: 20, padding: '14px 40px', borderRadius: 16, background: 'linear-gradient(135deg, #AA44FF, #6622CC)', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 700 }}>
          🎮 시작!
        </motion.button>
      )}

      <AnimatePresence>
        {question && !result && (
          <motion.div initial={{ opacity: 0, x: 50 }} animate={{ opacity: 1, x: 0 }}
            style={{ background: '#1a1a2e', borderRadius: 16, padding: 24, marginTop: 20, textAlign: 'left' }}>
            <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 20, textAlign: 'center' }}>{question.question}</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {(question.choices || []).map((c: string, i: number) => (
                <motion.button key={i} whileHover={{ scale: 1.02, x: 8 }} whileTap={{ scale: 0.98 }}
                  onClick={() => submitAnswer(i)}
                  style={{ padding: '12px 16px', borderRadius: 12, border: '2px solid #333', background: '#0a0a1a', color: '#ddd', cursor: 'pointer', textAlign: 'left', fontSize: 16 }}>
                  {String.fromCharCode(65 + i)}. {c}
                </motion.button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {result && (
          <motion.div initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }}
            style={{ background: '#1a1a2e', borderRadius: 16, padding: 24, marginTop: 20 }}>
            <div style={{ fontSize: 32, fontWeight: 700, color: result.result === 'correct' ? '#44BB44' : '#FF4444' }}>
              {result.result === 'correct' ? '정답! 🎉' : '오답 ❌'}
            </div>
            {result.points > 0 && <div style={{ color: '#FFD700', marginTop: 8 }}>+{result.points} pts</div>}
            <motion.button whileHover={{ scale: 1.05 }} onClick={() => { setQuestion(null); loadQuestion(); }}
              style={{ marginTop: 16, padding: '10px 30px', borderRadius: 12, background: '#AA44FF', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 700 }}>
              다음 문제 →
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
