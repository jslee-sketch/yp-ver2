import { createContext, useContext, useState, useCallback, useMemo } from 'react';
import type { CSSProperties, ReactNode } from 'react';

/* ──────────────────────────────────────────────────────────
 * SequentialHighlight
 * - 입력 폼에서 현재 → 다음 필드를 시각적으로 강조
 * - Provider + Step 래퍼 + useSeq() 훅
 * ────────────────────────────────────────────────────────── */

interface SeqCtx {
  current: number;
  total: number;
  complete: (step: number) => void;
  isCompleted: (step: number) => boolean;
}

const Ctx = createContext<SeqCtx>({ current: 0, total: 0, complete: () => {}, isCompleted: () => false });

export function useSeq() { return useContext(Ctx); }

interface ProviderProps {
  total: number;
  children: ReactNode;
}

export function SeqProvider({ total, children }: ProviderProps) {
  const [completed, setCompleted] = useState<Set<number>>(new Set());

  const current = useMemo(() => {
    for (let i = 0; i < total; i++) {
      if (!completed.has(i)) return i;
    }
    return total; // all done
  }, [completed, total]);

  const complete = useCallback((step: number) => {
    setCompleted(prev => {
      const next = new Set(prev);
      next.add(step);
      return next;
    });
  }, []);

  const isCompleted = useCallback((step: number) => completed.has(step), [completed]);

  return <Ctx.Provider value={{ current, total, complete, isCompleted }}>{children}</Ctx.Provider>;
}

/* ── SeqStep 래퍼 ── */
interface StepProps {
  step: number;
  children: ReactNode;
  label?: string;
  style?: CSSProperties;
}

const accentColor = 'var(--accent-green, #00e676)';
const dimOpacity = 0.35;

export function SeqStep({ step, children, label, style }: StepProps) {
  const { current, isCompleted } = useSeq();
  const done = isCompleted(step);
  const active = step === current;
  const future = step > current && !done;

  return (
    <div style={{
      position: 'relative',
      opacity: future ? dimOpacity : 1,
      transition: 'opacity 0.3s, border-color 0.3s',
      borderLeft: active ? `3px solid ${accentColor}` : done ? '3px solid rgba(0,230,118,0.25)' : '3px solid transparent',
      paddingLeft: active || done ? 12 : 12,
      marginBottom: 4,
      ...style,
    }}>
      {label && (
        <div style={{
          fontSize: 10, fontWeight: 700, letterSpacing: 0.5, marginBottom: 4,
          color: active ? accentColor : done ? 'rgba(0,230,118,0.6)' : 'var(--text-muted, #666)',
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          {done ? '✓' : `${step + 1}`} {label}
        </div>
      )}
      {children}
    </div>
  );
}

/* ── SeqProgress 바 ── */
export function SeqProgress({ style }: { style?: CSSProperties }) {
  const { current, total } = useSeq();
  const pct = total > 0 ? Math.min(100, (current / total) * 100) : 0;
  const allDone = current >= total;

  return (
    <div style={{ marginBottom: 12, ...style }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4,
      }}>
        <span style={{ fontSize: 11, fontWeight: 700, color: allDone ? accentColor : 'var(--text-secondary, #aaa)' }}>
          {allDone ? '모든 항목 완료!' : `${current}/${total} 완료`}
        </span>
      </div>
      <div style={{
        height: 3, borderRadius: 2,
        background: 'var(--bg-elevated, rgba(255,255,255,0.06))',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', borderRadius: 2,
          width: allDone ? '100%' : `${pct}%`,
          background: allDone ? accentColor : 'var(--accent-orange, #ff8c42)',
          transition: 'width 0.4s ease',
        }} />
      </div>
    </div>
  );
}
