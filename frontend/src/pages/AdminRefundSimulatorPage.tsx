import { useState } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

const inputStyle: React.CSSProperties = {
  padding: '8px 12px', borderRadius: 8, border: `1px solid var(--border-subtle)`,
  background: '#1a1a2e', color: '#e0e0e0', fontSize: 13, width: '100%',
};
const labelStyle: React.CSSProperties = { display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, fontWeight: 600 };
const radioRow: React.CSSProperties = { display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 };

function RadioGroup({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label style={labelStyle}>{label}</label>
      <div style={radioRow}>
        {options.map(o => (
          <label key={o.value} style={{
            padding: '6px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 12,
            background: value === o.value ? 'rgba(0,229,255,0.15)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${value === o.value ? C.cyan : 'var(--border-subtle)'}`,
            color: value === o.value ? C.cyan : 'var(--text-muted)',
          }}>
            <input type="radio" checked={value === o.value} onChange={() => onChange(o.value)} style={{ display: 'none' }} />
            {o.label}
          </label>
        ))}
      </div>
    </div>
  );
}

export default function AdminRefundSimulatorPage() {
  const [mode, setMode] = useState<'manual' | 'by_reservation'>('manual');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  // Manual inputs
  const [productPrice, setProductPrice] = useState(50000);
  const [shippingFee, setShippingFee] = useState(3000);
  const [quantity, setQuantity] = useState(2);
  const [refundQty, setRefundQty] = useState(1);
  const [faultParty, setFaultParty] = useState('BUYER');
  const [trigger, setTrigger] = useState('BUYER_CANCEL');
  const [coolingState, setCoolingState] = useState('BEFORE_SHIPPING');
  const [settlementState, setSettlementState] = useState('NOT_SETTLED');

  // By reservation
  const [reservationId, setReservationId] = useState('');
  const [resvFaultParty, setResvFaultParty] = useState('BUYER');
  const [resvTrigger, setResvTrigger] = useState('BUYER_CANCEL');

  const simulate = async () => {
    setLoading(true); setError(''); setResult(null);
    try {
      const body = mode === 'manual'
        ? { mode: 'manual', product_price: productPrice, shipping_fee: shippingFee, quantity, refund_quantity: refundQty, fault_party: faultParty, trigger, cooling_state: coolingState, settlement_state: settlementState }
        : { mode: 'by_reservation', reservation_id: parseInt(reservationId), fault_party: resvFaultParty, trigger: resvTrigger };
      const r = await apiClient.post(API.ADMIN.REFUND_SIMULATE, body);
      setResult(r.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || '시뮬레이션 실패');
    }
    setLoading(false);
  };

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>환불/정산 시뮬레이터</h1>

      {/* Mode tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {[{ v: 'manual' as const, l: '수동 시뮬레이션' }, { v: 'by_reservation' as const, l: '예약 조회' }].map(t => (
          <button key={t.v} onClick={() => { setMode(t.v); setResult(null); setError(''); }} style={{
            padding: '8px 20px', borderRadius: 8, border: `1px solid ${mode === t.v ? C.cyan : C.border}`,
            background: mode === t.v ? 'rgba(0,229,255,0.1)' : 'transparent',
            color: mode === t.v ? C.cyan : C.textSec, cursor: 'pointer', fontSize: 13, fontWeight: 600,
          }}>{t.l}</button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Left: Inputs */}
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 16 }}>
            {mode === 'manual' ? '조건 입력' : '예약 조회'}
          </h3>

          {mode === 'manual' ? (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div>
                  <label style={labelStyle}>상품 단가 (원)</label>
                  <input type="number" value={productPrice} onChange={e => setProductPrice(Number(e.target.value))} style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>배송비 (원)</label>
                  <input type="number" value={shippingFee} onChange={e => setShippingFee(Number(e.target.value))} style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>총 수량</label>
                  <input type="number" value={quantity} min={1} onChange={e => setQuantity(Number(e.target.value))} style={inputStyle} />
                </div>
                <div>
                  <label style={labelStyle}>환불 수량</label>
                  <input type="number" value={refundQty} min={1} max={quantity} onChange={e => setRefundQty(Number(e.target.value))} style={inputStyle} />
                </div>
              </div>

              <RadioGroup label="배송 상태" value={coolingState} onChange={setCoolingState} options={[
                { value: 'BEFORE_SHIPPING', label: '배송 전' },
                { value: 'SHIPPED_NOT_DELIVERED', label: '배송 중' },
                { value: 'WITHIN_COOLING', label: '수취 완료 (쿨링 내)' },
                { value: 'AFTER_COOLING', label: '쿨링 경과' },
              ]} />
              <RadioGroup label="귀책 사유" value={faultParty} onChange={setFaultParty} options={[
                { value: 'BUYER', label: '구매자' },
                { value: 'SELLER', label: '판매자' },
                { value: 'SYSTEM', label: '시스템' },
                { value: 'DISPUTE', label: '분쟁' },
              ]} />
              <RadioGroup label="환불 유형" value={trigger} onChange={setTrigger} options={[
                { value: 'BUYER_CANCEL', label: '구매자 취소' },
                { value: 'SELLER_CANCEL', label: '판매자 취소' },
                { value: 'ADMIN_FORCE', label: '관리자 강제' },
                { value: 'DISPUTE_RESOLVE', label: '분쟁 조정' },
              ]} />
              <RadioGroup label="정산 상태" value={settlementState} onChange={setSettlementState} options={[
                { value: 'NOT_SETTLED', label: '미정산' },
                { value: 'SETTLED_TO_SELLER', label: '정산 완료' },
              ]} />
            </>
          ) : (
            <>
              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>예약 번호 (R-###)</label>
                <input value={reservationId} onChange={e => setReservationId(e.target.value.replace(/[^0-9]/g, ''))}
                  placeholder="예약 ID 숫자만 입력" style={inputStyle} />
              </div>
              <RadioGroup label="귀책 사유" value={resvFaultParty} onChange={setResvFaultParty} options={[
                { value: 'BUYER', label: '구매자' },
                { value: 'SELLER', label: '판매자' },
                { value: 'SYSTEM', label: '시스템' },
              ]} />
              <RadioGroup label="환불 유형" value={resvTrigger} onChange={setResvTrigger} options={[
                { value: 'BUYER_CANCEL', label: '구매자 취소' },
                { value: 'SELLER_CANCEL', label: '판매자 취소' },
                { value: 'ADMIN_FORCE', label: '관리자 강제' },
                { value: 'DISPUTE_RESOLVE', label: '분쟁 조정' },
              ]} />
            </>
          )}

          <button onClick={simulate} disabled={loading || (mode === 'by_reservation' && !reservationId)} style={{
            width: '100%', padding: '12px', borderRadius: 8, border: 'none',
            background: C.cyan, color: '#000', fontWeight: 700, cursor: 'pointer', fontSize: 14, marginTop: 8,
            opacity: loading ? 0.6 : 1,
          }}>{loading ? '계산 중...' : '시뮬레이션 실행'}</button>
        </div>

        {/* Right: Result */}
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 16 }}>결과</h3>

          {error && <div style={{ padding: 12, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', borderRadius: 8, color: C.red, fontSize: 13, marginBottom: 12 }}>{error}</div>}

          {!result && !error && <div style={{ color: C.textSec, fontSize: 13, textAlign: 'center', padding: 40 }}>조건을 입력하고 시뮬레이션을 실행하세요</div>}

          {result?.error && <div style={{ padding: 12, background: 'rgba(255,82,82,0.1)', borderRadius: 8, color: C.red, fontSize: 13 }}>{result.error}</div>}

          {result && !result.error && mode === 'manual' && result.breakdown && (
            <>
              {/* Breakdown */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>환불 금액 분석</div>
                <Row label="상품 환불액" value={`${result.breakdown.goods_refund?.toLocaleString()}원`} color={C.text} />
                <Row label="배송비 자동배정 상한" value={`${result.breakdown.shipping_auto_max?.toLocaleString()}원`} color={C.textSec} />
                <Row label="배송비 정책 cap" value={`${result.breakdown.shipping_cap_by_policy?.toLocaleString()}원`} color={result.breakdown.shipping_cap_by_policy === 0 ? C.red : C.green} />
                <Row label="배송비 환불액" value={`${result.breakdown.shipping_refund?.toLocaleString()}원`} color={C.text} />
                <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 8, marginTop: 8 }}>
                  <Row label="총 환불액" value={`${result.breakdown.total_refund?.toLocaleString()}원`} color={C.green} bold />
                </div>
              </div>

              {/* Fees */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.orange, marginBottom: 8 }}>수수료</div>
                <Row label={`PG수수료 (${((result.fees?.pg_fee_rate || 0) * 100).toFixed(1)}%)`} value={`${result.fees?.pg_fee_amount?.toLocaleString()}원`} sub={`${result.fees?.pg_fee_bearer} 부담`} color={C.textSec} />
                <Row label={`플랫폼수수료 (${((result.fees?.platform_fee_rate || 0) * 100).toFixed(1)}%)`} value={`${result.fees?.platform_fee_amount?.toLocaleString()}원`} sub={`${result.fees?.platform_fee_bearer} 부담`} color={C.textSec} />
              </div>

              {/* Settlement impact */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#e040fb', marginBottom: 8 }}>정산 영향</div>
                <Row label="총 결제액" value={`${result.settlement_impact?.total_paid?.toLocaleString()}원`} color={C.text} />
                <Row label="판매자 정산 (기존)" value={`${result.settlement_impact?.seller_payout_original?.toLocaleString()}원`} color={C.textSec} />
                <Row label="판매자 정산 (환불 후)" value={`${result.settlement_impact?.seller_payout_after_refund?.toLocaleString()}원`} color={C.text} />
                <Row label="판매자 영향" value={`${result.settlement_impact?.seller_impact?.toLocaleString()}원`} color={result.settlement_impact?.seller_impact < 0 ? C.red : C.green} bold />
              </div>

              {/* Decision */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.text, marginBottom: 8 }}>정책 결정</div>
                <Row label="PG 환불 사용" value={result.decision?.use_pg_refund ? 'Y' : 'N'} color={result.decision?.use_pg_refund ? C.green : C.red} />
                <Row label="정산 회수 필요" value={result.decision?.need_settlement_recovery ? 'Y' : 'N'} color={result.decision?.need_settlement_recovery ? C.orange : C.textSec} />
                <Row label="구매자 포인트 회수" value={result.decision?.revoke_buyer_points ? 'Y' : 'N'} color={C.textSec} />
                <Row label="판매자 포인트 회수" value={result.decision?.revoke_seller_points ? 'Y' : 'N'} color={C.textSec} />
              </div>

              {/* Policy notes */}
              {result.policy_notes && (
                <div style={{ background: 'rgba(0,229,255,0.04)', border: `1px solid ${C.border}`, borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: C.textSec, marginBottom: 6 }}>정책 노트</div>
                  {result.policy_notes.map((n: string, i: number) => (
                    <div key={i} style={{ fontSize: 12, color: C.textSec, lineHeight: 1.6 }}>{n}</div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* By reservation result */}
          {result && !result.error && mode === 'by_reservation' && (
            <>
              {result.reservation_info && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>예약 정보</div>
                  <Row label="예약 ID" value={`R-${result.reservation_id}`} color={C.cyan} />
                  <Row label="상태" value={result.reservation_info.status} color={C.text} />
                  <Row label="결제 총액" value={`${result.reservation_info.amount_total?.toLocaleString()}원`} color={C.text} />
                  <Row label="상품금액" value={`${result.reservation_info.amount_goods?.toLocaleString()}원`} color={C.textSec} />
                  <Row label="배송비" value={`${result.reservation_info.amount_shipping?.toLocaleString()}원`} color={C.textSec} />
                  <Row label="수량" value={`${result.reservation_info.qty}`} color={C.textSec} />
                  <Row label="환불 수량" value={`${result.reservation_info.refunded_qty}`} color={C.textSec} />
                  <Row label="배송일" value={result.reservation_info.shipped_at || '-'} color={C.textSec} />
                  <Row label="수취확인" value={result.reservation_info.arrival_confirmed_at || '-'} color={C.textSec} />
                </div>
              )}
              {result.result && typeof result.result === 'object' && (
                <details style={{ marginTop: 8 }}>
                  <summary style={{ cursor: 'pointer', color: C.textSec, fontSize: 12 }}>상세 프리뷰 데이터</summary>
                  <pre style={{ background: '#0a0a1a', padding: 12, borderRadius: 8, fontSize: 11, color: '#888', overflow: 'auto', maxHeight: 300, marginTop: 8 }}>{JSON.stringify(result.result, null, 2)}</pre>
                </details>
              )}
            </>
          )}

          {/* Raw JSON */}
          {result && (
            <details style={{ marginTop: 12 }}>
              <summary style={{ cursor: 'pointer', color: C.textSec, fontSize: 11 }}>API 응답 원본</summary>
              <pre style={{ background: '#0a0a1a', padding: 12, borderRadius: 8, fontSize: 11, color: '#888', overflow: 'auto', maxHeight: 200, marginTop: 8 }}>{JSON.stringify(result, null, 2)}</pre>
            </details>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, sub, color, bold }: { label: string; value: string; sub?: string; color: string; bold?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '4px 0', fontSize: 13 }}>
      <span style={{ color: 'var(--text-muted)' }}>{label}</span>
      <span>
        <span style={{ color, fontWeight: bold ? 700 : 400 }}>{value}</span>
        {sub && <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 6 }}>{sub}</span>}
      </span>
    </div>
  );
}
