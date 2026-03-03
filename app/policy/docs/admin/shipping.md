 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# 배송/이행 정책 (Shipping / Fulfillment) — SSOT v3.6

배송은 거래 성립 이후의 신뢰를 좌우한다.
정확한 상태 전이 + 시간 정책 + 증빙이 결합되어야 한다.

---

## 1) 코드 SSOT 포인터

- 배송/이행 정책(함수/가드):
  - `app/crud.py`
    - `mark_reservation_shipped`
    - `confirm_reservation_arrival`
- (정책 파라미터/키)
  - `app/policy/shipping.py` (snapshot)
  - `app/policy/time.py` (time keys)

대표 라우트(존재 시):
- `/reservations/{reservation_id}/mark_shipped`
- `/reservations/{reservation_id}/arrival_confirm`
- `/v3_6/reservations/{reservation_id}/ship`
- `/v3_6/reservations/{reservation_id}/arrival-confirm`

---

## 2) 상태(정책집 표준)

권장 상태(명칭은 코드와 매핑):
- READY_TO_SHIP
- SHIPPED
- DELIVERED(선택)
- ARRIVAL_CONFIRMED(구매자 확정)
- AUTO_CONFIRMED(시간 경과 자동 확정)
- DISPUTE_OPEN(Freeze)

현재 CRUD 기준 핵심 가드:
- shipped/arrival_confirm은 Reservation이 **PAID** 여야 진행

---

## 3) 증빙(필수)

- shipped 처리 시:
  - 운송장/송장번호/발송 증빙(추가 필드가 있다면)
- arrival_confirm:
  - 구매자 확인(또는 자동확정)
- 분쟁 시:
  - 대화 로그 + 배송 증빙 + 상품 상태 증빙

---

## 4) Shipping Snapshot (Evidence)

- shipped 시점(또는 배송 이벤트 시점)에 `shipping_snapshot`을 Reservation.policy_snapshot_json에 기록한다.
- snapshot은 “배송/확정 시간 정책이 당시 무엇이었는지”를 재현하는 증빙이며,
  ActivityLog와 함께 CS/핑퐁이 설명 근거로 사용한다.
- snapshot은 멱등이어야 한다(이미 있으면 유지)

---

## 5) Snapshot 키 표준

`policy_snapshot_json.shipping_snapshot.keys`:

- `shipping.arrival_confirm_days`

---

## 6) 시간 정책 연결

- shipped 입력 지연 허용 시간
- arrival_confirm 윈도우
- 자동 확정 트리거

=> time.md의 키들과 연결하여 SSOT로 관리

---

## 7) 택배 API 연동 (SweetTracker)

### 7-1. 구조

```python
class TrackingProvider(ABC):
    def get_status(self, tracking_no, carrier_code) -> TrackingResult: ...

class MockTrackingProvider(TrackingProvider):
    """개발/테스트용 — 임의 상태 반환"""

class SweetTrackerProvider(TrackingProvider):
    """SweetTracker API 연동 (프로덕션)"""
    # GET https://info.sweettracker.co.kr/api/v1/trackingInfo
    # 인증: t_key 헤더
```

### 7-2. 연동 필드 (Reservation)

| 필드 | 설명 |
|------|------|
| `tracking_number` | 운송장 번호 |
| `carrier_code` | 택배사 코드 (예: `04` = CJ대한통운) |
| `delivery_auto_confirmed` | 자동 도착확인 여부 (bool) |
| `delivery_confirmed_source` | 확인 방법 (`buyer` / `auto_7day` / `api`) |

### 7-3. 환경 설정

```yaml
# app/config/ 또는 .env
TRACKING_PROVIDER: "mock"        # "mock" | "sweettracker"
SWEETTRACKER_API_KEY: "..."
SWEETTRACKER_MOCK_MODE: true     # 개발 환경에서 실 API 호출 방지
```

---

## 8) 배송 자동화 배치

### 8-1. 배송완료 자동 감지 (매 2시간)

- **주기**: 매 2시간
- **대상**: `SHIPPED` 상태 예약
- **동작**: SweetTracker API 조회 → `배송완료` 상태이면 `DELIVERED` 전환
- **가드**: Mock 모드에서는 실 API 호출 안 함

```python
# app/schedulers/delivery_checker.py
def run_delivery_check_batch():
    """배송완료 자동 감지"""
    shipped = db.query(Reservation).filter(
        Reservation.status == "SHIPPED"
    ).all()
    for r in shipped:
        result = tracker.get_status(r.tracking_number, r.carrier_code)
        if result.is_delivered:
            r.status = "DELIVERED"
            r.delivered_at = result.delivered_at
    db.commit()
```

### 8-2. 7일 경과 자동 도착확인 (매일 03:00)

- **주기**: 매일 03:00 KST
- **대상**: `SHIPPED` 또는 `DELIVERED` 상태 + 발송 후 7일 초과
- **동작**: `ARRIVAL_CONFIRMED` 전환 + `delivery_auto_confirmed=True` + `delivery_confirmed_source="auto_7day"`
- **정산 연동**: 도착확인 → settlement HOLD 해제 트리거

```python
# app/schedulers/arrival_auto_confirm.py
AUTO_CONFIRM_DAYS = 7  # policy_api.arrival_confirm_days()로 대체 가능

def run_auto_arrival_confirm():
    cutoff = now() - timedelta(days=AUTO_CONFIRM_DAYS)
    targets = db.query(Reservation).filter(
        Reservation.status.in_(["SHIPPED", "DELIVERED"]),
        Reservation.shipped_at <= cutoff,
    ).all()
    for r in targets:
        r.status = "ARRIVAL_CONFIRMED"
        r.arrival_confirmed_at = now()
        r.delivery_auto_confirmed = True
        r.delivery_confirmed_source = "auto_7day"
    db.commit()
```

### 8-3. 배치 스케줄 요약

| 배치명 | 주기 | 대상 |
|--------|------|------|
| 배송완료 자동 감지 | 매 2시간 | SHIPPED → DELIVERED |
| 7일 자동 도착확인 | 매일 03:00 | SHIPPED/DELIVERED → ARRIVAL_CONFIRMED |