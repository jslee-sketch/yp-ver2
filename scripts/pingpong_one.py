import json, urllib.request

BASE="http://127.0.0.1:9000"
payload={"screen":"admin","question":"정산 READY/APPROVED/PAID 흐름 설명해줘"}

req=urllib.request.Request(
  BASE+"/v3_6/pingpong/ask",
  data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
  headers={"Content-Type":"application/json; charset=utf-8"},
  method="POST"
)
with urllib.request.urlopen(req,timeout=30) as r:
  raw=r.read().decode("utf-8", errors="replace")
  obj=json.loads(raw)

print("ANSWER:", obj.get("answer"))
print("USED_POLICIES:", obj.get("used_policies"))
print("ACTIONS:", obj.get("actions"))
print("DEBUG:", json.dumps(obj.get("debug",{}), ensure_ascii=False, indent=2))
