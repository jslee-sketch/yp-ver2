# 역핑 정책/코드 정리 – 1차 인벤토리 (자동 스캔)

이 문서는 업로드된 `역핑자료.zip` 기준으로, **정책 중앙화(SSOT)** 작업을 시작하기 위한 1차 스냅샷입니다.

## 0) 현재 ‘정책 시스템’ 3종 (공존 중)

- **(A) Runtime 정책(코드가 직접 참조해야 하는 SSOT)**: `app/policy/params/policy_defaults.yaml` + `app/policy/params/schema.py` + `app/policy/runtime.py` + `app/policy/api.py`

- **(B) 레거시 설정/룰**: `app/config/project_rules.py` (R), `app/config/rules_v3_5.py` (RV)

- **(C) 정책 선언집(설명/근거, Pingpong용)**: DB 테이블 `policy_declarations` (모델 존재) + `crud.get_active_policies()`


핵심 방향: **A가 ‘실행 SSOT’, C가 ‘설명 SSOT(문서/근거)’**, B는 단계적으로 제거/축소.


## 1) 이미 중앙화된(PolicyBundle YAML에 존재) 필드

- `money.platform_fee_rate` = `0.05`
- `money.actuator_commission_rate` = `0.02`
- `money.pg_fee_rate` = `0.03`
- `time.payment_timeout_minutes` = `5`
- `time.cooling_days` = `7`
- `time.seller_decision_timeout_hours` = `48`
- `time.deal_deadline_hours` = `72`
- `time.offer_deadline_hours` = `48`
- `points_tier.points_earn_rate` = `0.01`
- `points_tier.points_expire_days` = `365`
- `points_tier.tier_window_days` = `90`
- `points_tier.tier_min_gmv` = `300000`

## 2) 코드에서 아직 레거시 R(project_rules)로 뽑아쓰는 키(getattr(R, ...))

- `DEPOSIT_FRESHNESS_ANCHOR` : 사용 파일 3개  | 예) admin_deposit.py, admin_policy.py, offers.py
- `DEPOSIT_MAX_AGE_MINUTES` : 사용 파일 3개  | 예) admin_deposit.py, admin_policy.py, offers.py
- `DEPOSIT_MIN_AMOUNT` : 사용 파일 3개  | 예) trust.py, admin_deposit.py, admin_policy.py
- `DEPOSIT_REQUIRE_ALWAYS` : 사용 파일 3개  | 예) admin_deposit.py, admin_policy.py, deposits.py
- `DEPOSIT_AUTO_REFUND_ON_PAY` : 사용 파일 2개  | 예) admin_deposit.py, admin_policy.py
- `RV` : 사용 파일 2개  | 예) seller_fees.py, trust.py
- `TIMELINE` : 사용 파일 2개  | 예) crud.py, seller_offers.py
- `BUYER_POINT_PER_QTY` : 사용 파일 1개  | 예) offers.py
- `DEPOSIT_AUTO_REFUND_SWEEP_PRE_ANCHOR` : 사용 파일 1개  | 예) admin_deposit.py
- `PG_FEE_RATE` : 사용 파일 1개  | 예) crud.py
- `PG_FEE_RATE_BPS` : 사용 파일 1개  | 예) crud.py
- `PLATFORM_COMMISSION_RATE` : 사용 파일 1개  | 예) offers.py
- `PLATFORM_FEE_RATE` : 사용 파일 1개  | 예) crud.py
- `PLATFORM_FEE_RATE_BPS` : 사용 파일 1개  | 예) crud.py
- `RECOMMENDER_REWARD_PT` : 사용 파일 1개  | 예) reviews.py
- `REVIEW_WINDOW_DAYS` : 사용 파일 1개  | 예) reviews.py
- `SELLER_LEVEL_RULES` : 사용 파일 1개  | 예) reviews.py
- `VAT_RATE` : 사용 파일 1개  | 예) crud.py
- `VAT_RATE_BPS` : 사용 파일 1개  | 예) crud.py

## 3) 코드에서 아직 레거시 RV(rules_v3_5)로 뽑아쓰는 키(getattr(RV, ...))

- `ACTUATOR_FEE_BY_LEVEL` : 사용 파일 2개  | 예) notifications_actuator.py, offers.py
- `REVIEW_POLICY` : 사용 파일 1개  | 예) reviews.py

## 4) 바로 ‘다음 이주 후보’ 추천(영향도/빈도 기준)

1) **플랫폼 수수료 계열**: `PLATFORM_FEE_RATE`, `PLATFORM_FEE_RATE_BPS`, `PLATFORM_COMMISSION_RATE` → `money.platform_fee_rate`로 단일화

2) **디파짓(예약금) 잔재 정책**: `DEPOSIT_AUTO_REFUND_*`, `DEPOSIT_FRESHNESS_ANCHOR` → 지금 설계에서 디파짓 제거했다면 ‘기능 플래그/레거시’로 격리(삭제 가능한지 판단)

3) **정산 지연일 정책**: 지금 `policy/api.py`에 함수는 있으나 `PolicyBundle`에는 없음 → `settlement` 섹션 신설 추천


## 5) 권장 폴더 정리(리팩터링 가이드)

- `app/policy/` 아래를 SSOT로 확정하고, 레거시(R/RV)는 `app/policy/legacy/`로 이동시키거나, 최소한 **‘레거시 전용’임을 명시**

- 신규 코드는 **절대 R/RV를 직접 import하지 않고**, `app.policy.api` 함수만 사용

- `policy_declarations`는 코드값(PolicyBundle)과 1:1 매핑되는 **설명 레이어**로 유지: `policy_key`(예: `money.platform_fee_rate`)를 키로 삼고, 운영자가 읽는 문서를 담음


## 6) 내일부터 시작할 때 ‘첫 작업’ 추천

1) (자동) 코드 스캔 리포트 생성 스크립트 추가 → 매일 diff 확인

2) `settlement` 정책을 PolicyBundle로 승격(스키마+YAML+api) → `routers/settlements.py`가 SSOT만 보게 만들기

3) 플랫폼 수수료 단일화(중복 상수 제거) → 정산/환불 계산 모두 동일 소스 참조

4) 전역로그 유틸(단일 함수)로 `event_logs` 삽입을 통합


