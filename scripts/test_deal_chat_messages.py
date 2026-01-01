# scripts/test_deal_chat_messages.py
import requests
import json

BASE_URL = "http://localhost:9000"  # 서버 주소/포트에 맞게 조정


def pretty_print(resp: requests.Response):
    print("status:", resp.status_code)
    try:
        print(json.dumps(resp.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(resp.text)


def send_message(deal_id: int, buyer_id: int, text: str):
    print("\n============================")
    print(f"▶ POST /deals/{deal_id}/chat/messages (buyer_id={buyer_id})")
    print("============================")
    url = f"{BASE_URL}/deals/{deal_id}/chat/messages"
    payload = {
        "buyer_id": buyer_id,
        "text": text,
    }
    resp = requests.post(url, json=payload)
    pretty_print(resp)


def list_messages(deal_id: int, buyer_id: int, q: str | None = None):
    print("\n============================")
    print(f"▶ GET /deals/{deal_id}/chat/messages (buyer_id={buyer_id}, q={q})")
    print("============================")
    url = f"{BASE_URL}/deals/{deal_id}/chat/messages"
    params = {
        "buyer_id": buyer_id,
        "limit": 50,
        "offset": 0,
    }
    if q:
        params["q"] = q
    resp = requests.get(url, params=params)
    pretty_print(resp)


def main():
    deal_id = 1     # 테스트용 딜 ID
    buyer_id = 1    # 테스트용 바이어 ID

    # 1) 정상 메시지
    send_message(deal_id, buyer_id, "안녕하세요, 이 딜 가격 어떻게 보세요?")

    # 2) 욕설/전화번호/계좌번호 케이스도 한 번씩 테스트 가능
    #    (필요하면 주석 풀고 써봐도 됨)
    # send_message(deal_id, buyer_id, "씨발 이 가격 뭐냐")      # 욕설 → blocked 기대
    # send_message(deal_id, buyer_id, "010-1234-5678 연락주세요")  # 전화번호 → blocked 기대
    # send_message(deal_id, buyer_id, "우리은행 1002-123-456789")  # 계좌 비슷한 형식 → blocked 기대

    # 3) 전체 메시지 목록 조회
    list_messages(deal_id, buyer_id)

    # 4) 검색어(q) 걸어서 필터링 조회
    list_messages(deal_id, buyer_id, q="가격")


if __name__ == "__main__":
    main()