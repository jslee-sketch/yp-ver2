# scripts/test_refund_preview_v36.py
import requests, json

BASE_URL = "http://localhost:9000"

def print_block(actor: str, rid: int):
    print("\n" + "=" * 30)
    print(f"▶ actor = {actor}")
    print("=" * 30)
    payload = {
        "reservation_id": rid,
        "actor": actor,
    }
    r = requests.post(f"{BASE_URL}/v3_6/reservations/refund/preview", json=payload)
    print("status:", r.status_code)
    try:
        print(json.dumps(r.json(), ensure_ascii=False, indent=2))
    except Exception:
        print(r.text)

def main():
    # 1) 이미 PAID 상태인 예약 id 하나 골라서 넣기
    #    방금 end-to-end에서 쓴 건 환불까지 해서 CANCELLED 됐으니까,
    #    새로 하나 만들고 그대로 PAID에서 멈춰두고 써도 되고,
    #    아니면 DB에서 status='PAID'인 reservation_id를 하나 보고 적어도 돼.
    rid = 72  # 예시: 실제로는 PAID 상태인 id로 바꿔줘

    for actor in ["buyer_cancel", "seller_cancel", "admin_force"]:
        print_block(actor, rid)

if __name__ == "__main__":
    main()