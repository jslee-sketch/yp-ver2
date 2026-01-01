# docs/policies/v3_6_refund_shipping_gate.md

# v3.6 배송비 환불 Gate (옵션B) — SSOT

## 목적
- 배송비를 환불에 포함할지 여부(allowed gate)만 결정한다.
- 배송비 금액은 Reservation.amount_shipping(SSOT) 기반 자동배정으로 계산되며,
  gate는 포함/제외만 제어한다.

## 입력(근거/로그 필드)
- cooling_state: BEFORE_SHIPPING / SHIPPED_NOT_DELIVERED / WITHIN_COOLING / AFTER_COOLING
- trigger: BUYER_CANCEL / SELLER_CANCEL / SYSTEM_ERROR / ADMIN_FORCE / DISPUTE_RESOLVE
- (참고) fault_party는 로깅/정산 귀책에 사용되지만, 옵션B gate는 trigger 중심으로 동작한다.

## 규칙(옵션B)
1) BEFORE_SHIPPING: 모든 trigger 허용
2) SHIPPED_NOT_DELIVERED / WITHIN_COOLING:
   - BUYER_CANCEL만 불허
   - 나머지 trigger는 허용
3) AFTER_COOLING:
   - DISPUTE_RESOLVE만 허용
   - 나머지는 불허
4) UNKNOWN: 불허

## 코드 SSOT 위치
- app/core/refund_policy.py
  - is_shipping_refundable_by_policy()

## 테스트/회귀 스크립트
- scripts/verify_refund_execution_cooling_v36.py
  - stage별(actor별) 검증 로그를 회귀 기준으로 사용

> NOTE:
> gate 판단은 trigger 기준이며, fault_party는 정산/로그 목적이다.