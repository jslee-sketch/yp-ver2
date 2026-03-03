# 시간 정책(Time)

역핑은 시간이 뼈대다.
(정책 원문에서도 “시간 규칙(마감/트리거/자동 처리)”이 핵심 축으로 명시됨)

핵심 원칙:
- “마감/트리거/자동 전이”는 반드시 SSOT(코드)로 정의되고, 운영 변경은 관리자 라우터를 통해서만 한다.

---

## 1) 시간 개념(정책집 표준)

- Deadline: 마감(딜 마감/오퍼 마감/결제 마감/정산 마감)
- Trigger: 자동 처리(만료/취소/확정/정산 준비)
- SLA: 배송/이행/응답 지연 허용
- Grace: 유예(짧은 허용 시간)
- Freeze: 분쟁/환불/차지백 등으로 “정산/전이 보류”

---

## 2) 절대 원칙(문서 기준)

- Deposit(예약금) 없음.
- 예약 후 “즉시 결제”가 원칙이며, 5분 결제 창이 정책 핵심임. (원문에 명시) 
- 5분 초과 시 자동 취소/복귀가 기본 전이.

---

## 3) 코드 SSOT 포인터(현재 트리 기준)

- 시간 키/정책 정의: `app/core/time_policy.py`
- 스케줄러/자동 트리거: `app/core/scheduler.py`
- 운영 변경(관리자): `app/routers/admin_policy.py`
  - `/admin/policy/status`
  - `/admin/policy/update-time`
  - `/admin/policy/update-deadtime`
  - `/admin/policy/bulk`
  - `/admin/policy/reset`

---

## 4) 권장 “시간 키” 표준(정책집에서 고정할 것)

(키 이름은 실제 구현에 맞춰 조정하되, 의미는 고정)

- payment_window_minutes
  - 예약 후 결제 제한(기본 5분)
- offer_confirm_window_minutes
  - 판매자 컨펌 제한(있다면)
- shipping_mark_window_hours
  - shipped 처리 제한(있다면)
- arrival_confirm_window_days
  - 구매자 수령확인/자동확정
- cooling_days
  - 분쟁 가능 기간/정산 보류 기간
- settlement_payout_delay_days
  - cooling 후 지급 지연(은행/운영)

---

## 5) 운영 체크리스트(9000 포트)

- 현재 정책 확인:
  - `GET http://127.0.0.1:9000/admin/policy/status`
- 특정 키 변경:
  - `POST http://127.0.0.1:9000/admin/policy/update-time?key=...&hours=...`
- 대량 변경/리셋:
  - `POST /admin/policy/bulk`
  - `POST /admin/policy/reset`