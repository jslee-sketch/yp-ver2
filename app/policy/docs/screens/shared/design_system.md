# 역핑 디자인 시스템 (Design System)

> 최종 수정: 2026-02-28  
> 기본 테마: 다크 네온 (Dark Neon)  
> 서브 테마: 클린 화이트 (Clean White)

---

## 1. 테마 구조

CSS 변수 기반 듀얼 테마. 코드는 하나, 색상만 스위칭.
사용자 설정 또는 시스템 설정(prefers-color-scheme)에 따라 전환.

### 1-1. 다크 네온 (기본값)

| 변수 | 값 | 용도 |
|------|---|------|
| --bg-primary | #0a0a0f | 최하위 배경 |
| --bg-secondary | #0f1419 | 카드/섹션 배경 |
| --bg-tertiary | rgba(255,255,255,0.03) | 서브카드/입력 필드 |
| --bg-elevated | rgba(255,255,255,0.06) | 호버/포커스 상태 |
| --text-primary | #e8eaed | 본문 텍스트 |
| --text-secondary | #b0bec5 | 섹션 제목/강조 |
| --text-muted | #607d8b | 라벨/보조 텍스트 |
| --text-disabled | #37474f | 비활성 텍스트 |
| --accent-green | #00e676 | 가격 절약, PASS, 긍정 |
| --accent-green-bg | rgba(0,230,118,0.12) | 녹색 배지 배경 |
| --accent-blue | #00b0ff | 목표가, 링크, 정보 |
| --accent-blue-bg | rgba(0,176,255,0.1) | 파란 배지 배경 |
| --accent-red | #ff5252 | 경고, 에러, 가격 상승 |
| --accent-orange | #ffb74d | 핑퐁이, 알림 |
| --accent-orange-bg | rgba(255,183,77,0.08) | 핑퐁이 카드 배경 |
| --accent-purple | #b388ff | 프리미엄 배지 |
| --border-subtle | rgba(255,255,255,0.06) | 카드 테두리 |
| --border-accent | rgba(0,230,118,0.15) | 강조 카드 테두리 |
| --gradient-price | linear-gradient(135deg, rgba(0,230,118,0.06), rgba(0,176,255,0.06)) | 가격 카드 배경 |
| --gradient-saving | linear-gradient(90deg, #00e676, #00b0ff) | 프로그레스 바/절약 |
| --gradient-pingpong | linear-gradient(135deg, rgba(255,183,77,0.08), rgba(255,152,0,0.05)) | 핑퐁이 카드 |
| --shadow-card | 0 2px 8px rgba(0,0,0,0.3) | 카드 그림자 |
| --shadow-elevated | 0 4px 16px rgba(0,0,0,0.5) | 모달/팝업 그림자 |

### 1-2. 클린 화이트 (라이트 모드)

| 변수 | 값 | 용도 |
|------|---|------|
| --bg-primary | #ffffff | 최하위 배경 |
| --bg-secondary | #f8fafb | 카드/섹션 배경 |
| --bg-tertiary | #f0f2f5 | 서브카드/입력 필드 |
| --bg-elevated | #e5e8eb | 호버/포커스 상태 |
| --text-primary | #191f28 | 본문 텍스트 |
| --text-secondary | #333d4b | 섹션 제목/강조 |
| --text-muted | #8b95a1 | 라벨/보조 텍스트 |
| --text-disabled | #b0b8c1 | 비활성 텍스트 |
| --accent-green | #2e7d32 | 가격 절약, PASS, 긍정 |
| --accent-blue | #3182f6 | 목표가, 링크, 추천 |
| --accent-red | #f04452 | 경고, 최저가 강조 |
| --accent-orange | #e65100 | 타이머, 긴급 |
| --accent-purple | #6b5ce7 | 프리미엄 |
| --border-subtle | #e5e8eb | 카드 테두리 |
| --border-accent | #3182f6 | 추천 카드 테두리 |
| --gradient-price | #f8fafb | 가격 카드 배경 (단색) |
| --gradient-saving | linear-gradient(135deg, #3182f6, #6b5ce7) | 절약 배지 |
| --gradient-pingpong | #f0f6ff | 핑퐁이 카드 배경 |
| --shadow-card | 0 1px 3px rgba(0,0,0,0.08) | 카드 그림자 |
| --shadow-elevated | 0 4px 12px rgba(0,0,0,0.12) | 모달/팝업 그림자 |

---

## 2. 타이포그래피

### 폰트
- 기본: Pretendard (-apple-system, BlinkMacSystemFont 폴백)
- 숫자 강조: Pretendard (고정폭 느낌의 tabular-nums 적용)
- 영문 라벨: Pretendard (letter-spacing: 1~3px, uppercase)

### 스케일

| 토큰 | 크기 | 굵기 | 용도 |
|------|------|------|------|
| display-lg | 28px | 800 | 메인 가격 |
| display-md | 22px | 800 | 오퍼 가격 |
| display-sm | 20px | 800 | 딜 제목 |
| heading-lg | 16px | 700 | 섹션 제목 |
| heading-md | 14px | 700 | 카드 제목 |
| heading-sm | 13px | 700 | 서브 제목 |
| body-md | 14px | 400 | 본문 |
| body-sm | 13px | 400 | 설명, 핑퐁이 텍스트 |
| caption-lg | 12px | 400~600 | 보조 정보 |
| caption-sm | 11px | 400 | 라벨, 조건 |
| micro | 10px | 700 | 영문 라벨 (uppercase) |
| tiny | 9px | 400 | 차트 라벨 |

### 줄 간격
- 본문: 1.6
- 핑퐁이 텍스트: 1.7
- 제목: 1.2
- 가격: 1.0

---

## 3. 간격 시스템 (Spacing)

4px 기준 배수:

| 토큰 | 값 | 용도 |
|------|---|------|
| space-xs | 4px | 인라인 요소 간격 |
| space-sm | 8px | 배지 간 간격, 아이콘-텍스트 |
| space-md | 12px | 카드 내부 요소 간격 |
| space-lg | 16px | 카드 패딩, 섹션 간 간격 |
| space-xl | 20px | 주요 섹션 패딩 |
| space-2xl | 24px | 페이지 좌우 패딩 |
| space-3xl | 32px | 섹션 간 대간격 |

---

## 4. 컴포넌트 규격

### 4-1. 카드 (Card)

| 속성 | 다크 | 라이트 |
|------|------|--------|
| border-radius | 12px~16px | 16px~20px |
| padding | 16px~20px | 16px~24px |
| border | 1px solid var(--border-subtle) | 1px solid var(--border-subtle) |
| background | var(--bg-tertiary) | var(--bg-secondary) |

카드 유형:
- **기본 카드**: 정보 표시용 (관전자 예측, 오퍼 목록)
- **강조 카드**: PREMIUM 오퍼, 가격 대시보드 (accent border + gradient bg)
- **액션 카드**: 클릭 가능 (호버 시 bg-elevated)
- **핑퐁이 카드**: 오렌지 계열 gradient + accent border

### 4-2. 배지 (Badge)

| 유형 | 다크 배경 | 다크 텍스트 | 라이트 배경 | 라이트 텍스트 |
|------|----------|------------|------------|--------------|
| LIVE | rgba(0,230,118,0.12) | #00e676 | #e8f5e9 | #2e7d32 |
| PREMIUM | rgba(0,230,118,0.15) | #00e676 | #3182f6 | #ffffff |
| 시간 | transparent | #607d8b | #fff3e0 | #e65100 |
| 관전 | transparent | #607d8b | #e3f2fd | #1565c0 |

크기: font-size 10~12px, padding 2~4px 6~10px, border-radius 3~20px

### 4-3. 프로그레스 바 (Progress)

```
높이: 6px
배경: var(--bg-elevated)
채움: var(--gradient-saving)
border-radius: 3px
애니메이션: width 1s ease
```

### 4-4. 바 차트 (관전자 예측 분포)

```
막대 높이: 비율 × 1.2~1.5px (최대 60px)
막대 색상: 기본 var(--bg-elevated), 최고값 var(--accent-green) gradient
간격: 2~4px
라벨: micro 크기, muted 색상
border-radius: 4px 4px 0 0
```

### 4-5. 버튼

| 유형 | 배경 | 텍스트 | border-radius |
|------|------|--------|---------------|
| Primary | var(--accent-green) | #0a0a0f | 12px |
| Secondary | var(--bg-elevated) | var(--text-primary) | 12px |
| Ghost | transparent | var(--accent-blue) | 8px |
| Danger | var(--accent-red) | #ffffff | 12px |

높이: 44px (터치 영역), font-size: 14px, font-weight: 700

### 4-6. 입력 필드

```
배경: var(--bg-tertiary)
border: 1px solid var(--border-subtle)
border-radius: 12px
padding: 12px 16px
font-size: 14px
포커스: border-color var(--accent-blue)
```

### 4-7. 핑퐁이 위젯

```
위치: 화면 하단 또는 딜 상세 내 인라인
배경: var(--gradient-pingpong)
border: 1px solid rgba(255,183,77,0.2) (다크) / 1px solid #d4e5ff (라이트)
border-radius: 12px
패딩: 16px
아이콘: 🤖 (추후 커스텀 아바타로 교체)
제목 색상: var(--accent-orange) (다크) / var(--accent-blue) (라이트)
텍스트: body-sm, line-height 1.7
```

---

## 5. 아이콘 시스템

이모지 기반 (MVP):

| 용도 | 아이콘 |
|------|--------|
| 시장가 | 📊 |
| 목표가 | 🎯 |
| 최저 오퍼 | ⚡ |
| 관전자 | 👀 |
| 핑퐁이 | 🤖 |
| 절약 | 🔥 |
| 오퍼 | 🏷️ |
| 별점 | ⭐ |
| 배송 | 📦 |
| 알림 | 🔔 |
| 라이브 | ● (녹색 텍스트) |

추후 Lucide React 또는 커스텀 SVG 아이콘으로 교체 가능.

---

## 6. 모션/애니메이션

| 대상 | 속성 | 지속시간 | 이징 |
|------|------|---------|------|
| 카드 호버 | background, border-color | 0.2s | ease |
| 프로그레스 바 | width | 1s | ease |
| 차트 막대 | height | 0.5s | ease-out |
| 가격 변경 | color flash | 0.3s | ease |
| 페이지 진입 | opacity, translateY | 0.3s | ease-out |
| 오퍼 도착 알림 | slideIn + fadeIn | 0.4s | cubic-bezier(0.16,1,0.3,1) |
| 핑퐁이 타이핑 | 점 3개 반복 | 1.4s | infinite |

---

## 7. 반응형 중단점

| 토큰 | 너비 | 대상 |
|------|------|------|
| mobile-sm | ~375px | iPhone SE |
| mobile | 376~428px | 일반 스마트폰 |
| mobile-lg | 429~768px | 큰 스마트폰/소형 태블릿 |
| tablet | 769~1024px | 태블릿 |
| desktop | 1025px~ | 데스크톱 (추후) |

MVP는 **mobile (376~428px) 기준** 설계, mobile-sm/mobile-lg 대응.
태블릿/데스크톱은 Phase 2.

---

## 8. 네비게이션 구조

### 하단 탭 바 (Bottom Tab Bar)

| 순서 | 아이콘 | 라벨 | 화면 |
|------|--------|------|------|
| 1 | 🏠 | 홈 | 홈 피드 (라이브 딜 목록) |
| 2 | 🔍 | 검색 | 딜 검색/필터 |
| 3 | ➕ | 딜 생성 | 딜 생성 (중앙, 강조) |
| 4 | 📋 | 내 딜 | 마이 딜 히스토리 |
| 5 | 👤 | MY | 마이페이지 |

```
높이: 56px + safe-area-bottom
배경: var(--bg-primary) + border-top 1px var(--border-subtle)
활성 탭: var(--accent-green) 아이콘 + 텍스트
비활성: var(--text-muted)
딜 생성 버튼: 원형 44px, var(--accent-green) 배경, 약간 위로 돌출
```

### 상단 헤더 (Top Bar)

```
높이: 48px + safe-area-top
좌측: 뒤로가기 또는 로고
중앙: 페이지 제목 (선택)
우측: 알림 아이콘 (🔔 + 읽지 않은 수 배지)
```

---

## 9. 상태 색상 매핑

### 딜 상태

| 상태 | 다크 색상 | 라이트 색상 | 의미 |
|------|----------|------------|------|
| OPEN | #00e676 | #2e7d32 | 진행 중 |
| CLOSED | #607d8b | #8b95a1 | 마감 |
| EXPIRED | #37474f | #b0b8c1 | 만료 |
| CANCELLED | #ff5252 | #f04452 | 취소 |

### 오퍼 티어

| 티어 | 다크 배경 | 다크 텍스트 | 의미 |
|------|----------|------------|------|
| PREMIUM | rgba(0,230,118,0.08) + accent border | #00e676 | 시장가 대비 우수 |
| MATCHING | var(--bg-tertiary) | var(--text-primary) | 시장가 수준 |
| BELOW | var(--bg-tertiary) | var(--text-muted) | 시장가 미만 |

### 관전자 판정 티어

| 티어 | 색상 | 의미 |
|------|------|------|
| PERFECT | #ffd700 (금색) | 정확히 적중 |
| EXCELLENT | #00e676 | 오차 3% 이내 |
| GOOD | #00b0ff | 오차 5% 이내 |
| FAIR | #ffb74d | 오차 10% 이내 |
| MISS | #607d8b | 10% 초과 |

### 정산 상태

| 상태 | 색상 | 의미 |
|------|------|------|
| HOLD | #ffb74d | 대기 |
| READY | #00b0ff | 준비 |
| APPROVED | #00e676 | 승인 |
| PAID | #b388ff | 지급 완료 |
| CANCELLED | #ff5252 | 취소 |

---

## 10. 테마 전환 구현

```javascript
// 테마 토글
function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('yp-theme', next);
}

// 초기화 (시스템 설정 우선, 사용자 설정 오버라이드)
function initTheme() {
  const saved = localStorage.getItem('yp-theme');
  if (saved) {
    document.documentElement.setAttribute('data-theme', saved);
  } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
  // 기본값: dark (속성 없으면 dark)
}
```
