import { useEffect, useRef, useState } from 'react';
import { T } from './journeyTokens';

/**
 * 공동구매 기대가격 곡선
 * P(n) = marketPrice - (marketPrice - targetPrice) * (n / qTarget)^0.7
 * n=0 → 시장가, n=qTarget → 목표가
 */
function groupPrice(q: number, anchor: number, qTarget: number, target?: number): number {
  if (qTarget <= 0) return anchor;
  const t = target ?? anchor * 0.9;
  const ratio = Math.min(1, Math.max(0, q / qTarget));
  return anchor - (anchor - t) * Math.pow(ratio, 0.7);
}

interface Props {
  anchor:          number;
  target:          number;
  currentQ:        number;
  qTarget:         number;
  lowestOfferPrice: number;
}

export function GroupCurveSection({ anchor, target, currentQ, qTarget, lowestOfferPrice }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const dragRef   = useRef({ active: false, q: currentQ });
  const [readoutQ, setReadoutQ] = useState(currentQ);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const MAX_Q = 150;
    const PL = 52, PR = 20, PT = 20, PB = 28;
    const dpr = window.devicePixelRatio || 1;

    let W = 0, H = 0, cW = 0, cH = 0;
    let pMin = 0, pRange = 0;

    const qToX  = (q: number) => PL + (q / MAX_Q) * cW;
    const pToY  = (p: number) => PT + (1 - (p - pMin) / pRange) * cH;
    const xToQ  = (x: number) => Math.max(1, Math.min(MAX_Q, Math.round(((x - PL) / cW) * MAX_Q)));

    function draw(hQ: number) {
      const ctx = canvas!.getContext('2d');
      if (!ctx) return;

      ctx.clearRect(0, 0, W * dpr, H * dpr);

      // Grid horizontals
      const grids = [pMin, target, anchor].concat(
        [280000, 300000, 320000, 340000].filter(p => p > pMin && p < anchor + 8000)
      );
      [...new Set(grids)].forEach(p => {
        const y = pToY(p);
        ctx.strokeStyle = 'rgba(74,85,104,0.25)';
        ctx.lineWidth = 0.5;
        ctx.setLineDash([]);
        ctx.beginPath(); ctx.moveTo(PL, y); ctx.lineTo(W - PR, y); ctx.stroke();
        ctx.fillStyle = '#4a5568';
        ctx.font = '9px "Space Mono", monospace';
        ctx.textAlign = 'right';
        ctx.fillText(`${Math.round(p / 10000)}만`, PL - 4, y + 3);
      });

      // X axis labels
      ctx.fillStyle = '#4a5568';
      ctx.font = '9px "Space Mono", monospace';
      ctx.textAlign = 'center';
      [1, 20, 50, 100, 150].forEach(q => ctx.fillText(`${q}`, qToX(q), H - 5));

      // Target line
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = 'rgba(0,240,255,0.45)';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(PL, pToY(target)); ctx.lineTo(W - PR, pToY(target)); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = 'rgba(0,240,255,0.7)';
      ctx.font = '9px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(`목표 ${(target / 10000).toFixed(1)}만`, W - PR, pToY(target) - 4);

      // Lowest offer line
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = 'rgba(57,255,20,0.35)';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(PL, pToY(lowestOfferPrice)); ctx.lineTo(W - PR, pToY(lowestOfferPrice)); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = 'rgba(57,255,20,0.65)';
      ctx.font = '9px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(`최저오퍼 ${(lowestOfferPrice / 10000).toFixed(1)}만`, PL + 4, pToY(lowestOfferPrice) - 4);

      // ── 부드러운 곡선: 300 포인트 직접 렌더링 (꺾임 제로) ──
      const CURVE_STEPS = 300;
      const keyPts: {x: number; y: number}[] = [];
      for (let i = 0; i <= CURVE_STEPS; i++) {
        const q = 1 + (MAX_Q - 1) * (i / CURVE_STEPS);
        keyPts.push({ x: qToX(q), y: pToY(groupPrice(q, anchor, qTarget, target)) });
      }

      // Catmull-Rom은 유지하되 포인트 밀도가 충분하여 직선 연결도 매끄러움
      function drawCatmullRom(points: {x:number;y:number}[], tension: number = 0.5) {
        if (points.length < 2 || !ctx) return;
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 0; i < points.length - 1; i++) {
          const p0 = points[Math.max(0, i - 1)];
          const p1 = points[i];
          const p2 = points[i + 1];
          const p3 = points[Math.min(points.length - 1, i + 2)];
          const cp1x = p1.x + (p2.x - p0.x) / (6 / tension);
          const cp1y = p1.y + (p2.y - p0.y) / (6 / tension);
          const cp2x = p2.x - (p3.x - p1.x) / (6 / tension);
          const cp2y = p2.y - (p3.y - p1.y) / (6 / tension);
          ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
        }
      }

      // Curve glow (wide soft stroke)
      ctx.beginPath();
      ctx.strokeStyle = 'rgba(255,140,66,0.12)';
      ctx.lineWidth = 12;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      drawCatmullRom(keyPts);
      ctx.stroke();

      // Curve main (sharp orange)
      ctx.beginPath();
      ctx.strokeStyle = T.orange;
      ctx.lineWidth = 2.5;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      drawCatmullRom(keyPts);
      ctx.stroke();

      // Fill under curve (subtle gradient)
      ctx.beginPath();
      drawCatmullRom(keyPts);
      ctx.lineTo(keyPts[keyPts.length - 1].x, H - PB);
      ctx.lineTo(keyPts[0].x, H - PB);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, PT, 0, H - PB);
      grad.addColorStop(0, 'rgba(255,140,66,0.08)');
      grad.addColorStop(1, 'rgba(255,140,66,0.0)');
      ctx.fillStyle = grad;
      ctx.fill();

      // Original position marker (shown when dragging away from currentQ)
      if (hQ !== currentQ) {
        const origP = groupPrice(currentQ, anchor, qTarget, target);
        const ox = qToX(currentQ), oy = pToY(origP);
        ctx.beginPath();
        ctx.arc(ox, oy, 5, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,140,66,0.25)';
        ctx.fill();
        ctx.fillStyle = 'rgba(255,140,66,0.45)';
        ctx.font = '8px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('현재', ox, oy - 10);
      }

      // qTarget projection
      const tgtP = groupPrice(qTarget, anchor, qTarget, target);
      const tgtX = qToX(qTarget);
      ctx.setLineDash([2, 3]);
      ctx.strokeStyle = 'rgba(255,140,66,0.2)';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(qToX(currentQ), pToY(groupPrice(currentQ, anchor, qTarget, target)));
      ctx.lineTo(tgtX, pToY(tgtP));
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.beginPath();
      ctx.arc(tgtX, pToY(tgtP), 4, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(255,140,66,0.35)';
      ctx.fill();
      ctx.fillStyle = 'rgba(255,140,66,0.6)';
      ctx.font = '8px "Space Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`${qTarget}개→${Math.round(tgtP / 1000)}K`, tgtX, pToY(tgtP) + 15);

      // Draggable dot
      const hP = groupPrice(hQ, anchor, qTarget, target);
      const hX = qToX(hQ), hY = pToY(hP);
      // outer ring
      ctx.beginPath();
      ctx.arc(hX, hY, 9, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255,140,66,0.35)';
      ctx.lineWidth = 2;
      ctx.stroke();
      // fill
      ctx.beginPath();
      ctx.arc(hX, hY, 5, 0, Math.PI * 2);
      ctx.fillStyle = T.orange;
      ctx.fill();
      // label
      ctx.fillStyle = T.orange;
      ctx.font = 'bold 9px "Space Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillText(`${hQ}개`, hX, hY - 18);

      // drag hint
      if (!dragRef.current.active && hQ === currentQ) {
        ctx.fillStyle = 'rgba(255,140,66,0.4)';
        ctx.font = '8px sans-serif';
        ctx.fillText('← 드래그 →', hX, hY + 21);
      }
    }

    function setup() {
      const rect = canvas!.getBoundingClientRect();
      W = rect.width; H = rect.height;
      cW = W - PL - PR; cH = H - PT - PB;
      pMin  = target - 15000;
      const pMax = anchor + 8000;
      pRange = pMax - pMin;
      canvas!.width  = W * dpr;
      canvas!.height = H * dpr;
      const ctx = canvas!.getContext('2d')!;
      ctx.scale(dpr, dpr);
      draw(dragRef.current.q);
    }

    const onPointerDown = (e: PointerEvent) => {
      const rect = canvas!.getBoundingClientRect();
      const x = e.clientX - rect.left;
      if (Math.abs(x - qToX(dragRef.current.q)) < 24) {
        dragRef.current.active = true;
        canvas!.setPointerCapture(e.pointerId);
        e.preventDefault();
      }
    };

    const onPointerMove = (e: PointerEvent) => {
      if (!dragRef.current.active) return;
      const rect = canvas!.getBoundingClientRect();
      const q = xToQ(e.clientX - rect.left);
      dragRef.current.q = q;
      setReadoutQ(q);
      draw(q);
    };

    const onPointerUp = () => { dragRef.current.active = false; };

    const ro = new ResizeObserver(setup);
    ro.observe(canvas);
    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup',   onPointerUp);
    window.addEventListener('pointerup',   onPointerUp);

    return () => {
      ro.disconnect();
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup',   onPointerUp);
      window.removeEventListener('pointerup',   onPointerUp);
    };
  }, [anchor, target, currentQ, qTarget, lowestOfferPrice]);

  const dragP          = Math.round(groupPrice(readoutQ, anchor, qTarget, target));
  const diffFromTarget = dragP - target;
  const currentGP      = Math.round(groupPrice(currentQ, anchor, qTarget, target));
  const savingVsCurrent = currentGP - dragP;

  return (
    <div style={{
      margin: '14px 16px 0',
      background: T.bgCard, border: `1px solid ${T.border}`,
      borderRadius: 20, padding: 20,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(255,140,66,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>
          📈
        </div>
        <div style={{ fontSize: 13, fontWeight: 700, color: T.text }}>공동구매 기대가격 곡선</div>
      </div>
      <div style={{ fontSize: 11, color: T.textSec, marginBottom: 14, paddingLeft: 36, lineHeight: 1.55 }}>
        참여 수량이 늘수록 기대할 수 있는 가격이에요. 오렌지 점을 <strong style={{ color: T.orange }}>드래그</strong>해서 시뮬레이션하세요.
      </div>

      <canvas
        ref={canvasRef}
        style={{ width: '100%', height: 215, display: 'block', cursor: 'grab', touchAction: 'pan-y' }}
      />

      {/* Legend */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 14, fontSize: 10, color: T.textSec, margin: '8px 0' }}>
        {([
          { color: T.orange, label: '공동구매 기대가' },
          { color: T.cyan,   label: '목표가' },
          { color: T.green,  label: '최저 오퍼' },
        ] as const).map(({ color, label }) => (
          <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: color, display: 'inline-block', flexShrink: 0 }} />
            {label}
          </span>
        ))}
      </div>

      {/* Readout callout */}
      <div style={{
        marginTop: 12, padding: '10px 14px',
        background: T.bgSurface, borderRadius: 10,
        display: 'flex', gap: 10, alignItems: 'flex-start',
      }}>
        <div style={{ fontSize: 22, flexShrink: 0, lineHeight: 1 }}>
          {diffFromTarget <= 0 ? '🎯' : '📦'}
        </div>
        <div style={{ fontSize: 11, color: T.textSec, lineHeight: 1.7 }}>
          <strong style={{ color: T.text }}>{readoutQ}개</strong> 참여 시 공동구매 기대가:{' '}
          <span style={{ color: T.orange, fontFamily: "'Space Mono', monospace", fontWeight: 700 }}>
            ₩{dragP.toLocaleString('ko-KR')}
          </span>
          <br />
          {diffFromTarget <= 0 ? (
            <span style={{ color: T.green, fontWeight: 700 }}>🎯 목표가 달성! {Math.abs(diffFromTarget).toLocaleString('ko-KR')}원 아래예요</span>
          ) : (
            <>
              목표가보다{' '}
              <span style={{ color: T.yellow, fontFamily: "'Space Mono', monospace" }}>+{diffFromTarget.toLocaleString('ko-KR')}원</span>
              {' '}높음
              {savingVsCurrent > 0 && (
                <> · 현재 대비{' '}
                  <span style={{ color: T.cyan, fontFamily: "'Space Mono', monospace" }}>{savingVsCurrent.toLocaleString('ko-KR')}원</span>
                  {' '}절약
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
