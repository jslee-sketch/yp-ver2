# 수수료/포인트/커미션 정책 (Fees & Points)

정산만이 아니라 “돈이 움직이는 모든 규칙”이 정책이다.

정책 원문 기준으로도 정책 범주에 “수수료/포인트 정책”이 포함됨.

---

## 1) 돈의 흐름(큰 그림)

1) Buyer 결제
2) 거래 확정/환불 여부 결정
3) 플랫폼 정산 확정
4) 플랫폼 → Seller 정산
5) 동시에 Seller 정산 중 일부를 Actuator 커미션으로 지급

---

## 2) Actuator 커미션(SSOT)

- ActuatorCommission 테이블/모델이 존재(너가 DB 카운트로 확인함)
- 관련 라우트:
  - `/actuators/{actuator_id}/commissions`
  - `/actuators/commissions/payout-due`
  - `/actuators/me/commissions/settle`
  - `/actuators/commissions/{commission_id}/mark_paid`

권장 SSOT 필드(문서 표준):
- commission_rate_percent
- commission_amount
- gmv(기준 금액)
- status: PENDING|PAID|HOLD
- ready_at / paid_at
- 근거: settlement_id 또는 reservation_id

---

## 3) 플랫폼 수수료(SSOT 위치)

현재 트리에서 “단일 수수료 규칙표 파일”이 명시적으로 보이진 않으므로,
SSOT는 아래 계층으로 정의한다.

1) (권장) 거래 스냅샷(policy snapshot)에 기록
2) 없으면 `app/policy/api.py` / `app/policy/runtime.py`에서 런타임 정책으로 제공
3) 마지막에만 하드코딩(하지만 즉시 런타임으로 승격)

---

## 4) 포인트(SSOT)

- 포인트 관련 라우트:
  - `/points/{user_type}/{user_id}/transactions`
  - `/points/{user_type}/{user_id}/balance`

문서 SSOT로 고정할 항목:
- 적립/차감 이벤트 타입(구매/추천/환불/패널티)
- 환불 시 포인트 처리 규칙(현금/포인트/혼합)
- 악용 방지(반복 취소/결제 실패) 시 포인트/등급 영향(tiers.md와 연결)

---

## 5) Deposit(예약금) — DEPRECATED

정책 원문에서 “Deposit 개념 제거”가 명시됨.
따라서:
- 문서에서는 DEPRECATED로 고정
- 코드/라우트/테스트에서 재등장하면 회귀(regression)로 취급


---

## 6) Fee Snapshot(결제 시점 수수료 박제) — SSOT

### 왜 필요한가
- 정책이 바뀌어도 “과거 거래”는 결제 시점 기준으로 동일하게 재현 가능해야 한다.
- 따라서 결제(PAID) 시점에 수수료율과 관련 파라미터를 Reservation에 박제한다.

### 저장 위치
- `Reservation.policy_snapshot_json.fee_snapshot`

### 스키마(표준)
```json
{
  "fee_snapshot": {
    "policy_version": "v0",
    "policy_hash": "aa59fe0e1158d56c",
    "captured_at": "2026-01-04T06:47:47.026732+00:00",
    "keys": {
      "fees.platform_fee_rate": 0.035,
      "fees.pg_fee_rate": 0.033,
      "fees.vat_rate": 0.10,
      "fees.seller_fee_floor": 0.0,
      "fees.seller_fee_ceil": 1.0,
      "fees.points_earn_rate": 0.01
    }
  }
}



# Fees (수수료) 정책 — SSOT

이 문서는 역핑의 **수수료(Fees)** 정책을 정의한다.

- **SSOT 원칙**
  1) 결제 시점에 `Reservation.policy_snapshot_json.fee_snapshot` 으로 박제한다.
  2) 이후 정산/환불 계산은 “가능하면 snapshot을 우선” 사용한다.
  3) snapshot이 없을 때만 런타임 정책(YAML/Rule) getter로 폴백한다.

---

## 1) 용어 / 단위

- **rate**: 0~1 (예: 3.5% = 0.035)
- **percent**: 0~100 (예: 3.5% = 3.5)
- 본 프로젝트의 수수료 SSOT는 **rate(0~1)** 이다.

---

## 2) Fee Snapshot Schema

`Reservation.policy_snapshot_json` 내부에 다음 구조로 저장한다.

```json
{
  "fee_snapshot": {
    "policy_version": "v0",
    "policy_hash": "aa59fe0e1158d56c",
    "captured_at": "2026-01-04T06:47:47.026732+00:00",
    "keys": {
      "fees.platform_fee_rate": 0.035,
      "fees.pg_fee_rate": 0.033,
      "fees.vat_rate": 0.10,
      "fees.seller_fee_floor": 0.0,
      "fees.seller_fee_ceil": 1.0,
      "fees.points_earn_rate": 0.01
    }
  }
}
