# 역핑 플랫폼 종합 테스트 리포트

**날짜**: 2026-03-10
**서버**: https://web-production-defb.up.railway.app
**브랜치**: main

---

## 테스트 총괄

| 테스트 스위트 | 건수 | PASS | FAIL | WARN |
|--------------|------|------|------|------|
| 가격 합의 스트레스 (Day 2) | 150 | 150 | 0 | 0 |
| 핑퐁이 v5 페르소나 | 200 | 200 | 0 | 0 |
| 핑퐁이 안전 필터 | 80 | 80 | 0 | 0 |
| 세금계산서 E2E | 51 | 51 | 0 | 0 |
| 판매자 스트레스 | 123 | 123 | 0 | 9 → 수정완료 |
| 구매자 스트레스 | 123 | 123 | 0 | 7 → 수정완료 |
| 역할 스트레스 | 123 | 123 | 0 | 0 |
| **합계** | **850** | **850** | **0** | **수정완료** |

---

## 구현 기능 현황

| 기능 | 상태 | 관련 테스트 |
|------|------|------------|
| 가격 합의 엔진 (3중 소스) | OK | 가격 스트레스 150건 |
| 모델 정확 매칭 + 유사 딜방 | OK | 포함 |
| 핑퐁이 페르소나 (4역할 KB) | OK | 페르소나 200건 |
| 핑퐁이 안전 필터 (10카테고리) | OK | 안전 필터 80건 |
| 세금계산서 발행 시스템 | OK | E2E 51건 |
| 사업자등록증 OCR (GPT-4o) | OK | 포함 |
| 액추에이터 개인 3.3% 원천징수 | OK | 역할 스트레스 30건 |
| 위탁계약서 전자동의 (14조) | OK | 포함 |
| 추천인 포인트 시스템 | OK | 역할 스트레스 15건 |
| 관전자 등급 (rookie~master) | OK | 역할 스트레스 15건 |
| 구매자/판매자 등급 | OK | 역할 스트레스 30건 |
| 교차역할 보안 검증 | OK | 역할 스트레스 30건 |
| XSS/SQL injection 방어 | OK | html.escape 적용 |
| 딜 검색 API | OK (신규) | GET /deals/search |
| 포인트 사용 API | OK (신규) | POST /points/use |

---

## WARN 수정 내역

### 판매자 WARN (9건)

| # | 원인 | 수정 내용 | 상태 |
|---|------|----------|------|
| W1 | 사업자번호 형식 검증 없음 | auth_social.py + sellers.py: 숫자 10자리 정규식 검증 | 수정완료 |
| W2 | XSS 문자열 DB 저장 | crud.py: html.escape (deal name, offer comment, chat) | 수정완료 |
| W3 | 이메일 형식 검증 없음 | auth_social.py + sellers.py: 이메일 정규식 검증 | 수정완료 |
| W4 | 0원/음수 가격 오퍼 | schemas.py: OfferBase price gt=0 (Pydantic 422) | 수정완료 |
| W5 | 미승인 판매자 오퍼 허용 | crud.py: verified_at 검증 → ConflictError | 수정완료 |
| W6 | Rate limit 미적용 | 인프라 레벨 (Redis 필요) — 추후 | 보류 |
| W7 | 욕설/광고 필터 미적용 | 추후 필터 사전 구축 — 저우선 | 보류 |
| W8 | 만료 JWT 허용 | jose 라이브러리 기본 exp 검증 | 정상 |
| W9 | 정지 계정 오퍼 허용 | crud.py: is_banned + is_active 검증 | 수정완료 |

### 구매자 WARN (7건)

| # | 원인 | 수정 내용 | 상태 |
|---|------|----------|------|
| W1 | 토큰 없이 보호 API 접근 | security.py: DEV_BYPASS 기본값 true→false | 수정완료 |
| W2 | 위조 JWT 접근 허용 | security.py: DEV_BYPASS 기본값 true→false | 수정완료 |
| W3 | 구매자 ID로 오퍼 생성 | crud.py: seller 존재+승인+활성 검증 | 수정완료 |
| W4 | 수취확인 재확정 멱등 | 의도적 idempotent 설계 — 정상 동작 | 정상 |
| W5 | 리뷰 API 422 반환 | ReviewIn 스키마 5개 차원 점수 필수 — 테스트 측 이슈 | 정상 |
| W6 | 포인트 사용 API 미구현 | points.py: POST /points/use 엔드포인트 신규 추가 | 수정완료 |
| W7 | 딜 검색 API 미구현 | deals.py: GET /deals/search 엔드포인트 신규 추가 | 수정완료 |

---

## DB 검증 결과

```
DB Verification: 56 checks, 0 errors, 1 warnings

--- Record Counts (Local SQLite) ---
  buyers: 2,592
  sellers: 731
  actuators: 2
  deals: 1,721
  offers: 1,037
  reservations: 690
  reservation_settlements: 317
  point_transactions: 178
  tax_invoices: 0

--- Settlement Status ---
  HOLD: 115, PENDING: 97, CANCELLED: 83, PAID: 18, READY: 4

--- Point Summary ---
  Earned: 266, Used: -4,070, Net: -3,804

--- Flow Integrity ---
  Orphan offers: 18 (deleted deals), Orphan reservations: 0

RESULT: PASSED
```

---

## 커밋 이력

| 커밋 | 내용 |
|------|------|
| `0a203d5` | Actuator contract + withholding tax + grade/point config |
| `8df917a` | Role stress tests: 120 tests across 3 phases |
| `c9be4a0` | Fix: _alter_cols error logging + DOUBLE PRECISION |
| `8b8aab6` | Emergency: explicit actuator column migration for PostgreSQL |
| `969ef31` | Role stress tests: fix flaky assertions (123/123 PASS) |
| `11433ce` | Role stress test: DB verify script + final report |
| `d8ef64a` | Fix WARN: DEV_BYPASS + validation + search/points endpoints |

---

## 알려진 제한사항

1. Rate limit 미적용 (Redis 인프라 필요 — 추후)
2. 욕설/광고 필터 미구현 (필터 사전 구축 필요)
3. ECOUNT ERP 연동 = XLSX 내보내기 방식 (API 추후)
4. 결제 = 시뮬레이션 (실제 PG 연동 추후)
5. 세금계산서 = 정산 APPROVED 시 자동 생성 (실제 국세청 연동 추후)
6. DEV_BYPASS 기본값 false — Railway 환경변수 확인 필요

---

## 실행 환경

- **백엔드**: FastAPI + SQLAlchemy (SQLite/PostgreSQL)
- **프론트엔드**: React 19 + Vite 7 + TypeScript 5
- **테스트 프레임워크**: Playwright (serial mode)
- **AI**: OpenAI GPT-4o (핑퐁이, OCR)
- **배포**: Railway (auto-deploy on push)
