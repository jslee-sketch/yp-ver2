import React from 'react';

type BadgeVariant = 'live' | 'premium' | 'matching' | 'below' | 'time' | 'spectator' | 'closed' | 'custom';

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

const styles: Record<BadgeVariant, React.CSSProperties> = {
  live: {
    background: 'rgba(0,230,118,0.12)',
    color: 'var(--accent-green)',
    border: '1px solid rgba(0,230,118,0.2)',
  },
  premium: {
    background: 'rgba(0,230,118,0.15)',
    color: 'var(--accent-green)',
    border: '1px solid rgba(0,230,118,0.3)',
  },
  matching: {
    background: 'rgba(0,176,255,0.1)',
    color: 'var(--accent-blue)',
    border: '1px solid rgba(0,176,255,0.2)',
  },
  below: {
    background: 'transparent',
    color: 'var(--text-muted)',
    border: '1px solid var(--border-subtle)',
  },
  time: {
    background: 'transparent',
    color: 'var(--accent-orange)',
    border: 'none',
  },
  spectator: {
    background: 'transparent',
    color: 'var(--text-muted)',
    border: 'none',
  },
  closed: {
    background: 'rgba(96,125,139,0.15)',
    color: 'var(--text-muted)',
    border: '1px solid rgba(96,125,139,0.2)',
  },
  custom: {},
};

export const Badge: React.FC<BadgeProps> = ({ variant, children, className, style }) => {
  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '3px',
        fontSize: '10px',
        fontWeight: 700,
        letterSpacing: '0.5px',
        padding: '2px 8px',
        borderRadius: '20px',
        whiteSpace: 'nowrap',
        ...styles[variant],
        ...style,
      }}
    >
      {children}
    </span>
  );
};
