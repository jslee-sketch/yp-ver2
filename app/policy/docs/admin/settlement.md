ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# 정산 & 액추에이터 커미션 정책 (Settlement & Actuator Commission) — SSOT

이 문서는 결제 완료(PAID)된 예약(Reservation)에 대해 **정산 스냅샷(ReservationSettlement)**을 생성/갱신하고,
지급(배치) 및 **액추에이터 커미션(ActuatorCommission)** 처리까지 포함하는 **운영/정책 SSOT**이다.

> 핵심: 정산은 “정책(시간·분쟁·환불) + 숫자(수수료·부가세) + 배치(지급) + 감사로그”가 결합된 영역이다.

---

## 0) 한 줄 요약 (운영 관점)

- **정산 SSOT 금액**: `Reservation.amount_total` (goods + shipping 스냅샷)
- **정산 계산 엔진**: `policy_api.calc_settlement_snapshot(paid_amount, level_str)` 단일 경로
- **환불 후 정산 갱신**: `remaining_gross = amount_total - refunded_amount_total` 기준으로 **정산 스냅샷 재계산**
- **지급은 배치로 진행**하며, 쿨링/분쟁 상태에서는 HOLD(Freeze)로 묶인다.

---

## 1) 코드/라우터 SSOT 위치 (현재 기준)

> 실제 파일명/라우터는 리팩터링될 수 있으니 “역할” 기준으로 본다.

- 정산 계산(정책 API):
  - `app/policy/api.py` 의 `calc_settlement_snapshot(...)` (정산 계산 단일 진입점)
- 정산 스냅샷 생성/갱신(CRUD):
  - `app/crud.py` 의 `create_settlement_for_paid_reservation(...)`
  - `app/crud.py` 의 `create_or_update_settlement_for_reservation(...)` (있다면 동일 SSOT로 유지)
- 정산 조회/운영 라우터:
  - `/settlements/...` , `/admin/settlements/...` 계열
- 배치/스케줄 실행(예):
  - `scripts/run_settlement_batches.ps1`
  - OS 스케줄러(schtasks 등)로 주기 실행

---

## 2) 데이터 모델 & 상태(Status) 정의

### 2.1 ReservationSettlement (예약 정산 스냅샷)

- 목적: “지급 전/후 정산 결과”를 DB에 **스냅샷**으로 보존 (감사/분쟁/재현 가능)
- 대표 상태(예시):
  - `PENDING` : 생성됨(대기)
  - `READY` : 지급 가능 상태로 갱신됨
  - `APPROVED` : 승인됨(자동/수동)
  - `PAID` : 지급 완료
  - `HOLD` : 분쟁/환불/정책상 Freeze로 지급 보류
  - `CANCELLED` : 전액 환불 등으로 지급액 0 확정

> 주의: 실제 코드/DB에서 쓰는 enum/string은 다를 수 있으나, 의미는 위와 동일해야 한다.

### 2.2 ActuatorCommission (액추에이터 커미션)

- 목적: 셀러가 정산을 받을 때, 플랫폼이 지급한 금액(또는 정책상 기준액)에서
  **액추에이터 보상/커미션**을 계산하여 별도 레코드로 관리
- 대표 상태(예시):
  - `PENDING`
  - `PAID`

---

## 3) 정산 계산의 SSOT (가장 중요)

### 3.1 입력 금액 SSOT: paid_amount

정산 계산의 기준 금액은 원칙적으로 아래를 따른다.

1) **SSOT**: `paid_amount = Reservation.amount_total`  
   - 예약 생성/결제 시점에 goods + shipping 을 합산한 스냅샷
2) **최후 fallback(방어)**: (과거 데이터/스냅샷 비정상만)
   - `Offer.price * Reservation.qty`

> v3.6 철학상, 정산/환불/배송비 로직의 SSOT는 Reservation.amount_* 이다.

---

### 3.2 수수료/부가세 계산 규칙

정산 계산은 다음의 “순서/저장값”을 따른다.

1) PG 수수료  
   `pg_fee_amount = round(paid_amount * pg_fee_rate)`

2) 플랫폼 수수료(공급가 기준)  
   `platform_fee = round(paid_amount * platform_fee_rate_for_level(level))`

3) VAT  
   `platform_fee_vat = round(platform_fee * vat_rate)`  
   - **VAT는 platform_fee에만 적용**한다.

4) 플랫폼 총 커미션(저장값)  
   `platform_commission_amount = platform_fee + platform_fee_vat`

5) 셀러 지급액  
   `seller_payout = paid_amount - pg_fee_amount - platform_commission_amount`  
   - 음수면 0으로 클램프한다.

> 수수료율(rate)은 원칙적으로 **정책 스냅샷/정책 API**를 우선 사용하고,
> 없으면 런타임 기본값으로 폴백한다.

---

### 3.3 Settlement Snapshot Schema (정산 결과 구조)

정산 계산 결과는 아래 구조로 다룬다(코드 반환/DB 저장용).

```json
{
  "paid_amount": 300000,
  "pg_fee_amount": 9900,
  "platform_fee": 10500,
  "platform_fee_vat": 1050,
  "platform_commission_amount": 11550,
  "seller_payout": 278550
}
```

---

## 4) Phase 3: 지급 실행 (Payout Gateway)

> 기존 Phase 1(스냅샷 생성) · Phase 2(HOLD→READY 갱신)에 이어,
> Phase 3는 **실제 돈이 움직이는 지급 실행** 단계다.

### 4-1. 데이터 모델

#### payout_requests 테이블
```
payout_requests
├── id                  PK, auto
├── settlement_id       FK → reservation_settlements.id
├── seller_id           FK → sellers.id
├── amount              Integer                  (지급 요청액, 원)
├── status              String                   (PENDING / PROCESSING / PAID / FAILED)
├── gateway             String                   (mock / toss / ...)
├── gateway_tx_id       String, nullable         (PG 트랜잭션 ID)
├── requested_at        DateTime
├── paid_at             DateTime, nullable
└── fail_reason         Text, nullable
```

### 4-2. PayoutGateway 인터페이스

```python
class PayoutGateway(ABC):
    def execute(self, seller_id, amount, meta) -> PayoutResult: ...
    def status(self, tx_id) -> PayoutStatus: ...

class MockPayoutGateway(PayoutGateway):
    """개발/테스트용 — 무조건 성공 반환"""

class TossPayoutGateway(PayoutGateway):
    """Toss Payments 계좌 이체 API 연동 (프로덕션)"""
    # POST /v1/payouts (Toss API)
    # 인증: API 키 헤더
    # 응답: transaction_id, status
```

### 4-3. 지급 실행 API

```
POST /admin/settlements/payout/{settlement_id}
  → 단건 지급 실행 (settlement APPROVED → payout_requests PAID)

POST /admin/settlements/payout/bulk
  Body: { "settlement_ids": [1, 2, 3] }
  → 일괄 지급 실행

GET /admin/settlements/payout/status/{payout_request_id}
  → 지급 상태 조회
```

---

## 5) 정산 자동화 배치

### 5-1. 정산 갱신 배치 (HOLD → READY)

- **주기**: 매 6시간
- **대상**: `HOLD` 상태 + 쿨링 기간 경과 + 분쟁 없음
- **동작**: `HOLD → READY` 전환 + ActivityLog 기록
- **가드**: 분쟁(dispute) 열려있으면 스킵

```python
# app/schedulers/settlement_updater.py
def run_hold_to_ready_batch():
    """HOLD → READY 전환 배치"""
    eligible = db.query(ReservationSettlement).filter(
        ReservationSettlement.status == "HOLD",
        ReservationSettlement.cooling_expires_at <= now(),
    ).all()
    for s in eligible:
        if not has_open_dispute(s.reservation_id):
            s.status = "READY"
    db.commit()
```

### 5-2. 정산 자동 승인 배치 (READY → APPROVED)

- **주기**: 매일 02:00 KST
- **대상**: `READY` 상태
- **동작**: `READY → APPROVED` 전환
- **목적**: 수동 승인 없이도 익일 지급 파이프라인 진입 가능

### 5-3. 배치 스케줄 요약

| 배치명 | 주기 | SSOT 위치 |
|--------|------|-----------|
| HOLD→READY 갱신 | 매 6시간 | `app/schedulers/settlement_updater.py` |
| READY→APPROVED 자동 승인 | 매일 02:00 | `app/schedulers/settlement_approver.py` |
| 지급 실행 (APPROVED→PAID) | 매일 02:30 또는 수동 | `app/schedulers/payout_executor.py` |