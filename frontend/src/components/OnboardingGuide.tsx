import { useState } from 'react';

const BUYER_STEPS = [
  { icon: '🏓', title: '역핑에 오신 걸 환영합니다!', desc: '소비자가 가격을 제안하는\n새로운 쇼핑 경험을 시작하세요.' },
  { icon: '📝', title: '딜 만들기', desc: '원하는 상품의 희망 가격을 제안하세요.\nAI가 시장가를 분석해 드립니다.' },
  { icon: '📩', title: '오퍼 받기', desc: '판매자들이 경쟁 입찰합니다.\n가장 좋은 조건의 오퍼를 선택하세요.' },
  { icon: '🎉', title: '공동구매 시작!', desc: '다른 구매자와 함께 구매하면\n더 큰 할인을 받을 수 있어요.' },
];

const SELLER_STEPS = [
  { icon: '🏓', title: '판매자로 시작하세요!', desc: '역핑에서 새로운 고객을\n만나보세요.' },
  { icon: '🔔', title: '관심 상품 알림', desc: '판매 가능한 딜이 올라오면\n실시간으로 알려드려요.' },
  { icon: '💰', title: '오퍼 제출', desc: '경쟁력 있는 가격을 제시하고\n주문을 확보하세요.' },
  { icon: '📊', title: '정산 관리', desc: '배송 완료 후 자동 정산!\n대시보드에서 한눈에 확인하세요.' },
];

export default function OnboardingGuide({
  role = 'buyer',
  onComplete,
}: {
  role?: 'buyer' | 'seller';
  onComplete: () => void;
}) {
  const [step, setStep] = useState(0);
  const steps = role === 'seller' ? SELLER_STEPS : BUYER_STEPS;
  const current = steps[step];
  const isLast = step === steps.length - 1;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 10000,
      background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 24,
    }}>
      <div style={{
        background: '#1a1a2e', borderRadius: 20, padding: '40px 32px',
        maxWidth: 400, width: '100%', textAlign: 'center',
        border: '1px solid #2a2a4a',
      }}>
        {/* Progress dots */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginBottom: 24 }}>
          {steps.map((_, i) => (
            <div key={i} style={{
              width: i === step ? 24 : 8, height: 8, borderRadius: 4,
              background: i === step ? '#4ade80' : '#333',
              transition: 'all 0.3s',
            }} />
          ))}
        </div>

        <div style={{ fontSize: 64, marginBottom: 16 }}>{current.icon}</div>
        <h2 style={{ color: '#e0e0e0', fontSize: 20, fontWeight: 800, marginBottom: 12 }}>
          {current.title}
        </h2>
        <p style={{ color: '#888', fontSize: 14, lineHeight: 1.8, whiteSpace: 'pre-line', marginBottom: 32 }}>
          {current.desc}
        </p>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
          <button
            onClick={onComplete}
            style={{
              padding: '10px 20px', borderRadius: 10,
              border: '1px solid #333', background: 'transparent',
              color: '#666', fontSize: 13, cursor: 'pointer',
            }}
          >
            건너뛰기
          </button>
          <button
            onClick={() => isLast ? onComplete() : setStep(s => s + 1)}
            style={{
              padding: '10px 28px', borderRadius: 10, border: 'none',
              background: '#4ade80', color: '#000',
              fontSize: 14, fontWeight: 700, cursor: 'pointer',
            }}
          >
            {isLast ? '시작하기! 🏓' : '다음'}
          </button>
        </div>
      </div>
    </div>
  );
}
