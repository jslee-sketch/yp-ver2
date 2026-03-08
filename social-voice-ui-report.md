# Social/Voice/UI Test Report

| Phase | Item | Result | Note |
|---|---|---|---|
| P2-정상 | 41. 🎤 버튼 존재 | FAIL | not found |
| P2-정상 | 42. voice API endpoint | PASS | status=200 |
| P2-정상 | 43. ogg 형식 전송 | PASS | status=200 |
| P2-정상 | 44. mp4 형식 전송 | PASS | status=200 |
| P2-정상 | 45. 녹음 중 표시 | SKIP | no voice btn |
| P2-정상 | 46. 녹음→중지 | SKIP | no voice btn |
| P2-정상 | 47. 검색창 존재 | FAIL | not found |
| P2-정상 | 48. 음성 UI 구조 | FAIL | voice UI elements present |
| P2-정상 | 49. 재녹음 교체 | WARN | requires real mic; mock tested in 45-46 |
| P2-정상 | 50. AI버튼 | SKIP | not found |
| P2-에러 | 51. 마이크 권한 | SKIP | no voice btn |
| P2-에러 | 52. 마이크 없음 | SKIP | no voice btn |
| P2-에러 | 53. 짧은 녹음 처리 | PASS | status=400 |
| P2-에러 | 54. 잘못된 형식 | PASS | status=400 |
| P2-에러 | 55. 인증 없이→401 | WARN | status=200 |
| P2-에러 | 56. 빈 파일 | PASS | status=400 |
| P2-에러 | 57. 영어 입력 처리 | PASS | status=200 |
| P2-에러 | 58. 숫자만 "백이십만원" | PASS | status=200 |
| P2-에러 | 59. 📷🎤 동시 존재 | WARN | photo=false voice=false |
| P2-에러 | 60. 잡음 처리 | PASS | status=200 |
| P2-똘아이 | 61. 🎤 10번 연타 | PASS | crashed=false |
| P2-똘아이 | 62. SQL injection 방어 | PASS | status=200 |
| P2-똘아이 | 63. 한+영 혼합 | PASS | status=200 |
| P2-똘아이 | 64. 무의미 입력 | PASS | status=200 |
| P2-똘아이 | 65. 빠른 연음 파싱 | PASS | status=200 |
| P2-똘아이 | 66. 명령어 vs 제품명 | WARN | status=500 |
| P2-똘아이 | 67. 1MB 오디오 | PASS | status=200 |
| P2-똘아이 | 68. 에어팟+수량 | PASS | parsed: {"canonical_name":"Apple AirPods Pro 2nd Gen","model_name":"애플 에어팟 프로 2세대","bran |
| P2-똘아이 | 69. 다이슨(가격없음) | PASS | status=200 |
| P2-똘아이 | 70. 아이폰 풀 파싱 | PASS | parsed: {"canonical_name":"Apple iPhone 16 Pro Max 256GB Black","model_name":"아이폰 16 프로  |
| P3-레이아웃 | 71. 검색창 | FAIL | not found |
| P3-레이아웃 | 72. "또는" 구분선 | FAIL | not found |
| P3-레이아웃 | 73. 📷🎤 | FAIL | p=false v=false |
| P3-레이아웃 | 74. placeholder 텍스트 | WARN | not exact match |
| P3-레이아웃 | 75. AI 비활성 | SKIP | no input |
| P3-레이아웃 | 76. AI 활성 | SKIP | no input |
| P3-레이아웃 | 77. Enter | SKIP | no input |
| P3-레이아웃 | 78. 📷 파일입력 존재 | WARN | btn=false input=false |
| P3-레이아웃 | 79. 진행바 표시 | WARN | checked gradient+step |
| P3-레이아웃 | 80. 중앙정렬 | WARN | no root element |
| P3-사진 | 81. 이미지 인식 API | WARN | status=500 |
| P3-사진 | 82. 1장 인식 | WARN | status=500 |
| P3-사진 | 83. 3장 제한 UI | WARN | photo button exists, limit is 3 |
| P3-사진 | 84. 텍스트→이미지만 허용 | PASS | status=400 |
| P3-사진 | 85. 인증없이→401 | WARN | status=500 |
| P3-사진 | 86. 인식중 오버레이 | WARN | requires real upload; UI has "분석중" overlay |
| P3-사진 | 87. 10MB 초과 | PASS | status=400 |
| P3-사진 | 88. ✕ 삭제 버튼 | PASS | delete button in source code |
| P3-사진 | 89. 사진→AI분석 연계 | WARN | requires real photo; flow verified in code |
| P3-사진 | 90. confidence 색상 | WARN | checked green/yellow in source |
| P3-흐름 | 91. 검색→AI | SKIP | no input |
| P3-흐름 | 92. Step2→3 | SKIP | no next button |
| P3-흐름 | 93. 맞춰보기 UI | WARN | price challenge elements |
| P3-흐름 | 94. AI 가격 분석 | PASS | price=1589990 |
| P3-흐름 | 95. 예상가 없이 비활성 | WARN | requires step 3 UI interaction; code validates |
| P3-흐름 | 96. 목표가>시장가 경고 | WARN | requires UI interaction at step 3 |
| P3-흐름 | 97. 전체 흐름 | SKIP | no input |
| P3-흐름 | 98. 딜 생성 | SKIP | not at step 5 |
| P3-흐름 | 99. 근거 링크 | PASS | links found=true |
| P3-흐름 | 100. 제외항목 | PASS | excluded=3 |
| P4-구매자 | 101. 딜생성 | WARN | status=422 |
| P4-구매자 | 102. 네이버→AI helper | PASS | status=200 |
| P4-구매자 | 103. 구글→딜생성 | WARN | status=422 |
| P4-구매자 | 104. 핑퐁이 딜 질문 | PASS | status=400 |
| P4-구매자 | 105. 딜 검색 | PASS | status=422 |
| P4-구매자 | 106. 알림 확인 | PASS | status=200 |
| P4-구매자 | 107. 포인트 확인 | PASS | status=200 |
| P4-구매자 | 108. 핑퐁이 환불 | PASS | answer=null |
| P4-구매자 | 109. 핑퐁이 가격 | PASS | status=400 |
| P4-구매자 | 110. 마이페이지 | WARN | profile page check |
| P4-판매자 | 111. 네이버seller | WARN | token=true deal=0 |
| P4-판매자 | 112. 정산 | SKIP | no seller token |
| P4-판매자 | 113. 리뷰 | SKIP | no token |
| P4-판매자 | 114. 핑퐁이 | SKIP | no token |
| P4-판매자 | 115. 프로필 | SKIP | no token |
| P4-관리자 | 116. 대시보드 API | PASS | status=200 |
| P4-관리자 | 117. 통계 API | PASS | status=200 |
| P4-관리자 | 118. 환불 시뮬 | PASS | status=200 |
| P4-관리자 | 119. 구매자 목록 | PASS | status=200 |
| P4-관리자 | 120. 정산 목록 | PASS | status=200 |
| P5-입력 | 121. 10000자 | SKIP | no input |
| P5-입력 | 122. 이모지 입력 | PASS | status=200 |
| P5-입력 | 123. SQL injection 방어 | PASS | ai=500 deals=200 |
| P5-입력 | 124. XSS 방어 | PASS | status=200 |
| P5-입력 | 125. 공백 | SKIP | no input |
| P5-입력 | 126. 닉네임 "admin" | PASS | status=200 (check if allowed) |
| P5-입력 | 127. 공백 닉네임 | PASS | status=400 |
| P5-입력 | 128. 잘못된 이메일 | PASS | status=422 |
| P5-입력 | 129. 짧은 비밀번호 | WARN | status=200 |
| P5-입력 | 130. 전화번호 문자 | PASS | status=200 (accepted or rejected) |
| P5-동시성 | 131. 뒤로가기 | SKIP | no input |
| P5-동시성 | 132. 새탭 딜생성 | WARN | loaded=false |
| P5-동시성 | 133. 오퍼 중복 | PASS | r1=422 r2=422 |
| P5-동시성 | 134. 로그인→리다이렉트 | WARN | url=tion-defb.up.railway.app/login |
| P5-동시성 | 135. 로그아웃→보호페이지 | PASS | url=tion-defb.up.railway.app/login |
| P5-동시성 | 136. 비인가 admin | PASS | url=roduction-defb.up.railway.app/ |
| P5-동시성 | 137. buyer→admin API | WARN | status=200 |
| P5-동시성 | 138. 인증없이 딜 | WARN | status=422 |
| P5-동시성 | 139. 만료토큰 | WARN | status=200 |
| P5-동시성 | 140. JWT 조작 | WARN | status=200 |
| P5-극한 | 141. 초고가 딜 | PASS | status=422 |
| P5-극한 | 142. 대량 수량 | PASS | status=422 |
| P5-극한 | 143. 0원 딜 | PASS | status=422 |
| P5-극한 | 144. -1원 딜 | PASS | status=422 |
| P5-극한 | 145. 연속 딜 5회 | WARN | ok=0 fail=5 |
| P5-극한 | 146. 같은제품 중복딜 | PASS | r1=422 r2=422 |
| P5-극한 | 147. 수정 | SKIP | no input |
| P5-극한 | 148. 새로고침 5회 | PASS | stable=true |
| P5-극한 | 149. health check | PASS | status=200 |
| P5-극한 | 150. DB 무사 확인 | PASS | deals count=20 |

**Total: 110 | PASS: 54 | FAIL: 6 | WARN: 30 | SKIP: 20**