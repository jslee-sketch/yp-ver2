import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { trackBehavior } from '../utils/behaviorTracker';
import { useAuth } from '../contexts/AuthContext';
import apiClient from '../api/client';
import { API } from '../api/endpoints';
import { showToast } from '../components/common/Toast';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

function fmtDate(s?: string) { return (s ?? '').split('T')[0].replace(/-/g, '.'); }

interface Inquiry {
  id: number;
  seller_id: number;
  buyer_id: number;
  reservation_id?: number;
  category: string;
  title: string;
  content: string;
  status: string;
  seller_reply?: string;
  replied_at?: string;
  created_at: string;
}

const CATEGORY_LABEL: Record<string, { label: string; color: string }> = {
  general:  { label: '일반',   color: '#78909c' },
  shipping: { label: '배송',   color: '#00b0ff' },
  refund:   { label: '환불',   color: '#ff5252' },
  product:  { label: '상품',   color: '#ff9100' },
};

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  open:     { label: '미답변', color: '#ff9100' },
  answered: { label: '답변완료', color: '#00e676' },
  closed:   { label: '닫힘', color: '#78909c' },
};

type FilterKey = '전체' | 'open' | 'answered' | 'closed';

export default function SellerInquiriesPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const sellerId = user?.seller?.id ?? user?.id ?? 0;

  const [items, setItems] = useState<Inquiry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterKey>('전체');

  // Reply modal
  const [replyTarget, setReplyTarget] = useState<Inquiry | null>(null);
  const [replyText, setReplyText] = useState('');
  const [replySaving, setReplySaving] = useState(false);

  useEffect(() => {
    if (!sellerId) return;
    (async () => {
      try {
        const res = await apiClient.get(API.CUSTOMER_INQUIRIES.LIST_SELLER(sellerId));
        setItems(Array.isArray(res.data) ? res.data : []);
      } catch (err) {
        console.error('문의 목록 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [sellerId]);

  const filtered = filter === '전체' ? items : items.filter(i => i.status === filter);

  const handleReply = async () => {
    if (!replyTarget || !replyText.trim()) return;
    setReplySaving(true);
    try {
      await apiClient.post(API.CUSTOMER_INQUIRIES.REPLY(replyTarget.id), {
        comment: replyText.trim(),
      });
      setItems(prev => prev.map(i => i.id === replyTarget.id
        ? { ...i, status: 'answered', seller_reply: replyText.trim(), replied_at: new Date().toISOString() }
        : i));
      setReplyTarget(null);
      setReplyText('');
      trackBehavior('SELLER_REPLY_INQUIRY', { target_type: 'inquiry', target_id: replyTarget.id });
      showToast('답변 등록 완료', 'success');
    } catch {
      showToast('답변 등록 실패', 'error');
    }
    setReplySaving(false);
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>고객 문의</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0', maxWidth: 1200, margin: '0 auto' }}>
        {/* 필터 */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14 }}>
          {([
            { key: '전체' as FilterKey, label: '전체' },
            { key: 'open' as FilterKey, label: '미답변' },
            { key: 'answered' as FilterKey, label: '답변완료' },
            { key: 'closed' as FilterKey, label: '닫힘' },
          ]).map(s => (
            <button key={s.key} onClick={() => setFilter(s.key)} style={{
              padding: '6px 12px', borderRadius: 20, fontSize: 12, cursor: 'pointer',
              background: filter === s.key ? `${C.green}22` : C.bgEl,
              border: `1px solid ${filter === s.key ? C.green : C.border}`,
              color: filter === s.key ? C.green : C.textSec,
              fontWeight: filter === s.key ? 700 : 400,
            }}>{s.label}</button>
          ))}
        </div>

        <div style={{ fontSize: 12, color: C.textDim, marginBottom: 10 }}>{filtered.length}건</div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>💬</div>
            <div style={{ fontSize: 13 }}>문의가 없어요</div>
          </div>
        ) : filtered.map(inq => {
          const cat = CATEGORY_LABEL[inq.category] ?? CATEGORY_LABEL.general;
          const st = STATUS_LABEL[inq.status] ?? STATUS_LABEL.open;
          return (
            <div key={inq.id} style={{
              background: C.bgCard, border: `1px solid ${C.border}`,
              borderLeft: `3px solid ${st.color}`,
              borderRadius: 14, padding: 14, marginBottom: 8,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4,
                    background: `${cat.color}22`, color: cat.color,
                  }}>{cat.label}</span>
                  <span style={{ fontSize: 12, color: C.textSec }}>구매자 #{inq.buyer_id}</span>
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                  background: `${st.color}22`, color: st.color,
                }}>{st.label}</span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 4 }}>{inq.title}</div>
              <div style={{ fontSize: 12, color: C.textSec, lineHeight: 1.5, marginBottom: 6 }}>{inq.content}</div>
              <div style={{ fontSize: 10, color: C.textDim, marginBottom: 6 }}>
                {inq.reservation_id ? `주문번호 #${inq.reservation_id} · ` : ''}{fmtDate(inq.created_at)}
              </div>

              {inq.seller_reply && (
                <div style={{
                  background: `${C.green}08`, border: `1px solid ${C.green}22`, borderRadius: 10,
                  padding: '10px 12px', marginBottom: 6,
                }}>
                  <div style={{ fontSize: 10, color: C.green, fontWeight: 700, marginBottom: 4 }}>판매자 답변</div>
                  <div style={{ fontSize: 12, color: C.text, lineHeight: 1.5 }}>{inq.seller_reply}</div>
                  {inq.replied_at && <div style={{ fontSize: 10, color: C.textDim, marginTop: 4 }}>{fmtDate(inq.replied_at)}</div>}
                </div>
              )}

              {inq.status === 'open' && (
                <button onClick={() => { setReplyTarget(inq); setReplyText(''); }}
                  style={{ marginTop: 4, padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, background: `${C.green}12`, border: `1px solid ${C.green}44`, color: C.green, cursor: 'pointer' }}>
                  답변하기
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* 답변 모달 */}
      {replyTarget && (
        <>
          <div onClick={() => setReplyTarget(null)} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 3000 }} />
          <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: '92%', maxWidth: 400, background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 20, padding: '24px 20px', zIndex: 3001 }}>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.text, marginBottom: 4 }}>답변 작성</div>
            <div style={{ fontSize: 12, color: C.textSec, marginBottom: 8 }}>{replyTarget.title}</div>
            <div style={{
              background: C.bgEl, border: `1px solid ${C.border}`, borderRadius: 10,
              padding: 12, fontSize: 12, color: C.textSec, marginBottom: 14, lineHeight: 1.5,
            }}>
              {replyTarget.content}
            </div>
            <textarea
              value={replyText} onChange={e => setReplyText(e.target.value)}
              placeholder="답변을 입력해주세요"
              rows={4}
              style={{ width: '100%', boxSizing: 'border-box', padding: '10px 14px', borderRadius: 10, fontSize: 13, background: C.bgEl, border: `1px solid ${C.border}`, color: C.text, resize: 'none', marginBottom: 16 }}
            />
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => setReplyTarget(null)} style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: C.bgEl, border: `1px solid ${C.border}`, color: C.textSec, cursor: 'pointer' }}>취소</button>
              <button disabled={replySaving || !replyText.trim()} onClick={() => void handleReply()}
                style={{ flex: 1, padding: '13px', borderRadius: 12, fontSize: 14, fontWeight: 700, background: replySaving ? `${C.green}55` : C.green, border: 'none', color: '#0a0a0f', cursor: replySaving || !replyText.trim() ? 'not-allowed' : 'pointer' }}>
                {replySaving ? '등록 중...' : '등록'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
