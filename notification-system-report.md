# Notification System Report

## Commit: 729792f
## Date: 2026-03-11

---

## 1. 구현 완료 항목

### Step 1: DB Models
- [x] `UserInterest` 모델 (user_id, role, level, value, source, priority)
- [x] `NotificationSetting` 모델 (user_id, event_type, channel_app/push/email)
- [x] `UserNotification` 확장 (deal_id, offer_id, reservation_id, settlement_id, sent_app/push/email)
- [x] DB 테이블 생성 + ALTER TABLE 마이그레이션

### Step 2: 64 Notification Event Templates
- [x] Buyer 22개 이벤트 (딜/오퍼/결제/배송/포인트/리뷰 등)
- [x] Seller 22개 이벤트 (오퍼/주문/배송/정산/리뷰 등)
- [x] Actuator 13개 이벤트 (커미션/판매자/계약 등)
- [x] Admin 7개 이벤트 (분쟁/이상/신규가입 등)
- [x] `render_notification()` 변수 치환 함수
- [x] `get_event_defaults()` 역할별 기본 채널 설정

### Step 3: Interest Registration UI
- [x] `InterestTagInput` 공통 컴포넌트 (프리셋 + 직접입력)
- [x] 15개 프리셋 카테고리 (스마트폰, 노트북, 태블릿 등)
- [x] 레벨별 색상 코딩 (category=파랑, product=초록, model=주황)
- [x] 역할별 최대 개수: buyer=3, seller=5, actuator=10
- [x] `InterestSettingsPage` (/settings/interests)

### Step 4: Notification Settings Page
- [x] `NotificationSettingsPage` (/settings/notifications)
- [x] 이벤트별 앱/푸시/이메일 토글
- [x] 그룹별 분류 표시
- [x] 벌크 ON/OFF 버튼
- [x] 저장 API 연동

### Step 5: Unified Notification Service
- [x] `send_notification()` — 설정 확인 → 앱 저장 → FCM 발송 → 이메일 (placeholder)
- [x] `notify_interest_match_on_deal_create()` — 딜 생성 시 관심 상품 매칭
- [x] `_get_fcm_token()` — 역할별 FCM 토큰 조회

### Step 6: defaults.yaml Policy Params
- [x] `notifications:` 섹션 (max_interests, thresholds, limits)
- [x] `interest_categories:` 프리셋 목록 (15개)

### Step 7: Sidebar + Routes
- [x] App.tsx 라우트 추가 (/settings/notifications, /settings/interests)
- [x] Sidebar.tsx 메뉴 추가 (관심 상품, 알림 설정)

### Step 8: Enhanced Notifications Page
- [x] 검색 기능 (제목/내용 통합 검색)
- [x] 읽음 상태 필터 (전체/안읽음/읽음)
- [x] 채널 배지 표시 (앱/푸시/이메일 발송 상태)
- [x] 로딩 상태 표시
- [x] MOCK 데이터 제거, 실제 API 연동

### Step 9: Backend API Endpoints
- [x] `GET /users/{user_id}/interests` — 관심 상품 목록
- [x] `POST /users/{user_id}/interests` — 관심 상품 저장
- [x] `GET /interests/presets` — 프리셋 카테고리 목록
- [x] `GET /notification-settings/events?role=` — 역할별 이벤트 목록
- [x] `GET /notification-settings/{user_id}` — 사용자 설정 조회
- [x] `POST /notification-settings/{user_id}` — 설정 저장
- [x] `POST /notification-settings/{user_id}/bulk` — 벌크 설정

---

## 2. 파일 목록

| 파일 | 유형 | 설명 |
|------|------|------|
| `app/models.py` | 수정 | UserInterest, NotificationSetting 모델 + UserNotification 확장 |
| `app/main.py` | 수정 | 모델 임포트 + 라우터 등록 |
| `app/services/notification_templates.py` | 신규 | 64개 이벤트 템플릿 + render 함수 |
| `app/services/notification_service.py` | 신규 | 통합 알림 발송 서비스 |
| `app/routers/notification_settings.py` | 신규 | 관심 상품 + 알림 설정 API |
| `app/routers/notifications.py` | 수정 | 검색 파라미터 추가 |
| `app/policy/params/defaults.yaml` | 수정 | 알림 정책 파라미터 + 프리셋 |
| `frontend/src/components/common/InterestTagInput.tsx` | 신규 | 관심 상품 태그 입력 컴포넌트 |
| `frontend/src/pages/InterestSettingsPage.tsx` | 신규 | 관심 상품 설정 페이지 |
| `frontend/src/pages/NotificationSettingsPage.tsx` | 신규 | 알림 설정 페이지 |
| `frontend/src/pages/NotificationsPage.tsx` | 수정 | 검색/필터/채널배지 추가 |
| `frontend/src/App.tsx` | 수정 | 라우트 추가 |
| `frontend/src/api/endpoints.ts` | 수정 | NOTIFICATION_SETTINGS 엔드포인트 |
| `frontend/src/components/layout/Sidebar.tsx` | 수정 | 메뉴 아이템 추가 |

---

## 3. 테스트 체크리스트

| # | 항목 | 상태 |
|---|------|------|
| 1 | UserInterest 테이블 생성 | PASS |
| 2 | NotificationSetting 테이블 생성 | PASS |
| 3 | UserNotification 컬럼 추가 (deal_id 등) | PASS |
| 4 | notification_settings 라우터 마운트 | PASS |
| 5 | GET /interests/presets 응답 | PASS |
| 6 | POST /users/{id}/interests 저장 | BUILD OK |
| 7 | GET /notification-settings/events?role=buyer | BUILD OK |
| 8 | 64개 이벤트 템플릿 로드 | PASS |
| 9 | render_notification 변수 치환 | BUILD OK |
| 10 | send_notification 함수 임포트 | PASS |
| 11 | FCM 토큰 조회 로직 | BUILD OK |
| 12 | InterestTagInput 컴포넌트 렌더링 | BUILD OK |
| 13 | 프리셋 카테고리 토글 | BUILD OK |
| 14 | 직접 입력 추가/삭제 | BUILD OK |
| 15 | 역할별 최대 개수 제한 | BUILD OK |
| 16 | NotificationSettingsPage 렌더링 | BUILD OK |
| 17 | 이벤트별 토글 동작 | BUILD OK |
| 18 | 벌크 ON/OFF | BUILD OK |
| 19 | 설정 저장 API 호출 | BUILD OK |
| 20 | NotificationsPage 검색 | BUILD OK |
| 21 | NotificationsPage 읽음 필터 | BUILD OK |
| 22 | 채널 배지 표시 | BUILD OK |
| 23 | App.tsx 라우트 등록 | PASS |
| 24 | Sidebar 메뉴 표시 | PASS |
| 25 | TypeScript 컴파일 (신규 파일) | PASS |
| 26 | Vite 빌드 성공 | PASS |
| 27 | Backend 전체 라우터 마운트 (55개) | PASS |
| 28 | defaults.yaml 파싱 | PASS |
| 29 | endpoints.ts 엔드포인트 매핑 | PASS |
| 30 | Git push 성공 | PASS |

---

## 4. 미구현/후속 작업

- [ ] 이메일 발송 실제 연동 (현재 placeholder)
- [ ] 관심 상품 매칭 딜 생성 훅 통합 (deal create 시 자동 호출)
- [ ] 가이드 MD 업데이트 (guide_buyer/seller/actuator/admin)
- [ ] 핑퐁이 FAQ 알림 관련 Q&A 추가
- [ ] E2E 테스트 작성
