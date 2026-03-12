import { useNavigate } from 'react-router-dom';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

const SECTIONS = [
  {
    title: '1. 수집하는 개인정보 항목',
    content: '가. 필수 수집 항목\n- 회원가입: 이메일, 닉네임, 비밀번호 (소셜 로그인 시 소셜 계정 정보)\n- 판매자 추가: 사업자등록번호, 상호, 대표자명, 사업장 주소, 업태/종목\n- 액츄에이터 추가: 계좌정보 (은행, 계좌번호, 예금주)\n- 결제: 결제수단 정보 (PG사를 통해 처리, 회사는 카드번호 미보관)\n- 배송: 수령인명, 배송지 주소, 연락처\n\n나. 선택 수집 항목\n- 관심 카테고리/제품/모델 (최대 10개)\n- 프로필 이미지\n- 사업자등록증 이미지 (OCR 처리 후 텍스트만 저장)\n\n다. 자동 수집 항목\n- 접속 IP, 브라우저 정보, 접속 일시, 서비스 이용 기록\n- 쿠키 (로그인 유지, 접속키 인증용)',
  },
  {
    title: '2. 개인정보의 수집 및 이용 목적',
    content: '- 회원 관리: 가입, 본인 확인, 서비스 이용\n- 거래 이행: 주문, 결제, 배송, 환불, 정산\n- 세금계산서 발행: 사업자 정보 기반 전자 세금계산서 발행\n- 원천징수: 개인 액츄에이터 소득 신고\n- 서비스 개선: 이용 통계, AI 모델 개선, 관심 상품 매칭\n- 알림 발송: 거래 알림, 마케팅 정보 (동의한 경우)\n- 부정 이용 방지: 이상 거래 탐지, 분쟁 해결',
  },
  {
    title: '3. 개인정보의 보유 및 이용 기간',
    content: '- 회원 정보: 회원 탈퇴 시까지 (탈퇴 후 즉시 파기)\n- 거래 기록: 전자상거래법에 따라 5년 보관\n- 결제 기록: 전자금융거래법에 따라 5년 보관\n- 접속 로그: 통신비밀보호법에 따라 3개월 보관\n- 세금 관련: 국세기본법에 따라 5년 보관\n- 소비자 불만/분쟁: 전자상거래법에 따라 3년 보관',
  },
  {
    title: '4. 개인정보의 제3자 제공',
    content: '회사는 이용자의 동의 없이 개인정보를 제3자에게 제공하지 않습니다.\n다만, 다음의 경우 제공할 수 있습니다:\n\n- 거래 이행: 구매자 배송 정보를 판매자에게 제공 (거래 성립 시 동의)\n- 결제 처리: PG사에 결제 정보 전달\n- 배송 추적: 택배사에 운송장 정보 조회 요청\n- 세금계산서: 국세청에 세금계산서 발행 정보 전달\n- 법적 요구: 수사기관의 적법한 요청 시',
  },
  {
    title: '5. 개인정보 처리 위탁',
    content: '회사는 서비스 제공을 위해 다음과 같이 개인정보 처리를 위탁합니다:\n\n- 클라우드 호스팅: Railway (서버 운영)\n- AI 서비스: OpenAI (상품 인식, 가격 분석 — 개인식별정보 미전송)\n- 이메일 발송: Google Gmail SMTP\n- 푸시 알림: Firebase Cloud Messaging (FCM)',
  },
  {
    title: '6. 이용자의 권리 및 행사 방법',
    content: '이용자는 언제든지 다음의 권리를 행사할 수 있습니다:\n\n- 개인정보 열람 요청\n- 개인정보 정정 요청\n- 개인정보 삭제 요청 (법령에 의한 보관 의무 제외)\n- 개인정보 처리 정지 요청\n- 회원 탈퇴\n\n요청 방법: 마이페이지 또는 이메일(sales@tellustech.co.kr)로 요청',
  },
  {
    title: '7. 개인정보의 안전성 확보 조치',
    content: '- 비밀번호 암호화 저장 (bcrypt)\n- HTTPS 통신 암호화\n- JWT 토큰 기반 인증\n- 관리자 접근 제어 (AdminAuthMiddleware)\n- Rate Limiting (API 호출 제한)\n- XSS/SQL Injection 방어',
  },
  {
    title: '8. 쿠키의 사용',
    content: '회사는 다음의 목적으로 쿠키를 사용합니다:\n\n- 로그인 상태 유지 (JWT 토큰)\n- 점검 모드 접속키 인증\n\n이용자는 브라우저 설정을 통해 쿠키를 거부할 수 있으나, 일부 서비스 이용에 제한이 있을 수 있습니다.',
  },
  {
    title: '9. 개인정보 보호 책임자',
    content: '성명: 이정상\n직위: 대표이사\n이메일: jslee@tellustech.co.kr',
  },
  {
    title: '10. 권익 침해 구제 방법',
    content: '개인정보 침해에 대한 신고·상담:\n\n- 개인정보침해신고센터: privacy.kisa.or.kr / 118\n- 대검찰청 사이버수사과: spo.go.kr / 1301\n- 경찰청 사이버안전국: cyberbureau.police.go.kr / 182\n\n시행일: 2026년 3월 12일',
  },
];

export default function PrivacyPage() {
  const navigate = useNavigate();

  return (
    <div style={{ minHeight: '100dvh', background: C.bg, paddingBottom: 100 }}>
      <div style={{
        position: 'sticky', top: 0, zIndex: 100,
        height: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 16px', background: C.bg, borderBottom: `1px solid ${C.border}`,
      }}>
        <button onClick={() => navigate(-1)} style={{ fontSize: 20, color: C.text, cursor: 'pointer', lineHeight: 1 }}>←</button>
        <span style={{ fontSize: 15, fontWeight: 700, color: C.text }}>개인정보처리방침</span>
        <div style={{ width: 24 }} />
      </div>

      <div style={{ padding: '14px 16px 0' }}>
        <div style={{
          background: C.bgCard, border: `1px solid ${C.border}`,
          borderRadius: 16, padding: '16px 18px',
        }}>
          <div style={{ fontSize: 16, fontWeight: 800, color: C.text, marginBottom: 4 }}>역핑 개인정보처리방침</div>
          <div style={{ fontSize: 11, color: C.textDim, marginBottom: 6 }}>
            (주)텔러스테크(이하 "회사")는 개인정보 보호법 등 관련 법령을 준수하며, 이용자의 개인정보를 보호하기 위해 최선을 다합니다.
          </div>
          <div style={{ fontSize: 11, color: C.textDim, marginBottom: 20 }}>시행일: 2026.03.12</div>

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
