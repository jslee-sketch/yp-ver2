import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import InterestTagInput from '../components/common/InterestTagInput';
import type { InterestEntry } from '../components/common/InterestTagInput';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)',
  text: 'var(--text-primary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

export default function InterestSettingsPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const userId = user?.id || 0;
  const role = user?.role === 'seller' || user?.role === 'both' ? 'seller' : user?.role === 'actuator' ? 'actuator' : 'buyer';
  const maxCount = role === 'actuator' ? 10 : role === 'seller' ? 5 : 3;

  const [interests, setInterests] = useState<InterestEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!userId) return;
    apiClient.get(`/users/${userId}/interests`)
      .then(r => setInterests(r.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [userId]);

  const save = async () => {
    setSaving(true);
    try {
      await apiClient.post(`/users/${userId}/interests`, { interests, role });
      alert('저장되었습니다!');
    } catch (e: any) {
      alert(e.response?.data?.detail || '저장 실패');
    }
    setSaving(false);
  };

  if (loading) return <div style={{ padding: 40, color: C.textDim }}>로딩 중...</div>;

  const roleLabel = role === 'seller' ? '주요 판매 품목' : role === 'actuator' ? '관심 카테고리/제품/모델' : '관심 상품';

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>{roleLabel}</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0', maxWidth: 600, margin: '0 auto' }}>
        <div style={{
          background: C.bgCard, borderRadius: 14, padding: 16,
          border: `1px solid ${C.border}`, marginBottom: 16,
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 4 }}>
            {roleLabel} 등록
          </div>
          <div style={{ fontSize: 12, color: C.textDim, marginBottom: 14, lineHeight: 1.6 }}>
            {role === 'seller'
              ? '등록하시면 관련 딜이 생성될 때 자동으로 알려드려요! 판매 기회를 놓치지 마세요!'
              : '관련 딜이 생성되면 알림을 받을 수 있어요!'}
          </div>

          <InterestTagInput
            interests={interests}
            onChange={setInterests}
            maxCount={maxCount}
            showPresets={true}
          />
        </div>

        {role === 'seller' && interests.length === 0 && (
          <div style={{
            padding: 12, borderRadius: 10,
            background: 'rgba(255,145,0,0.1)', border: '1px solid rgba(255,145,0,0.3)',
            color: '#ff9100', fontSize: 12, marginBottom: 16,
          }}>
            등록하지 않으면 새 딜 알림을 받을 수 없어요!
          </div>
        )}

        <button
          onClick={save}
          disabled={saving}
          style={{
            width: '100%', padding: 14, borderRadius: 12, border: 'none',
            background: saving ? '#4ade8055' : '#4ade80', color: '#000',
            fontWeight: 700, fontSize: 15, cursor: saving ? 'not-allowed' : 'pointer',
          }}
        >
          {saving ? '저장 중...' : '저장'}
        </button>
      </div>
    </div>
  );
}
