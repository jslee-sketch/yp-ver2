import os, json, requests, random, string
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:9000")
DEAL_ID  = int(os.getenv("DEAL_ID", "1"))
OFFER_ID = int(os.getenv("OFFER_ID", "46"))
BUYER_ID = int(os.getenv("BUYER_ID", "10"))

def post(path, payload, headers=None):
    r = requests.post(f"{BASE}{path}", json=payload, headers=headers or {}, timeout=5)
    return r.status_code, r.text

def make_key():
    return "resv-" + "".join(random.choices(string.ascii_letters + string.digits, k=12))

def worker(i):
    idem = make_key()
    code, _ = post("/reservations", {
        "deal_id": DEAL_ID, "offer_id": OFFER_ID, "buyer_id": BUYER_ID, "qty": 1, "hold_minutes": 3
    }, headers={"Idempotency-Key": idem})
    return code

def main():
    N = int(os.getenv("N", "30"))  # 동시 N건 예약 시도
    with ThreadPoolExecutor(max_workers=N) as ex:
        futs = [ex.submit(worker, i) for i in range(N)]
        results = [f.result() for f in as_completed(futs)]
    print("codes:", json.dumps(sorted(results), ensure_ascii=False))

if __name__ == "__main__":
    main()