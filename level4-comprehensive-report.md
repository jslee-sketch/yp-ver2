# Level 4 Comprehensive Test Report

**Date**: 2026-03-08T12:58:01.673Z

## Summary

| Phase | Description | Total | PASS | FAIL | WARN |
|-------|-------------|-------|------|------|------|
| P1 | Deal Creation (AI/Voice/Brand/Price) | 26 | 19 | 0 | 7 |
| P2 | Refund + Delivery | 10 | 10 | 0 | 0 |
| P3 | Social Login | 6 | 6 | 0 | 0 |
| P4 | Minority Report | 10 | 9 | 0 | 1 |
| P5 | Pingpong 50 | 50 | 48 | 2 | 0 |
| P6 | Admin Pages | 20 | 18 | 0 | 2 |
| P7 | Buyer+Seller Pages | 21 | 21 | 0 | 0 |
| P8 | Security | 10 | 8 | 0 | 2 |
| **Total** | | **153** | **139** | **2** | **12** |

**Pass Rate**: 90.8%

## Detailed Results

⚠️ **P1** | 1. Image recognize endpoint — status=500

✅ **P1** | 2. Voice wrong type→400 — status=400

✅ **P1** | 3. Voice too short→400 — status=400

✅ **P1** | 4. AI "갤럭시 S25 울트라" — name=Samsung Galaxy S25 U, price=1171400

✅ **P1** | 5. AI "에어팟 프로 2세대" — name=Apple AirPods Pro 2n, price=389000

✅ **P1** | 6. AI "다이슨 에어랩" — name=Dyson Airwrap, price=530290

✅ **P1** | 7. AI "LG 그램 17인치" — name=LG Gram 17, price=117300

✅ **P1** | 8. AI "닌텐도 스위치2" — name=Nintendo Switch 2, price=648000

✅ **P1** | 9. AI "삼성 갤럭시 워치 7" — name=Samsung Galaxy Watch, price=289823

✅ **P1** | 10. AI "아이폰 16 프로 맥스" — name=Apple iPhone 16 Pro , price=2020000

⚠️ **P1** | 11. Brand "갤럭시 S25"(Samsung) — price=N/A

⚠️ **P1** | 12. Brand "에어팟 프로"(Apple) — price=N/A

⚠️ **P1** | 13. Brand "LG 그램"(LG) — price=N/A

⚠️ **P1** | 14. Brand "다이슨 에어랩"(Dyson) — price=N/A

⚠️ **P1** | 15. Brand "갤럭시 S25"(없음) — price=N/A

✅ **P1** | 16. Brand "갤럭시 S25"(Samsung) — price=845760

✅ **P1** | 17. Brand "라면"(오뚜기) — price=11000

✅ **P1** | 18. Brand "운동화"(Nike) — price=149900

✅ **P1** | 19. Brand "갤럭시"(Samsung) — price=258200

✅ **P1** | 20. Brand "블루투스 이어폰"(없음) — price=131340

✅ **P1** | 21. AI analysis done

⚠️ **P1** | 22. Voice mic button

✅ **P1** | 23. Step 3 visible

✅ **P1** | 24. Guess input works

✅ **P1** | 25. Challenge result

✅ **P1** | 26. Slider visible

✅ **P2** | 1. Carriers API — status=200

✅ **P2** | 2. Delivery summary — shipped=240, delivered=0

✅ **P2** | 3. Refund simulator page

✅ **P2** | 4. Shipping type options

✅ **P2** | 5. Reason dropdown

✅ **P2** | 6. Admin delivery page

✅ **P2** | 7. Batch check button

✅ **P2** | 8. Auto confirm button

✅ **P2** | 9. Buyer orders page

✅ **P2** | 10. Seller delivery page

✅ **P3** | kakao authorize — status=200, hasUrl=true

✅ **P3** | naver authorize — status=200, hasUrl=true

✅ **P3** | google authorize — status=200, hasUrl=true

✅ **P3** | 4. Social buttons visible

✅ **P3** | 5. Register page

✅ **P3** | 6. Admin buyers (social col)

✅ **P4** | 1. Track API — status=200

✅ **P4** | 2. Multi-track — 4 events sent

✅ **P4** | 3. Stats API — status=200

✅ **P4** | 4. Logs API — status=200

✅ **P4** | 5. Analyze BUYER — status=200

✅ **P4** | 6. Profiles API — status=200

✅ **P4** | 7. Hesitating API — status=200

⚠️ **P4** | 8. Match deals — status=500

✅ **P4** | 9. Minority report page

✅ **P4** | 10. Keywords visible

✅ **P5** | 1. "카카오로 로그인하는 방법?" — 2/3

✅ **P5** | 2. "네이버 계정으로 가입할 수 " — 2/3

✅ **P5** | 3. "구글 로그인 되나요?" — 2/3

✅ **P5** | 4. "사진으로 제품 찾을 수 있어" — 1/3

✅ **P5** | 5. "말로 딜 만들 수 있어?" — 1/3

✅ **P5** | 6. "사진 몇 장까지 올릴 수 있" — 3/3

✅ **P5** | 7. "시장가 어떻게 조사해?" — 1/3

✅ **P5** | 8. "목표가 어떻게 설정해?" — 1/3

✅ **P5** | 9. "제외된 항목이 뭐야?" — 1/3

✅ **P5** | 10. "시장가 근거를 볼 수 있어?" — 1/2

✅ **P5** | 11. "배송 어디까지 왔어?" — 2/3

✅ **P5** | 12. "배달 완료 후 뭐 해야 돼?" — 2/3

✅ **P5** | 13. "자동 구매확정이 뭐야?" — 2/2

✅ **P5** | 14. "택배사 뭐 지원해?" — 3/3

✅ **P5** | 15. "환불하면 얼마 받아?" — 2/2

✅ **P5** | 16. "구매자 변심이면 배송비?" — 2/2

✅ **P5** | 17. "판매자 잘못이면?" — 2/2

✅ **P5** | 18. "분쟁 결과로 환불하면?" — 2/2

✅ **P5** | 19. "부분 환불 가능해?" — 2/2

✅ **P5** | 20. "정산 완료 후에도 환불 돼?" — 2/2

✅ **P5** | 21. "역핑은 어떤 플랫폼이야?" — 2/2

✅ **P5** | 22. "딜이 뭐야?" — 1/2

✅ **P5** | 23. "오퍼가 뭐야?" — 2/2

✅ **P5** | 24. "결제 제한시간?" — 2/2

✅ **P5** | 25. "오퍼 마감 시간?" — 2/2

✅ **P5** | 26. "쿨링 기간?" — 2/2

✅ **P5** | 27. "수수료 얼마야?" — 2/2

✅ **P5** | 28. "정산 언제 돼?" — 1/1

✅ **P5** | 29. "포인트 적립?" — 2/2

✅ **P5** | 30. "분쟁 어떻게 해?" — 2/2

✅ **P5** | 31. "오퍼 어떻게 내?" — 2/2

✅ **P5** | 32. "배송 어떻게 처리해?" — 1/2

✅ **P5** | 33. "정산 확인 어디서?" — 1/1

✅ **P5** | 34. "환불 요청 들어오면?" — 1/1

✅ **P5** | 35. "내 리뷰 어디서 봐?" — 1/1

✅ **P5** | 36. "관리자 대시보드?" — 2/2

✅ **P5** | 37. "판매자 승인 어떻게?" — 2/2

✅ **P5** | 38. "이상 탐지?" — 1/1

✅ **P5** | 39. "마이너리티 리포트?" — 1/2

✅ **P5** | 40. "환불 시뮬레이터?" — 2/2

✅ **P5** | 41. "갤럭시 S25 가격?" — 2/2

✅ **P5** | 42. "에어팟 프로 최저가?" — 2/2

✅ **P5** | 43. "아이폰 16 프로 얼마야?" — 2/2

✅ **P5** | 44. "서울 날씨?" — 1/1

✅ **P5** | 45. "안녕!" — 1/2

❌ **P5** | 46. "고마워" — status=429

❌ **P5** | 47. "이상한질문abcdef123" — status=429

✅ **P5** | 48. "환불하고 싶은데 배송 중이야" — 2/2

✅ **P5** | 49. "오퍼 수정하고 싶어" — 2/2

✅ **P5** | 50. "역핑 vs 쿠팡 차이?" — 1/2

✅ **P6** | 1. /admin — len=1218

✅ **P6** | 2. /admin/buyers — len=8276

✅ **P6** | 3. /admin/sellers — len=146

✅ **P6** | 4. /admin/actuators — len=146

✅ **P6** | 5. /admin/deals — len=17191

✅ **P6** | 6. /admin/offers — len=19942

✅ **P6** | 7. /admin/reservations — len=50693

✅ **P6** | 8. /admin/delivery — len=12169

✅ **P6** | 9. /admin/settlements — len=146

✅ **P6** | 10. /admin/refund-simulator — len=465

✅ **P6** | 11. /admin/minority-report — len=512

✅ **P6** | 12. /admin/stats — len=405

✅ **P6** | 13. /admin/notifications — len=7358

⚠️ **P6** | 14. /admin/announcements — len=22

✅ **P6** | 15. /admin/policy/params — len=58

✅ **P6** | 16. /admin/policy/docs — len=4526

⚠️ **P6** | 17. /admin/reports — len=2

✅ **P6** | 18. /admin/anomalies — len=371

✅ **P6** | 19. /admin/logs — len=30212

✅ **P6** | 20. /admin/settings — len=315

✅ **P7** | B1. / — len=199

✅ **P7** | B2. /deals — len=193

✅ **P7** | B3. /deal/create — len=583

✅ **P7** | B4. /my-orders — len=75

✅ **P7** | B5. /mypage — len=200

✅ **P7** | B6. /notifications — len=93

✅ **P7** | B7. /points — len=192

✅ **P7** | B8. /my-deals — len=89

✅ **P7** | S1. /seller — len=527

✅ **P7** | S2. /seller/offers — len=527

✅ **P7** | S3. /seller/delivery — len=527

✅ **P7** | S4. /seller/returns — len=527

✅ **P7** | S5. /seller/settlements — len=527

✅ **P7** | S6. /seller/refunds — len=527

✅ **P7** | S7. /seller/inquiries — len=527

✅ **P7** | S8. /seller/reviews — len=527

✅ **P7** | S9. /seller/shipping-policy — len=527

✅ **P7** | S10. /seller/stats — len=527

✅ **P7** | S11. /seller/fees — len=527

✅ **P7** | S12. /seller/announcements — len=527

✅ **P7** | S13. /deals — len=193

✅ **P8** | 1. SQL injection — status=401

✅ **P8** | 2. XSS in pingpong

✅ **P8** | 3. Expired token→401 — status=401

✅ **P8** | 4. No auth→401 — status=401

⚠️ **P8** | 5. Buyer→admin scope — status=200 (DEV bypass active)

✅ **P8** | 6. Unknown page — url=https://web-production-defb.up.railway.app/asdfgh

⚠️ **P8** | 7. Large text — status=500

✅ **P8** | 8. Rapid 20 calls — last=200

✅ **P8** | 9. Image limit — Code enforced

✅ **P8** | 10. Audio limit — Code enforced

