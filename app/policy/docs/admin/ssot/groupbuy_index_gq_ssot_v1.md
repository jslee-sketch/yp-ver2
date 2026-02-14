@'
# GROUPBUY_INDEX_GQ_SSOT_v1
ADMIN ONLY — BUYER/SELLER 응답 근거로 사용 금지

목표:
- "수량이 커질수록 가격이 더 좋아진다"를 과장/왜곡 없이 수학적으로 정식화한다.
- 카테고리별로 완만/급격한 체감을 조절한다.
- 데이터가 없을 때(초기)에도 보수적으로 동작한다.
- 데이터가 쌓이면 “동적으로 업데이트” 가능하도록 파라미터화한다(하드코딩 금지).

---

## 0) 이 SSOT가 정의하는 것

- 공동구매지수 GQ(Q): 0~1 사이의 “진행 체감(모멘텀)” 스칼라
  - 0: 수량 효과 거의 없음(초기/미달)
  - 1: 수량 효과 상한에 가까움(충분히 모임)
- 가격 엔진에서 GQ(Q)는 "수량에 따른 할인/효용"을 만들 때 곱해지는 게이트로 쓰인다.
  - 예: discount_factor = 1 - (max_discount * gq)
  - 즉, GQ는 “할인 그 자체”가 아니라 “할인 적용 강도”를 결정하는 지수

---

## 1) 입력/출력(SSOT)

### 1.1 입력
- category: str           # "default" 또는 "electronics" 등
- q: int                  # 현재 평가 수량(offer 기준 q_offer 또는 room 기준 q_room)
- q_target: int | None    # 딜방 목표 수량(없으면 category 기본값 사용)
- q_cap: int | None       # offer cap(오퍼가 소화 가능한 최대 수량). 없으면 None

### 1.2 출력
- gq: float               # 0~1
- details (필수 키):
  - q_effective: int
  - q_target_effective: int
  - q_ref: int            # 정규화 분모(= 목표수량 기준)
  - x: float              # q_effective / q_ref
  - shape: str            # "logistic"
  - params_used: dict     # k, x0, max_discount, q_target_default, q_target_floor 등

---

## 2) 정규화 규칙(가장 중요)

공동구매 수량은 “딜방 전체”가 아니라 UX/정책상 다음 원칙을 따른다:

### 2.1 용어 정리
- q_target_or_room = max(1, q_target or category_default_q_target)
- offer_cap = q_cap (없으면 None)

### 2.2 offer preview 기준(기본)
- Q_effective = min(q_target_or_room, offer_cap)  (offer_cap이 있으면)
- Q_effective = q_target_or_room                  (offer_cap이 없으면)

※ 의미:
- "이 오퍼가 실제로 소화 가능한 수량" 기준으로 공동구매 체감을 계산한다.
- offer_cap이 작으면 GQ가 낮아지는 것이 정상(“많이 못 받는다”)

### 2.3 ranked list 기준(단순화)
- ranked list는 “헷갈리면 안 됨”이 1순위.
- ranked list에서는 GQ 계산/노출 금지.
- GQ는 상세/프리뷰에서만 계산/사용/노출한다.

---

## 3) GQ(Q) 함수(기본형) — S-curve(로지스틱)

### 3.1 기본형 정의
정규화된 x를 만든다:
- Q_ref = q_target_or_room  (즉 "목표수량을 1.0 지점"으로 둔다)  ✅ 고정 규칙
- x = Q_effective / Q_ref

그 다음 로지스틱을 사용한다:
- GQ = clamp( 1 / (1 + exp(-k * (x - x0))) , 0, 1)

권장 기본값(초기 보수적):
- x0 = 1.0         # 목표수량을 중심점으로
- k  = 4.0         # 기울기(너무 크면 과장됨)

### 3.2 직관(설명용)
- 목표수량 근처에서 체감이 가장 빠르게 올라가고
- 목표수량보다 훨씬 작으면 거의 0
- 목표수량보다 훨씬 크면 1에 수렴

---

## 4) 카테고리별 파라미터(SSOT)

카테고리마다 “할인체감 곡선”이 다르다. (배송/재고/유통/마진 구조 차이)

### 4.1 최소 카테고리 세트(초기)
- default
- electronics
- groceries
- furniture
- luxury

### 4.2 기본 제안값(보수적)
- default:     k=4.0, x0=1.0, q_target_default=6
- electronics: k=3.5, x0=1.0, q_target_default=8
- groceries:   k=5.0, x0=0.9, q_target_default=12
- furniture:   k=3.0, x0=1.1, q_target_default=4
- luxury:      k=2.5, x0=1.2, q_target_default=5

원칙:
- 생필품/소모재는 규모효과가 더 빨리 나므로 k를 키우고 x0를 약간 낮출 수 있다.
- 고가/명품은 규모효과가 완만하므로 k를 낮추고 x0를 높인다.

---

## 5) 안전장치(Guardrail 성격)

GQ는 신뢰를 해치면 안 되므로 다음을 고정한다:

### 5.1 q_target 하한
- q_target_or_room = max(q_target_or_room, q_target_floor)
- q_target_floor 기본값: 3

### 5.2 파라미터 하드코딩 금지
- pricing.yaml(params)에서 로드
- 코드에는 "SSOT 링크 주석"만

---

## 6) pricing_engine 연결 규칙(SSOT)

### 6.1 PriceInputs / PriceOutputs에서의 위치
- PriceInputs:
  - q: Q_effective
  - q_target: q_target_or_room
- PriceOutputs:
  - gq: float
  - details["gq"] 또는 details["groupbuy"] 아래에 shape/params 저장(필수)

### 6.2 가격 반영(가장 단순한 형태) ✅ 정식
- p_group = p_base * (1 - max_discount * gq)

여기서:
- p_base: 기준축(목표가/기준가)
- max_discount: 카테고리별 상한(초기엔 보수적으로 0.02~0.06 권장)

권장 기본 상한(초기):
- default:     0.05
- electronics: 0.04
- groceries:   0.06
- furniture:   0.03
- luxury:      0.02

과장 방지(강제 규칙):
- max_discount는 초기 운영에서 0.08 초과 금지(= 8% 상한)  ✅ hard cap
- 절대 0.10(10%) 이상으로 시작하지 않는다.

---

## 7) 동적 업데이트(추후) — 코드에 반드시 반영할 주석

향후 데이터가 쌓이면 다음으로 파라미터를 업데이트할 수 있다:
- k, x0, max_discount
- q_target_default
- 카테고리 세분화(예: electronics/phone, electronics/tv)

업데이트 방식(권장):
- “오퍼/딜 실제 성사 데이터” 기반으로
- 목표수량 대비 가격개선이 관측되는 구간을 회귀/최적화해 k/x0 추정

코드 주석 필수 문구(SSOT):
- TODO(dynamic): learn k/x0/max_discount from historical deals per category.
- TODO(dynamic): add Bayesian shrinkage so cold-start categories stay conservative.

※ 강제 원칙:
- 데이터가 적을수록(default로) 보수적 파라미터로 수축(shrink)되어야 한다.
- “학습된 파라미터”가 튀면 운영 신뢰가 깨지므로, 업데이트는 점진적/가드레일 필요.

---

## 8) UI/핑퐁이 설명 규칙(노출 최소화)

- Ranked list(딜 상세 오퍼 리스트): GQ 노출 금지
- Preview/Detail에서만:
  - "공동구매 기준선은 현재 수량(Q) 기준으로 계산" 정도만 1줄
  - 수치 gq(0.73) 같은 건 운영/디버그 모드에서만

핑퐁이 답변 규칙:
- “할인은 약속이 아니라 ‘가능성’의 강도”라는 표현 사용
- gq 자체를 말하지 말고 “지금은 아직/이제 충분히 모였다”로 해석만 제공

---

## 9) 구현 체크리스트(완료 기준)

- [ ] pricing.yaml에 category별 (k, x0, q_target_default, q_target_floor, max_discount) 추가
- [ ] pricing_engine에 compute_gq(category, q, q_target, q_cap) 구현
- [ ] compute_pricing에서 gq를 사용해 p_group 산출
- [ ] PriceOutputs.details에 gq/params 기록
- [ ] Preview pack에서 "공동구매 기준" 문구 1줄 유지(길게 금지)
- [ ] Ranked list에서 GQ 계산/노출 안 함

'@ | Out-File -Encoding utf8 "app\policy\docs\admin\ssot\groupbuy_index_gq_ssot_v1.md"