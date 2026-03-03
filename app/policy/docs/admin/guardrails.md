 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# 운영/안전 가드레일 (Guardrails)

## 0. 목적
- 정책 변경은 “바로 반영”이 아니라 “안전 루프”로 운영한다.
- 핑퐁이는 변경 제안자이며, 적용은 관리자 승인/점진배포/롤백/감사로그가 필수다.

## 1. 플래그/가드레일(코드 근거)
- AUTO_SET_DEADLINES 같은 플래그는 운영 안전장치로 문서화 대상 28
- ENABLE_DEPOSIT_TRACKING 같은 “기록만 남는 레거시”도 DEPRECATED로 격리 29

## 2. 변경 안전 루프(표준)
- 제안(핑퐁) → 관리자 승인 → 적용(파라미터/룰/플래그) → 점진배포 → 모니터링 → 롤백 가능
- 모든 변경은:
  - before/after
  - 변경자(actor)
  - 사유(reason)
  - 근거(evidence_refs)
  - 영향 범위(scope)
  를 남긴다.

## 3. DEPRECATED 관리
- Deposit 관련 룰/키가 구버전에 남아있음 30
- “현재 정책상 제거”를 문서에 명시하고,
- 코드에서 다시 등장하면 테스트/검증 스크립트로 잡는다.

---

## 4) Rate Limiting (IP 기반)

### 4-1. 정책

| 경로 그룹 | 제한 | 비고 |
|-----------|------|------|
| 기본 (전체) | 60 req/분 | IP당 |
| `/ai/` | 10 req/분 | LLM 비용 보호 |
| `/v3_6/pingpong/` | 10 req/분 | AI 에이전트 |
| `/admin/` | 30 req/분 | 관리자 전용 |

### 4-2. 구현 위치

- `app/middleware/rate_limit.py` — `RateLimitMiddleware`
- 버킷 키: `{client_ip}:{matched_prefix}` (경로 그룹별 독립 버킷)
  - `/v3_6/reservations/` 와 `/v3_6/pingpong/` 는 **서로 다른 버킷**으로 관리됨
- 초과 시 `429 {"detail": "rate_limit_exceeded"}` 반환

### 4-3. 운영 규칙

- 테스트 시 `test_all.ps1` 연속 실행 → pingpong 10rpm 한도 초과 가능
- 서버 재기동 시 인메모리 카운터 리셋 (인메모리 방식)
- Redis 기반 분산 제한이 필요해지면 별도 모듈로 교체

---

## 5) 에러코드 표준화 (AppError)

### 5-1. 표준 예외 클래스

```python
# app/errors.py (예시)
class AppError(HTTPException):
    """역핑 표준 에러 — detail에 code 포함"""

class NotFound(AppError):       # 404
class Forbidden(AppError):      # 403
class BadRequest(AppError):     # 400
class AccountBanned(AppError):  # 403, code="account_banned"
class RateLimited(AppError):    # 429, code="rate_limit_exceeded"
class PolicyViolation(AppError):# 422, code="policy_violation"
```

### 5-2. 표준 에러 응답 형식

```json
{
  "detail": "이 계정은 현재 정지 상태입니다.",
  "code": "account_banned",
  "banned_until": "2026-03-15T00:00:00Z"
}
```

### 5-3. 에러 코드 목록

| 코드 | HTTP | 의미 |
|------|------|------|
| `not_found` | 404 | 리소스 없음 |
| `forbidden` | 403 | 권한 없음 |
| `account_banned` | 403 | 계정 정지 |
| `account_withdrawn` | 403 | 탈퇴 계정 |
| `rate_limit_exceeded` | 429 | 요청 한도 초과 |
| `policy_violation` | 422 | 정책 위반 (가격/상태) |
| `duplicate_prediction` | 400 | 이미 예측 제출함 |
| `deal_participant_restricted` | 400 | 딜 참여자 제한 |

---

## 6) 헬스체크 고도화

### 6-1. 엔드포인트

```
GET /health          → 기본 (서버 살아있는지만)
GET /health/deep     → 심층 (DB + OpenAI + 디스크 + 정책 파일)
```

### 6-2. /health/deep 점검 항목

```json
{
  "status": "ok",
  "db": { "ok": true, "latency_ms": 3 },
  "openai": { "ok": true, "latency_ms": 240 },
  "disk": { "ok": true, "free_gb": 12.4 },
  "policy_file": { "ok": true, "path": "app/policy/params/defaults.yaml" },
  "checked_at": "2026-02-28T12:00:00Z"
}
```

- **DB**: `SELECT 1` 쿼리 응답 여부
- **OpenAI**: `gpt-4.1-mini` 헬스 ping (비용 최소화 — 5초 캐시)
- **디스크**: `/` 여유 공간 1GB 이상
- **정책 파일**: `defaults.yaml` 파싱 가능 여부

### 6-3. 상태별 응답

| 상태 | HTTP |
|------|------|
| 전체 정상 | 200 |
| 일부 비정상 (degraded) | 200 + `status: "degraded"` |
| 서버 자체 오류 | 500 |

---

## 7) Policy Snapshot SSOT Guardrails (Reservation.policy_snapshot_json)

정책은 “지금의 정책”이 아니라 **거래 시점에 박제된 정책**이 1순위 SSOT다.  
따라서 `Reservation.policy_snapshot_json` 은 “SSOT 컨테이너”로 운영한다.

---

### 4.1 SSOT Container: Reservation.policy_snapshot_json (표준 스키마)

`policy_snapshot_json` 은 예약 단위로 “그 예약의 정책/수수료/등급”을 함께 박제한다.

    # ---------------------------------------------------------
    # ✅ Snapshot Guardrail (EVIDENCE ONLY)
    #
    # time_snapshot / exposure_snapshot 은 "결정(SSOT)"이 아니라
    # "그 시점의 계산 결과를 남기는 증빙(Evidence)" 용도다.
    #
    # - 이 값이 없거나(누락) UNKNOWN 이어도 예약 생성/결제 로직은 정상 동작해야 한다.
    # - 노출(Exposure) 정책의 실제 판단/차단은 'Offer 제출/노출 로직(랭킹/노출 API)'에서 수행한다.
    # - Reservation에 박제되는 exposure_snapshot은 CS/핑퐁이 설명/재현/디버깅을 위한 캐시+증빙이다.
    #
    # 따라서:
    # - exposure_snapshot.allowed=False 여도 create_reservation()은 실패시키지 않는다.
    # - wish_price 없는 경우(reason=wish_price_missing)는 정상 케이스로 취급한다.
    # ---------------------------------------------------------


#### 표준 키(✅ 고정)
- 오퍼 정책 스냅샷(취소 규칙)
  - `offer_policy_id`
  - `cancel_rule`
  - `cancel_within_days`
  - `extra_text`
- 결제 시점 수수료 스냅샷(SSOT)
  - `fee_snapshot`
- 결제 시점 등급/티어 스냅샷(SSOT)
  - `tier_snapshot`

#### 예시(JSON)
```json
{
  "offer_policy_id": 1,
  "cancel_rule": "A3",
  "cancel_within_days": 3,
  "extra_text": "배송완료 후 3일 이내 단순변심 취소 가능, 왕복배송비는 구매자 부담.",
  "fee_snapshot": {
    "policy_version": "v0",
    "policy_hash": "aa59fe0e1158d56c",
    "captured_at": "2026-01-04T06:47:47.026732+00:00",
    "keys": {
      "fees.platform_fee_rate": 0.035,
      "fees.pg_fee_rate": 0.033,
      "fees.vat_rate": 0.1,
      "fees.seller_fee_floor": 0.0,
      "fees.seller_fee_ceil": 1.0,
      "fees.points_earn_rate": 0.01
    }
  },
  "tier_snapshot": {
    "policy_version": "v0",
    "policy_hash": "aa59fe0e1158d56c",
    "captured_at": "2026-01-04T08:26:20.547973+00:00",
    "buyer": {
      "buyer_id": 1,
      "tier": "T4",
      "restricted": false,
      "total": 10,
      "paid": 4,
      "fulfillment_rate": 0.4,
      "deposit_percent": 0.0
    },
    "points": { "balance": 0, "grade": "BRONZE" },
    "seller": { "level": "Lv.2", "fee_percent": 0.025, "sold_count": 460, "rating": 4.0 }
  }
}