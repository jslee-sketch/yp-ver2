import React from 'react';

interface PriceTextProps {
  amount: number;
  size?: 'display-lg' | 'display-md' | 'display-sm' | 'heading-lg' | 'body-md';
  color?: string;
  strikethrough?: boolean;
  showWon?: boolean;
  className?: string;
}

const sizeMap: Record<string, React.CSSProperties> = {
  'display-lg': { fontSize: '28px', fontWeight: 800, lineHeight: 1.0 },
  'display-md': { fontSize: '22px', fontWeight: 800, lineHeight: 1.0 },
  'display-sm': { fontSize: '20px', fontWeight: 800, lineHeight: 1.2 },
  'heading-lg': { fontSize: '16px', fontWeight: 700 },
  'body-md':    { fontSize: '14px', fontWeight: 400 },
};

export const PriceText: React.FC<PriceTextProps> = ({
  amount,
  size = 'display-md',
  color,
  strikethrough = false,
  showWon = true,
  className,
}) => {
  const formatted = amount.toLocaleString('ko-KR');
  return (
    <span
      className={`tabular-nums ${className ?? ''}`}
      style={{
        ...sizeMap[size],
        color: color ?? 'var(--text-primary)',
        textDecoration: strikethrough ? 'line-through' : 'none',
        opacity: strikethrough ? 0.5 : 1,
      }}
    >
      {formatted}{showWon ? '원' : ''}
    </span>
  );
};
