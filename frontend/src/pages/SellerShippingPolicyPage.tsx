import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { showToast } from '../components/common/Toast';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

interface ShippingPolicy {
  default_carrier: string;
  free_shipping_threshold: number;
  shipping_fee_default: number;
  return_address: string;
  return_fee: number;
  exchange_fee: number;
  delivery_days_default: number;
  notice: string;
}

const EMPTY_POLICY: ShippingPolicy = {
  default_carrier: 'CJ대한통운',
  free_shipping_threshold: 0,
  shipping_fee_default: 3000,
  return_address: '',
  return_fee: 3000,
  exchange_fee: 6000,
  delivery_days_default: 3,
  notice: '',
};

const CARRIERS = ['CJ대한통운', '한진택배', '로젠택배', '우체국택배', 'CU편의점택배', '롯데택배'];

export default function SellerShippingPolicyPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const sellerId = user?.seller?.id ?? user?.id ?? 0;

  const [form, setForm] = useState<ShippingPolicy>(EMPTY_POLICY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!sellerId) return;
    (async () => {
      try {
        const res = await apiClient.get(API.SELLERS.PROFILE);
        const policy = res.data?.shipping_policy;
        if (policy && typeof policy === 'object') {
          setForm({ ...EMPTY_POLICY, ...policy });
        }
      } catch (err) {
        console.error('배송 정책 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [sellerId]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await apiClient.patch(API.SELLERS.UPDATE(sellerId), {
        shipping_policy: form,
      });
      showToast('배송 정책 저장 완료', 'success');
    } catch {
      showToast('저장 실패', 'error');
    }
    setSaving(false);
  };

  const setField = <K extends keyof ShippingPolicy>(key: K, value: ShippingPolicy[K]) => {
    setForm(prev => ({ ...prev, [key]: value }));
  };

  const inputStyle = {
    width: '100%', boxSizing: 'border-box' as const, padding: '10px 14px',
    borderRadius: 10, fontSize: 13, background: C.bgEl,
    border: `1px solid ${C.border}`, color: C.text, marginBottom: 14,
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>배송 정책</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0', maxWidth: 600, margin: '0 auto' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : (
          <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 16, padding: '20px 16px' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>기본 택배사</div>
            <select value={form.default_carrier} onChange={e => setField('default_carrier', e.target.value)}
              style={{ ...inputStyle, appearance: 'auto' as const }}>
              {CARRIERS.map(c => <option key={c} value={c}>{c}</option>)}
            </select>

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>기본 배송비 (원)</div>
            <input type="number" value={form.shipping_fee_default} onChange={e => setField('shipping_fee_default', Number(e.target.value))} style={inputStyle} />

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>무료배송 기준금액 (원, 0=없음)</div>
            <input type="number" value={form.free_shipping_threshold} onChange={e => setField('free_shipping_threshold', Number(e.target.value))} style={inputStyle} />

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>기본 리드타임 (일)</div>
            <input type="number" value={form.delivery_days_default} onChange={e => setField('delivery_days_default', Number(e.target.value))} style={inputStyle} />

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>반품 배송비 (원)</div>
            <input type="number" value={form.return_fee} onChange={e => setField('return_fee', Number(e.target.value))} style={inputStyle} />

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>교환 배송비 (원)</div>
            <input type="number" value={form.exchange_fee} onChange={e => setField('exchange_fee', Number(e.target.value))} style={inputStyle} />

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>반품 주소</div>
            <input type="text" value={form.return_address} onChange={e => setField('return_address', e.target.value)} placeholder="반품 수거 주소" style={inputStyle} />

            <div style={{ fontSize: 12, fontWeight: 700, color: C.textDim, marginBottom: 6 }}>배송 안내 메시지</div>
            <textarea value={form.notice} onChange={e => setField('notice', e.target.value)} placeholder="구매자에게 표시되는 배송 안내" rows={3}
              style={{ ...inputStyle, resize: 'none' as const }} />

            <button disabled={saving} onClick={() => void handleSave()}
              style={{
                width: '100%', padding: '14px', borderRadius: 12, fontSize: 15, fontWeight: 700,
                background: saving ? `${C.green}55` : C.green, border: 'none', color: '#0a0a0f',
                cursor: saving ? 'not-allowed' : 'pointer', marginTop: 8,
              }}>
              {saving ? '저장 중...' : '저장'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
