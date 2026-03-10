# FCM + WebSocket 검증 리포트 (20건)

**테스트 일시**: 2026-03-10
**환경**: Railway Production (https://web-production-defb.up.railway.app)
**결과**: **20/20 PASS (100%)**

---

## FCM 푸시 알림 (F1-F10)

| # | 항목 | 기대 | 결과 | 상태 |
|---|------|------|------|------|
| F1 | Admin 로그인 | 토큰 발급 | OK | PASS |
| F2 | FCM 토큰 등록 (buyer) | 200 | 200 | PASS |
| F3 | FCM 토큰 빈값 | 400 | 400 | PASS |
| F4 | FCM 토큰 user_id 없음 | 400 | 400 | PASS |
| F5 | 존재하지 않는 사용자 | 404 | 404 | PASS |
| F6 | FCM Seller 토큰 등록 | 200 | 200 | PASS |
| F7 | FCM Actuator 토큰 등록 | 200/404 | 404 | PASS |
| F8 | FCM graceful skip | 200 | 200 | PASS |
| F9 | Health Check | 200 | 200 | PASS |
| F10 | 기존 알림 목록 조회 | 200 | 200 | PASS |

## WebSocket 실시간 채팅 (W11-W20)

| # | 항목 | 기대 | 결과 | 상태 |
|---|------|------|------|------|
| W11 | WS 엔드포인트 존재 | != 404 | 200 | PASS |
| W12 | WS 잘못된 토큰 인증 | ERROR 메시지 | ERROR 수신 | PASS |
| W13 | WS 유효 토큰 인증 | AUTH_OK | AUTH_OK, user_id=1 | PASS |
| W14 | WS 메시지 + XSS 이스케이프 | `<script>` 차단 | hasScript=false | PASS |
| W15 | WS 입력 중 표시 | 전송 성공 | typing indicators sent | PASS |
| W16 | WS 온라인 목록 | count >= 1 | count=1 | PASS |
| W17 | 기존 HTTP 채팅 API | 200/404/422 | 422 | PASS |
| W18 | 딜 목록 조회 (회귀) | 200 | 200 | PASS |
| W19 | 정산내역서 PDF (회귀) | 200/404 | 200, PDF | PASS |
| W20 | 핑퐁이 ASK (회귀) | 200/201 | 200 | PASS |

---

## 구현 요약

### FCM 푸시 알림
- `app/services/fcm_push.py`: Firebase Admin SDK (graceful degradation - 미설치 시 skip)
- `POST /notifications/fcm-token`: FCM 토큰 등록/갱신 (buyer/seller/actuator)
- `create_notification()` 호출 시 자동 FCM 푸시 발송 (best-effort)
- 12개 알림 타입 헬퍼: notify_new_offer, notify_settlement_ready 등

### WebSocket 채팅
- `app/routers/deal_chat_ws.py`: 딜방 실시간 채팅
- `/ws/chat/{deal_id}`: JWT 인증 + 양방향 메시지
- ConnectionManager: 룸 기반 연결 관리
- 메시지 타입: CHAT, TYPING, STOP_TYPING, READ, ONLINE_LIST, SYSTEM
- XSS 방지: `html.escape()` 적용
- `frontend/src/components/DealChatWS.tsx`: React WS 채팅 컴포넌트

### 디버깅 이력
1. FCM 토큰 500 오류 → 라우트 순서 충돌 (`/fcm-token` vs `/{notification_id}/read`) → static 라우트 먼저 등록
2. PostgreSQL DATETIME 미지원 → `TIMESTAMP` 으로 변경
3. buyer/seller id=1 미존재 → 유효한 id (9) 사용
4. WebSocket onerror → `websockets` 패키지 미설치 → requirements.txt 추가
