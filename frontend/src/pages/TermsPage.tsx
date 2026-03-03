import { useNavigate } from 'react-router-dom';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

const SECTIONS = [
  {
    title: '제1조 (목적)',
    content: '이 약관은 역핑(이하 "회사")이 제공하는 공동구매 중개 서비스(이하 "서비스")의 이용과 관련하여 회사와 이용자 간의 권리, 의무 및 책임사항 등을 규정함을 목적으로 합니다.',
  },
  {
    title: '제2조 (정의)',
    content: '1. "서비스"란 회사가 제공하는 공동구매 중개 플랫폼을 말합니다.\n2. "이용자"란 이 약관에 따라 서비스를 이용하는 구매자 및 판매자를 말합니다.\n3. "딜"이란 구매자가 생성한 공동구매 요청을 말합니다.\n4. "오퍼"란 판매자가 딜에 대해 제시한 판매 조건을 말합니다.',
  },
  {
    title: '제3조 (서비스 이용)',
    content: '1. 서비스 이용을 위해 회원가입이 필요합니다.\n2. 이용자는 정확한 정보를 제공해야 합니다.\n3. 회사는 서비스의 안정적 운영을 위해 최선을 다합니다.',
  },
  {
    title: '제4조 (거래 및 결제)',
    content: '1. 거래는 구매자와 판매자 간의 직접 거래입니다.\n2. 회사는 거래의 중개자로서 거래 안전을 위한 에스크로 서비스를 제공합니다.\n3. 결제는 오퍼 마감 후 제한된 시간 내에 완료해야 합니다.',
  },
  {
    title: '제5조 (환불 및 취소)',
    content: '1. 결제 전 취소: 언제든지 가능합니다.\n2. 결제 후 배송 전 취소: 정책에 따라 수수료가 발생할 수 있습니다.\n3. 배송 후 환불: 상품 수령 후 7일 이내에 환불 요청이 가능합니다.',
  },
  {
    title: '제6조 (개인정보 보호)',
    content: '회사는 이용자의 개인정보를 관련 법률에 따라 보호하며, 개인정보처리방침에 따라 처리합니다.',
  },
];

export default function TermsPage() {
  const navigate = useNavigate();

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>이용약관</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 16, padding: '16px 18px',
        }}>
          <div style={{ fontSize: 16, fontWeight: 800, color: C.text, marginBottom: 4 }}>역핑 서비스 이용약관</div>
          <div style={{ fontSize: 11, color: C.textDim, marginBottom: 20 }}>시행일: 2026.01.01</div>

          {SECTIONS.map((s, i) => (
            <div key={i} style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: C.text, marginBottom: 6 }}>{s.title}</div>
              <div style={{ fontSize: 12, color: C.textSec, lineHeight: 1.7, whiteSpace: 'pre-line' }}>{s.content}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
