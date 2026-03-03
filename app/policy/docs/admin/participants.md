 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# 참여자(Actors) 정책 — SSOT v3.6



역핑은 “사람/역할” 중심으로 설명해야 CS/핑퐁이가 흔들리지 않는다.

권한 SSOT는 아래 두 축으로 정의한다.



1) **Action Permissions**: 누가 어떤 액션을 호출할 수 있는가

2) **State Transitions**: 상태머신 상 가능한 전이인가



---



## 1) 핵심 참여자



### Buyer(구매자)

- 딜 생성/그룹 참여/오퍼 선택/예약/결제

- 이슈 제기(환불/분쟁)

- 관련 라우트:

  - `/buyers/*`, `/dashboard/buyer/*`, `/insights/buyer/*`

  - `/reservations/buyer/{buyer_id}`



### Seller(판매자)

- 오퍼 제출/수락/출고/이행

- 리뷰/레벨 영향

- 관련 라우트:

  - `/sellers/*`, `/dashboard/seller/*`, `/insights/seller/*`

  - `/offers/*`, `/reservations/seller/{seller_id}`

  - `/reviews/seller/{seller_id}/*`



### Actuator(액추에이터)

- 판매자 모집/관리

- 정산 발생 시 커미션 수취(ActuatorCommission)

- 관련 라우트:

  - `/actuators/*`

  - `/actuators/{actuator_id}/commissions`

  - `/actuators/commissions/payout-due`

  - `/actuators/me/commissions/settle`



### Admin(관리자)

- 정책 변경, 환불 프리뷰/집행, 정산 운영, 시뮬레이션

- 관련 라우트:

  - `/admin/policy/*`

  - `/admin/refund/preview`

  - `/admin/settlements/*`

  - `/admin/simulate/*`



### System(시스템/배치)

- 시간 트리거/자동 만료/정산 배치/알림



### Agent(PingPong)

- “정책집 + 근거(로그/스냅샷)” 기반으로 설명/제안

- 운영자 승인 후 적용 구조가 목표



---



## 2) 표준 객체(정책이 적용되는 대상)



- Deal: 구매자 요청(딜)

- Offer: 판매자 제안(오퍼)

- Reservation: 오퍼 선택/예약(결제 윈도우 시작)

- Payment: 결제

- Fulfillment: 배송/이행

- Review: 신뢰 신호

- Dispute/Refund: 분쟁/환불

- Settlement: 정산

- ActuatorCommission: 액추에이터 커미션



---



## 3) 권한 SSOT (Action Permissions)



아래 ACTION_PERMISSIONS가 “누가 어떤 액션을 할 수 있나”의 SSOT다.



```python

ACTION_PERMISSIONS: Dict[str, Set[str]] = {

    # Reservation lifecycle

    "reservation.create": {"buyer", "system"},

    "reservation.pay": {"buyer", "system"}, # 결제 성공 webhook/시스템도 포함 가능

    "reservation.cancel": {"buyer", "admin", "system"},

    "reservation.expire": {"system", "admin"},



    # Shipping / Fulfillment

    "reservation.mark_shipped": {"seller", "admin", "system"},

    "reservation.confirm_arrival": {"buyer", "admin", "system"},



    # Refund/Dispute (preview는 안전하니 넓게)

    "refund.preview": {"buyer", "seller", "admin", "system", "agent"},

    "refund.force": {"admin", "system"},

    # Account management
    "account.withdraw": {"buyer", "seller"},
    "account.ban": {"admin"},
    "account.unban": {"admin"},
    "account.change_password": {"buyer", "seller"},
}
```

---

## 4) 계정 관리 (Account Management)

### 4-1. 회원 탈퇴 (Soft Delete)

```
DELETE /account/withdraw
Body: { "reason": "더 이상 사용하지 않음" }   // 선택
```

**탈퇴 처리 규칙**:

| 필드 | 처리 |
|------|------|
| `is_active` | `False` 로 변경 |
| `withdrawn_at` | 탈퇴 시각 기록 |
| 개인정보 | 30일 후 자동 익명화 (법적 보존 기간 준수) |
| 진행 중 예약 | 탈퇴 블록 (예약 정리 후 탈퇴 가능) |
| 포인트 | 탈퇴 시 소멸 |
| 닉네임/게시글 | 익명 처리 ("탈퇴한 사용자") |

**Buyer 모델 추가 필드**:
```
is_active       Boolean, default=True
withdrawn_at    DateTime, nullable
```

### 4-2. 계정 차단/정지 (Ban)

```
POST /admin/users/ban
Body: {
  "user_id": 123,
  "user_type": "buyer",  // "buyer" | "seller"
  "reason": "허위 오퍼 반복 등록",
  "banned_until": "2026-03-15T00:00:00Z"   // null = 영구 차단
}

POST /admin/users/unban
Body: { "user_id": 123, "user_type": "buyer" }
```

**차단 상태 필드**:
```
is_banned       Boolean, default=False
banned_until    DateTime, nullable     (null = 영구 차단)
ban_reason      Text, nullable
```

**차단된 계정 동작**:
- 로그인 불가 → `403 {"code": "account_banned", "banned_until": "..."}`
- 기존 예약/정산은 유지 (관리자 판단으로 처리)

### 4-3. 비밀번호 변경 / 리셋

```
POST /auth/change-password
Body: { "current_password": "...", "new_password": "..." }
// 본인 인증 필요 (JWT 토큰)

POST /auth/reset-password
Body: { "email": "user@example.com" }
// 이메일로 리셋 링크 발송
```

**비밀번호 정책**:
- 최소 8자 이상
- 영문 + 숫자 조합 권장
- 이전 비밀번호와 동일 불가 (최근 3개)

### 4-4. Buyer/Seller 모델 필드 추가 요약

```
Buyer / Seller 공통 추가:
├── is_active        Boolean, default=True
├── withdrawn_at     DateTime, nullable
├── is_banned        Boolean, default=False
├── banned_until     DateTime, nullable
└── ban_reason       Text, nullable
```