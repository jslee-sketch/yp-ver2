// 아레나 배틀맵 (Canvas 기반 파티클 맵)
import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import apiClient from '../../api/client';

const GAME_COLORS: Record<string, string> = {
  rps: '#FFD700', mjb: '#FF4444', yut: '#44BB44', math: '#4488FF', quiz: '#AA44FF', reaction: '#FF8800',
};

interface Particle {
  x: number; y: number; color: string; game_type: string; result: string; alpha: number; size: number;
}

export default function ArenaMapPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [particles, setParticles] = useState<Particle[]>([]);
  const [regions, setRegions] = useState<any[]>([]);
  const [_hovered, _setHovered] = useState<Particle | null>(null); // reserved for tooltip

  useEffect(() => {
    apiClient.get('/arena/map').then(r => {
      const ps = (r.data?.particles || []).map((p: any) => ({
        // 간단한 메르카토르 변환
        x: ((p.lng || 127) + 180) / 360,
        y: (90 - (p.lat || 37)) / 180,
        color: GAME_COLORS[p.game_type] || '#fff',
        game_type: p.game_type,
        result: p.result,
        alpha: 0.8,
        size: p.result === 'win' ? 4 : 3,
      }));
      setParticles(ps);
      setRegions(r.data?.regions || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;

    let animId: number;
    let tick = 0;

    const draw = () => {
      tick++;
      ctx.fillStyle = '#0a0a1a';
      ctx.fillRect(0, 0, W, H);

      // 격자 (대충 대륙)
      ctx.strokeStyle = '#111';
      ctx.lineWidth = 0.5;
      for (let i = 0; i < 18; i++) {
        ctx.beginPath(); ctx.moveTo(i * W / 18, 0); ctx.lineTo(i * W / 18, H); ctx.stroke();
      }
      for (let i = 0; i < 9; i++) {
        ctx.beginPath(); ctx.moveTo(0, i * H / 9); ctx.lineTo(W, i * H / 9); ctx.stroke();
      }

      // 파티클
      particles.forEach((p, idx) => {
        const px = p.x * W;
        const py = p.y * H;
        const pulse = 1 + 0.3 * Math.sin(tick * 0.05 + idx);
        ctx.beginPath();
        ctx.arc(px, py, p.size * pulse, 0, Math.PI * 2);
        ctx.fillStyle = p.color + Math.floor(p.alpha * 255).toString(16).padStart(2, '0');
        ctx.fill();

        // 글로우
        ctx.beginPath();
        ctx.arc(px, py, p.size * pulse * 2, 0, Math.PI * 2);
        const grad = ctx.createRadialGradient(px, py, 0, px, py, p.size * pulse * 2);
        grad.addColorStop(0, p.color + '44');
        grad.addColorStop(1, p.color + '00');
        ctx.fillStyle = grad;
        ctx.fill();
      });

      // 데이터 없으면 안내
      if (particles.length === 0) {
        ctx.fillStyle = '#666';
        ctx.font = '16px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('게임을 플레이하면 지도에 표시됩니다!', W / 2, H / 2);
      }

      animId = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(animId);
  }, [particles]);

  return (
    <div style={{ padding: 20, maxWidth: 800, margin: '0 auto' }}>
      <Link to="/arena" style={{ color: '#888', textDecoration: 'none' }}>← 아레나</Link>
      <h1 style={{ textAlign: 'center', color: '#4488FF', margin: '20px 0' }}>🗺️ 배틀 맵</h1>

      {/* 범례 */}
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
        {Object.entries(GAME_COLORS).map(([k, v]) => (
          <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: v, display: 'inline-block' }} />
            {k}
          </span>
        ))}
      </div>

      <canvas ref={canvasRef} width={760} height={400}
        style={{ width: '100%', borderRadius: 16, border: '1px solid #222', background: '#0a0a1a' }} />

      {/* 지역 통계 */}
      {regions.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <h3 style={{ color: '#888' }}>지역별 통계</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10 }}>
            {regions.map((r, i) => (
              <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.05 }}
                style={{ background: '#16213e', borderRadius: 10, padding: 12, textAlign: 'center' }}>
                <div style={{ fontWeight: 700 }}>{r.country} {r.region || ''}</div>
                <div style={{ fontSize: 12, color: '#888' }}>{r.total_games} games | {r.total_players} players</div>
                <div style={{ color: '#FFD700', fontSize: 14 }}>{r.composite_score?.toFixed(1)}</div>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
