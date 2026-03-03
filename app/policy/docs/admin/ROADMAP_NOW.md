 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

## NOTE (중요)
- 본 문서(ROADMAP_NOW)는 2026-01-16 기준으로 "처음" 작성되기 시작했다.
- 이전에는 정책선언서/설명서/운영 매뉴얼이 체계적으로 존재하지 않았으므로,
  앞으로의 로드맵에는 "정책집/설명서 문서화"를 필수 트랙으로 포함한다.


# 역핑 SSOT STATUS (ROADMAP_NOW)

> 이 문서는 "방이 바뀌어도 안 끊기게" 현재 상태(SSOT)와 다음 작업을 박제한다.
> 변경 시 반드시 PR/커밋으로만 갱신한다.

## 0. 오늘 기준: 완료된 것 (SSOT)
- 정책 SSOT 진입점: `app/policy/api.py` + `app/policy/params/defaults.yaml` + loader 경유로 단일 진입점화
- 레거시 TIME_POLICY: 핵심 로직(crud/offers)에서 제거 완료 (핵심 로직은 SSOT만 참조)
- 정책집 DB: `policy_declarations` 정상 운영 중 (정책 “DB/문서”의 사실상 SSOT)

## 1. QA 파이프라인 (one-shot 완주 상태)
- fuzz suite: ✅
- real suite (infra 노이즈 분리 옵션 포함): ✅
- atom suite (faq_atom fastpath): ✅ `fail_count=0`

## 2. 정책 제안 루프 (Proposal → ApplyRun)
- 테이블/연결:
  - `pingpong_policy_proposals`
  - `pingpong_policy_apply_runs`
  - `policy_declarations`
- 반영 검증:
  - `kb.social` + time-of-day greeting/farewell → proposal apply로 반영됨
  - apply_run 기록 남음

## 3. Fastpath 라우팅 (현재 활성)
- `hard_oos`
- `term_resolver`
- `proposal_read_only`
- `social_fastpath`
- `faq_atom` ✅

## 4. Fastpath 우선순위 (고정 순서)
social → hard_oos → faq_atom → term_resolver → proposal_read_only → plan/llm

## 5. 지금 "다음 작업 3개" (이 문서의 핵심)
1) faq_atom 범위 확장: 배송비 → 포인트 → VAT/PG/플랫폼 수수료 분해 → 정산 지급 지연일
2) “한 줄 + 근거 정책키 1개” 답변 규격을 모든 정책 숫자 응답에 강제
3) 전역 로그 기반 자동 개선 루프: 불만 신호 → 후보 생성 → evidence pack 첨부 → proposal 루프 연결

## 6. 답변 규격 (Atom의 형식 규약)
- 출력: 한 줄(최대 1~2문장) + 근거 정책키(1개)만 포함
- 예:
  - "배송비는 예약당 X원 + 수량당 Y원으로 계산돼요. (policy: shipping_fee_per_reservation)"



## 7. ChatContext SSOT (오퍼/딜/셀러 결부용 메타 컨텍스트)

> 목적: 핑퐁이가 "정책 일반론"이 아니라, 사용자가 보고 있는 실제 대상(offer/deal/seller)을 기준으로 단답하도록
> UI/서버가 구조화된 컨텍스트를 주입한다. (텍스트 파싱은 폴백)

### 7.1 컨텍스트 스키마 (요청 메타데이터)
- `context.entrypoint` : enum (예: OFFER_DETAIL_CHAT | DEAL_ROOM_CHAT | GENERAL_CS_CHAT)
- `context.offer_id` : string|null
- `context.deal_id` : string|null
- `context.seller_id` : string|null
- `context.viewer_role` : enum (BUYER | SELLER | ADMIN | GUEST)
- `context.viewer_id` : string|null (role에 따라 buyer_id/seller_id/user_id)
- `context.locale` : string|null
- (선택) `context.offer_snapshot` : object|null
  - 서버가 신뢰할 수 있는 최소 스냅샷(예: offer.shipping 요약 타입/값)만 포함 가능
  - 단, "정답 근거"는 항상 DB 조회 결과(SSOT) 기준으로 한다. 스냅샷은 UX/속도 최적화 보조.

### 7.2 주입 원칙 (UX)
- "ID 입력칸 강제"를 기본으로 두지 않는다.
- 사용자가 특정 화면(오퍼 상세/딜방/셀러 오퍼관리 등)에서 채팅을 열면,
  프론트가 해당 화면의 대상 ID를 `context.*_id`로 자동 주입한다.
- 범용 CS 진입(GENERAL_CS_CHAT)처럼 대상이 없을 때만, 링크 붙여넣기/검색(오퍼 피커) 등을 제공한다.

### 7.3 해석 우선순위 (컨텍스트 > 텍스트)
1) 메타 컨텍스트에 `context.offer_id`가 있으면 이를 최우선 사용한다.
2) 없으면 메시지 텍스트에서 식별자(offer# / OFFER- / URL) 파싱으로 폴백한다.
3) 둘 다 없으면 "오퍼마다 다름" 단답 + 오퍼 링크/ID 요청으로 종료한다.

### 7.4 서버 검증 규칙 (필수 가드레일)
- 어떤 경우든, 핑퐁이 답변 전 서버가 다음을 검증한다:
  1) 존재 검증: 해당 offer/deal/seller가 실제 존재하는가
  2) 권한 검증: viewer_role/viewer_id가 해당 대상 정보를 볼 권한이 있는가
  3) 상태 검증: 비공개/삭제/종료 등 조회 제한 상태인지
- 검증 실패 시:
  - 정보 노출 금지, 중립 단답으로 종료
  - 예: "해당 오퍼를 확인할 수 없어요. 오퍼 링크를 다시 확인해 주세요."

### 7.5 “오퍼 기반 단답(데이터 근거)” 규약
- 오퍼마다 달라지는 항목(배송비/재고/구성/배송방식/반품조건 등)은 정책키가 아니라 데이터키 앵커를 사용한다.
- 표기 규격:
  - `(... anchor: offer.shipping)` 처럼 "근거 필드"를 1개만 박는다.
- 출력은 한 줄(최대 1~2문장)로 제한한다.

### 7.6 배송비(Shipping) 처리 규칙 (faq_atom 확장)
- 배송비는 플랫폼 정책이 아니라 오퍼 속성(offer-level)로 간주한다.
- 동작:
  - offer_id가 확인되면 DB에서 `offer.shipping`을 조회해 1줄로 렌더링한다.
  - offer_id가 없으면: "배송비는 오퍼마다 다름" + "오퍼 링크/ID 필요" 단답으로 종료한다.
- 예시:
  - "이 오퍼는 무료배송이에요. (anchor: offer.shipping)"
  - "이 오퍼 배송비는 3,000원 선불이에요. (anchor: offer.shipping)"
  - "배송비는 오퍼마다 달라요—오퍼 링크/ID를 주시면 바로 확인해드릴게요. (anchor: offer.shipping)"




## 8. offer.shipping SSOT (최소 스키마) + Atom 렌더링 규칙

> 목적: 배송비는 오퍼마다 다르므로 "정책"이 아닌 "오퍼 데이터"로 통일한다.
> 핑퐁이는 offer.shipping을 읽어 1줄로 렌더링한다. (anchor는 항상 offer.shipping)

### 8.1 최소 스키마 (권장)
- `offer.shipping.type` : enum
  - `FREE` : 무료배송
  - `FLAT_PREPAID` : 정액 선불(판매자/오퍼가 배송비를 고지)
  - `FLAT_COD` : 정액 착불(수령 시 결제)
  - `BY_QUOTE` : 별도 협의/현장 정산/추후 안내 (가격 고정 불가)
  - `SELLER_POLICY` : 셀러 정책/오퍼 상세 참조 (텍스트 고지 중심)
- `offer.shipping.fee_amount` : int|null
  - FLAT_* 인 경우 권장 (원 단위)
- `offer.shipping.extra_remote_amount` : int|null
  - 도서산간 추가비(있다면)
- `offer.shipping.note` : string|null
  - 셀러 고지(최대 60자 권장). 길면 Atom은 잘라서 표시.

### 8.2 Atom 렌더링 규칙 (1줄, 1~2문장 제한)
- 공통: 문장 끝에 `(anchor: offer.shipping)` 고정
- type별 텍스트:

1) `FREE`
- 출력: `이 오퍼는 무료배송이에요. (anchor: offer.shipping)`

2) `FLAT_PREPAID` (+ fee_amount 있으면 표시)
- fee_amount 있음:
  - `이 오퍼 배송비는 {fee_amount}원 선불이에요. (anchor: offer.shipping)`
- fee_amount 없음:
  - `이 오퍼 배송비는 선불 조건이며 금액은 오퍼 상세를 따라요. (anchor: offer.shipping)`

3) `FLAT_COD` (+ fee_amount 있으면 표시)
- fee_amount 있음:
  - `이 오퍼 배송비는 {fee_amount}원 착불(수령 시 결제)이에요. (anchor: offer.shipping)`
- fee_amount 없음:
  - `이 오퍼는 착불(수령 시 결제) 조건이에요. (anchor: offer.shipping)`

4) `BY_QUOTE`
- 출력: `배송비는 별도 안내/협의가 필요한 오퍼예요. (anchor: offer.shipping)`

5) `SELLER_POLICY`
- note 있으면:
  - `배송비는 셀러 고지 기준이에요: "{note}" (anchor: offer.shipping)`
- note 없으면:
  - `배송비는 오퍼 상세의 셀러 고지 기준이에요. (anchor: offer.shipping)`

### 8.3 보조 표기 규칙 (옵션, 과도한 설명 금지)
- `extra_remote_amount`가 있고, 1줄 제한을 해치지 않을 때만 짧게 덧붙인다:
  - 예: `... 도서산간 추가 {extra_remote_amount}원. (anchor: offer.shipping)`
- note는 60자 초과 시 잘라서 `...` 처리한다.
- 계산/예시는 기본 금지 (장황해지므로). 필요 시 UI에서 별도 표시.

### 8.4 데이터 누락/불완전 처리 (안전)
- type이 없거나 shipping 필드가 비어있으면:
  - `이 오퍼는 배송비 정보가 아직 확정되지 않았어요—오퍼 상세를 확인해 주세요. (anchor: offer.shipping)`



## 9. offer_id 텍스트 파싱 폴백 규칙 (ChatContext 없을 때)

> 원칙: 메타 컨텍스트(context.offer_id)가 없을 때만 "텍스트 파싱"을 시도한다.
> 파싱 성공 ≠ 신뢰. 파싱 후 반드시 서버에서 존재/권한/상태 검증을 통과해야만 답변한다.

### 9.1 파싱 우선순위 (강한 신호 → 약한 신호)
1) 오퍼 상세 URL/딥링크에서 offer_id 추출
2) "명시적 접두어" 패턴: offer#, 오퍼#, OFFER-, offer_id=
3) "라벨+값" 패턴: "오퍼 ID: 123", "offer id 123"
4) (옵션) "단독 토큰" 패턴: 메시지가 거의 ID만 포함하는 경우만 허용

### 9.2 허용 패턴 6종 (권장)
- P1. URL 쿼리 파라미터:
  - 예: `...offer_id=12345` / `...offerId=12345`
- P2. URL 경로형:
  - 예: `/offers/12345`, `/offer/12345`, `/o/12345`
- P3. 해시/샵 표기:
  - 예: `offer#12345`, `오퍼#12345`, `오퍼 12345`
- P4. 하이픈/프리픽스:
  - 예: `OFFER-12345`, `offer-12345`
- P5. 라벨+구분자:
  - 예: `offer id: 12345`, `오퍼ID=12345`, `오퍼 아이디 12345`
- P6. 단독 토큰(가장 약함, 제한적 허용):
  - 예: 메시지 전체가 `12345` 또는 `OFFER-12345` 처럼 "거의 ID만" 있을 때만

### 9.3 오탐 방지 가드레일 (필수)
- 길이 제한:
  - 숫자형 ID는 최소 4자리(예: 1000 이상)부터 허용 (너무 짧으면 오탐 증가)
- 주변 단어 체크:
  - "가격/원/개/수량/분/일" 등 숫자와 자주 붙는 단어가 가까이 있으면 단독 숫자 토큰(P6)은 무효 처리
- 전화번호/주문번호/송장번호 방지:
  - `010-` 등 전화번호 패턴은 무조건 제외
  - `주문`, `송장`, `운송장`, `tracking` 등 키워드 근처의 숫자는 offer_id로 취급하지 않음
- 다중 후보 처리:
  - 후보가 2개 이상이면 "확정 불가"로 처리하고 링크/ID 재요청(단답)으로 종료

### 9.4 파싱 후 검증 (필수, 서버)
- 파싱된 offer_id는 반드시 아래를 통과해야 함:
  1) 존재 검증: offer 존재
  2) 권한 검증: viewer_role/viewer_id가 조회 가능
  3) 상태 검증: 삭제/비공개/만료 등 제한 상태 확인
- 검증 실패 시:
  - `해당 오퍼를 확인할 수 없어요. 오퍼 링크/ID를 다시 확인해 주세요.` 로 종료




## 10. ShippingOfferBoundAtom (faq_atom 확장) - 핸들러 규격 + 테스트

> 목적: 배송비는 오퍼마다 다르므로, 오퍼를 특정할 수 있을 때만 DB 조회 기반 단답을 제공한다.
> 입력은 (user_text, context)이며, 출력은 1줄(+ anchor 1개)로 제한한다.

### 10.1 트리거 조건 (intent)
- 아래 키워드 중 하나 이상 포함 시 shipping intent 후보:
  - `배송비`, `택배비`, `배송`, `shipping`, `delivery fee`
- 단, "주소/도서산간/퀵/당일/해외" 등 지역·수단 복잡 질문은 기본 공식 안내 대신
  offer.shipping의 note/type만 단답(또는 오퍼 상세 확인)으로 처리한다. (장황 금지)

### 10.2 해석 우선순위 (Context > Parse)
1) `context.offer_id`가 있으면 이를 최우선 사용
2) 없으면 텍스트 파서(섹션 9)로 offer_id 후보 추출
3) offer_id를 확정할 수 없으면 폴백 단답 후 종료

### 10.3 서버 검증 (필수)
- offer_id 확보 후, 반드시:
  1) 존재 검증
  2) 권한 검증 (viewer_role/viewer_id)
  3) 상태 검증 (삭제/비공개/만료 등)
- 실패 시 중립 단답 후 종료 (정보 노출 금지)

### 10.4 렌더링 (offer.shipping 기반, 1줄)
- 섹션 8의 type 매핑표를 따른다.
- anchor는 항상 `(anchor: offer.shipping)` 1개만 표기한다.

### 10.5 폴백 단답 템플릿
- 컨텍스트/파싱 모두 실패:
  - `배송비는 오퍼마다 달라요—오퍼 링크/ID를 주시면 바로 확인해드릴게요. (anchor: offer.shipping)`
- 후보 다수:
  - `오퍼 ID가 여러 개로 보여요—확인할 오퍼 링크/ID 하나만 보내주세요. (anchor: offer.shipping)`
- 검증 실패:
  - `해당 오퍼를 확인할 수 없어요. 오퍼 링크/ID를 다시 확인해 주세요. (anchor: offer.shipping)`

### 10.6 핸들러 의사코드 (구현 기준)
- 입력: user_text, context(viewer_role/viewer_id 포함)
- 출력: AtomAnswer(text)

Pseudo:

1) if not is_shipping_intent(user_text): return None
2) if context.offer_id exists:
     offer_id = context.offer_id
   else:
     candidates = parse_offer_ids(user_text) # section 9
     if len(candidates) == 0: return fallback_need_offer_id()
     if len(candidates) >= 2: return fallback_multiple()
     offer_id = candidates[0]
3) offer = offer_repo.get(offer_id)
   if not offer: return fallback_invalid()
4) if not can_view_offer(context.viewer_role, context.viewer_id, offer):
     return fallback_invalid()
5) if offer.status in [DELETED, PRIVATE, ...]:
     return fallback_invalid()
6) shipping = offer.shipping
7) text = render_shipping_one_liner(shipping) # section 8
8) return AtomAnswer(text=text)

### 10.7 테스트 케이스 12개 (정상/오탐/권한/다중후보)
[정상]
T1. context.offer_id 있음 + shipping.type=FREE
- input: "배송비 얼마야?"
- expect: "무료배송" 1줄 + anchor: offer.shipping

T2. context.offer_id 있음 + FLAT_PREPAID fee_amount=3000
- input: "배송비 알려줘"
- expect: "3,000원 선불" 1줄 + anchor

T3. 텍스트에 offer#12345 포함 + FLAT_COD fee_amount=4000
- input: "오퍼#12345 배송비?"
- expect: "4,000원 착불" 1줄 + anchor

T4. URL path /offers/7777 포함 + BY_QUOTE
- input: "https://.../offers/7777 배송비 어떻게 돼?"
- expect: "별도 안내/협의" 1줄 + anchor

T5. SELLER_POLICY + note 60자 이하
- input: "OFFER-9999 배송비?"
- expect: note 포함 1줄 + anchor

[폴백/오탐 방지]
T6. 컨텍스트 없음 + 텍스트에 ID 없음
- input: "배송비 규칙 뭐야?"
- expect: "오퍼마다 달라요—링크/ID" 1줄 + anchor

T7. 다중 후보 (offer#111 + offer#222)
- input: "오퍼#111이랑 오퍼#222 배송비?"
- expect: "여러 개" 폴백 1줄 + anchor

T8. 단독 숫자지만 주변에 '원' 존재 (가격 오탐 방지)
- input: "배송비 3000원 맞아?"
- expect: ID로 파싱하지 않고 폴백(링크/ID 요청) 1줄 + anchor

T9. 전화번호 패턴 포함 (오탐 방지)
- input: "010-1234-5678 이 번호로 연락했는데 배송비?"
- expect: 폴백(링크/ID 요청) 1줄 + anchor

[검증 실패/권한]
T10. 존재하지 않는 offer_id
- input: "오퍼#999999 배송비?"
- expect: "확인할 수 없어요" 1줄 + anchor

T11. 권한 없음 (다른 비공개 오퍼)
- input: "오퍼#12345 배송비?"
- expect: "확인할 수 없어요" 1줄 + anchor

T12. status 제한(삭제/비공개/만료)
- input: "오퍼#12345 배송비?"
- expect: "확인할 수 없어요" 1줄 + anchor



## ✅ Settlement/Refund/Pay 파트 마감 (v3.6)

- Pay → Settlement 스냅샷 생성: OK (v3.6 / v3.5 모두 확인)
- Partial Refund → Settlement sync: OK (remaining_gross 기준 재계산)
- Full Refund → Settlement CANCELLED: OK (buyer_paid_amount=0, status=CANCELLED)
- Settlement pipeline:
  - refresh-ready: HOLD → READY (ready_at 기준)
  - approve: READY → APPROVED
  - bulk-mark-paid: APPROVED → PAID + paid_at 기록 확인

검증 결과(샘플):
- settlement_id=76: status=PAID, approved_at/paid_at 정상 기록
- status 분포: CANCELLED=38, HOLD=35, READY=2, PAID=1