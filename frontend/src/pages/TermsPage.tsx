import { useNavigate } from 'react-router-dom';

const C = {
  bg: 'var(--bg-primary)', bgCard: 'var(--bg-secondary)',
  text: 'var(--text-primary)', textSec: 'var(--text-secondary)', textDim: 'var(--text-muted)',
  border: 'var(--border-subtle)', green: 'var(--accent-green)',
};

const SECTIONS = [
  {
    title: '제1조 (목적)',
    content: '이 약관은 (주)텔러스테크(이하 "회사")가 운영하는 역핑 플랫폼(이하 "서비스")의 이용과 관련하여 회사와 이용자 간의 권리, 의무 및 책임사항, 서비스 이용 조건 및 절차 등 기본적인 사항을 규정함을 목적으로 합니다.',
  },
  {
    title: '제2조 (정의)',
    content: '① "서비스"란 회사가 운영하는 역핑 플랫폼(www.yeokping.com)을 통해 제공하는 역경매 기반 전자상거래 중개 서비스를 말합니다.\n② "이용자"란 서비스에 접속하여 이 약관에 따라 서비스를 이용하는 회원 및 비회원을 말합니다.\n③ "구매자"란 서비스를 통해 딜(Deal)을 생성하고 상품 구매를 희망하는 회원을 말합니다.\n④ "판매자"란 서비스를 통해 구매자의 딜에 오퍼(Offer)를 제출하는 사업자를 말합니다.\n⑤ "딜"이란 구매자가 희망하는 상품, 가격, 조건을 등록하는 역경매 요청을 말합니다.\n⑥ "오퍼"란 판매자가 딜에 대해 제안하는 가격 및 거래 조건을 말합니다.\n⑦ "액츄에이터"란 회사와 업무 위탁 계약을 체결하고 판매자를 모집하는 자를 말합니다.',
  },
  {
    title: '제3조 (약관의 게시 및 변경)',
    content: '① 회사는 이 약관의 내용을 이용자가 알 수 있도록 서비스 내에 게시합니다.\n② 회사는 관련 법령에 위배되지 않는 범위에서 약관을 변경할 수 있으며, 변경 시 적용일자 7일 전부터 공지합니다.\n③ 이용자가 변경된 약관에 동의하지 않을 경우 서비스 이용을 중단하고 탈퇴할 수 있습니다.',
  },
  {
    title: '제4조 (회사의 지위 — 통신판매중개)',
    content: '① 회사는 통신판매중개자로서 구매자와 판매자 간 거래를 중개하며, 통신판매의 당사자가 아닙니다.\n② 회사는 판매자가 등록한 상품의 품질, 정보의 정확성, 거래의 이행에 대해 보증하지 않습니다.\n③ 구매자와 판매자 간 거래에서 발생하는 분쟁에 대해 회사는 중재를 지원할 수 있으나, 최종 책임은 거래 당사자에게 있습니다.\n④ 다만, 회사의 고의 또는 과실로 인해 이용자에게 손해가 발생한 경우 회사는 그에 대한 책임을 집니다.',
  },
  {
    title: '제5조 (회원 가입 및 자격)',
    content: '① 서비스는 만 14세 이상의 개인 또는 적법한 사업자가 이용할 수 있습니다.\n② 회원가입은 이용약관 동의, 개인정보 수집·이용 동의 후 가입 양식을 작성하여 신청합니다.\n③ 소셜 로그인(카카오, 네이버, 구글)을 통해 간편 가입이 가능합니다.\n④ 판매자는 사업자등록증 및 추가 서류 제출이 필요하며, 회사의 승인 후 활동이 가능합니다.',
  },
  {
    title: '제6조 (딜 및 오퍼)',
    content: '① 구매자는 희망 상품, 목표 가격, 수량, 조건을 입력하여 딜을 생성할 수 있습니다.\n② 판매자는 딜에 대해 가격, 배송 조건, 배송 기간 등을 포함한 오퍼를 제출할 수 있습니다.\n③ 구매자가 오퍼를 선택하고 결제하면 거래가 성립됩니다.\n④ 본 서비스의 가격 제안 방식은 "경매 등에 관한 법률"상의 경매에 해당하지 않으며, 구매자의 자유로운 가격 제안과 판매자의 자발적 응찰로 이루어지는 전자상거래 방식입니다.',
  },
  {
    title: '제7조 (AI 분석 및 가격 정보)',
    content: '① 회사는 AI 기술을 활용하여 시장가 분석, 상품 인식, 가격 추천 등의 보조 정보를 제공합니다.\n② AI가 제공하는 시장가, 가격 분석, 상품 정보는 참고 목적이며, 그 정확성이나 완전성을 보장하지 않습니다.\n③ AI 정보에 기반한 거래 결정의 책임은 이용자에게 있습니다.\n④ 핑퐁이(AI 어시스턴트)의 답변은 일반적인 안내이며, 법적·전문적 조언이 아닙니다.',
  },
  {
    title: '제8조 (결제 및 정산)',
    content: '① 구매자는 회사가 지정한 결제 수단을 통해 대금을 지불합니다.\n② 회사는 구매자의 구매확정 후 판매자에게 정산금을 지급합니다.\n③ 정산금은 판매 대금에서 PG 수수료, 플랫폼 수수료를 공제한 금액입니다.\n④ 플랫폼 수수료율은 판매자 등급에 따라 차등 적용됩니다.\n⑤ 정산은 구매확정 후 쿨링기간(최소 7일) 경과 후 진행됩니다.',
  },
  {
    title: '제9조 (청약철회 및 환불)',
    content: '① 구매자는 상품 수령 후 7일 이내에 청약을 철회할 수 있습니다.\n② 다만 다음의 경우 청약철회가 제한될 수 있습니다:\n  - 구매자의 귀책사유로 상품이 훼손된 경우\n  - 사용 또는 일부 소비로 상품 가치가 현저히 감소한 경우\n  - 복제 가능한 상품의 포장을 훼손한 경우\n③ 환불 시 배송비 부담은 귀책사유에 따라 결정됩니다 (구매자 사유: 구매자 부담, 판매자 사유: 판매자 부담).',
  },
  {
    title: '제10조 (분쟁 해결)',
    content: '① 거래 관련 분쟁 발생 시 회사는 중재를 지원합니다.\n② 분쟁 해결이 어려운 경우 한국소비자원 또는 전자거래분쟁조정위원회에 조정을 신청할 수 있습니다.\n③ 본 약관에 명시되지 않은 사항은 전자상거래 등에서의 소비자보호에 관한 법률, 약관의 규제에 관한 법률 등 관련 법령에 따릅니다.',
  },
  {
    title: '제11조 (서비스 이용 제한)',
    content: '① 회사는 다음의 경우 서비스 이용을 제한하거나 회원 자격을 정지할 수 있습니다:\n  - 허위 정보 등록\n  - 타인의 정보 도용\n  - 서비스 운영 방해\n  - 관련 법령 위반\n  - 부정 거래 행위\n② 이용 정지 전 사전 통지하며, 긴급한 경우 사후 통지할 수 있습니다.',
  },
  {
    title: '제12조 (면책 조항)',
    content: '① 천재지변, 전쟁, 기간통신사업자의 서비스 중단 등 불가항력으로 인한 서비스 중단 시 회사는 책임이 면제됩니다.\n② 회사는 이용자의 귀책사유로 인한 서비스 이용 장애에 대해 책임지지 않습니다.\n③ 회사는 이용자가 서비스 내에 게시한 정보의 신뢰성, 정확성에 대해 보증하지 않습니다.',
  },
  {
    title: '제13조 (관할 법원 및 준거법)',
    content: '① 이 약관은 대한민국 법률에 따라 규율됩니다.\n② 서비스 이용과 관련하여 분쟁이 발생한 경우, 회사의 본점 소재지를 관할하는 법원을 전속 관할법원으로 합니다.\n\n부칙\n이 약관은 2026년 3월 12일부터 시행합니다.\n\n사업자 정보\n상호: (주)텔러스테크\n대표: 이정상\n사업자등록번호: 113-86-39805\n통신판매업 신고번호: [신고 후 기입]\n주소: 서울시 금천구 두산로 70, 에이동 811호\n이메일: sales@tellustech.co.kr',
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
