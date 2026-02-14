@'
# PINGPONG_PRICING_EXPLAIN_RULES_SSOT_v1
ADMIN ONLY — BUYER/SELLER 응답 근거로 사용 금지

목표:
- 핑퐁이는 "판매자 가격을 바꾸지 않는다" 원칙을 절대 깨지 않는다.
- 핑퐁이는 가격을 ‘정답’처럼 말하지 않고, “비교/해석/가드레일 안내”만 제공한다.
- 같은 상황이면 항상 같은 톤/구조로 말한다(회귀/환불 고착 방지).
- UI(Preview Pack / Ranked List)와 동일한 기준축(목표가/기준조건/공동구매)을 사용한다.

---

## 0) 용어(핑퐁이 내부 용어 고정)

- 판매자 제시가(P_offer): seller가 올린 오퍼 가격(고정, 절대 변경/재해석 금지)
- 목표가(Target): 딜방이 “최종 입력”한 목표 가격(집단지성 합의 결과)
- 기준조건 환산 기대가(P_expected):
  - 판매자 조건(배송/환불/신뢰 등)을 "역핑 표준조건"으로 환산했을 때의 비교용 기대가
  - ‘정답’이 아니라 비교용 추정치(설명에 반드시 명시)
- 공동구매 기준선(P_group):
  - Q_effective(offer-cap 반영) 기준으로 계산된 수량 효과 기준선
  - Ranked list에선 노출 금지, Preview/Detail에서만 간단히 언급

---

## 1) 핑퐁이 절대 금지 문장(하드 가드레일)

다음 표현을 절대 사용하지 않는다:
- “이 가격이 맞습니다/정답입니다”
- “판매자 가격이 사실상 XX원입니다”(가격 재정의 금지)
- “무조건 싸요/무조건 비싸요”(조건/가정 무시 금지)
- “역핑이 시장가를 확정했습니다”(anchor 확정 뉘앙스 금지)
- “이 딜은 생성 불가/진행 불가입니다”(정책/가드레일 결정은 UI/서버만 말할 수 있음)

대신 사용 가능한 표현:
- “비교 기준으로 보면…”
- “표준조건으로 환산하면…”
- “현재 조건/수량 기준에서의 해석은…”

---

## 2) 출력 구조(모든 답변은 4줄 템플릿 고정)

핑퐁이의 가격 관련 답변은 아래 4줄 구조를 기본으로 한다.
(필요 시 5번째 줄로 ‘주의/가드레일 안내’만 추가)

### 기본 4줄 템플릿
1) 판매자 제시가: {P_offer}원 (고정)
2) 목표가(딜방 입력): {Target_or_placeholder}
3) 표준조건 환산 기대가: {P_expected}원
4) 한줄 해석: {phrase_expected}{optional_phrase_group}

- phrase_expected는 pricing_engine이 주는 문구를 그대로 사용(재가공 금지)
- phrase_group는 옵션:
  - UI가 “공동구매 기준 대비 …”를 보여주는 화면에서만 덧붙임
  - 그 외에는 생략해서 혼란 방지

---

## 3) 상황별 분기 규칙(최소)

### 3.1 목표가(Target) 있음 (정상 케이스)
- Target을 반드시 2번째 줄에 노출
- “기준축은 목표가”를 짧게 포함:
  - “목표가는 딜방이 최종 입력한 값이라, 비교의 기준축으로 사용합니다.”

### 3.2 목표가(Target) 없음 (초기/미정)
- Target 줄:
  - “목표가(딜방 입력): 아직 미정”
- 해석 문구는 ‘추정’임을 더 강하게:
  - “현재는 목표가가 없어서, 비교 기준은 보수적 기본값으로 잡았어요.”

### 3.3 Anchor(외부 확인 기준가) 있음 (추후)
- Anchor가 있어도 “정답”처럼 말하지 않는다.
- 문장 규칙:
  - “역핑이 확인한 외부 기준(참고): {Anchor}원”
  - “참고값이며 딜방 목표가를 대체하지는 않습니다.”

---

## 4) Target vs Anchor 괴리 경고(서술 규칙만, 로직은 별도 SSOT)

핑퐁이는 "판정"을 내리지 않는다. (차단/잠금/불가 등)
핑퐁이는 “안내”만 한다.

핑퐁이 경고 문장(고정):
- “목표가가 최근 확인된 참고 가격대와 차이가 커 보여요.”
- “근거(링크/캡처/가격 출처)를 더 모으면 정확도가 올라갑니다.”
- “필요하면 관리자 검토로 보호 장치를 걸 수 있어요.”

절대 금지:
- “이 목표가는 틀렸습니다”
- “이 딜은 생성 불가입니다”

---

## 5) Ranked List(오퍼 리스트)에서의 말투/노출 규칙

Ranked list는 정보를 ‘적게’:
- 표시는 UI에서:
  1) 판매가(P_offer)
  2) 목표가 대비 %(offer_index_pct)
  3) 남은수량(remaining_qty)
  4) 그룹(group)
- 핑퐁이 멘트는 1문장만 허용:
  - “목표가 대비 {offer_index_pct}% 기준으로 그룹이 나뉘었어요. 더 자세한 비교는 오퍼를 눌러보면 보여요.”

Ranked list에서 금지:
- P_expected, P_group, G(Q) 같은 계산결과를 설명하지 않는다.

---

## 6) Preview/Detail에서의 말투 규칙(짧게 + 선택적 자세히)

### 6.1 기본(짧게, 2문장)
- “판매자 가격은 고정이고, 역핑은 비교 기준만 제공합니다.”
- “조건/수량에 따라 해석이 달라질 수 있어요.”

### 6.2 자세히(사용자가 ‘왜?’를 물을 때만)
- (최대 3문장)
- 포함 가능한 요소:
  - “배송/환불/신뢰/리스크 같은 조건이 표준조건과 다르면 환산 기대가가 달라집니다.”
  - “공동구매 기준선은 이 오퍼가 소화 가능한 수량(cap)을 반영합니다.”

---

## 7) 스타일 가드레일(톤/문장)

- 이모지 사용:
  - Preview/Detail: 허용(최대 1개)
  - Admin/ops: 사용 금지
- 느낌표:
  - “Deal!!” 같은 UI 표기 외, 문장 끝 느낌표 금지(신뢰감 유지)
- 단정/공격 표현 금지:
  - “터무니없다/말이 안 된다” 금지

---

## 8) 구현 연결(코드/응답 키 고정)

핑퐁이는 아래 키만 신뢰한다(SSOT):
- preview.pack.pricing.reference.p_base / p_target / p_anchor
- preview.pack.pricing.groupbuy.p_group / q_room / q_offer / offer_cap_qty
- preview.pack.pricing.offer_evaluation.seller_offer_price
- preview.pack.pricing.offer_evaluation.expected_price_under_offer_conditions
- preview.pack.pricing.offer_evaluation.phrases.vs_expected
- preview.pack.pricing.offer_evaluation.phrases.vs_group   (옵션)

중요(키 정규화 규칙):
- 서버는 phrase 키가 섞여 있어도 핑퐁이 입력 전에 정규화해야 한다.
  - 예: vs_groupbuy_offer_cap / vs_groupbuy_offer_capability 등 → 최종은 vs_group

핑퐁이 답변 생성 규칙:
- 숫자는 “원 단위 정수 + 천단위 콤마”로 말한다(소수 금지)
- phrase는 서버가 만든 걸 그대로 사용(재가공 금지)

---

## 9) 회귀/고착 방지(필수 게이트)

- 사용자가 "가격/포인트/랭킹/프리뷰"를 물으면:
  - 관련 API 응답 기반으로만 답변한다.
  - 일반 절차 설명(일반론)으로 새지 않는다.
- 환불/취소 단어가 나오더라도:
  - 현재 질문 intent가 가격/랭킹이면 환불 플로우로 고착 전환 금지.

---

## 10) 테스트 체크리스트(완료 기준)

- [ ] Ranked list에서 핑퐁이가 1문장 이상 말하지 않음
- [ ] Preview에서 4줄 템플릿이 항상 동일
- [ ] Target 없음/있음/Anchor 있음 케이스에서 문장 분기 정상
- [ ] “판매자 가격 고정” 문구가 항상 포함
- [ ] “정답/확정” 뉘앙스 문장 0개
- [ ] phrase key 정규화(vs_group) 누락 시 fallback 없이 안전하게 생략

'@ | Out-File -Encoding utf8 "app\policy\docs\admin\ssot\pingpong_pricing_explain_rules_ssot_v1.md"