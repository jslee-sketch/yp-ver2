import { useNavigate } from 'react-router-dom';

const C = {
  bg: 'var(--bg-primary)', text: 'var(--text-primary)',
  textDim: 'var(--text-muted)', green: 'var(--accent-green)',
};

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div className="gradient-bg" style={{
      minHeight: '100dvh',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '0 24px', textAlign: 'center',
    }}>
      <div className="fade-in-up" style={{ fontSize: 80, marginBottom: 16 }}>🏓</div>
      <div className="fade-in-up" style={{ fontSize: 28, fontWeight: 900, color: C.text, marginBottom: 8, animationDelay: '0.1s' }}>
        404 — 아웃!
      </div>
      <div className="fade-in-up" style={{ fontSize: 14, color: C.textDim, marginBottom: 32, animationDelay: '0.2s' }}>
        페이지를 찾을 수 없어요
      </div>
      <button
        className="premium-card fade-in-up"
        onClick={() => navigate('/')}
        style={{
          padding: '14px 32px', borderRadius: 14, fontSize: 15, fontWeight: 700,
          background: `${C.green}22`, border: `1px solid ${C.green}66`,
          color: C.green, cursor: 'pointer', animationDelay: '0.3s',
        }}
      >
        홈으로 돌아가기
      </button>
    </div>
  );
}
