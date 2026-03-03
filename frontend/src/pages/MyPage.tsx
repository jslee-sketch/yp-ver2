import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  bg:      'var(--bg-primary)',
  bgCard:  'var(--bg-secondary)',
  bgEl:    'var(--bg-elevated)',
  text:    'var(--text-primary)',
  textSec: 'var(--text-secondary)',
  textDim: 'var(--text-muted)',
  border:  'var(--border-subtle)',
  green:   'var(--accent-green)',
  blue:    'var(--accent-blue)',
  orange:  'var(--accent-orange)',
  yellow:  '#ffe156',
};

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: C.bgCard, border: `1px solid ${C.border}`,
      borderRadius: 16, padding: '16px 18px', marginBottom: 12,
      ...style,
    }}>
      {children}
    </div>
  );
}

function CardTitle({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 12 }}>
      {children}
    </div>
  );
}

function InfoRow({ icon, label, value, valueColor }: {
  icon: string; label: string; value: string; valueColor?: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 0', borderBottom: `1px solid ${C.border}` }}>
      <span style={{ fontSize: 13, color: C.textSec }}>{icon} {label}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color: valueColor ?? C.text }}>{value}</span>
    </div>
  );
}

function ActionRow({ icon, label, onClick }: { icon: string; label: string; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '11px 0', background: 'none', border: 'none', cursor: 'pointer',
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      <span style={{ fontSize: 13, color: C.textSec }}>{icon} {label}</span>
      <span style={{ fontSize: 14, color: C.textDim }}>›</span>
    </button>
  );
}

interface PaymentMethod {
  id: number;
  type: 'card' | 'bank';
  name: string;
  last4: string;
  isDefault: boolean;
}

export default function MyPage() {
  const navigate = useNavigate();
  const { user: authUser } = useAuth();
  const [apiProfile, setApiProfile] = useState<Record<string, unknown> | null>(null);
  const [showProfileEdit, setShowProfileEdit] = useState(false);
  const [editName, setEditName] = useState('');
  const [editNickname, setEditNickname] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editAddress, setEditAddress] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!authUser) return;
    apiClient.get(API.BUYERS.PROFILE)
      .then(res => { if (res.data) setApiProfile(res.data as Record<string, unknown>); })
      .catch(() => {});
  }, [authUser]);

  const u = {
    id:           Number(apiProfile?.id ?? authUser?.id ?? 0),
    name:         String(apiProfile?.name ?? authUser?.name ?? '사용자'),
    nickname:     String(apiProfile?.nickname ?? authUser?.nickname ?? ''),
    email:        String(apiProfile?.email ?? authUser?.email ?? ''),
    level:        Number(apiProfile?.level ?? authUser?.level ?? 1),
    trust_tier:   String(apiProfile?.trust_tier ?? authUser?.trust_tier ?? 'Bronze'),
    points:       Number(apiProfile?.points ?? authUser?.points ?? 0),
    phone:        String(apiProfile?.phone ?? ''),
    address:      String(apiProfile?.address ?? ''),
    created_at:   String(apiProfile?.created_at ?? '').split('T')[0] || '-',
    total_orders: Number(apiProfile?.total_orders ?? 0),
    total_deals:  Number(apiProfile?.total_deals ?? 0),
    isSeller:     authUser?.role === 'seller' || authUser?.role === 'both',
    seller:       authUser?.seller,
  };

  const openProfileEdit = () => {
    setEditName(u.name);
    setEditNickname(u.nickname);
    setEditPhone(u.phone);
    setEditAddress(u.address);
    setShowProfileEdit(true);
  };

  const saveProfile = async () => {
    setSaving(true);
    try {
      await apiClient.patch(API.BUYERS.UPDATE(u.id), {
        name: editName,
        nickname: editNickname,
        phone: editPhone || undefined,
        address: editAddress || undefined,
      });
      setApiProfile(prev => ({
        ...prev,
        name: editName,
        nickname: editNickname,
        phone: editPhone,
        address: editAddress,
      }));
      setShowProfileEdit(false);
    } catch {
      alert('프로필 수정에 실패했어요');
    }
    setSaving(false);
  };

  const [showPayModal, setShowPayModal] = useState(false);
  const [payMethods, setPayMethods] = useState<PaymentMethod[]>([
    { id: 1, type: 'card', name: '신한카드',      last4: '1234', isDefault: true },
    { id: 2, type: 'bank', name: '국민은행 자동이체', last4: '5678', isDefault: false },
  ]);

  const setDefault = (id: number) =>
    setPayMethods(prev => prev.map(m => ({ ...m, isDefault: m.id === id })));
  const removeMethod = (id: number) =>
    setPayMethods(prev => prev.filter(m => m.id !== id));

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>

      {/* TopBar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px',
        background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>마이페이지</span>
        <button onClick={() => navigate('/notifications')} style={{ fontSize: 20, color: C.textSec, cursor: 'pointer', lineHeight: 1 }}>🔔</button>
      </div>

      <div style={{ padding: '16px 16px 0' }}>

        {/* 프로필 카드 */}
        <Card style={{ borderTop: `3px solid ${C.green}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
            <div style={{
              width: 60, height: 60, borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg, #00e676, #00b0ff)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 24, fontWeight: 800, color: '#0a0a0f',
            }}>
              {u.name[0]}
            </div>
            <div>
              <div style={{ fontSize: 17, fontWeight: 800, color: C.text }}>{u.name}</div>
              <div style={{ fontSize: 12, color: C.textSec }}>@{u.nickname}</div>
              <div style={{ fontSize: 11, color: C.textDim, marginTop: 2 }}>{u.email}</div>
            </div>
          </div>
          <button
            onClick={openProfileEdit}
            style={{
              width: '100%', padding: '9px 0', borderRadius: 10, fontSize: 13, fontWeight: 700,
              background: `${C.green}22`, border: `1px solid ${C.green}66`, color: C.green, cursor: 'pointer',
            }}
          >프로필 수정</button>
        </Card>

        {/* 구매자 정보 */}
        <Card>
          <CardTitle>구매자 정보</CardTitle>
          <InfoRow icon="📊" label="레벨"     value={`Lv.${u.level}`}    valueColor={C.blue} />
          <InfoRow icon="🏆" label="신뢰티어"  value={u.trust_tier}       valueColor="#c0c0c0" />
          <InfoRow icon="💰" label="포인트"    value={`${u.points.toLocaleString()}P`} valueColor={C.yellow} />
          <InfoRow icon="📅" label="가입일"    value={u.created_at.replace(/-/g, '.')} />
          <InfoRow icon="📦" label="총 참여"   value={`${u.total_orders}건`} />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 0' }}>
            <span style={{ fontSize: 13, color: C.textSec }}>생성한 딜</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{u.total_deals}건</span>
          </div>
        </Card>

        {/* 판매자 정보 */}
        {u.isSeller && u.seller && (
          <Card>
            <CardTitle>판매자 정보</CardTitle>
            <InfoRow icon="🏪" label="사업자명"      value={u.seller.business_name} />
            <InfoRow icon="📊" label="판매자 레벨"   value={`Lv.${u.seller.level}`}       valueColor={C.blue} />
            <InfoRow icon="💰" label="판매자 포인트" value={`${u.seller.points.toLocaleString()}P`} valueColor={C.yellow} />
            {/* 판매자 빠른 메뉴 */}
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 10 }}>빠른 메뉴</div>
              <div style={{ display: 'flex', gap: 8 }}>
                {[
                  { icon: '💵', label: '정산내역', path: '/settlements' },
                  { icon: '📝', label: '오퍼관리', path: '/seller/offers' },
                  { icon: '⭐', label: '리뷰관리', path: '/seller/reviews' },
                ].map(m => (
                  <button
                    key={m.label}
                    onClick={() => navigate(m.path)}
                    style={{
                      flex: 1, padding: '10px 4px', borderRadius: 10, fontSize: 11, fontWeight: 700,
                      background: C.bgEl, border: `1px solid ${C.border}`,
                      color: C.textSec, cursor: 'pointer',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                    }}
                  >
                    <span style={{ fontSize: 18 }}>{m.icon}</span>
                    <span>{m.label}</span>
                  </button>
                ))}
              </div>
            </div>
          </Card>
        )}

        {/* 계정 관리 */}
        <Card>
          <CardTitle>계정 관리</CardTitle>
          <button
            onClick={() => setShowPayModal(true)}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '11px 0', background: 'none', border: 'none', cursor: 'pointer',
              borderBottom: `1px solid ${C.border}`,
            }}
          >
            <span style={{ fontSize: 13, color: C.textSec }}>💳 결제수단 관리</span>
            <span style={{ fontSize: 14, color: C.textDim }}>›</span>
          </button>
          <ActionRow icon="🔔" label="알림 설정" onClick={() => navigate('/settings')} />
          <ActionRow icon="📋" label="이용약관" onClick={() => navigate('/terms')} />
          <ActionRow icon="💬" label="고객센터" onClick={() => navigate('/support')} />
        </Card>

      </div>

      {/* 프로필 수정 모달 */}
      {showProfileEdit && (
        <div
          onClick={() => setShowProfileEdit(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 2000, display: 'flex', alignItems: 'flex-end' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', maxHeight: '80dvh', background: C.bgCard,
              borderRadius: '20px 20px 0 0', padding: '20px 20px 40px', overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: C.text }}>프로필 수정</span>
              <button onClick={() => setShowProfileEdit(false)} style={{ fontSize: 18, color: C.textDim, cursor: 'pointer' }}>✕</button>
            </div>

            {[
              { label: '이름', value: editName, onChange: setEditName },
              { label: '닉네임', value: editNickname, onChange: setEditNickname },
              { label: '연락처', value: editPhone, onChange: setEditPhone },
              { label: '주소', value: editAddress, onChange: setEditAddress },
            ].map(field => (
              <div key={field.label} style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>{field.label}</div>
                <input
                  type="text" value={field.value}
                  onChange={e => field.onChange(e.target.value)}
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13,
                    background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
                    boxSizing: 'border-box' as const,
                  }}
                />
              </div>
            ))}

            <button
              onClick={saveProfile}
              disabled={saving}
              style={{
                width: '100%', padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                background: saving ? `${C.green}55` : `${C.green}22`, border: `1px solid ${C.green}66`,
                color: C.green, cursor: saving ? 'not-allowed' : 'pointer',
              }}
            >{saving ? '저장 중...' : '저장'}</button>
          </div>
        </div>
      )}

      {/* 결제수단 관리 모달 */}
      {showPayModal && (
        <div
          onClick={() => setShowPayModal(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 2000, display: 'flex', alignItems: 'flex-end' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', maxHeight: '80dvh', background: C.bgCard,
              borderRadius: '20px 20px 0 0', padding: '20px 20px 40px', overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: C.text }}>💳 결제수단 관리</span>
              <button onClick={() => setShowPayModal(false)} style={{ fontSize: 18, color: C.textDim, cursor: 'pointer' }}>✕</button>
            </div>

            <div style={{ fontSize: 11, color: C.textDim, fontWeight: 700, letterSpacing: 1, marginBottom: 10 }}>등록된 결제수단</div>

            {payMethods.map(m => (
              <div key={m.id} style={{
                background: C.bgEl, border: `1px solid ${m.isDefault ? C.green : C.border}`,
                borderRadius: 12, padding: '14px', marginBottom: 10,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 18 }}>{m.type === 'card' ? '💳' : '🏦'}</span>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{m.name}</div>
                      <div style={{ fontSize: 11, color: C.textSec }}>**** {m.last4}</div>
                    </div>
                  </div>
                  {m.isDefault && (
                    <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 6, background: `${C.green}22`, color: C.green }}>기본</span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  {!m.isDefault && (
                    <button onClick={() => setDefault(m.id)} style={{ flex: 1, padding: '6px', borderRadius: 8, fontSize: 11, fontWeight: 700, background: `${C.blue}22`, border: `1px solid ${C.blue}66`, color: C.blue, cursor: 'pointer' }}>기본으로 설정</button>
                  )}
                  <button onClick={() => removeMethod(m.id)} style={{ flex: 1, padding: '6px', borderRadius: 8, fontSize: 11, fontWeight: 700, background: 'rgba(255,82,82,0.1)', border: '1px solid rgba(255,82,82,0.3)', color: '#ff5252', cursor: 'pointer' }}>삭제</button>
                </div>
              </div>
            ))}

            {payMethods.length === 0 && (
              <div style={{ textAlign: 'center', padding: '20px 0', color: C.textDim, fontSize: 13 }}>등록된 결제수단이 없어요</div>
            )}

            <div style={{ padding: '12px 14px', background: 'rgba(255,152,0,0.08)', border: '1px solid rgba(255,152,0,0.25)', borderRadius: 10, marginTop: 8 }}>
              <div style={{ fontSize: 12, color: C.orange, lineHeight: 1.7 }}>
                오퍼 마감 후 결제 시간은 단 <strong>5분</strong>입니다. 미리 결제수단을 등록해주세요!
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
