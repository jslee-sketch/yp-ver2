import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', orange: 'var(--accent-orange)',
};

const ANNOUNCEMENTS = [
  { id: 1, date: '2026.03.01', title: '판매자 ERP 시스템 오픈 안내', content: '판매자 전용 관리 시스템이 업데이트되었습니다. 대시보드, 정산 관리, 고객 문의 등 다양한 기능을 이용해보세요.' },
  { id: 2, date: '2026.02.15', title: '수수료 정책 업데이트', content: '2026년 3월부터 적용되는 새로운 등급별 수수료 정책을 안내합니다. 수수료 안내 메뉴에서 확인해주세요.' },
  { id: 3, date: '2026.02.01', title: '배송 정책 설정 기능 추가', content: '판매자별 기본 배송비, 반품비, 교환비를 설정할 수 있는 배송 정책 페이지가 추가되었습니다.' },
];

const FAQ = [
  { q: '정산은 언제 이루어지나요?', a: '구매자 수령확인 후 쿨링 기간(3영업일)이 지나면 정산 가능 상태(READY)가 됩니다. 관리자 승인 후 지급됩니다.' },
  { q: '환불 요청이 들어오면 어떻게 하나요?', a: '환불 관리 페이지에서 동의 또는 미동의를 선택할 수 있습니다. 미동의 시 분쟁으로 전환되어 관리자가 중재합니다.' },
  { q: '오퍼 가격을 수정할 수 있나요?', a: '판매가 시작되기 전(sold_qty = 0)에만 가격 수정이 가능합니다. 배송비와 리드타임은 언제든 수정할 수 있습니다.' },
  { q: '판매자 등급은 어떻게 결정되나요?', a: '누적 거래 수와 가중평균 평점을 기반으로 Lv.1(최고)~Lv.6(신규)으로 자동 산정됩니다.' },
  { q: '고객 문의에 답변하지 않으면 어떻게 되나요?', a: '48시간 이내 답변을 권장합니다. 미답변 문의가 많으면 판매자 평가에 영향을 줄 수 있습니다.' },
];

export default function SellerAnnouncementsPage() {
  const navigate = useNavigate();
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100, height: 56,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer' }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>공지/도움말</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0', maxWidth: 800, margin: '0 auto' }}>
        {/* 공지사항 */}
        <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 10 }}>공지사항</div>
        {ANNOUNCEMENTS.map(a => (
          <div key={a.id} style={{
            background: C.bgCard, border: `1px solid ${C.border}`,
            borderRadius: 14, padding: 14, marginBottom: 8,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{a.title}</span>
              <span style={{ fontSize: 10, color: C.textDim }}>{a.date}</span>
            </div>
            <div style={{ fontSize: 12, color: C.textSec, lineHeight: 1.5 }}>{a.content}</div>
          </div>
        ))}

        {/* FAQ */}
        <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 10, marginTop: 20 }}>자주 묻는 질문</div>
        {FAQ.map((faq, i) => (
          <div key={i} style={{
            background: C.bgCard, border: `1px solid ${C.border}`,
            borderRadius: 14, marginBottom: 8, overflow: 'hidden',
          }}>
            <button onClick={() => setOpenFaq(openFaq === i ? null : i)} style={{
              width: '100%', padding: '14px 14px', display: 'flex', justifyContent: 'space-between',
              alignItems: 'center', background: 'none', cursor: 'pointer',
            }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: C.text, textAlign: 'left' }}>{faq.q}</span>
              <span style={{ fontSize: 14, color: C.textDim, flexShrink: 0, marginLeft: 8 }}>
                {openFaq === i ? '▲' : '▼'}
              </span>
            </button>
            {openFaq === i && (
              <div style={{
                padding: '0 14px 14px',
                fontSize: 12, color: C.textSec, lineHeight: 1.6,
                borderTop: `1px solid ${C.border}`, paddingTop: 12,
              }}>
                {faq.a}
              </div>
            )}
          </div>
        ))}

        {/* 고객센터 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 14, padding: 16, marginTop: 20, textAlign: 'center',
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: C.text, marginBottom: 8 }}>고객센터</div>
          <div style={{ fontSize: 12, color: C.textSec, lineHeight: 1.8 }}>
            이메일: seller-support@yeokping.com<br />
            운영시간: 평일 09:00~18:00<br />
            카카오톡: @역핑셀러
          </div>
        </div>
      </div>
    </div>
  );
}
