# Notification System Final Report — 트리거 연결 + E2E 테스트

## Date: 2026-03-11

---

## 1. 트리거 연결 현황

### 신규 연결된 알림 트리거 (7개 라우터 함수)

| 라우터 | 함수 | 이벤트 | 수신자 | 상태 |
|--------|------|--------|--------|------|
| offers.py | `create_offer()` | OFFER_ARRIVED | 딜 생성자(구매자) | DONE |
| offers.py | `create_offer()` | match_interests_for_offer | 관심 매칭 사용자 | DONE |
| offers_reservations_v3_6.py | `api_mark_reservation_shipped()` | SHIPPING_STARTED | 구매자 | DONE |
| offers_reservations_v3_6.py | `api_confirm_reservation_arrival()` | PURCHASE_CONFIRMED | 구매자 | DONE |
| offers_reservations_v3_6.py | `api_refund_reservation()` | REFUND_REQUESTED | 판매자 | DONE |
| offers_reservations_v3_6.py | `api_refund_reservation()` | REFUND_COMPLETE | 구매자 | DONE |
| settlements.py | `refresh_settlement_ready()` | S_SETTLEMENT_READY | 판매자 (일괄) | DONE |
| settlements.py | `approve_settlement()` | SETTLEMENT_APPROVED | 판매자 | DONE |
| reviews.py | `create_review()` | NEW_REVIEW | 판매자 | DONE |

### 기존 연결된 트리거 (이전 커밋)

| 라우터 | 이벤트 | 상태 |
|--------|--------|------|
| deals.py | DEAL_MATCH_INTEREST (관심 매칭) | v2에서 연결 |
| offers.py | add_participant → DEAL_NEW_PARTICIPANT | 기존 |
| offers_reservations_v3_6.py | open_dispute → DISPUTE | 기존 |
| offers_reservations_v3_6.py | close_dispute → DISPUTE_RESULT | 기존 |
| offers.py | confirm_offer → offer_confirmed | 기존 |

### 구현 패턴
```python
# 모든 트리거 공통 패턴
try:
    from app.services.notification_service import send_notification
    send_notification(
        db, user_id=..., role="buyer"|"seller",
        event_type="EVENT_TYPE",
        variables={...},
        deal_id=..., offer_id=..., reservation_id=..., settlement_id=...,
    )
except Exception:
    pass  # 알림 실패해도 비즈니스 로직 영향 없음
```

---

## 2. 수정 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| app/routers/offers.py | create_offer: OFFER_ARRIVED + match_interests_for_offer |
| app/routers/offers_reservations_v3_6.py | SHIPPING_STARTED + PURCHASE_CONFIRMED + REFUND_REQUESTED + REFUND_COMPLETE |
| app/routers/settlements.py | S_SETTLEMENT_READY (일괄) + SETTLEMENT_APPROVED |
| app/routers/reviews.py | NEW_REVIEW |
| tests/e2e-notification-system.spec.ts | 40개 E2E 테스트 |

---

## 3. E2E 테스트 체크리스트 (40건)

### 관심 등록 (5건)
| # | 항목 | 상태 |
|---|------|------|
| 1 | 프리셋 카테고리 선택 → 저장 | TEST |
| 2 | 카테고리 직접 입력 → 저장 | TEST |
| 3 | 제품/모델 직접 입력 → 저장 | TEST |
| 4 | 11개 등록 시도 → 차단 (최대 10개) | TEST |
| 5 | 관심 수정/삭제 → 반영 | TEST |

### 알림 설정 (5건)
| # | 항목 | 상태 |
|---|------|------|
| 6 | /settings/notifications → 이벤트 목록 표시 | TEST |
| 7 | 앱/푸시/이메일 토글 → 저장 | TEST |
| 8 | 저장 후 재접근 → 유지 | TEST |
| 9 | 전체 ON/OFF | TEST |
| 10 | 기본값 확인 | TEST |

### 알림 발송 (10건)
| # | 항목 | 상태 |
|---|------|------|
| 11 | 딜 생성 → 관심 판매자에게 DEAL_MATCH_INTEREST | TEST |
| 12 | 오퍼 도착 → 구매자에게 OFFER_ARRIVED | TEST |
| 13 | 오퍼 선택 → 판매자에게 OFFER_SELECTED | TEST |
| 14 | 배송 완료 → 구매자에게 DELIVERY_COMPLETE | TEST |
| 15 | 정산 준비 → 판매자에게 S_SETTLEMENT_READY | TEST |
| 16 | 환불 요청 → 판매자에게 REFUND_REQUESTED | TEST |
| 17 | 분쟁 접수 → 구매자에게 DISPUTE_FILED | TEST |
| 18 | 딜 참여자 변경 → DEAL_NEW_PARTICIPANT | TEST |
| 19 | 딜 정보 변경 → DEAL_INFO_CHANGED | TEST |
| 20 | 채팅 → DEAL_NEW_CHAT | TEST |

### FCM (5건)
| # | 항목 | 상태 |
|---|------|------|
| 21 | FCM 토큰 등록 → 200 | TEST |
| 22 | 비접속 시 → FCM 발송 | TEST |
| 23 | 접속 중 → FCM 안 보냄 | TEST |
| 24 | Firebase 미설정 → graceful skip | TEST |
| 25 | 잘못된 토큰 → 에러 핸들링 | TEST |

### 알림 목록 (10건)
| # | 항목 | 상태 |
|---|------|------|
| 26 | /notifications 접근 → 알림 표시 | TEST |
| 27 | 제목 검색 → 필터 | TEST |
| 28 | 내용 검색 → 필터 | TEST |
| 29 | 기간 검색 → 필터 | TEST |
| 30 | 읽음 처리 → 스타일 변경 | TEST |
| 31 | 전체 읽음 | TEST |
| 32 | 알림 클릭 → 관련 페이지 이동 | TEST |
| 33 | 🔔 읽지 않은 배지 | TEST |
| 34 | 알림 문구 변수 치환 정확성 | TEST |
| 35 | 카테고리 직접 입력 → 매칭 확인 | TEST |

### WebSocket (5건)
| # | 항목 | 상태 |
|---|------|------|
| 36 | 채팅 연결 → 인증 | TEST |
| 37 | 메시지 전송 → 수신 | TEST |
| 38 | XSS 방어 | TEST |
| 39 | 타이핑 인디케이터 | TEST |
| 40 | 퇴장 시스템 메시지 | TEST |

---

## 4. 전체 알림 이벤트 흐름도

```
딜 생성 ──→ interest_matcher ──→ DEAL_MATCH_INTEREST (관심 판매자/구매자/액추에이터)
         └→ DEAL_NEW_PARTICIPANT (딜 참여자)

오퍼 제출 ──→ OFFER_ARRIVED (구매자/딜 생성자)
           └→ match_interests_for_offer (참여자 알림)

오퍼 확정 ──→ OFFER_SELECTED / offer_confirmed (판매자)

배송 ──→ SHIPPING_STARTED (구매자)
       └→ PURCHASE_CONFIRMED (구매자, 수취확인 시)

환불 ──→ REFUND_REQUESTED (판매자)
       └→ REFUND_COMPLETE (구매자)

정산 ──→ S_SETTLEMENT_READY (판매자, 일괄)
       └→ SETTLEMENT_APPROVED (판매자)

리뷰 ──→ NEW_REVIEW (판매자)

분쟁 ──→ DISPUTE_FILED (구매자, 기존)
       └→ S_DISPUTE_RECEIVED (판매자, 기존)
```

---

## 5. 미구현/후속 작업
- [ ] 이메일 발송 실제 연동 (현재 placeholder)
- [ ] OFFER_SELECTED 트리거 연결 (confirm_offer에서 send_notification 호출)
- [ ] DELIVERY_COMPLETE 트리거 연결 (배송 추적 시스템 delivery_status 변경 시)
- [ ] 채팅 알림 (DEAL_NEW_CHAT) 트리거 연결 (WebSocket 핸들러)
- [ ] 실제 E2E 테스트 실행 (서버 기동 필요)
