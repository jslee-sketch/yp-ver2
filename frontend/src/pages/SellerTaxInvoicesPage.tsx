import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMyTaxInvoices, confirmTaxInvoice } from '../api/taxInvoiceApi';
import type { TaxInvoice, TaxInvoiceStatus } from '../types/taxInvoice';

const C = {
  cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
};

const STATUS_LABELS: Record<TaxInvoiceStatus, string> = {
  PENDING: '확인 대기', CONFIRMED: '확인완료', ISSUED: '발행완료', CANCELLED: '취소',
};
const STATUS_COLORS: Record<TaxInvoiceStatus, string> = {
  PENDING: C.orange, CONFIRMED: C.cyan, ISSUED: C.green, CANCELLED: C.red,
};

const fmt = (n: number) => n.toLocaleString('ko-KR');

export default function SellerTaxInvoicesPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<TaxInvoice[]>([]);
  const [loading, setLoading] = useState(true);

  // 로그인된 판매자 ID (로컬스토리지에서 가져오기)
  const sellerId = Number(localStorage.getItem('seller_id') || '0');

  const load = async () => {
    if (!sellerId) { setLoading(false); return; }
    try {
      const res = await fetchMyTaxInvoices(sellerId);
      setItems(res.items);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleConfirm = async (invoiceId: number) => {
    if (!confirm('세금계산서를 확인 처리하시겠습니까?')) return;
    try {
      await confirmTaxInvoice(invoiceId, sellerId);
      load();
    } catch { alert('확인 처리 실패'); }
  };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;
  if (!sellerId) return <div style={{ padding: 40, color: C.textSec }}>판매자 로그인이 필요합니다.</div>;

  return (
    <div style={{ padding: '20px 0' }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>세금계산서</h1>
      <p style={{ fontSize: 13, color: C.textSec, marginBottom: 20 }}>
        정산 승인 후 자동 생성된 세금계산서입니다. 대기 상태의 건은 내용 확인 후 [확인] 버튼을 눌러주세요.
      </p>

      {items.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: C.textSec, background: C.card, borderRadius: 12 }}>
          세금계산서가 없습니다.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {items.map(inv => (
            <div key={inv.id} style={{ background: C.card, borderRadius: 12, padding: 16, border: `1px solid ${C.border}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                <span style={{ fontSize: 14, fontWeight: 600, color: C.text }}>{inv.invoice_number}</span>
                <span style={{
                  padding: '2px 10px', borderRadius: 12, fontSize: 11, fontWeight: 700, color: '#000',
                  background: STATUS_COLORS[inv.status as TaxInvoiceStatus] || C.textSec,
                }}>
                  {STATUS_LABELS[inv.status as TaxInvoiceStatus] || inv.status}
                </span>
              </div>

              <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.8 }}>
                {(inv as any).product_name && <div style={{ fontWeight: 600, color: C.text }}>품목: {(inv as any).product_name}{(inv as any).quantity ? ` × ${(inv as any).quantity}` : ''}</div>}
                <div>공급자: {inv.supplier_business_name}</div>
                <div style={{ display: 'flex', gap: 16 }}>
                  <span>공급가액: {fmt(inv.supply_amount)}원</span>
                  <span>세액: {fmt(inv.tax_amount)}원</span>
                  <span style={{ fontWeight: 700, color: C.cyan }}>합계: {fmt(inv.total_amount)}원</span>
                </div>
                <div>작성일: {inv.created_at?.slice(0, 10)}</div>
                {inv.settlement_id && (
                  <div>
                    연결 정산:{' '}
                    <span
                      onClick={() => navigate('/seller/settlements')}
                      style={{ color: C.cyan, fontWeight: 700, cursor: 'pointer', textDecoration: 'underline' }}
                    >
                      #{inv.settlement_id}
                    </span>
                  </div>
                )}
                {((inv as Record<string, unknown>).payment_due_date || (inv as Record<string, unknown>).expected_payment_date) && (
                  <div>
                    지급 예정일:{' '}
                    <span style={{ fontWeight: 700, color: C.green }}>
                      {String((inv as Record<string, unknown>).payment_due_date ?? (inv as Record<string, unknown>).expected_payment_date).slice(0, 10)}
                    </span>
                  </div>
                )}
              </div>

              {inv.status === 'PENDING' && (
                <button onClick={() => handleConfirm(inv.id)} style={{
                  marginTop: 10, padding: '8px 20px', borderRadius: 8, border: 'none',
                  background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13,
                }}>
                  확인
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
