## Guardrails
### Privacy / Security
- PII 금지:
  - 배송지/주소/전화번호/이메일/실명
  - 결제수단 정보(카드번호/계좌/PG 원문 응답 전문)
- 허용되는 식별자:
  - 내부 ID (reservation_id, offer_id, deal_id, buyer_id, seller_id)
  - pg_tid 는 테스트/샌드박스 환경에서는 허용 가능
  - 운영에서는 pg_tid 저장 시 마스킹/해시 처리 권장

### Data Minimization
- “정책 검증/감사/디버깅”에 필요한 최소한의 필드만 저장한다.
- request/response 원문 전체를 저장하지 않는다(특히 PG/개인정보 포함 가능).

### Access Control
- 기본 접근은 Admin 전용.
- Buyer/Seller agent 는:
  - 자신의 건(reservation_id) + 비식별/요약 형태만 조회 가능하도록 제한.
- Evidence Pack 조회/다운로드는 모두 감사로그(누가/언제/무엇을) 남긴다.

### Integrity / Tamper Resistance
- Evidence Pack 생성 시:
  - `hash_sha256`(payload canonicalized) 저장 권장
  - 필요하면 `prev_hash`를 포함해 체인 형태(append-only)로 운영
- 운영 환경에서는 “수정” 대신 “정정 이벤트(REVISION)”를 추가한다.

### Retention
- 기본 보관:
  - 개발/스테이징: 7~30일
  - 운영: 90~180일 (법/정책 요구에 따름)
- 보관기간 종료 시:
  - 삭제 또는 비식별화(집계치만 유지)

### Reliability / Observability
- Evidence Pack 기록 실패는 핵심 로직(환불)을 막지 않되,
  - 경고 로그 + 카운터(메트릭) 증가 + 알림(옵션)
- 중복 기록 방지:
  - (reservation_id, stage, case, event_time bucket) 또는 run_id 기반 idempotency key 권장

### Policy Safety (Agent Proposal Loop)
- 핑퐁(Agent)이 Evidence Pack을 근거로 정책 제안할 때:
  - 제안(Proposal)에는 반드시 참조 evidence_pack_id 목록 포함
  - Admin 승인 전 자동 적용 금지
  - A/B or 점진배포 + 롤백 플로우 강제