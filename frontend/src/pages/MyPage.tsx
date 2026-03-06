import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { showToast } from '../components/common/Toast';

// ── Daum Postcode 타입 ───────────────────────────────────
declare global {
  interface Window {
    daum?: {
      Postcode: new (options: {
        oncomplete: (data: { zonecode: string; address: string }) => void;
      }) => { open: () => void };
    };
  }
}

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
  red:     '#ff5252',
};

const PAYMENT_OPTIONS = [
  { key: 'card',  label: '신용/체크카드', icon: '💳' },
  { key: 'bank',  label: '계좌이체',      icon: '🏦' },
  { key: 'kakao', label: '카카오페이',    icon: '💛' },
  { key: 'naver', label: '네이버페이',    icon: '💚' },
  { key: 'toss',  label: '토스페이',      icon: '💙' },
];

const GENDER_LABELS: Record<string, string> = { male: '남성', female: '여성', other: '기타' };

function formatKSTDate(raw: string): string {
  if (!raw || raw === '-') return '-';
  try {
    const d = new Date(raw);
    if (isNaN(d.getTime())) return raw.split('T')[0]?.replace(/-/g, '.') || '-';
    // UTC → KST (+9h)
    d.setHours(d.getHours() + 9);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}.${m}.${day}`;
  } catch {
    return '-';
  }
}

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

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

function InfoRow({ label, value, valueColor }: {
  label: string; value: string; valueColor?: string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '9px 0', borderBottom: `1px solid ${C.border}` }}>
      <span style={{ fontSize: 13, color: C.textSec }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color: valueColor ?? C.text, maxWidth: '60%', textAlign: 'right', wordBreak: 'break-word' }}>{value}</span>
    </div>
  );
}

export default function MyPage() {
  const navigate = useNavigate();
  const { user: authUser, logout } = useAuth();
  const [apiProfile, setApiProfile] = useState<Record<string, unknown> | null>(null);
  const [sellerProfile, setSellerProfile] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!authUser) return;
    apiClient.get(API.BUYERS.PROFILE)
      .then(res => { if (res.data) setApiProfile(res.data as Record<string, unknown>); })
      .catch(() => {});
    // seller profile fetch
    if (authUser.role === 'seller' || authUser.role === 'both') {
      apiClient.get(API.SELLERS.PROFILE)
        .then(res => { if (res.data) setSellerProfile(res.data as Record<string, unknown>); })
        .catch(() => {});
    }
  }, [authUser]);

  const u = {
    id:              Number(apiProfile?.id ?? authUser?.id ?? 0),
    name:            String(apiProfile?.name ?? authUser?.name ?? '사용자'),
    nickname:        String(apiProfile?.nickname ?? authUser?.nickname ?? ''),
    email:           String(apiProfile?.email ?? authUser?.email ?? ''),
    level:           Number(apiProfile?.level ?? authUser?.level ?? 1),
    trust_tier:      String(apiProfile?.trust_tier ?? authUser?.trust_tier ?? 'Bronze'),
    points:          Number(apiProfile?.points ?? authUser?.points ?? 0),
    phone:           String(apiProfile?.phone ?? ''),
    address:         String(apiProfile?.address ?? ''),
    zip_code:        String(apiProfile?.zip_code ?? ''),
    shipping_address:String(apiProfile?.shipping_address ?? ''),
    gender:          String(apiProfile?.gender ?? ''),
    birth_date:      String(apiProfile?.birth_date ?? '').split('T')[0] || '',
    payment_method:  String(apiProfile?.payment_method ?? ''),
    created_at:      String(apiProfile?.created_at ?? ''),
    is_active:       Boolean(apiProfile?.is_active ?? true),
    isSeller:        authUser?.role === 'seller' || authUser?.role === 'both',
    seller:          authUser?.seller,
  };

  // ── Edit Modal State ────────────────────────────────────
  const [showEditModal, setShowEditModal] = useState(false);
  const [editNickname, setEditNickname] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editAddress, setEditAddress] = useState('');
  const [editZipCode, setEditZipCode] = useState('');
  const [editAddressDetail, setEditAddressDetail] = useState('');
  const [editShippingAddr, setEditShippingAddr] = useState('');
  const [editShippingZip, setEditShippingZip] = useState('');
  const [editShippingDetail, setEditShippingDetail] = useState('');
  const [editSameAddr, setEditSameAddr] = useState(false);
  const [editGender, setEditGender] = useState('');
  const [editBirthYear, setEditBirthYear] = useState('');
  const [editBirthMonth, setEditBirthMonth] = useState('');
  const [editBirthDay, setEditBirthDay] = useState('');
  const [editPaymentMethod, setEditPaymentMethod] = useState('');

  // password change in edit modal
  const [editCurPw, setEditCurPw] = useState('');
  const [editNewPw, setEditNewPw] = useState('');
  const [editNewPwConfirm, setEditNewPwConfirm] = useState('');
  const [showEditNewPw, setShowEditNewPw] = useState(false);
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState('');

  // ── Seller Edit Modal State ─────────────────────────────
  const [showSellerEdit, setShowSellerEdit] = useState(false);
  const [sellerEditPhone, setSellerEditPhone] = useState('');
  const [sellerEditCompanyPhone, setSellerEditCompanyPhone] = useState('');
  const [sellerEditAddress, setSellerEditAddress] = useState('');
  const [sellerEditZipCode, setSellerEditZipCode] = useState('');
  const [sellerEditBankName, setSellerEditBankName] = useState('');
  const [sellerEditAccountNum, setSellerEditAccountNum] = useState('');
  const [sellerEditAccountHolder, setSellerEditAccountHolder] = useState('');
  const [sellerEditSaving, setSellerEditSaving] = useState(false);
  const [sellerEditError, setSellerEditError] = useState('');

  const openSellerEditModal = () => {
    const sp = sellerProfile || {};
    setSellerEditPhone(String(sp.phone ?? ''));
    setSellerEditCompanyPhone(String(sp.company_phone ?? ''));
    setSellerEditAddress(String(sp.address ?? ''));
    setSellerEditZipCode(String(sp.zip_code ?? ''));
    setSellerEditBankName(String(sp.bank_name ?? ''));
    setSellerEditAccountNum(String(sp.account_number ?? ''));
    setSellerEditAccountHolder(String(sp.account_holder ?? ''));
    setSellerEditError('');
    setShowSellerEdit(true);
  };

  const saveSellerProfile = async () => {
    if (!sellerProfile) return;
    setSellerEditSaving(true);
    setSellerEditError('');
    try {
      await apiClient.patch(API.SELLERS.UPDATE(Number(sellerProfile.id)), {
        phone: sellerEditPhone || undefined,
        company_phone: sellerEditCompanyPhone || undefined,
        address: sellerEditAddress || undefined,
        zip_code: sellerEditZipCode || undefined,
        bank_name: sellerEditBankName || undefined,
        account_number: sellerEditAccountNum || undefined,
        account_holder: sellerEditAccountHolder || undefined,
      });
      // refresh
      const res = await apiClient.get(API.SELLERS.PROFILE);
      if (res.data) setSellerProfile(res.data as Record<string, unknown>);
      setShowSellerEdit(false);
      showToast('판매자 정보가 수정되었어요', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e.response?.data?.detail;
      setSellerEditError(typeof detail === 'string' ? detail : '판매자 정보 수정에 실패했어요');
    }
    setSellerEditSaving(false);
  };

  // ── Withdraw Modal State ────────────────────────────────
  const [showWithdraw, setShowWithdraw] = useState(false);
  const [withdrawPw, setWithdrawPw] = useState('');
  const [withdrawReason, setWithdrawReason] = useState('');
  const [withdrawReasonText, setWithdrawReasonText] = useState('');
  const [withdrawing, setWithdrawing] = useState(false);

  const openEditModal = () => {
    setEditNickname(u.nickname);
    setEditPhone(u.phone);
    // parse address (may contain detail after base)
    setEditAddress(u.address);
    setEditZipCode(u.zip_code);
    setEditAddressDetail('');
    setEditShippingAddr(u.shipping_address);
    setEditShippingZip('');
    setEditShippingDetail('');
    setEditSameAddr(false);
    setEditGender(u.gender);
    // parse birth_date
    if (u.birth_date) {
      const parts = u.birth_date.split('-');
      setEditBirthYear(parts[0] || '');
      setEditBirthMonth(parts[1] ? String(Number(parts[1])) : '');
      setEditBirthDay(parts[2] ? String(Number(parts[2])) : '');
    } else {
      setEditBirthYear(''); setEditBirthMonth(''); setEditBirthDay('');
    }
    setEditPaymentMethod(u.payment_method);
    setEditCurPw(''); setEditNewPw(''); setEditNewPwConfirm('');
    setShowEditNewPw(false);
    setEditError('');
    setShowEditModal(true);
  };

  const openDaumPost = (target: 'main' | 'shipping') => {
    if (!window.daum?.Postcode) {
      showToast('주소 검색 서비스를 불러오는 중이에요.', 'info');
      return;
    }
    new window.daum.Postcode({
      oncomplete: (data) => {
        if (target === 'main') {
          setEditAddress(data.address);
          setEditZipCode(data.zonecode);
        } else {
          setEditShippingAddr(data.address);
          setEditShippingZip(data.zonecode);
        }
      },
    }).open();
  };

  const saveProfile = async () => {
    setEditSaving(true);
    setEditError('');
    try {
      const fullAddress = editAddress ? (editAddressDetail ? `${editAddress} ${editAddressDetail}` : editAddress) : undefined;
      const fullBirthDate = editBirthYear && editBirthMonth && editBirthDay
        ? `${editBirthYear}-${String(editBirthMonth).padStart(2, '0')}-${String(editBirthDay).padStart(2, '0')}`
        : undefined;

      await apiClient.patch(API.BUYERS.UPDATE(u.id), {
        nickname: editNickname || undefined,
        phone: editPhone || undefined,
        address: fullAddress,
        zip_code: editZipCode || undefined,
        gender: editGender || undefined,
        birth_date: fullBirthDate || undefined,
        payment_method: editPaymentMethod || null,
      });

      // password change if filled
      if (editCurPw && editNewPw) {
        if (editNewPw.length < 8) {
          setEditError('새 비밀번호는 8자 이상이어야 해요');
          setEditSaving(false);
          return;
        }
        if (editNewPw !== editNewPwConfirm) {
          setEditError('새 비밀번호가 일치하지 않아요');
          setEditSaving(false);
          return;
        }
        await apiClient.post(API.AUTH.CHANGE_PASSWORD, {
          user_id: u.id,
          user_type: u.isSeller ? 'seller' : 'buyer',
          current_password: editCurPw,
          new_password: editNewPw,
        });
      }

      // refresh profile
      const res = await apiClient.get(API.BUYERS.PROFILE);
      if (res.data) setApiProfile(res.data as Record<string, unknown>);

      setShowEditModal(false);
      showToast('회원정보가 수정되었어요', 'success');
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: unknown } } };
      const detail = e.response?.data?.detail;
      setEditError(typeof detail === 'string' ? detail : '회원정보 수정에 실패했어요');
    }
    setEditSaving(false);
  };

  const handleWithdraw = async () => {
    if (!withdrawReason) { showToast('탈퇴 사유를 선택해주세요', 'error'); return; }
    if (withdrawReason === '기타' && !withdrawReasonText.trim()) { showToast('탈퇴 사유를 입력해주세요', 'error'); return; }
    if (!withdrawPw) { showToast('비밀번호를 입력해주세요', 'error'); return; }
    setWithdrawing(true);
    const reason = withdrawReason === '기타' ? withdrawReasonText.trim() : withdrawReason;
    try {
      await apiClient.delete(API.ACCOUNT.WITHDRAW, {
        data: {
          user_id: u.id,
          user_type: 'buyer',
          password: withdrawPw,
          reason,
        },
      });
      showToast('회원 탈퇴가 완료되었어요', 'info');
      logout();
      navigate('/login');
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: unknown } } };
      if (e.response?.status === 409) {
        showToast('진행 중인 딜이 있어요. 완료 후 탈퇴해주세요.', 'error');
      } else if (e.response?.status === 401) {
        showToast('비밀번호가 올바르지 않아요', 'error');
      } else {
        const detail = e.response?.data?.detail;
        showToast(typeof detail === 'string' ? detail : '탈퇴에 실패했어요', 'error');
      }
    }
    setWithdrawing(false);
  };

  // ── Edit modal helpers ──────────────────────────────────
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: currentYear - 1920 + 1 }, (_, i) => currentYear - i);
  const months = Array.from({ length: 12 }, (_, i) => i + 1);
  const maxDay = editBirthYear && editBirthMonth ? daysInMonth(Number(editBirthYear), Number(editBirthMonth)) : 31;
  const days = Array.from({ length: maxDay }, (_, i) => i + 1);

  const selectStyle: React.CSSProperties = {
    flex: 1, padding: '8px 6px', borderRadius: 10, fontSize: 13,
    background: '#1a1a2e', border: `1px solid ${C.border}`, color: '#ffffff',
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13,
    background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
    boxSizing: 'border-box' as const,
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
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1, background: 'none', border: 'none' }}>&#x2190;</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>마이페이지</span>
        <button onClick={() => navigate('/notifications')} style={{ fontSize: 20, color: C.textSec, cursor: 'pointer', lineHeight: 1, background: 'none', border: 'none' }}>&#x1F514;</button>
      </div>

      <div style={{ padding: '16px 16px 0' }}>

        {/* 프로필 카드 — View Only */}
        <Card style={{ borderTop: `3px solid ${C.green}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
            <div style={{
              width: 56, height: 56, borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg, #00e676, #00b0ff)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 22, fontWeight: 800, color: '#0a0a0f',
            }}>
              {(u.nickname || u.name)[0]}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 17, fontWeight: 800, color: C.text }}>{u.nickname || u.name}</span>
                <span style={{
                  padding: '2px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700,
                  background: authUser?.role === 'admin' ? 'rgba(224,64,251,0.12)'
                    : (authUser?.role === 'seller' || authUser?.role === 'both') ? 'rgba(255,145,0,0.12)'
                    : 'rgba(0,230,118,0.12)',
                  color: authUser?.role === 'admin' ? '#e040fb'
                    : (authUser?.role === 'seller' || authUser?.role === 'both') ? '#ff9100'
                    : '#00e676',
                }}>
                  {authUser?.role === 'admin' ? '관리자' : (authUser?.role === 'seller' || authUser?.role === 'both') ? '판매자' : '구매자'}
                </span>
              </div>
              <div style={{ fontSize: 12, color: C.textSec }}>{u.email} | {u.phone || '전화번호 미등록'}</div>
            </div>
          </div>

          <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 12 }}>
            <InfoRow label="주소" value={u.address || '미등록'} />
            <InfoRow label="배송지주소" value={u.shipping_address || u.address || '미등록'} />
            <InfoRow label="성별" value={GENDER_LABELS[u.gender] || '미등록'} />
            <InfoRow label="생년월일" value={u.birth_date ? u.birth_date.replace(/-/g, '.') : '미등록'} />
            <InfoRow label="가입일" value={formatKSTDate(u.created_at)} />
            <InfoRow label="결제수단" value={PAYMENT_OPTIONS.find(p => p.key === u.payment_method)?.label || '미등록'} />
          </div>

          <button
            onClick={openEditModal}
            style={{
              width: '100%', marginTop: 14, padding: '11px 0', borderRadius: 12, fontSize: 13, fontWeight: 700,
              background: `${C.green}22`, border: `1px solid ${C.green}66`, color: C.green, cursor: 'pointer',
            }}
          >회원정보 수정</button>
        </Card>

        {/* 구매자 정보 */}
        <Card>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 12 }}>구매자 정보</div>
          <InfoRow label="레벨" value={`Lv.${u.level}`} valueColor={C.blue} />
          <InfoRow label="신뢰티어" value={u.trust_tier} valueColor="#c0c0c0" />
          <InfoRow label="포인트" value={`${u.points.toLocaleString()}P`} valueColor={C.yellow} />
        </Card>

        {/* 판매자 정보 */}
        {u.isSeller && (sellerProfile || u.seller) && (() => {
          const sp = sellerProfile || (u.seller as Record<string, unknown> | undefined) || {};
          const verifiedAt = String(sp.verified_at ?? '');
          const isVerified = !!verifiedAt && verifiedAt !== '' && verifiedAt !== 'null' && verifiedAt !== 'None';
          return (
            <Card>
              <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 12 }}>판매자 정보</div>
              <InfoRow label="사업자명" value={String(sp.business_name ?? '-')} />
              <InfoRow label="사업자번호" value={String(sp.business_number ?? '-')} />
              <InfoRow label="회사전화" value={String(sp.company_phone ?? '미등록')} />
              <InfoRow label="주소" value={String(sp.address ?? '미등록')} />
              <InfoRow label="정산 은행" value={String(sp.bank_name ?? '미등록')} />
              <InfoRow label="정산 계좌" value={String(sp.account_number ?? '미등록')} />
              <InfoRow label="예금주" value={String(sp.account_holder ?? '미등록')} />
              <InfoRow label="판매자 레벨" value={`Lv.${sp.level ?? 1}`} valueColor={C.blue} />
              <InfoRow label="판매자 포인트" value={`${Number(sp.points ?? 0).toLocaleString()}P`} valueColor={C.yellow} />
              <InfoRow label="검증 상태" value={isVerified ? '승인됨' : '승인 대기'} valueColor={isVerified ? C.green : C.orange} />

              <button
                onClick={openSellerEditModal}
                style={{
                  width: '100%', marginTop: 14, padding: '11px 0', borderRadius: 12, fontSize: 13, fontWeight: 700,
                  background: `${C.blue}22`, border: `1px solid ${C.blue}66`, color: C.blue, cursor: 'pointer',
                }}
              >판매자 정보 수정</button>

              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 10 }}>빠른 메뉴</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  {[
                    { icon: '📝', label: '내 오퍼', path: '/seller/offers' },
                    { icon: '📦', label: '배송관리', path: '/seller/delivery' },
                    { icon: '💵', label: '정산관리', path: '/seller/settlements' },
                    { icon: '📊', label: '판매통계', path: '/seller/stats' },
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
          );
        })()}

        {/* 계정 관리 */}
        <Card>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 12 }}>계정 관리</div>
          {[
            { icon: '🔔', label: '알림 설정', path: '/settings' },
            { icon: '📋', label: '이용약관', path: '/terms' },
            { icon: '💬', label: '고객센터', path: '/support' },
          ].map(m => (
            <button
              key={m.label}
              onClick={() => navigate(m.path)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '11px 0', background: 'none', border: 'none', cursor: 'pointer',
                borderBottom: `1px solid ${C.border}`,
              }}
            >
              <span style={{ fontSize: 13, color: C.textSec }}>{m.icon} {m.label}</span>
              <span style={{ fontSize: 14, color: C.textDim }}>&rsaquo;</span>
            </button>
          ))}
        </Card>

        {/* 회원 탈퇴 */}
        <div style={{ textAlign: 'center', marginTop: 16, marginBottom: 32 }}>
          <button
            onClick={() => { setWithdrawPw(''); setWithdrawReason(''); setWithdrawReasonText(''); setShowWithdraw(true); }}
            style={{ fontSize: 12, color: C.textDim, cursor: 'pointer', background: 'none', border: 'none', textDecoration: 'underline' }}
          >회원 탈퇴</button>
        </div>
      </div>

      {/* ════════════════════════════════════════════════════
          회원정보 수정 BottomSheet
         ════════════════════════════════════════════════════ */}
      {showEditModal && (
        <div
          onClick={() => setShowEditModal(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 2000, display: 'flex', alignItems: 'flex-end' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', maxHeight: '90dvh', background: C.bgCard,
              borderRadius: '20px 20px 0 0', padding: '20px 20px 40px', overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: C.text }}>회원정보 수정</span>
              <button onClick={() => setShowEditModal(false)} style={{ fontSize: 18, color: C.textDim, cursor: 'pointer', background: 'none', border: 'none' }}>✕</button>
            </div>

            {/* 기본 정보 */}
            <div style={{ fontSize: 11, color: C.textDim, fontWeight: 700, marginBottom: 10, letterSpacing: 1 }}>기본 정보</div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>이메일 (변경 불가)</div>
              <input readOnly value={u.email} style={{ ...inputStyle, opacity: 0.5 }} />
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>닉네임</div>
              <input value={editNickname} onChange={e => setEditNickname(e.target.value)} style={inputStyle} />
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>전화번호</div>
              <input type="tel" value={editPhone} onChange={e => setEditPhone(e.target.value)} style={inputStyle} />
            </div>

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

            {/* 생년월일 — 3 selects */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>생년월일</div>
              <div style={{ display: 'flex', gap: 6 }}>
                <select value={editBirthYear} onChange={e => setEditBirthYear(e.target.value)} style={selectStyle}>
                  <option value="" style={{ background: '#1a1a2e', color: '#ffffff' }}>년도</option>
                  {years.map(y => <option key={y} value={y} style={{ background: '#1a1a2e', color: '#ffffff' }}>{y}년</option>)}
                </select>
                <select value={editBirthMonth} onChange={e => setEditBirthMonth(e.target.value)} style={selectStyle}>
                  <option value="" style={{ background: '#1a1a2e', color: '#ffffff' }}>월</option>
                  {months.map(m => <option key={m} value={m} style={{ background: '#1a1a2e', color: '#ffffff' }}>{m}월</option>)}
                </select>
                <select value={editBirthDay} onChange={e => setEditBirthDay(e.target.value)} style={selectStyle}>
                  <option value="" style={{ background: '#1a1a2e', color: '#ffffff' }}>일</option>
                  {days.map(d => <option key={d} value={d} style={{ background: '#1a1a2e', color: '#ffffff' }}>{d}일</option>)}
                </select>
              </div>
            </div>

            {/* 주소 */}
            <div style={{ fontSize: 11, color: C.textDim, fontWeight: 700, marginTop: 16, marginBottom: 10, letterSpacing: 1 }}>주소</div>

            <div style={{ marginBottom: 8 }}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                <input readOnly value={editZipCode ? `[${editZipCode}] ${editAddress}` : editAddress} placeholder="주소 검색" style={{ ...inputStyle, flex: 1 }} />
                <button onClick={() => openDaumPost('main')} style={{ padding: '10px 12px', borderRadius: 10, fontSize: 12, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.blue, cursor: 'pointer', whiteSpace: 'nowrap' }}>주소 검색</button>
              </div>
              <input value={editAddressDetail} onChange={e => setEditAddressDetail(e.target.value)} placeholder="상세주소" style={inputStyle} />
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: C.textDim }}>배송지 주소</span>
                <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: C.textSec, cursor: 'pointer' }}>
                  <input type="checkbox" checked={editSameAddr} onChange={e => {
                    setEditSameAddr(e.target.checked);
                    if (e.target.checked) {
                      setEditShippingAddr(editAddress);
                      setEditShippingZip(editZipCode);
                      setEditShippingDetail(editAddressDetail);
                    }
                  }} />
                  위와 동일
                </label>
              </div>
              {!editSameAddr && (
                <>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                    <input readOnly value={editShippingZip ? `[${editShippingZip}] ${editShippingAddr}` : editShippingAddr} placeholder="주소 검색" style={{ ...inputStyle, flex: 1 }} />
                    <button onClick={() => openDaumPost('shipping')} style={{ padding: '10px 12px', borderRadius: 10, fontSize: 12, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.blue, cursor: 'pointer', whiteSpace: 'nowrap' }}>주소 검색</button>
                  </div>
                  <input value={editShippingDetail} onChange={e => setEditShippingDetail(e.target.value)} placeholder="상세주소" style={inputStyle} />
                </>
              )}
            </div>

            {/* 결제수단 */}
            <div style={{ fontSize: 11, color: C.textDim, fontWeight: 700, marginTop: 16, marginBottom: 10, letterSpacing: 1 }}>결제수단</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
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

            {/* 비밀번호 변경 */}
            <div style={{ fontSize: 11, color: C.textDim, fontWeight: 700, marginTop: 16, marginBottom: 10, letterSpacing: 1 }}>비밀번호 변경</div>
            <div style={{ fontSize: 11, color: C.textSec, marginBottom: 10 }}>변경하지 않으려면 비워두세요</div>

            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>현재 비밀번호</div>
              <input type="password" value={editCurPw} onChange={e => setEditCurPw(e.target.value)} style={inputStyle} />
            </div>

            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>새 비밀번호</div>
              <div style={{ position: 'relative' }}>
                <input
                  type={showEditNewPw ? 'text' : 'password'} value={editNewPw}
                  onChange={e => setEditNewPw(e.target.value)}
                  placeholder="8자 이상"
                  style={{ ...inputStyle, paddingRight: 36 }}
                />
                <button
                  onClick={() => setShowEditNewPw(!showEditNewPw)}
                  style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', fontSize: 16, cursor: 'pointer', color: C.textDim, background: 'none', border: 'none' }}
                >{showEditNewPw ? '🙈' : '👁'}</button>
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>새 비밀번호 확인</div>
              <input type="password" value={editNewPwConfirm} onChange={e => setEditNewPwConfirm(e.target.value)} style={inputStyle} />
            </div>

            {editError && (
              <div style={{ fontSize: 12, color: C.red, marginBottom: 14, padding: '8px 12px', borderRadius: 8, background: 'rgba(255,82,82,0.08)' }}>
                {editError}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setShowEditModal(false)}
                style={{
                  flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer',
                }}
              >취소</button>
              <button
                onClick={saveProfile}
                disabled={editSaving}
                style={{
                  flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  background: editSaving ? `${C.green}55` : `${C.green}22`, border: `1px solid ${C.green}66`,
                  color: C.green, cursor: editSaving ? 'not-allowed' : 'pointer',
                }}
              >{editSaving ? '저장 중...' : '저장'}</button>
            </div>
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════
          판매자 정보 수정 BottomSheet
         ════════════════════════════════════════════════════ */}
      {showSellerEdit && (
        <div
          onClick={() => setShowSellerEdit(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 2000, display: 'flex', alignItems: 'flex-end' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', maxHeight: '90dvh', background: C.bgCard,
              borderRadius: '20px 20px 0 0', padding: '20px 20px 40px', overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: C.text }}>판매자 정보 수정</span>
              <button onClick={() => setShowSellerEdit(false)} style={{ fontSize: 18, color: C.textDim, cursor: 'pointer', background: 'none', border: 'none' }}>&#x2715;</button>
            </div>

            <div style={{ fontSize: 11, color: C.textDim, fontWeight: 700, marginBottom: 10, letterSpacing: 1 }}>연락처</div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>전화번호</div>
              <input type="tel" value={sellerEditPhone} onChange={e => setSellerEditPhone(e.target.value)} style={inputStyle} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>회사 전화번호</div>
              <input type="tel" value={sellerEditCompanyPhone} onChange={e => setSellerEditCompanyPhone(e.target.value)} style={inputStyle} />
            </div>

            <div style={{ fontSize: 11, color: C.textDim, fontWeight: 700, marginTop: 16, marginBottom: 10, letterSpacing: 1 }}>주소</div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                <input readOnly value={sellerEditZipCode ? `[${sellerEditZipCode}] ${sellerEditAddress}` : sellerEditAddress} placeholder="주소 검색" style={{ ...inputStyle, flex: 1 }} />
                <button onClick={() => {
                  if (!window.daum?.Postcode) { showToast('주소 검색 서비스를 불러오는 중이에요.', 'info'); return; }
                  new window.daum.Postcode({
                    oncomplete: (data) => { setSellerEditAddress(data.address); setSellerEditZipCode(data.zonecode); },
                  }).open();
                }} style={{ padding: '10px 12px', borderRadius: 10, fontSize: 12, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.blue, cursor: 'pointer', whiteSpace: 'nowrap' }}>주소 검색</button>
              </div>
            </div>

            <div style={{ fontSize: 11, color: C.textDim, fontWeight: 700, marginTop: 16, marginBottom: 10, letterSpacing: 1 }}>정산 계좌</div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>은행명</div>
              <input value={sellerEditBankName} onChange={e => setSellerEditBankName(e.target.value)} style={inputStyle} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>계좌번호</div>
              <input value={sellerEditAccountNum} onChange={e => setSellerEditAccountNum(e.target.value)} style={inputStyle} />
            </div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>예금주</div>
              <input value={sellerEditAccountHolder} onChange={e => setSellerEditAccountHolder(e.target.value)} style={inputStyle} />
            </div>

            {sellerEditError && (
              <div style={{ fontSize: 12, color: C.red, marginBottom: 14, padding: '8px 12px', borderRadius: 8, background: 'rgba(255,82,82,0.08)' }}>
                {sellerEditError}
              </div>
            )}

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setShowSellerEdit(false)}
                style={{
                  flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer',
                }}
              >취소</button>
              <button
                onClick={saveSellerProfile}
                disabled={sellerEditSaving}
                style={{
                  flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  background: sellerEditSaving ? `${C.blue}55` : `${C.blue}22`, border: `1px solid ${C.blue}66`,
                  color: C.blue, cursor: sellerEditSaving ? 'not-allowed' : 'pointer',
                }}
              >{sellerEditSaving ? '저장 중...' : '저장'}</button>
            </div>
          </div>
        </div>
      )}

      {/* ════════════════════════════════════════════════════
          회원 탈퇴 BottomSheet
         ════════════════════════════════════════════════════ */}
      {showWithdraw && (
        <div
          onClick={() => setShowWithdraw(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 2000, display: 'flex', alignItems: 'flex-end' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', background: C.bgCard,
              borderRadius: '20px 20px 0 0', padding: '20px 20px 40px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: C.red }}>회원 탈퇴</span>
              <button onClick={() => setShowWithdraw(false)} style={{ fontSize: 18, color: C.textDim, cursor: 'pointer', background: 'none', border: 'none' }}>✕</button>
            </div>

            <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.8, marginBottom: 20, padding: '12px 14px', background: 'rgba(255,82,82,0.06)', borderRadius: 12, border: '1px solid rgba(255,82,82,0.2)' }}>
              탈퇴 시 모든 개인정보가 삭제되며 복구할 수 없습니다.<br />
              진행 중인 거래가 있으면 탈퇴할 수 없습니다.<br />
              적립된 포인트는 모두 소멸됩니다.
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>탈퇴 사유 *</div>
              <select
                value={withdrawReason}
                onChange={e => setWithdrawReason(e.target.value)}
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13,
                  background: '#1a1a2e', border: `1px solid ${C.border}`, color: '#ffffff',
                  boxSizing: 'border-box' as const,
                }}
              >
                <option value="" style={{ background: '#1a1a2e', color: '#ffffff' }}>사유를 선택해주세요</option>
                <option value="서비스를 잘 이용하지 않아요" style={{ background: '#1a1a2e', color: '#ffffff' }}>서비스를 잘 이용하지 않아요</option>
                <option value="원하는 딜이 없어요" style={{ background: '#1a1a2e', color: '#ffffff' }}>원하는 딜이 없어요</option>
                <option value="다른 서비스를 이용하고 있어요" style={{ background: '#1a1a2e', color: '#ffffff' }}>다른 서비스를 이용하고 있어요</option>
                <option value="개인정보가 걱정돼요" style={{ background: '#1a1a2e', color: '#ffffff' }}>개인정보가 걱정돼요</option>
                <option value="서비스 불만이 있어요" style={{ background: '#1a1a2e', color: '#ffffff' }}>서비스 불만이 있어요</option>
                <option value="기타" style={{ background: '#1a1a2e', color: '#ffffff' }}>기타</option>
              </select>
            </div>

            {withdrawReason === '기타' && (
              <div style={{ marginBottom: 14 }}>
                <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>상세 사유 *</div>
                <textarea
                  value={withdrawReasonText}
                  onChange={e => setWithdrawReasonText(e.target.value.slice(0, 200))}
                  placeholder="탈퇴 사유를 입력해주세요 (최대 200자)"
                  rows={3}
                  style={{
                    width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13,
                    background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
                    boxSizing: 'border-box' as const, resize: 'none',
                  }}
                />
                <div style={{ fontSize: 11, color: C.textDim, textAlign: 'right', marginTop: 4 }}>{withdrawReasonText.length}/200</div>
              </div>
            )}

            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 4 }}>비밀번호 확인 *</div>
              <input
                type="password" value={withdrawPw}
                onChange={e => setWithdrawPw(e.target.value)}
                placeholder="비밀번호를 입력해주세요"
                style={{
                  width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13,
                  background: C.bgEl, border: `1px solid ${C.border}`, color: C.text,
                  boxSizing: 'border-box' as const,
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setShowWithdraw(false)}
                style={{
                  flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer',
                }}
              >취소</button>
              <button
                onClick={handleWithdraw}
                disabled={withdrawing}
                style={{
                  flex: 1, padding: '12px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                  background: withdrawing ? 'rgba(255,82,82,0.3)' : 'rgba(255,82,82,0.15)',
                  border: '1px solid rgba(255,82,82,0.4)',
                  color: C.red, cursor: withdrawing ? 'not-allowed' : 'pointer',
                }}
              >{withdrawing ? '처리 중...' : '탈퇴하기'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
