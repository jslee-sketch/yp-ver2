"""
Pingpongi 100Q Save - 새 100문항 + 실제 답변 전문 저장
API: POST /v3_6/pingpong/ask
"""
import json, time, urllib.request, urllib.error, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = "https://www.yeokping.com"
ENDPOINT = f"{BASE}/v3_6/pingpong/ask"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = PROJECT_ROOT / "pingpongi_100q_results.json"

def http_post(url, payload, timeout=45):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read() if hasattr(e, "read") else b""
        return e.code, raw.decode("utf-8", errors="replace")
    except Exception as ex:
        return 0, str(ex)

def ask(question, role="buyer", screen="GENERAL"):
    payload = {
        "user_id": 1, "role": role, "screen": screen,
        "context": {"deal_id": None, "reservation_id": None, "offer_id": None},
        "question": question, "locale": "ko", "mode": "read_only", "max_chat_messages": 10,
    }
    status, text = http_post(ENDPOINT, payload)
    if status == 200:
        try:
            return status, json.loads(text).get("answer", "")
        except Exception:
            return status, text
    return status, text

QUESTIONS = [
    {"id":"Q001","question":"환불은 언제까지 가능해요?","expected":["7일","90일","쿨링","영업일","기간"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q002","question":"환불 신청하면 바로 돈 돌아와요?","expected":["영업일","승인","검수","PG","3~5","처리"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q003","question":"배송비는 누가 부담해요?","expected":["변심","구매자","판매자","귀책","바이어","셀러"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q004","question":"무료배송 상품 환불하면 배송비 얼마 차감돼요?","expected":["왕복","원복","반품","배송비","바이어"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q005","question":"유료배송 상품 환불하면 원래 배송비 돌려받나요?","expected":["환불","배송비","귀책","사유"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q006","question":"환불 금액을 미리 알 수 있어요?","expected":["시뮬레이터","미리","계산","환불"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q007","question":"판매자가 환불 거절하면 어떻게 해요?","expected":["분쟁","AI","중재","신청"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q008","question":"판매자가 환불 요청 무시하면요?","expected":["자동","영업일","승인","타임아웃"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q009","question":"환불 시 감가가 뭐예요?","expected":["검수","감가","사용","차감"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q010","question":"개봉만 했는데 감가 적용돼요?","expected":["감가","사용","검수","판매자","확인"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q011","question":"미배송이면 어떻게 해요?","expected":["전액","반품","환불","셀러"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q012","question":"배송 전에 취소하면요?","expected":["전액","취소","환불","차감"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q013","question":"환불 신청 후 취소할 수 있어요?","expected":["취소","승인","가능","전"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q014","question":"부분 환불도 되나요?","expected":["부분","환불","가능","정액","정률"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q015","question":"환불받으면 포인트도 돌려받나요?","expected":["포인트","환불","차감","적립"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q016","question":"환불 진행 상황을 어디서 확인해요?","expected":["상세","타임라인","진행","my-orders","주문"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q017","question":"수령 후 8일째인데 환불 가능한가요? 단순변심이에요.","expected":["불가","7일","초과","쿨링","기간"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q018","question":"수령 후 8일인데 품질불량이에요. 환불 가능?","expected":["가능","90일","귀책","불량","셀러"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q019","question":"여러 번 환불 신청해도 되나요?","expected":["환불","예약","단위","중복"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q020","question":"환불 시뮬레이터는 어디서 써요?","expected":["시뮬레이터","환불","메뉴","refund"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q021","question":"교환은 어떻게 해요?","expected":["교환","반품","검수","재발송","요청"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q022","question":"교환하면 추가 비용 있어요?","expected":["귀책","배송비","교환","부담"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q023","question":"교환 상품은 언제 와요?","expected":["영업일","검수","교환","발송"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q024","question":"교환 상품도 추적 가능해요?","expected":["추적","운송장","배송","교환"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q025","question":"교환받은 상품도 불량이면요?","expected":["분쟁","신청","재교환","환불"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q026","question":"교환 대신 환불로 바꿀 수 있어요?","expected":["변경","가능","환불","교환","전환"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q027","question":"교환 시 정산은 어떻게 돼요?","expected":["정산","변경","유지","교환"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q028","question":"판매자가 교환 상품 안 보내면요?","expected":["관리자","영업일","타임아웃","자동"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q029","question":"교환 상품 색상 변경 가능?","expected":["협의","판매자","교환","동일"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q030","question":"교환 중 환불로 전환 가능?","expected":["가능","환불","전환","교환"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q031","question":"반품 주소는 어디서 확인해요?","expected":["판매자","안내","반품","주소"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q032","question":"반품 운송장은 어디에 입력해요?","expected":["상세","입력","운송장","반품"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q033","question":"반품 기한은 얼마예요?","expected":["7일","기한","영업일","반품"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q034","question":"반품 기한 넘기면 어떻게 돼요?","expected":["자동","종결","타임아웃","취소"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q035","question":"반품 배송비는 얼마예요?","expected":["배송비","반품","부담","귀책","원"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q036","question":"판매자가 반품 수령 안 했다고 하면?","expected":["운송장","추적","증거","관리자"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q037","question":"반품 검수에서 FAIL 나오면?","expected":["관리자","개입","감가","검수"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q038","question":"반품 시 포장은 어떻게 해야 해요?","expected":["포장","반품","원래","상태"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q039","question":"반품 추적은 실시간인가요?","expected":["추적","배송","운송장","실시간","택배"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q040","question":"반품 없이 환불 가능한 경우는?","expected":["미배송","소액","반품","불필요"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q041","question":"분쟁 신청은 어떻게 해요?","expected":["신청","사유","증거","분쟁"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q042","question":"분쟁 제안은 자유롭게 쓸 수 있어요?","expected":["유형","선택","정액","정률","구조","금액","제안"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q043","question":"AI 중재는 어떻게 작동해요?","expected":["양쪽","분석","법","공정","AI","중재"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q044","question":"AI 중재가 편향되지는 않나요?","expected":["법","공정","양쪽","AI","중재","분석"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q045","question":"분쟁 Round 2가 뭐예요?","expected":["거절","재반론","2","Round","라운드"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q046","question":"2라운드까지 합의 안 되면?","expected":["법적","소액","소비자원","LEGAL","안내","미합의"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q047","question":"분쟁 기한은 얼마예요?","expected":["영업일","3","2","기한","마감"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q048","question":"기한 넘기면 어떻게 돼요?","expected":["자동","종결","타임아웃","경고"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q049","question":"분쟁 중 정산은 어떻게 돼요?","expected":["보류","HOLD","정산","분쟁"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q050","question":"분쟁 합의하면 자동으로 환불돼요?","expected":["자동","PG","정산","환불","처리"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q051","question":"분쟁에서 교환을 제안할 수 있어요?","expected":["교환","선택","가능","제안","유형"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q052","question":"AI가 제안한 금액이 마음에 안 들면?","expected":["거절","Round 2","재반론","2라운드"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q053","question":"증거는 뭘 올릴 수 있어요?","expected":["사진","동영상","텍스트","증거","첨부"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q054","question":"분쟁 신청하면 상대방에게 알림 가요?","expected":["알림","영업일","분쟁","통지"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q055","question":"분쟁 중 취소할 수 있어요?","expected":["취소","가능","분쟁","철회"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q056","question":"분쟁 결과에 불복하면?","expected":["2라운드","법적","Round","재반론","소비자원"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q057","question":"빨리 합의하면 뭐가 좋아요?","expected":["영업일","빨리","정산","합의","처리"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q058","question":"정액과 정률 차이가 뭐예요?","expected":["정액","원","정률","%","금액","비율"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q059","question":"배송비 부담은 어떻게 정해요?","expected":["선택","귀책","AI","셀러","바이어","부담"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q060","question":"분쟁 이력은 어디서 봐요?","expected":["마이페이지","내역","타임라인","분쟁","상세"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q061","question":"정산은 언제 되나요?","expected":["구매확정","쿨링","7일","정산","영업일"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q062","question":"환불되면 정산 어떻게 돼요?","expected":["재계산","차감","Clawback","정산","환불"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q063","question":"Clawback이 뭐예요?","expected":["지급","차기","차감","환수","Clawback"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q064","question":"수수료도 돌려받나요? (판매자)","expected":["수수료","환급","환불","정산"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q065","question":"정산이 LEGAL_HOLD면 뭔 뜻이에요?","expected":["미합의","법적","보류","분쟁","정산"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q066","question":"정산 취소되면 세금계산서도 바뀌나요?","expected":["수정","세금","계산서","정산"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q067","question":"부분 환불이면 정산 얼마 줄어요?","expected":["환불","수수료","차감","정산","금액"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q068","question":"Clawback이 잔액보다 크면?","expected":["부분","이월","다음","차감","Clawback"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q069","question":"Clawback 3번 실패하면?","expected":["관리자","수동","Clawback","처리"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q070","question":"정산 보류 중에 다른 거래 정산은 정상?","expected":["해당","정상","건","정산"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q071","question":"교환이면 정산 어떻게 돼요?","expected":["보류","해제","변경","정산","교환","유지"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q072","question":"보상금이면 정산 어떻게 돼요?","expected":["차감","정산","보상","환불"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q073","question":"환불 시뮬레이터에서 정산 영향도 볼 수 있어요?","expected":["판매자","관리자","영향","시뮬레이터","정산"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q074","question":"정산 조정 내역은 어디서 봐요?","expected":["대시보드","내역","이력","정산","조회"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q075","question":"수수료율이 얼마예요?","expected":["2","3.5","%","레벨","수수료"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q076","question":"역핑의 환불 정책이 다른 곳과 다른 점은?","expected":["AI","시뮬레이터","수수료","역핑","환불"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q077","question":"환불 정책은 어디서 볼 수 있어요?","expected":["가이드","정책","환불","약관"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q078","question":"예약할 때 환불 정책 동의하나요?","expected":["동의","체크","예약","환불"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q079","question":"주말에 환불 신청하면?","expected":["접수","영업일","환불","처리"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q080","question":"핑퐁이가 환불 도와줄 수 있어요?","expected":["안내","시뮬레이터","분쟁","환불","핑퐁"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q081","question":"관리자가 직접 환불 처리할 수도 있어요?","expected":["ADMIN","수동","관리자","환불","처리"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q082","question":"PG 환불이 안 되면 어떻게 해요?","expected":["재시도","관리자","수동","PG","환불"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q083","question":"반품 택배사는 어디 써야 해요?","expected":["택배","운송장","반품","아무"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q084","question":"여러 상품 중 하나만 환불 가능해요?","expected":["예약","단위","부분","환불"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q085","question":"해외에서도 환불 가능해요?","expected":["가능","배송비","환불","해외"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q086","question":"환불받으면 알림 오나요?","expected":["알림","완료","환불","notification"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q087","question":"판매자가 부당하게 검수 FAIL 주면?","expected":["관리자","개입","재검수","분쟁","신청"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q088","question":"돈쭐 상품권도 환불 돼요?","expected":["돈쭐","별도","기부","환불"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q089","question":"환불 중에 판매자가 탈퇴하면?","expected":["탈퇴","미처리","보류","환불","관리자"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q090","question":"포인트로 산 상품 환불하면?","expected":["포인트","환불","차감","환급"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q091","question":"사용 감가는 일수 기준이죠?","expected":["검수","판매자","감가","상태","확인"],"fail_keywords":["일수 기준으로","days_since","하루당"],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q092","question":"환불하면 정산은 어떻게 되나요? 그냥 취소?","expected":["CANCEL","DEDUCT","CLAWBACK","차감","재계산","정산"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q093","question":"분쟁 합의하면 그 다음은 수동 처리죠?","expected":["자동","PG","정산","환불","처리"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q094","question":"교환 프로세스가 있나요?","expected":["반품","검수","재발송","교환","프로세스"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q095","question":"분쟁 미합의되면 끝인가요?","expected":["LEGAL","관리자","법적","소비자원","안내"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q096","question":"이미 정산된 건에서 환불하면?","expected":["Clawback","차기","차감","환수","정산"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
    {"id":"Q097","question":"판매자가 환불 거절하면 구매자는 방법이 없나요?","expected":["분쟁","AI","2라운드","중재","신청"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q098","question":"환불 금액에 배송비가 포함되나요?","expected":["사유","배송","다름","귀책","포함"],"fail_keywords":[],"role":"buyer","screen":"REFUND_FLOW"},
    {"id":"Q099","question":"분쟁 제안은 텍스트로 쓰나요?","expected":["유형","선택","금액","구조","정액","정률","제안"],"fail_keywords":[],"role":"buyer","screen":"GENERAL"},
    {"id":"Q100","question":"수수료는 환불 시 돌려받나요? (판매자)","expected":["수수료","환급","환불","정산"],"fail_keywords":[],"role":"seller","screen":"GENERAL"},
]

# Graceful decline keywords (KB gap but not wrong)
GRACEFUL = ["찾지 못했", "안내드리기 어렵", "정보를 찾지", "궁금한 점"]

def judge(answer, expected, fail_kw):
    if not answer or not answer.strip():
        return "ERROR"
    for fk in fail_kw:
        if fk in answer:
            return "FAIL"
    for ek in expected:
        if ek.lower() in answer.lower():
            return "PASS"
    for g in GRACEFUL:
        if g in answer:
            return "WARN"
    return "WARN"

def main():
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', errors='replace')
    print(f"Endpoint: {ENDPOINT}")
    print(f"Questions: {len(QUESTIONS)}")
    print("=" * 60)

    results = []
    counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "ERROR": 0}

    for q in QUESTIONS:
        status, answer = ask(q["question"], role=q.get("role","buyer"), screen=q.get("screen","GENERAL"))
        if status != 200:
            verdict = "ERROR"
            answer = f"HTTP {status}: {answer[:200]}"
        else:
            verdict = judge(answer, q["expected"], q["fail_keywords"])
        counts[verdict] += 1

        tag = {"PASS":"OK","FAIL":"XX","WARN":"??","ERROR":"!!"}[verdict]
        print(f"  [{tag}] {q['id']}: {q['question'][:42]:<44} -> {verdict}")
        if verdict in ("FAIL","ERROR"):
            print(f"       {answer[:120]}")

        results.append({
            "index": q["id"],
            "question": q["question"],
            "answer": answer,
            "status": verdict,
            "expected_keywords": q["expected"],
            "fail_keywords": q["fail_keywords"],
        })
        time.sleep(0.5)

    print("\n" + "=" * 60)
    total = len(QUESTIONS)
    print(f"PASS: {counts['PASS']}  FAIL: {counts['FAIL']}  WARN: {counts['WARN']}  ERROR: {counts['ERROR']}  / {total}")
    pct = counts['PASS'] / total * 100
    print(f"Pass rate: {pct:.1f}%")

    output = {
        "test_date": datetime.now(timezone(timedelta(hours=9))).isoformat(),
        "endpoint": ENDPOINT,
        "summary": {"total": total, **counts, "pass_rate_pct": round(pct, 1)},
        "results": results,
    }
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {OUT_PATH}")
    return 0 if counts["FAIL"] == 0 else 1

if __name__ == "__main__":
    raise SystemExit(main())
