import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

const LEVEL_DATA = [
  { level: 'Lv.1', minOrders: 100, minRating: 4.5, fee: 2.0, color: '#00e676' },
  { level: 'Lv.2', minOrders: 100, minRating: 4.0, fee: 2.5, color: '#66ffa6' },
  { level: 'Lv.3', minOrders: 61,  minRating: 4.0, fee: 2.7, color: '#00b0ff' },
  { level: 'Lv.4', minOrders: 41,  minRating: 4.0, fee: 2.8, color: '#82b1ff' },
  { level: 'Lv.5', minOrders: 21,  minRating: 4.0, fee: 3.0, color: '#ff9100' },
  { level: 'Lv.6', minOrders: 0,   minRating: 0.0, fee: 3.5, color: '#78909c' },
];

interface LevelInfo {
  level: string;
  fee_percent: number;
  rating_adjusted: number;
  rating_count: number;
  total_orders: number;
}

export default function SellerFeesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const sellerId = user?.seller?.id ?? user?.id ?? 0;
  const [myLevel, setMyLevel] = useState<LevelInfo | null>(null);

  useEffect(() => {
    if (!sellerId) return;
    apiClient.get(API.REVIEWS.LEVEL(sellerId))
      .then(res => setMyLevel(res.data))
      .catch(() => {});
  }, [sellerId]);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>수수료 안내</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0', maxWidth: 800, margin: '0 auto' }}>
        {/* 내 현재 등급 */}
        {myLevel && (
          <div style={{
            background: C.bgCard, border: `1px solid ${C.border}`, borderTop: `3px solid ${C.green}`,
            borderRadius: 16, padding: 16, marginBottom: 16, textAlign: 'center',
          }}>
            <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>현재 내 등급</div>
            <div style={{ fontSize: 28, fontWeight: 800, color: C.green, marginBottom: 4 }}>{myLevel.level}</div>
            <div style={{ fontSize: 13, color: C.text, fontWeight: 700 }}>
              플랫폼 수수료: {myLevel.fee_percent}%
            </div>
            <div style={{ fontSize: 11, color: C.textDim, marginTop: 8 }}>
              평점 {myLevel.rating_adjusted.toFixed(1)} ({myLevel.rating_count}건) · 거래 {myLevel.total_orders}건
            </div>
          </div>
        )}

        {/* 등급별 수수료 표 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16,
          padding: 16, marginBottom: 16,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>등급별 플랫폼 수수료</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th style={{ padding: '8px 6px', textAlign: 'left', color: C.textDim, fontWeight: 600 }}>등급</th>
                  <th style={{ padding: '8px 6px', textAlign: 'center', color: C.textDim, fontWeight: 600 }}>수수료</th>
                  <th style={{ padding: '8px 6px', textAlign: 'center', color: C.textDim, fontWeight: 600 }}>최소 거래</th>
                  <th style={{ padding: '8px 6px', textAlign: 'center', color: C.textDim, fontWeight: 600 }}>최소 평점</th>
                </tr>
              </thead>
              <tbody>
                {LEVEL_DATA.map(lv => {
                  const isMine = myLevel?.level === lv.level;
                  return (
                    <tr key={lv.level} style={{
                      borderBottom: `1px solid ${C.border}`,
                      background: isMine ? `${C.green}0a` : 'transparent',
                    }}>
                      <td style={{ padding: '10px 6px', fontWeight: 700, color: lv.color }}>
                        {lv.level} {isMine && '← 현재'}
                      </td>
                      <td style={{ padding: '10px 6px', textAlign: 'center', fontWeight: 700, color: C.text }}>{lv.fee}%</td>
                      <td style={{ padding: '10px 6px', textAlign: 'center', color: C.textSec }}>{lv.minOrders}건 이상</td>
                      <td style={{ padding: '10px 6px', textAlign: 'center', color: C.textSec }}>{lv.minRating > 0 ? `${lv.minRating} 이상` : '-'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* 추가 수수료 안내 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16,
          padding: 16,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 12 }}>기타 수수료</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: C.textSec }}>PG 결제 수수료</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>3.3%</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 13, color: C.textSec }}>부가세 (VAT)</span>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>10%</span>
            </div>
            <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 10, marginTop: 4 }}>
              <div style={{ fontSize: 11, color: C.textDim, lineHeight: 1.6 }}>
                * 플랫폼 수수료는 정산액 기준으로 부과됩니다.<br />
                * PG 수수료는 결제액 기준으로 PG사에서 차감됩니다.<br />
                * VAT는 플랫폼 수수료에 대해 부과됩니다.<br />
                * 등급은 누적 거래수와 평점을 기반으로 자동 산정됩니다.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
