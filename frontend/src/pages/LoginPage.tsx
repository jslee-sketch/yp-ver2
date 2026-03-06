import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import type { AuthUser } from '../contexts/AuthContext';
import { FEATURES } from '../config';
import apiClient, { loginApi } from '../api/client';
import { API } from '../api/endpoints';
import { showToast } from '../components/common/Toast';

const C = {
  bgDeep:   '#0a0a0f',
  bgCard:   'rgba(255,255,255,0.04)',
  bgInput:  'rgba(255,255,255,0.06)',
  border:   'rgba(255,255,255,0.1)',
  cyan:     '#00e5ff',
  green:    '#00e676',
  magenta:  '#e040fb',
  text:     '#e8eaed',
  textSec:  '#78909c',
};

const MOCK_USER: AuthUser = {
  id: 1, email: 'hong@example.com', name: '홍길동', nickname: '딜마스터',
  role: 'buyer', level: 4, points: 1250, trust_tier: 'Silver',
};

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();

  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');

  // 회원가입 완료 후 넘어온 경우 이메일/비밀번호 자동 채움
  useEffect(() => {
    const st = location.state as { email?: string; password?: string } | null;
    if (st?.email) setEmail(st.email);
    if (st?.password) setPassword(st.password);
  }, [location.state]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');
  const [showForgot, setShowForgot] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotMsg, setForgotMsg] = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);

  const handleEmailLogin = async () => {
    if (!email.trim() || !password) {
      setError('이메일과 비밀번호를 입력해주세요');
      return;
    }
    setLoading(true);
    setError('');

    if (FEATURES.USE_API_AUTH) {
      try {
        const res = await loginApi(email.trim(), password);
        const { access_token } = res.data as { access_token: string };

        apiClient.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

        // JWT payload에서 role, verified 확인
        let jwtRole = '';
        let jwtVerified = true;
        try {
          const payload = JSON.parse(atob(access_token.split('.')[1]));
          jwtRole = payload.role || '';
          jwtVerified = payload.verified !== false;
        } catch { /* ignore */ }

        // 관리자 로그인
        if (jwtRole === 'admin') {
          login(access_token, {
            id: 0, email: email.trim(),
            name: '관리자',
            role: 'admin', level: 99, points: 0,
          });
          navigate('/admin');
          setLoading(false);
          return;
        }

        // JWT role에 따라 프로필 fetch
        if (jwtRole === 'seller') {
          try {
            const sellerRes = await apiClient.get(API.SELLERS.PROFILE);
            const s = sellerRes.data;
            login(access_token, {
              id: s.id, email: s.email || email,
              name: s.business_name || s.nickname || email.split('@')[0],
              nickname: s.nickname,
              role: 'seller',
              level: s.level ?? 1,
              points: s.points ?? 0,
              verified: jwtVerified,
              seller: { id: s.id, business_name: s.business_name || '', level: s.level ?? 1, points: s.points ?? 0 },
            });
          } catch {
            login(access_token, { id: 0, email: email.trim(), name: email.split('@')[0], role: 'seller', level: 1, points: 0, verified: jwtVerified });
          }
        } else if (jwtRole === 'actuator') {
          try {
            const actRes = await apiClient.get(API.ACTUATORS.PROFILE);
            const a = actRes.data as Record<string, unknown>;
            login(access_token, {
              id: a.id as number, email: (a.email as string) || email,
              name: (a.nickname as string) || (a.name as string) || email.split('@')[0],
              nickname: a.nickname as string,
              role: 'actuator',
              level: 1, points: 0,
            });
          } catch {
            login(access_token, { id: 0, email: email.trim(), name: email.split('@')[0], role: 'actuator' as 'buyer', level: 1, points: 0 });
          }
        } else {
          // 기본: 구매자 프로필 시도
          try {
            const buyerRes = await apiClient.get(API.BUYERS.PROFILE);
            const b = buyerRes.data;
            login(access_token, {
              id: b.id, email: b.email,
              name: b.name || b.nickname || email.split('@')[0],
              nickname: b.nickname,
              role: 'buyer',
              level: b.level ?? 1,
              points: b.points ?? 0,
              trust_tier: b.trust_tier,
            });
          } catch {
            login(access_token, { id: 0, email: email.trim(), name: email.split('@')[0], role: 'buyer', level: 1, points: 0 });
          }
        }
        navigate('/');
      } catch (err: unknown) {
        const e = err as { response?: { data?: { detail?: unknown } } };
        const detail = e.response?.data?.detail;
        setError(typeof detail === 'string' ? detail : '로그인에 실패했어요');
      }
    } else {
      // Mock 로그인
      login('mock-token-12345', MOCK_USER);
      navigate('/');
    }

    setLoading(false);
  };

  const handleSocialLogin = async (method: string) => {
    if (method === 'phone') {
      showToast('전화번호 로그인은 준비 중이에요. 이메일로 로그인해주세요!', 'info');
      return;
    }
    showToast('소셜 로그인은 준비 중이에요. 이메일로 로그인해주세요!', 'info');
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bgDeep, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', position: 'relative' }}>
      <style>{`
        @keyframes orbFloat1 { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(30px,-20px) scale(1.1)} }
        @keyframes orbFloat2 { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(-25px,30px) scale(0.95)} }
        @keyframes orbFloat3 { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(20px,15px) scale(1.05)} }
      `}</style>

      {/* 오브 배경 */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: '-10%', left: '-10%', width: 340, height: 340, borderRadius: '50%', background: `radial-gradient(circle, ${C.cyan}22 0%, transparent 70%)`, animation: 'orbFloat1 9s ease-in-out infinite' }} />
        <div style={{ position: 'absolute', bottom: '-5%', right: '-8%', width: 280, height: 280, borderRadius: '50%', background: `radial-gradient(circle, ${C.magenta}1a 0%, transparent 70%)`, animation: 'orbFloat2 11s ease-in-out infinite' }} />
        <div style={{ position: 'absolute', top: '40%', right: '15%', width: 200, height: 200, borderRadius: '50%', background: `radial-gradient(circle, ${C.green}18 0%, transparent 70%)`, animation: 'orbFloat3 7s ease-in-out infinite' }} />
      </div>

      {/* 카드 */}
      <div style={{
        position: 'relative', zIndex: 1,
        width: '100%', maxWidth: 360,
        margin: '0 24px',
        background: C.bgCard,
        border: `1px solid ${C.border}`,
        borderRadius: 24,
        padding: '40px 28px 32px',
        backdropFilter: 'blur(12px)',
      }}>
        {/* 로고 */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 34, fontWeight: 900, letterSpacing: '-1.5px', lineHeight: 1.1 }}>
            <span style={{
              background: `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>역핑</span>
          </div>
          <div style={{ fontSize: 13, color: C.textSec, marginTop: 6 }}>원하는 가격으로, 함께</div>
        </div>

        {/* 이메일 로그인 */}
        <div style={{ marginBottom: 16 }}>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="📧 이메일"
            style={{
              width: '100%', boxSizing: 'border-box' as const,
              padding: '13px 14px', borderRadius: 12, marginBottom: 8,
              background: C.bgInput, border: `1px solid ${C.border}`,
              color: C.text, fontSize: 14,
            }}
          />
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleEmailLogin(); }}
            placeholder="🔒 비밀번호"
            style={{
              width: '100%', boxSizing: 'border-box' as const,
              padding: '13px 14px', borderRadius: 12, marginBottom: error ? 8 : 12,
              background: C.bgInput, border: `1px solid ${error ? '#ff5252' : C.border}`,
              color: C.text, fontSize: 14,
            }}
          />
          {error && (
            <div style={{ fontSize: 12, color: '#ff5252', marginBottom: 10, paddingLeft: 2 }}>{error}</div>
          )}
          <button
            onClick={handleEmailLogin}
            disabled={loading}
            style={{
              width: '100%', padding: '14px', borderRadius: 14,
              background: loading ? `${C.green}55` : `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
              color: '#0a0a0f', fontSize: 14, fontWeight: 800,
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'opacity 0.15s',
            }}
          >
            {loading ? '로그인 중...' : '로그인하기'}
          </button>
          <div style={{ textAlign: 'right', marginTop: 6 }}>
            <button onClick={() => { setShowForgot(true); setForgotEmail(email); setForgotMsg(''); }} style={{ fontSize: 12, color: C.textSec, cursor: 'pointer', background: 'none', border: 'none', padding: 0 }}>
              비밀번호를 잊으셨나요?
            </button>
          </div>
        </div>

        {/* 구분선 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <div style={{ flex: 1, height: 1, background: C.border }} />
          <span style={{ fontSize: 11, color: C.textSec, whiteSpace: 'nowrap' }}>소셜로 시작하기</span>
          <div style={{ flex: 1, height: 1, background: C.border }} />
        </div>

        {/* 소셜 로그인 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14 }}>
          <button
            onClick={() => handleSocialLogin('kakao')}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '14px', borderRadius: 14, background: '#FEE500', color: '#3C1E1E', fontSize: 14, fontWeight: 700, cursor: 'pointer', transition: 'opacity 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.opacity = '0.88'; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}
          >
            <span style={{ fontSize: 18 }}>💬</span>카카오로 시작하기
          </button>

          <button
            onClick={() => handleSocialLogin('naver')}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '14px', borderRadius: 14, background: '#03C75A', color: '#fff', fontSize: 14, fontWeight: 700, cursor: 'pointer', transition: 'opacity 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.opacity = '0.88'; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}
          >
            <span style={{ fontWeight: 900, fontSize: 16, fontFamily: 'sans-serif' }}>N</span>네이버로 시작하기
          </button>

          <button
            onClick={() => handleSocialLogin('google')}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, padding: '14px', borderRadius: 14, background: 'rgba(255,255,255,0.92)', color: '#1f1f1f', fontSize: 14, fontWeight: 700, cursor: 'pointer', transition: 'opacity 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.opacity = '0.88'; }}
            onMouseLeave={e => { e.currentTarget.style.opacity = '1'; }}
          >
            <span style={{ fontSize: 17 }}>🌐</span>Google로 시작하기
          </button>
        </div>

        {/* 구분선 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
          <div style={{ flex: 1, height: 1, background: C.border }} />
          <span style={{ fontSize: 11, color: C.textSec }}>or</span>
          <div style={{ flex: 1, height: 1, background: C.border }} />
        </div>

        {/* 전화번호 */}
        <button
          onClick={() => handleSocialLogin('phone')}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
            padding: '14px', borderRadius: 14,
            background: 'rgba(255,255,255,0.06)', border: `1px solid ${C.border}`,
            color: C.text, fontSize: 14, fontWeight: 600, cursor: 'pointer', transition: 'background 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.1)'; }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
        >
          <span style={{ fontSize: 18 }}>📱</span>전화번호로 시작하기
        </button>

        {/* 회원가입 버튼 */}
        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <div style={{ fontSize: 12, color: C.textSec, marginBottom: 10 }}>아직 계정이 없으신가요?</div>
          <button
            onClick={() => navigate('/register?method=email')}
            style={{
              width: '100%', padding: '14px', borderRadius: 14,
              background: 'transparent',
              border: `2px solid ${C.green}`,
              color: C.green, fontSize: 15, fontWeight: 700,
              cursor: 'pointer', transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = `${C.green}15`; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
          >
            회원가입하기
          </button>
        </div>

        {/* 약관 안내 */}
        <div style={{ marginTop: 16, textAlign: 'center', fontSize: 11, color: C.textSec, lineHeight: 1.7 }}>
          가입 시{' '}
          <button style={{ color: C.cyan, fontSize: 11, cursor: 'pointer' }}>이용약관</button>
          {' '}및{' '}
          <button style={{ color: C.cyan, fontSize: 11, cursor: 'pointer' }}>개인정보처리방침</button>
          에 동의합니다.
        </div>
      </div>

      {/* 비밀번호 찾기 모달 */}
      {showForgot && (
        <>
          <div onClick={() => setShowForgot(false)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000 }} />
          <div style={{
            position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
            width: '90%', maxWidth: 360, background: '#1a1a2e', border: `1px solid ${C.border}`,
            borderRadius: 20, padding: '28px 24px', zIndex: 3001,
          }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 6 }}>비밀번호 찾기</div>
            <div style={{ fontSize: 12, color: C.textSec, marginBottom: 20 }}>가입한 이메일을 입력하면 재설정 안내를 보내드려요.</div>
            <input
              type="email"
              value={forgotEmail}
              onChange={e => setForgotEmail(e.target.value)}
              placeholder="가입한 이메일 주소"
              style={{
                width: '100%', boxSizing: 'border-box', padding: '13px 14px', borderRadius: 12, marginBottom: 12,
                background: C.bgInput, border: `1px solid ${C.border}`, color: C.text, fontSize: 14,
              }}
            />
            {forgotMsg && (
              <div style={{ fontSize: 12, color: forgotMsg.includes('실패') || forgotMsg.includes('없') ? '#ff5252' : C.green, marginBottom: 12, paddingLeft: 2 }}>
                {forgotMsg}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setShowForgot(false)} style={{
                flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                background: C.bgInput, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer',
              }}>닫기</button>
              <button
                disabled={forgotLoading || !forgotEmail.includes('@')}
                onClick={async () => {
                  setForgotLoading(true);
                  setForgotMsg('');
                  try {
                    await apiClient.post(API.AUTH.RESET_PASSWORD, { email: forgotEmail.trim() });
                    setForgotMsg('비밀번호 재설정 안내가 발송되었습니다.');
                  } catch (err: unknown) {
                    const e = err as { response?: { data?: { detail?: string } } };
                    setForgotMsg(e.response?.data?.detail || '이메일을 찾을 수 없습니다.');
                  }
                  setForgotLoading(false);
                }}
                style={{
                  flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  background: forgotLoading ? `${C.green}55` : C.green, border: 'none', color: '#0a0a0f',
                  cursor: forgotLoading || !forgotEmail.includes('@') ? 'not-allowed' : 'pointer',
                }}
              >
                {forgotLoading ? '처리 중...' : '재설정 요청'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
