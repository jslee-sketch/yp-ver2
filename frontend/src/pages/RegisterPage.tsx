import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../contexts/AuthContext';
import apiClient, { loginApi } from '../api/client';
import { API } from '../api/endpoints';
import { FEATURES } from '../config';
import { showToast } from '../components/common/Toast';

// ── Daum Postcode 타입 ───────────────────────────────────────
declare global {
  interface Window {
    daum?: {
      Postcode: new (options: {
        oncomplete: (data: { zonecode: string; address: string }) => void;
      }) => { open: () => void };
    };
  }
}

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
  red:         '#ff5252',
};

// ── 상수 ──────────────────────────────────────────────────
const BANNED_NICKNAMES = new Set([
  '관리자', 'admin', '운영자', '역핑', 'yeokping',
  'test', '테스트', 'system', '시스템',
]);

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PW_RE = /^(?=.*[a-zA-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]).{8,}$/;
const NICK_RE = /^[가-힣a-zA-Z0-9_]{2,20}$/;

// ── 방향 애니메이션 ──────────────────────────────────────
const variants = {
  enter:  (dir: number) => ({ x: dir > 0 ? '60%' : '-60%', opacity: 0 }),
  center: { x: 0, opacity: 1, transition: { type: 'spring' as const, damping: 28, stiffness: 300 } },
  exit:   (dir: number) => ({ x: dir > 0 ? '-60%' : '60%', opacity: 0, transition: { duration: 0.18 } }),
};

// ── 공용 InputField ──────────────────────────────────────
function InputField({
  label, value, onChange, placeholder, type = 'text', disabled, hint, error, suffix,
}: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string; disabled?: boolean;
  hint?: string; error?: string; suffix?: React.ReactNode;
}) {
  const [focused, setFocused] = useState(false);
  const borderColor = error ? C.red : focused ? C.borderFocus : C.border;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>{label}</label>
      <div style={{ position: 'relative' }}>
        <input
          type={type}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={placeholder}
          disabled={disabled}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={{
            width: '100%', boxSizing: 'border-box',
            padding: suffix ? '13px 40px 13px 14px' : '13px 14px', fontSize: 14, borderRadius: 12,
            background: C.bgInput,
            border: `1px solid ${borderColor}`,
            color: C.text, transition: 'border-color 0.15s',
            opacity: disabled ? 0.5 : 1,
          }}
        />
        {suffix && (
          <div style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)' }}>
            {suffix}
          </div>
        )}
      </div>
      {hint && !error && <div style={{ fontSize: 11, color: C.textSec, paddingLeft: 2 }}>{hint}</div>}
      {error && <div style={{ fontSize: 11, color: C.red, paddingLeft: 2 }}>{error}</div>}
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
function ProfileStep({
  nickname, setNickname, nickStatus, nickMsg,
  recommender, setRecommender, role,
  email, setEmail, emailStatus, emailMsg,
  password, setPassword, passwordConfirm, setPasswordConfirm,
  showPw, setShowPw, showPwConfirm, setShowPwConfirm,
  pwError, pwConfirmError,
  apiError, onNext,
}: {
  nickname: string; setNickname: (v: string) => void;
  nickStatus: 'idle' | 'checking' | 'ok' | 'taken' | 'banned' | 'invalid';
  nickMsg: string;
  recommender: string; setRecommender: (v: string) => void; role: string;
  email: string; setEmail: (v: string) => void;
  emailStatus: 'idle' | 'checking' | 'ok' | 'taken' | 'invalid';
  emailMsg: string;
  password: string; setPassword: (v: string) => void;
  passwordConfirm: string; setPasswordConfirm: (v: string) => void;
  showPw: boolean; setShowPw: (v: boolean) => void;
  showPwConfirm: boolean; setShowPwConfirm: (v: boolean) => void;
  pwError: string; pwConfirmError: string;
  apiError: string;
  onNext: () => void;
}) {
  const nickColor = { idle: C.textSec, checking: C.yellow, ok: C.green, taken: C.red, banned: C.red, invalid: C.red }[nickStatus];
  const emailColor = { idle: C.textSec, checking: C.yellow, ok: C.green, taken: C.red, invalid: C.red }[emailStatus];

  const canNext = !!nickname && nickStatus === 'ok'
    && !!email && emailStatus === 'ok'
    && !!password && !pwError
    && !!passwordConfirm && !pwConfirmError;

  const EyeBtn = ({ show, toggle }: { show: boolean; toggle: () => void }) => (
    <button
      type="button" onClick={toggle}
      style={{ fontSize: 16, cursor: 'pointer', color: C.textDim, background: 'none', border: 'none', padding: 0 }}
    >{show ? '🙈' : '👁'}</button>
  );

  return (
    <div style={{ padding: '40px 24px' }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 6 }}>프로필을 만들어요</div>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 28 }}>딜에서 사용할 정보를 입력해요.</div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 28 }}>
        {/* 이메일 */}
        <div>
          <InputField
            label="이메일" value={email} onChange={setEmail}
            placeholder="example@email.com" type="email"
            hint="실제 사용하는 이메일을 입력해주세요"
            error={emailMsg && emailStatus !== 'ok' && emailStatus !== 'idle' && emailStatus !== 'checking' ? emailMsg : undefined}
          />
          {emailMsg && (emailStatus === 'ok' || emailStatus === 'checking') && (
            <div style={{ fontSize: 11, color: emailColor, marginTop: 4, paddingLeft: 2 }}>{emailMsg}</div>
          )}
        </div>

        {/* 비밀번호 */}
        <InputField
          label="비밀번호" value={password} onChange={setPassword}
          placeholder="8자 이상, 영문+숫자+특수문자"
          type={showPw ? 'text' : 'password'}
          hint={!pwError ? '비밀번호는 8자 이상, 영문+숫자+특수문자를 포함해야 해요' : undefined}
          error={pwError}
          suffix={<EyeBtn show={showPw} toggle={() => setShowPw(!showPw)} />}
        />

        {/* 비밀번호 확인 */}
        <InputField
          label="비밀번호 확인" value={passwordConfirm} onChange={setPasswordConfirm}
          placeholder="비밀번호를 한 번 더 입력해주세요"
          type={showPwConfirm ? 'text' : 'password'}
          error={pwConfirmError}
          suffix={<EyeBtn show={showPwConfirm} toggle={() => setShowPwConfirm(!showPwConfirm)} />}
        />

        {/* 닉네임 */}
        <div>
          <InputField
            label="닉네임" value={nickname} onChange={setNickname}
            placeholder="역핑에서 쓸 이름"
            hint="2~20글자, 특수문자 제외"
            error={nickMsg && nickStatus !== 'ok' && nickStatus !== 'idle' && nickStatus !== 'checking' ? nickMsg : undefined}
          />
          {nickMsg && (nickStatus === 'ok' || nickStatus === 'checking') && (
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
          <div style={{ fontSize: 12, color: C.red, padding: '10px 14px', borderRadius: 10, background: 'rgba(255,82,82,0.08)', border: '1px solid rgba(255,82,82,0.25)' }}>
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

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function isUnder14(year: number, month: number, day: number): boolean {
  const today = new Date();
  const birth = new Date(year, month - 1, day);
  const age14 = new Date(birth);
  age14.setFullYear(age14.getFullYear() + 14);
  return today < age14;
}

function ExtraInfoStep({
  phone, setPhone, phoneStatus, phoneMsg,
  companyPhone, setCompanyPhone,
  address, setAddress, zipCode, setZipCode, addressDetail, setAddressDetail,
  shippingAddr, setShippingAddr, shippingZip, setShippingZip, shippingDetail, setShippingDetail,
  sameAsAddr, setSameAsAddr,
  gender, setGender,
  birthYear, setBirthYear, birthMonth, setBirthMonth, birthDay, setBirthDay, birthError,
  paymentMethod, setPaymentMethod,
  role, onNext,
}: {
  phone: string; setPhone: (v: string) => void;
  phoneStatus: 'idle' | 'checking' | 'ok' | 'taken' | 'invalid';
  phoneMsg: string;
  companyPhone: string; setCompanyPhone: (v: string) => void;
  address: string; setAddress: (v: string) => void;
  zipCode: string; setZipCode: (v: string) => void;
  addressDetail: string; setAddressDetail: (v: string) => void;
  shippingAddr: string; setShippingAddr: (v: string) => void;
  shippingZip: string; setShippingZip: (v: string) => void;
  shippingDetail: string; setShippingDetail: (v: string) => void;
  sameAsAddr: boolean; setSameAsAddr: (v: boolean) => void;
  gender: string; setGender: (v: string) => void;
  birthYear: string; setBirthYear: (v: string) => void;
  birthMonth: string; setBirthMonth: (v: string) => void;
  birthDay: string; setBirthDay: (v: string) => void;
  birthError: string;
  paymentMethod: string; setPaymentMethod: (v: string) => void;
  role: string; onNext: () => void;
}) {
  const isSeller = role === 'seller';
  const isActuator = role === 'actuator';
  const hideConsumerFields = isSeller || isActuator;
  const phoneColor = { idle: C.textSec, checking: C.yellow, ok: C.green, taken: C.red, invalid: C.red }[phoneStatus];

  const openDaumPost = (target: 'main' | 'shipping') => {
    if (!window.daum?.Postcode) {
      showToast('주소 검색 서비스를 불러오는 중이에요. 잠시 후 다시 시도해주세요.', 'info');
      return;
    }
    new window.daum.Postcode({
      oncomplete: (data) => {
        if (target === 'main') {
          setAddress(data.address);
          setZipCode(data.zonecode);
        } else {
          setShippingAddr(data.address);
          setShippingZip(data.zonecode);
        }
      },
    }).open();
  };

  const phoneDigits = phone.replace(/\D/g, '');
  const canNext = phoneDigits.length === 11 && phoneDigits.startsWith('010') && phoneStatus !== 'taken';

  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: currentYear - 1920 + 1 }, (_, i) => currentYear - i);
  const months = Array.from({ length: 12 }, (_, i) => i + 1);
  const maxDay = birthYear && birthMonth ? daysInMonth(Number(birthYear), Number(birthMonth)) : 31;
  const days = Array.from({ length: maxDay }, (_, i) => i + 1);

  const selectStyle: React.CSSProperties = {
    flex: 1, padding: '10px 8px', borderRadius: 12, fontSize: 13,
    background: '#1a1a2e', border: `1px solid ${C.border}`, color: '#ffffff',
  };

  // 회사전화 포맷 (010 강제 아님, 일반전화 허용)
  const formatGeneralPhone = (raw: string): string => {
    const digits = raw.replace(/\D/g, '').slice(0, 12);
    if (digits.length <= 3) return digits;
    if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
    if (digits.startsWith('02')) {
      if (digits.length <= 6) return `${digits.slice(0, 2)}-${digits.slice(2)}`;
      if (digits.length <= 10) return `${digits.slice(0, 2)}-${digits.slice(2, 6)}-${digits.slice(6)}`;
      return `${digits.slice(0, 2)}-${digits.slice(2, 6)}-${digits.slice(6, 10)}`;
    }
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
  };

  return (
    <div style={{ padding: '40px 24px' }}>
      <div style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 6 }}>추가 정보를 입력해요</div>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 28 }}>
        {hideConsumerFields ? '활동을 위한 연락처와 주소를 입력해주세요.' : '원활한 거래를 위해 정보를 입력해주세요. (전화번호만 필수)'}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 28 }}>
        {/* 전화번호 (핸드폰) */}
        <div>
          <InputField
            label="전화번호 (핸드폰) *" value={phone} onChange={setPhone}
            placeholder="010-0000-0000" type="tel"
            error={phoneMsg && phoneStatus !== 'ok' && phoneStatus !== 'idle' && phoneStatus !== 'checking' ? phoneMsg : undefined}
          />
          {phoneMsg && (phoneStatus === 'ok' || phoneStatus === 'checking') && (
            <div style={{ fontSize: 11, color: phoneColor, marginTop: 4, paddingLeft: 2 }}>{phoneMsg}</div>
          )}
        </div>

        {/* 판매자: 회사 전화번호 */}
        {isSeller && (
          <InputField
            label="회사 전화번호"
            value={companyPhone}
            onChange={v => setCompanyPhone(formatGeneralPhone(v))}
            placeholder="02-0000-0000 또는 070-0000-0000"
            type="tel"
          />
        )}

        {/* 주소 (Daum Postcode) */}
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 6 }}>주소</div>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
            <input
              readOnly value={zipCode ? `[${zipCode}] ${address}` : address}
              placeholder="주소 검색을 눌러주세요"
              style={{
                flex: 1, padding: '13px 14px', fontSize: 14, borderRadius: 12,
                background: C.bgInput, border: `1px solid ${C.border}`, color: C.text,
              }}
            />
            <button
              onClick={() => openDaumPost('main')}
              style={{
                padding: '13px 14px', borderRadius: 12, fontSize: 13, fontWeight: 700,
                background: C.bgInput, border: `1px solid ${C.border}`, color: C.cyan,
                cursor: 'pointer', whiteSpace: 'nowrap',
              }}
            >주소 검색</button>
          </div>
          <input
            value={addressDetail}
            onChange={e => setAddressDetail(e.target.value)}
            placeholder="상세주소 입력 (동/호수 등)"
            style={{
              width: '100%', boxSizing: 'border-box', padding: '13px 14px', fontSize: 14, borderRadius: 12,
              background: C.bgInput, border: `1px solid ${C.border}`, color: C.text,
            }}
          />
        </div>

        {/* 구매자 전용: 배송지, 성별, 생년월일, 결제수단 */}
        {!hideConsumerFields && (
          <>
            {/* 배송지 주소 */}
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec }}>배송지 주소</label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: C.textSec, cursor: 'pointer' }}>
                  <input
                    type="checkbox" checked={sameAsAddr}
                    onChange={e => {
                      setSameAsAddr(e.target.checked);
                      if (e.target.checked) {
                        setShippingAddr(address);
                        setShippingZip(zipCode);
                        setShippingDetail(addressDetail);
                      }
                    }}
                  />
                  위와 동일
                </label>
              </div>
              {sameAsAddr ? (
                <input
                  readOnly
                  value={zipCode ? `[${zipCode}] ${address} ${addressDetail}` : `${address} ${addressDetail}`}
                  style={{
                    width: '100%', boxSizing: 'border-box', padding: '13px 14px', fontSize: 14, borderRadius: 12,
                    background: C.bgInput, border: `1px solid ${C.border}`, color: C.text, opacity: 0.5,
                  }}
                />
              ) : (
                <>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                    <input
                      readOnly value={shippingZip ? `[${shippingZip}] ${shippingAddr}` : shippingAddr}
                      placeholder="주소 검색을 눌러주세요"
                      style={{
                        flex: 1, padding: '13px 14px', fontSize: 14, borderRadius: 12,
                        background: C.bgInput, border: `1px solid ${C.border}`, color: C.text,
                      }}
                    />
                    <button
                      onClick={() => openDaumPost('shipping')}
                      style={{
                        padding: '13px 14px', borderRadius: 12, fontSize: 13, fontWeight: 700,
                        background: C.bgInput, border: `1px solid ${C.border}`, color: C.cyan,
                        cursor: 'pointer', whiteSpace: 'nowrap',
                      }}
                    >주소 검색</button>
                  </div>
                  <input
                    value={shippingDetail}
                    onChange={e => setShippingDetail(e.target.value)}
                    placeholder="상세주소 입력 (동/호수 등)"
                    style={{
                      width: '100%', boxSizing: 'border-box', padding: '13px 14px', fontSize: 14, borderRadius: 12,
                      background: C.bgInput, border: `1px solid ${C.border}`, color: C.text,
                    }}
                  />
                </>
              )}
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

            {/* 생년월일 — 3 selects */}
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec, display: 'block', marginBottom: 6 }}>생년월일</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <select value={birthYear} onChange={e => setBirthYear(e.target.value)} style={selectStyle}>
                  <option value="" style={{ background: '#1a1a2e', color: '#ffffff' }}>년도</option>
                  {years.map(y => <option key={y} value={y} style={{ background: '#1a1a2e', color: '#ffffff' }}>{y}년</option>)}
                </select>
                <select value={birthMonth} onChange={e => setBirthMonth(e.target.value)} style={selectStyle}>
                  <option value="" style={{ background: '#1a1a2e', color: '#ffffff' }}>월</option>
                  {months.map(m => <option key={m} value={m} style={{ background: '#1a1a2e', color: '#ffffff' }}>{m}월</option>)}
                </select>
                <select value={birthDay} onChange={e => setBirthDay(e.target.value)} style={selectStyle}>
                  <option value="" style={{ background: '#1a1a2e', color: '#ffffff' }}>일</option>
                  {days.map(d => <option key={d} value={d} style={{ background: '#1a1a2e', color: '#ffffff' }}>{d}일</option>)}
                </select>
              </div>
              {birthError && <div style={{ fontSize: 11, color: C.red, marginTop: 6 }}>{birthError}</div>}
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
              <div style={{ fontSize: 12, color: C.orange, marginTop: 8, padding: '8px 12px', background: 'rgba(255,152,0,0.06)', borderRadius: 8, lineHeight: 1.6 }}>
                선호 결제수단입니다. 실제 결제 시 PG사를 통해 안전하게 처리됩니다.
              </div>
            </div>
          </>
        )}
      </div>

      <PrimaryBtn label="다음" onClick={onNext} disabled={!canNext} />
    </div>
  );
}

// ── Step 4: 약관 동의 ─────────────────────────────────────
function TermsStep({ termsAgreed, setTermsAgreed, privacyAgreed, setPrivacyAgreed,
  marketingAgreed, setMarketingAgreed,
  sellerTermsAgreed, setSellerTermsAgreed,
  ecommerceTermsAgreed, setEcommerceTermsAgreed,
  role, onNext,
}: {
  termsAgreed: boolean; setTermsAgreed: (v: boolean) => void;
  privacyAgreed: boolean; setPrivacyAgreed: (v: boolean) => void;
  marketingAgreed: boolean; setMarketingAgreed: (v: boolean) => void;
  sellerTermsAgreed: boolean; setSellerTermsAgreed: (v: boolean) => void;
  ecommerceTermsAgreed: boolean; setEcommerceTermsAgreed: (v: boolean) => void;
  role: string; onNext: () => void;
}) {
  const isSeller = role === 'seller';
  const allChecked = termsAgreed && privacyAgreed && marketingAgreed
    && (!isSeller || (sellerTermsAgreed && ecommerceTermsAgreed));
  const toggleAll = () => {
    const next = !allChecked;
    setTermsAgreed(next); setPrivacyAgreed(next); setMarketingAgreed(next);
    if (isSeller) { setSellerTermsAgreed(next); setEcommerceTermsAgreed(next); }
  };
  const canNext = termsAgreed && privacyAgreed
    && (!isSeller || (sellerTermsAgreed && ecommerceTermsAgreed));

  const [termModal, setTermModal] = useState<string | null>(null);

  const TERM_CONTENTS: Record<string, string> = {
    '이용약관': '역핑 서비스 이용약관\n\n제1조 (목적)\n이 약관은 역핑(이하 "회사")이 제공하는 공동구매 중개 서비스(이하 "서비스")의 이용 조건 및 절차에 관한 사항을 규정함을 목적으로 합니다.\n\n제2조 (정의)\n1. "이용자"란 회사의 서비스에 접속하여 이 약관에 따라 회사가 제공하는 서비스를 이용하는 회원을 말합니다.\n2. "딜"이란 이용자가 공동구매를 위해 생성하는 거래 요청을 말합니다.\n3. "오퍼"란 판매자가 딜에 대해 제안하는 가격 및 조건을 말합니다.\n\n제3조 (약관의 효력)\n이 약관은 서비스 화면에 게시하거나 기타의 방법으로 이용자에게 공지함으로써 효력을 발생합니다.',
    '개인정보처리방침': '개인정보처리방침\n\n역핑(이하 "회사")은 이용자의 개인정보를 중요시하며, "개인정보 보호법" 등 관련 법령을 준수합니다.\n\n1. 수집하는 개인정보 항목\n- 필수: 이메일, 비밀번호, 닉네임\n- 선택: 전화번호, 주소, 성별, 생년월일\n\n2. 개인정보의 수집 및 이용 목적\n- 서비스 이용에 따른 본인확인, 회원관리\n- 공동구매 거래 처리 및 정산\n- 서비스 개선 및 마케팅 활용\n\n3. 개인정보의 보유 및 이용 기간\n- 회원 탈퇴 시까지 (법령에 따른 보관 의무가 있는 경우 해당 기간까지)',
    '마케팅 수신': '마케팅 정보 수신 동의\n\n역핑에서 제공하는 이벤트, 할인 정보, 신규 서비스 안내 등의 마케팅 정보를 이메일, SMS, 푸시 알림 등으로 수신하는 것에 동의합니다.\n\n마케팅 수신 동의는 선택사항이며, 동의하지 않아도 서비스 이용에는 제한이 없습니다.\n\n수신 동의 후에도 마이페이지에서 언제든 수신 거부할 수 있습니다.',
    '판매자 이용약관': '역핑 판매자 이용약관\n\n제1조 (목적)\n이 약관은 역핑 플랫폼에서 판매 활동을 수행하는 판매자의 권리와 의무를 규정합니다.\n\n제2조 (판매자 의무)\n1. 판매자는 정확한 상품 정보를 제공해야 합니다.\n2. 판매자는 약속한 배송 기한 내에 상품을 발송해야 합니다.\n3. 판매자는 오퍼 확정 후 임의로 거래를 취소할 수 없습니다.\n\n제3조 (수수료)\n역핑은 거래 성사 시 정책에 따른 플랫폼 수수료를 정산 시 차감합니다.\n\n제4조 (정산)\n정산은 구매자의 구매확정 후 정산 정책에 따라 진행됩니다.',
    '전자상거래법 동의': '전자상거래 등에서의 소비자보호에 관한 법률 동의\n\n전자상거래법 제13조에 따라 판매자는 다음 정보를 소비자에게 제공해야 합니다:\n\n1. 상호, 대표자 성명, 주소, 전화번호\n2. 사업자등록번호, 통신판매업 신고번호\n3. 상품의 가격, 배송비, 설치비 등 추가비용\n4. 청약철회 및 교환/반품 조건\n\n판매자는 위 법률을 준수하며 건전한 전자상거래 환경 조성에 동참합니다.',
  };

  const CheckRow = ({ checked, onChange, label, required, termKey }: {
    checked: boolean; onChange: (v: boolean) => void; label: string; required?: boolean; termKey?: string;
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
          {required ? <span style={{ color: C.red, marginRight: 4 }}>[필수]</span> : <span style={{ color: C.textSec, marginRight: 4 }}>[선택]</span>}
          {label}
        </span>
      </div>
      {termKey && (
        <button
          onClick={e => { e.preventDefault(); e.stopPropagation(); setTermModal(termKey); }}
          style={{ fontSize: 11, color: C.cyan, cursor: 'pointer', whiteSpace: 'nowrap', background: 'none', border: 'none', padding: 0 }}
        >보기</button>
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
        <CheckRow checked={termsAgreed} onChange={setTermsAgreed} label="이용약관 동의" required termKey="이용약관" />
        <div style={{ height: 1, background: C.border, margin: '0 16px' }} />
        <CheckRow checked={privacyAgreed} onChange={setPrivacyAgreed} label="개인정보처리방침 동의" required termKey="개인정보처리방침" />
        <div style={{ height: 1, background: C.border, margin: '0 16px' }} />
        <CheckRow checked={marketingAgreed} onChange={setMarketingAgreed} label="마케팅 수신 동의" termKey="마케팅 수신" />
        {isSeller && (
          <>
            <div style={{ height: 1, background: C.border, margin: '0 16px' }} />
            <CheckRow checked={sellerTermsAgreed} onChange={setSellerTermsAgreed} label="판매자 이용약관 동의" required termKey="판매자 이용약관" />
            <div style={{ height: 1, background: C.border, margin: '0 16px' }} />
            <CheckRow checked={ecommerceTermsAgreed} onChange={setEcommerceTermsAgreed} label="전자상거래법 동의" required termKey="전자상거래법 동의" />
          </>
        )}
      </div>

      <PrimaryBtn label="다음" onClick={onNext} disabled={!canNext} />

      {/* 약관 보기 모달 */}
      {termModal && (
        <div
          onClick={() => setTermModal(null)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000, display: 'flex', alignItems: 'flex-end' }}
        >
          <div
            onClick={e => e.stopPropagation()}
            style={{
              width: '100%', maxHeight: '80dvh', background: '#1a1a2e',
              borderRadius: '20px 20px 0 0', padding: '20px 20px 40px', overflowY: 'auto',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <span style={{ fontSize: 16, fontWeight: 800, color: C.text }}>{termModal}</span>
              <button onClick={() => setTermModal(null)} style={{ fontSize: 18, color: C.textDim, cursor: 'pointer', background: 'none', border: 'none' }}>✕</button>
            </div>
            <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.8, whiteSpace: 'pre-wrap' }}>
              {TERM_CONTENTS[termModal] ?? '약관 내용을 불러올 수 없습니다.'}
            </div>
            <button
              onClick={() => setTermModal(null)}
              style={{
                width: '100%', marginTop: 20, padding: '14px', borderRadius: 14,
                background: C.green, color: '#0a0a0f', fontSize: 14, fontWeight: 800, cursor: 'pointer',
              }}
            >확인</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Step 5: 사업자 정보 ───────────────────────────────────
function BizStep({
  role,
  bizName, setBizName, bizNum, setBizNum, ceoName, setCeoName,
  bankName, setBankName, accountNum, setAccountNum, accountHolder, setAccountHolder,
  actuatorCode, setActuatorCode, actuatorVerified, setActuatorVerified, setActuatorResolvedId,
  fromRef,
  bizLicenseUrl, setBizLicenseUrl, ecommercePermitUrl, setEcommercePermitUrl, bankbookUrl, setBankbookUrl,
  // actuator biz fields
  actIsBusiness, setActIsBusiness,
  actBizName, setActBizName, actBizNum, setActBizNum, actEcommerceNum, setActEcommerceNum,
  actBizAddress, setActBizAddress, actBizZipCode, setActBizZipCode,
  actBizAddressDetail, setActBizAddressDetail,
  actCompanyPhone, setActCompanyPhone,
  actBizLicenseUrl, setActBizLicenseUrl, actEcommercePermitUrl, setActEcommercePermitUrl,
  externalRatings, setExternalRatings,
  onNext,
}: {
  role: string;
  bizName: string; setBizName: (v: string) => void;
  bizNum: string; setBizNum: (v: string) => void;
  ceoName: string; setCeoName: (v: string) => void;
  bankName: string; setBankName: (v: string) => void;
  accountNum: string; setAccountNum: (v: string) => void;
  accountHolder: string; setAccountHolder: (v: string) => void;
  actuatorCode: string; setActuatorCode: (v: string) => void;
  actuatorVerified: boolean; setActuatorVerified: (v: boolean) => void;
  setActuatorResolvedId: (v: number | null) => void;
  fromRef?: boolean;
  bizLicenseUrl: string; setBizLicenseUrl: (v: string) => void;
  ecommercePermitUrl: string; setEcommercePermitUrl: (v: string) => void;
  bankbookUrl: string; setBankbookUrl: (v: string) => void;
  // actuator biz
  actIsBusiness: boolean; setActIsBusiness: (v: boolean) => void;
  actBizName: string; setActBizName: (v: string) => void;
  actBizNum: string; setActBizNum: (v: string) => void;
  actEcommerceNum: string; setActEcommerceNum: (v: string) => void;
  actBizAddress: string; setActBizAddress: (v: string) => void;
  actBizZipCode: string; setActBizZipCode: (v: string) => void;
  actBizAddressDetail: string; setActBizAddressDetail: (v: string) => void;
  actCompanyPhone: string; setActCompanyPhone: (v: string) => void;
  actBizLicenseUrl: string; setActBizLicenseUrl: (v: string) => void;
  actEcommercePermitUrl: string; setActEcommercePermitUrl: (v: string) => void;
  externalRatings: { platform: string; score: string; maxScore: string; evidenceType: 'file' | 'url'; evidenceFile: string; evidenceUrl: string }[];
  setExternalRatings: (v: { platform: string; score: string; maxScore: string; evidenceType: 'file' | 'url'; evidenceFile: string; evidenceUrl: string }[]) => void;
  onNext: () => void;
}) {
  const [bizVerify, setBizVerify] = useState<'idle' | 'checking' | 'ok'>('idle');
  const [actuatorName, setActuatorName] = useState('');
  const [actuatorError, setActuatorError] = useState('');
  const [uploadingField, setUploadingField] = useState('');

  const isSeller = role === 'seller';
  const isActuator = role === 'actuator';

  // actuator: region (kept as local state since not submitted)
  const [region, setRegion] = useState('');

  const doVerifyBiz = () => {
    if (!bizNum || bizVerify === 'ok') return;
    setBizVerify('checking');
    setTimeout(() => setBizVerify('ok'), 1200);
  };

  const doVerifyActuator = async (codeOverride?: string) => {
    const code = (codeOverride || actuatorCode).trim().toUpperCase();
    if (!code) return;
    if (!code.startsWith('ACT-')) {
      setActuatorError('ACT-XXXXX 형식으로 입력해주세요');
      return;
    }
    setActuatorError('');
    try {
      const res = await apiClient.get(API.ACTUATORS.VERIFY_CODE(code));
      const data = res.data as { valid: boolean; actuator_id?: number; name?: string; message?: string };
      if (data.valid) {
        setActuatorName(data.name || `액추에이터 #${data.actuator_id}`);
        setActuatorResolvedId(data.actuator_id ?? null);
        setActuatorVerified(true);
      } else {
        setActuatorError(data.message || '해당 추천코드를 찾을 수 없습니다');
        setActuatorResolvedId(null);
        setActuatorVerified(false);
      }
    } catch {
      setActuatorError('추천코드 확인에 실패했습니다');
      setActuatorResolvedId(null);
      setActuatorVerified(false);
    }
  };

  const uploadFileGeneric = (file: File, fieldKey: string, setter: (url: string) => void) => {
    if (file.size > 5 * 1024 * 1024) {
      showToast('파일 크기는 5MB 이하여야 해요.', 'error');
      return;
    }
    setUploadingField(fieldKey);
    const reader = new FileReader();
    reader.onload = () => {
      setter(reader.result as string);
      setUploadingField('');
    };
    reader.onerror = () => {
      showToast('파일 읽기에 실패했어요', 'error');
      setUploadingField('');
    };
    reader.readAsDataURL(file);
  };

  // seller용 shortcut
  const fieldSetters: Record<string, (url: string) => void> = {
    bizLicense: setBizLicenseUrl,
    ecommercePermit: setEcommercePermitUrl,
    bankbook: setBankbookUrl,
  };
  if (isActuator) {
    fieldSetters.bizLicense = setActBizLicenseUrl;
    fieldSetters.ecommercePermit = setActEcommercePermitUrl;
    // bankbook remains same
  }

  const [fileNames, setFileNames] = useState<Record<string, string>>({});
  const FileUploadRow = ({ label, url, field, required, disabled: rowDisabled }: {
    label: string; url: string; field: string; required?: boolean; disabled?: boolean;
  }) => {
    const isImage = url && url.startsWith('data:image/');
    const busy = uploadingField === field;
    return (
      <div style={{ opacity: rowDisabled ? 0.45 : 1, pointerEvents: rowDisabled ? 'none' : 'auto' }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 6 }}>
          {label} {required && <span style={{ color: C.red }}>*</span>}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ position: 'relative', flexShrink: 0 }}>
            <div style={{
              padding: '10px 16px', borderRadius: 12, fontSize: 13, fontWeight: 700,
              background: url ? `${C.green}20` : C.bgInput,
              border: `1px solid ${url ? C.green : C.border}`,
              color: url ? C.green : C.textSec,
              whiteSpace: 'nowrap', transition: 'all 0.15s',
              pointerEvents: 'none',
            }}>
              {busy ? '읽는 중...' : url ? '변경' : '파일 선택'}
            </div>
            <input
              type="file" accept=".jpg,.jpeg,.png,.pdf"
              disabled={busy || rowDisabled}
              style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0, cursor: busy ? 'not-allowed' : 'pointer' }}
              onClick={() => {
                const sy = window.scrollY;
                const restore = () => { window.scrollTo(0, sy); window.removeEventListener('focus', restore); };
                window.addEventListener('focus', restore);
              }}
              onChange={e => {
                const f = e.target.files?.[0];
                if (f) {
                  setFileNames(prev => ({ ...prev, [field]: f.name }));
                  uploadFileGeneric(f, field, fieldSetters[field] || (() => {}));
                }
                e.target.value = '';
              }}
            />
          </div>
          <span style={{ fontSize: 12, color: url ? C.green : C.textDim, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {url ? (fileNames[field] || '첨부 완료 ✓') : '미첨부'}
          </span>
        </div>
        {isImage && (
          <img src={url} alt={label} style={{ marginTop: 8, maxWidth: 120, maxHeight: 80, borderRadius: 8, border: `1px solid ${C.border}` }} />
        )}
        {url && !isImage && (
          <div style={{ marginTop: 6, fontSize: 11, color: C.textSec }}>📄 PDF 파일 첨부됨</div>
        )}
      </div>
    );
  };

  const canNext = isSeller
    ? !!bizName && !!ceoName && bizVerify === 'ok' && !!bankName && !!accountNum && !!accountHolder
      && !!bizLicenseUrl && !!ecommercePermitUrl && !!bankbookUrl
    : isActuator
      ? actIsBusiness
        ? !!actBizName && !!actBizNum && !!actBizLicenseUrl
        : !!bankName && !!accountNum && !!accountHolder && !!bankbookUrl
      : false;

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
            <InputField label="사업자명 *" value={bizName} onChange={setBizName} placeholder="상호명 입력" />
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec, display: 'block', marginBottom: 6 }}>사업자번호 *</label>
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
            <InputField label="대표자 이름 *" value={ceoName} onChange={setCeoName} placeholder="대표자 성함" />

            {/* 서류 첨부 3종 */}
            <div style={{ padding: '16px', background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 12 }}>서류 첨부</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <FileUploadRow label="사업자등록증" url={bizLicenseUrl} field="bizLicense" required />
                <FileUploadRow label="통신판매업신고증" url={ecommercePermitUrl} field="ecommercePermit" required />
                <FileUploadRow label="통장사본" url={bankbookUrl} field="bankbook" required />
              </div>
            </div>

            {/* 정산 계좌 */}
            <div style={{ padding: '16px', background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 12 }}>정산 계좌</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <InputField label="은행명 *" value={bankName} onChange={setBankName} placeholder="예: 국민은행" />
                <InputField label="계좌번호 *" value={accountNum} onChange={setAccountNum} placeholder="- 없이 숫자만" type="tel" />
                <InputField label="예금주 *" value={accountHolder} onChange={setAccountHolder} placeholder="예금주명" />
              </div>
            </div>

            {/* 액추에이터 추천 코드 */}
            <div>
              <label style={{ fontSize: 12, fontWeight: 600, color: C.textSec, display: 'block', marginBottom: 6 }}>추천 액추에이터 코드 — 선택</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  value={actuatorCode}
                  onChange={e => { setActuatorCode(e.target.value); setActuatorVerified(false); setActuatorResolvedId(null); setActuatorError(''); }}
                  placeholder="ACT-XXXXX 형식으로 입력"
                  disabled={actuatorVerified || fromRef}
                  style={{
                    flex: 1, padding: '13px 14px', fontSize: 14, borderRadius: 12,
                    background: C.bgInput, border: `1px solid ${C.border}`, color: C.text,
                    opacity: (actuatorVerified || fromRef) ? 0.5 : 1,
                  }}
                />
                <button
                  onClick={() => void doVerifyActuator()}
                  disabled={!actuatorCode || actuatorVerified}
                  style={{
                    padding: '13px 14px', borderRadius: 12, fontSize: 13, fontWeight: 700,
                    background: actuatorVerified ? `${C.green}20` : C.bgInput,
                    border: `1px solid ${actuatorVerified ? C.green : C.border}`,
                    color: actuatorVerified ? C.green : C.textSec,
                    cursor: (!actuatorCode || actuatorVerified) ? 'not-allowed' : 'pointer',
                    whiteSpace: 'nowrap', transition: 'all 0.15s',
                  }}
                >
                  {actuatorVerified ? '확인됨 ✓' : '확인'}
                </button>
              </div>
              {actuatorVerified && actuatorName && (
                <div style={{ fontSize: 11, color: C.green, marginTop: 4, paddingLeft: 2 }}>담당 액추에이터: {actuatorName}</div>
              )}
              {actuatorError && (
                <div style={{ fontSize: 11, color: C.red, marginTop: 4, paddingLeft: 2 }}>{actuatorError}</div>
              )}
            </div>

            {/* ── 외부 평점 (선택) ── */}
            <div style={{ padding: '16px', background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 4 }}>외부 평점 (선택)</div>
              <div style={{ fontSize: 11, color: C.textDim, marginBottom: 14 }}>타 플랫폼에서의 판매 평점을 입력하면 신뢰도가 올라갑니다.</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {externalRatings.map((r, idx) => {
                  const update = (field: string, val: string) => {
                    const next = [...externalRatings];
                    (next[idx] as Record<string, string>)[field] = val;
                    setExternalRatings(next);
                  };
                  const isCustom = idx >= 2; // 카카오, 네이버 이외
                  return (
                    <div key={idx} style={{ padding: '12px', background: 'rgba(255,255,255,0.02)', border: `1px solid ${C.border}`, borderRadius: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                        {isCustom ? (
                          <input
                            value={r.platform} onChange={e => update('platform', e.target.value)}
                            placeholder="플랫폼명"
                            style={{ fontSize: 13, fontWeight: 700, color: C.text, background: C.bgInput, border: `1px solid ${C.border}`, borderRadius: 8, padding: '6px 10px', width: 140 }}
                          />
                        ) : (
                          <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{r.platform}</span>
                        )}
                        {isCustom && (
                          <button onClick={() => { const next = externalRatings.filter((_, i) => i !== idx); setExternalRatings(next); }}
                            style={{ fontSize: 11, color: C.red, cursor: 'pointer', background: 'none', padding: '4px 8px' }}>삭제</button>
                        )}
                      </div>
                      <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 10 }}>
                        <input value={r.score} onChange={e => update('score', e.target.value.replace(/[^\d.]/g, ''))}
                          placeholder="평점" style={{ width: 60, padding: '8px 10px', fontSize: 13, borderRadius: 8, background: C.bgInput, border: `1px solid ${C.border}`, color: C.text, textAlign: 'center' }} />
                        <span style={{ fontSize: 13, color: C.textSec }}>/</span>
                        <input value={r.maxScore} onChange={e => update('maxScore', e.target.value.replace(/[^\d.]/g, ''))}
                          placeholder="만점" style={{ width: 60, padding: '8px 10px', fontSize: 13, borderRadius: 8, background: C.bgInput, border: `1px solid ${C.border}`, color: C.text, textAlign: 'center' }} />
                        <span style={{ fontSize: 11, color: C.textDim, marginLeft: 4 }}>근거:</span>
                        <select value={r.evidenceType} onChange={e => update('evidenceType', e.target.value)}
                          style={{ fontSize: 12, padding: '6px 8px', borderRadius: 8, background: C.bgInput, border: `1px solid ${C.border}`, color: C.text, cursor: 'pointer' }}>
                          <option value="file">파일</option>
                          <option value="url">URL</option>
                        </select>
                      </div>
                      {r.evidenceType === 'url' ? (
                        <input value={r.evidenceUrl} onChange={e => update('evidenceUrl', e.target.value)}
                          placeholder="https://..." style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', fontSize: 13, borderRadius: 8, background: C.bgInput, border: `1px solid ${C.border}`, color: C.text }} />
                      ) : (
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          <div style={{ position: 'relative', flexShrink: 0 }}>
                            <div style={{ padding: '8px 14px', borderRadius: 10, fontSize: 12, fontWeight: 700, background: r.evidenceFile ? `${C.green}20` : C.bgInput, border: `1px solid ${r.evidenceFile ? C.green : C.border}`, color: r.evidenceFile ? C.green : C.textSec, whiteSpace: 'nowrap', pointerEvents: 'none' }}>
                              {r.evidenceFile ? '변경' : '파일 선택'}
                            </div>
                            <input
                              type="file" accept=".jpg,.jpeg,.png,.pdf"
                              style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0, cursor: 'pointer' }}
                              onChange={e => {
                                const f = e.target.files?.[0];
                                if (f) {
                                  if (f.size > 5 * 1024 * 1024) { showToast('파일 크기는 5MB 이하여야 해요.', 'error'); return; }
                                  const reader = new FileReader();
                                  reader.onload = () => update('evidenceFile', reader.result as string);
                                  reader.readAsDataURL(f);
                                }
                                e.target.value = '';
                              }}
                            />
                          </div>
                          <span style={{ fontSize: 11, color: r.evidenceFile ? C.green : C.textDim }}>{r.evidenceFile ? '첨부됨 ✓' : '미첨부'}</span>
                        </div>
                      )}
                    </div>
                  );
                })}
                {externalRatings.length < 7 && (
                  <button onClick={() => setExternalRatings([...externalRatings, { platform: '', score: '', maxScore: '', evidenceType: 'file', evidenceFile: '', evidenceUrl: '' }])}
                    style={{ fontSize: 13, fontWeight: 700, color: C.cyan, background: 'none', cursor: 'pointer', padding: '8px 0', textAlign: 'left' }}>
                    + 플랫폼 추가
                  </button>
                )}
              </div>
            </div>
          </>
        ) : (
          <>
            {/* 주요 운영 지역 (선택) */}
            <InputField label="주요 운영 지역 (선택)" value={region} onChange={setRegion} placeholder="예: 서울·경기" />

            {/* 유형 선택: 개인 / 사업자 */}
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 8 }}>유형 선택</div>
              <div style={{ display: 'flex', gap: 8 }}>
                {([false, true] as const).map(isBiz => {
                  const selected = actIsBusiness === isBiz;
                  const label = isBiz ? '사업자' : '개인';
                  const icon = isBiz ? '🏢' : '👤';
                  const accentColor = isBiz ? C.yellow : C.green;
                  return (
                    <button key={label} onClick={() => setActIsBusiness(isBiz)} style={{
                      flex: 1, padding: '14px 12px', borderRadius: 12, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 10, transition: 'all 0.15s',
                      background: selected ? `${accentColor}10` : 'transparent',
                      border: `1.5px solid ${selected ? accentColor : C.border}`,
                    }}>
                      <div style={{
                        width: 20, height: 20, borderRadius: '50%', flexShrink: 0,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        background: selected ? accentColor : 'transparent',
                        border: `2px solid ${selected ? accentColor : C.border}`,
                        transition: 'all 0.15s',
                      }}>
                        {selected && <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#0a0a0f' }} />}
                      </div>
                      <span style={{ fontSize: 14 }}>{icon}</span>
                      <span style={{ fontSize: 13, fontWeight: 700, color: selected ? accentColor : C.text }}>{label}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* ── 개인 선택 시 ── */}
            {!actIsBusiness && (
              <div style={{ padding: '16px', background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 12 }}>정산 계좌</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <InputField label="은행명 *" value={bankName} onChange={setBankName} placeholder="예: 국민은행" />
                  <InputField label="계좌번호 *" value={accountNum} onChange={setAccountNum} placeholder="- 없이 숫자만" type="tel" />
                  <InputField label="예금주 *" value={accountHolder} onChange={setAccountHolder} placeholder="예금주명" />
                  <FileUploadRow label="통장사본" url={bankbookUrl} field="bankbook" required />
                </div>
              </div>
            )}

            {/* ── 사업자 선택 시 ── */}
            {actIsBusiness && (
              <>
                <div style={{ padding: '16px', background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 12 }}>회사 정보</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <InputField label="상호명 (사업자명) *" value={actBizName} onChange={setActBizName} placeholder="상호명 입력" />
                    <InputField label="사업자등록번호 *" value={actBizNum} onChange={setActBizNum} placeholder="000-00-00000" />
                    <InputField label="통신판매업신고번호 (선택)" value={actEcommerceNum} onChange={setActEcommerceNum} placeholder="신고번호" />
                    {/* 주소 (카카오 주소 API) */}
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 6 }}>주소</div>
                      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
                        <input
                          readOnly value={actBizZipCode ? `[${actBizZipCode}] ${actBizAddress}` : actBizAddress}
                          placeholder="주소 검색을 눌러주세요"
                          style={{
                            flex: 1, padding: '13px 14px', fontSize: 14, borderRadius: 12,
                            background: C.bgInput, border: `1px solid ${C.border}`, color: C.text,
                          }}
                        />
                        <button
                          onClick={() => {
                            if (!window.daum?.Postcode) { showToast('주소 검색 서비스를 불러오는 중이에요.', 'info'); return; }
                            new window.daum.Postcode({
                              oncomplete: (data) => { setActBizAddress(data.address); setActBizZipCode(data.zonecode); },
                            }).open();
                          }}
                          style={{
                            padding: '13px 14px', borderRadius: 12, fontSize: 13, fontWeight: 700,
                            background: C.bgInput, border: `1px solid ${C.border}`, color: C.cyan,
                            cursor: 'pointer', whiteSpace: 'nowrap',
                          }}
                        >주소 검색</button>
                      </div>
                      <input
                        value={actBizAddressDetail}
                        onChange={e => setActBizAddressDetail(e.target.value)}
                        placeholder="상세주소 입력"
                        style={{
                          width: '100%', boxSizing: 'border-box', padding: '13px 14px', fontSize: 14, borderRadius: 12,
                          background: C.bgInput, border: `1px solid ${C.border}`, color: C.text,
                        }}
                      />
                    </div>
                    <InputField label="전화번호 (회사)" value={actCompanyPhone} onChange={setActCompanyPhone} placeholder="02-0000-0000" type="tel" />
                  </div>
                </div>

                <div style={{ padding: '16px', background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 12 }}>서류 첨부</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <FileUploadRow label="사업자등록증" url={actBizLicenseUrl} field="bizLicense" required />
                    <FileUploadRow label="통신판매업신고증 (선택)" url={actEcommercePermitUrl} field="ecommercePermit" />
                  </div>
                </div>

                {/* 사업자 정산 계좌 (선택) */}
                <div style={{ padding: '16px', background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.textSec, marginBottom: 4 }}>정산 계좌 (선택)</div>
                  <div style={{ fontSize: 11, color: C.textDim, marginBottom: 10 }}>사업자의 경우 선택 항목입니다</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <InputField label="은행명" value={bankName} onChange={setBankName} placeholder="예: 국민은행" />
                    <InputField label="계좌번호" value={accountNum} onChange={setAccountNum} placeholder="- 없이 숫자만" type="tel" />
                    <InputField label="예금주" value={accountHolder} onChange={setAccountHolder} placeholder="예금주명" />
                    <FileUploadRow label="통장사본" url={bankbookUrl} field="bankbook" />
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </div>

      <PrimaryBtn label="다음" onClick={onNext} disabled={!canNext} />
    </div>
  );
}

// ── Step 6: 완료 ──────────────────────────────────────────
const METHOD_LABELS: Record<string, string> = { kakao: '카카오', naver: '네이버', google: 'Google', phone: '전화번호', email: '이메일' };
const ROLE_LABELS: Record<string, string> = { buyer: '구매자', seller: '판매자', actuator: '액추에이터' };

function CompleteStep({ method, role, nickname, onFinish, navigate, email, password }: {
  method: string; role: string; nickname: string; onFinish: () => void;
  navigate: (path: string, opts?: { state?: Record<string, string> }) => void;
  email?: string; password?: string;
}) {
  const isSeller = role === 'seller';
  const isActuator = role === 'actuator';
  const needsApproval = isSeller || isActuator;

  return (
    <div style={{
      minHeight: '100dvh', display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', padding: '24px',
    }}>
      <style>{`@keyframes checkPop { 0%{transform:scale(0);opacity:0} 60%{transform:scale(1.2)} 100%{transform:scale(1);opacity:1} }`}</style>
      <div style={{
        width: 80, height: 80, borderRadius: '50%',
        background: `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 36, color: '#0a0a0f', fontWeight: 900,
        marginBottom: 24, animation: 'checkPop 0.5s cubic-bezier(0.175,0.885,0.32,1.275) both',
      }}>✓</div>

      <div style={{ fontSize: 24, fontWeight: 900, color: C.text, marginBottom: 6, textAlign: 'center' }}>가입 완료!</div>
      <div style={{ fontSize: 14, color: C.textSec, marginBottom: 36, textAlign: 'center' }}>역핑에 오신 걸 환영해요</div>

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

      {needsApproval ? (
        /* 판매자/액츄에이터: 승인 대기 안내 */
        <div style={{
          width: '100%', maxWidth: 320,
          background: 'rgba(0,229,255,0.06)',
          border: '1px solid rgba(0,229,255,0.25)',
          borderRadius: 16, padding: '18px 20px', marginBottom: 20,
        }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: C.cyan, marginBottom: 8 }}>관리자 승인 대기 중</div>
          <div style={{ fontSize: 13, color: C.textSec, lineHeight: 1.7 }}>
            제출하신 정보를 검토 중이에요.<br />
            관리자 승인 후 {isSeller ? '판매를' : '활동을'} 시작할 수 있어요.<br />
            승인이 완료되면 알림을 보내드릴게요.
          </div>
        </div>
      ) : (
        /* 구매자: 결제수단 CTA */
        <div style={{
          width: '100%', maxWidth: 320,
          background: 'rgba(255,152,0,0.06)',
          border: '1px solid rgba(255,152,0,0.25)',
          borderRadius: 16, padding: '18px 20px', marginBottom: 20,
        }}>
          <div style={{ fontSize: 15, fontWeight: 800, color: C.orange, marginBottom: 8 }}>결제수단을 미리 등록하세요!</div>
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
      )}

      <button
        onClick={needsApproval ? () => navigate('/login', { state: { email: email || '', password: password || '' } }) : onFinish}
        style={{
          width: '100%', maxWidth: 320, padding: '15px',
          borderRadius: 14, fontSize: 15, fontWeight: 800,
          background: `linear-gradient(135deg, ${C.green}, ${C.cyan})`,
          color: '#0a0a0f', cursor: 'pointer',
        }}
      >{needsApproval ? '로그인하기' : '역핑 시작하기 →'}</button>
    </div>
  );
}

// ── 메인 컴포넌트 ────────────────────────────────────────
export default function RegisterPage() {
  const navigate       = useNavigate();
  const [searchParams] = useSearchParams();
  const method         = searchParams.get('method') ?? 'email';
  const { login }      = useAuth();

  const [step, setStep] = useState(1);
  const [dir,  setDir]  = useState(1);

  // step 1 — role
  const [role, setRole] = useState<'buyer' | 'seller' | 'actuator' | ''>('');

  // step 2 — email / password
  const [email,            setEmailRaw]          = useState('');
  const [emailStatus,      setEmailStatus]       = useState<'idle' | 'checking' | 'ok' | 'taken' | 'invalid'>('idle');
  const [emailMsg,         setEmailMsg]          = useState('');
  const [password,         setPasswordRaw]       = useState('');
  const [passwordConfirm,  setPasswordConfirmRaw]= useState('');
  const [showPw,           setShowPw]            = useState(false);
  const [showPwConfirm,    setShowPwConfirm]     = useState(false);
  const [apiError,         setApiError]          = useState('');
  const [registering,      setRegistering]       = useState(false);

  // step 2 — nickname
  const [nickname,    setNicknameRaw] = useState('');
  const [nickStatus,  setNickStatus]  = useState<'idle' | 'checking' | 'ok' | 'taken' | 'banned' | 'invalid'>('idle');
  const [nickMsg,     setNickMsg]     = useState('');
  const [recommender, setRecommender] = useState('');

  // step 3 — extra info
  const [phone,         setPhoneRaw]     = useState('');
  const [phoneStatus,   setPhoneStatus]  = useState<'idle' | 'checking' | 'ok' | 'taken' | 'invalid'>('idle');
  const [phoneMsg,      setPhoneMsg]     = useState('');
  const [address,       setAddress]      = useState('');
  const [zipCode,       setZipCode]      = useState('');
  const [addressDetail, setAddressDetail]= useState('');
  const [shippingAddr,  setShippingAddr] = useState('');
  const [shippingZip,   setShippingZip]  = useState('');
  const [shippingDetail,setShippingDetail]= useState('');
  const [sameAsAddr,    setSameAsAddr]   = useState(false);
  const [gender,        setGender]       = useState('');
  const [birthYear,     setBirthYear]    = useState('');
  const [birthMonth,    setBirthMonth]   = useState('');
  const [birthDay,      setBirthDay]     = useState('');
  const [paymentMethod, setPaymentMethod]= useState('');
  const [companyPhone,  setCompanyPhone] = useState('');

  // step 4 — terms
  const [termsAgreed,     setTermsAgreed]     = useState(false);
  const [privacyAgreed,   setPrivacyAgreed]   = useState(false);
  const [marketingAgreed, setMarketingAgreed] = useState(false);
  const [sellerTermsAgreed,    setSellerTermsAgreed]    = useState(false);
  const [ecommerceTermsAgreed, setEcommerceTermsAgreed] = useState(false);

  // step 5 — biz (lifted from BizStep for seller API call)
  const [bizName,       setBizName]       = useState('');
  const [bizNum,        setBizNum]        = useState('');
  const [ceoName,       setCeoName]       = useState('');
  const [bankName,      setBankName]      = useState('');
  const [accountNum,    setAccountNum]    = useState('');
  const [accountHolder, setAccountHolder] = useState('');
  const [actuatorCode,     setActuatorCode]     = useState('');  // ACT-XXXXX 코드
  const [actuatorVerified, setActuatorVerified] = useState(false);
  const [actuatorResolvedId, setActuatorResolvedId] = useState<number | null>(null);  // 확인된 DB id
  const [fromRef, setFromRef] = useState(false);  // URL 파라미터로 자동 입력됨
  const [bizLicenseUrl,       setBizLicenseUrl]       = useState('');
  const [ecommercePermitUrl,  setEcommercePermitUrl]  = useState('');
  const [bankbookUrl,         setBankbookUrl]         = useState('');

  // step 5 — actuator biz (사업자 체크 시)
  const [actIsBusiness, setActIsBusiness] = useState(false);
  const [actBizName, setActBizName] = useState('');
  const [actBizNum, setActBizNum] = useState('');
  const [actEcommerceNum, setActEcommerceNum] = useState('');
  const [actBizAddress, setActBizAddress] = useState('');
  const [actBizZipCode, setActBizZipCode] = useState('');
  const [actBizAddressDetail, setActBizAddressDetail] = useState('');
  const [actCompanyPhone, setActCompanyPhone] = useState('');
  const [actBizLicenseUrl, setActBizLicenseUrl] = useState('');
  const [actEcommercePermitUrl, setActEcommercePermitUrl] = useState('');

  // step 5 — external ratings (seller only)
  interface ExtRating { platform: string; score: string; maxScore: string; evidenceType: 'file' | 'url'; evidenceFile: string; evidenceUrl: string }
  const [externalRatings, setExternalRatings] = useState<ExtRating[]>([
    { platform: '카카오 스토어', score: '', maxScore: '', evidenceType: 'file', evidenceFile: '', evidenceUrl: '' },
    { platform: '네이버 스마트스토어', score: '', maxScore: '', evidenceType: 'file', evidenceFile: '', evidenceUrl: '' },
  ]);

  // ── Debounce timers ─────────────────────────────────────
  const nickTimer  = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const emailTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const phoneTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => {
    clearTimeout(nickTimer.current);
    clearTimeout(emailTimer.current);
    clearTimeout(phoneTimer.current);
  }, []);

  // ── URL 파라미터 자동 처리 (초대 링크) ──────────────────
  useEffect(() => {
    const refCode = searchParams.get('ref');
    const roleParam = searchParams.get('role');
    if (roleParam === 'seller') {
      setRole('seller');
    }
    if (refCode && refCode.toUpperCase().startsWith('ACT-')) {
      const code = refCode.toUpperCase();
      setActuatorCode(code);
      setFromRef(true);
      // 자동 검증
      (async () => {
        try {
          const res = await apiClient.get(API.ACTUATORS.VERIFY_CODE(code));
          const data = res.data as { valid: boolean; actuator_id?: number; name?: string };
          if (data.valid) {
            setActuatorResolvedId(data.actuator_id ?? null);
            setActuatorVerified(true);
          }
        } catch { /* 자동 검증 실패 시 수동 입력 가능 */ }
      })();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Nickname handler ────────────────────────────────────
  const setNickname = useCallback((val: string) => {
    setNicknameRaw(val);
    clearTimeout(nickTimer.current);

    if (!val) { setNickStatus('idle'); setNickMsg(''); return; }
    if (val.length < 2) {
      setNickStatus('invalid');
      setNickMsg('닉네임은 2글자 이상이어야 해요');
      return;
    }
    if (BANNED_NICKNAMES.has(val.toLowerCase())) {
      setNickStatus('banned');
      setNickMsg('사용할 수 없는 닉네임이에요');
      return;
    }
    if (!NICK_RE.test(val)) {
      setNickStatus('invalid');
      setNickMsg('한글, 영문, 숫자, _만 사용할 수 있어요');
      return;
    }

    setNickStatus('checking');
    setNickMsg('확인 중...');
    nickTimer.current = setTimeout(async () => {
      try {
        const res = await apiClient.get(API.AUTH.CHECK_NICKNAME, { params: { nickname: val } });
        const data = res.data as { available: boolean; reason?: string };
        if (data.available) {
          setNickStatus('ok');
          setNickMsg('사용할 수 있는 닉네임이에요 ✓');
        } else if (data.reason === 'banned') {
          setNickStatus('banned');
          setNickMsg('사용할 수 없는 닉네임이에요');
        } else {
          setNickStatus('taken');
          setNickMsg('이미 사용 중인 닉네임이에요');
        }
      } catch {
        setNickStatus('ok');
        setNickMsg('사용할 수 있는 닉네임이에요 ✓');
      }
    }, 600);
  }, []);

  // ── Email handler ───────────────────────────────────────
  const setEmail = useCallback((val: string) => {
    setEmailRaw(val);
    clearTimeout(emailTimer.current);

    if (!val) { setEmailStatus('idle'); setEmailMsg(''); return; }
    if (!EMAIL_RE.test(val)) {
      setEmailStatus('invalid');
      setEmailMsg('올바른 이메일 형식이 아니에요');
      return;
    }

    setEmailStatus('checking');
    setEmailMsg('확인 중...');
    emailTimer.current = setTimeout(async () => {
      try {
        const res = await apiClient.get(API.AUTH.CHECK_EMAIL, { params: { email: val.trim() } });
        const data = res.data as { available: boolean };
        if (data.available) {
          setEmailStatus('ok');
          setEmailMsg('사용할 수 있는 이메일이에요 ✓');
        } else {
          setEmailStatus('taken');
          setEmailMsg('이미 사용 중인 이메일이에요');
        }
      } catch {
        setEmailStatus('ok');
        setEmailMsg('사용할 수 있는 이메일이에요 ✓');
      }
    }, 600);
  }, []);

  // ── Password validation ─────────────────────────────────
  const pwError = password && !PW_RE.test(password)
    ? '비밀번호는 8자 이상, 영문+숫자+특수문자를 포함해야 해요'
    : '';
  const pwConfirmError = passwordConfirm && password !== passwordConfirm
    ? '비밀번호가 일치하지 않아요'
    : '';

  const setPassword = (val: string) => setPasswordRaw(val);
  const setPasswordConfirm = (val: string) => setPasswordConfirmRaw(val);

  // ── Phone handler ───────────────────────────────────────
  const formatPhone = (raw: string): string => {
    const digits = raw.replace(/\D/g, '').slice(0, 11);
    if (digits.length <= 3) return digits;
    if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
  };

  const setPhone = useCallback((val: string) => {
    const formatted = formatPhone(val);
    setPhoneRaw(formatted);
    clearTimeout(phoneTimer.current);

    const digits = formatted.replace(/\D/g, '');
    if (!digits) { setPhoneStatus('idle'); setPhoneMsg(''); return; }
    if (!digits.startsWith('010') || digits.length !== 11) {
      setPhoneStatus('invalid');
      setPhoneMsg('올바른 전화번호 형식이 아니에요 (010-XXXX-XXXX)');
      return;
    }

    setPhoneStatus('checking');
    setPhoneMsg('확인 중...');
    phoneTimer.current = setTimeout(async () => {
      try {
        const res = await apiClient.get(API.AUTH.CHECK_PHONE, { params: { phone: digits } });
        const data = res.data as { available: boolean };
        if (data.available) {
          setPhoneStatus('ok');
          setPhoneMsg('사용할 수 있는 전화번호예요 ✓');
        } else {
          setPhoneStatus('taken');
          setPhoneMsg('이미 등록된 전화번호예요');
        }
      } catch {
        setPhoneStatus('ok');
        setPhoneMsg('사용할 수 있는 전화번호예요 ✓');
      }
    }, 600);
  }, []);

  // ── Birth date validation ───────────────────────────────
  const birthError = birthYear && birthMonth && birthDay
    ? isUnder14(Number(birthYear), Number(birthMonth), Number(birthDay))
      ? '만 14세 이상만 가입할 수 있어요'
      : ''
    : '';

  // ── Navigation ──────────────────────────────────────────
  const goTo = (n: number) => { setDir(n > step ? 1 : -1); setStep(n); };

  const TOTAL_STEPS = 5;

  const goNext = async () => {
    if (step === 1) { goTo(2); return; }
    if (step === 2) { goTo(3); return; }
    if (step === 3) { goTo(4); return; }
    if (step === 4) {
      // 약관 동의 후 → 구매자면 buyer API, 판매자/액츄에이터는 BizStep
      if (role === 'buyer') {
        if (FEATURES.USE_API_AUTH && method === 'email') {
          setRegistering(true);
          setApiError('');

          const fullAddress = address ? (addressDetail ? `${address} ${addressDetail}` : address) : undefined;
          const fullBirthDate = birthYear && birthMonth && birthDay
            ? `${birthYear}-${String(birthMonth).padStart(2, '0')}-${String(birthDay).padStart(2, '0')}`
            : undefined;

          try {
            await apiClient.post(API.BUYERS.LIST, {
              email: email.trim(), password,
              name: nickname, nickname,
              phone: phone.replace(/\D/g, '') || undefined,
              address: fullAddress,
              zip_code: zipCode || undefined,
              gender: gender || undefined,
              birth_date: fullBirthDate || undefined,
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
            goTo(6);
          } catch (err: unknown) {
            const e = err as { response?: { data?: { detail?: unknown }; status?: number } };
            const detail = e.response?.data?.detail;
            const status = e.response?.status;
            let msg: string;
            if (typeof detail === 'string') {
              msg = detail;
            } else if (Array.isArray(detail)) {
              msg = detail.map((d: Record<string, unknown>) => {
                const field = Array.isArray(d.loc) ? (d.loc as string[]).slice(-1)[0] : '';
                return field ? `${field}: ${d.msg}` : String(d.msg || '');
              }).join(' / ');
            } else if (status) {
              msg = `서버 오류 (${status}): 가입에 실패했어요.`;
            } else {
              msg = '네트워크 오류: 서버에 연결할 수 없어요.';
            }
            setApiError(msg);
          } finally {
            setRegistering(false);
          }
          return;
        }
        goTo(6);
      } else {
        // 판매자/액추에이터 → BizStep
        goTo(5);
      }
      return;
    }
    if (step === 5) {
      if (FEATURES.USE_API_AUTH && method === 'email') {
        setRegistering(true);
        setApiError('');

        const fullAddress = address ? (addressDetail ? `${address} ${addressDetail}` : address) : undefined;

        try {
          if (role === 'seller') {
            // 판매자 API 호출
            await apiClient.post(API.SELLERS.LIST, {
              email: email.trim(), password,
              business_name: bizName,
              nickname,
              business_number: bizNum.replace(/\D/g, ''),
              phone: phone.replace(/\D/g, '') || undefined,
              company_phone: companyPhone.replace(/\D/g, '') || undefined,
              address: fullAddress || '',
              zip_code: zipCode || '',
              established_date: new Date().toISOString(),
              bank_name: bankName || undefined,
              account_number: accountNum || undefined,
              account_holder: accountHolder || undefined,
              actuator_id: actuatorVerified && actuatorResolvedId ? actuatorResolvedId : undefined,
              business_license_image: bizLicenseUrl || undefined,
              ecommerce_permit_image: ecommercePermitUrl || undefined,
              bankbook_image: bankbookUrl || undefined,
              external_ratings: externalRatings.some(r => r.score) ? JSON.stringify(externalRatings.filter(r => r.score)) : undefined,
            });
          } else if (role === 'actuator') {
            // 액추에이터 API 호출
            const actFullBizAddr = actBizAddress
              ? (actBizAddressDetail ? `${actBizAddress} ${actBizAddressDetail}` : actBizAddress)
              : undefined;
            await apiClient.post(API.ACTUATORS.CREATE, {
              name: nickname,
              email: email.trim(),
              phone: phone.replace(/\D/g, '') || undefined,
              password,
              nickname,
              bank_name: bankName || undefined,
              account_number: accountNum || undefined,
              account_holder: accountHolder || undefined,
              bankbook_image: bankbookUrl || undefined,
              is_business: actIsBusiness,
              ...(actIsBusiness ? {
                business_name: actBizName || undefined,
                business_number: actBizNum || undefined,
                ecommerce_permit_number: actEcommerceNum || undefined,
                business_address: actFullBizAddr || undefined,
                business_zip_code: actBizZipCode || undefined,
                company_phone: actCompanyPhone || undefined,
                business_license_image: actBizLicenseUrl || undefined,
                ecommerce_permit_image: actEcommercePermitUrl || undefined,
              } : {}),
            });
          }
          // 자동 로그인 스킵 → CompleteStep
          goTo(6);
        } catch (err: unknown) {
          const e = err as { response?: { data?: { detail?: unknown }; status?: number } };
          const detail = e.response?.data?.detail;
          const status = e.response?.status;
          let msg: string;
          if (typeof detail === 'string') {
            msg = detail;
          } else if (Array.isArray(detail)) {
            msg = detail.map((d: Record<string, unknown>) => {
              const field = Array.isArray(d.loc) ? (d.loc as string[]).slice(-1)[0] : '';
              return field ? `${field}: ${d.msg}` : String(d.msg || '');
            }).join(' / ');
          } else if (status) {
            msg = `서버 오류 (${status}): ${role === 'seller' ? '판매자' : '액추에이터'} 가입에 실패했어요.`;
          } else {
            msg = '네트워크 오류: 서버에 연결할 수 없어요.';
          }
          setApiError(msg);
        } finally {
          setRegistering(false);
        }
        return;
      }
      goTo(6);
    }
  };

  const goBack = () => {
    if (step === 1) navigate('/login');
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
          <button onClick={goBack} style={{ fontSize: 14, color: C.textSec, cursor: 'pointer', padding: '6px 2px', background: 'none', border: 'none' }}>
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
            {step === 1 && (
              <RoleStep
                role={role}
                onSelect={r => setRole(r)}
                onNext={() => { void goNext(); }}
              />
            )}
            {step === 2 && (
              <ProfileStep
                nickname={nickname} setNickname={setNickname}
                nickStatus={nickStatus} nickMsg={nickMsg}
                recommender={recommender} setRecommender={setRecommender}
                role={role}
                email={email} setEmail={setEmail}
                emailStatus={emailStatus} emailMsg={emailMsg}
                password={password} setPassword={setPassword}
                passwordConfirm={passwordConfirm} setPasswordConfirm={setPasswordConfirm}
                showPw={showPw} setShowPw={setShowPw}
                showPwConfirm={showPwConfirm} setShowPwConfirm={setShowPwConfirm}
                pwError={pwError} pwConfirmError={pwConfirmError}
                apiError={apiError}
                onNext={() => { void goNext(); }}
              />
            )}
            {step === 3 && (
              <ExtraInfoStep
                phone={phone} setPhone={setPhone}
                phoneStatus={phoneStatus} phoneMsg={phoneMsg}
                companyPhone={companyPhone} setCompanyPhone={setCompanyPhone}
                address={address} setAddress={setAddress}
                zipCode={zipCode} setZipCode={setZipCode}
                addressDetail={addressDetail} setAddressDetail={setAddressDetail}
                shippingAddr={shippingAddr} setShippingAddr={setShippingAddr}
                shippingZip={shippingZip} setShippingZip={setShippingZip}
                shippingDetail={shippingDetail} setShippingDetail={setShippingDetail}
                sameAsAddr={sameAsAddr} setSameAsAddr={setSameAsAddr}
                gender={gender} setGender={setGender}
                birthYear={birthYear} setBirthYear={setBirthYear}
                birthMonth={birthMonth} setBirthMonth={setBirthMonth}
                birthDay={birthDay} setBirthDay={setBirthDay}
                birthError={birthError}
                paymentMethod={paymentMethod} setPaymentMethod={setPaymentMethod}
                role={role}
                onNext={() => { void goNext(); }}
              />
            )}
            {step === 4 && (
              <div>
                <TermsStep
                  termsAgreed={termsAgreed} setTermsAgreed={setTermsAgreed}
                  privacyAgreed={privacyAgreed} setPrivacyAgreed={setPrivacyAgreed}
                  marketingAgreed={marketingAgreed} setMarketingAgreed={setMarketingAgreed}
                  sellerTermsAgreed={sellerTermsAgreed} setSellerTermsAgreed={setSellerTermsAgreed}
                  ecommerceTermsAgreed={ecommerceTermsAgreed} setEcommerceTermsAgreed={setEcommerceTermsAgreed}
                  role={role}
                  onNext={() => { void goNext(); }}
                />
                {apiError && (
                  <div style={{ padding: '0 24px 20px', marginTop: -16 }}>
                    <div style={{ fontSize: 12, color: C.red, padding: '10px 14px', borderRadius: 10, background: 'rgba(255,82,82,0.08)', border: '1px solid rgba(255,82,82,0.25)' }}>
                      {apiError}
                    </div>
                  </div>
                )}
                {registering && (
                  <div style={{ textAlign: 'center', padding: '0 24px 20px', fontSize: 13, color: C.textSec }}>가입 처리 중...</div>
                )}
              </div>
            )}
            {step === 5 && (
              <div>
                <BizStep
                  role={role}
                  bizName={bizName} setBizName={setBizName}
                  bizNum={bizNum} setBizNum={setBizNum}
                  ceoName={ceoName} setCeoName={setCeoName}
                  bankName={bankName} setBankName={setBankName}
                  accountNum={accountNum} setAccountNum={setAccountNum}
                  accountHolder={accountHolder} setAccountHolder={setAccountHolder}
                  actuatorCode={actuatorCode} setActuatorCode={setActuatorCode}
                  actuatorVerified={actuatorVerified} setActuatorVerified={setActuatorVerified} setActuatorResolvedId={setActuatorResolvedId}
                  fromRef={fromRef}
                  bizLicenseUrl={bizLicenseUrl} setBizLicenseUrl={setBizLicenseUrl}
                  ecommercePermitUrl={ecommercePermitUrl} setEcommercePermitUrl={setEcommercePermitUrl}
                  bankbookUrl={bankbookUrl} setBankbookUrl={setBankbookUrl}
                  actIsBusiness={actIsBusiness} setActIsBusiness={setActIsBusiness}
                  actBizName={actBizName} setActBizName={setActBizName}
                  actBizNum={actBizNum} setActBizNum={setActBizNum}
                  actEcommerceNum={actEcommerceNum} setActEcommerceNum={setActEcommerceNum}
                  actBizAddress={actBizAddress} setActBizAddress={setActBizAddress}
                  actBizZipCode={actBizZipCode} setActBizZipCode={setActBizZipCode}
                  actBizAddressDetail={actBizAddressDetail} setActBizAddressDetail={setActBizAddressDetail}
                  actCompanyPhone={actCompanyPhone} setActCompanyPhone={setActCompanyPhone}
                  actBizLicenseUrl={actBizLicenseUrl} setActBizLicenseUrl={setActBizLicenseUrl}
                  actEcommercePermitUrl={actEcommercePermitUrl} setActEcommercePermitUrl={setActEcommercePermitUrl}
                  externalRatings={externalRatings} setExternalRatings={setExternalRatings}
                  onNext={() => { void goNext(); }}
                />
                {apiError && (
                  <div style={{ padding: '0 24px 20px', marginTop: -16 }}>
                    <div style={{ fontSize: 12, color: C.red, padding: '10px 14px', borderRadius: 10, background: 'rgba(255,82,82,0.08)', border: '1px solid rgba(255,82,82,0.25)' }}>
                      {apiError}
                    </div>
                  </div>
                )}
                {registering && (
                  <div style={{ textAlign: 'center', padding: '0 24px 20px', fontSize: 13, color: C.textSec }}>가입 처리 중...</div>
                )}
              </div>
            )}
            {step === 6 && (
              <CompleteStep
                method={method}
                role={role}
                nickname={nickname}
                email={email}
                password={password}
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
