# analyze_simulation_viz.py
import json
import os
from datetime import datetime
import matplotlib.pyplot as plt

# -----------------------
# 1️⃣ JSON 로드
# -----------------------
JSON_PATH = "simulation_results_fullflow_v3_4.json"
assert os.path.exists(JSON_PATH), f"❌ {JSON_PATH} not found."

with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

meta = data.get("meta", {})
buyers = data.get("buyers", [])
sellers = data.get("sellers", [])
deals = data.get("deals", [])
participants = data.get("participants", [])
deal_summary = data.get("deal_summary", [])
points = data.get("point_balances", {})

print("\n✅ Loaded simulation data version:", meta.get("version"))
print("📦 Total Deals:", len(deals))
print("👥 Buyers:", len(buyers))
print("🏢 Sellers:", len(sellers))
print("🧾 Participants:", len(participants))

# -----------------------
# 2️⃣ Deal 요약 테이블 출력
# -----------------------
print("\n📊 DEAL SUMMARY")
print("-" * 60)
for ds in deal_summary:
    print(f"📦 {ds['product_name']:<25} | 참가자 {ds['participants']:>2}명 | 오퍼 {ds['offers']:>2}개")

# -----------------------
# 3️⃣ 분석용 디렉토리 준비
# -----------------------
OUTPUT_DIR = "analysis_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# -----------------------
# 4️⃣ 그래프 1: Deal별 참여자 & Offer 수
# -----------------------
deal_names = [d["product_name"] for d in deal_summary]
participant_counts = [d["participants"] for d in deal_summary]
offer_counts = [d["offers"] for d in deal_summary]

plt.figure(figsize=(8, 5))
plt.bar(deal_names, participant_counts, label="Participants", alpha=0.7)
plt.bar(deal_names, offer_counts, label="Offers", alpha=0.7)
plt.title("Deal별 참여자 수 & Offer 수")
plt.ylabel("Count")
plt.legend()
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"deal_participants_offers_{timestamp}.png"))
plt.close()

# -----------------------
# 5️⃣ 그래프 2: Buyer 포인트
# -----------------------
buyer_points = points.get("buyers", {})
plt.figure(figsize=(8, 4))
plt.bar([f"Buyer {k}" for k in buyer_points.keys()], buyer_points.values(), color="skyblue")
plt.title("Buyer 포인트 변화")
plt.ylabel("Points")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"buyer_points_{timestamp}.png"))
plt.close()

# -----------------------
# 6️⃣ 그래프 3: Seller 포인트
# -----------------------
seller_points = points.get("sellers", {})
plt.figure(figsize=(8, 4))
plt.bar([f"Seller {k}" for k in seller_points.keys()], seller_points.values(), color="lightcoral")
plt.title("Seller 포인트 변화")
plt.ylabel("Points")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, f"seller_points_{timestamp}.png"))
plt.close()

# -----------------------
# 7️⃣ 결과 요약
# -----------------------

# analyze_simulation_viz.py (수정 버전 상단에 추가)
import json, os
print("🚀 분석 스크립트 시작")

JSON_PATH = "simulation_results_fullflow_v3_4.json"
print("📂 현재 디렉토리:", os.getcwd())

if not os.path.exists(JSON_PATH):
    print(f"❌ 파일을 찾을 수 없습니다: {JSON_PATH}")
    exit()

print("✅ 파일 존재 확인 완료")

print("\n📈 그래프 저장 완료:")
for file in os.listdir(OUTPUT_DIR):
    if file.endswith(".png"):
        print("   -", os.path.join(OUTPUT_DIR, file))

print("\n✅ 분석 완료! →", OUTPUT_DIR)