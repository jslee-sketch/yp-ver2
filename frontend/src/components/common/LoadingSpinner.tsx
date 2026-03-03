export default function LoadingSpinner({ size = 40 }: { size?: number }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
      <style>{`@keyframes _spin { to { transform: rotate(360deg); } }`}</style>
      <div style={{
        width: size,
        height: size,
        border: '3px solid rgba(255,255,255,0.1)',
        borderTop: '3px solid #00ff88',
        borderRadius: '50%',
        animation: '_spin 0.8s linear infinite',
      }} />
    </div>
  );
}
