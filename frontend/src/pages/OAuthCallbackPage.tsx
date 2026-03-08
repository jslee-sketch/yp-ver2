import { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  bgDeep: '#0a0a0f',
  text: '#e8eaed',
  textDim: '#78909c',
  green: '#00e676',
  cyan: '#00e5ff',
};

export default function OAuthCallbackPage() {
  const { provider } = useParams<{ provider: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [error, setError] = useState('');
  const [processing, setProcessing] = useState(true);

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');

    if (!code || !provider) {
      setError('인증 코드를 받지 못했어요');
      setProcessing(false);
      return;
    }

    void (async () => {
      try {
        // 백엔드에 코드 교환 요청
        const res = await apiClient.post(`/auth/social/${provider}/callback`, {
          code,
          state,
        });

        const { access_token, is_new_user, social_provider: sp, social_id, social_email, social_name } = res.data as {
          access_token: string | null;
          is_new_user: boolean;
          social_provider?: string;
          social_id?: string;
          social_email?: string;
          social_name?: string;
        };

        if (is_new_user || !access_token) {
          // 신규: 소셜 정보 저장 → 회원가입 페이지
          localStorage.setItem('social_pending', JSON.stringify({
            provider: sp || provider,
            social_id: social_id || '',
            email: social_email || '',
            name: social_name || '',
          }));
          navigate(`/register?method=${provider}`, { replace: true });
          return;
        }

        // 기존 유저: JWT 설정
        apiClient.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;

        // 프로필 가져오기 (buyer → seller → actuator 순서 시도)
        let profileOk = false;
        try {
          const buyerRes = await apiClient.get(API.BUYERS.PROFILE);
          const b = buyerRes.data;
          login(access_token, {
            id: b.id,
            email: b.email,
            name: b.name || b.nickname || '',
            nickname: b.nickname,
            role: 'buyer',
            level: b.level ?? 1,
            points: b.points ?? 0,
            trust_tier: b.trust_tier,
            social_provider: provider,
          });
          profileOk = true;
        } catch { /* not a buyer */ }

        if (!profileOk) {
          try {
            const sellerRes = await apiClient.get(API.SELLERS.PROFILE);
            const s = sellerRes.data;
            login(access_token, {
              id: s.id,
              email: s.email,
              name: s.business_name || s.nickname || '',
              nickname: s.nickname,
              role: 'seller',
              level: s.level ?? 6,
              points: s.points ?? 0,
              social_provider: provider,
            });
            profileOk = true;
          } catch { /* not a seller */ }
        }

        if (!profileOk) {
          try {
            const actRes = await apiClient.get(API.ACTUATORS.PROFILE);
            const a = actRes.data;
            login(access_token, {
              id: a.id,
              email: a.email,
              name: a.name || a.nickname || '',
              nickname: a.nickname,
              role: 'actuator',
              level: 1,
              points: 0,
              social_provider: provider,
            });
            profileOk = true;
          } catch { /* fallback */ }
        }

        if (!profileOk) {
          login(access_token, {
            id: 0,
            email: social_email || '',
            name: provider,
            role: 'buyer',
            level: 1,
            points: 0,
            social_provider: provider,
          });
        }

        navigate('/', { replace: true });
      } catch (err: unknown) {
        const e = err as { response?: { data?: { detail?: string } } };
        setError(e.response?.data?.detail ?? '소셜 로그인에 실패했어요');
        setProcessing(false);
      }
    })();
  }, [provider, searchParams]); // eslint-disable-line

  return (
    <div style={{
      minHeight: '100dvh', background: C.bgDeep,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '0 24px',
    }}>
      {processing && !error && (
        <>
          <div style={{
            width: 48, height: 48, borderRadius: '50%',
            border: `3px solid ${C.green}`,
            borderTopColor: 'transparent',
            animation: 'spin 0.8s linear infinite',
            marginBottom: 20,
          }} />
          <style>{`@keyframes spin { 100% { transform: rotate(360deg) } }`}</style>
          <div style={{ fontSize: 14, color: C.text, marginBottom: 4 }}>
            {provider} 로그인 처리 중...
          </div>
          <div style={{ fontSize: 12, color: C.textDim }}>잠시만 기다려주세요</div>
        </>
      )}

      {error && (
        <>
          <div style={{ fontSize: 40, marginBottom: 16 }}>😥</div>
          <div style={{ fontSize: 14, color: '#ff5252', marginBottom: 8 }}>{error}</div>
          <button
            onClick={() => navigate('/login', { replace: true })}
            style={{
              padding: '12px 24px', borderRadius: 12, fontSize: 14, fontWeight: 700,
              background: `${C.green}22`, border: `1px solid ${C.green}66`,
              color: C.green, cursor: 'pointer', marginTop: 12,
            }}
          >
            로그인 페이지로 돌아가기
          </button>
        </>
      )}
    </div>
  );
}
