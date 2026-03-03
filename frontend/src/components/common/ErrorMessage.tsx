export default function ErrorMessage({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div style={{
      padding: 24, textAlign: 'center',
      color: 'rgba(255,255,255,0.6)', fontSize: 14,
    }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>😢</div>
      <div style={{ marginBottom: onRetry ? 16 : 0 }}>{message}</div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            padding: '8px 20px', borderRadius: 8,
            background: 'rgba(0,255,136,0.1)',
            border: '1px solid rgba(0,255,136,0.3)',
            color: '#00ff88', cursor: 'pointer', fontSize: 13,
          }}
        >
          다시 시도
        </button>
      )}
    </div>
  );
}
