import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  bg: 'var(--bg-primary)', card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)',
  cyan: '#00e5ff', green: '#00e676', orange: '#ff9100', red: '#ff5252',
};

interface Conditions {
  user_id: number;
  user_info: { type: string; name: string; level?: number };
  defaults: Record<string, any>;
  current: Record<string, any>;
  has_override: boolean;
  modified_by: number | null;
  modified_at: string | null;
}

const FIELDS = [
  { key: 'fee_rate', label: '수수료율 (%)', type: 'number', step: 0.1 },
  { key: 'cooling_days', label: '쿨링기간 (일)', type: 'number', step: 1 },
  { key: 'settlement_days', label: '정산주기 (일)', type: 'number', step: 1 },
  { key: 'shipping_support', label: '배송료 지원', type: 'checkbox' },
  { key: 'level', label: 'VIP 등급', type: 'number', step: 1 },
];

export default function AdminUserConditionsPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<Conditions | null>(null);
  const [form, setForm] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!userId) return;
    setLoading(true);
    apiClient.get(API.USER_CONDITIONS.GET(Number(userId)))
      .then(res => {
        const d = res.data as Conditions;
        setData(d);
        setForm({ ...d.current });
      })
      .catch(() => alert('조건 조회 실패'))
      .finally(() => setLoading(false));
  }, [userId]);

  const handleSave = async () => {
    if (!userId) return;
    setSaving(true);
    try {
      await apiClient.put(API.USER_CONDITIONS.UPDATE(Number(userId)), {
        fee_rate_override: form.fee_rate,
        cooling_days_override: form.cooling_days,
        settlement_days_override: form.settlement_days,
        shipping_support: form.shipping_support,
        level_override: form.level,
      });
      alert('저장되었습니다.');
      // reload
      const res = await apiClient.get(API.USER_CONDITIONS.GET(Number(userId)));
      setData(res.data as Conditions);
    } catch { alert('저장 실패'); }
    setSaving(false);
  };

  const handleReset = async () => {
    if (!userId || !confirm('기본값으로 초기화하시겠습니까?')) return;
    try {
      await apiClient.delete(API.USER_CONDITIONS.RESET(Number(userId)));
      alert('초기화되었습니다.');
      const res = await apiClient.get(API.USER_CONDITIONS.GET(Number(userId)));
      const d = res.data as Conditions;
      setData(d);
      setForm({ ...d.current });
    } catch { alert('초기화 실패'); }
  };

  if (loading) return <div style={{ padding: 40, color: C.textSec }}>로딩 중...</div>;
  if (!data) return <div style={{ padding: 40, color: C.red }}>데이터를 불러올 수 없습니다.</div>;

  return (
    <div>
      <button onClick={() => navigate(-1)} style={{ background: 'none', border: 'none', color: C.cyan, cursor: 'pointer', fontSize: 13, marginBottom: 12 }}>
        ← 뒤로
      </button>

      <h1 style={{ fontSize: 20, fontWeight: 800, color: C.text, marginBottom: 8 }}>
        참여자 조건 관리 — {data.user_info.name} (ID: {data.user_id})
      </h1>
      <p style={{ fontSize: 13, color: C.textSec, marginBottom: 20 }}>
        유형: {data.user_info.type} {data.has_override && '| 커스텀 조건 적용 중'}
        {data.modified_at && ` | 마지막 수정: ${data.modified_at.slice(0, 10)}`}
      </p>

      <div style={{ borderRadius: 12, border: `1px solid ${C.border}`, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ background: '#1a1a2e' }}>
              <th style={{ padding: 10, color: C.textSec, textAlign: 'left' }}>항목</th>
              <th style={{ padding: 10, color: C.textSec, textAlign: 'center' }}>역핑 기본</th>
              <th style={{ padding: 10, color: C.textSec, textAlign: 'center' }}>현재 적용</th>
              <th style={{ padding: 10, color: C.textSec, textAlign: 'center' }}>수정</th>
            </tr>
          </thead>
          <tbody>
            {FIELDS.map(f => (
              <tr key={f.key} style={{ borderTop: `1px solid ${C.border}` }}>
                <td style={{ padding: 10, color: C.text }}>{f.label}</td>
                <td style={{ padding: 10, color: C.textSec, textAlign: 'center' }}>{data.defaults[f.key]?.toString() ?? '-'}</td>
                <td style={{ padding: 10, textAlign: 'center', color: data.current[f.key] !== data.defaults[f.key] ? C.orange : C.text, fontWeight: data.current[f.key] !== data.defaults[f.key] ? 700 : 400 }}>
                  {data.current[f.key]?.toString() ?? '-'}
                </td>
                <td style={{ padding: 10, textAlign: 'center' }}>
                  {f.type === 'checkbox' ? (
                    <input type="checkbox" checked={!!form[f.key]} onChange={e => setForm({ ...form, [f.key]: e.target.checked })} />
                  ) : (
                    <input type="number" step={f.step} value={form[f.key] ?? ''} onChange={e => setForm({ ...form, [f.key]: e.target.value === '' ? null : Number(e.target.value) })}
                      style={{ width: 80, padding: '4px 8px', borderRadius: 6, border: `1px solid ${C.border}`, background: C.card, color: C.text, textAlign: 'center', fontSize: 13 }}
                    />
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p style={{ fontSize: 12, color: C.orange, marginTop: 12 }}>
        ⚠️ 변경된 조건은 현재 진행 중인 딜/오퍼 종료 후 적용됩니다.
      </p>

      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <button onClick={handleSave} disabled={saving}
          style={{ padding: '10px 24px', borderRadius: 8, border: 'none', background: C.green, color: '#000', fontWeight: 700, cursor: 'pointer', fontSize: 14 }}>
          {saving ? '저장 중...' : '저장'}
        </button>
        <button onClick={handleReset}
          style={{ padding: '10px 24px', borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.textSec, fontWeight: 600, cursor: 'pointer', fontSize: 14 }}>
          초기화 (기본값)
        </button>
      </div>
    </div>
  );
}
