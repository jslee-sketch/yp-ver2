export default function EmptyState({
  icon = '📭',
  message,
  sub,
  actionLabel,
  onAction,
}: {
  icon?: string;
  message: string;
  sub?: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '60px 24px', textAlign: 'center',
    }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>{icon}</div>
      <div style={{
        fontSize: 15, fontWeight: 600, color: 'var(--text-secondary)',
        marginBottom: sub ? 6 : actionLabel ? 20 : 0, lineHeight: 1.5,
      }}>
        {message}
      </div>
      {sub && (
        <div style={{
          fontSize: 13, color: 'var(--text-muted)',
          marginBottom: actionLabel ? 20 : 0, lineHeight: 1.5,
        }}>
          {sub}
        </div>
      )}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          style={{
            padding: '10px 24px', borderRadius: 'var(--radius-full)',
            background: 'var(--accent-green-bg)',
            border: '1px solid var(--accent-green)',
            color: 'var(--accent-green)',
            fontSize: 14, fontWeight: 700, cursor: 'pointer',
            transition: 'all 0.15s',
          }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
