# Pricing Formula SSOT (Low / Conditional)

## 목적
역핑의 가격 계산을 2개 공식으로 고정한다.
- 공동구매 최저가(LOW): “사람이 모이면 내려갈 수 있는 바닥”
- 조건 반영가(CONDITIONAL): “배송/환불/리드타임/품질 조건을 반영한 체감가”

---

## 1) 공동구매 최저가 포뮬러 (LOW)
입력:
- base_value (Anchor 또는 Base)
- group_size (현재 인원)
- target_group (목표 인원)
- elasticity (민감도 파라미터, SSOT param)

출력:
- formula_low

원칙:
- 인원이 늘수록 내려가되, 과도한 하락은 clamp로 제한
- base_value가 없으면 계산 불가(그래서 Base가 필수)

(초기 버전은 단순하게 시작하고, 추후 WTP/컨조인트로 고도화)

---

## 2) 조건 반영 가격 포뮬러 (CONDITIONAL)
입력:
- formula_low 또는 base_value
- shipping_days / shipping_method
- refund_policy_grade
- seller_tier / risk
- option_flags (예: 빠른배송, 검수 등)

출력:
- formula_conditional

원칙:
- 조건이 불리할수록 체감가는 올라간다(리스크 프리미엄)
- 조건이 좋을수록 체감가는 내려간다(신뢰 할인)
- 결과는 “결제 강제”가 아니라 “비교/설명”에 사용

---

## 3) UI 노출 원칙
- 가격 결과는 “사용자가 원할 때 열람”
- 핑퐁이는 결과를 인지하지만, 최종 결제 가격을 강제하지 않는다
- ID(딜/딜방/오퍼/예약)가 있으면 해당 프리뷰 화면으로 연결
