 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# 환불/분쟁 정책 (Refund & Dispute) — SSOT v3.6

환불은 “감정”이 아니라 “증거/정책/시간”으로 처리해야 CS 비용이 줄고,
핑퐁이도 같은 결론을 낼 수 있다.

이 문서는 **환불/분쟁의 SSOT(결정 지점)** 과 **Evidence(스냅샷/로그)** 를 분리해,
운영/디버깅/CS 설명이 흔들리지 않도록 고정한다.

---

## 0) 한 줄 요약

- **SSOT(결정)**: 환불 계산/허용/배송비 포함 여부는 `refund_policy + crud preview/refund 로직`이 결정한다.
- **Evidence(증빙)**: `Reservation.policy_snapshot_json.refund_snapshot`은 “그 시점 정책 파라미터”를 박제한다.
- **추적(로그)**: ActivityLog는 “무슨 일이 일어났는지”를 남긴다(리플레이/통계/정책 튜닝).

---

## 1) 코드 SSOT 포인터(현재 트리)

### 1-1) 환불 정책 엔진/규칙(SSOT)
- `app/core/refund_policy.py`
  - `compute_cooling_state(...)`
  - `is_shipping_refundable_by_policy(...)` (배송비 환불 gate / 옵션B)
  - `RefundPolicyEngine` (귀책/정산 상태에 따른 결정)

### 1-2) 환불 Preview / 계산(SSOT)
- `app/crud.py`
  - `preview_refund_for_paid_reservation(...)`
    - 부분환불 수량(qty) 처리
    - 배송비 자동배정(Reservation.amount_shipping SSOT)
    - override + cap
    - shipping gate 적용
    - preview 로그(Event/Evidence Pack)
    - refund_snapshot 박제(best-effort, 멱등)
  - `preview_refund_for_reservation(...)` (admin 라우터 호환 래퍼)

### 1-3) 관리자 프리뷰 API
- `app/routers/admin_refund_preview.py`
  - `GET /admin/refund/preview?reservation_id=...&fault_party=...&trigger=...`

### 1-4) 실제 환불/취소(집행 SSOT)
- (존재 기준)
  - `/reservations/force_refund` (운영 강제)
  - `refund_paid_reservation(...)` 등 실제 돈/상태 변경 CRUD

---

## 2) 분쟁(Dispute) 라우트(존재 확인)

- `/v3_6/{reservation_id}/dispute/open`
- `/v3_6/{reservation_id}/dispute/close`

분쟁이 열리면:
- settlement/commission HOLD 가능
- shipping/arrival_confirm 전이도 보류 가능(Freeze)

> “분쟁”은 귀책이 확정되지 않은 상태(DISPUTE)로 취급할 수 있으며,
> 환불은 DISPUTE_RESOLVE 같은 트리거에서 확정 처리하는 것이 안전하다.

---

## 3) Freeze(보류) 원칙

- 분쟁/차지백/의심 거래는 “자동 확정/정산”을 멈춘다.
- HOLD 상태는 시간이 지나면 자동 해제되는 것이 아니라,
  1) 증빙 확보
  2) 관리자 판단
  3) 정책 기준 충족
  이 3가지로 해제된다.

---

## 4) Cooling(쿨링) 상태 SSOT

쿨링 상태는 `compute_cooling_state(...)` 결과를 SSOT로 한다.

- BEFORE_SHIPPING: 결제는 되었지만 발송 전
- SHIPPED_NOT_DELIVERED: 발송은 했지만 도착/구매자 확인 전
- WITHIN_COOLING: 도착(또는 수령확정) 후 쿨링 기간 이내
- AFTER_COOLING: 도착(또는 수령확정) 후 쿨링 기간 경과
- UNKNOWN: 판단 불가

### 4-1) 쿨링 기준일
- 원칙: `arrival_confirmed_at` 기준
- fallback: `delivered_at` (arrival_confirmed_at이 없을 때)

### 4-2) cooling_days 결정 우선순위(SSOT)
1) `Reservation.policy_id` 로 연결된 `OfferPolicy.cancel_within_days`
2) `OfferPolicy.offer_id` 로 조회한 `cancel_within_days`
3) `policy_api.cooling_days()`
4) `DEFAULT_COOLING_DAYS` 안전 fallback

(음수/과대 값은 가드로 보정)

---

## 5) 배송비 환불 Gate(옵션B) — SSOT

배송비를 “환불에 포함할지 여부”는 `is_shipping_refundable_by_policy(...)`를 SSOT로 한다.

**옵션B 규칙(요약)**

1) BEFORE_SHIPPING:
- 모든 trigger에 대해 배송비 환불 허용

2) SHIPPED_NOT_DELIVERED / WITHIN_COOLING:
- BUYER_CANCEL만 불허
- SELLER_CANCEL / SYSTEM_ERROR / ADMIN_FORCE / DISPUTE_RESOLVE 는 허용

3) AFTER_COOLING:
- DISPUTE_RESOLVE만 허용
- 그 외는 불허

4) UNKNOWN:
- 보수적으로 불허

> 참고: “허용 여부(gate)”와 “금액 계산”은 분리한다.  
> 금액은 preview에서 자동배정/override/cap로 계산되며, gate가 False면 최종 배송비 환불액은 0이다.

---

## 6) 부분환불(Quantity) SSOT

- 환불 수량은 `Reservation.qty`, `Reservation.refunded_qty` 기반으로 산정한다.
- remaining = qty_total - already_refunded
- `quantity_refund` 미입력 시 remaining 전체
- 입력이 remaining을 초과하면 remaining으로 캡

---

## 7) Refund Snapshot (Evidence) — “박제” 의미

### 7-1) 박제가 의미하는 것
`Reservation.policy_snapshot_json.refund_snapshot`은
“그 시점의 환불 관련 정책 파라미터”를 Reservation에 기록해두는 것이다.

- **SSOT(결정)**: refund_policy / preview 로직
- **Evidence(재현 근거)**: refund_snapshot + shipping_snapshot + time_snapshot + activity_log

즉,
- 나중에 정책값이 바뀌더라도,
- 과거 예약 케이스를 “당시 정책 기준”으로 설명/재현할 수 있다.

### 7-2) 멱등 규칙(중요)
- `refund_snapshot`이 이미 있으면 **재기록하지 않는다**
  - captured_at이 고정되어야 “박제”가 된다.

### 7-3) 저장 위치
- `Reservation.policy_snapshot_json["refund_snapshot"]`

---

## 8) Refund Snapshot 표준 키

`policy_snapshot_json.refund_snapshot.keys`:

- `refund.dispute_hold_days`

추가 키가 필요해지면 `CANON_KEYS`에 확장한다.

---

## 9) ActivityLog(근거) 표준

핑퐁이/CS 설명을 위해 환불 preview/실행은 로그를 남기는 것을 권장한다.

권장 필드:
- actor_type: buyer|seller|admin|system|agent
- actor_id
- event_type:
  - `refund.preview.v36`
  - `evidence_pack.refund_dispute_v1`
  - `refund.executed.*` (실집행 시)
- buyer_id / seller_id / deal_id / offer_id / reservation_id
- meta(JSON): preview 계산값, shipping gate 결과, override 정보 등
- policy_snapshot_ref(선택): meta에 policy_version/hash를 담아도 됨

---

## 10) 운영/CS/핑퐁이 설명 템플릿

아래 순서대로만 말하면 결론이 흔들리지 않는다.

1) **현재 상태**
- 예약 상태(PAID/…)
- 배송 상태(shipped/delivered/arrival_confirmed)
- 분쟁 여부(dispute open?)

2) **환불 가능 여부**
- cooling_state(SSOT)
- trigger/fault_party(입력 or actor 매핑)
- shipping gate 결과(배송비 포함 여부)

3) **금액**
- 상품 환불액(수량×단가)
- 배송비 환불액(자동배정/override/cap + gate)
- 총 환불액

4) **근거**
- ActivityLog 이벤트
- Reservation policy_snapshot(refund/shipping/time)
- (필요 시) offer_policy.cancel_within_days

5) **다음 단계**
- 자동 처리(있다면 트리거/시간)
- 관리자 검토 필요 여부
- 필요한 증빙(사진/운송장/대화 로그)

---

## 11) 정리

- refund_policy/preview 로직이 **결정(SSOT)** 이다.
- refund_snapshot은 **증빙(Evidence)** 이다.
- ActivityLog는 **추적/통계/정책 튜닝**을 위한 이벤트 기반 근거다.

따라서 “스냅샷을 박제한다”는 것은
환불 계산을 바꾸는 것이 아니라,
**나중에 설명/재현 가능한 근거를 Reservation에 남긴다**는 뜻이다.

---

## 12) 신고/클레임 시스템 (Reports)

### 12-1. reports 테이블

```
reports
├── id                  PK, auto
├── reporter_id         Integer              (신고자 buyer/seller/actuator id)
├── reporter_type       String               (buyer / seller / actuator)
├── target_type         String               (deal / offer / reservation / user)
├── target_id           Integer
├── reason_code         String               (fraud / fake_offer / abuse / spam / other)
├── description         Text, nullable       (상세 내용)
├── status              String               (PENDING / REVIEWED / RESOLVED / DISMISSED)
├── resolution          Text, nullable       (처리 결과)
├── created_at          DateTime
├── reviewed_by         String, nullable
└── reviewed_at         DateTime, nullable
```

### 12-2. 신고 접수 API

```
POST /reports
Body: {
  “target_type”: “reservation”,
  “target_id”: 403,
  “reason_code”: “fraud”,
  “description”: “배송 안 됐는데 배송완료로 처리됨”
}
Response: { “id”: 12, “status”: “PENDING” }
```

### 12-3. 관리자 신고 처리 API

```
GET /admin/reports
  → 신고 목록 (status/reason 필터)

POST /admin/reports/{id}/resolve
Body: {
  “resolution”: “셀러 경고 처리. 반복 시 계정 정지.”,
  “action”: “seller_warning”   // warn / ban / dismiss
}
```

### 12-4. 신고 reason_code 표준

| 코드 | 설명 |
|------|------|
| `fraud` | 사기 / 허위 거래 |
| `fake_offer` | 허위 오퍼 (재고 없음, 가격 조작) |
| `abuse` | 욕설 / 협박 |
| `spam` | 광고성 메시지 |
| `duplicate` | 중복 딜/오퍼 |
| `other` | 기타 |

---

## 13) 이미지 업로드 (증거 첨부)

### 13-1. uploaded_files 테이블

```
uploaded_files
├── id                  PK, auto
├── uploader_id         Integer
├── uploader_type       String               (buyer / seller / admin)
├── file_key            String               (S3/로컬 경로)
├── original_name       String
├── mime_type           String               (image/jpeg, image/png, ...)
├── size_bytes          Integer
├── purpose             String               (report_evidence / dispute / profile)
├── ref_type            String, nullable     (reservation / report / deal)
├── ref_id              Integer, nullable
└── created_at          DateTime
```

### 13-2. 업로드 API

```
POST /uploads/image
Content-Type: multipart/form-data
Fields:
  file         (필수, 이미지 파일)
  purpose      (필수: report_evidence / dispute / profile)
  ref_type     (선택: reservation / report / deal)
  ref_id       (선택: 연결할 대상 ID)

Response:
{
  “id”: 7,
  “file_key”: “uploads/2026/02/28/abc123.jpg”,
  “url”: “https://cdn.yeokping.com/uploads/2026/02/28/abc123.jpg”
}
```

### 13-3. 운영 규칙

- 최대 파일 크기: 10MB
- 허용 형식: JPEG, PNG, WEBP
- 저장 방식: 개발 = 로컬 `uploads/` 디렉토리, 프로덕션 = S3
- 신고 제출 시 `uploaded_files.id`를 `reports.meta`에 포함
- 30일 후 미연결 파일 자동 삭제 (배치)



