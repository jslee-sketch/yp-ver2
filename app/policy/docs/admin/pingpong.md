 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# 핑퐁이/서버 SSOT 구조 (Admin)

## 핵심
- 숫자/상태/결론은 서버가 확정(SSOT)
- 핑퐁이는 그 결과를 자연어로 풀어 설명

## fastpath
- policy one-liner precheck
- faq_atom (팩트 단답)
- term_resolver (팩트 질문 스킵)

---

## 정책 제안 워크플로 (Policy Proposal)

### 흐름

```
[이상 감지]
    │  핑퐁이 또는 배치가 패턴 이상 탐지
    ▼
[제안서 생성]
    │  LLM이 policy_proposals 레코드 + 변경 diff 생성
    │  status: PROPOSED
    ▼
[관리자 검토]
    │  POST /admin/policy/proposals/{id}/approve  → APPROVED
    │  POST /admin/policy/proposals/{id}/reject   → REJECTED
    ▼
[정책 반영 또는 롤백]
    │  APPROVED → defaults.yaml 파라미터 적용 (YAML 버전 백업)
    │  REJECTED → 기존 설정 유지
    ▼
[감사 로그]
    │  변경자 / before / after / 사유 / 근거 모두 기록
    └─ policy_proposals 테이블에 영구 보존
```

### policy_proposals 테이블

```
policy_proposals
├── id                  PK, auto
├── title               String               (제안 제목)
├── type                String               (parameter_change / rule_change)
├── status              String               (PROPOSED / APPROVED / REJECTED)
├── proposed_by         String               (agent / admin_id)
├── proposed_at         DateTime
├── diff_json           JSON                 (before/after 파라미터 diff)
├── reason              Text                 (변경 근거)
├── reviewed_by         String, nullable     (승인/거절한 관리자)
├── review_note         Text, nullable
└── reviewed_at         DateTime, nullable
```

### YAML 버전 관리

- 파라미터 변경 전 `defaults.yaml.bak.{timestamp}` 백업 생성
- 롤백: `POST /admin/policy/rollback/{backup_id}`
- 현재 YAML 버전 해시를 `policy_proposals.diff_json.yaml_hash`에 기록

---

## 이상 감지 패턴 (5종)

| 패턴 | 감지 기준 | 알림 방식 |
|------|-----------|-----------|
| **가격 이상** | 동일 딜에서 오퍼 가격 표준편차 > 30% | policy_proposal 자동 생성 |
| **대량 예약** | 동일 IP에서 10분 내 예약 5건 이상 | 어드민 알림 |
| **환불 패턴** | 특정 셀러의 환불률 > 20% (1주간) | policy_proposal + 셀러 경고 |
| **셀러 클레임** | 동일 구매자에게 분쟁 3건 이상 (30일) | 어드민 검토 큐 |
| **봇 의심** | 예측 제출 횟수 > rate_limit × 0.8 | rate_limit 일시 강화 |

---

## 핑퐁이 일일 리포트 배치 (매일 오전)

- **주기**: 매일 오전 (기본 08:00 KST)
- **생성 내용**: 전날 활동 요약 (LLM으로 요약문 생성)

```json
{
  "date": "2026-02-27",
  "total_questions": 47,
  "error_count": 3,
  "top_intents": ["환불", "가격", "배송"],
  "top_screens": ["DEAL_ROOM", "home"],
  "unresolved_ratio": 0.06,
  "anomaly_flags": ["환불 패턴 감지: seller_id=5"],
  "summary": "어제 47건의 질문 중 3건 오류. 환불 관련 질문이 가장 많았습니다..."
}
```

- **저장 위치**: `pingpong_logs` + 어드민 대시보드
- **구현 위치**: `app/schedulers/pingpong_daily_report.py`

