import React from 'react';

interface PingpongCardProps {
  message: string;
  onAsk?: () => void;
  className?: string;
}

export const PingpongCard: React.FC<PingpongCardProps> = ({ message, onAsk, className }) => {
  return (
    <div
      className={className}
      style={{
        background: 'var(--gradient-pingpong)',
        border: '1px solid rgba(255,183,77,0.2)',
        borderRadius: 'var(--radius-md)',
        padding: 'var(--space-lg)',
      }}
    >
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 10 }}>
        <span style={{ fontSize: 20, flexShrink: 0 }}>🤖</span>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent-orange)', marginBottom: 6 }}>
            핑퐁이
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7 }}>
            {message}
          </p>
        </div>
      </div>
      {onAsk && (
        <button
          onClick={onAsk}
          style={{
            width: '100%',
            padding: '10px',
            background: 'rgba(255,183,77,0.12)',
            border: '1px solid rgba(255,183,77,0.2)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--accent-orange)',
            fontSize: 13,
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          핑퐁이에게 질문하기
        </button>
      )}
    </div>
  );
};
