import { useState, useEffect, useRef } from 'react';
import apiClient from '../api/client';
import { ocrBusinessRegistration, updateBusinessInfo } from '../api/taxInvoiceApi';

const C = {
  cyan: '#00e5ff', green: '#00e676', orange: '#ff9100',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
};

const FIELDS = [
  { key: 'business_name', label: '상호(법인명)' },
  { key: 'business_number', label: '사업자등록번호' },
  { key: 'representative_name', label: '대표자명' },
  { key: 'address', label: '사업장 소재지' },
  { key: 'business_type', label: '업태' },
  { key: 'business_item', label: '종목' },
  { key: 'tax_invoice_email', label: '세금계산서 수신 이메일' },
] as const;

export default function SellerBusinessInfoPage() {
  const sellerId = Number(localStorage.getItem('seller_id') || '0');
  const [form, setForm] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!sellerId) { setLoading(false); return; }
    (async () => {
      try {
        const { data } = await apiClient.get(`/sellers/${sellerId}`);
        const seller = data?.seller || data;
        const init: Record<string, string> = {};
        FIELDS.forEach(f => { init[f.key] = seller?.[f.key] || ''; });
        setForm(init);
      } catch (e) { console.error(e); }
      setLoading(false);
    })();
  }, [sellerId]);

  const handleOcr = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setOcrLoading(true);
    try {
      const result = await ocrBusinessRegistration(file);
      setForm(prev => ({
        ...prev,
        business_name: result.business_name || prev.business_name,
        business_number: result.business_number || prev.business_number,
        representative_name: result.representative_name || prev.representative_name,
        address: result.address || prev.address,
        business_type: result.business_type || prev.business_type,
        business_item: result.business_item || prev.business_item,
      }));
      alert('사업자등록증 OCR 파싱 완료! 내용을 확인 후 저장해주세요.');
    } catch (err) {
      alert('OCR 파싱 실패. 다시 시도해주세요.');
    }
    setOcrLoading(false);
    if (fileRef.current) fileRef.current.value = '';
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateBusinessInfo(sellerId, form);
      alert('사업자 정보가 저장되었습니다.');
    } catch { alert('저장 실패'); }
    setSaving(false);
  };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;
  if (!sellerId) return <div style={{ padding: 40, color: C.textSec }}>판매자 로그인이 필요합니다.</div>;

  const inputStyle = {
    width: '100%', padding: '10px 12px', borderRadius: 8,
    border: `1px solid ${C.border}`, background: C.card, color: C.text, fontSize: 14,
    boxSizing: 'border-box' as const,
  };

  return (
    <div style={{ padding: '20px 0', maxWidth: 600 }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 8 }}>사업자 정보</h1>
      <p style={{ fontSize: 13, color: C.textSec, marginBottom: 20 }}>
        세금계산서 발행에 사용되는 사업자 정보입니다. 사업자등록증 OCR로 자동 입력할 수 있습니다.
      </p>

      {/* OCR Upload */}
      <div style={{ marginBottom: 24, padding: 16, background: C.card, borderRadius: 12, border: `1px dashed ${C.border}` }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: C.text, marginBottom: 8 }}>
          사업자등록증 OCR 업로드
        </div>
        <p style={{ fontSize: 12, color: C.textSec, marginBottom: 10 }}>
          사업자등록증 이미지를 업로드하면 AI가 자동으로 정보를 추출합니다.
        </p>
        <input ref={fileRef} type="file" accept="image/*" onChange={handleOcr} style={{ display: 'none' }} />
        <button onClick={() => fileRef.current?.click()} disabled={ocrLoading}
          style={{
            padding: '10px 20px', borderRadius: 8, border: 'none',
            background: ocrLoading ? C.textSec : C.orange, color: '#000',
            fontWeight: 600, cursor: ocrLoading ? 'wait' : 'pointer', fontSize: 13,
          }}>
          {ocrLoading ? 'OCR 분석 중...' : '사업자등록증 업로드'}
        </button>
      </div>

      {/* Form */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {FIELDS.map(f => (
          <div key={f.key}>
            <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 4, display: 'block' }}>{f.label}</label>
            <input value={form[f.key] || ''} onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))} style={inputStyle} />
          </div>
        ))}
      </div>

      <button onClick={handleSave} disabled={saving}
        style={{
          marginTop: 20, width: '100%', padding: '12px', borderRadius: 8, border: 'none',
          background: saving ? C.textSec : C.cyan, color: '#000', fontWeight: 700, cursor: 'pointer', fontSize: 15,
        }}>
        {saving ? '저장 중...' : '저장'}
      </button>
    </div>
  );
}
