#!/usr/bin/env bash
set -euo pipefail
BASE=${1:-http://127.0.0.1:9000}
DEAL=${2:-1}
OFFER=${3:-46}
BUYER=${4:-10}

curl -s -X POST "$BASE/admin/deposit/update?key=DEPOSIT_REQUIRE_ALWAYS&value=true" >/dev/null
curl -s -X POST "$BASE/admin/deposit/update?key=DEPOSIT_AUTO_REFUND_ON_PAY&value=true" >/dev/null
curl -s -X POST "$BASE/admin/deposit/update?key=DEPOSIT_AUTO_REFUND_SWEEP_PRE_ANCHOR&value=true" >/dev/null
curl -s -X POST "$BASE/admin/deposit/update?key=DEPOSIT_FRESHNESS_ANCHOR&value=reservation" >/dev/null
curl -s -X POST "$BASE/admin/deposit/update?key=DEPOSIT_MAX_AGE_MINUTES&value=null" >/dev/null

curl -s -X POST "$BASE/offers/$OFFER/set_total_qs?total=999" >/dev/null
curl -s -H 'Content-Type: application/json' -d '{"amount":3000}' "$BASE/deposits/hold/$DEAL/$BUYER" >/dev/null
curl -s -H 'Content-Type: application/json' -d '{"amount":3000}' "$BASE/deposits/hold/$DEAL/$BUYER" >/dev/null

RID=$(curl -s -H 'Content-Type: application/json' -d "{\"deal_id\":$DEAL,\"offer_id\":$OFFER,\"buyer_id\":$BUYER,\"qty\":1,\"hold_minutes\":5}" "$BASE/reservations" | jq -r .id)
curl -s -o /dev/null -w '' -H 'Content-Type: application/json' -d "{\"reservation_id\":$RID,\"buyer_id\":$BUYER}" "$BASE/reservations/pay" || true
curl -s -H 'Content-Type: application/json' -d '{"amount":3000}' "$BASE/deposits/hold/$DEAL/$BUYER" >/dev/null
curl -s -H 'Content-Type: application/json' -d "{\"reservation_id\":$RID,\"buyer_id\":$BUYER}" "$BASE/reservations/pay" | jq -r .status
curl -s "$BASE/deposits/active/$DEAL/$BUYER" | jq .