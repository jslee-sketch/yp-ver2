@'
# PRICING_GUARDRAIL_SSOT_v1
ADMIN ONLY — BUYER/SELLER 응답 근거로 사용 금지

본 문서는 역핑 가격축(Target/Anchor/Offer/Group)에서 **터무니없는 목표가(Target)**, **외부 기준가격(Anchor) 부재/불안정**, **조작/허위근거**로 인해
서비스 신뢰도가 깨지는 것을 방지하기 위한 “가드레일(차단/경고/허용)” SSOT이다.

---

## 0) 용어(SSOT)

- **Target (딜방 목표가)**: 딜방 참여자들이 토론/근거를 바탕으로 **최종 입력한 가격**. “사용자 입력값”이며 최종 의사결정축.
- **Anchor (외부 기준가격)**: 역핑이 외부 근거(링크/이미지/영수증/시장데이터 등)로 **비동기 산출**한 “현실 기준가격”.
  - Anchor는 “정답”이 아니라 **검증 가능한 기준선**.
- **Offer (판매자 제시가)**: 판매자 고정 가격. 역핑은 변경하지 않음.
- **Group price / G(Q)**: 공동구매 지수/조건 환산을 통한 비교축(별도 SSOT).
- **Gap**: 두 가격 사이 괴리율. 기본 정의:
  - `gap(A,B) = abs(A - B) / max(B, eps)`  (기본 기준은 B)
  - 본 문서에서는 주로 `gap(Target, Anchor)` 를 사용한다.

---

## 1) 목적(WHY)

- “역핑이 터무니없는 가격을 제시한다”는 신뢰도 리스크를 방지한다.
- “딜방 참여자들이 비현실적인 목표가를 고집”하는 상황에서,
  - 최소한의 안전장치로 **딜 생성 자체를 차단(Block)** 또는 **강한 경고(Warn)** 한다.
- Anchor는 비동기이므로, Anchor가 없더라도 서비스는 흐를 수 있어야 한다.
  - 단, Anchor가 도착하면 **재평가(후속 경고/차단)** 가능해야 한다.

---

## 2) 적용 범위(WHERE)

### 2.1 적용 시점
- (S1) 딜방 생성/오픈 시도 시점
- (S2) Target 업데이트(딜방 목표가 변경) 시점
- (S3) Anchor 업데이트(비동기 기준가격 도착/갱신) 시점
- (S4) 오퍼 노출/랭킹 표시 시점(표시용 경고 뱃지)

### 2.2 적용 대상
- Deal(딜방)
- DealPriceEvidence(근거 묶음; 링크/이미지/텍스트/신뢰도 점수)
- AnchorPriceResult(비동기 산출 결과)

---

## 3) 가드레일 레벨 정의(WHAT)

### 3.1 결과 타입
- **ALLOW**: 정상 진행
- **WARN_SOFT**: “참고 경고”(UI 배지/핑퐁이 안내)
- **WARN_HARD**: “강한 경고 + 추가 확인 필요”(체크박스/추가 근거 요구)
- **BLOCK**: 딜방 생성/목표가 확정/진행 차단

### 3.2 기준 메시지 원칙(UI/핑퐁이 공통)
- “사용자가 틀렸다”가 아니라 “근거가 부족/현실 괴리 가능성” 중심
- 가격 단정 금지: “정답” 표현 금지
- 표현 템플릿(요약):
  - WARN: “외부 기준가격 대비 목표가가 많이 낮습니다. 근거를 추가하거나 목표가를 조정해 주세요.”
  - BLOCK: “외부 기준가격 대비 목표가 괴리가 너무 큽니다. 딜방을 생성/유지할 수 없습니다.”

---

## 4) 핵심 규칙(정책 본문)

### 4.1 Anchor가 없을 때(비동기 전)
- Anchor 미도착 상태에서는 기본적으로 **ALLOW**.
- 단, 아래 조건 중 하나면 **WARN_HARD**:
  1) 근거(Evidence)가 전무하거나 신뢰점수(E_score)가 매우 낮음
  2) Target이 비정상 범위(예: 0원/극단값)로 입력됨
  3) 동일 카테고리 최근 분포(내부 벤치)와 극단적으로 벗어남 (옵션; 추후)

> 이유: Anchor가 없다고 딜방을 막으면 “초기 cold start”에서 서비스가 멈춘다.

### 4.2 Anchor가 도착했을 때(비동기 후) — 핵심
- 기본 비교: `gap = abs(Target - Anchor) / Anchor`
- 카테고리별 임계값에 따라 레벨을 결정한다.

#### 4.2.1 기본 임계값(보수적 시작; 네 요청 반영: 40% block)
- **BLOCK**: `gap >= 0.40`  (40% 이상 괴리)
- **WARN_HARD**: `0.25 <= gap < 0.40`
- **WARN_SOFT**: `0.15 <= gap < 0.25`
- **ALLOW**: `gap < 0.15`

> 주의: “너무 높음”도 동일하게 적용한다. (Target이 Anchor보다 지나치게 높아도 사기/무지/오입력 가능)

---

## 5) 카테고리별 튜닝(초기값)

초기에는 “보수적”으로 동일 임계값을 쓰되, 카테고리별로 점진 조정 가능하게 설계한다.
(코드에는 반드시 TODO/주석으로 “동적 튜닝” 지점 남길 것)

### 5.1 카테고리 그룹(예시)
- C1: 디지털/전자(스마트폰, 노트북, 모니터 등) — 가격정보 비교가 쉬움 → 더 엄격 가능
- C2: 생활/가전(청소기, 공기청정기 등) — 프로모션 다양 → 중간
- C3: 패션/잡화 — 사이즈/컨디션/정품변수 큼 → 완화 가능
- C4: 식품/신선 — 구성/중량/원산지 변수 큼 → 완화 가능

### 5.2 초기 테이블(SSOT 파라미터)
- 기본값(ALL):
  - soft_warn = 0.15
  - hard_warn = 0.25
  - block     = 0.40

- 향후(예시, 아직 적용 X):
  - C1(전자): block 0.35
  - C3(패션): block 0.50

---

## 6) Evidence(근거) 기반 보정(방향성)

Anchor/Target gap만으로 기계적으로 막으면 “근거가 탄탄한데도 막힘”이 생긴다.
따라서 Evidence score로 **경고 레벨을 상향/하향 보정**한다.

### 6.1 Evidence Score (E_score) 정의(0~100)
- 0: 근거 없음 / 텍스트만 / 출처 불명
- 30: 링크 1개 있으나 신뢰 낮음
- 60: 링크+이미지/영수증 등 2개 이상, 출처 양호
- 80+: 다수 출처, 가격 일관, 최근성 높음, 조작 가능성 낮음

### 6.2 보정 규칙(초기 간단 버전)
- E_score >= 80: 레벨을 1단계 완화(예: BLOCK→WARN_HARD, WARN_HARD→WARN_SOFT)
- E_score <= 20: 레벨을 1단계 강화(예: WARN_SOFT→WARN_HARD, WARN_HARD→BLOCK)

> 단, “BLOCK” 완화는 최대 WARN_HARD까지만 허용(= 완전 ALLOW로 풀지 않음).
> 이유: 오남용/조작 리스크.

---

## 7) 딜방 생성 차단 정책(핵심 UX)

### 7.1 생성 시점(S1)
- Anchor가 아직 없으면: 원칙적으로 ALLOW(단, 근거 0개면 WARN_HARD)
- Anchor가 있으면: 4.2 규칙 적용
  - BLOCK이면 “딜방 생성 불가”
  - WARN_HARD이면 “추가 근거 제출 or 목표가 조정 확인” 후 생성 허용

### 7.2 운영 중(S2/S3)
- 딜방이 이미 존재하더라도 Anchor 갱신으로 BLOCK 수준이 되면:
  - 즉시 강제 종료는 UX 리스크가 큼 → 기본 정책은 **“잠금(Lock) + 조정 요구”**
  - 상태:
    - Deal.status = `needs_reconfirm` (가칭) 또는 flag로 표현
    - 추가 행동: Target 수정/근거 추가/관리자 승인 중 하나 필요

---

## 8) 로그/이벤트(감사 + 핑퐁이 근거)

### 8.1 Evidence Pack 이벤트(필수)
- `evidence_pack.pricing_guardrail_v1`
  - idempotency_key: `evidence:pricing_guardrail_v1:deal:{deal_id}:anchor:{anchor_version}`
  - payload:
    - deal_id
    - category
    - target_price
    - anchor_price
    - gap
    - e_score
    - decision_level (ALLOW/WARN_SOFT/WARN_HARD/BLOCK)
    - reason_codes (배열)
    - timestamps

### 8.2 reason_codes (표준)
- `ANCHOR_MISSING`
- `EVIDENCE_LOW`
- `GAP_SOFT_WARN`
- `GAP_HARD_WARN`
- `GAP_BLOCK`
- `E_SCORE_RELAXED`
- `E_SCORE_TIGHTENED`

---

## 9) 구현 가이드(코드 반영 규칙)

### 9.1 SSOT → 코드 연결(필수)
- 본 문서의 임계값은 “하드코딩 금지”.
- 초기 구현은 다음 중 하나로:
  1) `app/policy/params/pricing.yaml`에 guardrail 섹션 추가 (권장)
  2) `app/config/project_rules.py`에 상수로 두되 “SSOT 링크 주석” 필수

### 9.2 비동기 Anchor 구조
- Anchor는 “없어도 진행” 가능해야 하며,
  - Anchor 도착 이벤트에서 “재평가” 로직을 실행한다.
- Anchor 불확실할 때(신뢰 낮음)는 E_score로 커버.

### 9.3 UI/오퍼랭킹 노출
- ranked 리스트에는 최소 다음만 표기 권장:
  1) 판매가(offer.price)
  2) 목표가 대비 %(offer_index_pct = offer / target * 100)
  3) 남은수량
  4) 그룹(PREMIUM/MATCHING/BELOW)
- guardrail 관련 메시지는 “상세/클릭 후” 또는 “딜방 상단 배지”로 노출

---

## 10) 변경 프로세스(PolicyOps)

- 임계값 변경은 반드시:
  - SSOT 수정 → 테스트(시뮬) → 점진 적용(플래그) → 로그 확인 → 롤백 가능
- 핑퐁이는:
  - 전역 로그 기반으로 “임계값 조정 제안”만 하고,
  - 적용은 관리자 승인 후.

---

## Appendix A) 기본 파라미터(초기)

- soft_warn = 0.15
- hard_warn = 0.25
- block     = 0.40  ✅ (요청 반영)
- relax_if_e_score_ge = 80
- tighten_if_e_score_le = 20
'@ | Out-File -Encoding utf8 "policy\docs\admin\ssot\pricing_guardrail_v1.md"