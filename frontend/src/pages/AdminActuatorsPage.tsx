import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  green: '#00e676', orange: '#ff9100', red: '#ff5252', cyan: '#00e5ff',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)', textDim: '#546e7a',
  bgInput: 'rgba(255,255,255,0.06)',
};

const STATUS_STYLE: Record<string, { bg: string; color: string }> = {
  ACTIVE:    { bg: 'rgba(0,230,118,0.1)',  color: C.green },
  SUSPENDED: { bg: 'rgba(255,145,0,0.1)',  color: C.orange },
  CLOSED:    { bg: 'rgba(255,82,82,0.1)',  color: C.red },
};

interface Actuator {
  id: number;
  name?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  password_hash?: string;
  status?: string;
  bank_name?: string;
  account_number?: string;
  account_holder?: string;
  bankbook_image?: string;
  is_business?: boolean;
  business_name?: string;
  business_number?: string;
  ecommerce_permit_number?: string;
  business_address?: string;
  business_zip_code?: string;
  company_phone?: string;
  business_license_image?: string;
  ecommerce_permit_image?: string;
  created_at?: string;
}

function Row({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div style={{ display: 'flex', padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
      <span style={{ width: 130, flexShrink: 0, fontSize: 12, fontWeight: 600, color: C.textSec }}>{label}</span>
      <span style={{ fontSize: 13, color: C.text, wordBreak: 'break-all' }}>{value ?? '-'}</span>
    </div>
  );
}

function DocPreview({ label, src }: { label: string; src?: string | null }) {
  if (!src) return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 12, color: C.red }}>미첨부</div>
    </div>
  );
  const isImage = src.startsWith('data:image/');
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: C.textSec, marginBottom: 6 }}>{label}</div>
      {isImage ? (
        <img src={src} alt={label} style={{ maxWidth: '100%', maxHeight: 200, borderRadius: 10, border: `1px solid ${C.border}` }} />
      ) : src.startsWith('data:application/pdf') ? (
        <div style={{ fontSize: 12, color: C.cyan }}>PDF 첨부됨</div>
      ) : (
        <a href={src} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: C.cyan }}>파일 보기</a>
      )}
    </div>
  );
}

export default function AdminActuatorsPage() {
  const [actuators, setActuators] = useState<Actuator[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Actuator | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.get(API.ACTUATORS.LIST);
        setActuators(Array.isArray(res.data) ? res.data : []);
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, []);

  return (
    <div style={{ padding: '24px 16px', maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>액추에이터 관리</h1>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 20 }}>총 {actuators.length}명</div>

      {loading ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>로딩 중...</div>
      ) : actuators.length === 0 ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>액추에이터가 없습니다.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {actuators.map(a => {
            const st = STATUS_STYLE[a.status || 'ACTIVE'] || STATUS_STYLE.ACTIVE;
            return (
              <div key={a.id} onClick={() => setSelected(a)} style={{
                background: C.card, border: `1px solid ${C.border}`, borderRadius: 14,
                padding: '16px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                cursor: 'pointer',
              }}>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 4 }}>
                    #{a.id} {a.name || a.nickname || '(이름 없음)'}
                    {a.is_business && <span style={{ fontSize: 11, color: C.orange, marginLeft: 8 }}>사업자</span>}
                  </div>
                  <div style={{ fontSize: 12, color: C.textSec }}>
                    {a.email} · {a.phone || '-'}
                    {a.business_name && ` · ${a.business_name}`}
                  </div>
                  <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                    가입: {a.created_at ? new Date(a.created_at).toLocaleDateString('ko-KR') : '-'}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                  <span style={{ padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: st.bg, color: st.color }}>
                    {a.status || 'ACTIVE'}
                  </span>
                  <span style={{ fontSize: 13, color: C.textDim }}>→</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 상세 모달 */}
      {selected && (
        <>
          <div onClick={() => setSelected(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)', zIndex: 3000 }} />
          <div style={{
            position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
            width: '94%', maxWidth: 520, maxHeight: '85vh', overflowY: 'auto',
            background: 'var(--bg-secondary)', border: `1px solid ${C.border}`,
            borderRadius: 20, padding: '28px 24px', zIndex: 3001,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color: C.text }}>액추에이터 상세</div>
                <div style={{ fontSize: 12, color: C.textSec }}>#{selected.id}</div>
              </div>
              <button onClick={() => setSelected(null)} style={{
                width: 32, height: 32, borderRadius: '50%', background: C.bgInput,
                color: C.textSec, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>✕</button>
            </div>

            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>기본 정보</div>
              <Row label="ID" value={selected.id} />
              <Row label="이름" value={selected.name} />
              <Row label="닉네임" value={selected.nickname} />
              <Row label="이메일 (ID)" value={selected.email} />
              <Row label="비밀번호" value={selected.password_hash ? '설정됨 (해시)' : '미설정'} />
              <Row label="전화번호" value={selected.phone} />
              <Row label="상태" value={selected.status || 'ACTIVE'} />
              <Row label="유형" value={selected.is_business ? '사업자' : '개인'} />
              <Row label="가입일" value={selected.created_at ? new Date(selected.created_at).toLocaleString('ko-KR') : '-'} />
            </div>

            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>정산 계좌</div>
              <Row label="은행명" value={selected.bank_name} />
              <Row label="계좌번호" value={selected.account_number} />
              <Row label="예금주" value={selected.account_holder} />
            </div>

            {selected.is_business && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>사업자 정보</div>
                <Row label="상호명" value={selected.business_name} />
                <Row label="사업자번호" value={selected.business_number} />
                <Row label="통신판매업번호" value={selected.ecommerce_permit_number} />
                <Row label="주소" value={selected.business_address ? `[${selected.business_zip_code || ''}] ${selected.business_address}` : '-'} />
                <Row label="회사 전화번호" value={selected.company_phone} />
              </div>
            )}

            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 10 }}>첨부 서류</div>
              <DocPreview label="통장사본" src={selected.bankbook_image} />
              {selected.is_business && (
                <>
                  <DocPreview label="사업자등록증" src={selected.business_license_image} />
                  <DocPreview label="통신판매업신고증" src={selected.ecommerce_permit_image} />
                </>
              )}
            </div>

            <button onClick={() => setSelected(null)} style={{
              width: '100%', padding: '14px', borderRadius: 12, fontSize: 14, fontWeight: 700,
              background: C.bgInput, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer',
            }}>닫기</button>
          </div>
        </>
      )}
    </div>
  );
}
