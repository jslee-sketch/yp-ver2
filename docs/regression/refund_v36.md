# v36 regression run (baseline)
python .\scripts\verify_refund_execution_cooling_v36.py 305 --actors=dispute_resolve --stages=AFTER_COOLING --full
python .\scripts\verify_refund_execution_cooling_v36.py 305 --actors=dispute_resolve --full


# Refund Regression: verify_refund_execution_cooling_v36

## Status
- Frozen: ✅ YES (regression baseline)
- Verified OK on: 2025-12-22
- Purpose: refund execution behavior must not change unintentionally

## What this script verifies
- actors: dispute_resolve
- stages:
  - BEFORE_SHIPPING
  - SHIPPED_NOT_DELIVERED
  - WITHIN_COOLING
  - AFTER_COOLING
- cases:
  - PARTIAL (qty=3 중 일부 환불)
  - FULL (최종 CANCELLED)

## How to run (recommended)
### 1) Create a fresh test offer & reservation
- Create offer (PER_RESERVATION example)
  - `python scripts/create_offer_sqlite.py --shipping-mode PER_RESERVATION --per-reservation 10001`
- Create reservation
  - `python scripts/create_reservation_sqlite.py --offer-id <NEW_OFFER_ID> --qty 3 --buyer-id 2`

### 2) Run regression
- Single stage:
  - `python scripts/verify_refund_execution_cooling_v36.py <RESERVATION_ID> --actors=dispute_resolve --stages=AFTER_COOLING --full`
- All stages:
  - `python scripts/verify_refund_execution_cooling_v36.py <RESERVATION_ID> --actors=dispute_resolve --full`

## Pass criteria
- No exception
- All cases print `result: OK`
- Invariants:
  - refunded_qty and refunded_amount_total increase monotonically
  - FULL ends in status=CANCELLED
  - offer_sold_qty decreases by refunded qty

## Known failure modes (not logic bugs)
### NotFoundError: Offer not found for deal
Meaning:
- offer is not visible/valid in deal context (mapping/active/confirmed constraints)
Fix:
- Ensure offer is properly tied to deal and meets visibility conditions used by service queries.

## Freeze policy
- Do NOT modify v36 behavior.
- If changes are needed:
  - copy file to `verify_refund_execution_cooling_v37.py`
  - update docs and keep v36 as baseline