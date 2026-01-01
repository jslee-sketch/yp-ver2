# Policy audit (legacy references)

## getattr(R, ...)
- `DEPOSIT_FRESHNESS_ANCHOR` (3 files) :: app\routers\admin_deposit.py, app\routers\admin_policy.py, app\routers\offers.py
- `DEPOSIT_MAX_AGE_MINUTES` (3 files) :: app\routers\admin_deposit.py, app\routers\admin_policy.py, app\routers\offers.py
- `DEPOSIT_MIN_AMOUNT` (3 files) :: app\logic\trust.py, app\routers\admin_deposit.py, app\routers\admin_policy.py
- `DEPOSIT_REQUIRE_ALWAYS` (3 files) :: app\routers\admin_deposit.py, app\routers\admin_policy.py, app\routers\deposits.py
- `DEPOSIT_AUTO_REFUND_ON_PAY` (2 files) :: app\routers\admin_deposit.py, app\routers\admin_policy.py
- `RV` (2 files) :: app\logic\seller_fees.py, app\logic\trust.py
- `TIMELINE` (2 files) :: app\crud.py, app\routers\seller_offers.py
- `BUYER_POINT_PER_QTY` (1 files) :: app\routers\offers.py
- `DEFAULT_COOLING_DAYS` (1 files) :: scripts\verify_refund_execution_cooling_v36.py
- `DEPOSIT_AUTO_REFUND_SWEEP_PRE_ANCHOR` (1 files) :: app\routers\admin_deposit.py
- `PG_FEE_RATE` (1 files) :: app\crud.py
- `PG_FEE_RATE_BPS` (1 files) :: app\crud.py
- `PLATFORM_COMMISSION_RATE` (1 files) :: app\routers\offers.py
- `PLATFORM_FEE_RATE` (1 files) :: app\crud.py
- `PLATFORM_FEE_RATE_BPS` (1 files) :: app\crud.py
- `RECOMMENDER_REWARD_PT` (1 files) :: app\routers\reviews.py
- `REVIEW_WINDOW_DAYS` (1 files) :: app\routers\reviews.py
- `SELLER_LEVEL_RULES` (1 files) :: app\routers\reviews.py
- `VAT_RATE` (1 files) :: app\crud.py
- `VAT_RATE_BPS` (1 files) :: app\crud.py

## getattr(RV, ...)
- `ACTUATOR_FEE_BY_LEVEL` (2 files) :: app\logic\notifications_actuator.py, app\routers\offers.py
- `REVIEW_POLICY` (1 files) :: app\routers\reviews.py

## R.<CONST>
- `DEPOSIT_REQUIRE_ALWAYS` (2 files) :: app\routers\deposits.py, tests\test_deposit_freshness_e2e.py
- `RV` (2 files) :: app\logic\seller_fees.py, app\logic\trust.py
- `ACTUATOR_FEE_BY_LEVEL` (1 files) :: app\crud.py
- `BUYER_POINT_ON_PAID` (1 files) :: app\crud.py
- `BUYER_POINT_ON_REFUND` (1 files) :: app\crud.py
- `DEPOSIT_MIN_AMOUNT` (1 files) :: _t_min.py
- `TIMELINE` (1 files) :: app\crud.py

## RV.<CONST>
- `REVIEW_POLICY` (1 files) :: app\routers\insights_overview.py
