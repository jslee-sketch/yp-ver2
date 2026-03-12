export default function ErrorState({
  message = '데이터를 불러오지 못했습니다',
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '60px 24px', textAlign: 'center',
    }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>😵</div>
      <div style={{
        fontSize: 15, fontWeight: 600, color: 'var(--text-secondary)',
        marginBottom: onRetry ? 20 : 0, lineHeight: 1.5,
      }}>
        {message}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            padding: '10px 24px', borderRadius: 'var(--radius-full, 9999px)',
            background: 'rgba(255,82,82,0.12)',
            border: '1px solid #ff5252',
            color: '#ff5252',
            fontSize: 14, fontWeight: 700, cursor: 'pointer',
            transition: 'all 0.15s',
          }}
        >
          다시 시도
        </button>
      )}
    </div>
  );
}
