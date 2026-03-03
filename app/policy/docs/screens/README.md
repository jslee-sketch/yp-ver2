# 역핑 화면 설계 문서 인덱스

> 이 폴더는 역핑 프론트엔드 화면별 UX/UI 설계 문서를 관리한다.
> 각 문서는 해당 화면의 API 연동, 컴포넌트 구성, 상태별 변화, Mock 데이터를 정의한다.

---

## 공통 (shared/)

| 파일 | 내용 |
|------|------|
| [design_system.md](shared/design_system.md) | 디자인 시스템 전체 — 테마(다크 네온/클린 화이트), 타이포그래피, 간격, 컴포넌트 규격, 아이콘, 모션, 반응형 중단점 |

---

## 구매자 화면 (buyer/)

| 파일 | 우선순위 | 구현 상태 | 내용 |
|------|----------|----------|------|
| [home_feed.md](buyer/home_feed.md) | ★★★★☆ | ✅ 구현됨 | 홈 피드 — 실시간 피드 띠, 마감 임박 딜, 인기 딜 카드, 관전자 랭킹 미니 위젯 |
| [deal_detail.md](buyer/deal_detail.md) | ★★★★★ | ✅ 구현됨 | 딜 상세 — 가격 대시보드, 관전자 예측 분포, 오퍼 목록(티어별), 핑퐁이 인사이트 |

---

## 추가 예정 화면

| 화면 | 우선순위 | 파일명 (예정) |
|------|----------|--------------|
| 딜 생성 | ★★★★★ | buyer/deal_create.md |
| 오퍼 상세 바텀 시트 | ★★★★☆ | buyer/offer_detail_sheet.md |
| 관전자 예측 입력 | ★★★★☆ | buyer/spectator_predict_sheet.md |
| 딜 검색/필터 | ★★★★☆ | buyer/search.md |
| 마이 딜 히스토리 | ★★★☆☆ | buyer/my_deals.md |
| 마이페이지 | ★★★☆☆ | buyer/my_page.md |
| 관전자 랭킹 전체 | ★★★☆☆ | buyer/spectator_rankings.md |
| 핑퐁이 채팅 바텀 시트 | ★★★☆☆ | shared/pingpong_chat_sheet.md |
| 판매자 대시보드 | ★★★☆☆ | seller/seller_dashboard.md |
| 오퍼 제출 | ★★★☆☆ | seller/offer_submit.md |

---

## 프론트엔드 구현 위치

```
C:\dev\yp-ver2\frontend\src\
├── pages/          ← 화면 단위 컴포넌트
├── components/     ← 재사용 UI 컴포넌트
│   ├── common/     ← Badge, PriceText, ProgressBar, BarChart, PingpongCard
│   ├── deal/       ← PriceDashboard, OfferCard, OfferList, SpectatorPanel, DealHeader
│   ├── home/       ← LiveTicker, DealCard, ClosingSoonList, RankingWidget, MySummaryCard
│   └── layout/     ← Layout, TopBar, BottomTabBar
├── api/client.ts   ← axios 인스턴스 (baseURL: http://127.0.0.1:9000)
├── types/index.ts  ← TypeScript 타입 정의
└── styles/theme.css← 디자인 시스템 CSS 변수
```
