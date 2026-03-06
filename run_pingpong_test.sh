#!/bin/bash
# Pingpong 50-question test runner
BASE="http://127.0.0.1:9000/v3_6/pingpong/ask"
OUT="pingpong_50_test_results.md"

questions=(
  "안녕"
  "오늘 기분이 좋아"
  "카리나는 어느 그룹이야?"
  "맛있는 저녁 메뉴 추천해줘"
  "핑퐁이 넌 누구야?"
  "역핑은 어떤 플랫폼이야?"
  "딜방이 뭐야?"
  "오퍼가 뭐야?"
  "액츄에이터가 뭐야?"
  "관전자는 뭐하는 사람이야?"
  "환불 정책 알려줘"
  "환불 가능 기간이 며칠이야?"
  "배송 전에 환불 가능해?"
  "배송 후에도 환불 돼?"
  "부분 환불도 가능해?"
  "결제 제한시간이 몇 분이야?"
  "정산은 언제 되나요?"
  "쿨링 기간이 뭐야?"
  "수수료는 얼마야?"
  "포인트는 어떻게 적립돼?"
  "오퍼 마감이 몇 시간이야?"
  "딜방 모집 기간은?"
  "오퍼 수정 가능해?"
  "오퍼 취소는 어떻게 해?"
  "딜방은 어떻게 만들어?"
  "예약번호 13번 환불 가능해?"
  "딜 15번 상태가 어때?"
  "오퍼 10번 마감 언제야?"
  "내 포인트 잔액 얼마야?"
  "예약 7번 배송 어디까지 왔어?"
  "오늘 서울 날씨 어때?"
  "미국 관련 뉴스 알려줘"
  "갤럭시 S25 최저가 얼마야?"
  "환율 알려줘"
  "에어팟 프로 가격 비교해줘"
  "딜 만들고 싶은데 어떻게 해?"
  "오퍼 중에 어떤 걸 선택하면 좋아?"
  "배송이 안 오면 어떻게 해?"
  "리뷰는 어디서 써?"
  "분쟁 신청하고 싶어"
  "오퍼를 어떻게 제출해?"
  "정산 내역은 어디서 확인해?"
  "배송 처리는 어떻게 하나요?"
  "구매자가 환불 요청했는데 어떻게 해?"
  "내 판매 수수료율이 얼마야?"
  "김치 먹다가 갤럭시 봤는데 가격이 궁금해"
  "쿨링 기간 지나면 정산 돼?"
  "환불하면 포인트도 돌려받아?"
  "역핑이랑 쿠팡이랑 뭐가 달라?"
  "판매자 등급이 올라가면 수수료가 달라져?"
)

echo "# 핑퐁이 50개 대화 실제 테스트 결과" > "$OUT"
echo "# 일시: $(date '+%Y-%m-%d %H:%M')" >> "$OUT"
echo "" >> "$OUT"
echo "| # | 질문 | 답변 (200자) | engine | 판정 |" >> "$OUT"
echo "|---|------|-------------|--------|------|" >> "$OUT"

pass=0
fail=0

for i in "${!questions[@]}"; do
  num=$((i+1))
  q="${questions[$i]}"

  # Build JSON body
  body=$(python -c "import json; print(json.dumps({'question': '''$q''', 'screen': 'home', 'context': {}, 'mode': 'read_only'}, ensure_ascii=False))")

  # Call API
  resp=$(curl -s --max-time 30 -X POST "$BASE" \
    -H "Content-Type: application/json" \
    -d "$body" 2>/dev/null)

  if [ $? -ne 0 ] || [ -z "$resp" ]; then
    answer="ERROR: 응답 없음"
    engine="error"
    verdict="FAIL"
  else
    # Extract answer and engine using python
    read answer engine <<< $(python -c "
import json, sys
try:
    d = json.loads('''$resp'''.replace(\"'\", \"\\\\'\"))
except:
    try:
        d = json.loads(sys.stdin.read())
    except:
        d = {}
a = (d.get('answer') or '(빈 답변)').replace('|', '/').replace('\n', ' ')[:200]
e = d.get('engine', 'unknown')
print(a)
print(e)
" <<< "$resp" 2>/dev/null)

    if [ -z "$answer" ]; then
      answer="(파싱 실패)"
      engine="error"
    fi

    # Determine pass/fail
    if echo "$answer" | grep -qiE "확인 중이에요|네트워크 연결|ERROR"; then
      verdict="FAIL"
    else
      verdict="PASS"
    fi
  fi

  [ "$verdict" = "PASS" ] && pass=$((pass+1)) || fail=$((fail+1))

  echo "| $num | $q | $answer | $engine | $verdict |" >> "$OUT"
  echo "[$num/50] $verdict - $q"
done

echo "" >> "$OUT"
echo "## 요약: PASS=$pass / FAIL=$fail / 총 50개" >> "$OUT"
echo ""
echo "=== 결과 저장: $OUT ==="
echo "PASS: $pass / FAIL: $fail"
