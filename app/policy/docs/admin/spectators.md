# 관전자(Spectator) 시스템 — SSOT 정책 문서

> **문서 버전**: v1.0  
> **최종 수정**: 2026-02-27  
> **상태**: 정책 확정 → 구현 대기  
> **YAML 파라미터**: `app/policy/params/spectator.yaml`

---

## 1. 개요

### 1-1. 관전자란?

관전자(Spectator)는 딜방에 직접 참여하지 않으면서, **거래 성사 가격을 예측**하는 사용자다.
예측이 적중하면 포인트를 받고, 누적 성과에 따라 랭커로 선정된다.

### 1-2. 목적

| 목적 | 설명 |
|------|------|
| **시장 가격 신호** | 다수의 관전자 예측값이 모이면 "시장이 생각하는 적정가"가 형성됨 |
| **커뮤니티 활성화** | 딜 참여 안 해도 역핑에 올 이유가 생김 (참여형 콘텐츠) |
| **참여 전환 유도** | 관전하다가 "이 가격이면 나도 살래" → 딜방 참여로 자연 전환 |
| **가격 발견 기능** | 관전자들의 예측 근거/코멘트가 딜 참여자에게 시장 정보로 기능 |

### 1-3. 한 줄 요약

> 딜방을 구경하다가 "이 딜은 얼마에 성사될 것 같다"고 1회 예측.
> 맞추면 포인트. 많이 맞추면 랭커.

---

## 2. 자격 및 권한

### 2-1. 관전 자격 (딜방 열람)

| 조건 | 관전 가능 여부 |
|------|---------------|
| 로그인한 구매자(Buyer) | ✅ |
| 로그인한 판매자(Seller) | ❌  |
| 로그인한 액추에이터(Actuator) | ❌  |
| 비로그인 | ❌ |

**모든 로그인 구매자**는 딜방을 관전(열람)할 수 있다.

### 2-2. 가격 예측 자격

| 조건 | 예측 제시 가능 여부 | 사유 |
|------|-------------------|------|
| 로그인한 구매자 + 해당 딜방 **미참여** | ✅ | 핵심 대상 |
| 로그인한 구매자 + 해당 딜방 **참여 중** | ❌ | 본인이 참여한 딜의 가격을 예측하는 건 이해충돌 |
| 로그인한 판매자 | ❌ | 판매자가 시장가를 조작할 유인 존재 |
| 로그인한 액추에이터 | ❌ (v1 기준) | 내부 운영자 제외. 향후 검토 가능 |

**핵심 원칙**: 가격 예측은 **해당 딜방에 이해관계가 없는 구매자**만 할 수 있다.

### 2-3. 관전 → 참여 전환

관전자(가격 예측 자격이 있는 구매자)는 언제든지 **딜방에 참여** 가능하다.

```
관전 중 → "이 딜 참여하기" → 딜방 참여자로 전환
```

**전환 시 규칙**:
- 이미 제출한 가격 예측은 **그대로 유효** (취소/삭제 안 됨)
- 딜방 참여 후에는 **추가 예측 불가** (이미 1회 제출했으므로)
- 아직 예측을 안 했으면, 참여 후에는 **예측 자격 소멸** (이해관계자가 되었으므로)

---

## 3. 가격 예측 메커니즘

### 3-1. 예측 가능 기간

```
딜방 생성 시점 ──────────────────── 딜방 마감 시점
     │          예측 제출 가능 구간          │
     ▼                                      ▼
  open_at                              deadline_at
```

- **시작**: 딜방 status가 `open`이 된 시점
- **종료**: 딜방 status가 `closed` / `completed` / `expired`가 된 시점
- 마감 후에는 예측 제출/수정 불가

### 3-2. 제출 규칙

| 항목 | 규칙 |
|------|------|
| 제출 횟수 | **딱 1회** (수정/취소 불가) |
| 입력 단위 | **1원 단위 자유 입력** |
| 입력 범위 | 1원 ~ 99,999,999원 (상한은 YAML에서 조정) |
| 필수 입력 | 예측 가격 (필수) |
| 선택 입력 | 예측 근거/코멘트 (선택, 최대 200자) |

### 3-3. 예측 근거/코멘트

관전자는 가격과 함께 **짧은 근거**를 남길 수 있다 (선택).

```
예측 가격: 310,000원
코멘트: "다나와 최저가 329,000인데 공구 10명이면 5% 할인 가능할 듯"
```

**코멘트 활용**:
- 딜방 참여자들에게 **시장 정보**로 노출 (익명/닉네임 선택)
- 향후 랭커 시스템에서 "근거의 질" 평가 요소로 활용 가능 (v2)
- 욕설/광고 필터링 필요 (v1은 기본 금칙어 필터)

### 3-4. 예측값 공개 정책

| 시점 | 다른 관전자에게 | 딜 참여자에게 |
|------|---------------|-------------|
| 예측 제출 직후 | ❌ 비공개 | ❌ 비공개 |
| 딜 마감 후 | ✅ 전체 공개 | ✅ 전체 공개 |

**이유**: 제출 전에 다른 관전자의 예측을 보면 **쏠림 현상** 발생.
딜 마감 후 일괄 공개하여 독립적 예측을 보장한다.

---

## 4. 적중 판정 및 포인트

### 4-1. "성사 가격"의 정의

```
성사 가격 = 딜에서 실제로 거래가 완료된 Offer의 최종 가격
```

- 하나의 딜에서 여러 Offer가 성사될 수 있음
- **판정 기준 가격**: 첫 번째 성사(status=PAID or COMPLETED) Offer의 price
- 성사된 Offer가 없으면 → 해당 딜의 모든 예측은 **무효** (포인트 없음)

### 4-2. 적중 구간 및 포인트 (구간별 차등)

|      구간        |    조건    | 기본 포인트 | 예시 (성사가 100,000원) |
|-----------------|-----------|------------|----------------------|
| 🎯 **정확 적중** | 오차 0원   |     5pt    | 100,000원 딱 맞춤     |
| 🔥 **근접**      | 오차 ≤ 1% |     3pt    | 99,000 ~ 101,000원   |
| 👍 **우수**      | 오차 ≤ 3% |     2pt    | 97,000 ~ 103,000원   |
| 👏 **참여**      | 오차 ≤ 5% |     1pt    | 95,000 ~ 105,000원   |
| ❌ **미스**      | 오차 > 5% |     0pt    | 범위 밖               |

### 4-3. 적중 판정 수식

```
오차율(%) = |예측가 - 성사가| / 성사가 × 100

예: 예측가 97,500원, 성사가 100,000원
   → |97,500 - 100,000| / 100,000 × 100 = 2.5%
   → ±3% 이내 → 2pt (우수)
```

### 4-4. YAML 파라미터

```yaml
# app/policy/params/spectator.yaml

spectator:
  # ── 예측 규칙 ──
  prediction:
    max_per_deal: 1           # 딜당 최대 예측 횟수
    min_price: 1              # 최소 입력가 (원)
    max_price: 99999999       # 최대 입력가 (원)
    comment_max_length: 200   # 코멘트 최대 글자수
    reveal_after_close: true  # 마감 후 예측값 공개

  # ── 적중 판정 ──
  scoring:
    # 구간별 임계값 (% 단위) — 좁은 구간이 우선 판정
    tiers:
      - name: "exact"
        max_error_pct: 0      # 정확 일치
        points: 5
        label: "🎯 정확 적중"
      - name: "close"
        max_error_pct: 1      # ±1% 이내
        points: 3
        label: "🔥 근접"
      - name: "good"
        max_error_pct: 3      # ±3% 이내
        points: 2
        label: "👍 우수"
      - name: "participate"
        max_error_pct: 5      # ±5% 이내
        points: 1
        label: "👏 참여"
    miss_points: 0            # 미스 시 포인트
    no_deal_settled: null     # 성사 없으면 무효 (포인트 없음)

  # ── 성사가 기준 ──
  settlement:
    # 어떤 Offer를 "성사 가격"으로 볼 것인가
    target_status:
      - "PAID"
      - "COMPLETED"
    # 여러 Offer 중 기준
    pick: "first"             # "first" | "lowest" | "average"
```

---

## 5. 랭커 시스템

### 5-1. 랭킹 기간

**월간 리셋** 방식.

```
매월 1일 00:00 ~ 말일 23:59 (KST)
→ 해당 월 내 적중 포인트 합산으로 순위 결정
→ 다음 달 1일에 리셋
```

**누적 랭킹**은 별도로 유지 (명예의 전당).

### 5-2. 랭킹 지표

| 지표              | 설명                      |    표시     |
|------------------|---------------------------|------------|
| **총 포인트**     | 월간 적중 포인트 합계        | "320pt"    |
| **참여 횟수**     | 예측 제출한 딜 수           | "42회 참여" |
| **적중 횟수**     | 1pt 이상 받은 횟수          | "28회 적중" |
| **적중률**        | 적중 횟수 / 참여 횟수 × 100 | "66.7%"    |
| **정확 적중 횟수** | 5pt(정확) 받은 횟수        | "🎯 × 3"   |
| **평균 오차율**    | 전체 예측의 평균 오차(%)    | "2.3%"     |

**기본 정렬**: 총 포인트 내림차순. 동점 시 적중률 → 참여 횟수 순.

### 5-3. 랭커 등급

| 등급           | 이름       | 조건 (월간)         | 뱃지     | 혜택                    |
|---------------|------------|-------------------|----------|------------------------|
| 🏆 **구루**   | 가격의 신    | 월간 1위           | 금색 왕관 | 전용 뱃지 + 보너스 포인트 |
| 🥇 **마스터** | 시세 달인    | 월간 Top 3         | 은색 메달 | 전용 뱃지 + 보너스 포인트 |
| 🥈 **프로**   | 눈썰미 프로  | 월간 Top 10        | 동색 메달 | 전용 뱃지               |
| 🥉 **루키**   | 관전 루키    | 월간 5회 이상 참여  | 초록 뱃지 | 참여 인정               |
| ⬜ **일반**   | —           | 그 외             | 없음      | —                     |

### 5-4. 혜택 체계

| 혜택 종류          |     대상     |          내용         |     비고     |
|-------------------|-------------|----------------------|--------------|
| **보너스 포인트**   | 마스터/챔피언 | 월말 추가 포인트 지급   | YAML에서 조정 |
| **전용 뱃지**      | 프로 이상     | 프로필에 영구 표시     | 월별 누적     |
| **명예의 전당**     | 마스터       | 역핑 메인에 닉네임 노출 | 월간         |
| **딜방 우선 알림**  | 챔피언 이상   | 신규 딜 개설 시 알림   | 참여 전환 유도 |
| **상금/쿠폰**       | 마스터       | 실물 보상 (운영 판단)  | v2에서 확정   |

### 5-5. YAML 파라미터 (랭커)

```yaml
  # ── 랭커 등급 ──
  ranks:
    tiers:
      - name: "master"
        label: "🏆 가격의 신"
        condition: "monthly_rank <= 1"
        badge: "gold_crown"
        bonus_points: 50
      - name: "champion"
        label: "🥇 시세 달인"
        condition: "monthly_rank <= 3"
        badge: "silver_medal"
        bonus_points: 20
      - name: "pro"
        label: "🥈 눈썰미 프로"
        condition: "monthly_rank <= 10"
        badge: "bronze_medal"
        bonus_points: 0
      - name: "rookie"
        label: "🥉 관전 루키"
        condition: "monthly_predictions >= 5"
        badge: "green_badge"
        bonus_points: 0

  # ── 랭킹 정렬 ──
  ranking:
    period: "monthly"               # "monthly" | "weekly"
    reset_day: 1                    # 매월 1일 리셋
    sort_by:
      - "total_points:desc"
      - "hit_rate:desc"
      - "predictions_count:desc"
    hall_of_fame: true              # 누적 명예의 전당
```

---

## 6. 데이터 모델 (DB)

### 6-1. spectator_predictions 테이블

```
spectator_predictions
├── id                  PK, auto
├── deal_id             FK → deals.id         (어떤 딜에 대한 예측)
├── buyer_id            FK → buyers.id        (예측한 구매자)
├── predicted_price     Integer, NOT NULL      (예측 가격, 원)
├── comment             Text, nullable         (예측 근거, 최대 200자)
├── created_at          DateTime               (제출 시각)
│
│   ── 판정 결과 (딜 성사 후 채워짐) ──
├── settled_price       Integer, nullable      (실제 성사 가격)
├── error_pct           Float, nullable        (오차율 %)
├── tier_name           String, nullable       (exact/close/good/participate/miss)
├── points_earned       Integer, default=0     (획득 포인트)
├── settled_at          DateTime, nullable     (판정 시각)
│
│   ── 제약 조건 ──
└── UNIQUE(deal_id, buyer_id)                  (딜당 1인 1예측)
```

### 6-2. spectator_monthly_stats 테이블

```
spectator_monthly_stats
├── id                  PK, auto
├── buyer_id            FK → buyers.id
├── year_month          String (예: "2026-02")
│
├── total_points        Integer, default=0
├── predictions_count   Integer, default=0     (참여 횟수)
├── hits_count          Integer, default=0     (적중 횟수, 1pt 이상)
├── exact_count         Integer, default=0     (정확 적중 횟수)
├── avg_error_pct       Float, nullable        (평균 오차율)
├── rank_tier           String, nullable       (master/champion/pro/rookie)
├── bonus_points        Integer, default=0     (등급 보너스)
│
└── UNIQUE(buyer_id, year_month)
```

### 6-3. spectator_badges 테이블

```
spectator_badges
├── id                  PK, auto
├── buyer_id            FK → buyers.id
├── badge_type          String                 (gold_crown/silver_medal/...)
├── year_month          String                 (어떤 달에 획득)
├── created_at          DateTime
```

---

## 7. API 엔드포인트 (예상)

### 7-1. 관전자 예측

```
POST /spectator/predict
Body: {
    "deal_id": 123,
    "buyer_id": 456,
    "predicted_price": 310000,
    "comment": "다나와 최저가 329,000 기준 공구 5% 할인 예상"  // 선택
}
Response: {
    "id": 789,
    "deal_id": 123,
    "predicted_price": 310000,
    "comment": "...",
    "created_at": "2026-02-27T10:30:00Z"
}
Errors:
  400 — 이미 예측 제출함 / 딜 참여자임 / 판매자임 / 딜 마감됨
  404 — 딜 없음
```

### 7-2. 예측 조회

```
GET /spectator/predictions/{deal_id}
- 딜 마감 전: 본인 예측만 반환
- 딜 마감 후: 전체 예측 + 판정 결과 반환

GET /spectator/my_predictions?buyer_id=456
- 내 전체 예측 이력
```

### 7-3. 랭킹

```
GET /spectator/rankings?year_month=2026-02
Response: {
    "rankings": [
        {
            "rank": 1,
            "buyer_id": 456,
            "nickname": "가격왕",
            "total_points": 320,
            "predictions_count": 42,
            "hits_count": 28,
            "hit_rate": 66.7,
            "exact_count": 3,
            "tier": "master",
            "badge": "gold_crown"
        },
        ...
    ]
}
```

### 7-4. 판정 트리거

```
POST /spectator/settle/{deal_id}     (내부/관리자용)
- 딜 성사 확정 시 호출
- 해당 딜의 모든 예측에 대해 적중 판정 수행
- spectator_predictions 테이블의 settled_* 컬럼 채움
- spectator_monthly_stats 업데이트
```

---

## 8. 비즈니스 로직 흐름

### 8-1. 전체 생명주기

```
[딜방 생성]
    │
    ▼
[관전자 예측 수집 기간]
    │  구매자 A: "310,000원" + "다나와 기준 공구 할인 예상"
    │  구매자 B: "305,000원"
    │  구매자 C: "320,000원" + "이 가격대가 적정"
    │
    ▼
[Offer 접수 → 거래 성사]
    │  성사 가격: 312,000원
    │
    ▼
[적중 판정]  ← settle 트리거
    │  A: |310,000 - 312,000| / 312,000 = 0.64% → ±1% → 3pt 🔥
    │  B: |305,000 - 312,000| / 312,000 = 2.24% → ±3% → 2pt 👍
    │  C: |320,000 - 312,000| / 312,000 = 2.56% → ±3% → 2pt 👍
    │
    ▼
[월간 통계 업데이트]
    │  A: 총 포인트 +3, 참여 +1, 적중 +1
    │
    ▼
[월말 랭킹 확정]
    │  1위 → 마스터 뱃지 + 보너스 50pt
    │
    ▼
[다음 달 리셋]
```

### 8-2. 예측 제출 시 검증 로직

```python
def validate_prediction(deal_id, buyer_id):
    # 1. 딜 존재 확인
    deal = get_deal(deal_id)
    if not deal or deal.status != "open":
        raise "딜이 열려있지 않음"

    # 2. 로그인 확인 + 구매자 확인
    buyer = get_buyer(buyer_id)
    if not buyer:
        raise "구매자 자격 없음"

    # 3. 딜 참여자가 아닌지 확인
    if is_deal_participant(deal_id, buyer_id):
        raise "딜 참여자는 예측 불가"

    # 4. 이미 예측했는지 확인
    existing = get_prediction(deal_id, buyer_id)
    if existing:
        raise "이미 예측 제출함 (1회 제한)"

    # 5. 가격 범위 확인
    if price < MIN_PRICE or price > MAX_PRICE:
        raise "가격 범위 초과"

    return OK
```

### 8-3. 적중 판정 로직

```python
def settle_predictions(deal_id):
    # 1. 성사 가격 확정
    settled_price = get_settled_price(deal_id)  # YAML pick 기준
    if not settled_price:
        return  # 성사 없으면 무효

    # 2. 해당 딜의 모든 예측 조회
    predictions = get_predictions_for_deal(deal_id)

    for pred in predictions:
        # 3. 오차율 계산
        error_pct = abs(pred.predicted_price - settled_price) / settled_price * 100

        # 4. 구간 판정 (YAML tiers 순회, 좁은 구간 우선)
        tier, points = judge_tier(error_pct)

        # 5. 결과 저장
        pred.settled_price = settled_price
        pred.error_pct = error_pct
        pred.tier_name = tier
        pred.points_earned = points
        pred.settled_at = now()

        # 6. 월간 통계 업데이트
        update_monthly_stats(pred.buyer_id, points, error_pct)
```

---

## 9. 관전자 예측의 딜방 내 활용

### 9-1. 딜 마감 전 — 집계 정보만 노출

딜방 참여자에게는 개별 예측값을 보여주지 않되, **집계 정보**는 노출 가능:

```
📊 현재 관전자 12명이 가격을 예측했습니다
```

이를 통해 딜방의 "관심도"를 보여줄 수 있다.

### 9-2. 딜 마감 후 — 전체 공개

```
📊 관전자 예측 결과
─────────────────────
예측 평균: 312,500원
예측 중앙값: 310,000원
예측 범위: 295,000 ~ 335,000원
참여 관전자: 12명
─────────────────────
🎯 구매자A: 310,000원 (오차 0.64%) — "다나와 기준 공구 할인 예상"
👍 구매자B: 305,000원 (오차 2.24%)
👍 구매자C: 320,000원 (오차 2.56%) — "이 가격대가 적정"
...
```

### 9-3. 핑퐁이 연동 (향후)

핑퐁이가 관전자 데이터를 활용하여 답변에 반영:

```
사용자: "이 딜 적정 가격이 얼마야?"
핑퐁이: "현재 12명의 관전자가 예측한 평균 가격은 312,500원이에요.
         네이버 최저가 329,000원 대비 약 5% 낮은 수준입니다."
```

---

## 10. 운영 고려사항

### 10-1. 어뷰징 방지

| 위험 | 대응 |
|------|------|
| 다중 계정으로 예측 범위 뿌리기 | 1인 1계정 정책 + 이상 패턴 모니터링 |
| 딜 참여자와 짜고 가격 맞추기 | 예측값은 마감 전 비공개 → 정보 교환 무의미 |
| 봇으로 자동 예측 | rate limit + captcha (v2) |

### 10-2. 엣지 케이스
  
|                상황           |                      처리                        |
|------------------------------|-------------------------------------------------|
| 딜이 성사 없이 마감             | 모든 예측 무효, 포인트 없음                         |
| 여러 Offer가 성사              | YAML의 `pick` 설정에 따라 기준가 결정 (기본: first) |
| 관전자가 예측 후 딜방 참여       | 예측 유효 유지, 추가 예측 불가                      |
| 딜 마감일 연장                 | 이미 예측한 건 유효, 새 관전자도 예측 가능            |
| 성사가가 극단적 (1원, 9999만원) | 오차율 계산은 동일하게 적용                          |

### 10-3. v1 → v2 로드맵

| 항목            | v1 (지금)          | v2 (향후)              |
|----------------|--------------------|-----------------------|
| 적중 판정       | 구간별 차등 포인트    | + 연속 적중 보너스      |
| 코멘트          | 단순 텍스트          | + 좋아요/추천 + 질 평가 |
| 랭커 혜택       | 뱃지 + 보너스 포인트  | + 상금/쿠폰/할인       |
| 핑퐁이 연동     | 없음                | 관전자 평균가 활용      |
| 관전자 팔로우    | 없음               | 상위 랭커 예측 알림      |
| 액추에이터 참여  | 불가                | 검토 가능              |

---

## 11. 파일 경로 (SSOT)

| 파일 | 경로 | 상태 |
|------|------|------|
| 정책 문서 (본 파일) | `app/policy/docs/admin/ssot/spectator.md` | ✅ 확정 |
| YAML 파라미터 | `app/policy/params/spectator.yaml` | 생성 예정 |
| 모델 | `app/models.py` (SpectatorPrediction 등) | 생성 예정 |
| 스키마 | `app/schemas.py` 또는 `app/schemas_spectator.py` | 생성 예정 |
| 라우터 | `app/routers/spectator.py` | 생성 예정 |
| 판정 로직 | `app/policy/spectator_settlement.py` | 생성 예정 |
| 랭킹 로직 | `app/policy/spectator_ranking.py` | 생성 예정 |

---

## 11-a. 관전자 결과 알림

### 11-a-1. settle 시 자동 알림 발송

딜 성사 확정(settle) 직후, 해당 딜에 예측을 제출한 모든 관전자에게 **결과 알림**을 자동 발송한다.

```python
# app/routers/spectator.py — settle 처리 후
def notify_spectator_results(db, deal_id, predictions):
    for pred in predictions:
        create_notification(
            db,
            user_id=pred.buyer_id,
            type="spectator_result",
            title=f"딜 #{deal_id} 관전 예측 결과가 나왔어요!",
            message=_build_result_message(pred),
            meta={
                "deal_id": deal_id,
                "predicted_price": pred.predicted_price,
                "settled_price": pred.settled_price,
                "tier_name": pred.tier_name,
                "tier_label": pred.tier_label,
                "points_earned": pred.points_earned,
                "error_pct": pred.error_pct,
            }
        )
```

### 11-a-2. 알림 메시지 템플릿

| 결과 | 메시지 예시 |
|------|------------|
| 정확 적중 (exact) | "완벽! 예측가 100,000원 = 성사가. +5pt 획득" |
| 근접 (close) | "근접! 예측가 98,500원, 성사가 100,000원 (오차 1.5%). +3pt 획득" |
| 우수 (good) | "우수! 오차 2.5%, +2pt 획득" |
| 참여 (participate) | "참여 인정! 오차 4.8%, +1pt 획득" |
| 미스 (miss) | "惜! 오차 7.2%, 이번엔 포인트가 없었어요. 다음 기회에!" |

### 11-a-3. 알림 구조 (UserNotification)

```
notification_type: "spectator_result"
meta:
  deal_id, predicted_price, settled_price,
  tier_name, tier_label, points_earned, error_pct
```

---

## 12. 미확정 사항 (결정 필요)

| # | 항목                | 선택지 | 현재 상태 |
|---|--------------------|----------------------------|---------------------------------------|
| 1 | 관전자 닉네임 표시    | 실명 / 닉네임 / 익명         | **닉네임 ✅ 확정** (2026-03-01)         |
| 2 | 마스터 실물 보상      | 상금 / 쿠폰 / 포인트만       | 포인트                                 |
| 3 | 포인트의 현금 가치     | 1pt = ?원                 | 1pt = 1원                             |
| 4 | 코멘트 노출 범위      | 딜방 내만 / 랭킹 페이지에도   | 랭킹 페이지도(포인트/닉네임/랭킹 등 클릭시) |
| 5 | 관전자 수 딜방 노출   | "12명이 지켜보는 중" / 비공개 | 공개                                   |
