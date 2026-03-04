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
      <span style={{ fontSize: 14, color: C.textDim }}>&rsaquo;</span>
    </button>
  );
}

const PAYMENT_OPTIONS = [
  { key: 'card',  label: '신용/체크카드', icon: '💳' },
  { key: 'bank',  label: '계좌이체',      icon: '🏦' },
  { key: 'kakao', label: '카카오페이',    icon: '💛' },
  { key: 'naver', label: '네이버페이',    icon: '💚' },
  { key: 'toss',  label: '토스페이',      icon: '💙' },
];

const GENDER_LABELS: Record<string, string> = { male: '남성', female: '여성', other: '기타' };

export default function MyPage() {
  const navigate = useNavigate();
  const { user: authUser } = useAuth();
  const [apiProfile, setApiProfile] = useState<Record<string, unknown> | null>(null);
  const [showProfileEdit, setShowProfileEdit] = useState(false);
  const [editName, setEditName] = useState('');
  const [editNickname, setEditNickname] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editAddress, setEditAddress] = useState('');
  const [editGender, setEditGender] = useState('');
  const [editBirthDate, setEditBirthDate] = useState('');
  const [editPaymentMethod, setEditPaymentMethod] = useState('');
  const [saving, setSaving] = useState(false);

  // password change
  const [showPwModal, setShowPwModal] = useState(false);
  const [curPw, setCurPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [newPwConfirm, setNewPwConfirm] = useState('');
  const [pwError, setPwError] = useState('');
  const [pwSaving, setPwSaving] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);

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
    gender:       String(apiProfile?.gender ?? ''),
    birth_date:   String(apiProfile?.birth_date ?? '').split('T')[0] || '',
    payment_method: String(apiProfile?.payment_method ?? ''),
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
    setEditGender(u.gender);
    setEditBirthDate(u.birth_date);
    setEditPaymentMethod(u.payment_method);
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
        gender: editGender || undefined,
        birth_date: editBirthDate || undefined,
        payment_method: editPaymentMethod || undefined,
      });
      setApiProfile(prev => ({
        ...prev,
        name: editName,
        nickname: editNickname,
        phone: editPhone,
        address: editAddress,
        gender: editGender,
        birth_date: editBirthDate,
        payment_method: editPaymentMethod,
      }));
      setShowProfileEdit(false);
    } catch {
      alert('회원정보 수정에 실패했어요');
    }
    setSaving(false);
  };

  const handlePasswordChange = async () => {
    setPwError('');
    if (!curPw || !newPw) { setPwError('모든 필드를 입력해주세요'); return; }
    if (newPw.length < 8) { setPwError('새 비밀번호는 8자 이상이어야 해요'); return; }
    if (newPw !== newPwConfirm) { setPwError('새 비밀번호가 일치하지 않아요'); return; }
    setPwSaving(true);
    try {
      await apiClient.post('/auth/change-password', {
        user_id: u.id,
        user_type: u.isSeller ? 'seller' : 'buyer',
        current_password: curPw,
        new_password: newPw,
      });
      setShowPwModal(false);
      setCurPw(''); setNewPw(''); setNewPwConfirm('');
      alert('비밀번호가 변경되었어요');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e.response?.data?.detail;
      setPwError(typeof detail === 'string' ? detail : '비밀번호 변경에 실패했어요');
    }
    setPwSaving(false);
  };

  const [showPayModal, setShowPayModal] = useState(false);
  const [payModalMethod, setPayModalMethod] = useState('');
  const [payModalSaving, setPayModalSaving] = useState(false);

  const openPayModal = () => {
    setPayModalMethod(u.payment_method);
    setShowPayModal(true);
  };

  const savePaymentMethod = async () => {
    setPayModalSaving(true);
    try {
      await apiClient.patch(API.BUYERS.UPDATE(u.id), { payment_method: payModalMethod || null });
      setApiProfile(prev => ({ ...prev, payment_method: payModalMethod }));
      setShowPayModal(false);
    } catch {
      alert('결제수단 저장에 실패했어요');
    }
    setPayModalSaving(false);
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>

      {/* TopBar */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px',
        background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>&#x2190;</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>마이페이지</span>
        <button onClick={() => navigate('/notifications')} style={{ fontSize: 20, color: C.textSec, cursor: 'pointer', lineHeight: 1 }}>&#x1F514;</button>
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
          >회원정보 수정</button>
        </Card>

        {/* 회원 정보 */}
        <Card>
          <CardTitle>회원 정보</CardTitle>
          <InfoRow icon="&#x1F4E7;" label="이메일" value={u.email} />
          <InfoRow icon="&#x1F464;" label="닉네임" value={u.nickname || '-'} />
          <InfoRow icon="&#x1F4DE;" label="전화번호" value={u.phone || '미등록'} />
          <InfoRow icon="&#x1F3E0;" label="주소" value={u.address || '미등록'} />
          <InfoRow icon="&#x1F9D1;" label="성별" value={GENDER_LABELS[u.gender] || '미등록'} />
          <InfoRow icon="&#x1F382;" label="생년월일" value={u.birth_date || '미등록'} />
          <InfoRow icon="&#x1F4B3;" label="결제수단" value={PAYMENT_OPTIONS.find(p => p.key === u.payment_method)?.label || '미등록'} />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 0' }}>
            <span style={{ fontSize: 13, color: C.textSec }}>&#x1F512; 비밀번호</span>
            <button
              onClick={() => { setPwError(''); setCurPw(''); setNewPw(''); setNewPwConfirm(''); setShowPwModal(true); }}
              style={{ fontSize: 12, fontWeight: 700, color: C.blue, cursor: 'pointer', background: 'none', border: 'none', padding: 0 }}
            >변경하기</button>
          </div>
        </Card>

        {/* 구매자 정보 */}
        <Card>
          <CardTitle>구매자 정보</CardTitle>
          <InfoRow icon="&#x1F4CA;" label="레벨"     value={`Lv.${u.level}`}    valueColor={C.blue} />
          <InfoRow icon="&#x1F3C6;" label="신뢰티어"  value={u.trust_tier}       valueColor="#c0c0c0" />
          <InfoRow icon="&#x1F4B0;" label="포인트"    value={`${u.points.toLocaleString()}P`} valueColor={C.yellow} />
          <InfoRow icon="&#x1F4C5;" label="가입일"    value={u.created_at.replace(/-/g, '.')} />
          <InfoRow icon="&#x1F4E6;" label="총 참여"   value={`${u.total_orders}건`} />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '7px 0' }}>
            <span style={{ fontSize: 13, color: C.textSec }}>생성한 딜</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: C.text }}>{u.total_deals}건</span>
          </div>
        </Card>

        {/* 판매자 정보 */}
        {u.isSeller && u.seller && (
          <Card>
            <CardTitle>판매자 정보</CardTitle>
            <InfoRow icon="&#x1F3EA;" label="사업자명"      value={u.seller.business_name} />
            <InfoRow icon="&#x1F4CA;" label="판매자 레벨"   value={`Lv.${u.seller.level}`}       valueColor={C.blue} />
            <InfoRow icon="&#x1F4B0;" label="판매자 포인트" value={`${u.seller.points.toLocaleString()}P`} valueColor={C.yellow} />
            {/* 판매자 빠른 메뉴 */}
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 10 }}>빠른 메뉴</div>
              <div style={{ display: 'flex', gap: 8 }}>
                {[
                  { icon: '&#x1F4B5;', label: '정산내역', path: '/settlements' },
                  { icon: '&#x1F4DD;', label: '오퍼관리', path: '/seller/offers' },
                  { icon: '&#x2B50;', label: '리뷰관리', path: '/seller/reviews' },
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
                    <span style={{ fontSize: 18 }} dangerouslySetInnerHTML={{ __html: m.icon }} />
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
            onClick={openPayModal}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '11px 0', background: 'none', border: 'none', cursor: 'pointer',
              borderBottom: `1px solid ${C.border}`,
            }}
          >
            <span style={{ fontSize: 13, color: C.textSec }}>💳 결제수단 관리</span>
            <span style={{ fontSize: 14, color: C.textDim }}>&rsaquo;</span>
          </button>
          <ActionRow icon="🔔" label="알림 설정" onClick={() => navigate('/settings')} />
          <ActionRow icon="📋" label="이용약관" onClick={() => navigate('/terms')} />
          <ActionRow icon="💬" label="고객센터" onClick={() => navigate('/support')} />
        </Card>

      </div>

      {/* 회원정보 수정 모달 */}
      {showProfileEdit && (
        <div
          onClick={() => setShowProfileEdit(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 2000, display: 'flex', alignItems: 'flex-end' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', maxHeight: '85dvh', background: C.bgCard,
              borderRadius: '20px 20px 0 0', padding: '20px 20px 40px', overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: C.text }}>회원정보 수정</span>
              <button onClick={() => setShowProfileEdit(false)} style={{ fontSize: 18, color: C.textDim, cursor: 'pointer' }}>&#x2715;</button>
            </div>

            {[
              { label: '이름', value: editName, onChange: setEditName, type: 'text' },
              { label: '닉네임', value: editNickname, onChange: setEditNickname, type: 'text' },
              { label: '전화번호', value: editPhone, onChange: setEditPhone, type: 'tel' },
              { label: '주소', value: editAddress, onChange: setEditAddress, type: 'text' },
            ].map(field => (
              <div key={field.label} style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>{field.label}</div>
                <input
                  type={field.type} value={field.value}
                  onChange={e => field.onChange(e.target.value)}
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13,
                    background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
                    boxSizing: 'border-box' as const,
                  }}
                />
              </div>
            ))}

            {/* 성별 */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>성별</div>
              <div style={{ display: 'flex', gap: 6 }}>
                {[{ key: 'male', label: '남성' }, { key: 'female', label: '여성' }, { key: 'other', label: '기타' }].map(g => {
                  const active = editGender === g.key;
                  return (
                    <button
                      key={g.key}
                      onClick={() => setEditGender(active ? '' : g.key)}
                      style={{
                        flex: 1, padding: '8px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                        background: active ? `${C.green}22` : C.bgEl,
                        border: `1px solid ${active ? C.green : C.border}`,
                        color: active ? C.green : C.textSec,
                        cursor: 'pointer',
                      }}
                    >{g.label}</button>
                  );
                })}
              </div>
            </div>

            {/* 생년월일 */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>생년월일</div>
              <input
                type="date" value={editBirthDate}
                onChange={e => setEditBirthDate(e.target.value)}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13,
                  background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
                  boxSizing: 'border-box' as const,
                }}
              />
            </div>

            {/* 결제수단 */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>결제수단</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {PAYMENT_OPTIONS.map(opt => {
                  const active = editPaymentMethod === opt.key;
                  return (
                    <button
                      key={opt.key}
                      onClick={() => setEditPaymentMethod(active ? '' : opt.key)}
                      style={{
                        padding: '7px 12px', borderRadius: 8, fontSize: 12, fontWeight: 600,
                        background: active ? `${C.green}22` : C.bgEl,
                        border: `1px solid ${active ? C.green : C.border}`,
                        color: active ? C.green : C.textSec,
                        cursor: 'pointer',
                      }}
                    >{opt.icon} {opt.label}</button>
                  );
                })}
              </div>
            </div>

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

      {/* 비밀번호 변경 모달 */}
      {showPwModal && (
        <div
          onClick={() => setShowPwModal(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 2000, display: 'flex', alignItems: 'flex-end' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', maxHeight: '70dvh', background: C.bgCard,
              borderRadius: '20px 20px 0 0', padding: '20px 20px 40px', overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: C.text }}>비밀번호 변경</span>
              <button onClick={() => setShowPwModal(false)} style={{ fontSize: 18, color: C.textDim, cursor: 'pointer' }}>&#x2715;</button>
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>현재 비밀번호</div>
              <input
                type="password" value={curPw}
                onChange={e => setCurPw(e.target.value)}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13,
                  background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
                  boxSizing: 'border-box' as const,
                }}
              />
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>새 비밀번호</div>
              <div style={{ position: 'relative' }}>
                <input
                  type={showNewPw ? 'text' : 'password'} value={newPw}
                  onChange={e => setNewPw(e.target.value)}
                  placeholder="8자 이상 입력"
                  style={{
                    width: '100%', padding: '10px 36px 10px 12px', borderRadius: 10, fontSize: 13,
                    background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
                    boxSizing: 'border-box' as const,
                  }}
                />
                <button
                  onClick={() => setShowNewPw(!showNewPw)}
                  style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 16, cursor: 'pointer', color: C.textDim, background: 'none', border: 'none' }}
                >{showNewPw ? '🙈' : '👁'}</button>
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>새 비밀번호 확인</div>
              <input
                type="password" value={newPwConfirm}
                onChange={e => setNewPwConfirm(e.target.value)}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13,
                  background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
                  boxSizing: 'border-box' as const,
                }}
              />
            </div>

            {pwError && (
              <div style={{ fontSize: 12, color: '#ff5252', marginBottom: 14, padding: '8px 12px', borderRadius: 8, background: 'rgba(255,82,82,0.08)' }}>
                {pwError}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setShowPwModal(false)}
                style={{
                  flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer',
                }}
              >취소</button>
              <button
                onClick={handlePasswordChange}
                disabled={pwSaving}
                style={{
                  flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  background: pwSaving ? `${C.green}55` : `${C.green}22`, border: `1px solid ${C.green}66`,
                  color: C.green, cursor: pwSaving ? 'not-allowed' : 'pointer',
                }}
              >{pwSaving ? '변경 중...' : '변경'}</button>
            </div>
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
              <span style={{ fontSize: 16, fontWeight: 800, color: C.text }}>결제수단 관리</span>
              <button onClick={() => setShowPayModal(false)} style={{ fontSize: 18, color: C.textDim, cursor: 'pointer' }}>&#x2715;</button>
            </div>

            <div style={{ fontSize: 11, color: C.textDim, fontWeight: 700, letterSpacing: 1, marginBottom: 12 }}>선호 결제수단 선택</div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
              {PAYMENT_OPTIONS.map(opt => {
                const active = payModalMethod === opt.key;
                return (
                  <button
                    key={opt.key}
                    onClick={() => setPayModalMethod(active ? '' : opt.key)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 12,
                      padding: '14px 16px', borderRadius: 12, cursor: 'pointer',
                      background: active ? `${C.green}12` : C.bgEl,
                      border: `1.5px solid ${active ? C.green : C.border}`,
                      transition: 'all 0.15s',
                    }}
                  >
                    <span style={{ fontSize: 20 }}>{opt.icon}</span>
                    <span style={{ fontSize: 13, fontWeight: 600, color: active ? C.green : C.text, flex: 1, textAlign: 'left' }}>{opt.label}</span>
                    {active && <span style={{ fontSize: 14, color: C.green, fontWeight: 800 }}>&#x2713;</span>}
                  </button>
                );
              })}
            </div>

            <div style={{ padding: '12px 14px', background: 'rgba(255,152,0,0.08)', border: '1px solid rgba(255,152,0,0.25)', borderRadius: 10, marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: C.orange, lineHeight: 1.7 }}>
                오퍼 마감 후 결제 시간은 단 <strong>5분</strong>입니다. 미리 결제수단을 등록해주세요!
              </div>
            </div>

            <button
              onClick={savePaymentMethod}
              disabled={payModalSaving}
              style={{
                width: '100%', padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                background: payModalSaving ? `${C.green}55` : `${C.green}22`, border: `1px solid ${C.green}66`,
                color: C.green, cursor: payModalSaving ? 'not-allowed' : 'pointer',
              }}
            >{payModalSaving ? '저장 중...' : '저장'}</button>
          </div>
        </div>
      )}
    </div>
  );
}
