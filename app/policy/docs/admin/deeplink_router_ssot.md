# 딥링크 라우팅 SSOT

## 목적
본 문서는 역핑 앱 내 프리뷰 화면으로 이동하기 위한 딥링크 규격의 단일 진실원본(SSOT)이다.

---

## 기본 원칙
- 딥링크는 앱 전용이다.
- 웹 URL은 제공하지 않는다.
- ID 기반 질문은 항상 딥링크를 포함한다.

---

## 딥링크 스키마
yeokping://preview/{entity}/{id}/{topic}

### entity
- reservation
- offer
- dealroom

### topic
- refund
- payment
- shipping
- summary

---

## 예시
- 예약 환불 프리뷰  
  `yeokping://preview/reservation/403/refund`

- 예약 배송 프리뷰  
  `yeokping://preview/reservation/403/shipping`

- 딜방 프리뷰  
  `yeokping://preview/dealroom/77`

---

## 실패 시 원칙
- 서버 조회 실패 여부와 무관하게 딥링크는 제공한다.
- "정확한 정보는 화면에서 확인" 문구와 함께 사용한다.
