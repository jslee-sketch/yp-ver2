1) 용어/상태
ReservationStatus: PENDING, PAID, CANCELLED
Cooling stage:
BEFORE_SHIPPING, SHIPPED_NOT_DELIVERED, WITHIN_COOLING, AFTER_COOLING
Case:
PARTIAL: 일부 수량 환불(예: qty=3 중 1개)
FULL: 전량 환불(결과적으로 status=CANCELLED)
2) 금액 모델(정확히)
amount_total = amount_items + amount_shipping
shipping 계산은 offer의 shipping_mode에 따라:
PER_RESERVATION: amount_shipping = shipping_fee_per_reservation
PER_QTY: amount_shipping = shipping_fee_per_qty * qty
PARTIAL 환불 시 분배 규칙
아이템 단가 = price * refunded_qty
배송비 포함 분배 규칙은 현재 구현(로그 기준)대로 명시:
예: amount_total=310001이면 1개 환불이 103334 같이 정수 나눗셈 반올림/잔차 처리가 들어감
로그에 preview와 fallback이 동시에 찍히는 걸 보면:
preview_amount_total_refund (메타 기반)
fallback_amount_total_refund (계산 fallback)
문서에 “잔차 1원 처리 규칙”을 적어야 함:
✅ 권장 표준: 처음 n-1개는 floor, 마지막 1개에 잔차를 몰아준다 (또는 반대로)
지금 결과가 그 표준을 따르는지 문서에 “예시 로그”로 박제
3) 실행 규칙(상태/수량/카운터)
PARTIAL:
refunded_qty += k
refunded_amount_total += amount_total_refund
status 유지(PAID)
offer.sold_qty -= k
FULL:
최종적으로 refunded_qty == qty
status CANCELLED
offer.sold_qty는 환불 수량만큼 감소해서 0까지 가능
4) 검증 기준(“무에러 패스” 정의)
decision_supported == true
meta_supported == true
before/after의:
refunded_qty/amount_total 누적 일관성
status 전이 일관성
offer_sold_qty 감소 일관성
stage별 결과가 모두 result: OK
5) Known failures(로직 버그 아닌 케이스)
NotFoundError: Offer not found for deal
원인: offer가 deal 컨텍스트에서 조회/노출되지 않음(관계/활성/확정 조건)
해결: 테스트용 offer는 deal + confirmed/active + deadline 조건을 만족하게 생성



# Refund Execution Policy (Cooling Stages)

## Scope
- Reservation refund execution for dispute resolution flow.
- Applies to stages:
  - BEFORE_SHIPPING
  - SHIPPED_NOT_DELIVERED
  - WITHIN_COOLING
  - AFTER_COOLING

## Terms
- ReservationStatus:
  - PENDING: created but not paid
  - PAID: paid
  - CANCELLED: fully refunded / cancelled
- Case:
  - PARTIAL: partial qty refund (e.g. qty=3 중 1개 환불)
  - FULL: remaining qty refund -> final CANCELLED

## Amount model
### Total
- `amount_total = amount_items + amount_shipping`
- `amount_items = offer.price * reservation.qty`

### Shipping calculation (Offer)
- If `shipping_mode = PER_RESERVATION`
  - `amount_shipping = shipping_fee_per_reservation`
- If `shipping_mode = PER_QTY`
  - `amount_shipping = shipping_fee_per_qty * qty`

## Refund amount calculation
- Refund amount is computed from:
  - `preview_meta` (preferred) if available and supported
  - fallback calculation otherwise

### Integer rounding & remainder
- When total is not divisible by qty, refunds can differ by 1 due to rounding.
- Example:
  - amount_total=310001, qty=3
  - partial 1 unit refund can be 103334
  - fallback may show 103333 depending on rounding strategy

**Policy requirement (must be explicit in code/doc):**
- Choose ONE rounding strategy and keep it stable:
  - Option A: distribute floor to first (n-1) units, remainder to last unit
  - Option B: distribute ceil to first units, remainder adjusted later
- Regression tests (v36) are the current observed behavior baseline.

## State transitions
### PARTIAL
- refunded_qty += k
- refunded_amount_total += amount_total_refund
- status stays PAID
- offer_sold_qty decreases by k

### FULL
- final refunded_qty == reservation.qty
- status becomes CANCELLED
- offer_sold_qty decreases by remaining qty

## Verification invariants
- refunded_qty monotonic increasing
- refunded_amount_total monotonic increasing
- refunded_amount_total never exceeds amount_total
- FULL implies status=CANCELLED
- offer_sold_qty decreases exactly by refunded qty deltas

## Known operational failure modes
### NotFoundError: Offer not found for deal
- Cause: offer not discoverable in deal context (active/confirmed/deadline/relationship constraints)
- Fix: create test offers that satisfy service visibility conditions.