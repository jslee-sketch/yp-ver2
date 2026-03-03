import { useNavigate } from 'react-router-dom';

const C = {
  bg: 'var(--bg-primary)', text: 'var(--text-primary)',
  textDim: 'var(--text-muted)', green: 'var(--accent-green)',
};

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div style={{
      minHeight: '100dvh', background: C.bg,
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '0 24px', textAlign: 'center',
    }}>
      <div style={{ fontSize: 64, marginBottom: 16 }}>🔍</div>
      <div style={{ fontSize: 20, fontWeight: 800, color: C.text, marginBottom: 8 }}>404</div>
      <div style={{ fontSize: 14, color: C.textDim, marginBottom: 24 }}>
        페이지를 찾을 수 없어요
      </div>
      <button
        onClick={() => navigate('/')}
        style={{
          padding: '12px 24px', borderRadius: 12, fontSize: 14, fontWeight: 700,
          background: `${C.green}22`, border: `1px solid ${C.green}66`,
          color: C.green, cursor: 'pointer',
        }}
      >
        홈으로 돌아가기
      </button>
    </div>
  );
}
