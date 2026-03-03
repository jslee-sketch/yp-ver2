# Pricing SSOT (Anchor / Base / Target)

## 목적
역핑의 가격 판단은 “기준값(Anchor/Base)”과 “희망값(Target)”을 분리해,
Anchor가 없어도 서비스가 진행되도록 설계한다.

---

## 핵심 용어
- Target: 구매자 희망가격(사용자 입력)
- Base: 임시 기준가격(서비스 진행용, clamp/내부벤치 혼합)
- Anchor: 비동기 기준가격(외부/내부 데이터 기반, 도착하면 교체/보정)
- Formula Output: 실제 추천/설명에 쓰이는 계산 결과(단, 결제 가격을 강제하지 않음)

---

## 원칙
1) Anchor는 늦게 와도 된다(없어도 flow 진행)
2) Base는 항상 존재해야 한다(결정론적 생성)
3) Target은 사용자의 의도이며, 시스템은 “왜 가능한지/불가능한지”를 설명한다
4) 가격 결과는 UI에서 사용자가 원할 때만 노출
5) 핑퐁이는 가격을 결정하지 않고, 계산 근거/화면 연결만 한다

---

## 데이터 우선순위
- Anchor가 존재하면: Anchor를 기준값으로 사용
- Anchor가 없으면: Base를 기준값으로 사용
- Target은 비교 대상(차이/괴리/합리성 설명용)

---

## 출력 형식(표준)
- base_used: Anchor|Base
- base_value: number
- target_value: number|null
- formula_low: number (공동구매 최저가)
- formula_conditional: number (조건 반영가)
- explain: 3줄 이내 요약 + 근거 링크(선택)

---

## Deal AI Helper 자동 연동 (POST /deals/ 통합)

### 개요

`POST /deals/` 호출 시 `anchor_price`가 없으면, 서버가 자동으로
`deal_ai_helper`(LLM + 네이버 쇼핑 API)를 호출하여 딜 레코드를 보강한다.

### 자동 채움 흐름

```
POST /deals/ (anchor_price 미입력)
    │
    ▼
crud.create_deal()  ← 딜 최소 정보로 생성
    │
    ▼
_run_ai_deal_helper(product_name, free_text)
    │   ① LLM 호출 → canonical_name, brand, suggested_options, conditions
    │   ② 네이버 쇼핑 API → naver_lowest_price, naver_brand
    │   ③ 가격 보강 → center_price = naver_lowest_price
    │
    ▼
deals 테이블 자동 업데이트:
    ├── anchor_price  ← naver_lowest_price
    ├── brand         ← LLM/네이버 추출 브랜드명
    ├── ai_product_key← canonical_name (검색용 정규화명)
    ├── option1~5     ← suggested_options (빈 슬롯만 채움)
    └── conditions    ← shipping_fee_krw, warranty_months, delivery_days 등
    │
    ▼
guardrail S1 실행 (anchor_price가 이제 존재)
```

### 옵션 selected_value 파싱

LLM 프롬프트가 사용자 입력에서 **구체적으로 명시된 값**을 `selected_value`로 추출한다.

```json
// 입력: "에어팟 프로 2 256GB 블랙 미개봉"
"suggested_options": [
  {"title": "용량", "selected_value": "256GB", "values": ["128GB", "256GB"]},
  {"title": "색상", "selected_value": "블랙", "values": ["화이트", "블랙"]},
  {"title": "상태", "selected_value": "미개봉", "values": ["미개봉", "개봉"]}
]
```

- `selected_value`: 사용자 입력에서 명시된 값 (없으면 `null`)
- `values`: 이 옵션에서 가능한 후보 목록
- deal 저장 시: `selected_value` 우선, 없으면 `values[0]` 사용

### 자동 채움 필드 SSOT

| 딜 필드 | 출처 | 조건 |
|---------|------|------|
| `anchor_price` | `price.naver_lowest_price` | 미입력 시만 |
| `brand` | LLM 또는 네이버 `naver_brand` | 항상 덮어씀 |
| `ai_product_key` | `canonical_name` | 항상 덮어씀 |
| `option1~5_title/value` | `suggested_options[0~4]` | 해당 슬롯이 null일 때만 |
| `shipping_fee_krw` | `conditions.shipping_fee_krw` | 미입력 시만 |
| `warranty_months` | `conditions.warranty_months` | 미입력 시만 |
| `delivery_days` | `conditions.delivery_days` | 미입력 시만 |
| `refund_days` | `conditions.refund_days` | 미입력 시만 |
| `extra_conditions` | `conditions.extra_conditions` | 미입력 시만 |

### 코드 위치

- `app/routers/deal_ai_helper.py` — `_run_ai_deal_helper(raw_title, raw_free_text)` (내부 호출용)
- `app/routers/deals.py` — `POST /deals/` 내 자동 호출 블록
- **비동기 원칙**: AI 호출 실패 시 `logging.warning`만 남기고 딜 생성은 정상 완료
- **anchor_price가 이미 있으면 AI 호출 스킵** (사용자 직접 입력 우선)
