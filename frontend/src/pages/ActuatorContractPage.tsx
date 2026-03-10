import { useState, useRef, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { API } from '../api/endpoints';
import apiClient from '../api/client';

/* ── 계약서 전문 (14조) ─────────────────────────────────── */
const CONTRACT_TEXT = `
역핑(Yeokping) 플랫폼 액추에이터 위탁 계약서

제1조 (목적)
본 계약은 (주)텔러스테크(이하 "회사")가 운영하는 역핑 플랫폼에서 액추에이터(이하 "을")가 판매자 모집 및 관리 업무를 위탁받아 수행함에 있어 필요한 사항을 정합니다.

제2조 (정의)
1. "플랫폼"이란 회사가 운영하는 역핑(Yeokping) 공동구매 중개 서비스를 말합니다.
2. "액추에이터"란 플랫폼의 판매자 모집·관리 업무를 위탁받은 개인 또는 사업자를 말합니다.
3. "커미션"이란 액추에이터가 모집한 판매자의 거래에서 발생하는 수수료 수익을 말합니다.

제3조 (계약 기간)
1. 본 계약의 유효기간은 계약 체결일로부터 1년으로 합니다.
2. 계약 만료 1개월 전까지 쌍방 중 어느 일방이 서면으로 해지 의사를 통보하지 않는 한 동일 조건으로 1년씩 자동 갱신됩니다.

제4조 (을의 의무)
1. 을은 성실히 판매자 모집 및 관리 업무를 수행해야 합니다.
2. 을은 플랫폼의 운영 정책 및 관련 법령을 준수해야 합니다.
3. 을은 모집한 판매자의 상품 품질 및 서비스 수준을 관리·감독해야 합니다.
4. 을은 회사의 영업비밀 및 고객 정보를 보호해야 합니다.

제5조 (회사의 의무)
1. 회사는 을의 업무 수행에 필요한 시스템 접근 권한을 제공합니다.
2. 회사는 커미션을 약정된 조건에 따라 정산·지급합니다.
3. 회사는 을의 업무 수행에 필요한 교육 및 지원을 제공합니다.

제6조 (커미션 산정)
1. 커미션은 을이 모집한 판매자의 확정 거래 금액에 대해 판매자 등급별 차등 요율을 적용하여 산정합니다.
2. 커미션 요율은 별도 부속서(정책 문서)에 따르며, 회사는 30일 전 사전 통보 후 변경할 수 있습니다.
3. 커미션은 거래 확정(구매확인) 후 정산 주기에 따라 지급합니다.

제7조 (정산 및 지급)
1. 정산 주기: 거래 확정 후 쿨링 기간(7~30일) 경과 후 정산 READY 상태로 전환됩니다.
2. 지급 방법:
   (가) 개인 액추에이터: 원천징수(소득세 3% + 지방소득세 0.3% = 3.3%)를 공제한 후 등록 계좌로 이체합니다.
   (나) 사업자 액추에이터: 세금계산서 발행 후 등록 계좌로 이체합니다.
3. 최소 지급 금액: 10,000원 미만일 경우 다음 정산 주기로 이월됩니다.

제8조 (원천징수)
1. 개인 액추에이터의 소득에 대해 소득세법에 따라 원천징수를 실시합니다.
2. 원천징수세율: 소득세 3% + 지방소득세 0.3% = 총 3.3%
3. 회사는 원천징수 영수증을 매년 2월 말까지 교부합니다.
4. 사업자 액추에이터의 경우 원천징수 대신 세금계산서를 발행합니다.

제9조 (비밀유지)
1. 을은 계약 기간 및 계약 종료 후 2년간 업무상 알게 된 회사의 영업비밀, 고객 정보, 기술 정보 등을 제3자에게 누설하거나 업무 외 목적으로 사용하지 않습니다.

제10조 (손해배상)
1. 을이 고의 또는 중대한 과실로 회사 또는 제3자에게 손해를 끼친 경우, 을은 그 손해를 배상해야 합니다.
2. 회사가 을에게 지급해야 할 커미션을 정당한 사유 없이 지연할 경우, 지연일수에 대해 연 5%의 지연이자를 가산하여 지급합니다.

제11조 (계약 해지)
1. 쌍방은 30일 전 서면 통보로 본 계약을 해지할 수 있습니다.
2. 다음 각 호에 해당하는 경우 상대방에 대한 서면 통보로 즉시 해지할 수 있습니다:
   (가) 관련 법령 위반
   (나) 허위 정보 제공
   (다) 플랫폼 운영 방해 행위
   (라) 3개월 이상 활동 실적이 없는 경우

제12조 (계약 종료 후 처리)
1. 계약 종료 시 미지급 커미션은 30일 이내에 정산·지급합니다.
2. 을은 계약 종료 즉시 회사로부터 제공받은 자료, 접근 권한 등을 반환하거나 삭제해야 합니다.

제13조 (분쟁 해결)
1. 본 계약과 관련된 분쟁은 서울중앙지방법원을 관할 법원으로 합니다.

제14조 (기타)
1. 본 계약에 명시되지 않은 사항은 관련 법령 및 상관례에 따릅니다.
2. 본 계약의 변경은 서면 합의에 의해서만 유효합니다.
`.trim();

export default function ActuatorContractPage() {
  const navigate = useNavigate();
  const scrollRef = useRef<HTMLDivElement>(null);

  const [scrolledToEnd, setScrolledToEnd] = useState(false);
  const [check1, setCheck1] = useState(false);
  const [check2, setCheck2] = useState(false);
  const [check3, setCheck3] = useState(false);
  const [loading, setLoading] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState('');

  // 이미 동의 여부 확인
  useEffect(() => {
    const u = localStorage.getItem('user');
    if (!u) return;
    try {
      const user = JSON.parse(u);
      const aid = user.actuator_id || user.id;
      if (!aid) return;
      apiClient.get(API.ACTUATORS.CONTRACT_STATUS(aid)).then((r: { data?: { contract_agreed?: boolean } }) => {
        if (r.data?.contract_agreed) setAgreed(true);
      }).catch(() => {});
    } catch {}
  }, []);

  const handleScroll = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
    if (atBottom) setScrolledToEnd(true);
  }, []);

  const canAgree = scrolledToEnd && check1 && check2 && check3 && !loading;

  const handleAgree = async () => {
    setLoading(true);
    setError('');
    try {
      const u = localStorage.getItem('user');
      if (!u) throw new Error('로그인 필요');
      const user = JSON.parse(u);
      const aid = user.actuator_id || user.id;
      await apiClient.post(API.ACTUATORS.AGREE_CONTRACT(aid));
      setAgreed(true);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e.message || '오류 발생');
    } finally {
      setLoading(false);
    }
  };

  if (agreed) {
    return (
      <div style={{ padding: 32, maxWidth: 800, margin: '0 auto', textAlign: 'center' }}>
        <h2 style={{ color: 'var(--color-success, #22c55e)', marginBottom: 16 }}>위탁계약서 동의 완료</h2>
        <p>계약 버전: v1.0</p>
        <p style={{ marginTop: 16, color: 'var(--color-text-secondary)' }}>
          커미션 정산이 활성화되었습니다.
        </p>
        <button
          onClick={() => navigate('/actuator/commissions')}
          style={{
            marginTop: 24, padding: '12px 32px',
            background: 'var(--color-primary, #6366f1)', color: '#fff',
            border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 16,
          }}
        >
          커미션 관리로 이동
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 800, margin: '0 auto' }}>
      <h2 style={{ marginBottom: 8 }}>역핑 액추에이터 위탁 계약서</h2>
      <p style={{ color: 'var(--color-text-secondary)', marginBottom: 16, fontSize: 14 }}>
        계약서 전문을 끝까지 읽은 후 동의해 주세요.
      </p>

      {/* 계약서 본문 스크롤 영역 */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        style={{
          height: 400, overflowY: 'auto',
          border: '1px solid var(--color-border, #e5e7eb)',
          borderRadius: 8, padding: 20,
          background: 'var(--color-bg-secondary, #f9fafb)',
          whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.8,
        }}
      >
        {CONTRACT_TEXT}
      </div>

      {!scrolledToEnd && (
        <p style={{ color: 'var(--color-warning, #f59e0b)', fontSize: 13, marginTop: 8 }}>
          계약서를 끝까지 스크롤해 주세요.
        </p>
      )}

      {/* 체크박스 3개 */}
      <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
          <input type="checkbox" checked={check1} onChange={e => setCheck1(e.target.checked)} />
          위탁계약서 전문을 읽고 이해하였습니다.
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
          <input type="checkbox" checked={check2} onChange={e => setCheck2(e.target.checked)} />
          커미션 정산 및 원천징수(개인 3.3%) 조건에 동의합니다.
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
          <input type="checkbox" checked={check3} onChange={e => setCheck3(e.target.checked)} />
          비밀유지 의무 및 손해배상 책임에 동의합니다.
        </label>
      </div>

      {error && (
        <p style={{ color: 'var(--color-error, #ef4444)', marginTop: 12, fontSize: 14 }}>{error}</p>
      )}

      <button
        onClick={handleAgree}
        disabled={!canAgree}
        style={{
          marginTop: 24, width: '100%', padding: '14px 0',
          background: canAgree ? 'var(--color-primary, #6366f1)' : '#ccc',
          color: '#fff', border: 'none', borderRadius: 8,
          cursor: canAgree ? 'pointer' : 'not-allowed',
          fontSize: 16, fontWeight: 600,
        }}
      >
        {loading ? '처리 중...' : '동의하고 계약 체결'}
      </button>
    </div>
  );
}
