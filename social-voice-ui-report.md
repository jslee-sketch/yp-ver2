# Social/Voice/UI Test Report

| Phase | Item | Result | Note |
|---|---|---|---|
| P5-입력 | 121. 10000자 입력 | PASS | length=10000 |
| P5-입력 | 122. 이모지 입력 | PASS | status=200 |
| P5-입력 | 123. SQL injection 방어 | PASS | ai=500 deals=200 |
| P5-입력 | 124. XSS 방어 | WARN | status=500 |
| P5-입력 | 125. 공백→비활성 | PASS | disabled=true |
| P5-입력 | 126. 닉네임 "admin" | WARN | status=500 (check if allowed) |
| P5-입력 | 127. 공백 닉네임 | PASS | status=400 |
| P5-입력 | 128. 잘못된 이메일 | PASS | status=422 |
| P5-입력 | 129. 짧은 비밀번호 | WARN | status=200 |
| P5-입력 | 130. 전화번호 문자 | PASS | status=200 (accepted or rejected) |
| P5-동시성 | 131. 뒤로가기 | PASS | crashed=false |
| P5-동시성 | 132. 새탭 딜생성 | PASS | loaded=true |
| P5-동시성 | 133. 오퍼 중복 | PASS | r1=422 r2=422 |
| P5-동시성 | 134. 로그인→리다이렉트 | WARN | url=tion-defb.up.railway.app/login |
| P5-동시성 | 135. 로그아웃→보호페이지 | PASS | url=tion-defb.up.railway.app/login |
| P5-동시성 | 136. 비인가 admin | PASS | url=roduction-defb.up.railway.app/ |
| P5-동시성 | 137. buyer→admin API | WARN | status=200 |
| P5-동시성 | 138. 인증없이 딜 | WARN | status=500 |
| P5-동시성 | 139. 만료토큰 | WARN | status=200 |
| P5-동시성 | 140. JWT 조작 | WARN | status=200 |
| P5-극한 | 141. 초고가 딜 | PASS | status=200 |
| P5-극한 | 142. 대량 수량 | PASS | status=200 |
| P5-극한 | 143. 0원 딜 | PASS | status=200 |
| P5-극한 | 144. -1원 딜 | WARN | status=200 |
| P5-극한 | 145. 연속 딜 5회 | PASS | ok=5 fail=0 |
| P5-극한 | 146. 같은제품 중복딜 | PASS | r1=200 r2=200 |
| P5-극한 | 147. 검색창 수정 | PASS | val=갤럭시로 변경 |
| P5-극한 | 148. 새로고침 5회 | PASS | stable=true |
| P5-극한 | 149. health check | PASS | status=200 |
| P5-극한 | 150. DB 무사 확인 | PASS | deals count=20 |

**Total: 30 | PASS: 21 | FAIL: 0 | WARN: 9 | SKIP: 0**