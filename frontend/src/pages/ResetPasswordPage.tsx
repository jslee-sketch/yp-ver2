import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  bgDeep:  '#0a0a0f',
  bgCard:  'rgba(255,255,255,0.04)',
  bgInput: 'rgba(255,255,255,0.06)',
  border:  'rgba(255,255,255,0.1)',
  cyan:    '#00e5ff',
  green:   '#00e676',
  magenta: '#e040fb',
  text:    '#e8eaed',
  textSec: '#78909c',
};

type PageState = 'loading' | 'valid' | 'expired' | 'invalid' | 'success';

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  const [state, setState] = useState<PageState>('loading');
  const [password, setPassword] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!token) {
      setState('invalid');
      return;
    }
    apiClient.get(API.AUTH.RESET_PASSWORD_VERIFY, { params: { token } })
      .then(() => setState('valid'))
      .catch((err) => {
        const detail = err.response?.data?.detail;
        setState(detail === 'token_expired' ? 'expired' : 'invalid');
      });
  }, [token]);

  const handleSubmit = async () => {
    setError('');
    if (password.length < 8) {
      setError('비밀번호는 8자 이상이어야 합니다.');
      return;
    }
    if (password !== confirmPw) {
      setError('비밀번호가 일치하지 않습니다.');
      return;
    }
    setSubmitting(true);
    try {
      await apiClient.post(API.AUTH.RESET_PASSWORD_CONFIRM, { token, new_password: password });
      setState('success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      const detail = e.response?.data?.detail;
      if (detail === 'token_expired') {
        setState('expired');
      } else if (detail === 'invalid_token') {
        setState('invalid');
      } else if (detail === 'password_too_short') {
        setError('비밀번호는 8자 이상이어야 합니다.');
      } else {
        setError('오류가 발생했습니다. 다시 시도해주세요.');
      }
    }
    setSubmitting(false);
  };

  const cardStyle: React.CSSProperties = {
    position: 'relative', zIndex: 1,
    width: '100%', maxWidth: 400,
    margin: '0 24px',
    background: C.bgCard,
    border: `1px solid ${C.border}`,
    borderRadius: 24,
    padding: '40px 28px 32px',
    backdropFilter: 'blur(12px)',
  };

  const renderContent = () => {
    if (state === 'loading') {
      return (
        <div style={cardStyle}>
          <div style={{ textAlign: 'center', color: C.textSec, fontSize: 14 }}>
            토큰 확인 중...
          </div>
        </div>
      );
    }

    if (state === 'invalid') {
      return (
        <div style={cardStyle}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>&#x26A0;&#xFE0F;</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 8 }}>유효하지 않은 링크</div>
            <div style={{ fontSize: 13, color: C.textSec, marginBottom: 24, lineHeight: 1.6 }}>
              비밀번호 재설정 링크가 유효하지 않습니다.<br/>
              새로운 재설정 요청을 해주세요.
            </div>
            <button onClick={() => navigate('/login')} style={{
              width: '100%', padding: '14px', borderRadius: 14,
              background: `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
              color: '#0a0a0f', fontSize: 14, fontWeight: 800, cursor: 'pointer',
            }}>로그인 페이지로</button>
          </div>
        </div>
      );
    }

    if (state === 'expired') {
      return (
        <div style={cardStyle}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>&#x23F0;</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 8 }}>링크 만료</div>
            <div style={{ fontSize: 13, color: C.textSec, marginBottom: 24, lineHeight: 1.6 }}>
              비밀번호 재설정 링크가 만료되었습니다.<br/>
              로그인 페이지에서 다시 요청해주세요.
            </div>
            <button onClick={() => navigate('/login')} style={{
              width: '100%', padding: '14px', borderRadius: 14,
              background: `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
              color: '#0a0a0f', fontSize: 14, fontWeight: 800, cursor: 'pointer',
            }}>로그인 페이지로</button>
          </div>
        </div>
      );
    }

    if (state === 'success') {
      return (
        <div style={cardStyle}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>&#x2705;</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 8 }}>비밀번호 변경 완료</div>
            <div style={{ fontSize: 13, color: C.textSec, marginBottom: 24, lineHeight: 1.6 }}>
              새 비밀번호로 로그인할 수 있습니다.
            </div>
            <button onClick={() => navigate('/login')} style={{
              width: '100%', padding: '14px', borderRadius: 14,
              background: `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
              color: '#0a0a0f', fontSize: 14, fontWeight: 800, cursor: 'pointer',
            }}>로그인하기</button>
          </div>
        </div>
      );
    }

    // state === 'valid' — 비밀번호 입력 폼
    return (
      <div style={cardStyle}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 34, fontWeight: 900, letterSpacing: '-1.5px', lineHeight: 1.1 }}>
            <span style={{
              background: `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
              WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
            }}>역핑</span>
          </div>
          <div style={{ fontSize: 13, color: C.textSec, marginTop: 6 }}>새 비밀번호를 설정해주세요</div>
        </div>

        <div style={{ marginBottom: 16 }}>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="새 비밀번호 (8자 이상)"
            style={{
              width: '100%', boxSizing: 'border-box',
              padding: '13px 14px', borderRadius: 12, marginBottom: 8,
              background: C.bgInput, border: `1px solid ${C.border}`,
              color: C.text, fontSize: 14,
            }}
          />
          <input
            type="password"
            value={confirmPw}
            onChange={e => setConfirmPw(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleSubmit(); }}
            placeholder="비밀번호 확인"
            style={{
              width: '100%', boxSizing: 'border-box',
              padding: '13px 14px', borderRadius: 12, marginBottom: error ? 8 : 16,
              background: C.bgInput, border: `1px solid ${error ? '#ff5252' : C.border}`,
              color: C.text, fontSize: 14,
            }}
          />
          {error && (
            <div style={{ fontSize: 12, color: '#ff5252', marginBottom: 12, paddingLeft: 2 }}>{error}</div>
          )}
          <button
            onClick={handleSubmit}
            disabled={submitting}
            style={{
              width: '100%', padding: '14px', borderRadius: 14,
              background: submitting ? `${C.green}55` : `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
              color: '#0a0a0f', fontSize: 14, fontWeight: 800,
              cursor: submitting ? 'not-allowed' : 'pointer',
            }}
          >
            {submitting ? '처리 중...' : '비밀번호 변경하기'}
          </button>
        </div>

        <div style={{ textAlign: 'center' }}>
          <button
            onClick={() => navigate('/login')}
            style={{ fontSize: 12, color: C.textSec, cursor: 'pointer', background: 'none', border: 'none', padding: 0 }}
          >
            로그인 페이지로 돌아가기
          </button>
        </div>
      </div>
    );
  };

  return (
    <div style={{
      minHeight: '100dvh', background: C.bgDeep,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      overflow: 'hidden', position: 'relative',
    }}>
      <style>{`
        @keyframes orbFloat1 { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(30px,-20px) scale(1.1)} }
        @keyframes orbFloat2 { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(-25px,30px) scale(0.95)} }
      `}</style>

      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: '-10%', left: '-10%', width: 340, height: 340, borderRadius: '50%', background: `radial-gradient(circle, ${C.cyan}22 0%, transparent 70%)`, animation: 'orbFloat1 9s ease-in-out infinite' }} />
        <div style={{ position: 'absolute', bottom: '-5%', right: '-8%', width: 280, height: 280, borderRadius: '50%', background: `radial-gradient(circle, ${C.magenta}1a 0%, transparent 70%)`, animation: 'orbFloat2 11s ease-in-out infinite' }} />
      </div>

      {renderContent()}
    </div>
  );
}
