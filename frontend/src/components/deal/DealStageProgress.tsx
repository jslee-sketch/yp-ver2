import React, { useState, useEffect, useCallback } from 'react';
import type { DealStage } from '../../types';

interface DealStageProgressProps {
  stages: DealStage[];
  currentStageKey: string;
  deadlineAt?: string | null;
}

// ── 타이머 유틸 ────────────────────────────────────────
function formatCountdown(deadline: string | null): string {
  if (!deadline) return '';
  const diff = new Date(deadline).getTime() - Date.now();
  if (diff <= 0) return '마감됨';
  const totalSec = Math.floor(diff / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatDeadlineLabel(deadline: string): string {
  const d = new Date(deadline);
  const DAY = ['일', '월', '화', '수', '목', '금', '토'];
  const mo = d.getMonth() + 1;
  const dt = d.getDate();
  const dy = DAY[d.getDay()];
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `마감: ${mo}/${dt}(${dy}) ${hh}:${mm}`;
}

function getUrgencyClass(diff: number): string {
  const min = diff / 60000;
  if (min <= 10) return 'blink-fast';
  if (min <= 60) return 'blink-slow';
  return '';
}

function getUrgencyColor(diff: number): string {
  const h = diff / 3600000;
  if (h <= 3)  return 'var(--accent-red)';
  if (h <= 12) return 'var(--accent-orange)';
  if (h <= 24) return 'var(--text-secondary)';
  return 'var(--text-muted)';
}

// ── 컴포넌트 ──────────────────────────────────────────
export const DealStageProgress: React.FC<DealStageProgressProps> = ({
  stages,
  currentStageKey,
  deadlineAt,
}) => {
  const [countdown, setCountdown] = useState(() => formatCountdown(deadlineAt ?? null));
  const [showDeadlineLabel, setShowDeadlineLabel] = useState(false);

  const tick = useCallback(() => {
    setCountdown(formatCountdown(deadlineAt ?? null));
  }, [deadlineAt]);

  useEffect(() => {
    if (!deadlineAt) return;
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [deadlineAt, tick]);

  const diff = deadlineAt ? new Date(deadlineAt).getTime() - Date.now() : Infinity;
  const urgencyColor = getUrgencyColor(diff);
  const urgencyClass = getUrgencyClass(diff);

  const currentIdx = stages.findIndex(s => s.key === currentStageKey);

  return (
    <div style={{
      margin: '0 16px 16px',
      padding: '14px 16px',
      background: 'var(--bg-tertiary)',
      border: '1px solid var(--border-subtle)',
      borderRadius: 'var(--radius-md)',
    }}>
      {/* 단계 진행 바 */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        position: 'relative',
        marginBottom: deadlineAt ? 12 : 0,
      }}>
        {stages.map((stage, idx) => {
          const isCurrent = stage.key === currentStageKey;
          const isPast    = idx < currentIdx;
          const isFuture  = idx > currentIdx;

          return (
            <React.Fragment key={stage.key}>
              {/* 연결선 (첫 번째 원 제외) */}
              {idx > 0 && (
                <div style={{
                  flex: 1,
                  height: 2,
                  background: isPast || isCurrent ? 'var(--accent-green)' : 'var(--bg-elevated)',
                  transition: 'background 0.4s ease',
                }} />
              )}

              {/* 단계 원 + 라벨 */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
                <div
                  className={isCurrent ? 'pulse-dot' : ''}
                  style={{
                    width: isCurrent ? 14 : 10,
                    height: isCurrent ? 14 : 10,
                    borderRadius: '50%',
                    background: isPast
                      ? 'var(--accent-green)'
                      : isCurrent
                        ? 'var(--accent-green)'
                        : 'var(--bg-elevated)',
                    border: isCurrent
                      ? '2px solid var(--accent-green)'
                      : isPast
                        ? 'none'
                        : '2px solid var(--border-subtle)',
                    transition: 'all 0.3s ease',
                    flexShrink: 0,
                  }}
                />
                <span style={{
                  fontSize: 9,
                  fontWeight: isCurrent ? 700 : 400,
                  color: isCurrent
                    ? 'var(--accent-green)'
                    : isPast
                      ? 'var(--text-muted)'
                      : 'var(--text-disabled)',
                  whiteSpace: 'nowrap',
                  letterSpacing: '-0.2px',
                  opacity: isFuture ? 0.5 : 1,
                }}>
                  {stage.label}
                </span>
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {/* 카운트다운 타이머 */}
      {deadlineAt && countdown && (
        <button
          onClick={() => setShowDeadlineLabel(p => !p)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            background: 'none',
            padding: 0,
            cursor: 'pointer',
          }}
        >
          <span style={{ fontSize: 13 }}>⏱️</span>
          <span
            className={urgencyClass}
            style={{
              fontSize: 15,
              fontWeight: 800,
              color: urgencyColor,
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: '0.5px',
              fontFamily: 'inherit',
            }}
          >
            {showDeadlineLabel && deadlineAt
              ? formatDeadlineLabel(deadlineAt)
              : `${countdown} 남음`}
          </span>
        </button>
      )}
    </div>
  );
};
