---

📘 PROJECT_RULES_v3.5_DeadTimeAware.md

YeokPing (역핑) 거래정책 v3.5 — Working Hour-Aware Edition
Writer: Jeong Sang Lee
Date: 2025-11-12
Version: 3.5 (Stable Declaration)


---

1️⃣ 개요

역핑(YeokPing) 은 소비자가 조건을 먼저 제시하고, 판매자가 그 조건에 맞춰 가격과 조건을 제안(Offer)하는 소비자 주도형 역입찰 공동구매 플랫폼입니다.

핵심 철학:

> “판매자가 입찰하고, 소비자가 선택한다.”



모든 거래는 공정성, 신뢰성, 참여 유도성을 원칙으로 설계됩니다.


---

2️⃣ 시스템 기본 구조

단계	주체	설명

1	구매자(방장)	상품명, 수량, 희망가, 옵션(최대 5개), 자유기재로 Deal 생성
2	구매자(참여자)	기존 Deal에 참여(수량 입력)
3	판매자	조건을 기반으로 Offer 제출(가격, 수량, 자유기재)
4	거래성립	구매자 결제 → 판매자 수락/철회 → 확정 또는 무산



---

3️⃣ 타임라인 (KST, UTC+9) — Dead Time 반영

이벤트	소요시간	설명

(1) Deal 생성 ~ 모집 마감	24h (Dead Time 제외)	신규 판매자 승인(최대 12h)과 병렬 가능
(2) 신규 판매자 승인	≤ 12h	서류 검토 완료 시 Offer 가능
(3) Offer 제출·수정 가능	Offer 생성 ~ Offer 마감 전	마감 전 자유 수정
(4) 구매자 결제 창	2h (총)	방장 우선 15분 → 이후 전체 구매자 동시 결제 가능(2h 안 포함)
(5) 판매자 수락/철회 결정	30m	(4) 종료 직후 30분 내 미응답 시 자동 철회
(6) Dead Time	평일 18:00~익일09:00 + 주말·공휴일 전시간	모든 타이머 Pause/Resume


> Dead Time 원칙: Dead Time 동안 모든 마감 타이머 정지, 영업시간 재개 시 남은 시간만큼 이어서 진행.




---

4️⃣ Dead Time 정책 (Pause/Resume)

기준 타임존: KST (UTC+9)

주말/공휴일/야간(18:00~09:00) 동안 모든 타이머 일시정지

Deal/Offer 마감, 결제창 2h, 판매자 30m 결정, 예약 보류시간(hold TTL) 모두 Pause/Resume 대상


재개 시점에 남은 시간부터 카운트


예시

금 17:00, 24h 타이머 시작 → 월 09:00 마감

수 22:00, 24h 타이머 시작 → 금 09:00 마감


시스템 메시지 예:

> “⏸ Dead Time입니다. 남은 7시간 25분은 다음 영업시간부터 재개됩니다.”




---

5️⃣ Offer 수락/철회 정책 (v3.5 확정 규칙)

판매 결과 상태	판매자 행동	결과	비고

부분수량 판매 (결제 일부 발생)	철회 가능(30m 이내)	거래 무산	자동 환불 처리(결제건 전액 환불)
완전수량 판매 (전량 결제 완료)	철회 불가 / 수락 필수	자동 확정	sold_qty == total_available_qty 시 자동수락/확정
결제 미발생	철회 가능(30m 이내)	거래 무산	미응답 30m 경과 시 자동 철회


“전량 판매 성공”의 판단 기준: sold_qty == total_available_qty

판매자 미응답: 결제창 종료 후 30m 경과 시 자동 철회 처리

판매자 철회로 거래 무산 시: 모든 결제 전액 환불(자동)



---

6️⃣ 예약/결제/취소 상태 (Reservation Lifecycle)

상태 흐름: PENDING → PAID → (CANCELLED | 확정 포함), 또는 보류시간 경과 시 EXPIRED

PENDING: 예약 생성, 보류시간(기본 5분) 내 결제 가능 (Dead Time 중 Pause)

PAID: 결제 완료 (바이어 포인트 즉시 적립)

CANCELLED:

구매자 취소, 또는

판매자 철회로 인한 강제 취소, 또는

운영/시스템에 의한 취소


EXPIRED: 보류시간 초과로 자동 만료


> 포인트 정책 (v3.5)

결제 성공(PAID): +20 pt

결제 취소(환불 발생, 사유 무관): −20 pt (해당 결제로 적립된 포인트 되돌림)

PENDING → CANCELLED/EXPIRED(결제 전): 포인트 변동 없음





---

7️⃣ 포인트/등급 체계

7-1. 구매자 Trust Tier (누적 이행률 기반, v3.5)

이행률 정의: fulfillment_rate = 이행건수 / 총 참여건수

이행건수 포함:

PAID로 결제 완료된 예약

결제 후 판매자 철회로 무산된 예약(구매자 책임 아님) → 이행으로 간주


티어 기준(누적)


티어	기준	Deposit 비율	비고

Tier 1	참여 ≥ 10, 이행률 ≥ 95%	0%	골드 뱃지
Tier 2	참여 ≥ 10, 86%~95%	5%	실버 뱃지
Tier 3	참여 ≥ 10, 61%~85%	8%	브론즈 뱃지
Tier 4	기본/신규	10%	기본 참여 가능
Tier 5	참여 ≥ 5 & 이행률 ≤ 20%	10%	참여 제한(차단)


> 티어 산정은 매일 배치 또는 이벤트 트리거로 증분 갱신.



7-2. 구매자 Point 등급 (표시/혜택 용도)

등급	포인트 구간	혜택

브론즈	0~50	등급 표시
실버	51~200	등급 표시
골드	201~500	등급 표시
플래티넘	500+	등급 표시


적립/차감 규칙 (v3.5)

결제 성공(PAID): +20 pt

결제 취소(사유 무관, 환불 발생): −20 pt

PENDING 단계에서의 취소/만료: 변동 없음

Idempotency 보장: 동일 결제/환불에 대해 중복 적립·차감 방지



7-3. 판매자 Level & 수수료

레벨	조건(누적 거래/평점)	수수료

Lv.6	신규~20건	3.5%
Lv.5	21~40건 & 역핑평점 4.0+	3.0%
Lv.4	41~60건 & 역핑평점 4.0+	2.8%
Lv.3	61~100건 & 역핑평점 4.0+	2.7%
Lv.2	100건+ & 역핑평점 4.0+	2.5%
Lv.1	100건+ & 역핑평점 4.5+	2.0%


> 역핑평점 = 베이지안 보정 가중 평균(아래 §8 참조).
조건·수수료는 중앙 규칙 파일에서 상시 조정 가능.




---

8️⃣ 역핑 리뷰 시스템 (Verified·가중·보정형)

원칙

Verified Purchase Only: Reservation PAID 경험자만 리뷰 가능
(단, 판매자 철회로 무산된 케이스도 리뷰 허용)

다차원 평가(최소 5축):
price_fairness, quality, shipping, communication, accuracy (각 1~5점)


가중치

구매자 티어 가중: T1/T2 상향, T4/T5 하향

시간 가중: 반감기 365일(최신 리뷰 가중 ↑)

미디어 가중: 사진/영상 포함 시 +5%/매체, 최대 +25%


집계

베이지안 평균: Prior mean 4.3, prior weight 5

“도움돼요” 정렬: **윌슨 신뢰구간(95%)**로 품질 정렬


안전장치

동일 예약 중복 리뷰 금지

자기거래/조작 방지: 이상치 탐지, IP/패턴 감시

리뷰 신고·블라인드, 셀러 1회 답글(수정 제한) 워크플로


판매자 등급 연동

SellerRatingAggregate.rating_adjusted(보정 평점)를 레벨 조건의 평점으로 사용

리뷰 생성/수정 시 집계 즉시/지연 갱신 모드 선택 가능



---

9️⃣ Offer 노출·제출 규칙

조건	처리

Offer 금액 ≤ 구매희망가	전면 노출
구매희망가 < 금액 ≤ 구매희망가 + 10%	“프리미엄 제안” 섹션 제한 노출
금액 > 구매희망가 + 10%	Offer 제출 불가(차단)


> 과도한 고가 제안 방지로 품질 관리.




---

🔟 Trigger Points (시스템 트리거)

이벤트	트리거

Deal Closing	모집시간 24h 경과 (Dead Time 제외)
Offer Phase Start	Deal 모집 마감 직후
Offer Closing	정책상 마감 시각 도래
구매자 결제 가능	결제창 2h 오픈(방장 15m 선점 포함)
판매자 수락/철회	결제창 종료 후 30m 내
Trust/Tier 갱신	일/주 단위 스케줄러
신규 판매자 승인	서류 검토 완료 시 활성



---

1️⃣1️⃣ Deposit 정책

항목	규칙

기본 비율	10% (티어에 따라 0~10%)
납입 시점	Deal 모집 마감 이전까지
미납 시	해당 Deal 자동 탈퇴
반환	판매자 수락/철회 마감 시점에 100% 즉시 반환 (거래 성사/무산 무관)
몰수	없음(의도 불참은 Trust/포인트로 관리)
목적	허수 참여 억제 + 신뢰 강화



---

1️⃣2️⃣ 상태 전이(개략)

Round: PLANNED → OPEN → FINALIZING → (CLOSED | CANCELLED)

Reservation: PENDING → (PAID | CANCELLED | EXPIRED)

Offer 확정:

sold_qty == total_available_qty ⇒ 자동 수락/확정(철회 불가)

그 외(부분/무판매) ⇒ 30m 내 판매자 철회 가능, 미응답 자동 철회




---

1️⃣3️⃣ 검색·중복방지 규칙 (Buyer/Seller 공통)

정확 일치 사전검사(Precheck)

신규 Deal 생성 시, 제품명/옵션 정규화 후 정확 지문(fingerprint) 생성

정확 매칭 존재: 해당 Deal로 이동하여 참여할지 여부 확인

정확 매칭 없음: 신규 Deal 생성 진행


검색(노출)

Buyer: 제품명/옵션으로 기존 Deal 검색, 필터(진행중/마감/라운드 상태, 가격대, 옵션 키워드)

Seller: 자신이 파는 제품명 중심으로 Deal 검색 → Offer 제안 진입


정규화 규칙(예시)

Lowercase, 공백/특수문자 정리, 한글 자모/영문 변환 일관화, 옵션 키-값 정렬 및 직렬화 → SHA-1 등으로 해시



---

1️⃣4️⃣ 오류/차단 시나리오 표준 처리

시나리오	시스템 처리

Overbook(남은수량 초과 예약)	예약 거절(409), 이벤트 로그 기록
Wrong-owner Pay(타인 결제 시도)	결제 거절(409), 이벤트 로그
Pay after Expire(만료 후 결제)	거절(409), 이벤트 로그
Cancel after Paid(결제 후 취소 시도)	정책에 따라 환불/포인트 −20, 이벤트 로그
Confirm Not Soldout(미완판 확정 시도)	거절(409), 이벤트 로그


> 모든 예외는 Idempotency Key 기반으로 중복 처리 방지.




---

1️⃣5️⃣ 감사로그·가시성(관리자/사용자)

거래 이벤트 로그: 예약/결제/취소/만료/확정 전 과정을 이벤트 스트림으로 기록

필드(예): event_type, actor_type, actor_id, deal_id, offer_id, reservation_id, amount/qty, reason, idempotency_key, created_at


포인트/티어/리뷰/레벨 로그:

관리자: 전체 현황(집계·분포·추이), 개별 ID 상세, 증감 로그(사유/타임스탬프) 조회

구매자/판매자: 본인 계정의 현재 등급·포인트·리뷰/평점, 증감 로그(초 단위) 조회


데이터 보존·내보내기: CSV/JSON 익스포트



---

1️⃣6️⃣ 중앙 규칙 파일(코드 반영 가이드)

모든 숫자/가중치/임계값은 단일 파일에서 관리:
app/config/rules_v3_5.py

예시 키(권장):

시간/윈도우:
DEAL_CREATION_WINDOW_H, SELLER_VERIFICATION_WINDOW_H,
OFFER_EDITABLE_WINDOW_H, BUYER_PAYMENT_WINDOW_H,
BUYER_LEADER_PRIORITY_MIN, SELLER_DECISION_WINDOW_MIN,
RESERVATION_HOLD_MIN

Dead Time:
WEEKDAY_START, WEEKDAY_END, PAUSE_WEEKENDS, PAUSE_HOLIDAYS, TIMEZONE

가격 노출 임계:
PREMIUM_THRESHOLD_PCT(예: 10)

포인트:
BUYER_PAY_REWARD_PT(예: +20), BUYER_REFUND_PENALTY_PT(예: −20)

Deposit 비율:
DEPOSIT_BASE_PCT(기본 10), DEPOSIT_BY_TIER = {T1:0, T2:5, T3:8, T4:10, T5:10}

리뷰 가중:
RATING_PRIOR_MEAN, RATING_PRIOR_WEIGHT,
RATING_HALF_LIFE_DAYS, MEDIA_WEIGHT_STEP, MEDIA_WEIGHT_MAX,
TIER_WEIGHT = {T1:1.1, T2:1.05, T3:1.0, T4:0.95, T5:0.9}

등급/레벨:
BUYER_POINT_TIERS, SELLER_LEVELS, SELLER_FEE_BY_LEVEL

검색 정규화:
NORMALIZE_OPTIONS, FINGERPRINT_ALGO




---

1️⃣7️⃣ 향후 확장 (로드맵)

옵션 자동매칭(AI), Seller Trust Index(응답률/이행시간)

실시간 상담(인앱 채팅)

실패딜 리포트 자동화(미결제/비응답 원인 분석)

멀티 리전 Dead Time / 리전별 공휴일 캘린더



---

✅ 결론

v3.5는 판매자 수락/철회 규칙(부분/전량), 구매자 포인트(결제 +20 / 취소 −20),
구매자 Trust Tier(누적 이행률), 역핑 리뷰(가중·보정형), 검색/중복방지를 표준화했습니다.
Dead Time 기반 Pause/Resume로 공정한 타이밍을 보장하고, 중앙 규칙 파일로 운영 민첩성을 확보합니다.

> “역핑은 시간의 공정성 + 데이터 기반 신뢰로 움직이는 유통 OS입니다.”