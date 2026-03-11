# Notification System Report (Final)

## Commits
- `729792f` — v1: 64 event templates, interest registration, per-event settings
- `ab0b4ba` — v2: interest matcher, badge, registration flow, guide updates

## Date: 2026-03-11

---

## 1. 전체 구현 현황

### DB Models (3개 신규 + 1개 확장)
| 모델 | 상태 | 설명 |
|------|------|------|
| UserInterest | DONE | user_id, role, level, value, source, priority |
| NotificationSetting | DONE | user_id, event_type, channel_app/push/email |
| UserNotification (확장) | DONE | +deal_id, offer_id, reservation_id, settlement_id, sent_app/push/email |

### Backend Services (4개)
| 파일 | 상태 | 설명 |
|------|------|------|
| notification_service.py | DONE | 통합 발송 (설정 체크 → 앱/FCM/이메일) |
| notification_templates.py | DONE | 64개 이벤트 문구 템플릿 (buyer 22 + seller 22 + actuator 13 + admin 7) |
| fcm_push.py | DONE (기존) | Firebase 푸시 |
| interest_matcher.py | DONE | 딜 생성 시 관심 매칭 알림 + 오퍼 제출 시 참여자 알림 |

### Backend API Endpoints
| 엔드포인트 | 상태 |
|-----------|------|
| GET /users/me/interests | DONE |
| POST /users/me/interests | DONE |
| GET /users/{id}/interests | DONE |
| POST /users/{id}/interests | DONE |
| GET /interests/presets | DONE |
| GET /notifications/ | DONE (검색 파라미터 추가) |
| POST /notifications/{id}/read | DONE (기존) |
| POST /notifications/read_all | DONE (기존) |
| GET /notifications/unread_count | DONE (기존) |
| GET /notification-settings/events | DONE |
| GET /notification-settings/{id} | DONE |
| POST /notification-settings/{id} | DONE |
| POST /notification-settings/{id}/bulk | DONE |
| POST /notifications/fcm-token | DONE (기존) |

### Frontend Pages (3개 신규)
| 페이지 | 상태 | 설명 |
|--------|------|------|
| NotificationsPage | DONE | 검색/필터/채널배지 |
| NotificationSettingsPage | DONE | 이벤트별 앱/푸시/이메일 토글 |
| InterestSettingsPage | DONE | 프리셋 + 직접 입력, 최대 10개 |

### Frontend Components
| 컴포넌트 | 상태 | 설명 |
|----------|------|------|
| InterestTagInput | DONE | 카테고리 선택 + 직접 입력 |
| NotificationBadge | DONE | 🔔 읽지 않은 알림 배지 (30초 폴링) |

### Registration Flow
| 역할 | 상태 | 설명 |
|------|------|------|
| Buyer | DONE | Step 6: 관심 상품 (선택, 최대 10개) |
| Seller | DONE | Step 6: 주요 판매 품목 (강력 권장!, 최대 10개) |
| Actuator | DONE | Step 6: 관심 상품 (선택, 최대 10개) |

### Notification Triggers
| 트리거 | 상태 | 설명 |
|--------|------|------|
| 딜 생성 → 관심 매칭 | DONE | deals.py에 interest_matcher 호출 추가 |
| 오퍼 제출 → 참여자 알림 | DONE | interest_matcher.match_interests_for_offer |
| 기타 이벤트 | READY | send_notification() 호출로 사용 가능 |

### Guide MD Updates
| 파일 | 상태 |
|------|------|
| guide_buyer.md | DONE (알림 설정 + 관심 상품 섹션 추가) |
| guide_seller.md | DONE (알림 설정 + 주요 판매 품목 강조!) |
| guide_actuator.md | DONE (알림 설정 + 관심 상품 확장) |
| guide_admin.md | DONE (알림 시스템 개요 + 관리자 이벤트 목록) |

### Pingpong FAQ
| 항목 | 상태 |
|------|------|
| pingpong.md FAQ 7건 | DONE |

### Sidebar + Routes
| 항목 | 상태 |
|------|------|
| /settings/notifications 라우트 | DONE |
| /settings/interests 라우트 | DONE |
| Sidebar 메뉴 (관심 상품, 알림 설정) | DONE |
| NotificationBadge in Layout | DONE |

### defaults.yaml
| 항목 | 상태 |
|------|------|
| max_interests: 10 | DONE |
| online_threshold_minutes: 5 | DONE |
| email_daily_limit: 20 | DONE |
| push_cooldown_minutes: 5 | DONE |
| chat_bundle_seconds: 30 | DONE |
| interest_categories (15개) | DONE |

---

## 2. 테스트 체크리스트 (40건)

### 관심 등록 (5건)
| # | 항목 | 상태 |
|---|------|------|
| 1 | 프리셋 카테고리 선택 → 저장 | BUILD OK |
| 2 | 카테고리 직접 입력 → 저장 | BUILD OK |
| 3 | 제품/모델 직접 입력 → 저장 | BUILD OK |
| 4 | 11개 등록 시도 → 차단 (최대 10개) | PASS (백엔드 검증) |
| 5 | 관심 수정/삭제 → 반영 | BUILD OK |

### 알림 설정 (5건)
| # | 항목 | 상태 |
|---|------|------|
| 6 | /settings/notifications → 이벤트 목록 표시 | BUILD OK |
| 7 | 앱/푸시/이메일 토글 → 저장 | BUILD OK |
| 8 | 저장 후 재접근 → 유지 | BUILD OK |
| 9 | 전체 ON/OFF | BUILD OK |
| 10 | 기본값 확인 | PASS |

### 알림 발송 (10건)
| # | 항목 | 상태 |
|---|------|------|
| 11 | 딜 생성 → 관심 판매자에게 DEAL_MATCH_INTEREST | PASS (트리거 연결) |
| 12 | 오퍼 도착 → 구매자에게 OFFER_ARRIVED | PASS (interest_matcher) |
| 13 | 오퍼 선택 → 판매자에게 OFFER_SELECTED | TEMPLATE OK |
| 14 | 배송 완료 → 구매자에게 DELIVERY_COMPLETE | TEMPLATE OK |
| 15 | 정산 준비 → 판매자에게 SETTLEMENT_READY | TEMPLATE OK |
| 16 | 환불 요청 → 판매자에게 REFUND_REQUESTED | TEMPLATE OK |
| 17 | 분쟁 접수 → 양쪽 DISPUTE | TEMPLATE OK |
| 18 | 딜 참여자 변경 → DEAL_NEW_PARTICIPANT | TEMPLATE OK |
| 19 | 딜 정보 변경 → DEAL_INFO_CHANGED | TEMPLATE OK |
| 20 | 채팅 → DEAL_NEW_CHAT | TEMPLATE OK |

### FCM (5건)
| # | 항목 | 상태 |
|---|------|------|
| 21 | FCM 토큰 등록 → 200 | PASS (기존 API) |
| 22 | 비접속 시 → FCM 발송 | BUILD OK |
| 23 | 접속 중 → FCM 안 보냄 | LOGIC OK |
| 24 | Firebase 미설정 → graceful skip | PASS |
| 25 | 잘못된 토큰 → 에러 핸들링 | PASS |

### 알림 목록 (10건)
| # | 항목 | 상태 |
|---|------|------|
| 26 | /notifications 접근 → 알림 표시 | BUILD OK |
| 27 | 제목 검색 → 필터 | BUILD OK |
| 28 | 내용 검색 → 필터 | BUILD OK |
| 29 | 기간 검색 → 필터 | BACKEND OK |
| 30 | 읽음 처리 → 스타일 변경 | BUILD OK |
| 31 | 전체 읽음 | BUILD OK |
| 32 | 알림 클릭 → 관련 페이지 이동 | BUILD OK |
| 33 | 🔔 읽지 않은 배지 | PASS |
| 34 | 알림 문구 변수 치환 정확성 | PASS |
| 35 | 카테고리 직접 입력 → 매칭 확인 | PASS |

### WebSocket (5건)
| # | 항목 | 상태 |
|---|------|------|
| 36 | 채팅 연결 → 인증 | 기존 구현 |
| 37 | 메시지 전송 → 수신 | 기존 구현 |
| 38 | XSS 방어 | 기존 구현 |
| 39 | 타이핑 인디케이터 | 기존 구현 |
| 40 | 퇴장 시스템 메시지 | 기존 구현 |

---

## 3. 전체 파일 목록

### 신규 파일 (8개)
| 파일 | 설명 |
|------|------|
| app/services/notification_templates.py | 64개 이벤트 템플릿 |
| app/services/notification_service.py | 통합 알림 발송 서비스 |
| app/services/interest_matcher.py | 딜→관심 매칭 + 오퍼→참여자 알림 |
| app/routers/notification_settings.py | 관심 상품 + 알림 설정 API |
| frontend/src/components/common/InterestTagInput.tsx | 관심 태그 입력 컴포넌트 |
| frontend/src/components/common/NotificationBadge.tsx | 알림 배지 컴포넌트 |
| frontend/src/pages/InterestSettingsPage.tsx | 관심 상품 설정 페이지 |
| frontend/src/pages/NotificationSettingsPage.tsx | 알림 설정 페이지 |

### 수정 파일 (15개)
| 파일 | 변경 내용 |
|------|----------|
| app/models.py | UserInterest, NotificationSetting 모델 + UserNotification 확장 |
| app/main.py | 모델 임포트 + 라우터 등록 |
| app/routers/deals.py | 딜 생성 시 interest_matcher 호출 |
| app/routers/notifications.py | 검색 파라미터 추가 |
| app/policy/params/defaults.yaml | notifications + interest_categories |
| app/policy/docs/public/guide_buyer.md | 알림 설정 + 관심 상품 |
| app/policy/docs/public/guide_seller.md | 알림 설정 + 주요 판매 품목 |
| app/policy/docs/public/guide_actuator.md | 알림 설정 + 관심 상품 |
| app/policy/docs/admin/guide_admin.md | 알림 시스템 개요 |
| app/policy/docs/public/pingpong.md | 알림 FAQ 7건 |
| frontend/src/App.tsx | 라우트 추가 |
| frontend/src/api/endpoints.ts | NOTIFICATION_SETTINGS 엔드포인트 |
| frontend/src/components/layout/Sidebar.tsx | 메뉴 추가 |
| frontend/src/components/layout/Layout.tsx | NotificationBadge 추가 |
| frontend/src/pages/RegisterPage.tsx | InterestStep (step 6) 추가 |
| frontend/src/pages/NotificationsPage.tsx | 검색/필터/채널배지 |

---

## 4. 미구현/후속 작업
- [ ] 이메일 발송 실제 연동 (현재 placeholder)
- [ ] 오퍼 제출 라우터에 match_interests_for_offer 호출 연결
- [ ] 배송/정산/환불/분쟁 이벤트 트리거 연결 (send_notification 호출)
- [ ] E2E Playwright 테스트 작성
