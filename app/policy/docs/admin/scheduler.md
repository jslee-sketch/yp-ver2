 ADMIN ONLY: BUYER/SELLER 응답 근거로 사용 금지

# 통합 스케줄러 정책 (Scheduler) — SSOT

역핑의 모든 자동화 배치 작업을 단일 문서에서 관리한다.
"언제, 무엇을, 어디서" 가 이 문서 하나로 파악 가능해야 한다.

---

## 1) 전체 배치 목록

| 주기 | 배치명 | 대상/동작 | 구현 위치 |
|------|--------|-----------|-----------|
| **매 10분** | 예약 만료 스윕 | PENDING 예약 → 결제 타임아웃 초과 시 CANCELLED | `app/schedulers/reservation_expiry.py` |
| **매 1시간** | 딜 마감 종료 | open 딜 → deadline_at 초과 시 closed | `app/schedulers/deal_close.py` |
| **매 2시간** | 배송완료 자동 감지 | SHIPPED → SweetTracker API → DELIVERED | `app/schedulers/delivery_checker.py` |
| **매 6시간** | 정산 갱신 (HOLD→READY) | 쿨링 종료 + 분쟁 없음 → READY 전환 | `app/schedulers/settlement_updater.py` |
| **매일 02:00** | 정산 자동 승인 | READY → APPROVED 일괄 전환 | `app/schedulers/settlement_approver.py` |
| **매일 02:30** | 지급 실행 | APPROVED → payout_requests PAID | `app/schedulers/payout_executor.py` |
| **매일 03:00** | 도착확인 자동처리 | 발송 후 7일 경과 → ARRIVAL_CONFIRMED | `app/schedulers/arrival_auto_confirm.py` |
| **매일 04:00** | 오퍼 만료 처리 | expires_at 초과 open 오퍼 → expired | `app/schedulers/offer_expiry.py` |
| **매일 08:00** | 핑퐁이 일일 리포트 | 전날 활동 요약 → 어드민 대시보드 | `app/schedulers/pingpong_daily_report.py` |
| **매일 10:00** | 리뷰 요청 발송 | 도착확인 후 3일 경과 + 리뷰 없음 → 알림 | `app/schedulers/review_request.py` |

---

## 2) 배치별 상세

### 2-1. 예약 만료 스윕 (매 10분)

```python
# app/schedulers/reservation_expiry.py
def run_reservation_expiry():
    """결제 타임아웃 초과 PENDING 예약 → CANCELLED"""
    timeout_minutes = policy_api.payment_timeout_minutes()
    cutoff = now() - timedelta(minutes=timeout_minutes)
    expired = db.query(Reservation).filter(
        Reservation.status == "PENDING",
        Reservation.created_at <= cutoff,
    ).all()
    for r in expired:
        r.status = "CANCELLED"
        r.cancel_reason = "payment_timeout"
    db.commit()
```

**정책 파라미터**: `policy_api.payment_timeout_minutes()` (defaults.yaml)

---

### 2-2. 딜 마감 종료 (매 1시간)

```python
# app/schedulers/deal_close.py
def run_deal_close():
    """deadline_at 초과 open 딜 → closed + 참여자 알림"""
    expired_deals = db.query(Deal).filter(
        Deal.status == "open",
        Deal.deadline_at.isnot(None),
        Deal.deadline_at < now(),
    ).all()
    for deal in expired_deals:
        deal.status = "closed"
        # 참여자/생성자 알림
        notify_deal_closed(db, deal)
    db.commit()
```

---

### 2-3. 배송완료 자동 감지 (매 2시간)

- SweetTracker API 또는 Mock Provider 호출
- `SHIPPED` 상태 예약의 운송장 번호로 배송 상태 조회
- 배송완료 확인 시 `DELIVERED` 전환
- 상세: `shipping.md` § 8-1 참조

---

### 2-4. 정산 갱신 HOLD→READY (매 6시간)

- 쿨링 기간 종료 + 분쟁 없음 조건
- `HOLD → READY` 전환
- 상세: `settlement.md` § 5-1 참조

---

### 2-5. 정산 자동 승인 READY→APPROVED (매일 02:00)

- `READY` 상태 전체를 `APPROVED`로 일괄 전환
- 관리자 수동 검토 없이 익일 지급 파이프라인 진입 가능
- 상세: `settlement.md` § 5-2 참조

---

### 2-6. 지급 실행 (매일 02:30)

- `APPROVED` 정산에 대해 PayoutGateway 호출
- `payout_requests` 레코드 생성 + PAID 처리
- 실패 시 `FAILED` 상태로 재시도 큐 대기
- 상세: `settlement.md` § 4 참조

---

### 2-7. 도착확인 자동 처리 (매일 03:00)

- 발송 후 7일 경과 예약 자동 `ARRIVAL_CONFIRMED`
- `delivery_auto_confirmed = True`, `delivery_confirmed_source = "auto_7day"`
- 정산 HOLD 해제 트리거로 연결
- 상세: `shipping.md` § 8-2 참조

---

### 2-8. 오퍼 만료 처리 (매일 04:00)

- `expires_at` 초과 + `open` 상태 오퍼 → `expired` 전환
- 상세: `exposure.md` § 11-1 참조

---

### 2-9. 핑퐁이 일일 리포트 (매일 08:00)

- 전날 핑퐁이 활동 요약 (LLM으로 요약문 생성)
- 이상 감지 패턴 포함 (환불률, 봇 의심 등)
- 어드민 대시보드에 저장
- 상세: `pingpong.md` § 핑퐁이 일일 리포트 참조

---

### 2-10. 리뷰 요청 발송 (매일 10:00)

- 도착확인 후 3일 경과 + 리뷰 미작성 구매자에게 알림
- 1인당 1회 발송 (review_requested 플래그로 중복 방지)
- 상세: `exposure.md` § 11-2 참조

---

## 3) 운영 규칙

### 3-1. 스케줄러 실행 방식

| 환경 | 방식 |
|------|------|
| 개발 | PS 스크립트 수동 실행 (`scripts/run_*_batch.ps1`) |
| 프로덕션 | OS 스케줄러 (schtasks / cron) 또는 APScheduler |

### 3-2. 오류 처리

- 각 배치는 try/except로 감싸고 예외를 `activity_log`에 기록
- 배치 실패가 다른 배치를 막지 않아야 함 (독립 실행)
- 치명적 실패 시 관리자 알림 (Slack/이메일 — v2)

### 3-3. 멱등성 원칙

- 모든 배치는 **같은 시각에 2번 실행되어도 결과가 동일**해야 함
- 상태 전이 조건을 정확히 걸어 중복 처리 방지
- `activity_log`에 배치 실행 기록 남겨 재실행 여부 판단 가능

### 3-4. Dead Time 고려

- 야간/주말 Dead Time 중 쿨링 타이머는 일시정지
- 배치가 Dead Time 범위의 정산/만료를 처리할 때는 `policy_api.is_dead_time(ts)` 확인
- 상세: `time.md` 참조

---

## 4) 파일 경로 (SSOT)

```
app/schedulers/
├── reservation_expiry.py      # 예약 만료
├── deal_close.py              # 딜 마감
├── delivery_checker.py        # 배송완료 감지
├── settlement_updater.py      # HOLD→READY
├── settlement_approver.py     # READY→APPROVED
├── payout_executor.py         # 지급 실행
├── arrival_auto_confirm.py    # 7일 자동 도착확인
├── offer_expiry.py            # 오퍼 만료
├── pingpong_daily_report.py   # 핑퐁이 리포트
└── review_request.py          # 리뷰 요청
```
