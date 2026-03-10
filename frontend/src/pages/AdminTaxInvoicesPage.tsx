import { useState, useEffect, useCallback, useRef } from 'react';
import DateRangeFilter from '../components/common/DateRangeFilter';
import {
  fetchTaxInvoices,
  batchIssueTaxInvoices,
  issueTaxInvoice,
  cancelTaxInvoice,
  exportEcountXlsx,
} from '../api/taxInvoiceApi';
import type { TaxInvoice, TaxInvoiceStatus } from '../types/taxInvoice';

const C = {
  cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
};

const STATUS_LABELS: Record<TaxInvoiceStatus, string> = {
  PENDING: '대기', CONFIRMED: '확인완료', ISSUED: '발행완료', CANCELLED: '취소',
};
const STATUS_COLORS: Record<TaxInvoiceStatus, string> = {
  PENDING: C.orange, CONFIRMED: C.cyan, ISSUED: C.green, CANCELLED: C.red,
};

const TABS: Array<{ label: string; value: string }> = [
  { label: '전체', value: '' },
  { label: '대기', value: 'PENDING' },
  { label: '확인완료', value: 'CONFIRMED' },
  { label: '발행완료', value: 'ISSUED' },
  { label: '취소', value: 'CANCELLED' },
];

const fmt = (n: number) => n.toLocaleString('ko-KR');

export default function AdminTaxInvoicesPage() {
  const [items, setItems] = useState<TaxInvoice[]>([]);
  const [total, setTotal] = useState(0);
  const [tab, setTab] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<TaxInvoice | null>(null);
  const dateRef = useRef({ from: '', to: '' });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchTaxInvoices({ status: tab || undefined, limit: 200, date_from: dateRef.current.from || undefined, date_to: dateRef.current.to || undefined } as any);
      setItems(res.items);
      setTotal(res.total);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [tab]);

  useEffect(() => { load(); }, [load]);

  const toggle = (id: number) => {
    setSelected(prev => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  };

  const toggleAll = () => {
    if (selected.size === items.length) setSelected(new Set());
    else setSelected(new Set(items.map(i => i.id)));
  };

  const handleBatchIssue = async () => {
    if (selected.size === 0) return alert('발행할 세금계산서를 선택하세요.');
    if (!confirm(`${selected.size}건을 일괄 발행하시겠습니까?`)) return;
    try {
      await batchIssueTaxInvoices([...selected]);
      setSelected(new Set());
      load();
    } catch (e) { alert('일괄 발행 실패'); }
  };

  const handleSingleIssue = async (id: number) => {
    try { await issueTaxInvoice(id); load(); } catch { alert('발행 실패'); }
  };

  const handleCancel = async (id: number) => {
    if (!confirm('취소하시겠습니까?')) return;
    try { await cancelTaxInvoice(id); load(); } catch { alert('취소 실패'); }
  };

  const handleExport = async () => {
    const ids = selected.size > 0 ? [...selected] : items.map(i => i.id);
    if (ids.length === 0) return;
    try {
      const blob = await exportEcountXlsx(ids);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'tax_invoices_ecount.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch { alert('내보내기 실패'); }
  };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>세금계산서 관리</h1>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        {TABS.map(t => (
          <button key={t.value} onClick={() => setTab(t.value)}
            style={{
              padding: '6px 16px', borderRadius: 20, border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 600,
              background: tab === t.value ? C.cyan : C.card,
              color: tab === t.value ? '#000' : C.textSec,
            }}>
            {t.label}
          </button>
        ))}
      </div>

      <DateRangeFilter onFilter={(f, t) => { dateRef.current = { from: f, to: t }; load(); }} style={{ marginBottom: 12 }} />

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button onClick={handleBatchIssue} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: C.green, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>
          일괄 발행 ({selected.size})
        </button>
        <button onClick={handleExport} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: '#7c4dff', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>
          ECOUNT 내보내기
        </button>
        <button onClick={load} style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>
          새로고침
        </button>
        <span style={{ marginLeft: 'auto', color: C.textSec, fontSize: 13 }}>총 {total}건</span>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', borderRadius: 12, border: `1px solid ${C.border}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#1a1a2e' }}>
              <th style={{ padding: 8 }}><input type="checkbox" checked={selected.size === items.length && items.length > 0} onChange={toggleAll} /></th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'left' }}>번호</th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'left' }}>정산</th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'left' }}>품목명</th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'center' }}>수량</th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'left' }}>판매자</th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'right' }}>공급가액</th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'right' }}>세액</th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'right' }}>합계</th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'center' }}>상태</th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'center' }}>작성일</th>
              <th style={{ padding: 8, color: C.textSec, textAlign: 'center' }}>액션</th>
            </tr>
          </thead>
          <tbody>
            {items.map(inv => (
              <tr key={inv.id} style={{ borderTop: `1px solid ${C.border}`, cursor: 'pointer' }} onClick={() => setDetail(inv)}>
                <td style={{ padding: 8 }} onClick={e => e.stopPropagation()}>
                  <input type="checkbox" checked={selected.has(inv.id)} onChange={() => toggle(inv.id)} />
                </td>
                <td style={{ padding: 8, color: C.text }}>{inv.invoice_number}</td>
                <td style={{ padding: 8 }}>{inv.settlement_id ? <span style={{ color: '#7c4dff', fontWeight: 600, fontSize: 12 }}>S-{inv.settlement_id}</span> : '-'}</td>
                <td style={{ padding: 8, color: C.text, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={(inv as any).product_name || ''}>{(inv as any).product_name || '-'}</td>
                <td style={{ padding: 8, color: C.textSec, textAlign: 'center' }}>{(inv as any).quantity ?? '-'}</td>
                <td style={{ padding: 8, color: C.text }}>{inv.recipient_business_name || '-'}</td>
                <td style={{ padding: 8, color: C.text, textAlign: 'right' }}>{fmt(inv.supply_amount)}</td>
                <td style={{ padding: 8, color: C.text, textAlign: 'right' }}>{fmt(inv.tax_amount)}</td>
                <td style={{ padding: 8, color: C.cyan, textAlign: 'right', fontWeight: 600 }}>{fmt(inv.total_amount)}</td>
                <td style={{ padding: 8, textAlign: 'center' }}>
                  <span style={{ padding: '2px 10px', borderRadius: 12, fontSize: 11, fontWeight: 700, color: '#000', background: STATUS_COLORS[inv.status as TaxInvoiceStatus] || C.textSec }}>
                    {STATUS_LABELS[inv.status as TaxInvoiceStatus] || inv.status}
                  </span>
                </td>
                <td style={{ padding: 8, color: C.textSec, textAlign: 'center', fontSize: 12 }}>{inv.created_at?.slice(0, 10)}</td>
                <td style={{ padding: 8, textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                  {(inv.status === 'PENDING' || inv.status === 'CONFIRMED') && (
                    <button onClick={() => handleSingleIssue(inv.id)} style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: C.green, color: '#000', fontSize: 11, fontWeight: 600, cursor: 'pointer', marginRight: 4 }}>발행</button>
                  )}
                  {inv.status !== 'CANCELLED' && inv.status !== 'ISSUED' && (
                    <button onClick={() => handleCancel(inv.id)} style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: C.red, color: '#fff', fontSize: 11, fontWeight: 600, cursor: 'pointer' }}>취소</button>
                  )}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={12} style={{ padding: 40, textAlign: 'center', color: C.textSec }}>세금계산서가 없습니다.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Detail Modal */}
      {detail && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={() => setDetail(null)}>
          <div style={{ background: C.card, borderRadius: 16, padding: 24, width: 520, maxHeight: '80vh', overflow: 'auto', color: C.text }} onClick={e => e.stopPropagation()}>
            <h2 style={{ fontSize: 18, fontWeight: 700, marginBottom: 16 }}>세금계산서 상세</h2>
            <p style={{ fontSize: 13, color: C.textSec, marginBottom: 4 }}>{detail.invoice_number}</p>
            {detail.settlement_id && <p style={{ fontSize: 12, color: '#7c4dff', fontWeight: 600, marginBottom: 12 }}>정산: S-{detail.settlement_id}</p>}

            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: C.cyan }}>공급자</h3>
            <div style={{ fontSize: 13, marginBottom: 16, lineHeight: 1.8 }}>
              <div>상호: {detail.supplier_business_name}</div>
              <div>사업자번호: {detail.supplier_business_number}</div>
              <div>대표자: {detail.supplier_representative}</div>
              <div>주소: {detail.supplier_address}</div>
              <div>이메일: {detail.supplier_email || '-'}</div>
            </div>

            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: C.cyan }}>공급받는 자</h3>
            <div style={{ fontSize: 13, marginBottom: 16, lineHeight: 1.8 }}>
              <div>상호: {detail.recipient_business_name || '-'}</div>
              <div>사업자번호: {detail.recipient_business_number || '-'}</div>
              <div>대표자: {detail.recipient_representative || '-'}</div>
              <div>업태: {detail.recipient_business_type || '-'}</div>
              <div>종목: {detail.recipient_business_item || '-'}</div>
              <div>주소: {detail.recipient_address || '-'}</div>
              <div>이메일: {detail.recipient_email || '-'}</div>
            </div>

            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8, color: C.cyan }}>금액</h3>
            <div style={{ fontSize: 13, marginBottom: 16, lineHeight: 1.8 }}>
              <div>공급가액: {fmt(detail.supply_amount)}원</div>
              <div>세액: {fmt(detail.tax_amount)}원</div>
              <div style={{ fontWeight: 700, color: C.cyan }}>합계: {fmt(detail.total_amount)}원</div>
            </div>

            <button onClick={() => setDetail(null)} style={{ width: '100%', padding: '10px', borderRadius: 8, border: 'none', background: C.cyan, color: '#000', fontWeight: 600, cursor: 'pointer' }}>닫기</button>
          </div>
        </div>
      )}
    </div>
  );
}
