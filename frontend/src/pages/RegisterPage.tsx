import { useState, useRef, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';
import apiClient, { loginApi } from '../api/client';
import { API } from '../api/endpoints';
import { FEATURES } from '../config';

// ── 디자인 토큰 ──────────────────────────────────────────
const C = {
  bgDeep:      '#0a0a0f',
  bgCard:      'rgba(255,255,255,0.04)',
  bgInput:     'rgba(255,255,255,0.06)',
  border:      'rgba(255,255,255,0.1)',
  borderFocus: 'rgba(0,230,118,0.5)',
  cyan:        '#00e5ff',
  green:       '#00e676',
  magenta:     '#e040fb',
  orange:      '#ff9800',
  yellow:      '#ffd740',
  text:        '#e8eaed',
  textSec:     '#78909c',
  textDim:     'rgba(255,255,255,0.25)',
};

// ── 방향 애니메이션 ──────────────────────────────────────
const variants = {
  enter:  (dir: number) => ({ x: dir > 0 ? '60%' : '-60%', opacity: 0 }),
  center: { x: 0, opacity: 1, transition: { type: 'spring' as const, damping: 28, stiffness: 300 } },
  exit:   (dir: number) => ({ x: dir > 0 ? '-60%' : '60%', opacity: 0, transition: { duration: 0.18 } }),
};

// ── 공용 컴포넌트 ────────────────────────────────────────
function InputField({
  label, value, onChange, placeholder, type = 'text', disabled,
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string; disabled?: boolean;
}) {
  const [focused, setFocused] = useState(false);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        style={{
          padding: '13px 14px', fontSize: 14, borderRadius: 12,
          background: C.bgInput,
          border: `1px solid ${focused ? C.borderFocus : C.border}`,
          color: C.text, transition: 'border-color 0.15s',
          opacity: disabled ? 0.5 : 1,
        }}
      />
    </div>
  );
}

function PrimaryBtn({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        width: '100%', padding: '15px', borderRadius: 14,
        background: disabled ? 'rgba(0,230,118,0.3)' : C.green,
        color: '#0a0a0f', fontSize: 15, fontWeight: 800,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'opacity 0.15s',
      }}
    >
      {label}
    </button>
  );
}

// ── Step 0: 전화번호 인증 ─────────────────────────────────
function PhoneStep({ onNext }: { onNext: () => void }) {
  const [phone, setPhone]       = useState('');
  const [otpSent, setOtpSent]   = useState(false);
  const [otp, setOtp]           = useState(['', '', '', '', '', '']);
  const [timer, setTimer]       = useState(0);
  const otpRefs    = useRef<(HTMLInputElement | null)[]>([]);
  const intervalRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  const sendOtp = () => {
    if (phone.replace(/\D/g, '').length < 10) return;
    setOtpSent(true);
    setTimer(180);
    clearInterval(intervalRef.current);
    intervalRef.current = setInterval(() => {
      setTimer(prev => {
        if (prev <= 1) { clearInterval(intervalRef.current); return 0; }
        return prev - 1;
      });
    }, 1000);
  };

  useEffect(() => () => clearInterval(intervalRef.current), []);

  const handleOtp = (idx: number, val: string) => {
    const next = [...otp];
    next[idx] = val.replace(/\D/g, '').slice(-1);
    setOtp(next);
    if (val && idx < 5) otpRefs.current[idx + 1]?.focus();
  };

  const handleOtpKey = (idx: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otp[idx] && idx > 0) {
      otpRefs.current[idx - 1]?.focus();
    }
  };

  const otpFilled = otp.every(d => d !== '');
  const fmtTimer  = `${String(Math.floor(timer / 60)).padStart(2, '0')}:${String(timer % 60).padStart(2, '0')}`;

  return (
    <div style={{ padding: '40px 24px' }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 6 }}>내 번호를 확인해요</div>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 32 }}>인증 후 역핑 서비스를 시작할 수 있어요.</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* 전화번호 입력 */}
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ flex: 1 }}>
            <InputField label="전화번호" value={phone} onChange={setPhone} placeholder="010-0000-0000" type="tel" />
          </div>
          <button
            onClick={sendOtp}
            disabled={phone.replace(/\D/g, '').length < 10}
            style={{
              alignSelf: 'flex-end', padding: '13px 16px',
              borderRadius: 12, fontSize: 13, fontWeight: 700,
              background: phone.replace(/\D/g, '').length >= 10 ? C.cyan : C.bgInput,
              color: phone.replace(/\D/g, '').length >= 10 ? '#000' : C.textDim,
              cursor: phone.replace(/\D/g, '').length >= 10 ? 'pointer' : 'not-allowed',
              border: `1px solid ${C.border}`, transition: 'all 0.15s', whiteSpace: 'nowrap',
            }}
          >
            {otpSent ? '재전송' : '인증번호 전송'}
          </button>
        </div>

        {/* OTP 박스 */}
        {otpSent && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 8 }}>
              인증번호 6자리
              {timer > 0 && <span style={{ color: C.orange, marginLeft: 8 }}>{fmtTimer}</span>}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {otp.map((d, i) => (
                <input
                  key={i}
                  ref={el => { otpRefs.current[i] = el; }}
                  value={d}
                  onChange={e => handleOtp(i, e.target.value)}
                  onKeyDown={e => handleOtpKey(i, e)}
                  maxLength={1}
                  inputMode="numeric"
                  style={{
                    flex: 1, height: 52, borderRadius: 12, textAlign: 'center',
                    fontSize: 22, fontWeight: 700, color: C.text,
                    background: C.bgInput,
                    border: `1px solid ${d ? C.green : C.border}`,
                    transition: 'border-color 0.15s',
                  }}
                />
              ))}
            </div>
          </motion.div>
        )}

        <PrimaryBtn
          label="확인하고 시작하기 →"
          onClick={onNext}
          disabled={otpSent ? !otpFilled : true}
        />
      </div>
    </div>
  );
}

// ── Step 1: 역할 선택 ─────────────────────────────────────
const ROLES = [
  { key: 'buyer',    icon: '🛍️', title: '구매자',    desc: '원하는 가격의 딜에 참여해요', color: C.cyan },
  { key: 'seller',   icon: '🏪', title: '판매자',    desc: '딜을 만들고 오퍼를 제출해요', color: C.green },
  { key: 'actuator', icon: '⚡', title: '액추에이터', desc: '딜 진행을 지원하는 전문가예요', color: C.yellow },
] as const;

function RoleStep({ role, onSelect, onNext }: {
  role: string;
  onSelect: (r: 'buyer' | 'seller' | 'actuator') => void;
  onNext: () => void;
}) {
  return (
    <div style={{ padding: '40px 24px' }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 6 }}>어떤 역할로 시작할까요?</div>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 28 }}>나중에 변경할 수 있어요.</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 28 }}>
        {ROLES.map(r => {
          const active = role === r.key;
          return (
            <button
              key={r.key}
              onClick={() => onSelect(r.key)}
              style={{
                display: 'flex', alignItems: 'center', gap: 16,
                padding: '18px 20px', borderRadius: 16, textAlign: 'left',
                background: active ? `${r.color}12` : C.bgCard,
                border: `1.5px solid ${active ? r.color : C.border}`,
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >
              <span style={{ fontSize: 28, flexShrink: 0 }}>{r.icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 15, fontWeight: 700, color: active ? r.color : C.text }}>{r.title}</div>
                <div style={{ fontSize: 12, color: C.textSec, marginTop: 2 }}>{r.desc}</div>
              </div>
              {active && <span style={{ color: r.color, fontSize: 18 }}>✓</span>}
            </button>
          );
        })}
      </div>

      <PrimaryBtn label="다음" onClick={onNext} disabled={!role} />
    </div>
  );
}

// ── Step 2: 프로필 ────────────────────────────────────────
function ProfileStep({ role, method, nickname, setNickname, nickStatus, recommender, setRecommender,
  email, setEmail, password, setPassword, apiError, onNext }: {
  role: string; method: string;
  nickname: string; setNickname: (v: string) => void;
  nickStatus: 'idle' | 'checking' | 'ok' | 'taken';
  recommender: string; setRecommender: (v: string) => void;
  email: string; setEmail: (v: string) => void;
  password: string; setPassword: (v: string) => void;
  apiError: string;
  onNext: () => void;
}) {
  const nickMsg   = { idle: '', checking: '확인 중...', ok: '사용 가능한 닉네임이에요 ✓', taken: '이미 사용 중인 닉네임이에요' }[nickStatus];
  const nickColor = { idle: C.textSec, checking: C.yellow, ok: C.green, taken: '#ff5252' }[nickStatus];
  const isEmail   = method === 'email';
  const canNext   = !!nickname && nickStatus === 'ok' && (!isEmail || (!!email && !!password));

  return (
    <div style={{ padding: '40px 24px' }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 6 }}>프로필을 만들어요</div>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 28 }}>딜에서 사용할 정보를 입력해요.</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 28 }}>
        {isEmail && (
          <>
            <InputField label="이메일" value={email} onChange={setEmail} placeholder="example@email.com" type="email" />
            <InputField label="비밀번호" value={password} onChange={setPassword} placeholder="8자 이상 입력" type="password" />
          </>
        )}
        <div>
          <InputField label="닉네임" value={nickname} onChange={setNickname} placeholder="역핑에서 쓸 이름" />
          {nickMsg && (
            <div style={{ fontSize: 11, color: nickColor, marginTop: 4, paddingLeft: 2 }}>{nickMsg}</div>
          )}
        </div>

        {role === 'buyer' && (
          <InputField
            label="추천인 코드 (선택)"
            value={recommender} onChange={setRecommender}
            placeholder="친구에게 받은 코드를 입력하세요"
          />
        )}

        {apiError && (
          <div style={{ fontSize: 12, color: '#ff5252', padding: '10px 14px', borderRadius: 10, background: 'rgba(255,82,82,0.08)', border: '1px solid rgba(255,82,82,0.25)' }}>
            {apiError}
          </div>
        )}
      </div>

      <PrimaryBtn label="다음" onClick={onNext} disabled={!canNext} />
    </div>
  );
}

// ── Step 3: 추가 정보 ─────────────────────────────────────
const REG_PAYMENT_OPTIONS = [
  { key: 'card',  label: '신용/체크카드', icon: '💳' },
  { key: 'bank',  label: '계좌이체',      icon: '🏦' },
  { key: 'kakao', label: '카카오페이',    icon: '💛' },
  { key: 'naver', label: '네이버페이',    icon: '💚' },
  { key: 'toss',  label: '토스페이',      icon: '💙' },
];

function ExtraInfoStep({ phone, setPhone, address, setAddress, shippingAddr, setShippingAddr,
  sameAsAddr, setSameAsAddr, gender, setGender, birthDate, setBirthDate,
  paymentMethod, setPaymentMethod, onNext }: {
  phone: string; setPhone: (v: string) => void;
  address: string; setAddress: (v: string) => void;
  shippingAddr: string; setShippingAddr: (v: string) => void;
  sameAsAddr: boolean; setSameAsAddr: (v: boolean) => void;
  gender: string; setGender: (v: string) => void;
  birthDate: string; setBirthDate: (v: string) => void;
  paymentMethod: string; setPaymentMethod: (v: string) => void;
  onNext: () => void;
}) {
  const canNext = !!phone.replace(/\D/g, '');

  return (
    <div style={{ padding: '40px 24px' }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 6 }}>추가 정보를 입력해요</div>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 28 }}>원활한 거래를 위해 정보를 입력해주세요. (전화번호만 필수)</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 28 }}>
        <InputField label="전화번호 *" value={phone} onChange={setPhone} placeholder="010-0000-0000" type="tel" />
        <InputField label="주소" value={address} onChange={setAddress} placeholder="서울시 강남구..." />

        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>배송지 주소</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: C.textSec, cursor: 'pointer' }}>
              <input type="checkbox" checked={sameAsAddr} onChange={e => { setSameAsAddr(e.target.checked); if (e.target.checked) setShippingAddr(address); }} />
              위와 동일
            </label>
          </div>
          <input
            type="text"
            value={sameAsAddr ? address : shippingAddr}
            onChange={e => setShippingAddr(e.target.value)}
            disabled={sameAsAddr}
            placeholder="배송받을 주소"
            style={{
              width: '100%', boxSizing: 'border-box', padding: '13px 14px', fontSize: 14, borderRadius: 12,
              background: C.bgInput, border: `1px solid ${C.border}`, color: C.text,
              opacity: sameAsAddr ? 0.5 : 1,
            }}
          />
        </div>

        {/* 성별 */}
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 8 }}>성별</div>
          <div style={{ display: 'flex', gap: 8 }}>
            {[{ key: 'male', label: '남성' }, { key: 'female', label: '여성' }, { key: 'other', label: '기타' }].map(g => {
              const active = gender === g.key;
              return (
                <button
                  key={g.key}
                  onClick={() => setGender(active ? '' : g.key)}
                  style={{
                    flex: 1, padding: '10px', borderRadius: 12, fontSize: 13, fontWeight: 600,
                    background: active ? `${C.green}20` : C.bgInput,
                    border: `1px solid ${active ? C.green : C.border}`,
                    color: active ? C.green : C.textSec,
                    cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >
                  {g.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* 생년월일 */}
        <div>
          <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec, display: 'block', marginBottom: 6 }}>생년월일</label>
          <input
            type="date"
            value={birthDate}
            onChange={e => setBirthDate(e.target.value)}
            style={{
              width: '100%', boxSizing: 'border-box', padding: '13px 14px', fontSize: 14, borderRadius: 12,
              background: C.bgInput, border: `1px solid ${C.border}`, color: C.text,
            }}
          />
        </div>

        {/* 결제수단 */}
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 8 }}>선호 결제수단</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {REG_PAYMENT_OPTIONS.map(opt => {
              const active = paymentMethod === opt.key;
              return (
                <button
                  key={opt.key}
                  onClick={() => setPaymentMethod(active ? '' : opt.key)}
                  style={{
                    padding: '8px 14px', borderRadius: 12, fontSize: 12, fontWeight: 600,
                    background: active ? `${C.green}20` : C.bgInput,
                    border: `1px solid ${active ? C.green : C.border}`,
                    color: active ? C.green : C.textSec,
                    cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >
                  {opt.icon} {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      <PrimaryBtn label="다음" onClick={onNext} disabled={!canNext} />
    </div>
  );
}

// ── Step 4: 약관 동의 ─────────────────────────────────────
function TermsStep({ termsAgreed, setTermsAgreed, privacyAgreed, setPrivacyAgreed,
  marketingAgreed, setMarketingAgreed, onNext }: {
  termsAgreed: boolean; setTermsAgreed: (v: boolean) => void;
  privacyAgreed: boolean; setPrivacyAgreed: (v: boolean) => void;
  marketingAgreed: boolean; setMarketingAgreed: (v: boolean) => void;
  onNext: () => void;
}) {
  const allChecked = termsAgreed && privacyAgreed && marketingAgreed;
  const toggleAll = () => {
    const next = !allChecked;
    setTermsAgreed(next); setPrivacyAgreed(next); setMarketingAgreed(next);
  };
  const canNext = termsAgreed && privacyAgreed;

  const CheckRow = ({ checked, onChange, label, required, linkLabel }: {
    checked: boolean; onChange: (v: boolean) => void; label: string; required?: boolean; linkLabel?: string;
  }) => (
    <label style={{
      display: 'flex', alignItems: 'center', gap: 12, padding: '14px 16px',
      background: checked ? `${C.green}08` : 'transparent',
      borderRadius: 12, cursor: 'pointer', transition: 'background 0.15s',
    }}>
      <div style={{
        width: 22, height: 22, borderRadius: 6, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: checked ? C.green : 'transparent',
        border: `2px solid ${checked ? C.green : C.border}`,
        color: '#0a0a0f', fontSize: 14, fontWeight: 900,
        transition: 'all 0.15s',
      }}>
        {checked && '✓'}
      </div>
      <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} style={{ display: 'none' }} />
      <div style={{ flex: 1 }}>
        <span style={{ fontSize: 13, color: C.text, fontWeight: 500 }}>
          {label}
          {required && <span style={{ color: '#ff5252', marginLeft: 4 }}>(필수)</span>}
          {!required && <span style={{ color: C.textSec, marginLeft: 4 }}>(선택)</span>}
        </span>
      </div>
      {linkLabel && (
        <button
          onClick={e => { e.preventDefault(); e.stopPropagation(); }}
          style={{ fontSize: 11, color: C.cyan, cursor: 'pointer', whiteSpace: 'nowrap' }}
        >{linkLabel}</button>
      )}
    </label>
  );

  return (
    <div style={{ padding: '40px 24px' }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 6 }}>약관에 동의해주세요</div>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 28 }}>서비스 이용을 위해 약관 동의가 필요해요.</div>

      {/* 전체 동의 */}
      <label style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '16px',
        background: allChecked ? `${C.green}12` : C.bgCard,
        border: `1.5px solid ${allChecked ? C.green : C.border}`,
        borderRadius: 14, cursor: 'pointer', marginBottom: 12,
      }}>
        <div style={{
          width: 24, height: 24, borderRadius: 7, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: allChecked ? C.green : 'transparent',
          border: `2px solid ${allChecked ? C.green : C.border}`,
          color: '#0a0a0f', fontSize: 15, fontWeight: 900,
        }}>
          {allChecked && '✓'}
        </div>
        <input type="checkbox" checked={allChecked} onChange={toggleAll} style={{ display: 'none' }} />
        <span style={{ fontSize: 15, fontWeight: 700, color: allChecked ? C.green : C.text }}>전체 동의</span>
      </label>

      <div style={{
        background: C.bgCard, border: `1px solid ${C.border}`,
        borderRadius: 14, overflow: 'hidden', marginBottom: 28,
      }}>
        <CheckRow checked={termsAgreed} onChange={setTermsAgreed} label="이용약관 동의" required linkLabel="보기" />
        <div style={{ height: 1, background: C.border, margin: '0 16px' }} />
        <CheckRow checked={privacyAgreed} onChange={setPrivacyAgreed} label="개인정보처리방침 동의" required linkLabel="보기" />
        <div style={{ height: 1, background: C.border, margin: '0 16px' }} />
        <CheckRow checked={marketingAgreed} onChange={setMarketingAgreed} label="마케팅 수신 동의" linkLabel="보기" />
      </div>

      <PrimaryBtn label="다음" onClick={onNext} disabled={!canNext} />
    </div>
  );
}

// ── Step 5: 사업자 정보 ───────────────────────────────────
function BizStep({ role, onNext }: { role: string; onNext: () => void }) {
  // 셀러용
  const [bizName,    setBizName]    = useState('');
  const [bizNum,     setBizNum]     = useState('');
  const [bizVerify,  setBizVerify]  = useState<'idle' | 'checking' | 'ok'>('idle');
  const [ceoName,    setCeoName]    = useState('');
  const [bankName,   setBankName]   = useState('');
  const [accountNum, setAccountNum] = useState('');
  // 액추에이터용
  const [manager, setManager] = useState('');
  const [contact,  setContact]  = useState('');
  const [region,   setRegion]   = useState('');
  const [skills,   setSkills]   = useState<string[]>([]);

  const SKILL_OPTIONS = ['물류', '검수', '통관', 'QC', '계약', '컨설팅'];

  const doVerifyBiz = () => {
    if (!bizNum || bizVerify === 'ok') return;
    setBizVerify('checking');
    setTimeout(() => setBizVerify('ok'), 1200);
  };

  const isSeller = role === 'seller';
  const canNext  = isSeller
    ? !!bizName && !!ceoName && bizVerify === 'ok' && !!bankName && !!accountNum
    : !!manager && !!contact;

  return (
    <div style={{ padding: '40px 24px', paddingBottom: 60 }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 6 }}>
        {isSeller ? '판매자 정보를 입력해요' : '액추에이터 정보를 입력해요'}
      </div>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 28 }}>
        {isSeller ? '정산을 위한 사업자 정보가 필요해요.' : '활동 정보를 알려주세요.'}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 28 }}>
        {isSeller ? (
          <>
            <InputField label="사업자명" value={bizName} onChange={setBizName} placeholder="상호명 입력" />

            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec, display: 'block', marginBottom: 6 }}>사업자번호</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  value={bizNum}
                  onChange={e => { setBizNum(e.target.value); setBizVerify('idle'); }}
                  placeholder="000-00-00000"
                  style={{
                    flex: 1, padding: '13px 14px', fontSize: 14, borderRadius: 12,
                    background: C.bgInput, border: `1px solid ${C.border}`, color: C.text,
                  }}
                />
                <button
                  onClick={doVerifyBiz}
                  disabled={!bizNum || bizVerify === 'ok'}
                  style={{
                    padding: '13px 14px', borderRadius: 12, fontSize: 13, fontWeight: 700,
                    background: bizVerify === 'ok' ? `${C.green}20` : C.bgInput,
                    border: `1px solid ${bizVerify === 'ok' ? C.green : C.border}`,
                    color: bizVerify === 'ok' ? C.green : C.textSec,
                    cursor: (!bizNum || bizVerify === 'ok') ? 'not-allowed' : 'pointer',
                    whiteSpace: 'nowrap', transition: 'all 0.15s',
                  }}
                >
                  {bizVerify === 'checking' ? '확인 중...' : bizVerify === 'ok' ? '인증 완료 ✓' : '인증하기'}
                </button>
              </div>
            </div>

            <InputField label="대표자 이름" value={ceoName} onChange={setCeoName} placeholder="대표자 성함" />

            <div style={{ padding: '16px', background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 12 }}>정산 계좌</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <InputField label="은행명" value={bankName} onChange={setBankName} placeholder="예: 국민은행" />
                <InputField label="계좌번호" value={accountNum} onChange={setAccountNum} placeholder="- 없이 숫자만" type="tel" />
              </div>
            </div>
          </>
        ) : (
          <>
            <InputField label="담당자 이름" value={manager} onChange={setManager} placeholder="담당자 성함" />
            <InputField label="연락처" value={contact} onChange={setContact} placeholder="010-0000-0000" type="tel" />
            <InputField label="주요 운영 지역" value={region} onChange={setRegion} placeholder="예: 서울·경기" />
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 8 }}>역량 태그 (선택)</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {SKILL_OPTIONS.map(s => {
                  const active = skills.includes(s);
                  return (
                    <button
                      key={s}
                      onClick={() => setSkills(prev => active ? prev.filter(x => x !== s) : [...prev, s])}
                      style={{
                        padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600,
                        background: active ? `${C.yellow}20` : C.bgInput,
                        border: `1px solid ${active ? C.yellow : C.border}`,
                        color: active ? C.yellow : C.textSec,
                        cursor: 'pointer', transition: 'all 0.15s',
                      }}
                    >
                      {s}
                    </button>
                  );
                })}
              </div>
            </div>
          </>
        )}
      </div>

      <PrimaryBtn label="다음" onClick={onNext} disabled={!canNext} />
    </div>
  );
}

// ── Step 6: 완료 ──────────────────────────────────────────
const METHOD_LABELS: Record<string, string> = {
  kakao: '카카오', naver: '네이버', google: 'Google', phone: '전화번호',
};
const ROLE_LABELS: Record<string, string> = {
  buyer: '구매자', seller: '판매자', actuator: '액추에이터',
};

function CompleteStep({ method, role, nickname, onFinish, navigate }: {
  method: string; role: string; nickname: string; onFinish: () => void;
  navigate: (path: string) => void;
}) {
  return (
    <div style={{
      minHeight: '100dvh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', padding: '24px',
    }}>
      <style>{`
        @keyframes checkPop {
          0%   { transform: scale(0); opacity: 0; }
          60%  { transform: scale(1.2); }
          100% { transform: scale(1); opacity: 1; }
        }
      `}</style>

      <div style={{
        width: 80, height: 80, borderRadius: '50%',
        background: `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 36, color: '#0a0a0f', fontWeight: 900,
        marginBottom: 24,
        animation: 'checkPop 0.5s cubic-bezier(0.175,0.885,0.32,1.275) both',
      }}>
        ✓
      </div>

      <div style={{ fontSize: 24, fontWeight: 900, color: C.text, marginBottom: 6, textAlign: 'center' }}>가입 완료!</div>
      <div style={{ fontSize: 14, color: C.textSec, marginBottom: 36, textAlign: 'center' }}>역핑에 오신 걸 환영해요 🎉</div>

      <div style={{
        width: '100%', maxWidth: 320,
        background: C.bgCard, border: `1px solid ${C.border}`,
        borderRadius: 18, padding: '20px 22px', marginBottom: 32,
      }}>
        {[
          { label: '가입 방법', value: METHOD_LABELS[method] ?? method },
          { label: '역할',     value: ROLE_LABELS[role] ?? role },
          { label: '닉네임',   value: nickname || '미설정' },
        ].map(({ label, value }, idx, arr) => (
          <div key={label} style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '10px 0',
            borderBottom: idx < arr.length - 1 ? `1px solid ${C.border}` : 'none',
          }}>
            <span style={{ fontSize: 13, color: C.textSec }}>{label}</span>
            <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{value}</span>
          </div>
        ))}
      </div>

      {/* 결제수단 안내 */}
      <div style={{
        width: '100%', maxWidth: 320,
        background: 'rgba(255,152,0,0.06)',
        border: '1px solid rgba(255,152,0,0.25)',
        borderRadius: 16, padding: '18px 20px', marginBottom: 20,
      }}>
        <div style={{ fontSize: 15, fontWeight: 800, color: C.orange, marginBottom: 8 }}>💳 결제수단을 미리 등록하세요!</div>
        <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.7, marginBottom: 14 }}>
          역핑에서는 오퍼 확정 후 결제 시간이 단 <strong style={{ color: C.orange }}>5분</strong>입니다.<br />
          원활한 거래를 위해 결제수단을 먼저 등록해주세요.
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={() => navigate('/mypage')}
            style={{
              flex: 1, padding: '11px', borderRadius: 10, fontSize: 13, fontWeight: 700,
              background: `${C.orange}18`, border: `1px solid ${C.orange}44`, color: C.orange, cursor: 'pointer',
            }}
          >지금 등록하기</button>
          <button
            onClick={onFinish}
            style={{
              flex: 1, padding: '11px', borderRadius: 10, fontSize: 13, fontWeight: 600,
              background: 'rgba(255,255,255,0.06)', border: `1px solid rgba(255,255,255,0.1)`, color: C.textSec, cursor: 'pointer',
            }}
          >나중에 할게요</button>
        </div>
      </div>

      <button
        onClick={onFinish}
        style={{
          width: '100%', maxWidth: 320, padding: '15px',
          borderRadius: 14, fontSize: 15, fontWeight: 800,
          background: `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
          color: '#0a0a0f', cursor: 'pointer',
        }}
      >
        역핑 시작하기 →
      </button>
    </div>
  );
}

// ── 메인 컴포넌트 ────────────────────────────────────────
export default function RegisterPage() {
  const navigate       = useNavigate();
  const [searchParams] = useSearchParams();
  const method         = searchParams.get('method') ?? 'kakao';
  const { login }      = useAuth();

  const [step, setStep] = useState(method === 'phone' ? 0 : 1);
  const [dir,  setDir]  = useState(1);

  // step 1
  const [role, setRole] = useState<'buyer' | 'seller' | 'actuator' | ''>('');

  // step 2 — email auth fields
  const [email,       setEmail]       = useState('');
  const [password,    setPassword]    = useState('');
  const [apiError,    setApiError]    = useState('');
  const [registering, setRegistering] = useState(false);

  // step 2 — profile fields
  const [nickname,    setNicknameRaw] = useState('');
  const [nickStatus,  setNickStatus]  = useState<'idle' | 'checking' | 'ok' | 'taken'>('idle');
  const [recommender, setRecommender] = useState('');

  // step 3 — extra info
  const [phone,        setPhone]        = useState('');
  const [address,      setAddress]      = useState('');
  const [shippingAddr, setShippingAddr] = useState('');
  const [sameAsAddr,   setSameAsAddr]   = useState(false);
  const [gender,         setGender]         = useState('');
  const [birthDate,      setBirthDate]      = useState('');
  const [paymentMethod,  setPaymentMethod]  = useState('');

  // step 4 — terms
  const [termsAgreed,     setTermsAgreed]     = useState(false);
  const [privacyAgreed,   setPrivacyAgreed]   = useState(false);
  const [marketingAgreed, setMarketingAgreed] = useState(false);
  const nickTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const setNickname = (val: string) => {
    setNicknameRaw(val);
    setNickStatus('idle');
    clearTimeout(nickTimer.current);
    if (!val) return;
    setNickStatus('checking');
    nickTimer.current = setTimeout(() => {
      setNickStatus(val === '역핑왕' ? 'taken' : 'ok');
    }, 600);
  };

  useEffect(() => () => clearTimeout(nickTimer.current), []);

  const goTo = (n: number) => { setDir(n > step ? 1 : -1); setStep(n); };

  const TOTAL_STEPS = 5; // 1~5 visible steps (role, profile, extra, terms, biz/complete)

  const goNext = async () => {
    if (step === 0) { goTo(1); return; }
    if (step === 1) { goTo(2); return; }
    if (step === 2) { goTo(3); return; }
    if (step === 3) { goTo(4); return; }
    if (step === 4) {
      // 약관 동의 후 → API 가입 실행
      if (FEATURES.USE_API_AUTH && method === 'email') {
        setRegistering(true);
        setApiError('');
        try {
          await apiClient.post(API.BUYERS.LIST, {
            email: email.trim(), password,
            name: nickname, nickname,
            phone: phone || undefined,
            address: address || undefined,
            gender: gender || undefined,
            birth_date: birthDate || undefined,
            payment_method: paymentMethod || undefined,
          });
          const loginRes = await loginApi(email.trim(), password);
          const { access_token } = loginRes.data as { access_token: string };
          apiClient.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
          login(access_token, {
            id: 0, email: email.trim(),
            name: nickname, nickname,
            role: 'buyer', level: 1, points: 0,
          });
          goTo(role === 'buyer' ? 6 : 5);
        } catch (err: unknown) {
          const e = err as { response?: { data?: { detail?: unknown } } };
          const detail = e.response?.data?.detail;
          setApiError(typeof detail === 'string' ? detail : '가입에 실패했어요. 이미 사용된 이메일일 수 있어요.');
        } finally {
          setRegistering(false);
        }
        return;
      }
      goTo(role === 'buyer' ? 6 : 5);
      return;
    }
    if (step === 5) goTo(6);
  };

  const goBack = () => {
    if (step === 0 || step === 1) navigate('/login');
    else if (step === 2) goTo(1);
    else if (step === 3) goTo(2);
    else if (step === 4) goTo(3);
    else if (step === 5) goTo(4);
  };

  const visibleStep = step >= 1 && step <= TOTAL_STEPS ? step : null;
  const stepLabel = visibleStep ? `${visibleStep}/${TOTAL_STEPS}` : null;

  return (
    <div style={{ minHeight: '100dvh', background: C.bgDeep, overflow: 'hidden' }}>
      {/* TopBar */}
      {step < 6 && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, height: 56,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 20px', zIndex: 10,
          background: 'rgba(10,10,15,0.85)', backdropFilter: 'blur(10px)',
          borderBottom: `1px solid ${C.border}`,
        }}>
          <button onClick={goBack} style={{ fontSize: 14, color: C.textSec, cursor: 'pointer', padding: '6px 2px' }}>
            ← 뒤로
          </button>
          {stepLabel && (
            <div style={{ fontSize: 13, fontWeight: 700 }}>
              <span style={{ color: C.green }}>{visibleStep}</span>
              <span style={{ color: C.textSec }}>/{TOTAL_STEPS}</span>
            </div>
          )}
          <div style={{ width: 48 }} />
        </div>
      )}

      {/* 진행 바 */}
      {step >= 1 && step <= TOTAL_STEPS && (
        <div style={{ position: 'fixed', top: 56, left: 0, right: 0, height: 3, zIndex: 10, background: C.border }}>
          <div style={{
            height: '100%', width: `${(step / TOTAL_STEPS) * 100}%`,
            background: `linear-gradient(90deg, ${C.green}, ${C.cyan})`,
            transition: 'width 0.3s ease',
          }} />
        </div>
      )}

      {/* 콘텐츠 */}
      <div style={{ paddingTop: step < 6 ? 60 : 0, minHeight: '100dvh' }}>
        <AnimatePresence mode="wait" custom={dir}>
          <motion.div
            key={step}
            custom={dir}
            variants={variants}
            initial="enter"
            animate="center"
            exit="exit"
            style={{ width: '100%', maxWidth: 480, margin: '0 auto' }}
          >
            {step === 0 && <PhoneStep onNext={() => { void goNext(); }} />}
            {step === 1 && (
              <RoleStep
                role={role}
                onSelect={r => setRole(r)}
                onNext={() => { void goNext(); }}
              />
            )}
            {step === 2 && (
              <ProfileStep
                role={role}
                method={method}
                nickname={nickname}
                setNickname={setNickname}
                nickStatus={nickStatus}
                recommender={recommender}
                setRecommender={setRecommender}
                email={email}
                setEmail={setEmail}
                password={password}
                setPassword={setPassword}
                apiError={apiError}
                onNext={() => { void goNext(); }}
              />
            )}
            {step === 3 && (
              <ExtraInfoStep
                phone={phone} setPhone={setPhone}
                address={address} setAddress={setAddress}
                shippingAddr={shippingAddr} setShippingAddr={setShippingAddr}
                sameAsAddr={sameAsAddr} setSameAsAddr={setSameAsAddr}
                gender={gender} setGender={setGender}
                birthDate={birthDate} setBirthDate={setBirthDate}
                paymentMethod={paymentMethod} setPaymentMethod={setPaymentMethod}
                onNext={() => { void goNext(); }}
              />
            )}
            {step === 4 && (
              <div>
                <TermsStep
                  termsAgreed={termsAgreed} setTermsAgreed={setTermsAgreed}
                  privacyAgreed={privacyAgreed} setPrivacyAgreed={setPrivacyAgreed}
                  marketingAgreed={marketingAgreed} setMarketingAgreed={setMarketingAgreed}
                  onNext={() => { void goNext(); }}
                />
                {apiError && (
                  <div style={{ padding: '0 24px 20px', marginTop: -16 }}>
                    <div style={{ fontSize: 12, color: '#ff5252', padding: '10px 14px', borderRadius: 10, background: 'rgba(255,82,82,0.08)', border: '1px solid rgba(255,82,82,0.25)' }}>
                      {apiError}
                    </div>
                  </div>
                )}
                {registering && (
                  <div style={{ textAlign: 'center', padding: '0 24px 20px', fontSize: 13, color: C.textSec }}>가입 처리 중...</div>
                )}
              </div>
            )}
            {step === 5 && <BizStep role={role} onNext={() => { void goNext(); }} />}
            {step === 6 && (
              <CompleteStep
                method={method}
                role={role}
                nickname={nickname}
                onFinish={() => navigate('/')}
                navigate={navigate}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
