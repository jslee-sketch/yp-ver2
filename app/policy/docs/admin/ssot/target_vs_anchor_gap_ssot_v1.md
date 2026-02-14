@'
# TARGET_VS_ANCHOR_GAP_SSOT_v1
ADMIN ONLY — BUYER/SELLER 응답 근거로 사용 금지

본 문서는 Guardrail(차단/경고/허용)을 실제 코드/상태/UI가 “한 덩어리로” 쓰기 위해,
Target(딜방 목표가) vs Anchor(외부 기준가) 괴리 평가 로직을 SSOT로 고정한다.

---

## 0) 핵심 요약(이 문서가 보장하는 것)

- Target은 “최종 입력값”이며 의사결정 축이다.
- Anchor는 “외부 근거 기반 비동기 기준가”이며 신뢰를 보조하는 축이다.
- Anchor가 없어도 딜은 흐를 수 있어야 한다(Cold start).
- Anchor가 도착하면 즉시 재평가한다(사후 경고/잠금/차단 가능).
- 결과는 반드시 표준 Decision(레벨) + reason_codes + 숫자(gap 등)로 반환한다.
- UI는 “딜 리스트/오퍼랭킹”에서는 최소 정보만, 상세에서만 설명을 노출한다.

---

## 1) 입력/출력(SSOT)

### 1.1 입력(PriceAxisEvaluationInput)
- deal_id: int
- category: str | None
- target_price: float | None       # 딜방 목표가(입력값). None이면 평가 불가(ANCHOR만 저장)
- anchor_price: float | None       # 비동기 기준가. None 가능
- evidence_score: int | None       # 0~100. None이면 0으로 간주
- anchor_confidence: float | None  # 0~1. (있으면 사용, 없으면 1로 간주)
- now_ts: datetime

### 1.2 출력(PriceAxisEvaluationResult)
- level: "ALLOW" | "WARN_SOFT" | "WARN_HARD" | "BLOCK"
- reason_codes: list[str]          # 표준 코드(아래 정의)
- metrics:
  - target: float | None
  - anchor: float | None
  - gap: float | None              # abs(target-anchor)/anchor
  - abs_diff: float | None         # abs(target-anchor)
  - thresholds:
    - soft_warn: float
    - hard_warn: float
    - block: float
  - evidence_score: int
  - anchor_confidence: float
- ui:
  - badge: "NONE"|"SOFT"|"HARD"|"BLOCK"
  - short_title: str               # 1줄
  - short_body: str                # 1~2줄
  - cta: "NONE"|"ADD_EVIDENCE"|"ADJUST_TARGET"|"CONFIRM_ANYWAY"|"LOCKED"
- ops:
  - deal_state_action: "NOOP"|"MARK_NEEDS_RECONFIRM"|"LOCK_TARGET"|"BLOCK_CREATE"
  - log_event: bool                # 항상 true 권장

---

## 2) 임계값(Guardrail SSOT 연결)

- 기본 임계값(ALL):
  - soft_warn = 0.15
  - hard_warn = 0.25
  - block     = 0.40   ✅ (요청: 40% block)

- evidence 보정:
  - relax_if_e_score_ge = 80  → 레벨 1단계 완화(최대 WARN_HARD까지)
  - tighten_if_e_score_le = 20 → 레벨 1단계 강화

- anchor 신뢰도 보정(선택):
  - anchor_confidence < 0.5 이면: 레벨 1단계 완화(단, BLOCK→WARN_HARD까지만)

※ 임계값은 “하드코딩 금지”. pricing.yaml 또는 project_rules에 두되 SSOT 링크 주석 필수.

---

## 3) 결정 로직(정식)

### 3.1 Anchor 없을 때(비동기 전)
- anchor_price is None:
  - target_price is None → level=ALLOW, reason=["ANCHOR_MISSING","TARGET_MISSING"]
  - target_price <= 0 → level=WARN_HARD, reason=["ANCHOR_MISSING","TARGET_INVALID"]
  - evidence_score <= 0 → level=WARN_HARD, reason=["ANCHOR_MISSING","EVIDENCE_MISSING"]
  - evidence_score <= 20 → level=WARN_HARD, reason=["ANCHOR_MISSING","EVIDENCE_LOW"]
  - else → level=ALLOW, reason=["ANCHOR_MISSING"]

UI:
- WARN_HARD: "근거를 추가해 주세요" + CTA=ADD_EVIDENCE
- ALLOW: 배지 없음

### 3.2 Anchor 있을 때(비동기 후)
- gap = abs(target-anchor)/anchor  (anchor<=0이면 ANCHOR_INVALID 처리)
- base_level:
  - gap >= block     → BLOCK
  - gap >= hard_warn → WARN_HARD
  - gap >= soft_warn → WARN_SOFT
  - else             → ALLOW
- reason_codes:
  - GAP_SOFT_WARN / GAP_HARD_WARN / GAP_BLOCK / GAP_OK

### 3.3 Evidence 보정
- evidence_score >= 80:
  - level을 1단계 완화
  - reason += ["E_SCORE_RELAXED"]
- evidence_score <= 20:
  - level을 1단계 강화
  - reason += ["E_SCORE_TIGHTENED"]

완화/강화는 다음 순서를 따른다:
ALLOW < WARN_SOFT < WARN_HARD < BLOCK

단, 완화 시 BLOCK은 최대 WARN_HARD까지만.

### 3.4 Anchor 신뢰도 보정(선택)
- anchor_confidence < 0.5:
  - level 1단계 완화(단, BLOCK→WARN_HARD)
  - reason += ["ANCHOR_LOW_CONFIDENCE"]

---

## 4) 상태 전이(Deal 제어)

### 4.1 적용 시점별 action

(A) 딜방 생성 시도(S1)
- level == BLOCK → deal_state_action="BLOCK_CREATE"
- level == WARN_HARD → "ALLOW_CREATE_WITH_CONFIRM" (UI 확인 체크 후 생성 허용)
- else → NOOP

(B) Target 업데이트(S2) / Anchor 업데이트(S3)
- level == BLOCK:
  - deal_state_action="LOCK_TARGET"
  - deal.status 또는 flag: needs_reconfirm = true
  - UI: "목표가 조정 또는 근거 추가 필요"
- level == WARN_HARD:
  - deal_state_action="MARK_NEEDS_RECONFIRM"
  - needs_reconfirm = true
- else:
  - needs_reconfirm = false (단, 운영 정책상 유지해도 됨)

※ “이미 열린 딜을 즉시 삭제/강제 종료”는 UX 리스크 큼 → 기본은 잠금/재확인.

---

## 5) reason_codes (표준)

필수 표준(변경 금지):
- ANCHOR_MISSING
- ANCHOR_INVALID
- ANCHOR_LOW_CONFIDENCE
- TARGET_MISSING
- TARGET_INVALID
- EVIDENCE_MISSING
- EVIDENCE_LOW
- GAP_OK
- GAP_SOFT_WARN
- GAP_HARD_WARN
- GAP_BLOCK
- E_SCORE_RELAXED
- E_SCORE_TIGHTENED

---

## 6) UI 규칙(딜/오퍼 화면 연결)

### 6.1 딜 상세 상단(딜방 목표가 영역)
- WARN_SOFT: 작은 노란 배지 "현실 가격과 다를 수 있어요"
- WARN_HARD: 주황 배지 + 1줄 안내 + CTA(근거 추가 / 목표가 수정)
- BLOCK: 빨강 배지 + 입력 잠금 + “조정 필요” 고정 노출

### 6.2 오퍼 랭킹 화면(딜 기준 리스트)
- 이 화면은 “헷갈리면 안 됨”이 1순위.
- 표시 최소 4개:
  1) 판매가(offer.price)
  2) 목표가 대비 %(offer_index_pct = offer/target*100)
  3) 남은수량
  4) 그룹(PREMIUM/MATCHING/BELOW)

- guardrail 설명/Anchor/근거는 여기서 길게 보여주지 않는다.
  - 딜 상태가 WARN_HARD/BLOCK이면 배지만 얹는다(예: "목표가 재확인 필요")

---

## 7) 이벤트/로그(핑퐁이 근거)

### 7.1 Evidence Pack 이벤트(필수)
- event_type: "evidence_pack.pricing_guardrail_v1"
- idempotency_key:
  - `evidence:pricing_guardrail_v1:deal:{deal_id}:anchor:{anchor_version_or_ts}`
- payload 최소:
  - deal_id, category
  - target_price, anchor_price
  - gap, abs_diff
  - evidence_score, anchor_confidence
  - level, reason_codes
  - thresholds
  - deal_state_action

---

## 8) 구현 연결 지점(어디서 호출할지)

다음 3곳에서 “동일 함수”를 호출해야 한다(중복 로직 금지):
1) Deal 생성/오픈 endpoint (S1)
2) Deal target_price 업데이트 endpoint (S2)
3) Anchor 비동기 결과 저장 후 hook/worker (S3)

이 함수는:
- evaluate_target_vs_anchor(input) → result
- result.level/action을 기반으로:
  - deal.needs_reconfirm flag
  - deal.target_locked flag (또는 status)
  - evidence event 기록
  - UI용 badge/short message 생성

---

## Appendix A) “짧은 문구” 템플릿(SSOT)

- WARN_SOFT:
  - title: "목표가 확인"
  - body: "외부 기준가격과 차이가 있을 수 있어요."
  - cta: "NONE"

- WARN_HARD:
  - title: "목표가 재확인 필요"
  - body: "외부 기준가격과 차이가 큽니다. 근거 추가 또는 목표가 조정이 필요해요."
  - cta: "ADD_EVIDENCE"

- BLOCK:
  - title: "목표가 조정 필요"
  - body: "외부 기준가격과 괴리가 너무 큽니다. 이 목표가로는 진행할 수 없어요."
  - cta: "LOCKED"

'@ | Out-File -Encoding utf8 "policy\docs\admin\ssot\target_vs_anchor_gap_ssot_v1.md"