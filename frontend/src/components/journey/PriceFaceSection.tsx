import { useEffect, useRef, useState } from 'react';
import { T } from './journeyTokens';

interface Props {
  anchor:        number;
  target:        number;
  lowestPrice:   number;
  lowestSeller:  string;
  lowestQty:     number;
  onEditTarget?: () => void;
}

export function PriceFaceSection({ anchor, target, lowestPrice, lowestSeller, lowestQty, onEditTarget }: Props) {
  const [rate, setRate]   = useState(0);
  const rafRef            = useRef<number | null>(null);
  const targetRate        = Math.max(0, Math.min(100, Math.round(((anchor - lowestPrice) / (anchor - target)) * 100)));
  const diff              = lowestPrice - target;

  useEffect(() => {
    let start: number | null = null;
    const duration = 1500;
    const tick = (ts: number) => {
      if (!start) start = ts;
      const p = Math.min((ts - start) / duration, 1);
      setRate(Math.round((1 - Math.pow(1 - p, 3)) * targetRate));
      if (p < 1) rafRef.current = requestAnimationFrame(tick);
    };
    const tid = setTimeout(() => { rafRef.current = requestAnimationFrame(tick); }, 500);
    return () => { clearTimeout(tid); if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [targetRate]);

  const fillPct  = Math.min(Math.max(rate, 0), 100);
  const dotLeft  = `${Math.min(Math.max(fillPct, 2), 97)}%`;

  return (
    <div style={{
      margin: '0 16px', background: T.bgCard,
      border: `1px solid ${T.border}`, borderRadius: 20,
      padding: '24px 20px', position: 'relative', overflow: 'hidden',
    }}>
      {/* decorative glow */}
      <div style={{
        position: 'absolute', top: -60, right: -60, width: 160, height: 160,
        background: 'radial-gradient(circle, rgba(0,240,255,0.05), transparent 70%)',
        pointerEvents: 'none',
      }} />

      {/* ── Two price boxes ── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <div style={{
          flex: 1, borderRadius: 14, padding: '16px 14px', textAlign: 'center',
          background: 'rgba(0,240,255,0.08)', border: '1px solid rgba(0,240,255,0.2)',
          position: 'relative',
        }}>
          {onEditTarget && (
            <button
              onClick={onEditTarget}
              style={{
                position: 'absolute', top: 6, right: 6,
                fontSize: 10, fontWeight: 700,
                color: T.cyan,
                background: 'rgba(0,229,255,0.12)',
                border: '1px solid rgba(0,229,255,0.35)',
                borderRadius: 6,
                padding: '2px 7px',
                cursor: 'pointer',
                lineHeight: 1.5,
              }}
            >
              수정
            </button>
          )}
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, color: T.cyan, marginBottom: 8, fontFamily: "'Space Mono', monospace", textTransform: 'uppercase' }}>
            🏁 목표가
          </div>
          <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: 24, fontWeight: 800, color: T.cyan, lineHeight: 1 }}>
            {target.toLocaleString('ko-KR')}
          </div>
          <div style={{ fontSize: 10, marginTop: 6, color: 'rgba(0,240,255,0.6)' }}>
            100개 · 무료배송 기준
          </div>
        </div>

        <div style={{
          flex: 1, borderRadius: 14, padding: '16px 14px', textAlign: 'center',
          background: 'rgba(57,255,20,0.06)', border: '1px solid rgba(57,255,20,0.2)',
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: 1, color: T.green, marginBottom: 8, fontFamily: "'Space Mono', monospace", textTransform: 'uppercase' }}>
            ⛵ 최저 오퍼
          </div>
          <div style={{ fontFamily: "'Outfit', sans-serif", fontSize: 24, fontWeight: 800, color: T.green, lineHeight: 1 }}>
            {lowestPrice.toLocaleString('ko-KR')}
          </div>
          <div style={{ fontSize: 10, marginTop: 6, color: 'rgba(57,255,20,0.6)' }}>
            {lowestSeller} · {lowestQty}개 기준
          </div>
        </div>
      </div>

      {/* ── Gap badge ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20, padding: '10px 0' }}>
        <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, transparent, #4a5568, transparent)' }} />
        <div style={{
          background: T.bgSurface, border: `1px solid ${T.border}`,
          borderRadius: 20, padding: '6px 14px',
          fontSize: 12, fontWeight: 600, color: T.yellow, whiteSpace: 'nowrap',
        }}>
          {diff > 0
            ? `차이 ${diff.toLocaleString('ko-KR')}원`
            : `목표가 달성! −${Math.abs(diff).toLocaleString('ko-KR')}원 저렴`}
        </div>
        <div style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, transparent, #4a5568, transparent)' }} />
      </div>

      {/* ── Journey track ── */}
      <div style={{ position: 'relative', height: 52, margin: '0 4px' }}>
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, display: 'flex', justifyContent: 'space-between', fontSize: 10, color: T.textSec }}>
          <span>시장가</span>
          <span style={{ color: T.cyan }}>목표가</span>
        </div>
        <div style={{
          position: 'absolute', top: 18, left: 0, right: 0, height: 6,
          background: T.bgSurface, borderRadius: 3, overflow: 'hidden',
        }}>
          <div style={{
            height: '100%', borderRadius: 3,
            background: 'linear-gradient(90deg, #ff2d78, #ff8c42, #39ff14)',
            width: `${fillPct}%`,
            transition: 'width 1.5s cubic-bezier(0.22,1,0.36,1)',
            boxShadow: '0 0 10px rgba(57,255,20,0.3)',
          }} />
        </div>
        <div style={{
          position: 'absolute', top: 30, left: dotLeft,
          transform: 'translateX(-50%)',
          fontFamily: "'Space Mono', monospace", fontSize: 11, fontWeight: 700, color: T.green,
          transition: 'left 1.5s cubic-bezier(0.22,1,0.36,1)',
          whiteSpace: 'nowrap',
        }}>
          {rate}%
        </div>
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, display: 'flex', justifyContent: 'space-between', fontSize: 10 }}>
          <span style={{ color: T.textDim }}>₩{anchor.toLocaleString('ko-KR')}</span>
          <span style={{ color: T.cyan }}>₩{target.toLocaleString('ko-KR')}</span>
        </div>
      </div>

      {/* ── Arrival callout ── */}
      <div style={{
        marginTop: 16, padding: '12px 14px',
        background: T.bgSurface, borderRadius: 12,
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          fontFamily: "'Outfit', sans-serif", fontSize: 32, fontWeight: 800,
          background: 'linear-gradient(135deg, #ff2d78, #00f0ff)',
          WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          backgroundClip: 'text', lineHeight: 1,
        }}>
          {rate}%
        </div>
        <div style={{ fontSize: 12, color: T.textSec, lineHeight: 1.7 }}>
          시장가에서 목표가까지<br />
          <strong style={{ color: T.text }}>{targetRate}% 지점</strong>에 와 있어요
        </div>
      </div>
    </div>
  );
}
