import { useNavigate } from 'react-router-dom';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

const SECTIONS = [
  {
    title: '1. 수집하는 개인정보 항목',
    content: '회사는 서비스 제공을 위해 다음과 같은 개인정보를 수집합니다.\n\n[필수 항목]\n- 이메일 주소, 비밀번호, 닉네임\n- 판매자: 사업자등록번호, 대표자명, 사업장 주소, 세금계산서 이메일, 은행 계좌정보\n\n[선택 항목]\n- 전화번호, 주소, 성별, 생년월일\n- 프로필 이미지\n\n[자동 수집 항목]\n- IP 주소, 쿠키, 서비스 이용 기록, 접속 로그, 기기 정보',
  },
  {
    title: '2. 개인정보의 수집 및 이용 목적',
    content: '- 회원 가입 및 본인 확인\n- 공동구매 거래 처리 및 정산\n- 서비스 제공 및 개선\n- 고객 상담 및 불만 처리\n- 부정 이용 방지 및 서비스 안전성 확보\n- 법적 의무 이행 (전자상거래법, 세법 등)\n- 마케팅 및 이벤트 안내 (동의한 경우에 한함)',
  },
  {
    title: '3. 개인정보의 보유 및 이용 기간',
    content: '회원 탈퇴 시 즉시 파기합니다. 다만, 관련 법령에 따라 다음 기간 동안 보관합니다.\n\n- 계약 또는 청약철회 등에 관한 기록: 5년 (전자상거래법)\n- 대금결제 및 재화 등의 공급에 관한 기록: 5년 (전자상거래법)\n- 소비자 불만 또는 분쟁처리에 관한 기록: 3년 (전자상거래법)\n- 표시·광고에 관한 기록: 6개월 (전자상거래법)\n- 웹사이트 방문 기록: 3개월 (통신비밀보호법)',
  },
  {
    title: '4. 개인정보의 제3자 제공',
    content: '회사는 원칙적으로 이용자의 동의 없이 개인정보를 제3자에게 제공하지 않습니다. 다만, 다음의 경우는 예외로 합니다.\n\n- 거래 이행을 위해 배송 정보를 판매자에게 제공 (이름, 주소, 연락처)\n- 정산을 위해 판매자 정보를 결제 대행사에 제공\n- 법령에 의한 요청이 있는 경우\n\n※ 결제 시 배송에 필요한 개인정보(이름, 주소, 연락처)가 해당 거래의 판매자에게 제공되며, 이에 대해 결제 과정에서 별도 동의를 받습니다.',
  },
  {
    title: '5. 개인정보 처리 위탁',
    content: '회사는 서비스 제공을 위해 다음과 같이 개인정보 처리를 위탁하고 있습니다.\n\n- 결제 처리: PG사 (결제 관련 정보)\n- 이메일 발송: SMTP 서비스 제공자 (이메일 주소)\n- 클라우드 서버: 서버 호스팅 업체 (서비스 데이터 전반)\n\n위탁 업체가 변경되는 경우 공지사항을 통해 알려드립니다.',
  },
  {
    title: '6. 이용자의 권리 및 행사 방법',
    content: '이용자는 언제든지 다음의 권리를 행사할 수 있습니다.\n\n- 개인정보 열람 요청\n- 개인정보 정정·삭제 요청\n- 개인정보 처리 정지 요청\n- 회원 탈퇴 요청\n\n위 권리는 마이페이지 또는 고객센터(support@yeokping.com)를 통해 행사할 수 있으며, 회사는 지체 없이 조치합니다.',
  },
  {
    title: '7. 개인정보의 안전성 확보 조치',
    content: '회사는 개인정보의 안전성 확보를 위해 다음과 같은 조치를 취하고 있습니다.\n\n- 비밀번호 암호화 저장 (bcrypt)\n- SSL/TLS를 통한 데이터 전송 암호화\n- 접근 권한 관리 및 접근 통제\n- 개인정보 접근 로그 기록 및 보관\n- 보안 프로그램 설치 및 주기적 점검',
  },
  {
    title: '8. 쿠키의 사용',
    content: '회사는 서비스 이용 편의를 위해 쿠키를 사용합니다.\n\n- 사용 목적: 로그인 상태 유지, 서비스 설정 저장\n- 쿠키 거부 방법: 브라우저 설정에서 쿠키를 차단할 수 있습니다. 다만, 쿠키를 차단하면 서비스 이용에 제한이 있을 수 있습니다.',
  },
  {
    title: '9. 개인정보 보호 책임자',
    content: '회사는 개인정보 보호 관련 문의 및 불만 처리를 위해 아래와 같이 개인정보 보호 책임자를 지정하고 있습니다.\n\n- 개인정보 보호 책임자: 대표이사\n- 이메일: privacy@yeokping.com\n- 연락처: support@yeokping.com',
  },
  {
    title: '10. 권익 침해 구제 방법',
    content: '개인정보 침해에 대한 상담이 필요한 경우 다음 기관에 문의할 수 있습니다.\n\n- 개인정보 침해신고센터: privacy.kisa.or.kr (국번없이 118)\n- 개인정보 분쟁조정위원회: kopico.go.kr (1833-6972)\n- 대검찰청 사이버수사과: spo.go.kr (국번없이 1301)\n- 경찰청 사이버안전국: cyberbureau.police.go.kr (국번없이 182)\n\n시행일: 2026년 1월 1일',
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
