 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# OFFER 노출 정책 (Exposure) — SSOT v3.6 (Hybrid)

노출(Exposure)은 “공정성 + 효율”을 동시에 달성하기 위한 핵심 정책이다.
이 문서는 **원안(Top20 + 그룹핑/정렬 + 점수모델)** 을 유지하면서,
현재 코드에 들어간 **가격비율 기반 분류/증빙(exposure_snapshot)** 을 “증빙 레이어”로 정리한 최종본이다.

---

## 0) 한 줄 정의

- **SSOT(결정)**: “어떤 오퍼가 노출/차단/순서에 놓일지”는 **오퍼 제출 단계 + 랭킹 API** 에서 결정된다.
- **Evidence(증빙)**: Reservation에 저장되는 `exposure_snapshot`은 **결정이 아니라**, “그 예약 당시 기준가격 대비 오퍼가격 판정 결과”를 남기는 **증빙**이다.

즉,
- *노출 정책*은 여러 buyer/seller가 얽힌 “시장 상태”에 의해 계속 변할 수 있고,
- Reservation은 “거래(결제 윈도우) 개시 시점”의 증빙을 남기는 것이 맞다.

---

## 1) 원칙(정책집 표준)

1) **Top20 먼저 만든다**
- 전체 후보 중 우선순위가 높은 20개를 만든 뒤,
- 그 Top20 내부에서만 그룹핑/정렬을 적용한다.

2) **그룹 크기는 고정이 아니다**
- PREMIUM/MATCHING/BELOW 각 그룹은 상황에 따라 0개 이상 가능
- 단, 그룹핑/정렬은 Top20 내부에서만 적용한다.

---

## 2) 코드 SSOT 포인터(현재 라우트 기준)

### 2-1) 랭킹 노출(SSOT)
- `/offers/deal/{deal_id}/ranked` (GET)  
  - Top20 + 그룹핑/정렬 적용의 “결정 지점(SSOT)” 후보

### 2-2) 오퍼 제출/검증(SSOT 후보)
- `/offers/*`
- `/offers/validate_price`

### 2-3) Reservation 증빙(Evidence)
- Reservation 생성 시점에 `policy_snapshot_json.exposure_snapshot`을 저장할 수 있음(증빙/설명/재현 목적)

---

## 3) 점수 모델(원안 유지)

Top20 점수의 기본 축(가중치는 런타임 정책화 대상):

- Price: 가격 경쟁력
- Condition: 조건 적합(딜 조건 충족)
- Reliability: 신뢰(셀러 레벨/리뷰/분쟁율)
- Speed: 배송/응답 속도
- Policy: 환불/보증/추가 조건 명확성
- Freshness: 오퍼 최신성
- Capacity: 남은 수량/확정 가능성

> 참고: 현재 구현이 “가격비율 분류”에 우선 집중되어 있어도,
> 이 점수모델은 SSOT 문서상 유지한다(향후 중앙화 시 확장).

---

## 4) 그룹 정의(원안 유지)

- PREMIUM: 높은 신뢰 + 높은 적합 + 경쟁력 높은 오퍼
- MATCHING: 딜 조건과 “정확히 맞는” 오퍼(조건 충족 최우선)
- BELOW: 비교군/대안(점수 낮지만 의미 있는 오퍼)

---

## 5) 가격비율 기반 분류(현행 v3.6 최소 정책)

### 5-1) 기준가격(wish_price) 정의
- 기본: `Deal.target_price` (또는 정책상 “구매희망가”로 정의되는 값)
- 데이터가 없으면 판정 불가(UNKNOWN)

### 5-2) 판정 로직(요약)
- wish_price 존재 시:
  - ratio = offer_price / wish_price
  - ratio가 특정 임계치(premium_max_ratio 등) 초과하면 BLOCK 등의 판정 가능
- wish_price 누락 시:
  - 판정 불가이므로 `UNKNOWN` 처리(정책 위반이 아니라 “정보 부족”)

---

## 6) Reservation.policy_snapshot_json 의 exposure_snapshot 의미 (Evidence)

Reservation에 저장되는 `exposure_snapshot`은 **SSOT(결정)** 이 아니라 **증빙(Evidence)** 이다.

- “이 예약이 생성될 당시” 기준가격(wish_price)과 offer_price로 계산하면
  어떤 분류(category)로 보였는지 기록한다.
- 누락되거나 `UNKNOWN`이어도 정상이다.
- `allowed=False`여도 **예약 생성/결제를 실패시키지 않는다**(노출정책은 시장/노출 레이어의 판단이기 때문).
- CS/핑퐁이 설명/재현/디버깅을 위한 캐시+증빙이다.

---

## 7) Snapshot 표준 키 (권장/현행)

`policy_snapshot_json.exposure_snapshot.keys` 표준:

- `exposure.premium_max_ratio`
- `exposure.wish_price`
- `exposure.offer_price`
- `exposure.ratio`
- `exposure.category` (FRONT / PREMIUM / BLOCK / UNKNOWN)
- `exposure.allowed` (bool)
- `exposure.reason` (e.g. wish_price_missing, ratio>premium_max)

---

## 8) 데이터 결손 처리(가격 미존재)

Deal/Offer에 기준가격이 없을 수 있다.

- wish_price 없으면:
  - `category=UNKNOWN`, `allowed=True`, `reason=wish_price_missing`
  - 이는 정책 위반이 아니라 “판정 불가(정보 부족)”

---

## 9) 운영/분쟁/CS 관점 결론

- “왜 이 오퍼가 상단에 떴는지”의 SSOT는 랭킹/제출 레이어에 있다.
- “왜 이 예약이 그 가격으로 성립했는지”의 증빙은 Reservation snapshot이 빠르게 답해준다.
- 전역 로그(ActivityLog)는 “분석/정책 튜닝”에 강하고,
  Reservation snapshot은 “개별 케이스 재현/설명”에 강하다.

---

## 10) 딜 검색/필터/페이지네이션 (GET /deals/)

### 10-1. 엔드포인트

```
GET /deals/
Query params:
  status    String  open|closed|completed|expired (복수: comma-separated)
  category  String  카테고리 필터 (선택)
  keyword   String  제품명 부분 검색
  min_price Float   target_price 하한
  max_price Float   target_price 상한
  buyer_id  Int     내 딜만 보기
  sort      String  created_at:desc | target_price:asc | ...
  page      Int     (기본 1)
  size      Int     (기본 20, 최대 100)
```

### 10-2. 응답 형식

```json
{
  “items”: [ { ...DealOut... } ],
  “total”: 142,
  “page”: 1,
  “size”: 20,
  “pages”: 8
}
```

### 10-3. 정렬 지원 필드

| sort 값 | 설명 |
|---------|------|
| `created_at:desc` | 최신순 (기본) |
| `created_at:asc` | 오래된 순 |
| `target_price:asc` | 희망가 낮은 순 |
| `target_price:desc` | 희망가 높은 순 |
| `deadline_at:asc` | 마감 임박 순 |

---

## 11) 자동화 배치 (노출 관련)

### 11-1. 오퍼 만료 자동 처리 (매일 04:00)

- **주기**: 매일 04:00 KST
- **대상**: 오퍼 유효기간(`expires_at`) 초과 + status=`open`
- **동작**: `open → expired` 전환 + 연결 Reservation이 있으면 알림
- **구현**: `app/schedulers/offer_expiry.py`

```python
def run_offer_expiry_batch():
    expired_offers = db.query(Offer).filter(
        Offer.status == “open”,
        Offer.expires_at <= now(),
    ).all()
    for offer in expired_offers:
        offer.status = “expired”
    db.commit()
```

### 11-2. 리뷰 요청 자동 발송 (매일 10:00)

- **주기**: 매일 10:00 KST
- **대상**: `ARRIVAL_CONFIRMED` 후 3일 경과 + 리뷰 미작성
- **동작**: 구매자에게 “리뷰를 남겨주세요” 알림 발송 (1회)
- **구현**: `app/schedulers/review_request.py`

```python
def run_review_request_batch():
    cutoff = now() - timedelta(days=3)
    targets = db.query(Reservation).filter(
        Reservation.status == “ARRIVAL_CONFIRMED”,
        Reservation.arrival_confirmed_at <= cutoff,
        ~Reservation.review_requested,
    ).all()
    for r in targets:
        create_notification(db, user_id=r.buyer_id, type=”review_request”, ...)
        r.review_requested = True
    db.commit()
```

### 11-3. 배치 스케줄 요약

| 배치명 | 주기 | 구현 위치 |
|--------|------|-----------|
| 오퍼 만료 처리 | 매일 04:00 | `app/schedulers/offer_expiry.py` |
| 리뷰 요청 발송 | 매일 10:00 | `app/schedulers/review_request.py` |
