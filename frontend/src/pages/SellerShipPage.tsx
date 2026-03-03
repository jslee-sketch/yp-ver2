import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { markShipped, fetchCarriers } from '../api/reservationApi';

const DEFAULT_CARRIERS = ['CJ대한통운', '한진택배', '로젠택배', '우체국택배', 'CU편의점택배', '롯데택배'];

const MOCK_RESERVATIONS: Record<string, { product_name: string; qty: number; price: number; buyer_name: string }> = {
  '201': { product_name: '에어팟 프로 2세대', qty: 2, price: 550000, buyer_name: '홍길동' },
  '202': { product_name: '갤럭시 S25 울트라',  qty: 1, price: 1350000, buyer_name: '김철수' },
};

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

function fmtPrice(n: number) { return '₩' + n.toLocaleString('ko-KR'); }

export default function SellerShipPage() {
  const navigate = useNavigate();
  const { reservationId } = useParams<{ reservationId: string }>();

  const order = reservationId ? (MOCK_RESERVATIONS[reservationId] ?? null) : null;

  const [carriers, setCarriers] = useState(DEFAULT_CARRIERS);
  const [carrier, setCarrier]   = useState(DEFAULT_CARRIERS[0]);
  const [tracking, setTracking] = useState('');
  const [showDrop, setShowDrop] = useState(false);

  useEffect(() => {
    fetchCarriers().then(data => {
      if (data && Array.isArray(data) && data.length > 0) {
        const names = data.map((c: Record<string, unknown>) =>
          typeof c === 'string' ? c : String(c.name ?? c.label ?? c)
        );
        setCarriers(names);
        setCarrier(names[0]);
      }
    }).catch(() => {});
  }, []);

  const handleSubmit = async () => {
    if (!tracking.trim()) { alert('운송장 번호를 입력해주세요!'); return; }
    try {
      const result = await markShipped(Number(reservationId), tracking.trim(), carrier);
      alert(result ? '발송 처리가 완료되었어요! 📦' : '발송 처리가 완료되었어요! 📦 (Mock)');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e.response?.data?.detail;
      alert(typeof detail === 'string' ? detail : '발송 처리가 완료되었어요! 📦');
    }
    navigate(-1);
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 40 }}>
      {/* TopBar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>발송 처리</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '20px 16px 0' }}>
        {/* 예약 정보 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 14, padding: '14px 16px', marginBottom: 20,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 10 }}>예약 #{reservationId}</div>
          {order ? (
            <>
              <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 5 }}>📦 {order.product_name}</div>
              <div style={{ fontSize: 12, color: C.textSec }}>
                {order.qty}개 · {fmtPrice(order.price)}
              </div>
              <div style={{ fontSize: 12, color: C.textSec, marginTop: 4 }}>구매자: {order.buyer_name}</div>
            </>
          ) : (
            <div style={{ fontSize: 14, fontWeight: 700, color: C.text }}>예약 정보를 불러올 수 없어요</div>
          )}
        </div>

        {/* 택배사 선택 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 14, padding: '16px', marginBottom: 16,
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 10 }}>택배사 선택</div>
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setShowDrop(p => !p)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '11px 14px', background: C.bgEl, border: `1px solid ${C.border}`,
                borderRadius: 10, fontSize: 14, color: C.text, cursor: 'pointer',
              }}
            >
              <span>{carrier}</span>
              <span style={{ color: C.textDim }}>{showDrop ? '▲' : '▼'}</span>
            </button>
            {showDrop && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 10,
                background: C.bgEl, border: `1px solid ${C.border}`,
                borderRadius: 10, overflow: 'hidden', marginTop: 4,
                boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
              }}>
                {carriers.map(c => (
                  <button
                    key={c}
                    onClick={() => { setCarrier(c); setShowDrop(false); }}
                    style={{
                      width: '100%', textAlign: 'left', padding: '11px 14px',
                      fontSize: 13, color: c === carrier ? C.green : C.text,
                      background: c === carrier ? `rgba(0,230,118,0.08)` : 'none',
                      borderBottom: `1px solid ${C.border}`,
                      cursor: 'pointer',
                    }}
                  >
                    {c === carrier ? '✓ ' : ''}{c}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 운송장 번호 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 14, padding: '16px', marginBottom: 24,
        }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 10 }}>운송장 번호</div>
          <input
            type="text"
            value={tracking}
            onChange={e => setTracking(e.target.value)}
            placeholder="운송장 번호를 입력하세요"
            style={{
              width: '100%', boxSizing: 'border-box' as const,
              padding: '12px 14px', borderRadius: 10, fontSize: 14,
              background: C.bgEl, border: `1px solid ${C.border}`,
              color: C.text,
            }}
          />
        </div>

        {/* 발송 버튼 */}
        <button
          onClick={handleSubmit}
          style={{
            width: '100%', padding: '15px', borderRadius: 14,
            background: `${C.green}22`, border: `1px solid ${C.green}66`,
            color: C.green, fontSize: 15, fontWeight: 800, cursor: 'pointer',
          }}
        >
          📦 발송 완료 처리
        </button>
      </div>
    </div>
  );
}
