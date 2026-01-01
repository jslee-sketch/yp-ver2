# Evidence Pack Spec: refund_dispute_v1

## Purpose
To store structured evidence for:
- policy audits
- debugging
- PingPong agent proposals (admin approval loop)
- regression / anomaly detection

## Storage
- JSON (single object)
- Recommended: NDJSON append (1 line per evidence pack) OR DB JSON column (activity_log.meta)

## Schema (v1)

### Top-level
- evidence_pack_version: "refund_dispute_v1"
- event_time: ISO8601 with timezone
- context:
  - actor
  - stage
  - case
- entities:
  - reservation: ids, qty, statuses
  - offer: shipping params + counters
- amounts:
  - amount_total
  - amount_shipping
  - refund:
    - amount_total_refund
    - refunded_qty_delta
  - source:
    - expected_source
    - preview_amount_total_refund
    - fallback_amount_total_refund
    - meta_supported
- checks:
  - decision_supported
  - invariants_ok
- trace:
  - pg_tid
  - run_id
  - notes[]

## Example
```json
{
  "evidence_pack_version": "refund_dispute_v1",
  "event_time": "2025-12-22T14:43:51+09:00",
  "context": { "actor": "dispute_resolve", "stage": "AFTER_COOLING", "case": "PARTIAL" },
  "entities": {
    "reservation": {
      "id": 307,
      "buyer_id": 2,
      "offer_id": 4,
      "qty": 3,
      "status_before": "PAID",
      "status_after": "PAID"
    },
    "offer": {
      "id": 4,
      "deal_id": 1,
      "seller_id": 1,
      "price": 100000.0,
      "shipping_mode": "PER_RESERVATION",
      "shipping_fee_per_reservation": 10001,
      "shipping_fee_per_qty": 0,
      "sold_qty_before": 3,
      "sold_qty_after": 2
    }
  },
  "amounts": {
    "amount_total": 310001,
    "amount_shipping": 10001,
    "refund": { "amount_total_refund": 103334, "refunded_qty_delta": 1 },
    "source": {
      "expected_source": "preview_meta",
      "preview_amount_total_refund": 103334,
      "fallback_amount_total_refund": 103333,
      "meta_supported": true
    }
  },
  "checks": { "decision_supported": true, "invariants_ok": true },
  "trace": {
    "pg_tid": "DUMMY_PAY_reservation:307",
    "run_id": "verify_refund_execution_cooling_v36",
    "notes": []
  }
}