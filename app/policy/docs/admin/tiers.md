 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# 등급/티어 정책 (Tier & Grade)

티어는 “누가 더 신뢰할 수 있는가”를 수치화한 정책이다.
(노출/수수료/제재/한도/자동화에 모두 연결됨)

---

## 1) Buyer 티어

라우트 기준으로 Buyer는 최소 두 축이 존재:
- trust_tier
  - `/buyers/{buyer_id}/trust_tier`
  - `/insights/buyer/{buyer_id}/trust`
- points_grade
  - `/buyers/{buyer_id}/points_grade`
  - `/insights/buyer/{buyer_id}/grade`

권장 정책 항목(문서 표준):
- trust_tier 산정 입력: 결제 성공률, 취소율, 분쟁율, 리뷰/클레임 등
- points_grade 산정 입력: 포인트 잔액/이력, 악용 패턴 등
- 페널티 정책: 반복 “예약 후 미결제(5분 초과)” 발생 시 티어 하락/제한

---

## 2) Seller 레벨

Seller 레벨/리뷰 관련 라우트가 존재:
- `/reviews/seller/{seller_id}/level`
- `/reviews/seller/{seller_id}/summary`
- `/insights/seller/{seller_id}/level`

권장 정책 항목:
- 레벨 산정 입력: 평균 평점, 리뷰 수, 환불/분쟁율, 배송 지연율, 취소율
- 레벨이 영향을 주는 영역:
  - 노출(exposure)
  - 수수료(fees)
  - 제재(offers 제한/정산 보류)
  - 운영 자동화(빠른 확정/추가 검증)

---

## 3) 티어 정책의 SSOT 계층 (스냅샷 우선)

티어/레벨/그레이드는 “실시간 계산값”도 제공하지만,
거래가 발생한 시점의 판단 근거는 결제(PAID) 시점에 박제된 스냅샷이 1순위 SSOT다.

1) **스냅샷(최우선 SSOT)**  
   - `Reservation.policy_snapshot_json.tier_snapshot`
   - 결제(PAID) 시점에 캡처해서 저장하며, 이후 정책/룰이 바뀌어도 이미 결제된 예약의 등급 근거는 바뀌지 않는다.

2) 실시간 계산(라우트/API 제공)  
   - CS/조회/대시보드용 “현재 상태” 제공
   - 단, 과거 거래 설명은 스냅샷이 우선

3) 런타임 정책(컷/가중치/제재 기준)  
   - `app/policy/*`에 중앙화
   - 실시간 계산과 “다음 거래부터 적용되는 정책”의 근거

### tier_snapshot 표준 키
- `tier_snapshot.policy_version`, `tier_snapshot.policy_hash`, `tier_snapshot.captured_at`
- `tier_snapshot.buyer` (trust tier)
- `tier_snapshot.points` (points grade)
- `tier_snapshot.seller` (seller level / fee)

### 단위(Unit)
- `tier_snapshot.seller.fee_percent` 는 이름에 percent가 들어가지만,
  저장 값은 **rate(0~1)** 로 통일한다. (예: 2.5% = 0.025)

### 멱등/보존(Overwrite 금지)
- `tier_snapshot` 은 결제 시점 박제이므로:
  - 없으면 추가(멱등)
  - 있으면 덮어쓰지 않는다(보존)



---

## 3-1) Tier Snapshot (결제 시점 박제) — SSOT

### 왜 필요한가
- 티어/등급/셀러레벨은 시간이 지나며 변한다.
- 그러나 “과거 거래”의 노출/수수료/제재/리뷰 가중/CS 근거는 **거래 당시 상태**로 재현 가능해야 한다.
- 따라서 결제(PAID) 시점에 tier/grade/level을 Reservation에 박제한다.

### 저장 위치
- `Reservation.policy_snapshot_json.tier_snapshot`

### 스키마(표준)
```json
{
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
      "deposit_percent": 0.0,
      "reason": "new_or_low_participation"
    },
    "points": {
      "balance": 0,
      "grade": "BRONZE"
    },
    "seller": {
      "level": "Lv.2",
      "fee_percent": 0.025,
      "sold_count": 460,
      "rating": 4.0
    }
  }
}


---

## 3-2) Deposit(예치금) 제거 — 문서 표준

- Deposit 기능은 제거되었고 회귀(regression)로 취급한다.
- tier_snapshot의 `deposit_percent`는 **항상 0.0** 으로 유지한다.


- Deposit(예치금)은 제거되었으며 tier 계산 결과에 포함되더라도 deposit_percent는 항상 0.0


---

## 4) 핑퐁이/CS 설명 템플릿

- “현재 등급(숫자/레벨)” + “왜 그런지(근거 이벤트)” + “어떻게 올리는지(행동 가이드)”
- 근거는 activity_log(이벤트 로그)와 연결







