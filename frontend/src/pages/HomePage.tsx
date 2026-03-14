import { useState, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { aiResolveIntent } from '../api/aiApi';
import { showToast } from '../components/common/Toast';

// ── Mock 통계 데이터 ──────────────────────────────────
const STATS = {
  todaySavings: 12847000,
  avgSavingPct: 13.7,
  topSavingPct: 23,
  hitRate: 67.2,
  watchingNow: 342,
  liveDeals: 12,
};

const HINTS = ['에어팟 프로', '갤럭시 S25', '나이키 에어맥스', '다이슨 에어랩'];

// ── Count-up 훅 ──────────────────────────────────────
function useCountUp(target: number, duration = 2000): number {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number | null>(null);
  const startRef = useRef<number | null>(null);

  const animate = useCallback((timestamp: number) => {
    if (!startRef.current) startRef.current = timestamp;
    const progress = Math.min((timestamp - startRef.current) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    setValue(Math.round(eased * target));
    if (progress < 1) rafRef.current = requestAnimationFrame(animate);
  }, [target, duration]);

  useEffect(() => {
    setValue(0);
    startRef.current = null;
    rafRef.current = requestAnimationFrame(animate);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [animate]);

  return value;
}

// ── 페이지 ───────────────────────────────────────────
export default function HomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [query, setQuery] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const savings = useCountUp(STATS.todaySavings);
  const isLoggedIn = !!user;

  const handleSearch = async (q = query) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    if (!isLoggedIn) {
      navigate('/login?returnUrl=' + encodeURIComponent('/search?q=' + encodeURIComponent(trimmed)));
      return;
    }

    // AI 의도 분석 시도 — 매칭/생성된 딜이 있으면 바로 이동
    setAiLoading(true);
    try {
      const result = await aiResolveIntent(trimmed);
      if (result && result.deal_id) {
        const verb = result.created ? '새 딜이 생성' : '딜이 매칭';
        showToast(`"${result.product_name}" ${verb}되었어요!`, 'success');
        navigate(`/deal/${result.deal_id}`);
        setAiLoading(false);
        return;
      }
    } catch {
      // AI 실패 시 일반 검색으로 fallback
    }
    setAiLoading(false);

    // fallback: 일반 검색
    navigate('/search?q=' + encodeURIComponent(trimmed));
  };

  const handleLiveDeals = () => {
    if (!isLoggedIn) {
      navigate('/login?returnUrl=/deals');
      return;
    }
    navigate('/deals');
  };

  return (
    <div style={{
      minHeight: '100dvh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      background: `
        radial-gradient(ellipse 80% 60% at 50% -10%, rgba(0,230,118,0.06) 0%, transparent 60%),
        radial-gradient(ellipse 60% 50% at 80% 80%, rgba(0,176,255,0.04) 0%, transparent 50%),
        #0a0a0f
      `,
      padding: '24px 20px 80px',
    }}>
      <div style={{ width: '100%', maxWidth: 480, display: 'flex', flexDirection: 'column', gap: 0 }}>

        {/* 상단 네비 */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 4 }}>
          {isLoggedIn ? (
            <>
              <button
                onClick={() => navigate('/mypage')}
                style={{
                  width: 36, height: 36, borderRadius: '50%',
                  background: 'rgba(255,255,255,0.05)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  fontSize: 18, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
                aria-label="마이페이지"
              >👤</button>
            </>
          ) : (
            <>
              <button
                onClick={() => navigate('/login')}
                style={{
                  padding: '8px 16px', borderRadius: 10,
                  background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
                  color: '#e8eaed', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                }}
              >로그인</button>
              <button
                onClick={() => navigate('/register')}
                style={{
                  padding: '8px 16px', borderRadius: 10,
                  background: 'linear-gradient(135deg, #00e676, #00b0ff)',
                  border: 'none', color: '#0a0a0f', fontSize: 13, fontWeight: 700, cursor: 'pointer',
                }}
              >회원가입</button>
            </>
          )}
        </div>

        {/* 로고 */}
        <div style={{ textAlign: 'center', marginBottom: 36 }}>
          <div style={{
            fontSize: 10, fontWeight: 700, letterSpacing: '6px',
            color: '#37474f', textTransform: 'uppercase', marginBottom: 8,
          }}>
            YEOKPING
          </div>
          <div style={{
            fontSize: 36, fontWeight: 900, letterSpacing: '-1px',
            background: 'linear-gradient(135deg, #00e676 0%, #00b0ff 100%)',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            display: 'inline-block',
            lineHeight: 1.1,
          }}>
            역핑
          </div>
          <div style={{ fontSize: 13, color: '#546e7a', marginTop: 6 }}>
            원하는 가격으로, 함께
          </div>
        </div>

        {/* 비로그인 환영 배너 */}
        {!isLoggedIn && (
          <div style={{
            textAlign: 'center', padding: '24px 16px', marginBottom: 20,
            background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 16,
          }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: '#e8eaed', marginBottom: 6 }}>
              역핑에 오신 것을 환영합니다!
            </div>
            <div style={{ fontSize: 13, color: '#78909c', marginBottom: 18 }}>
              소비자 주도형 공동구매 플랫폼
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
              <button
                onClick={() => navigate('/login')}
                style={{
                  padding: '12px 28px', borderRadius: 12,
                  background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
                  color: '#e8eaed', fontSize: 14, fontWeight: 700, cursor: 'pointer',
                }}
              >로그인</button>
              <button
                onClick={() => navigate('/register')}
                style={{
                  padding: '12px 28px', borderRadius: 12,
                  background: 'linear-gradient(135deg, #00e676, #00b0ff)',
                  border: 'none', color: '#0a0a0f', fontSize: 14, fontWeight: 700, cursor: 'pointer',
                }}
              >회원가입</button>
            </div>
          </div>
        )}

        {/* 검색 바 */}
        <div style={{
          position: 'relative',
          marginBottom: 12,
        }}>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') void handleSearch(); }}
            placeholder="자! 오늘 어떤 세상을 바꿔볼까요?"
            disabled={aiLoading}
            style={{
              width: '100%',
              padding: '16px 52px 16px 20px',
              fontSize: 14,
              borderRadius: 16,
              background: 'rgba(255,255,255,0.04)',
              border: `1px solid ${aiLoading ? 'rgba(0,230,118,0.3)' : 'rgba(255,255,255,0.08)'}`,
              color: 'var(--text-primary)',
              outline: 'none',
              boxSizing: 'border-box',
              opacity: aiLoading ? 0.7 : 1,
              transition: 'border-color 0.2s, box-shadow 0.2s, opacity 0.2s',
            }}
            onFocus={e => {
              if (!aiLoading) {
                e.target.style.borderColor = 'rgba(0,230,118,0.3)';
                e.target.style.boxShadow = '0 0 20px rgba(0,230,118,0.05)';
              }
            }}
            onBlur={e => {
              if (!aiLoading) {
                e.target.style.borderColor = 'rgba(255,255,255,0.08)';
                e.target.style.boxShadow = 'none';
              }
            }}
          />
          <button
            onClick={() => void handleSearch()}
            disabled={aiLoading}
            style={{
              position: 'absolute', right: 14, top: '50%',
              transform: 'translateY(-50%)',
              width: 32, height: 32,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: aiLoading ? 'transparent' : (query.trim() ? 'var(--accent-green)' : 'transparent'),
              borderRadius: 8,
              color: query.trim() ? '#0a0a0f' : 'var(--text-muted)',
              fontSize: 16,
              cursor: aiLoading ? 'wait' : 'pointer',
              transition: 'background 0.2s',
            }}
          >
            {aiLoading ? '...' : '🔍'}
          </button>
        </div>

        {/* AI 분석 중 인디케이터 */}
        {aiLoading && (
          <div style={{
            fontSize: 12, color: '#00e676', textAlign: 'center',
            marginBottom: 8, opacity: 0.8,
          }}>
            AI가 딜을 찾고 있어요...
          </div>
        )}

        {/* 힌트 칩 */}
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 28 }}>
          {HINTS.map(hint => (
            <button
              key={hint}
              onClick={() => {
                setQuery(hint);
                void handleSearch(hint);
              }}
              style={{
                padding: '5px 12px',
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 20,
                fontSize: 12, color: '#90a4ae',
                cursor: 'pointer',
                transition: 'border-color 0.15s, color 0.15s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.borderColor = 'rgba(0,230,118,0.25)';
                e.currentTarget.style.color = 'var(--accent-green)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
                e.currentTarget.style.color = '#90a4ae';
              }}
            >
              {hint}
            </button>
          ))}
        </div>

        {/* 라이브 딜 링크 */}
        <button
          onClick={handleLiveDeals}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            padding: '11px 20px',
            background: 'rgba(0,230,118,0.06)',
            border: '1px solid rgba(0,230,118,0.15)',
            borderRadius: 12,
            color: 'var(--accent-green)',
            fontSize: 14, fontWeight: 700,
            cursor: 'pointer',
            marginBottom: 32,
            transition: 'background 0.15s',
          }}
          onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,230,118,0.10)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(0,230,118,0.06)')}
        >
          🔥 지금 진행 중인 딜 {STATS.liveDeals}개
          <span style={{ opacity: 0.7, fontSize: 13 }}>→</span>
        </button>

        {/* 통계 섹션 */}
        <div style={{ marginBottom: 8 }}>
          <div style={{
            textAlign: 'center',
            fontSize: 11, fontWeight: 700, letterSpacing: '1.5px',
            color: '#455a64', textTransform: 'uppercase',
            marginBottom: 16,
          }}>
            ── 오늘 역핑이 뒤집은 세상 ──
          </div>

          {/* 오늘 절약 (wide) */}
          <div style={{
            padding: '16px 20px',
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 14,
            textAlign: 'center',
            marginBottom: 8,
            boxShadow: '0 0 20px rgba(0,230,118,0.08)',
          }}>
            <div style={{ fontSize: 11, color: '#78909c', marginBottom: 6 }}>💰 오늘 절약된 금액</div>
            <div style={{
              fontSize: 32, fontWeight: 900,
              color: 'var(--accent-green)',
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: '-0.5px',
            }}>
              ₩{savings.toLocaleString('ko-KR')}
            </div>
          </div>

          {/* 2열 그리드 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <StatBox
              icon="📉"
              label="평균 절약률"
              value={`-${STATS.avgSavingPct}%`}
              color="var(--text-secondary)"
            />
            <StatBox
              icon="⚡"
              label="최고 절약"
              value={`-${STATS.topSavingPct}%`}
              color="#ffd54f"
            />
            <StatBox
              icon="🎯"
              label="예측 적중률"
              value={`${STATS.hitRate}%`}
              color="var(--accent-blue)"
            />
            <StatBox
              icon="👀"
              label="지금 관전 중"
              value={`${STATS.watchingNow.toLocaleString()}명`}
              color="var(--accent-blue)"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 서브 컴포넌트 ─────────────────────────────────────
const StatBox: React.FC<{ icon: string; label: string; value: string; color: string }> = ({
  icon, label, value, color,
}) => (
  <div style={{
    padding: '13px 14px',
    background: 'rgba(255,255,255,0.025)',
    border: '1px solid rgba(255,255,255,0.05)',
    borderRadius: 12,
  }}>
    <div style={{ fontSize: 11, color: '#546e7a', marginBottom: 5 }}>
      {icon} {label}
    </div>
    <div style={{ fontSize: 18, fontWeight: 800, color }}>
      {value}
    </div>
  </div>
);
