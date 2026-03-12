export default function LoadingSpinner({ size = 40, message = '로딩 중...' }: { size?: number; message?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
      <style>{`@keyframes _spin { to { transform: rotate(360deg); } }`}</style>
      <div style={{
        width: size,
        height: size,
        border: '3px solid rgba(255,255,255,0.1)',
        borderTop: '3px solid #00ff88',
        borderRadius: '50%',
        animation: '_spin 0.8s linear infinite',
      }} />
      {message && <p style={{ marginTop: 16, fontSize: 14, color: '#888' }}>{message}</p>}
    </div>
  );
}
