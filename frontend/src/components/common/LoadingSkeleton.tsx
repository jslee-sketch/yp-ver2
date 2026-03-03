const shimmer = `
@keyframes _shimmer {
  0%   { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}
`;

const barStyle = (w: string, h: number, mb = 8): React.CSSProperties => ({
  width: w,
  height: h,
  borderRadius: 8,
  background: 'linear-gradient(90deg, var(--bg-elevated) 25%, rgba(255,255,255,0.08) 50%, var(--bg-elevated) 75%)',
  backgroundSize: '800px 100%',
  animation: '_shimmer 1.6s ease-in-out infinite',
  marginBottom: mb,
});

function Card() {
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: 'var(--radius-lg)',
      padding: 16,
      border: '1px solid var(--border-subtle)',
    }}>
      <div style={barStyle('60%', 14)} />
      <div style={barStyle('90%', 12)} />
      <div style={barStyle('40%', 12, 0)} />
    </div>
  );
}

function Row() {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', padding: '12px 0' }}>
      <div style={{ ...barStyle('40px', 40, 0), borderRadius: '50%', flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div style={barStyle('70%', 12)} />
        <div style={barStyle('45%', 10, 0)} />
      </div>
    </div>
  );
}

type Variant = 'cards' | 'list' | 'detail';

export default function LoadingSkeleton({ variant = 'cards', count = 3 }: { variant?: Variant; count?: number }) {
  return (
    <div style={{ padding: '20px 16px' }}>
      <style>{shimmer}</style>
      {variant === 'cards' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {Array.from({ length: count }, (_, i) => <Card key={i} />)}
        </div>
      )}
      {variant === 'list' && (
        <div>
          {Array.from({ length: count }, (_, i) => <Row key={i} />)}
        </div>
      )}
      {variant === 'detail' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={barStyle('50%', 22)} />
          <div style={{
            background: 'var(--bg-secondary)',
            borderRadius: 'var(--radius-lg)',
            padding: 20,
            border: '1px solid var(--border-subtle)',
          }}>
            <div style={barStyle('80%', 14)} />
            <div style={barStyle('100%', 12)} />
            <div style={barStyle('65%', 12)} />
            <div style={{ ...barStyle('100%', 120, 0), borderRadius: 12 }} />
          </div>
          <div style={barStyle('30%', 14)} />
          <Card />
        </div>
      )}
    </div>
  );
}
