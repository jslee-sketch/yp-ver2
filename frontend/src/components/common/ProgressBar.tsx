import React from 'react';

interface ProgressBarProps {
  value: number;        // 0~100
  label?: string;
  showLabel?: boolean;
  height?: number;
  colorOverride?: string;
  className?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  value,
  label,
  showLabel = true,
  height = 6,
  colorOverride,
  className,
}) => {
  const capped = Math.min(value, 100);
  const isAchieved = value >= 100;

  return (
    <div className={className} style={{ width: '100%' }}>
      {showLabel && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
            {label ?? '목표 달성률'}
          </span>
          <span style={{
            fontSize: 12,
            fontWeight: 700,
            color: isAchieved ? 'var(--accent-green)' : 'var(--accent-blue)',
          }}>
            {isAchieved ? '목표 달성! 🎉' : `${Math.round(capped)}%`}
          </span>
        </div>
      )}
      <div style={{
        height,
        background: 'var(--bg-elevated)',
        borderRadius: height / 2,
        overflow: 'hidden',
      }}>
        <div
          className="progress-animate"
          style={{
            height: '100%',
            width: `${capped}%`,
            background: colorOverride ?? 'var(--gradient-saving)',
            borderRadius: height / 2,
          }}
        />
      </div>
    </div>
  );
};
