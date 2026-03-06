import { useState, useEffect, useCallback } from 'react';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { showToast } from '../components/common/Toast';

const C = {
  green: '#00e676', orange: '#ff9100', red: '#ff5252', cyan: '#00e5ff',
  card: 'var(--bg-elevated)', border: 'var(--border-subtle)',
  text: 'var(--text-primary)', textSec: 'var(--text-muted)', textDim: '#546e7a',
  bgInput: 'rgba(255,255,255,0.06)',
};

interface Seller {
  id: number;
  name?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  company_phone?: string;
  business_name?: string;
  business_number?: string;
  address?: string;
  zip_code?: string;
  verified_at?: string | null;
  created_at?: string;
  actuator_id?: number | null;
  bank_name?: string;
  account_number?: string;
  account_holder?: string;
  business_license_image?: string | null;
  ecommerce_permit_image?: string | null;
  bankbook_image?: string | null;
  external_ratings?: string | null;
}

/* ── 검증 모달 내 정보 행 ── */
function Row({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div style={{ display: 'flex', padding: '8px 0', borderBottom: `1px solid ${C.border}` }}>
      <span style={{ width: 120, flexShrink: 0, fontSize: 12, fontWeight: 600, color: C.textSec }}>{label}</span>
      <span style={{ fontSize: 13, color: C.text, wordBreak: 'break-all' }}>{value ?? '-'}</span>
    </div>
  );
}

/* ── 이미지/PDF 미리보기 ── */
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
        <div style={{ fontSize: 12, color: C.cyan }}>📄 PDF 첨부됨 (base64)</div>
      ) : (
        <a href={src} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: C.cyan }}>📎 파일 보기</a>
      )}
    </div>
  );
}

export default function AdminSellersPage() {
  const [sellers, setSellers] = useState<Seller[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'pending' | 'all'>('pending');
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const [selected, setSelected] = useState<Seller | null>(null);

  const fetchSellers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get(API.SELLERS.LIST, { params: { limit: 1000 } });
      setSellers(Array.isArray(res.data) ? res.data : []);
    } catch {
      showToast('판매자 목록 로드 실패', 'error');
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchSellers(); }, [fetchSellers]);

  const handleApprove = async (id: number) => {
    setApprovingId(id);
    try {
      await apiClient.post(API.SELLERS.VERIFY(id));
      showToast('판매자 승인 완료', 'success');
      setSelected(null);
      fetchSellers();
    } catch {
      showToast('승인 실패', 'error');
    }
    setApprovingId(null);
  };

  const filtered = tab === 'pending'
    ? sellers.filter(s => !s.verified_at)
    : sellers;

  // 외부 평점 파싱
  const parseRatings = (raw?: string | null) => {
    if (!raw) return [];
    try { return JSON.parse(raw) as { platform: string; score: string; maxScore: string }[]; } catch { return []; }
  };

  return (
    <div style={{ padding: '24px 16px', maxWidth: 900, margin: '0 auto' }}>
      <h1 style={{ fontSize: 22, fontWeight: 800, color: C.text, marginBottom: 16 }}>판매자 관리</h1>

      {/* 탭 */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {(['pending', 'all'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 20px', borderRadius: 10, fontSize: 13, fontWeight: 700, cursor: 'pointer',
            background: tab === t ? C.green : 'var(--bg-elevated)',
            color: tab === t ? '#0a0a0f' : C.textSec,
            border: `1px solid ${tab === t ? C.green : C.border}`,
          }}>
            {t === 'pending' ? `승인 대기 (${sellers.filter(s => !s.verified_at).length})` : `전체 (${sellers.length})`}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>로딩 중...</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', color: C.textSec, padding: 40 }}>
          {tab === 'pending' ? '승인 대기 중인 판매자가 없습니다.' : '판매자가 없습니다.'}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(s => (
            <div key={s.id} style={{
              background: C.card, border: `1px solid ${C.border}`, borderRadius: 14,
              padding: '16px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              cursor: 'pointer',
            }} onClick={() => setSelected(s)}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 700, color: C.text, marginBottom: 4 }}>
                  #{s.id} {s.business_name || s.name || s.nickname || '(이름 없음)'}
                </div>
                <div style={{ fontSize: 12, color: C.textSec }}>
                  {s.email} · {s.phone || '-'} · 사업자번호: {s.business_number || '-'}
                </div>
                <div style={{ fontSize: 11, color: C.textSec, marginTop: 2 }}>
                  가입: {s.created_at ? new Date(s.created_at).toLocaleDateString('ko-KR') : '-'}
                  {s.verified_at && ` · 승인: ${new Date(s.verified_at).toLocaleDateString('ko-KR')}`}
                </div>
              </div>
              <div style={{ flexShrink: 0, marginLeft: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
                {s.verified_at ? (
                  <span style={{ padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(0,230,118,0.1)', color: C.green }}>승인됨</span>
                ) : (
                  <span style={{ padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: 'rgba(255,145,0,0.1)', color: C.orange }}>대기</span>
                )}
                <span style={{ fontSize: 13, color: C.textDim }}>→</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── 검증 모달 ── */}
      {selected && (
        <>
          <div onClick={() => setSelected(null)} style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)', zIndex: 3000,
          }} />
          <div style={{
            position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
            width: '94%', maxWidth: 520, maxHeight: '85vh', overflowY: 'auto',
            background: 'var(--bg-secondary)', border: `1px solid ${C.border}`,
            borderRadius: 20, padding: '28px 24px', zIndex: 3001,
          }}>
            {/* 헤더 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color: C.text }}>판매자 검증</div>
                <div style={{ fontSize: 12, color: C.textSec }}>등록 정보를 확인 후 승인해주세요</div>
              </div>
              <button onClick={() => setSelected(null)} style={{
                width: 32, height: 32, borderRadius: '50%', background: C.bgInput,
                color: C.textSec, fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>✕</button>
            </div>

            {/* 기본 정보 */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>기본 정보</div>
              <Row label="ID" value={selected.id} />
              <Row label="닉네임" value={selected.nickname} />
              <Row label="이메일" value={selected.email} />
              <Row label="전화번호" value={selected.phone} />
              <Row label="회사 전화번호" value={selected.company_phone} />
              <Row label="가입일" value={selected.created_at ? new Date(selected.created_at).toLocaleString('ko-KR') : '-'} />
              <Row label="승인 상태" value={selected.verified_at ? `승인됨 (${new Date(selected.verified_at).toLocaleDateString('ko-KR')})` : '미승인'} />
            </div>

            {/* 사업자 정보 */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>사업자 정보</div>
              <Row label="상호명" value={selected.business_name} />
              <Row label="사업자번호" value={selected.business_number} />
              <Row label="주소" value={selected.address ? `[${selected.zip_code || ''}] ${selected.address}` : '-'} />
              <Row label="액추에이터 ID" value={selected.actuator_id} />
            </div>

            {/* 정산 계좌 */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>정산 계좌</div>
              <Row label="은행명" value={selected.bank_name} />
              <Row label="계좌번호" value={selected.account_number} />
              <Row label="예금주" value={selected.account_holder} />
            </div>

            {/* 서류 확인 */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 10 }}>첨부 서류</div>
              <DocPreview label="사업자등록증" src={selected.business_license_image} />
              <DocPreview label="통신판매업신고증" src={selected.ecommerce_permit_image} />
              <DocPreview label="통장사본" src={selected.bankbook_image} />
            </div>

            {/* 외부 평점 */}
            {selected.external_ratings && parseRatings(selected.external_ratings).length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: C.cyan, marginBottom: 8 }}>외부 평점</div>
                {parseRatings(selected.external_ratings).map((r, i) => (
                  <Row key={i} label={r.platform || `플랫폼 ${i + 1}`} value={r.score && r.maxScore ? `${r.score} / ${r.maxScore}` : '-'} />
                ))}
              </div>
            )}

            {/* 하단 버튼 */}
            <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
              <button onClick={() => setSelected(null)} style={{
                flex: 1, padding: '14px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                background: C.bgInput, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer',
              }}>닫기</button>
              {!selected.verified_at && (
                <button
                  onClick={() => handleApprove(selected.id)}
                  disabled={approvingId === selected.id}
                  style={{
                    flex: 1, padding: '14px', borderRadius: 12, fontSize: 14, fontWeight: 700,
                    background: approvingId === selected.id ? `${C.green}55` : C.green,
                    border: 'none', color: '#0a0a0f',
                    cursor: approvingId === selected.id ? 'not-allowed' : 'pointer',
                  }}
                >
                  {approvingId === selected.id ? '처리중...' : '승인하기'}
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
