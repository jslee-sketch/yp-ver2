import { useState, useEffect } from 'react';

const BASE = import.meta.env.VITE_API_BASE || '';

interface DeductionItem {
  type: string;
  amount: number;
  note?: string;
}

interface SimResult {
  can_refund: boolean;
  original_amount: number;
  buyer_refund_amount: number;
  deductions: DeductionItem[];
  reason: string;
  cooling_period_days: number;
  settlement_impact?: {
    before: number;
    after: number;
    loss: number;
    fee_rate: number;
    return_shipping_burden?: number;
    platform_fee_refund?: number;
    note?: string;
  };
}

export default function RefundSimulatorPage({ role = 'buyer' }: { role?: string }) {
  const [amount, setAmount] = useState(350000);
  const [reason, setReason] = useState('buyer_change_mind');
  const [deliveryStatus, setDeliveryStatus] = useState('before_shipping');
  const [shippingMode, setShippingMode] = useState('free');
  const [shippingCost] = useState(3000);
  const [daysSince, setDaysSince] = useState(0);
  const [result, setResult] = useState<SimResult | null>(null);

  useEffect(() => {
    const params = new URLSearchParams({
      amount: String(amount), reason, delivery_status: deliveryStatus,
      shipping_mode: shippingMode, shipping_fee: String(shippingCost),
      days_since_delivery: String(daysSince), role,
    });
    fetch(`${BASE}/v3_6/refund-simulator/calculate?${params}`)
      .then(r => r.json())
      .then(setResult)
      .catch(() => {});
  }, [amount, reason, deliveryStatus, shippingMode, shippingCost, daysSince, role]);

  const reasons = [
    { value: 'buyer_change_mind', label: '단순 변심' },
    { value: 'defective', label: '품질 불량' },
    { value: 'wrong_item', label: '오배송' },
    { value: 'damaged', label: '파손' },
  ];

  const deliveryStatuses = [
    { value: 'before_shipping', label: '배송 전' },
    { value: 'in_transit', label: '배송 중' },
    { value: 'delivered', label: '수령 후' },
  ];

  const shippingModes = [
    { value: 'free', label: '무료 배송' },
    { value: 'buyer_paid', label: '구매자 부담' },
    { value: 'conditional_free', label: '조건부 무료' },
  ];

  const inputStyle = {
    width: '100%', padding: '8px 12px', borderRadius: 8,
    border: '1px solid var(--border-subtle)', background: 'var(--bg-secondary)', color: 'var(--text-primary)',
    fontSize: 14,
  };

  return (
    <div style={{ maxWidth: 500, margin: '0 auto', padding: 20 }}>
      <h2 style={{ color: 'var(--text-primary)', fontSize: 18, marginBottom: 16 }}>
        환불 시뮬레이터 {role === 'seller' ? '(판매자)' : '(구매자)'}
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
        <label style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          주문 금액
          <input type="number" value={amount} onChange={e => setAmount(+e.target.value)}
            style={{ ...inputStyle, marginTop: 4 }} />
        </label>

        <label style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          환불 사유
          <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
            {reasons.map(r => (
              <button key={r.value} onClick={() => setReason(r.value)} style={{
                padding: '6px 12px', borderRadius: 8, fontSize: 12,
                border: reason === r.value ? '1px solid #60a5fa' : '1px solid var(--border-subtle)',
                background: reason === r.value ? 'rgba(96,165,250,0.15)' : 'var(--bg-secondary)',
                color: reason === r.value ? '#60a5fa' : 'var(--text-muted)', cursor: 'pointer',
              }}>{r.label}</button>
            ))}
          </div>
        </label>

        <label style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          배송 상태
          <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
            {deliveryStatuses.map(d => (
              <button key={d.value} onClick={() => setDeliveryStatus(d.value)} style={{
                padding: '6px 12px', borderRadius: 8, fontSize: 12,
                border: deliveryStatus === d.value ? '1px solid #4ade80' : '1px solid var(--border-subtle)',
                background: deliveryStatus === d.value ? 'rgba(74,222,128,0.15)' : 'var(--bg-secondary)',
                color: deliveryStatus === d.value ? '#4ade80' : 'var(--text-muted)', cursor: 'pointer',
              }}>{d.label}</button>
            ))}
          </div>
        </label>

        <label style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          배송비 모드
          <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
            {shippingModes.map(s => (
              <button key={s.value} onClick={() => setShippingMode(s.value)} style={{
                padding: '6px 12px', borderRadius: 8, fontSize: 12,
                border: shippingMode === s.value ? '1px solid #f59e0b' : '1px solid var(--border-subtle)',
                background: shippingMode === s.value ? 'rgba(245,158,11,0.15)' : 'var(--bg-secondary)',
                color: shippingMode === s.value ? '#f59e0b' : 'var(--text-muted)', cursor: 'pointer',
              }}>{s.label}</button>
            ))}
          </div>
        </label>

        <label style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
          수령 후 경과일
          <input type="number" value={daysSince} onChange={e => setDaysSince(+e.target.value)}
            style={{ ...inputStyle, marginTop: 4 }} min={0} />
        </label>
      </div>

      {/* Result */}
      {result && (
        <div style={{
          padding: 16, borderRadius: 12,
          background: result.can_refund ? 'rgba(74,222,128,0.06)' : 'rgba(239,68,68,0.06)',
          border: `1px solid ${result.can_refund ? 'rgba(74,222,128,0.2)' : 'rgba(239,68,68,0.2)'}`,
        }}>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>
            {result.can_refund ? '환불 가능' : `환불 불가 (쿨링 ${result.cooling_period_days}일 초과)`}
          </div>

          <div style={{ fontSize: 22, fontWeight: 700, color: '#4ade80', marginBottom: 8 }}>
            {(result.buyer_refund_amount ?? 0).toLocaleString()}원
          </div>

          {result.deductions.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              {result.deductions.map((d, i) => (
                <div key={i} style={{ fontSize: 12, color: '#f59e0b' }}>
                  {d.type}: -{(d.amount ?? 0).toLocaleString()}원{d.note ? ` (${d.note})` : ''}
                </div>
              ))}
            </div>
          )}

          {reason !== 'buyer_change_mind' && (
            <div style={{ fontSize: 12, color: '#4ade80' }}>
              판매자 귀책 → 전액 환불
            </div>
          )}

          {/* Seller: Settlement Impact */}
          {result.settlement_impact && (
            <div style={{
              marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border-subtle)',
            }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                정산 영향
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                환불 전 정산금: {(result.settlement_impact.before ?? 0).toLocaleString()}원
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                환불 후 정산금: {(result.settlement_impact.after ?? 0).toLocaleString()}원
              </div>
              <div style={{ fontSize: 12, color: '#ef4444' }}>
                정산 감소: -{(result.settlement_impact.loss ?? 0).toLocaleString()}원
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
