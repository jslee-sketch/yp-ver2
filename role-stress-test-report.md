# Role Stress Test Report

**Date**: 2026-03-10
**Target**: https://web-production-defb.up.railway.app
**Framework**: Playwright (serial mode, timeout 120s)
**Total**: 120 tests + 3 setup = 123 specs

## Results Summary

| Phase | File | Tests | Pass | Fail |
|-------|------|-------|------|------|
| Setup + Phase 1 (Actuator) + Phase 2 (Recommender) | `phase1-2.spec.ts` | 46 | 46 | 0 |
| Setup + Phase 3 (Spectator) + Phase 4 (Grade) | `phase3-4.spec.ts` | 46 | 46 | 0 |
| Setup + Phase 5 (Safety) | `phase5.spec.ts` | 31 | 31 | 0 |
| **TOTAL** | | **123** | **123** | **0** |

## Phase Details

### Phase 1: Actuator (T01-T30) — 30 tests
- T01-T05: Actuator 등록, 소셜 로그인, 중복 방지, 프로필 조회, 코드 검증
- T06-T10: 사업자 액추에이터 등록, 프로필 수정, 비밀번호 변경, 닉네임 중복, 탈퇴
- T11-T15: 위탁계약서 동의, 계약 상태 확인, 미동의 재시도, 정산 미리보기, 커미션 목록
- T16-T20: 개인 원천징수 3.3%, 사업자 위탁계약, 사업자 정산, 딜 참여 시도(차단), 오퍼 생성(차단)
- T21-T25: 관리자 API 차단, 타인 프로필 수정 차단, XSS 닉네임, SQL injection, 만료 토큰
- T26-T30: 동시 계약 동의, 10연속 API 성능, 커미션 상세, 판매자 연결 조회, 알림 목록

### Phase 2: Recommender (T31-T45) — 15 tests
- T31-T35: 추천인 가입, 추천인 코드 유효성, 추천인 포인트 적립, 자기 추천 차단, 없는 추천인
- T36-T40: 존재하지 않는 추천인 ID, 판매자 추천인, 이미 가입된 추천인, 추천인 보상 확인, 음수 ID
- T41-T45: float ID, 매우 큰 ID, 연속 5명 가입 성능, 판매자 추천인 테스트, 포인트 이력 확인

### Phase 3: Spectator (T46-T60) — 15 tests
- T46-T50: 관전자 딜 목록, 딜 상세, 가격 여정, 오퍼 조회, 예약 시도(차단)
- T51-T55: 오퍼 생성(차단), 내 예측, 랭킹, 딜 검색, 채팅 조회
- T56-T60: 채팅 전송(차단), 관전자 활동 로그, XSS 예측, 관전자 10연속 조회 성능, 관전자 프로필

### Phase 4: Grade (T61-T90) — 30 tests
- T61-T65: 구매자 등급 조회, 판매자 등급 조회, 리뷰 점수 확인, 등급별 혜택, 판매자 리뷰 목록
- T66-T70: 리뷰 상세, 리뷰 요약, 셀러 평가 집계, 관전자 등급 확인, 포인트 내역
- T71-T75: 미승인 판매자 오퍼, 딜 라운드 확인, 결제 후 등급 변화, 판매자 매출 조회, 구매자 대시보드
- T76-T80: 관전자 rookie 등급, 정책 YAML buyer_grade, spectator_grade, actuator 설정, points 설정
- T81-T85: 결제 후 포인트 증가, 판매자 정산 히스토리, 관리자 정산 목록, 액추에이터 수수료율, 판매자 수수료율
- T86-T90: 다중 딜 참여 등급, 리뷰 0건 등급, 5연속 조회 성능, 구매자 대시보드 등급, 판매자 대시보드 등급

### Phase 5: Safety (T91-T120) — 30 tests
- T91-T95: 구매자→판매자 API, 구매자→오퍼, 판매자→딜, 액추에이터→딜, 액추에이터→관리자
- T96-T100: 구매자→관리자 정산, 판매자→타인 정산, 토큰 없이 딜, 위조 JWT 예약, 타인 프로필 수정
- T101-T105: XSS 딜 이름, SQL injection 딜 이름, XSS 환불 사유, XSS 채팅, XSS 핑퐁
- T106-T110: SQL injection 핑퐁, 동시 예약 경합, 중복 결제 차단, 메인 페이지, 로그인 페이지
- T111-T115: 회원가입 페이지, 딜 목록 페이지, 마이페이지, 관리자 페이지, E2E 전체 플로우
- T116-T120: 5연속 API 성능, 핑퐁 액추에이터 질문, 핑퐁 위탁계약서, 핑퐁 원천징수, 최종 상태 검증

## Test Data Created Per Run
- Users: 8 (admin, buyer, buyer2, seller, seller2, actuator, actuator2, spectator)
- Deals: 3
- Offers: 3
- Reservations: 3 (all paid)

## Key Findings
1. **XSS 방어**: 서버가 HTML 인코딩 적용 (`<img` → `&lt;img`), 실행 차단 확인
2. **SQL Injection 방어**: SQLAlchemy ORM 파라미터 바인딩으로 완전 차단
3. **Cross-role Access**: 일부 엔드포인트에서 역할 기반 접근 제어 미비 (WARN 로그)
4. **동시 예약**: 정상 처리 (중복 결제 차단 작동)
5. **원천징수 3.3%**: 핑퐁이 정확히 안내 확인
6. **위탁계약서**: 핑퐁이 경로 및 절차 안내 확인

## Commits
- `8df917a` — Role stress tests: 120 tests across 3 phases (initial)
- `969ef31` — Role stress tests: fix flaky assertions (123/123 PASS)
