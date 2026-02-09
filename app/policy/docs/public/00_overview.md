# 역핑(Yeokping) 플랫폼 설명서 (Public)

## 한 줄 요약
역핑은 **소비자가 원하는 가격/조건을 먼저 제시**하고, 판매자들이 **경쟁적으로 제안(Offer)** 하는 **소비자 주도형 역입찰 공동구매 플랫폼**입니다.

## 역핑이 해결하려는 문제(WHY)
- “정가를 보고 고민” → “내가 원하는 가격을 제시하고 시장 반응을 받는 구조”로 전환
- 가격뿐 아니라 배송/환불/조건까지 한 화면에서 비교 → 숨은 비용과 후회 감소
- 신뢰(리뷰/등급/분쟁/정산) 체계를 운영 레벨에서 강제 → 거래 안정성 강화

## 핵심 용어
- 딜방(Deal Room): 구매자 수요가 모이는 방(가격/수량/조건 제시)
- 오퍼(Offer): 판매자가 내는 가격/조건 제안
- 예약(Reservation): 특정 오퍼를 구매자가 잡아두는 거래 단위(결제와 연결)
- 환불/분쟁: 귀책/상태/정책에 따라 처리(서버 SSOT가 확정)
- 정산(Settlement): 판매자/액추에이터 등에 지급되는 흐름(쿨링 포함)

## 시간 정책(정본)
- 런타임 SSOT: app/policy/params/defaults.yaml
- 설명 SSOT: app/policy/docs/public/time.md

## 다음 문서
- buyer.md / seller.md / actuator.md / recommender.md
- fees.md / tiers.md / refund.md / shipping.md
- pingpong.md (핑퐁이 안내)
