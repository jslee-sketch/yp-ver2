import { useState, useEffect } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';

const C = {
  green: '#00e676', cyan: '#00e5ff', red: '#ff5252',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)', textDim: '#546e7a',
  bgInput: 'rgba(255,255,255,0.06)',
};

interface Buyer {
  id: number;
  name?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  level?: number;
  points?: number;
  trust_tier?: string;
  address?: string;
  zip_code?: string;
  gender?: string;
  birth_date?: string;
  payment_method?: string;
  created_at?: string;
  password_hash?: string;
}

function Row({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div style={{ display: 'flex', padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
      <span style={{ width: 110, flexShrink: 0, fontSize: 12, fontWeight: 600, color: C.textSec }}>{label}</span>
      <span style={{ fontSize: 13, color: C.text, wordBreak: 'break-all' }}>{value ?? '-'}</span>
    </div>
  );
}

export default function AdminBuyersPage() {
  const [buyers, setBuyers] = useState<Buyer[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Buyer | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.get(API.BUYERS.LIST);
        setBuyers(Array.isArray(res.data) ? res.data : []);
      } catch { /* ignore */ }
      setLoading(false);
    })();
  }, []);

  return (
    <div style={{ padding: '24px 16px', maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>구매자 관리</h1>
      <div style={{ fontSize: 13, color: C.textSec, marginBottom: 20 }}>총 {buyers.length}명</div>

      {loading ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>로딩 중...</div>
      ) : buyers.length === 0 ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>구매자가 없습니다.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {buyers.map(b => (
            <div key={b.id} onClick={() => setSelected(b)} style={{
              background: C.card, border: `1px solid ${C.border}`, borderRadius: 14,
              padding: '16px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              cursor: 'pointer',
            }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 4 }}>
                  #{b.id} {b.name || b.nickname || '(이름 없음)'}
                  {b.nickname && <span style={{ fontSize: 12, color: C.textSec, marginLeft: 6 }}>@{b.nickname}</span>}
                </div>
                <div style={{ fontSize: 12, color: C.textSec }}>
                  {b.email} · {b.phone || '-'}
                </div>
                <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                  가입: {b.created_at ? new Date(b.created_at).toLocaleDateString('ko-KR') : '-'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexShrink: 0, alignItems: 'center' }}>
                <span style={{ padding: '4px 10px', borderRadius: 8, fontSize: 11, fontWeight: 700, background: 'rgba(0,176,255,0.08)', color: '#00b0ff' }}>Lv.{b.level ?? 1}</span>
                <span style={{ padding: '4px 10px', borderRadius: 8, fontSize: 11, fontWeight: 700, background: 'rgba(0,230,118,0.08)', color: '#00e676' }}>{(b.points ?? 0).toLocaleString()}P</span>
                <span style={{ padding: '4px 10px', borderRadius: 8, fontSize: 11, fontWeight: 700, background: 'rgba(192,192,192,0.08)', color: '#c0c0c0' }}>{b.trust_tier || 'Bronze'}</span>
                <span style={{ fontSize: 13, color: C.textDim }}>→</span>
              </div>
            </div>
          ))}
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
                <div style={{ fontSize: 18, fontWeight: 800, color: C.text }}>구매자 상세</div>
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
              <Row label="가입일" value={selected.created_at ? new Date(selected.created_at).toLocaleString('ko-KR') : '-'} />
            </div>

            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>활동 정보</div>
              <Row label="레벨" value={`Lv.${selected.level ?? 1}`} />
              <Row label="포인트" value={`${(selected.points ?? 0).toLocaleString()}P`} />
              <Row label="신뢰등급" value={selected.trust_tier || 'Bronze'} />
            </div>

            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>추가 정보</div>
              <Row label="주소" value={selected.address ? `[${selected.zip_code || ''}] ${selected.address}` : '-'} />
              <Row label="성별" value={selected.gender || '-'} />
              <Row label="생년월일" value={selected.birth_date || '-'} />
              <Row label="결제수단" value={selected.payment_method || '-'} />
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
