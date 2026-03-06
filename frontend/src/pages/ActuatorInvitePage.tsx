import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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

interface InvitedSeller {
  seller_id: number;
  name?: string;
  business_name?: string;
  verified_at?: string;
  created_at?: string;
}

export default function ActuatorInvitePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [sellers, setSellers] = useState<InvitedSeller[]>([]);
  const [loading, setLoading] = useState(true);

  const actuatorId = user?.id ?? 0;
  const refCode = `ACT-${actuatorId}`;
  const inviteLink = `${window.location.origin}/register?ref=${refCode}`;

  useEffect(() => {
    if (!actuatorId) return;
    (async () => {
      try {
        const res = await apiClient.get(API.ACTUATORS.SELLERS(actuatorId));
        const data = res.data;
        setSellers(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error('초대 현황 로드 실패:', err);
      } finally {
        setLoading(false);
      }
    })();
  }, [actuatorId]);

  const copyToClipboard = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast(`${label} 복사 완료!`, 'success');
    } catch {
      showToast('복사 실패', 'error');
    }
  };

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>판매자 초대</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        {/* 추천 코드 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: 14,
          padding: 18, marginBottom: 12, textAlign: 'center',
        }}>
          <div style={{ fontSize: 12, color: C.textDim, marginBottom: 6 }}>내 추천 코드</div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 14 }}>
            <span style={{ fontSize: 22, fontWeight: 800, color: C.green, letterSpacing: 2 }}>{refCode}</span>
            <button onClick={() => void copyToClipboard(refCode, '추천 코드')}
              style={{
                padding: '6px 12px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                background: `${C.green}22`, border: `1px solid ${C.green}44`, color: C.green, cursor: 'pointer',
              }}>
              복사
            </button>
          </div>
          <div style={{ fontSize: 12, color: C.textDim, marginBottom: 8 }}>초대 링크</div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            background: C.bgEl, border: `1px solid ${C.border}`, borderRadius: 10,
            padding: '10px 14px',
          }}>
            <span style={{ fontSize: 11, color: C.textSec, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {inviteLink}
            </span>
            <button onClick={() => void copyToClipboard(inviteLink, '초대 링크')}
              style={{
                padding: '5px 10px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                background: `${C.green}22`, border: `1px solid ${C.green}44`, color: C.green,
                cursor: 'pointer', flexShrink: 0,
              }}>
              복사
            </button>
          </div>
        </div>

        {/* 안내 */}
        <div style={{
          background: 'rgba(0,176,255,0.06)', border: '1px solid rgba(0,176,255,0.15)',
          borderRadius: 12, padding: 14, marginBottom: 16, fontSize: 12, color: C.textSec, lineHeight: 1.6,
        }}>
          판매자 회원가입 시 추천 코드를 입력하면 자동으로 연결됩니다.
          연결된 판매자의 거래에서 커미션이 발생합니다.
        </div>

        {/* 초대 현황 */}
        <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 10 }}>
          초대 현황 ({sellers.length}명)
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>불러오는 중...</div>
        ) : sellers.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: C.textDim }}>
            <div style={{ fontSize: 40, marginBottom: 8 }}>📢</div>
            <div style={{ fontSize: 13 }}>아직 초대한 판매자가 없어요</div>
            <div style={{ fontSize: 11, color: C.textDim, marginTop: 4 }}>추천 코드를 공유해 판매자를 초대해보세요</div>
          </div>
        ) : sellers.map(s => (
          <div key={s.seller_id} style={{
            background: C.bgCard, border: `1px solid ${C.border}`,
            borderLeft: `3px solid ${s.verified_at ? C.green : C.orange}`,
            borderRadius: 14, padding: 14, marginBottom: 8,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 2 }}>
                  {s.business_name || s.name || `판매자 #${s.seller_id}`}
                </div>
                <div style={{ fontSize: 11, color: C.textDim }}>
                  {s.created_at ? fmtDate(s.created_at) + ' 가입' : ''}
                </div>
              </div>
              <span style={{
                fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 6,
                background: s.verified_at ? `${C.green}22` : `${C.orange}22`,
                color: s.verified_at ? C.green : C.orange,
              }}>
                {s.verified_at ? '승인완료' : '가입대기'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
