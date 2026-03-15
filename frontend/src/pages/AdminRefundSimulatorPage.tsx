import { useState } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = { cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252', card: 'var(--bg-elevated)', border: 'var(--border-subtle)', text: 'var(--text-primary)', textSec: 'var(--text-muted)' };

/* ── utils ── */
function fmtNum(v: number | string): string {
  const s = String(v).replace(/[^\d]/g, '');
  return s ? Number(s).toLocaleString() : '';
}
function parseNum(s: string): number {
  return Number(String(s).replace(/[^\d]/g, '')) || 0;
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 4, fontWeight: 600 };
const numInput: React.CSSProperties = {
  padding: '8px 12px', borderRadius: 6, border: '1px solid #444',
  background: '#0f0f1a', color: '#e0e0e0', fontSize: 15, width: '100%', textAlign: 'right',
};

/* ── reason mapping ── */
const reasonMap: Record<string, { fault: string; trigger: string; label: string; hint: string }> = {
  BUYER:   { fault: 'BUYER',   trigger: 'BUYER_CANCEL',    label: '구매자 사유',  hint: '배송비/PG수수료 구매자 부담. 배송 시작 후 배송비 환불 불가.' },
  SELLER:  { fault: 'SELLER',  trigger: 'SELLER_CANCEL',   label: '판매자 사유',  hint: '배송비/PG수수료 판매자 부담. 쿨링 경과 전까지 배송비 환불 가능.' },
  SYSTEM:  { fault: 'SYSTEM',  trigger: 'SYSTEM_ERROR',    label: '시스템 오류',  hint: '배송비/PG수수료 시스템 부담.' },
  DISPUTE: { fault: 'DISPUTE', trigger: 'DISPUTE_RESOLVE', label: '분쟁 결과',   hint: '배송 상태 무관 배송비 항상 환불. 수수료 시스템 부담.' },
};
const reasonOpts: Record<string, string[]> = {
  BUYER:   ['단순 변심', '다른 곳에서 더 저렴하게 구매', '배송 지연으로 인한 취소', '주문 실수 (수량/옵션 오류)', '개인 사정 변경', '중복 주문', '상품 필요 없어짐', '가격 변동 (더 저렴해짐)', '리뷰 확인 후 취소', '직접 입력'],
  SELLER:  ['상품 불량/하자', '오배송 (다른 상품 수령)', '상품 설명과 다름', '수량 부족', '파손된 상태로 배송', '유통기한 초과', '부품/액세서리 누락', '작동 불량', '사이즈/색상 불일치', '허위 광고', '직접 입력'],
  SYSTEM:  ['PG 결제 오류', '시스템 장애로 인한 이중 결제', '가격 표기 오류', '플랫폼 정책 변경', '서버 오류로 인한 주문 오류', '자동 취소 기한 초과', '테스트 주문 정리', '직접 입력'],
  DISPUTE: ['분쟁 결과: 구매자 승', '분쟁 결과: 판매자 승', '분쟁 결과: 합의 (부분 환불)', '분쟁 결과: 합의 (전액 환불)', '분쟁 결과: 상호 취소', '분쟁 시한 초과 자동 판정', '관리자 직권 판정', '직접 입력'],
};

const btnStyle = (active: boolean): React.CSSProperties => ({
  padding: '8px 16px', borderRadius: 6, border: 'none', cursor: 'pointer', fontSize: 13,
  background: active ? '#4ade80' : '#333', color: active ? '#000' : '#e0e0e0', fontWeight: active ? 700 : 400,
});

/* ── dispute simulation types ── */
type SimType = 'normal' | 'dispute_agreed' | 'dispute_direct' | 'dispute_external' | 'dispute_admin';
const simTypeOptions: { v: SimType; l: string }[] = [
  { v: 'normal', l: '일반 환불 (기존)' },
  { v: 'dispute_agreed', l: '분쟁 합의 후 환불' },
  { v: 'dispute_direct', l: '분쟁 결렬 → 직접 합의' },
  { v: 'dispute_external', l: '분쟁 결렬 → 외부기관 결정' },
  { v: 'dispute_admin', l: '분쟁 결렬 → 관리자 강제 종결' },
];
const externalOrgOptions = ['한국소비자원', '공정거래위원회', '전자상거래분쟁조정위원회', '소비자분쟁조정위원회'];
const PLATFORM_FEE_RATE = 0.035;

export default function AdminRefundSimulatorPage() {
  const [mode, setMode] = useState<'manual' | 'by_reservation'>('manual');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState('');

  // Simulation type
  const [simType, setSimType] = useState<SimType>('normal');

  // Dispute fields
  const [disputeDays, setDisputeDays] = useState(7);
  const [compensationType, setCompensationType] = useState<'fixed' | 'rate'>('fixed');
  const [compensationAmount, setCompensationAmount] = useState(5000);
  const [compensationRate, setCompensationRate] = useState(10);
  const [disputeHandling, setDisputeHandling] = useState<'refund' | 'partial' | 'exchange'>('refund');
  const [externalOrg, setExternalOrg] = useState(externalOrgOptions[0]);
  const [holdPeriod, setHoldPeriod] = useState(30);

  // Manual
  const [productPrice, setProductPrice] = useState(50000);
  const [quantity, setQuantity] = useState(2);
  const [refundQty, setRefundQty] = useState(1);
  const [refundError, setRefundError] = useState('');
  const [shippingMode, setShippingMode] = useState('FREE');
  const [shippingBase, setShippingBase] = useState(3000);
  const [shippingPerItem, setShippingPerItem] = useState(1000);
  const [coolingState, setCoolingState] = useState('BEFORE_SHIPPING');
  const [refundReason, setRefundReason] = useState('BUYER');
  const [reasonDetail, setReasonDetail] = useState('');
  const [customReason, setCustomReason] = useState('');
  const [settlementState, setSettlementState] = useState('NOT_SETTLED');

  // By reservation
  const [reservationId, setReservationId] = useState('');
  const [resvReason, setResvReason] = useState('BUYER');

  const isDispute = simType !== 'normal';

  const totalShipping = shippingMode === 'FREE' ? 0 : shippingMode === 'PER_RESERVATION' ? shippingBase : shippingBase + shippingPerItem * refundQty;
  const mapped = reasonMap[refundReason];

  const simulate = async () => {
    setLoading(true); setError(''); setResult(null);
    try {
      const body = mode === 'manual'
        ? {
            mode: 'manual', product_price: productPrice, shipping_fee: totalShipping,
            quantity, refund_quantity: refundQty,
            fault_party: mapped.fault, trigger: mapped.trigger,
            cooling_state: coolingState, settlement_state: settlementState,
          }
        : {
            mode: 'by_reservation', reservation_id: parseInt(reservationId),
            fault_party: reasonMap[resvReason].fault, trigger: reasonMap[resvReason].trigger,
          };
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
        {[{ v: 'manual' as const, l: '수동 시뮬레이션' }, { v: 'by_reservation' as const, l: '주문 조회' }].map(t => (
          <button key={t.v} onClick={() => { setMode(t.v); setResult(null); setError(''); }} style={{
            padding: '8px 20px', borderRadius: 8, border: `1px solid ${mode === t.v ? C.cyan : C.border}`,
            background: mode === t.v ? 'rgba(0,229,255,0.1)' : 'transparent',
            color: mode === t.v ? C.cyan : C.textSec, cursor: 'pointer', fontSize: 13, fontWeight: 600,
          }}>{t.l}</button>
        ))}
      </div>

      {/* Simulation Type Selector */}
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 16, marginBottom: 20 }}>
        <label style={{ ...labelStyle, marginBottom: 8 }}>시뮬레이션 유형</label>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {simTypeOptions.map(t => (
            <button key={t.v} onClick={() => { setSimType(t.v); setResult(null); setError(''); }} style={{
              padding: '7px 14px', borderRadius: 6, border: `1px solid ${simType === t.v ? C.cyan : '#444'}`,
              background: simType === t.v ? 'rgba(0,229,255,0.12)' : '#1a1a2e',
              color: simType === t.v ? C.cyan : '#bbb', cursor: 'pointer', fontSize: 12, fontWeight: simType === t.v ? 700 : 400,
            }}>{t.l}</button>
          ))}
        </div>

        {/* Dispute fields */}
        {isDispute && (
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #333' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
              <div>
                <label style={labelStyle}>분쟁 경과일 (일)</label>
                <input type="text" value={fmtNum(disputeDays)}
                  onChange={e => setDisputeDays(parseNum(e.target.value))}
                  onFocus={e => e.target.select()} placeholder="7" style={numInput} />
              </div>
              <div>
                <label style={labelStyle}>보상 방식</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button onClick={() => setCompensationType('fixed')} style={btnStyle(compensationType === 'fixed')}>정액</button>
                  <button onClick={() => setCompensationType('rate')} style={btnStyle(compensationType === 'rate')}>정율</button>
                </div>
              </div>
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={labelStyle}>{compensationType === 'fixed' ? '보상 금액 (원)' : '보상 비율 (%)'}</label>
              {compensationType === 'fixed' ? (
                <input type="text" value={fmtNum(compensationAmount)}
                  onChange={e => setCompensationAmount(parseNum(e.target.value))}
                  onFocus={e => e.target.select()} placeholder="0" style={numInput} />
              ) : (
                <input type="text" value={fmtNum(compensationRate)}
                  onChange={e => { const v = parseNum(e.target.value); setCompensationRate(Math.min(v, 100)); }}
                  onFocus={e => e.target.select()} placeholder="10" style={numInput} />
              )}
            </div>
            <div style={{ marginBottom: 12 }}>
              <label style={labelStyle}>처리 방식</label>
              <div style={{ display: 'flex', gap: 6 }}>
                <button onClick={() => setDisputeHandling('refund')} style={btnStyle(disputeHandling === 'refund')}>환불</button>
                <button onClick={() => setDisputeHandling('partial')} style={btnStyle(disputeHandling === 'partial')}>부분환불</button>
                <button onClick={() => setDisputeHandling('exchange')} style={btnStyle(disputeHandling === 'exchange')}>교환</button>
              </div>
            </div>

            {/* 관리자 강제 종결: AI 중재안 금액 */}
            {simType === 'dispute_admin' && (() => {
              const goodsTotal = productPrice * refundQty;
              const aiMediation = Math.round(goodsTotal * 0.5);
              return (
                <div style={{ marginBottom: 12, padding: 10, background: 'rgba(224,64,251,0.08)', border: '1px solid rgba(224,64,251,0.25)', borderRadius: 8 }}>
                  <label style={{ ...labelStyle, color: '#e040fb' }}>AI 중재안 금액</label>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#e040fb' }}>{aiMediation.toLocaleString()}원</div>
                  <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>상품 환불액의 50% 자동 산정 (상품 {goodsTotal.toLocaleString()}원 × 50%)</div>
                </div>
              );
            })()}

            {/* 외부기관: 기관 유형, 정산 보류 기간 */}
            {simType === 'dispute_external' && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={labelStyle}>기관 유형</label>
                  <select value={externalOrg} onChange={e => setExternalOrg(e.target.value)}
                    style={{ background: '#1a1a2e', color: '#e0e0e0', border: '1px solid #444', borderRadius: 6, padding: '8px 12px', width: '100%', fontSize: 13 }}>
                    {externalOrgOptions.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>정산 보류 기간 (일)</label>
                  <input type="text" value={fmtNum(holdPeriod)}
                    onChange={e => setHoldPeriod(parseNum(e.target.value))}
                    onFocus={e => e.target.select()} placeholder="30" style={numInput} />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* ═══ Left: Inputs ═══ */}
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 16 }}>
            {mode === 'manual' ? '조건 입력' : '주문 조회'}
          </h3>

          {mode === 'manual' ? (
            <>
              {/* 1. 상품 단가 */}
              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>상품 단가 (원)</label>
                <input type="text" value={fmtNum(productPrice)}
                  onChange={e => setProductPrice(parseNum(e.target.value))}
                  onFocus={e => e.target.select()} placeholder="0" style={numInput} />
              </div>

              {/* 2-3. 총수량 / 환불수량 */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div>
                  <label style={labelStyle}>총 수량</label>
                  <input type="text" value={fmtNum(quantity)}
                    onChange={e => { const v = parseNum(e.target.value); setQuantity(v); if (refundQty > v) setRefundQty(v); }}
                    onFocus={e => e.target.select()} placeholder="1" style={numInput} />
                </div>
                <div>
                  <label style={labelStyle}>환불 수량</label>
                  <input type="text" value={fmtNum(refundQty)}
                    onChange={e => {
                      const v = parseNum(e.target.value);
                      if (v > quantity) { setRefundError('총 수량을 초과할 수 없습니다'); return; }
                      setRefundError(''); setRefundQty(v);
                    }}
                    onFocus={e => e.target.select()} placeholder="1"
                    style={{ ...numInput, borderColor: refundError ? '#ef4444' : '#444' }} />
                  {refundError && <span style={{ color: '#ef4444', fontSize: 11, marginTop: 2, display: 'block' }}>{refundError}</span>}
                </div>
              </div>

              {/* 4. 배송비 유형 + 금액 */}
              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>배송비 유형</label>
                <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                  {([['FREE', '무료배송'], ['PER_RESERVATION', '건당 배송비'], ['PER_ITEM', '수량당 배송비']] as const).map(([k, l]) => (
                    <button key={k} onClick={() => setShippingMode(k)}
                      style={btnStyle(shippingMode === k)}>{l}</button>
                  ))}
                </div>
                {shippingMode === 'PER_RESERVATION' && (
                  <>
                    <label style={labelStyle}>배송비 (건당, 원)</label>
                    <input type="text" value={fmtNum(shippingBase)}
                      onChange={e => setShippingBase(parseNum(e.target.value))}
                      onFocus={e => e.target.select()} placeholder="0" style={numInput} />
                  </>
                )}
                {shippingMode === 'PER_ITEM' && (
                  <>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 4 }}>
                      <div>
                        <label style={labelStyle}>배송비 (기본, 원)</label>
                        <input type="text" value={fmtNum(shippingBase)}
                          onChange={e => setShippingBase(parseNum(e.target.value))}
                          onFocus={e => e.target.select()} placeholder="0" style={numInput} />
                      </div>
                      <div>
                        <label style={labelStyle}>배송비 (개당, 원)</label>
                        <input type="text" value={fmtNum(shippingPerItem)}
                          onChange={e => setShippingPerItem(parseNum(e.target.value))}
                          onFocus={e => e.target.select()} placeholder="0" style={numInput} />
                      </div>
                    </div>
                    <div style={{ color: '#888', fontSize: 12, marginTop: 6 }}>
                      총 배송비: {totalShipping.toLocaleString()}원 = 기본 {shippingBase.toLocaleString()} + 개당 {shippingPerItem.toLocaleString()} × 환불 {refundQty}개
                    </div>
                  </>
                )}
              </div>

              {/* 5. 배송 상태 */}
              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>배송 상태</label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {([['BEFORE_SHIPPING', '배송 전'], ['SHIPPED_NOT_DELIVERED', '배송 중'], ['WITHIN_COOLING', '수취 완료 (쿨링 내)'], ['AFTER_COOLING', '쿨링 경과']] as const).map(([k, l]) => (
                    <button key={k} onClick={() => setCoolingState(k)} style={btnStyle(coolingState === k)}>{l}</button>
                  ))}
                </div>
              </div>

              {/* 6. 환불 사유 (통합: 귀책+트리거+드롭다운) */}
              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>환불 사유</label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                  {Object.entries(reasonMap).map(([k, v]) => (
                    <button key={k} onClick={() => { setRefundReason(k); setReasonDetail(''); setCustomReason(''); }}
                      style={btnStyle(refundReason === k)}>{v.label}</button>
                  ))}
                </div>
                <div style={{ fontSize: 12, color: '#888', padding: '8px 10px', background: '#1a1a2e', borderRadius: 6, marginBottom: 8, lineHeight: 1.5 }}>
                  {mapped.hint}
                </div>
                <select value={reasonDetail} onChange={e => { setReasonDetail(e.target.value); if (e.target.value !== '직접 입력') setCustomReason(''); }}
                  style={{ background: '#1a1a2e', color: '#e0e0e0', border: '1px solid #444', borderRadius: 6, padding: '8px 12px', width: '100%', fontSize: 13 }}>
                  <option value="">-- 상세 사유 선택 --</option>
                  {reasonOpts[refundReason]?.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
                {reasonDetail === '직접 입력' && (
                  <input type="text" maxLength={20} value={customReason} onChange={e => setCustomReason(e.target.value)}
                    placeholder="사유를 직접 입력 (20자 이내)" style={{ ...numInput, textAlign: 'left', marginTop: 8 }} />
                )}
                {reasonDetail && reasonDetail !== '직접 입력' && <div style={{ marginTop: 4, fontSize: 12, color: '#4ade80' }}>{reasonDetail}</div>}
                {customReason && <div style={{ marginTop: 4, fontSize: 12, color: '#4ade80' }}>{customReason}</div>}
              </div>

              {/* 7. 정산 상태 */}
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>정산 상태</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button onClick={() => setSettlementState('NOT_SETTLED')} style={btnStyle(settlementState === 'NOT_SETTLED')}>정산 미완료</button>
                  <button onClick={() => setSettlementState('SETTLED_TO_SELLER')} style={btnStyle(settlementState === 'SETTLED_TO_SELLER')}>정산 완료</button>
                </div>
              </div>
            </>
          ) : (
            /* ─── By reservation ─── */
            <>
              <div style={{ marginBottom: 12 }}>
                <label style={labelStyle}>주문번호 (R-###)</label>
                <input value={reservationId} onChange={e => setReservationId(e.target.value.replace(/[^0-9]/g, ''))}
                  placeholder="주문 ID 숫자만 입력" style={{ ...numInput, textAlign: 'left' }} />
              </div>
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>환불 사유</label>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {Object.entries(reasonMap).map(([k, v]) => (
                    <button key={k} onClick={() => setResvReason(k)} style={btnStyle(resvReason === k)}>{v.label}</button>
                  ))}
                </div>
                <div style={{ fontSize: 12, color: '#888', padding: '8px 10px', background: '#1a1a2e', borderRadius: 6, marginTop: 8, lineHeight: 1.5 }}>
                  {reasonMap[resvReason].hint}
                </div>
              </div>
            </>
          )}

          {/* 8. 실행 버튼 */}
          <button onClick={simulate} disabled={loading || (mode === 'by_reservation' && !reservationId)} style={{
            width: '100%', padding: '12px', borderRadius: 8, border: 'none',
            background: C.cyan, color: '#000', fontWeight: 700, cursor: 'pointer', fontSize: 14,
            opacity: loading ? 0.6 : 1,
          }}>{loading ? '계산 중...' : '시뮬레이션 실행'}</button>
        </div>

        {/* ═══ Right: Result ═══ */}
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 16 }}>결과</h3>

          {error && <div style={{ padding: 12, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', borderRadius: 8, color: C.red, fontSize: 13, marginBottom: 12 }}>{error}</div>}
          {!result && !error && <div style={{ color: C.textSec, fontSize: 13, textAlign: 'center', padding: 40 }}>조건을 입력하고 시뮬레이션을 실행하세요</div>}
          {result?.error && <div style={{ padding: 12, background: 'rgba(255,82,82,0.1)', borderRadius: 8, color: C.red, fontSize: 13 }}>{result.error}</div>}

          {result && !result.error && result.breakdown && (
            <>
              {/* Reason summary */}
              <div style={{ marginBottom: 16, padding: 12, background: 'rgba(0,229,255,0.04)', border: `1px solid ${C.border}`, borderRadius: 8 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>환불 사유</div>
                <Row label="사유 주체" value={reasonMap[mode === 'manual' ? refundReason : resvReason]?.label || '-'} color={C.text} />
                <Row label="귀책" value={result.breakdown.fault_party || reasonMap[mode === 'manual' ? refundReason : resvReason]?.fault || '-'} color={C.textSec} />
                <Row label="트리거" value={result.breakdown.trigger || reasonMap[mode === 'manual' ? refundReason : resvReason]?.trigger || '-'} color={C.textSec} />
                {(reasonDetail || customReason) && mode === 'manual' && (
                  <Row label="상세 사유" value={reasonDetail === '직접 입력' ? customReason : reasonDetail} color="#4ade80" />
                )}
              </div>

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

              {/* ── Dispute: 정산 영향 (client-side) ── */}
              {isDispute && (() => {
                const goodsTotal = mode === 'manual'
                  ? productPrice * refundQty
                  : (result.breakdown?.goods_refund || 0);
                const shippingTotal = mode === 'manual'
                  ? totalShipping
                  : (result.breakdown?.shipping_refund || 0);
                const paymentTotal = goodsTotal + shippingTotal;
                const compAmount = compensationType === 'fixed'
                  ? compensationAmount
                  : Math.round(goodsTotal * compensationRate / 100);
                const handlingLabel = disputeHandling === 'refund' ? '전액 환불'
                  : disputeHandling === 'partial' ? '부분 환불' : '교환';
                const refundAmount = disputeHandling === 'exchange' ? 0
                  : disputeHandling === 'refund' ? paymentTotal : Math.round(paymentTotal * 0.5);
                const totalWithComp = refundAmount + compAmount;
                const platformFeeOriginal = Math.round(paymentTotal * PLATFORM_FEE_RATE);
                const platformFeeAfter = disputeHandling === 'refund' ? 0
                  : Math.round((paymentTotal - refundAmount) * PLATFORM_FEE_RATE);
                const sellerPayoutOriginal = paymentTotal - platformFeeOriginal;
                const sellerPayoutAfter = (paymentTotal - refundAmount) - platformFeeAfter;
                const isSettled = settlementState === 'SETTLED_TO_SELLER';
                const clawbackAmount = isSettled ? Math.max(0, sellerPayoutOriginal - sellerPayoutAfter) : 0;
                const disputeHoldDays = simType === 'dispute_external' ? holdPeriod
                  : simType === 'dispute_admin' ? 14 : disputeDays;
                const currentSettlementLabel = isSettled ? 'PAID (정산 완료)' : 'HOLD (보류 중)';
                const aiMediation = simType === 'dispute_admin' ? Math.round(goodsTotal * 0.5) : null;

                return (
                  <div style={{ marginBottom: 16, padding: 14, background: 'rgba(224,64,251,0.05)', border: '1px solid rgba(224,64,251,0.2)', borderRadius: 8 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#e040fb', marginBottom: 10 }}>분쟁 정산 영향</div>

                    {/* 분쟁 개요 */}
                    <div style={{ marginBottom: 10, padding: 10, background: 'rgba(0,0,0,0.2)', borderRadius: 6 }}>
                      <Row label="시뮬레이션 유형" value={simTypeOptions.find(t => t.v === simType)?.l || ''} color={C.cyan} />
                      <Row label="분쟁 경과일" value={`${disputeDays}일`} color={C.textSec} />
                      <Row label="처리 방식" value={handlingLabel} color={C.text} />
                      <Row label="보상 방식" value={compensationType === 'fixed' ? `정액 ${compAmount.toLocaleString()}원` : `정율 ${compensationRate}% (${compAmount.toLocaleString()}원)`} color={C.text} />
                      {simType === 'dispute_external' && <Row label="외부 기관" value={externalOrg} color={C.textSec} />}
                      {aiMediation !== null && <Row label="AI 중재안 금액" value={`${aiMediation.toLocaleString()}원`} color="#e040fb" />}
                    </div>

                    {/* 정산 상태 */}
                    <div style={{ marginBottom: 10 }}>
                      <Row label="현재 정산 상태" value={currentSettlementLabel} color={isSettled ? C.green : C.orange} bold />
                      <Row label="정산 보류 기간" value={`${disputeHoldDays}일`} color={C.textSec} />
                    </div>

                    {/* 보류 해제 후 */}
                    <div style={{ marginBottom: 10, paddingTop: 8, borderTop: '1px solid rgba(224,64,251,0.15)' }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: '#888', marginBottom: 6 }}>보류 해제 후 정산</div>
                      <Row label="환불 금액" value={`${refundAmount.toLocaleString()}원`} color={C.text} />
                      <Row label="보상 금액" value={`+${compAmount.toLocaleString()}원`} color={C.orange} />
                      <Row label="총 지급액 (환불+보상)" value={`${totalWithComp.toLocaleString()}원`} color={C.green} bold />
                    </div>

                    {/* 판매자 정산 재계산 */}
                    <div style={{ marginBottom: 10, paddingTop: 8, borderTop: '1px solid rgba(224,64,251,0.15)' }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: '#888', marginBottom: 6 }}>판매자 정산 재계산</div>
                      <Row label="판매자 정산 (기존)" value={`${sellerPayoutOriginal.toLocaleString()}원`} color={C.textSec} />
                      <Row label={`플랫폼 수수료 (기존, ${(PLATFORM_FEE_RATE * 100).toFixed(1)}%)`} value={`${platformFeeOriginal.toLocaleString()}원`} color={C.textSec} />
                      <Row label={`플랫폼 수수료 (재계산, ${(PLATFORM_FEE_RATE * 100).toFixed(1)}%)`} value={`${platformFeeAfter.toLocaleString()}원`} color={C.text} />
                      <Row label="보류 해제 후 판매자 정산 금액" value={`${sellerPayoutAfter.toLocaleString()}원`} color={sellerPayoutAfter >= 0 ? C.green : C.red} bold />
                    </div>

                    {/* 이미 정산 완료된 경우 (clawback) */}
                    <div style={{ paddingTop: 8, borderTop: '1px solid rgba(224,64,251,0.15)' }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: '#888', marginBottom: 6 }}>이미 정산 완료된 경우</div>
                      {isSettled ? (
                        <>
                          <Row label="정산 회수(clawback) 필요" value="Y" color={C.red} bold />
                          <Row label="회수 금액" value={`${clawbackAmount.toLocaleString()}원`} color={C.red} />
                          <div style={{ fontSize: 11, color: '#888', marginTop: 6, lineHeight: 1.5, padding: '6px 8px', background: 'rgba(255,82,82,0.06)', borderRadius: 4 }}>
                            판매자에게 이미 정산된 {sellerPayoutOriginal.toLocaleString()}원 중 {clawbackAmount.toLocaleString()}원을
                            회수해야 합니다. 회수 방법: 다음 정산에서 차감 또는 별도 청구.
                          </div>
                        </>
                      ) : (
                        <>
                          <Row label="정산 회수(clawback) 필요" value="N" color={C.green} />
                          <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
                            아직 정산 전이므로 보류 상태에서 직접 차감 가능합니다.
                          </div>
                        </>
                      )}
                    </div>
                  </div>
                );
              })()}

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
          {result && !result.error && mode === 'by_reservation' && result.reservation_info && (
            <>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>예약 정보</div>
                <Row label="주문번호" value={result.order_number || `R-${result.reservation_id}`} color={C.cyan} />
                <Row label="상태" value={result.reservation_info.status} color={C.text} />
                <Row label="결제 총액" value={`${result.reservation_info.amount_total?.toLocaleString()}원`} color={C.text} />
                <Row label="상품금액" value={`${result.reservation_info.amount_goods?.toLocaleString()}원`} color={C.textSec} />
                <Row label="배송비" value={`${result.reservation_info.amount_shipping?.toLocaleString()}원`} color={C.textSec} />
                <Row label="수량" value={`${result.reservation_info.qty}`} color={C.textSec} />
                <Row label="환불 수량" value={`${result.reservation_info.refunded_qty}`} color={C.textSec} />
                <Row label="배송일" value={result.reservation_info.shipped_at || '-'} color={C.textSec} />
                <Row label="수취확인" value={result.reservation_info.arrival_confirmed_at || '-'} color={C.textSec} />
              </div>
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
