import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)', bgEl: 'var(--bg-elevated)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)', cyan: '#00e5ff',
  orange: 'var(--accent-orange)',
};

const FAQ_ITEMS = [
  { q: '딜은 어떻게 만드나요?', a: '홈 화면에서 "딜 만들기" 버튼을 누르고, 원하는 상품명과 희망 가격을 입력하면 딜이 생성됩니다. 다른 구매자들이 참여하면 공동구매 효과로 더 좋은 가격을 받을 수 있어요.' },
  { q: '결제는 언제 하나요?', a: '셀러가 오퍼를 제출하고 마감되면, 결제 시간이 주어집니다. 결제 시간은 기본 5분이므로, 미리 결제수단을 등록해두세요.' },
  { q: '환불은 어떻게 되나요?', a: '결제 전 취소는 언제든 가능합니다. 결제 후에는 배송 전까지 취소 가능하며, 배송 후에는 상품 수령 7일 이내에 환불 요청이 가능합니다.' },
  { q: '관전 모드는 뭔가요?', a: '딜의 최종 체결 가격을 예측하는 기능입니다. 예측이 적중하면 포인트를 받을 수 있어요!' },
  { q: '판매자 등록은 어떻게 하나요?', a: '설정 > 판매자 등록에서 사업자 정보를 입력하면 판매자로 등록할 수 있습니다. 인증 후 오퍼를 제출할 수 있어요.' },
  { q: '포인트는 어디에 쓰나요?', a: '적립된 포인트는 다음 결제 시 할인으로 사용하거나, 특별 이벤트에 참여할 때 사용할 수 있습니다.' },
];

export default function SupportPage() {
  const navigate = useNavigate();
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>고객센터</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>

        {/* 핑퐁이 상담 */}
        <div style={{
          background: C.bgCard, border: `1px solid rgba(255,183,77,0.25)`,
          borderLeft: `3px solid ${C.orange}`,
          borderRadius: 16, padding: '16px 18px', marginBottom: 16,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{ fontSize: 28 }}>🤖</span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: C.orange }}>핑퐁이에게 물어보세요</div>
              <div style={{ fontSize: 11, color: C.textDim }}>AI 상담원이 24시간 대기 중이에요</div>
            </div>
          </div>
          <div style={{ fontSize: 12, color: C.textSec, lineHeight: 1.6, marginBottom: 12 }}>
            정책, 가격, 딜 관련 궁금한 점을 자연어로 물어보세요. 화면 우측 하단의 핑퐁이 버튼을 눌러도 됩니다.
          </div>
        </div>

        {/* FAQ */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 16, padding: '4px 0', marginBottom: 16,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, padding: '14px 18px 8px' }}>
            자주 묻는 질문
          </div>

          {FAQ_ITEMS.map((item, i) => {
            const isOpen = expandedIdx === i;
            return (
              <div key={i}>
                <button
                  onClick={() => setExpandedIdx(isOpen ? null : i)}
                  style={{
                    width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '12px 18px', background: 'none', border: 'none', cursor: 'pointer',
                    borderTop: i > 0 ? `1px solid ${C.border}` : 'none',
                  }}
                >
                  <span style={{ fontSize: 13, color: C.text, textAlign: 'left' }}>{item.q}</span>
                  <span style={{ fontSize: 14, color: C.textDim, flexShrink: 0, marginLeft: 8 }}>
                    {isOpen ? '▲' : '▼'}
                  </span>
                </button>
                {isOpen && (
                  <div style={{
                    padding: '0 18px 14px',
                    fontSize: 12, color: C.textSec, lineHeight: 1.7,
                  }}>
                    {item.a}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* 연락처 */}
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 16, padding: '16px 18px',
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: C.textDim, letterSpacing: 1, marginBottom: 10 }}>
            직접 문의
          </div>
          <div style={{ fontSize: 12, color: C.textSec, lineHeight: 1.8 }}>
            이메일: support@yeokping.com<br />
            운영시간: 평일 10:00~18:00
          </div>
        </div>
      </div>
    </div>
  );
}
