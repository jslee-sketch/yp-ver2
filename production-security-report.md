# Production Security Hardening Report

## Date: 2026-03-11

---

## 1. DEV_BYPASS Default False
- **상태**: DONE (기존 설정 확인)
- `app/security.py` — `DEV_BYPASS` 기본값 `"false"` 유지
- SECRET_KEY 기본값 사용 시 경고 메시지 추가

## 2. Auth-Missing Endpoint Audit + Admin Auth Middleware
- **상태**: DONE
- **발견**: 82+ 엔드포인트에 인증 미적용 (특히 `/admin/*` 전체 무방비)
- **조치**: `app/middleware/admin_auth.py` — AdminAuthMiddleware 추가
  - `/admin/*` 모든 엔드포인트에 JWT + `role=admin` 검증
  - 유효하지 않은 토큰 → 401, admin 아닌 역할 → 403
  - OPTIONS (CORS preflight) 통과

## 3. CORS Hardening
- **상태**: DONE
- `ALLOWED_ORIGINS` 환경변수로 프로덕션 도메인 제어
- 프로덕션: `ALLOWED_ORIGINS=https://web-production-defb.up.railway.app,https://yeokping.com`
- 개발: `ALLOWED_ORIGINS=*` (기본값)

## 4. Secret Key Hardening
- **상태**: DONE (문서화)
- Railway 환경변수에 강력한 `SECRET_KEY` 설정 필요:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
- 기본값 사용 시 `warnings.warn()` + 콘솔 경고

## 5. SQL Injection Final Defense
- **상태**: DONE (감사 완료 — 안전)
- `basic_info.py`, `admin_custom_report.py`, `buyers_extended.py` — 모든 f-string은 서버측 화이트리스트 기반, 사용자 입력 없음
- 모든 사용자 입력 값은 `:param` 바인딩 사용

## 6. Rate Limiting
- **상태**: DONE
- `app/middleware/rate_limit.py` — IP 기반 인메모리 rate limiter
  - 기본: 100 req/min (`RATE_LIMIT_RPM` 환경변수)
  - AI 엔드포인트: 10 req/min
  - Admin 엔드포인트: 30 req/min
- 429 Too Many Requests 응답

## 7. Error Handling (Production)
- **상태**: DONE
- `DEV_DEBUG_ERRORS` = `DEV_BYPASS` 환경변수 연동
- 프로덕션: 상세 에러 숨김 → `"서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."`
- 개발: 에러 클래스명, 메시지, 트레이스 tail 노출
- 모든 500 에러는 서버 로그에 전체 traceback 기록

## 8. DB Indexes for Performance
- **상태**: DONE
- `ReservationSettlement`:
  - `ix_settlement_seller_status` (seller_id, status)
  - `ix_settlement_status_created` (status, created_at)
- `UserNotification`:
  - `ix_notif_user_read` (user_id, is_read)
  - `ix_notif_user_created` (user_id, created_at)

## 9. Health Check Enhancement
- **상태**: DONE
- `GET /health` — DB 접속 확인, 버전, 타임스탬프 포함:
  ```json
  {"ok": true, "status": "ok", "db": "ok", "version": "2.0.0", "timestamp": "2026-03-11T07:44:17.373308+00:00"}
  ```
- `GET /health/deep` — 디스크 사용량, DB 응답시간 포함

## 10. Build + Push
- **상태**: DONE (아래 커밋 참조)

## 11. Production Security E2E Tests (20/20 PASS)

### Phase 1: Admin Endpoint Protection (5건)
| # | 항목 | 상태 |
|---|------|------|
| 1 | GET /admin/settlements/ without token → 401 | PASS |
| 2 | GET /admin/stats/counts without token → 401 | PASS |
| 3 | POST /admin/users/ban without token → 401 | PASS |
| 4 | Admin endpoint with buyer token → 403 | PASS |
| 5 | Admin endpoint with admin token → 200 | PASS |

### Phase 2: Public Endpoints Accessible (5건)
| # | 항목 | 상태 |
|---|------|------|
| 6 | GET /health → 200 (no auth needed) | PASS |
| 7 | GET /health/deep → 200 (no auth needed) | PASS |
| 8 | GET /deals/ → 200 (public list, no auth) | PASS |
| 9 | POST /auth/login valid creds → 200 + token | PASS |
| 10 | POST /auth/login wrong password → 401 | PASS |

### Phase 3: Rate Limiting & Error Handling (5건)
| # | 항목 | 상태 |
|---|------|------|
| 11 | Rate limiter → 429 after burst | PASS |
| 12 | 500 error hides details in production | PASS |
| 13 | Invalid JSON body → 422 (not 500) | PASS |
| 14 | Non-existent API path → graceful | PASS |
| 15 | CORS headers present | PASS |

### Phase 4: JWT Security & Auth Flow (5건)
| # | 항목 | 상태 |
|---|------|------|
| 16 | Expired/invalid JWT → 401 | PASS |
| 17 | JWT with tampered payload → 401 | PASS |
| 18 | Admin login → JWT with role=admin | PASS |
| 19 | Buyer social login → JWT with role=buyer | PASS |
| 20 | Health check → DB status + version + timestamp | PASS |

---

## 수정 파일 목록

| 파일 | 변경 내용 |
|------|----------|
| `app/security.py` | SECRET_KEY 기본값 경고 추가 |
| `app/main.py` | DEV_DEBUG_ERRORS 연동, 에러 핸들러 강화, health check 강화, CORS 문서화, rate limit 100rpm, AdminAuthMiddleware 마운트 |
| `app/models.py` | ReservationSettlement + UserNotification 인덱스 추가 |
| `app/middleware/admin_auth.py` | 신규 — Admin JWT 인증 미들웨어 |
| `tests/e2e-production-security.spec.ts` | 신규 — 20건 프로덕션 보안 E2E 테스트 |
| `production-security-report.md` | 본 리포트 |

---

## 후속 작업 (권장)
- [ ] Railway `SECRET_KEY` 환경변수 설정 (강력한 랜덤 키)
- [ ] Railway `ALLOWED_ORIGINS` 환경변수 설정 (프로덕션 도메인만)
- [ ] 비-admin 엔드포인트 (payments, settlements, points 등) 개별 인증 추가
- [ ] 소유권 검증 (buyer_id 매칭 등) 추가
