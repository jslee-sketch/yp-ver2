import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const BASE = import.meta.env.VITE_API_BASE || '';

interface Candidate {
  store_id: number;
  store_name: string;
  story_text: string;
  score: number;
}

interface VoteWeek {
  id: number;
  week_label: string;
  vote_start: string;
  vote_end: string;
  status: string;
  total_votes: number;
  candidates: Candidate[];
  rank_1_store_id: number | null;
  rank_2_store_id: number | null;
  rank_3_store_id: number | null;
  announced_at: string | null;
}

export default function DonzzulVotePage() {
  const [currentWeek, setCurrentWeek] = useState<VoteWeek | null>(null);
  const [pastWeeks, setPastWeeks] = useState<VoteWeek[]>([]);
  const [loading, setLoading] = useState(true);
  const [voted, setVoted] = useState(false);
  const [votedStoreId, setVotedStoreId] = useState<number | null>(null);
  const [voteResult, setVoteResult] = useState<string>('');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [currentRes, pastRes] = await Promise.all([
        fetch(`${BASE}/donzzul/votes/current-week`),
        fetch(`${BASE}/donzzul/votes/weeks?status=CLOSED`),
      ]);
      if (currentRes.ok) {
        const data = await currentRes.json();
        setCurrentWeek(data);
      }
      if (pastRes.ok) {
        const data = await pastRes.json();
        setPastWeeks(data);
      }
    } catch {}
    setLoading(false);
  };

  const handleVote = async (storeId: number) => {
    if (!currentWeek || voted) return;
    try {
      const res = await fetch(`${BASE}/donzzul/votes/cast`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ week_id: currentWeek.id, store_id: storeId }),
      });
      const data = await res.json();
      if (res.ok) {
        setVoted(true);
        setVotedStoreId(storeId);
        setVoteResult(data.message || '투표 완료!');
        fetchData();
      } else {
        setVoteResult(data.detail || '투표 실패');
      }
    } catch {
      setVoteResult('네트워크 오류');
    }
  };

  if (loading) return <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>로딩 중...</div>;

  const sortedCandidates = [...(currentWeek?.candidates || [])].sort((a, b) => b.score - a.score);
  const maxScore = Math.max(...sortedCandidates.map(c => c.score), 1);

  return (
    <div style={{ maxWidth: 600, margin: '0 auto', padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 style={{ color: '#e0e0e0', fontSize: 22, margin: 0 }}>이번 주 투표</h1>
        <Link to="/donzzul" style={{ color: '#888', textDecoration: 'none', fontSize: 13 }}>← 돈쭐 메인</Link>
      </div>

      {!currentWeek && (
        <div style={{ textAlign: 'center', padding: 40, color: '#888', background: '#1a1a2e', borderRadius: 12 }}>
          현재 진행 중인 투표가 없습니다.
        </div>
      )}

      {currentWeek && (
        <>
          <div style={{
            background: '#1a1a2e', borderRadius: 12, padding: 16, marginBottom: 16,
            border: '1px solid rgba(74,222,128,0.2)',
          }}>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#4ade80', marginBottom: 4 }}>
              {currentWeek.week_label}
            </div>
            <div style={{ fontSize: 12, color: '#888' }}>
              {currentWeek.status === 'VOTING' ? '투표 진행 중' : currentWeek.status}
              {' | '}총 {currentWeek.total_votes}표
            </div>
          </div>

          {voteResult && (
            <div style={{
              padding: 12, borderRadius: 8, marginBottom: 12,
              background: voted ? 'rgba(74,222,128,0.1)' : 'rgba(239,68,68,0.1)',
              border: `1px solid ${voted ? 'rgba(74,222,128,0.3)' : 'rgba(239,68,68,0.3)'}`,
              color: voted ? '#4ade80' : '#ef4444', fontSize: 14, textAlign: 'center',
            }}>
              {voteResult}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {sortedCandidates.map((c, i) => (
              <div key={c.store_id} style={{
                background: '#1a1a2e', borderRadius: 12, padding: 16,
                border: votedStoreId === c.store_id ? '2px solid #4ade80' : '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <div>
                    <span style={{ fontSize: 16, fontWeight: 700, color: '#e0e0e0' }}>
                      {i === 0 && c.score > 0 ? '🥇 ' : i === 1 && c.score > 0 ? '🥈 ' : i === 2 && c.score > 0 ? '🥉 ' : ''}
                      {c.store_name}
                    </span>
                  </div>
                  <span style={{ fontSize: 14, fontWeight: 600, color: '#f472b6' }}>{c.score}표</span>
                </div>
                <div style={{ fontSize: 13, color: '#999', marginBottom: 10, lineHeight: 1.5 }}>
                  {c.story_text}
                </div>
                {/* Progress bar */}
                <div style={{ height: 6, background: '#2a2a4a', borderRadius: 3, overflow: 'hidden', marginBottom: 10 }}>
                  <div style={{
                    height: '100%', width: `${(c.score / maxScore) * 100}%`,
                    background: 'linear-gradient(90deg, #4ade80, #f472b6)',
                    borderRadius: 3, transition: 'width 0.5s',
                  }} />
                </div>
                {currentWeek.status === 'VOTING' && !voted && (
                  <button
                    onClick={() => handleVote(c.store_id)}
                    style={{
                      width: '100%', padding: 12, borderRadius: 10, fontSize: 14, fontWeight: 700,
                      background: '#4ade80', color: '#000', border: 'none', cursor: 'pointer',
                    }}
                  >
                    이 가게에 투표하기
                  </button>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* 지난 투표 */}
      {pastWeeks.length > 0 && (
        <div style={{ marginTop: 32 }}>
          <h2 style={{ color: '#888', fontSize: 16, marginBottom: 12 }}>지난 투표 결과</h2>
          {pastWeeks.map(w => (
            <div key={w.id} style={{
              background: '#1a1a2e', borderRadius: 10, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 14, fontWeight: 600, color: '#e0e0e0' }}>{w.week_label}</span>
                <span style={{ fontSize: 12, color: '#888' }}>총 {w.total_votes}표</span>
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: '#999' }}>
                {w.candidates
                  .sort((a, b) => b.score - a.score)
                  .slice(0, 3)
                  .map((c, i) => (
                    <span key={c.store_id} style={{ marginRight: 12 }}>
                      {i === 0 ? '🥇' : i === 1 ? '🥈' : '🥉'} {c.store_name} ({c.score}표)
                    </span>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
